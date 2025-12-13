"""
Yahoo Finance Adapter (v2) - Robust Pricing Utility
專為股價查詢設計的轉接器，作為 TEJ 的備援方案。
"""

from typing import Dict, Any, Optional
import yfinance as yf
from datetime import datetime, timedelta
from .tool_adapter import ToolAdapter
from worker.utils.symbol_utils import normalize_symbol

class YahooPriceAdapter(ToolAdapter):
    """
    Yahoo Finance 股價查詢工具 (v2)
    作為 TEJ 的 Fallback，提供全球與台股即時/歷史股價。
    """
    
    @property
    def name(self) -> str:
        return "yahoo.stock_info"  # Backward compatibility alias
    
    @property
    def alias(self) -> str:
        return "yahoo.stock_price"

    @property
    def version(self) -> str:
        return "v2.0"

    @property
    def description(self) -> str:
        return "查詢全球即時與歷史股價 (Yahoo Finance)。作為 TEJ 數據不足時的備援工具。支援台股 (2330.TW) 與美股 (NVDA)。"

    @property
    def schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "symbol": {
                    "type": "string",
                    "description": "股票代碼 (支援自動修正，如 2330 -> 2330.TW, NVDA)"
                },
                "start_date": {
                    "type": "string",
                    "description": "開始日期 (YYYY-MM-DD)",
                    "format": "date"
                },
                "end_date": {
                    "type": "string",
                    "description": "結束日期 (YYYY-MM-DD). 預設為今天.",
                    "format": "date"
                },
                "period": {
                    "type": "string",
                    "description": "快捷期間 (若有指定日期則忽略). e.g. '1d', '5d', '1mo', '3mo', '1y'",
                    "default": "1mo"
                }
            },
            "required": ["symbol"]
        }

    def describe(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "version": self.version,
            "description": self.description,
            "schema": self.schema
        }

    def invoke(self, **kwargs: Any) -> Dict[str, Any]:
        raw_symbol = kwargs.get("symbol")
        start_date = kwargs.get("start_date")
        end_date = kwargs.get("end_date")
        period = kwargs.get("period", "1mo")

        if not raw_symbol:
            raise ValueError("Stock symbol is required")

        # 1. Symbol Normalization (Auto-fix .TW for Yahoo)
        # normalize_symbol returns a dict, we need the ticker
        norm_res = normalize_symbol(raw_symbol)
        symbol = norm_res.get("yahoo_ticker", raw_symbol)

        try:
            ticker = yf.Ticker(symbol)
            
            # 2. Determine Fetch Mode
            hist_data = None
            
            if start_date:
                # Specific Date Range
                # Yahoo end_date is exclusive, so we might need to add 1 day if we want inclusive?
                # But usually users pass range. Let's stick to library default.
                hist_data = ticker.history(start=start_date, end=end_date)
            else:
                # Period Mode
                hist_data = ticker.history(period=period)
            
            if hist_data.empty:
                return {
                    "symbol": symbol,
                    "data": [],
                    "message": "No data found for the specified range. Try adjusting dates or symbol."
                }
                
            # 3. Format Result
            results = []
            
            # Reset index to get Date column
            hist_data = hist_data.reset_index()
            
            for _, row in hist_data.iterrows():
                # Format Date
                date_val = row['Date']
                if isinstance(date_val, datetime):
                    date_str = date_val.strftime('%Y-%m-%d')
                else:
                    date_str = str(date_val).split(" ")[0]
                    
                results.append({
                    "date": date_str,
                    "open": round(row['Open'], 2),
                    "high": round(row['High'], 2),
                    "low": round(row['Low'], 2),
                    "close": round(row['Close'], 2),
                    "volume": int(row['Volume']),
                    "source": "Yahoo Finance"
                })
            
            # Sort by date descending (newest first)
            results.sort(key=lambda x: x['date'], reverse=True)
            
            return {
                "symbol": symbol,
                "count": len(results),
                "data": results,
                "meta": {
                    "currency": ticker.info.get("currency", "Unknown"),
                    "exchange": ticker.info.get("exchange", "Unknown"),
                    "last_updated": datetime.now().isoformat()
                }
            }

        except Exception as e:
            # Catch yfinance specific errors
            return {
                "error": str(e),
                "symbol": symbol,
                "hint": "Check if symbol is correct (e.g., 2330.TW for TSMC)"
            }