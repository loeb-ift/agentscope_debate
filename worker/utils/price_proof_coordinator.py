"""
Price Proof Coordinator
負責協調多來源股價驗證，實作 Waterfall Fallback 機制。
優先級: TEJ (高精度) -> TWSE (官方備援) -> Yahoo (外部備援)
"""

from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
import asyncio
import json

from adapters.integration.tej_price_client import TejPriceClient
from adapters.twse_adapter import TWSEStockDay
from adapters.yahoo_adapter import YahooPriceAdapter
from adapters.chinatimes_suite import ChinaTimesStockRTAdapter
from worker.utils.symbol_utils import normalize_symbol
from api.redis_client import get_redis_client

class PriceProofCoordinator:
    def __init__(self):
        from adapters.alpha_vantage_mcp_adapter import AlphaVantageMCPAdapter

        self.tej_client = TejPriceClient()
        self.twse_adapter = TWSEStockDay()
        self.yahoo_adapter = YahooPriceAdapter()
        self.chinatimes_adapter = ChinaTimesStockRTAdapter()
        self.redis = get_redis_client()
        
        # Initialize Alpha Vantage (Optional)
        try:
            self.av_adapter = AlphaVantageMCPAdapter()
        except Exception as e:
            print(f"[PriceProof] Alpha Vantage Init Failed (Skipping): {e}")
            self.av_adapter = None

    def _get_cached_symbol(self, raw_symbol: str) -> Optional[str]:
        """Check if we have a cached mapped symbol (e.g. 5371 -> 5371.TWO)"""
        try:
            return self.redis.get(f"symbol_map:{raw_symbol}")
        except Exception as e:
            print(f"[PriceProof] Redis Read Error: {e}")
            return None

    def _cache_symbol(self, raw_symbol: str, mapped_symbol: str):
        """Cache successful mapping for 7 days"""
        try:
            self.redis.setex(f"symbol_map:{raw_symbol}", 604800, mapped_symbol)
        except Exception as e:
            print(f"[PriceProof] Redis Write Error: {e}")

    def get_verified_price(self, symbol: str, date: str = None, lookback_days: int = 5) -> Dict[str, Any]:
        """
        獲取經過驗證的股價數據 (同步方法 Wrapper)
        """
        return asyncio.run(self.get_verified_price_async(symbol, date, lookback_days))

    async def get_verified_price_async(self, symbol: str, date: str = None, lookback_days: int = 5) -> Dict[str, Any]:
        """
        獲取經過驗證的股價數據 (非同步)
        
        策略:
        1. 嘗試 ChinaTimes (最優先，即時/盤中)。
        2. 若 ChinaTimes 無法滿足 (如需歷史)，嘗試 TWSE (官方)。
        3. 若 TWSE 失敗，嘗試 Yahoo (外部)。
        4. 若 Yahoo 失敗，嘗試 TEJ (歷史庫)。
        """
        # 1. Date Calculation
        target_date = date or datetime.now().strftime("%Y-%m-%d")
        
        # Determine start/end date for range query (to handle holidays/weekends)
        # We query a small window to ensure we find the nearest trading day
        end_date_dt = datetime.strptime(target_date, "%Y-%m-%d")
        start_date_dt = end_date_dt - timedelta(days=lookback_days)
        
        start_date_str = start_date_dt.strftime("%Y-%m-%d")
        end_date_str = target_date # Inclusive for most adapters
        
        # 2. Symbol Normalization
        norm_res = normalize_symbol(symbol)
        clean_symbol = norm_res["coid"] # Plain ID (e.g. 2330)
        yahoo_ticker = norm_res.get("yahoo_ticker", clean_symbol) # Proper ticker for Yahoo (e.g. 8069.TWO)
        market = norm_res.get("market", "TW")
        exchange = norm_res.get("exchange", "Unknown")

        # [Cache Check] If we have a better mapping cached, use it
        cached_ticker = self._get_cached_symbol(clean_symbol)
        if cached_ticker:
            yahoo_ticker = cached_ticker
            if cached_ticker.endswith('.TWO'):
                exchange = 'TPEx' # Infer exchange from cached suffix
            print(f"[PriceProof] Using Cached Symbol Mapping: {clean_symbol} -> {yahoo_ticker}")

        print(f"[PriceProof] Fetching {clean_symbol} (Yahoo: {yahoo_ticker}, Exch: {exchange}) for {target_date} (Window: {start_date_str} ~ {end_date_str})")
        
        # --- Source 1: ChinaTimes (Realtime/Latest) ---
        # Check if target_date is today or future (meaning we want latest)
        is_latest_request = (target_date >= datetime.now().strftime("%Y-%m-%d"))
        
        if is_latest_request:
            try:
                print("[PriceProof] Trying ChinaTimes (Realtime)...")
                ct_res = self.chinatimes_adapter.invoke(code=clean_symbol)
                # Handle ToolResult object or dict
                ct_data = ct_res.data if hasattr(ct_res, 'data') else ct_res.get("data")
                
                if ct_data and ct_data.get("Price"):
                    # Use NowDate from API, or fallback to target_date
                    # API returns NowDate like "2025/12/16", convert to YYYY-MM-DD
                    raw_date = ct_data.get("NowDate", target_date).replace("/", "-")
                    
                    return {
                        "status": "success",
                        "source": "ChinaTimes (Realtime)",
                        "symbol": clean_symbol,
                        "date": raw_date,
                        "price": float(ct_data["Price"]),
                        "data": ct_data,
                        "verified": True,
                        "fallback_used": False
                    }
                print("[PriceProof] ChinaTimes returned empty or no price.")
            except Exception as e:
                print(f"[PriceProof] ChinaTimes Failed: {e}")

        # --- Source 2: TWSE (Secondary - Official) ---
        # Skip TWSE if it's an OTC stock (TPEx)
        is_likely_otc = (exchange == 'TPEx') # Flag to guide Yahoo fallback

        if is_likely_otc:
            print(f"[PriceProof] Skipping TWSE for OTC stock {clean_symbol}")
        else:
            try:
                print("[PriceProof] Fallback to TWSE...")
                # TWSE adapter takes 'symbol' and 'date' (month level) or range?
                # Our TWSEStockDay uses 'date' (YYYY-MM-DD) to find that specific month
                # It returns the whole month. We need to filter.
                
                # Using loop.run_in_executor for sync adapter calls if needed, but here we just call directly
                # assuming adapters are fast enough or we accept blocking for now (or make adapters async later)
                
                # Convert YYYY-MM-DD to YYYYMMDD for TWSE
                twse_date = target_date.replace("-", "")
                twse_res = self.twse_adapter.invoke(symbol=clean_symbol, date=twse_date)
                
                # Handle ToolResult object or dict
                twse_data = twse_res.data if hasattr(twse_res, 'data') else twse_res.get("data")
                
                if twse_data:
                    # DEBUG: Print twse_data keys to verify structure
                    # print(f"DEBUG: TWSE Data keys: {twse_data.keys()}")
                    if "error" in twse_data:
                        print(f"DEBUG: TWSE Error found: {twse_data['error']}")

                    # Check for explicit "No Data" error which hints this might be OTC
                    # Also check for "很抱歉，沒有符合條件的資料!" which is another common message
                    err_msg = str(twse_data.get("error", ""))
                    if err_msg and ("查無資料" in err_msg or "沒有符合條件" in err_msg):
                         print(f"[PriceProof] TWSE returned '{err_msg}'. Marking {clean_symbol} as likely OTC.")
                         is_likely_otc = True

                    # TWSE returns list of days in that month. We need to find the target date or nearest past date.
                    # Assuming data is sorted? Usually TWSE returns chronological.
                    # Let's search for exact match first, then closest previous.
                    
                    rows = twse_data.get("rows", []) # TWSE adapter result structure has "rows"
                    # Filter rows within our window
                    valid_rows = [r for r in rows if start_date_str <= r["date"] <= end_date_str]
                    
                    if valid_rows:
                        # Get latest (max date)
                        best_match = max(valid_rows, key=lambda x: x["date"])
                        
                        return {
                            "status": "success",
                            "source": "TWSE (Official Backup)",
                            "symbol": clean_symbol,
                            "date": best_match["date"],
                            "price": best_match["close"],
                            "data": best_match,
                            "verified": True,
                            "fallback_used": True
                        }
                print("[PriceProof] TWSE returned empty data or no match in window.")
            except Exception as e:
                print(f"[PriceProof] TWSE Failed: {e}")

        # --- Source 3: Alpha Vantage (New MCP Integration) ---
        # Primarily for US stocks, but we try it as intermediate fallback
        # Also used to RESOLVE symbol if unsure (using SYMBOL_SEARCH)
        
        av_resolved_symbol = None
        
        if self.av_adapter:
            try:
                # 3.1 Try to RESOLVE symbol if we suspect issues (e.g., market is TW but uncertain suffix)
                # Or simply use SYMBOL_SEARCH to find the best match
                if is_likely_otc or market == 'TW':
                     print(f"[PriceProof] Using Alpha Vantage SEARCH to resolve symbol for {clean_symbol}...")
                     search_res = self.av_adapter.invoke_tool_sync("SYMBOL_SEARCH", {"keywords": clean_symbol})
                     
                     # Parse search results (CSV format usually)
                     # symbol,name,type,region,marketOpen,marketClose,timezone,currency,matchScore
                     lines = search_res.strip().split('\n')
                     if len(lines) > 1:
                          header = lines[0].split(',')
                          # Look for 'symbol' column
                          if 'symbol' in header:
                               sym_idx = header.index('symbol')
                               # Iterate rows to find best match (Region=Taiwan)
                               for line in lines[1:]:
                                    cols = line.split(',')
                                    if len(cols) > sym_idx:
                                         s_code = cols[sym_idx]
                                         # Check if it looks like a Taiwan stock match
                                         if '.TW' in s_code or '.TWO' in s_code:
                                              av_resolved_symbol = s_code
                                              print(f"[PriceProof] AV Search resolved {clean_symbol} -> {av_resolved_symbol}")
                                              break
                
                # Use resolved symbol or fallback to clean_symbol
                av_symbol = av_resolved_symbol or clean_symbol
                
                # 3.2 Fetch Data
                print("[PriceProof] Fallback to Alpha Vantage (MCP)...")
                
                # Only proceed if we have a resolved symbol OR it's not a TW stock (since raw numbers fail for TW in AV)
                should_try_av = (av_resolved_symbol is not None) or (market != 'TW')
                
                if should_try_av:
                    # Sync call
                    av_res_str = self.av_adapter.invoke_tool_sync("TIME_SERIES_DAILY", {"symbol": av_symbol})
                    
                    # Parse CSV/JSON string from AV
                    # The adapter returns string. We need to parse it to check success.
                    # AV returns CSV usually or Error Message.
                    if "Error Message" not in av_res_str and "Invalid API call" not in av_res_str:
                         # Basic parsing (assume CSV: timestamp,open,high,low,close,volume)
                         # We just check if it has data.
                         lines = av_res_str.strip().split('\n')
                         if len(lines) > 1:
                              # Parse last line (or first data line)
                              # Line 0: headers
                              # Line 1: latest data
                              header = lines[0].split(',')
                              first_row = lines[1].split(',')
                              if 'close' in header and len(first_row) > header.index('close'):
                                   close_idx = header.index('close')
                                   date_idx = header.index('timestamp')
                                   return {
                                        "status": "success",
                                        "source": "Alpha Vantage (MCP)",
                                        "symbol": av_symbol,
                                        "date": first_row[date_idx],
                                        "price": float(first_row[close_idx]),
                                        "verified": True,
                                        "fallback_used": True
                                   }
                    print(f"[PriceProof] Alpha Vantage returned error or no data: {av_res_str[:50]}...")
                else:
                     print(f"[PriceProof] Skipping Alpha Vantage data fetch (Unresolved TW symbol: {av_symbol})")

            except Exception as e:
                print(f"[PriceProof] Alpha Vantage Failed: {e}")

        # --- Source 4: Yahoo (Fallback - External) ---
        try:
            print("[PriceProof] Fallback to Yahoo...")
            
            # Helper to query Yahoo
            def try_yahoo(ticker):
                res = self.yahoo_adapter.invoke(
                    symbol=ticker,
                    start_date=start_date_str,
                    end_date=end_date_str
                )
                return res.get("data") if isinstance(res, dict) else (res.data if hasattr(res, 'data') else None)

            # 1. Optimize Ticker based on previous hints
            # Priority:
            # 1. AV Resolved Symbol (if it worked)
            # 2. TWSE Failure Hint (switch .TW -> .TWO)
            
            current_yahoo_ticker = yahoo_ticker
            
            if av_resolved_symbol:
                 # If AV found a valid ticker (e.g. 5371.TWO), use it!
                 # AV tickers for TW often match Yahoo
                 current_yahoo_ticker = av_resolved_symbol
                 print(f"[PriceProof] Using AV-resolved ticker for Yahoo: {current_yahoo_ticker}")
            elif is_likely_otc and current_yahoo_ticker.endswith('.TW') and len(clean_symbol) == 4 and clean_symbol.isdigit():
                 current_yahoo_ticker = clean_symbol + ".TWO"
                 print(f"[PriceProof] Preemptively switching to OTC suffix (.TWO) based on TWSE failure: {current_yahoo_ticker}")

            # 2. Try Yahoo
            yahoo_data = try_yahoo(current_yahoo_ticker)
            
            # 3. [Smart Retry] If failed and we haven't tried the other one yet
            # If we tried .TW and failed -> Try .TWO
            # If we tried .TWO (preemptively) and failed -> Try .TW (maybe it was listed but just no data in TWSE?)
            
            if not yahoo_data:
                 retry_ticker = None
                 if current_yahoo_ticker.endswith('.TW') and len(clean_symbol) == 4 and clean_symbol.isdigit():
                      retry_ticker = clean_symbol + ".TWO"
                 elif current_yahoo_ticker.endswith('.TWO'):
                      retry_ticker = clean_symbol + ".TW"
                 
                 if retry_ticker:
                      print(f"[PriceProof] Yahoo {current_yahoo_ticker} failed, retrying with alternative: {retry_ticker}")
                      yahoo_data = try_yahoo(retry_ticker)
                      if yahoo_data:
                          # If retry succeeded, cache this mapping!
                          self._cache_symbol(clean_symbol, retry_ticker)
                          print(f"[PriceProof] Cached successful mapping: {clean_symbol} -> {retry_ticker}")

            if yahoo_data:
                # If we used a different ticker than originally planned (e.g. pre-emptive switch), cache it!
                if current_yahoo_ticker != yahoo_ticker:
                     self._cache_symbol(clean_symbol, current_yahoo_ticker)
                     print(f"[PriceProof] Cached successful mapping: {clean_symbol} -> {current_yahoo_ticker}")

                latest = yahoo_data[0] # Assumed sorted desc
                return {
                    "status": "success",
                    "source": "Yahoo Finance (External Backup)",
                    "symbol": clean_symbol,
                    "date": latest["date"],
                    "price": latest["close"],
                    "data": latest,
                    "verified": False, # External source needs caution
                    "fallback_used": True,
                    "note": "Data from external source, strictly for reference."
                }
            print("[PriceProof] Yahoo returned empty data.")
        except Exception as e:
            print(f"[PriceProof] Yahoo Failed: {e}")

        # --- Ultimate Fallback: Retrieve Latest Available Data (Any Date) ---
        # If specific window query failed, user might be asking for future date (Simulation mismatch).
        # We try to get the absolute latest data from TEJ/Yahoo to prevent "No Data" error.
        try:
            print("[PriceProof] Ultimate Fallback: Fetching latest available data...")
            # Look back 365 days from TODAY (System Time) to find *something*
            start_fb = (datetime.strptime(target_date, "%Y-%m-%d") - timedelta(days=365)).strftime("%Y-%m-%d")
            
            # Try Yahoo first (in fallback)
            def try_yahoo_fb(ticker):
                res = self.yahoo_adapter.invoke(symbol=ticker, start_date=start_fb, end_date=target_date)
                return res.get("data") if isinstance(res, dict) else (res.data if hasattr(res, 'data') else None)

            # Use same smart logic for fallback
            current_yahoo_ticker_fb = yahoo_ticker
            if is_likely_otc and current_yahoo_ticker_fb.endswith('.TW') and len(clean_symbol) == 4 and clean_symbol.isdigit():
                 current_yahoo_ticker_fb = clean_symbol + ".TWO"

            yahoo_data = try_yahoo_fb(current_yahoo_ticker_fb)
            
            if not yahoo_data:
                 retry_ticker = None
                 if current_yahoo_ticker_fb.endswith('.TW') and len(clean_symbol) == 4 and clean_symbol.isdigit():
                      retry_ticker = clean_symbol + ".TWO"
                 elif current_yahoo_ticker_fb.endswith('.TWO'):
                      retry_ticker = clean_symbol + ".TW"
                 
                 if retry_ticker:
                      print(f"[PriceProof] Ultimate Yahoo {current_yahoo_ticker_fb} failed, retrying with alternative: {retry_ticker}")
                      yahoo_data = try_yahoo_fb(retry_ticker)
            
            if yahoo_data:
                latest = yahoo_data[0]
                return {
                    "status": "success",
                    "source": "Yahoo (Latest Available)",
                    "symbol": clean_symbol,
                    "date": latest["date"],
                    "price": latest["close"],
                    "data": latest,
                    "verified": False,
                    "fallback_used": True,
                    "note": f"⚠️ Requested date ({target_date}) unavailable. Showing LATEST data from {latest['date']}."
                }
        except Exception as e:
            print(f"[PriceProof] Ultimate Fallback Failed: {e}")

        # --- Source 5: TEJ (Last Resort) ---
        try:
            print("[PriceProof] Trying TEJ (Last Resort)...")
            tej_res = self.tej_client.get_price(clean_symbol, start_date_str, end_date_str)
            if tej_res.get("data"):
                # Found data!
                latest = tej_res["data"][0] # Assumed sorted desc
                return {
                    "status": "success",
                    "source": "TEJ (Historical Archive)",
                    "symbol": clean_symbol,
                    "date": latest["date"],
                    "price": latest["close"],
                    "data": latest,
                    "verified": True, # TEJ is trusted
                    "fallback_used": True
                }
            print("[PriceProof] TEJ returned empty data.")
        except Exception as e:
            print(f"[PriceProof] TEJ Failed: {e}")

        # --- All Failed ---
        return {
            "status": "failed",
            "source": "None",
            "symbol": clean_symbol,
            "error": "All data sources failed (ChinaTimes, TWSE, Yahoo, TEJ)."
        }