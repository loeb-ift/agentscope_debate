"""
Pandas DataReader Adapter - 提供多源數據拉取能力
"""
from adapters.tool_adapter import ToolAdapter
from typing import Dict, Any, Optional
import pandas as pd
import pandas_datareader.data as web
from datetime import datetime, timedelta
from worker.utils.symbol_utils import normalize_symbol

class PandasDataReaderAdapter(ToolAdapter):
    """
    使用 pandas-datareader 從多個來源（如 Stooq, FRED）拉取數據。
    """
    
    @property
    def name(self) -> str:
        return "financial.pdr_reader"
    
    @property
    def version(self) -> str:
        return "v1"
    
    @property
    def description(self) -> str:
        return """
        使用 pandas-datareader 獲取歷史價格數據。
        預設使用 Stooq 來源，支援台股 (2330.JP 格式或自動轉寄) 與全球市場。
        """
    
    @property
    def schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "symbol": {
                    "type": "string",
                    "description": "股票代碼 (例如: 2330.TW, AAPL)"
                },
                "start_date": {
                    "type": "string",
                    "description": "開始日期 (YYYY-MM-DD)"
                },
                "end_date": {
                    "type": "string",
                    "description": "結束日期 (YYYY-MM-DD)"
                },
                "source": {
                    "type": "string",
                    "default": "stooq",
                    "description": "數據來源 (e.g., stooq, fred, av-daily)"
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
        source = kwargs.get("source", "stooq")
        
        if not raw_symbol:
            return {"error": "Symbol is required"}
            
        try:
            # 1. 處理日期
            if not end_date:
                end_dt = datetime.now()
            else:
                end_dt = pd.to_datetime(end_date)
                
            if not start_date:
                start_dt = end_dt - timedelta(days=60)
            else:
                start_dt = pd.to_datetime(start_date)
            
            # 2. 處理 Symbol (針對 Stooq 的特殊處理)
            # Stooq 的台股格式通常是 2330.TW 或在某些 API 中需要調整
            # 這裡我們嘗試獲取建議的 ticker
            norm_res = normalize_symbol(raw_symbol)
            symbol = norm_res.get("ticker", raw_symbol)
            
            # Stooq 特殊轉換: 2330.TW -> 2330.TW (Stooq 支援)
            # 註：雖然 2330.TW 有時回傳空值，但這是 Stooq 端的限制，
            # 優先權已設為高於 Yahoo，若失敗則會自動降級。
            
            # 3. 拉取數據
            print(f"[PDR Adapter] Fetching {symbol} from {source} ({start_dt.date()} to {end_dt.date()})...")
            
            df = web.DataReader(symbol, data_source=source, start=start_dt, end=end_dt)
            
            if df.empty:
                return {"error": f"No data found for {symbol} via {source}", "symbol": symbol}
            
            # 4. 標準化輸出 (OHLCV)
            df = df.reset_index()
            # Stooq 返回的欄位可能是大寫，且 Date 是 index
            df.columns = [c.lower() for c in df.columns]
            
            # 確保有 date 欄位
            if 'date' not in df.columns:
                # 有些來源可能叫別的名字
                date_cols = [c for c in df.columns if 'date' in c or 'time' in c]
                if date_cols:
                    df = df.rename(columns={date_cols[0]: 'date'})
            
            # 格式化日期
            df['date'] = pd.to_datetime(df['date']).dt.strftime('%Y-%m-%d')
            
            # 排序
            df = df.sort_values('date', ascending=False)
            
            results = df.to_dict('records')
            
            return {
                "success": True,
                "symbol": symbol,
                "source": source,
                "count": len(results),
                "data": results
            }
            
        except Exception as e:
            return {"error": str(e), "symbol": raw_symbol}
