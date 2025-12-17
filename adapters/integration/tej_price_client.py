"""
TEJ Price Client (Integration Layer)
專門用於內部整合的 TEJ 股價查詢客戶端，不經過 Tool Registry。
用於 Price Proof Coordinator 的數據源之一。
"""

from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
from adapters.tej_adapter import TEJStockPrice
from mars.types.errors import ToolRecoverableError

class TejPriceClient:
    """
    TEJ 股價查詢客戶端 (Internal Use)
    """
    
    def __init__(self):
        # Instantiate the existing adapter directly
        # This reuses the auth, rate limiting, and request logic of the adapter
        self._adapter = TEJStockPrice()

    def get_price(self, symbol: str, start_date: str, end_date: str) -> Dict[str, Any]:
        """
        獲取 TEJ 股價數據 (標準化格式)
        
        Args:
            symbol: 股票代碼 (e.g., 2330)
            start_date: YYYY-MM-DD
            end_date: YYYY-MM-DD
            
        Returns:
            Dict: {
                "source": "TEJ",
                "symbol": str,
                "data": List[Dict]  # OHLCV list
            }
        """
        try:
            # Invoke adapter (it returns ToolResult object or raises error)
            # Note: TEJStockPrice.invoke returns ToolResult
            tool_result = self._adapter.invoke(
                coid=symbol,
                start_date=start_date,
                end_date=end_date,
                limit=5000 # Max limit for internal fetching
            )
            
            # Extract data from ToolResult
            raw_data = tool_result.data.get("rows", [])
            
            if not raw_data:
                return {
                    "source": "TEJ",
                    "symbol": symbol,
                    "data": [],
                    "message": "Empty data returned"
                }

            # Normalize data format to match PriceProofCoordinator expectations
            # TEJ Format: mdate, open_d, high_d, low_d, close_d, volume
            normalized_data = []
            for row in raw_data:
                # Handle mdate format (could be YYYY-MM-DD or with time)
                mdate = str(row.get("mdate", "")).split("T")[0]
                
                normalized_data.append({
                    "date": mdate,
                    "open": row.get("open_d"),
                    "high": row.get("high_d"),
                    "low": row.get("low_d"),
                    "close": row.get("close_d"),
                    "volume": row.get("volume"),
                    "source": "TEJ"
                })
            
            # Sort by date descending
            normalized_data.sort(key=lambda x: x['date'], reverse=True)

            return {
                "source": "TEJ",
                "symbol": symbol,
                "count": len(normalized_data),
                "data": normalized_data
            }

        except ToolRecoverableError as e:
            # Handle "date_span_too_large" or empty data signals gracefully
            print(f"TEJ Client Warning: {e.message}")
            return {
                "source": "TEJ",
                "symbol": symbol,
                "data": [],
                "error": e.message
            }
        except Exception as e:
            print(f"TEJ Client Error: {e}")
            return {
                "source": "TEJ",
                "symbol": symbol,
                "data": [],
                "error": str(e)
            }