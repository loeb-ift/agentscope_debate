from typing import Dict, Any, List, Optional
import requests
import datetime
from .base import BaseToolAdapter, ToolResult, UpstreamError

class TWSEStockDay(BaseToolAdapter):
    name = "twse.stock_day"
    version = "v1"
    description = """查詢台灣證交所 (TWSE) 個股日成交資訊 (STOCK_DAY)。
    資料包含：日期、成交股數、成交金額、開盤價、最高價、最低價、收盤價、漲跌價差、成交筆數。
    注意：TWSE API 採用月為單位查詢。"""

    @property
    def auth_config(self) -> Dict:
        return {} # Public API

    @property
    def rate_limit_config(self) -> Dict:
        return {"tps": 3, "burst": 5} # TWSE is strict

    @property
    def cache_ttl(self) -> int:
        return 3600 # 1 hour

    def describe(self) -> Dict:
        return {
            "name": self.name,
            "description": self.description,
            "parameters": {
                "type": "object",
                "properties": {
                    "symbol": {
                        "type": "string",
                        "description": "股票代碼 (e.g. '2330')"
                    },
                    "date": {
                        "type": "string",
                        "description": "查詢日期 (YYYYMMDD)，例如 '20251201'。系統會自動抓取該月份資料。"
                    }
                },
                "required": ["symbol", "date"]
            }
        }

    def validate(self, params: Dict) -> None:
        if "symbol" not in params:
            raise ValueError("symbol is required")
        if "date" not in params:
            raise ValueError("date is required (YYYYMMDD)")

    def auth(self, req: Dict) -> Dict:
        return req

    def invoke(self, **kwargs) -> ToolResult:
        # Repack kwargs into params to match internal logic or just use kwargs
        params = kwargs
        
        symbol = params["symbol"]
        date_str = params["date"]
        
        # Format date for TWSE (YYYYMM01 usually suffices, but we pass full date)
        # Ensure YYYYMMDD format
        if len(date_str) != 8:
             raise ValueError(f"Date format must be YYYYMMDD, got {date_str}")
             
        url = "https://www.twse.com.tw/exchangeReport/STOCK_DAY"
        query_params = {
            "response": "json",
            "date": date_str,
            "stockNo": symbol
        }
        
        try:
            # Add User-Agent to avoid blocking
            headers = {
                "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            }
            resp = requests.get(url, params=query_params, headers=headers, timeout=10)
            resp.raise_for_status()
            raw_data = resp.json()
        except Exception as e:
            raise UpstreamError("ERR-TWSE", 500, str(e))
            
        if raw_data.get("stat") != "OK":
             # e.g., "查無資料"
             return ToolResult(
                 data={"error": raw_data.get("stat"), "info": raw_data},
                 raw=raw_data,
                 used_cache=False,
                 cost=0.0,
                 citations=[]
             )
        
        # Parse data
        # Fields: ["日期", "成交股數", "成交金額", "開盤價", "最高價", "最低價", "收盤價", "漲跌價差", "成交筆數"]
        rows = []
        fields = raw_data.get("fields", [])
        for item in raw_data.get("data", []):
            try:
                # Convert ROC Date (112/01/01) to AD
                roc_date = item[0]
                y, m, d = roc_date.split('/')
                ad_year = int(y) + 1911
                ad_date = f"{ad_year}-{int(m):02d}-{int(d):02d}"
                
                row = {
                    "date": ad_date,
                    "volume": int(item[1].replace(',', '')),
                    "amount": int(item[2].replace(',', '')),
                    "open": float(item[3].replace(',', '').replace('--', '0')),
                    "high": float(item[4].replace(',', '').replace('--', '0')),
                    "low": float(item[5].replace(',', '').replace('--', '0')),
                    "close": float(item[6].replace(',', '').replace('--', '0')),
                    "change": item[7],
                    "transactions": int(item[8].replace(',', ''))
                }
                rows.append(row)
            except Exception as e:
                print(f"Error parsing TWSE row: {item} -> {e}")
                continue
                
        result_data = {
            "symbol": symbol,
            "title": raw_data.get("title"),
            "date": raw_data.get("date"),
            "rows": rows
        }
        
        citations = [{
            "title": f"TWSE {symbol} {date_str[:6]}",
            "url": resp.url,
            "snippet": f"Found {len(rows)} trading days.",
            "source": "TWSE"
        }]
        
        return ToolResult(
            data=result_data,
            raw=raw_data,
            used_cache=False,
            cost=0.0,
            citations=citations
        )

    def should_cache(self, params: Dict) -> bool:
        return True

    def cache_key(self, params: Dict) -> str:
        return f"twse:stock_day:{params['symbol']}:{params['date']}"

    def map_error(self, http_status: int, body: Any) -> Exception:
        return Exception(f"TWSE Error {http_status}: {body}")