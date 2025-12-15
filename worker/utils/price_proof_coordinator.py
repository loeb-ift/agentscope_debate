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
from worker.utils.symbol_utils import normalize_symbol

class PriceProofCoordinator:
    def __init__(self):
        self.tej_client = TejPriceClient()
        self.twse_adapter = TWSEStockDay()
        self.yahoo_adapter = YahooPriceAdapter()

    def get_verified_price(self, symbol: str, date: str = None, lookback_days: int = 5) -> Dict[str, Any]:
        """
        獲取經過驗證的股價數據 (同步方法 Wrapper)
        """
        return asyncio.run(self.get_verified_price_async(symbol, date, lookback_days))

    async def get_verified_price_async(self, symbol: str, date: str = None, lookback_days: int = 5) -> Dict[str, Any]:
        """
        獲取經過驗證的股價數據 (非同步)
        
        策略:
        1. 嘗試 TEJ。
        2. 若 TEJ 失敗或無數據，嘗試 TWSE。
        3. 若 TWSE 失敗或無數據，嘗試 Yahoo。
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

        print(f"[PriceProof] Fetching {clean_symbol} (Yahoo: {yahoo_ticker}, Exch: {exchange}) for {target_date} (Window: {start_date_str} ~ {end_date_str})")
        
        # --- Source 1: TEJ (Primary) ---
        try:
            print("[PriceProof] Trying TEJ...")
            tej_res = self.tej_client.get_price(clean_symbol, start_date_str, end_date_str)
            if tej_res.get("data"):
                # Found data!
                latest = tej_res["data"][0] # Assumed sorted desc
                return {
                    "status": "success",
                    "source": "TEJ (Primary)",
                    "symbol": clean_symbol,
                    "date": latest["date"],
                    "price": latest["close"],
                    "data": latest,
                    "verified": True, # TEJ is trusted
                    "fallback_used": False
                }
            print("[PriceProof] TEJ returned empty data.")
        except Exception as e:
            print(f"[PriceProof] TEJ Failed: {e}")

        # --- Source 2: TWSE (Secondary - Official) ---
        # Skip TWSE if it's an OTC stock (TPEx)
        if exchange == 'TPEx':
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

        # --- Source 3: Yahoo (Fallback - External) ---
        try:
            print("[PriceProof] Fallback to Yahoo...")
            yahoo_res = self.yahoo_adapter.invoke(
                symbol=yahoo_ticker,
                start_date=start_date_str,
                end_date=end_date_str
            )
            
            # Handle ToolResult or dict (Yahoo adapter returns dict directly in code I saw, but verify)
            # YahooPriceAdapter.invoke returns dict directly based on read file
            yahoo_data = yahoo_res.get("data") if isinstance(yahoo_res, dict) else (yahoo_res.data if hasattr(yahoo_res, 'data') else None)

            if yahoo_data:
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
            
            # Try TEJ first
            tej_res = self.tej_client.get_price(clean_symbol, start_fb, target_date)
            if tej_res.get("data"):
                latest = tej_res["data"][0]
                return {
                    "status": "success",
                    "source": "TEJ (Latest Available)",
                    "symbol": clean_symbol,
                    "date": latest["date"],
                    "price": latest["close"],
                    "data": latest,
                    "verified": True,
                    "fallback_used": True,
                    "note": f"⚠️ Requested date ({target_date}) unavailable. Showing LATEST data from {latest['date']}."
                }
                
            # Try Yahoo second
            yahoo_res = self.yahoo_adapter.invoke(symbol=yahoo_ticker, start_date=start_fb, end_date=target_date)
            yahoo_data = yahoo_res.get("data") if isinstance(yahoo_res, dict) else (yahoo_res.data if hasattr(yahoo_res, 'data') else None)
            
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

        # --- All Failed ---
        return {
            "status": "failed",
            "source": "None",
            "symbol": clean_symbol,
            "error": "All data sources failed (TEJ, TWSE, Yahoo). Data unavailable for this period."
        }