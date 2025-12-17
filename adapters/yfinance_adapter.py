from .tool_adapter import ToolAdapter
from typing import Dict, Any
import yfinance as yf

class YFinanceAdapter(ToolAdapter):
    """
    Yahoo Finance 工具的轉接器。
    """
    @property
    def name(self) -> str:
        return "yfinance.stock_info"

    @property
    def version(self) -> str:
        return "v1"

    @property
    def description(self) -> str:
        return "Yahoo Finance 股票資訊查詢工具。提供全球股市的即時報價、歷史數據與相關新聞。"

    @property
    def cache_ttl(self) -> int:
        return 300  # 5分鐘快取

    @property
    def schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "symbol": {
                    "type": "string",
                    "description": "股票代碼 (支援美股如 AAPL, 台股如 2330.TW)"
                },
                "info_type": {
                    "type": "string",
                    "enum": ["basic", "history", "news"],
                    "default": "basic",
                    "description": "查詢類型：basic (基本資料與即時價)、history (近一月歷史股價)、news (相關新聞)"
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
        symbol = kwargs.get("symbol")
        info_type = kwargs.get("info_type", "basic")

        if not symbol:
            raise ValueError("Stock symbol is required")

        try:
            ticker = yf.Ticker(symbol)
            
            if info_type == "basic":
                info = ticker.info
                # 篩選一些關鍵欄位回傳，避免資料量過大
                keys_to_keep = [
                    'shortName', 'longName', 'currentPrice', 'marketCap', 
                    'trailingPE', 'forwardPE', 'dividendYield', 'sector', 
                    'industry', 'website', 'longBusinessSummary'
                ]
                result = {k: info.get(k) for k in keys_to_keep if k in info}
                return {"data": result}
            
            elif info_type == "history":
                # 預設取得最近一個月的歷史資料
                hist = ticker.history(period="1mo")
                # 轉換為字典格式
                hist_data = []
                for date, row in hist.iterrows():
                    hist_data.append({
                        "date": date.strftime('%Y-%m-%d'),
                        "open": row['Open'],
                        "high": row['High'],
                        "low": row['Low'],
                        "close": row['Close'],
                        "volume": row['Volume']
                    })
                return {"data": hist_data}
                
            elif info_type == "news":
                return {"data": ticker.news}
            
            else:
                raise ValueError(f"Unknown info_type: {info_type}")

        except Exception as e:
            raise RuntimeError(f"YFinance Error: {e}")
