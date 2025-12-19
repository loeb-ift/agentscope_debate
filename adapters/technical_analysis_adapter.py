"""
Technical Analysis Adapter - 提供技術分析指標計算
"""
from adapters.tool_adapter import ToolAdapter
from typing import Dict, Any, List
import pandas as pd
import pandas_ta_classic as ta
import yfinance as yf
from datetime import datetime, timedelta

class TechnicalAnalysisAdapter(ToolAdapter):
    """
    技術分析工具，提供多種技術指標計算。
    """
    
    @property
    def name(self) -> str:
        return "financial.technical_analysis"
    
    @property
    def version(self) -> str:
        return "v1"
    
    @property
    def description(self) -> str:
        return """
        獲取股票的技術分析指標（如 RSI, MACD, 移動平均線等）。
        支援 Yahoo Finance 數據源。
        """
    
    @property
    def schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "symbol": {
                    "type": "string",
                    "description": "股票代碼（例如：2330.TW, AAPL）"
                },
                "lookback_days": {
                    "type": "integer",
                    "default": 60,
                    "description": "回溯天數"
                },
                "indicators": {
                    "type": "array",
                    "items": {
                        "type": "string",
                        "enum": ["sma", "rsi", "macd", "bbands", "willr", "cci", "adx"]
                    },
                    "default": ["sma", "rsi", "macd"],
                    "description": "要計算的指標列表"
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
        lookback_days = kwargs.get("lookback_days", 60)
        indicators = kwargs.get("indicators", ["sma", "rsi", "macd"])
        
        try:
            # 1. 下載數據
            ticker = yf.Ticker(symbol)
            end_date = datetime.now()
            start_date = end_date - timedelta(days=lookback_days + 50) # 多拿一點數據以確保指標計算準確
            
            df = ticker.history(start=start_date, end=end_date)
            if df.empty:
                return {"error": f"No data found for {symbol}"}
            
            # 標準化欄位名稱
            df.columns = [c.lower() for c in df.columns]
            
            # 2. 計算指標
            results = {}
            
            if "sma" in indicators:
                df.ta.sma(length=20, append=True)
                df.ta.sma(length=50, append=True)
            
            if "rsi" in indicators:
                df.ta.rsi(length=14, append=True)
            
            if "macd" in indicators:
                df.ta.macd(append=True)
                
            if "bbands" in indicators:
                df.ta.bbands(append=True)
                
            if "willr" in indicators:
                df.ta.willr(append=True)
                
            if "cci" in indicators:
                df.ta.cci(append=True)
                
            if "adx" in indicators:
                df.ta.adx(append=True)
            
            # 3. 取得最新一筆數據的值
            latest = df.iloc[-1].to_dict()
            
            # 過濾出計算出的指標欄位
            # 排除原始價格欄位
            base_cols = ['open', 'high', 'low', 'close', 'volume', 'dividends', 'stock splits']
            ta_results = {k: v for k, v in latest.items() if k not in base_cols and not pd.isna(v)}
            
            # 整理輸出
            summary = self._generate_signal_summary(symbol, ta_results)
            
            return {
                "success": True,
                "symbol": symbol,
                "latest_values": ta_results,
                "summary": summary,
                "data_points": len(df)
            }
            
        except Exception as e:
            return {"error": str(e)}

    def _generate_signal_summary(self, symbol: str, ta_results: Dict[str, Any]) -> str:
        """生成簡單的信號摘要"""
        signals = []
        
        # RSI 判斷
        rsi = ta_results.get("RSI_14")
        if rsi:
            if rsi > 70:
                signals.append(f"RSI 為 {rsi:.2f}，進入超買區。")
            elif rsi < 30:
                signals.append(f"RSI 為 {rsi:.2f}，進入超賣區。")
            else:
                signals.append(f"RSI 為 {rsi:.2f}，處於中性區間。")
        
        # MACD 判斷
        macd = ta_results.get("MACD_12_26_9")
        signal = ta_results.get("MACDs_12_26_9")
        if macd and signal:
            if macd > signal:
                signals.append("MACD 位於信號線上方（黃金交叉），偏向多頭。")
            else:
                signals.append("MACD 位於信號線下方（死亡交叉），偏向空頭。")
        
        # SMA 判斷
        sma20 = ta_results.get("SMA_20")
        sma50 = ta_results.get("SMA_50")
        if sma20 and sma50:
            if sma20 > sma50:
                signals.append("短期均線 (SMA20) 高於長期均線 (SMA50)，趨勢向上。")
            else:
                signals.append("短期均線 (SMA20) 低於長期均線 (SMA50)，趨勢向下。")
                
        if not signals:
            return f"{symbol} 的技術指標計算完成，未發現顯著極端信號。"
            
        return f"{symbol} 技術分析摘要：\n" + "\n".join(signals)
