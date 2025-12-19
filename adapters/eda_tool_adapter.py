"""
EDA Tool Adapter - 提供自動化探索性數據分析功能

這是一個高階工具，整合了：
1. 數據準備（從 Yahoo Finance 拉取）
2. EDA 服務調用（ODS Internal API）
3. Gate 檢查（品質驗證）
4. Evidence 攝取（自動入庫）

僅供主席使用。
"""
from adapters.tool_adapter import ToolAdapter
from typing import Dict, Any
import asyncio
from pathlib import Path
from datetime import datetime, timedelta
import pandas_ta_classic as ta


class EDAToolAdapter(ToolAdapter):
    """
    EDA 自動分析工具。
    
    此工具為主席提供一站式的數據分析能力：
    - 自動拉取股票數據
    - 生成 EDA 報表
    - 驗證品質並攝取到 Evidence 系統
    """
    
    @property
    def name(self) -> str:
        return "chairman.eda_analysis"
    
    @property
    def version(self) -> str:
        return "v1"
    
    @property
    def description(self) -> str:
        return """
        主席專用：自動化探索性數據分析 (EDA) 工具。
        
        功能：
        1. 自動拉取股票歷史數據（Yahoo Finance）
        2. 生成完整 EDA 報表（ydata-profiling）
        3. 產生統計圖表（直方圖、相關矩陣、箱型圖）
        4. 品質檢查與驗證
        5. 自動攝取到 Evidence 系統
        
        適用場景：
        - 主席在總結時需要實證數據支持
        - 需要量化分析股票表現
        - 生成可引用的統計報表
        
        注意：
        - 此工具會自動處理數據準備、分析、驗證全流程
        - 結果會自動入庫為 VERIFIED Evidence
        - 若品質檢查失敗，會返回降級模式說明
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
                "debate_id": {
                    "type": "string",
                    "description": "辯論 ID（用於數據隔離和 Evidence 關聯）"
                },
                "lookback_days": {
                    "type": "integer",
                    "default": 120,
                    "description": "回溯天數（預設 120 天）"
                },
                "include_financials": {
                    "type": "boolean",
                    "default": True,
                    "description": "是否包含財務報表分析（預設 True）"
                },
                "include_technical": {
                    "type": "boolean",
                    "default": True,
                    "description": "是否包含技術指標分析（預設 True）"
                }
            },
            "required": ["symbol", "debate_id"]
        }
    
    def describe(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "version": self.version,
            "description": self.description,
            "schema": self.schema
        }
    
    def invoke(self, **kwargs: Any) -> Dict[str, Any]:
        """
        執行 EDA 分析（同步包裝）。
        
        Args:
            symbol: 股票代碼
            debate_id: 辯論 ID
            lookback_days: 回溯天數
            
        Returns:
            Dictionary with:
                - success: bool
                - summary: 分析摘要文本
                - evidence_ids: Evidence 文件 ID 列表
                - artifacts: 產出檔案路徑
                - error: 錯誤訊息（若失敗）
        """
    def invoke(self, **kwargs: Any) -> Dict[str, Any]:
        """
        執行 EDA 分析（同步包裝）。
        """
        try:
            # 檢查是否有正在運行的 event loop
            asyncio.get_running_loop()
            # 如果有，則在另一個執行緒中運行，避免 "loop already running" 錯誤
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as pool:
                return pool.submit(lambda: asyncio.run(self._invoke_async(**kwargs))).result()
        except RuntimeError:
            # 沒有正在運行的 loop，直接使用 asyncio.run
            return asyncio.run(self._invoke_async(**kwargs))
    
    async def _invoke_async(self, **kwargs: Any) -> Dict[str, Any]:
        """異步執行 EDA 分析"""
        symbol = kwargs.get("symbol")
        debate_id = kwargs.get("debate_id")
        lookback_days = kwargs.get("lookback_days", 120)
        include_financials = kwargs.get("include_financials", True)
        include_technical = kwargs.get("include_technical", True)  # 新增
        
        if not symbol or not debate_id:
            return {
                "success": False,
                "error": "缺少必要參數：symbol 和 debate_id"
            }
        
        try:
            # Step 1: 準備股價數據
            # 優先使用 ChinaTimes，失敗則降級使用 Yahoo Finance
            csv_path = await self._prepare_stock_data_chinatimes(symbol, debate_id, lookback_days)
            
            if not csv_path:
                print(f"[EDA Tool] ChinaTimes data retrieval failed, trying pandas-datareader...")
                csv_path = await self._prepare_stock_data_pdr(symbol, debate_id, lookback_days)

            if not csv_path:
                print(f"[EDA Tool] PDR retrieval failed, falling back to Yahoo Finance...")
                csv_path = await self._prepare_stock_data(symbol, debate_id, lookback_days)
            
            if not csv_path:
                return {
                    "success": False,
                    "error": "數據準備失敗：無法下載股票數據 (ChinaTimes & Yahoo Finance)"
                }
            
            # Step 1.5: 準備財務數據並合併到 CSV
            financial_data = None
            if include_financials:
                financial_data = await self._prepare_financial_data_basic(symbol, debate_id)
                if financial_data and financial_data.get("success"):
                    print(f"[EDA Tool] ✓ Financial data prepared, merging to CSV...")
                    csv_path = await self._merge_financial_data_to_csv(csv_path, financial_data)
                else:
                    print(f"[EDA Tool] ⚠️ Financial data unavailable, continuing with price data only")
            
            # Step 1.6: 計算技術指標
            if include_technical:
                print(f"[EDA Tool] Calculating technical indicators for {symbol}...")
                csv_path = await self._calculate_technical_indicators(csv_path)
            
            # Step 2: 調用 EDA 服務
            eda_artifacts = await self._invoke_eda_service(csv_path)
            
            if not eda_artifacts:
                return {
                    "success": False,
                    "error": "EDA 服務調用失敗"
                }
            
            # Step 3: Gate 檢查
            gate_result = self._validate_artifacts(eda_artifacts)
            
            if not gate_result['passed']:
                # 降級模式
                from worker.eda_gate_checker import EDAGateChecker
                checker = EDAGateChecker()
                degradation_msg = checker.get_degradation_message(gate_result['issues'])
                
                return {
                    "success": True,
                    "degraded": True,
                    "summary": f"EDA 分析完成（降級模式）\n\n{degradation_msg}",
                    "issues": gate_result['issues']
                }
            
            # Step 4: 攝取到 Evidence
            evidence_docs = self._ingest_artifacts(eda_artifacts, debate_id)
            
            # Step 5: 生成摘要（包含財務數據）
            summary = self._format_summary(eda_artifacts, evidence_docs, symbol, financial_data)
            
            return {
                "success": True,
                "degraded": False,
                "summary": summary,
                "evidence_ids": [doc.id for doc in evidence_docs],
                "artifacts": {
                    "report": eda_artifacts['report_path'],
                    "plots": eda_artifacts['plot_paths'],
                    "tables": eda_artifacts['table_paths']
                },
                "metadata": eda_artifacts['metadata'],
                "financial_data": financial_data  # 新增財務數據
            }
            
        except Exception as e:
            import traceback
            traceback.print_exc()
            return {
                "success": False,
                "error": f"EDA 分析異常：{str(e)}"
            }
    
    async def _prepare_stock_data_chinatimes(self, symbol: str, debate_id: str, lookback_days: int) -> str:
        """
        準備股票數據 CSV (使用 ChinaTimes)
        
        Args:
            symbol: 股票代碼 (e.g., 2330.TW or 2330)
            debate_id: 辯論 ID
            lookback_days: 回溯天數
            
        Returns:
            CSV 檔案路徑，若失敗返回 None
        """
        # 移除 .TW 後綴
        code = symbol.replace(".TW", "").replace(".TWO", "")
        
        # 使用本地 data 目錄
        script_dir = Path(__file__).parent.parent
        data_dir = script_dir / "data" / "staging" / debate_id
        data_dir.mkdir(parents=True, exist_ok=True)
        
        csv_path = data_dir / f"{symbol}_ct.csv" # 區分來源
        
        # 檢查是否已存在
        if csv_path.exists():
            # 檢查檔案新鮮度 (可選)
            print(f"[EDA Tool] ChinaTimes CSV already exists: {csv_path.name}")
            return str(csv_path)
            
        print(f"[EDA Tool] Downloading {symbol} data from ChinaTimes (via stock_kline)...")
        
        try:
            from worker.tool_invoker import call_tool
            loop = asyncio.get_running_loop()
            
            # 調用 ChinaTimes K線工具
            # chinatimes.stock_kline 參數: code, days (日K)
            result = await loop.run_in_executor(
                None,
                call_tool,
                "chinatimes.stock_kline",
                {"code": code, "days": lookback_days}
            )
            
            if not result or result.get("error"):
                print(f"[EDA Tool] ChinaTimes data fetch failed: {result.get('error', 'Unknown')}")
                return None
                
            data = result.get("data", [])
            if not data:
                print(f"[EDA Tool] ChinaTimes returned no data for {code}")
                return None
                
            # 轉換為 DataFrame 並儲存為 CSV
            import pandas as pd
            
            # ChinaTimes K線格式: [{date, open, high, low, close, volume}, ...]
            # 需要確保欄位名稱符合 ODS EDA 要求: date, open, high, low, close, volume (小寫)
            df = pd.DataFrame(data)
            
            # 標準化欄位名稱 (ChinaTimes 可能是全小寫或首字大寫，這裡做防禦性處理)
            # 假設 chinatimes.stock_kline 返回的是標準化後的 dict list
            # 若不是，需在此處 mapping
            
            # 確保欄位存在
            required_cols = ['date', 'open', 'high', 'low', 'close', 'volume']
            if not all(col in df.columns for col in required_cols):
                print(f"[EDA Tool] ChinaTimes data missing columns. Available: {df.columns.tolist()}")
                return None
            
            # 排序 (日期升序)
            if 'date' in df.columns:
                df['date'] = pd.to_datetime(df['date'])
                df = df.sort_values('date')
            
            # 儲存
            df.to_csv(csv_path, index=False)
            print(f"[EDA Tool] ChinaTimes data saved: {len(df)} records")
            
            return str(csv_path)
            
        except Exception as e:
            print(f"[EDA Tool] ChinaTimes processing failed: {e}")
            return None

    async def _prepare_stock_data_pdr(self, symbol: str, debate_id: str, lookback_days: int) -> str:
        """
        準備股票數據 CSV (使用 pandas-datareader)
        """
        # 使用本地 data 目錄
        script_dir = Path(__file__).parent.parent
        data_dir = script_dir / "data" / "staging" / debate_id
        data_dir.mkdir(parents=True, exist_ok=True)
        
        csv_path = data_dir / f"{symbol}_pdr.csv"
        
        if csv_path.exists():
            return str(csv_path)
            
        print(f"[EDA Tool] Fetching {symbol} data from pandas-datareader (stooq)...")
        
        try:
            from worker.tool_invoker import call_tool
            loop = asyncio.get_running_loop()
            
            end_date = datetime.now().strftime("%Y-%m-%d")
            start_date = (datetime.now() - timedelta(days=lookback_days)).strftime("%Y-%m-%d")
            
            result = await loop.run_in_executor(
                None,
                call_tool,
                "financial.pdr_reader",
                {"symbol": symbol, "start_date": start_date, "end_date": end_date, "source": "stooq"}
            )
            
            if not result or result.get("error"):
                print(f"[EDA Tool] PDR fetch failed: {result.get('error', 'Unknown')}")
                return None
                
            data = result.get("data", [])
            if not data:
                return None
                
            import pandas as pd
            df = pd.DataFrame(data)
            
            # 確保欄位小寫且包含必要項
            df.columns = [c.lower() for c in df.columns]
            
            # 存檔
            df.to_csv(csv_path, index=False)
            print(f"[EDA Tool] PDR data saved: {len(df)} records")
            
            return str(csv_path)
            
        except Exception as e:
            print(f"[EDA Tool] PDR processing failed: {e}")
            return None

    async def _prepare_stock_data(self, symbol: str, debate_id: str, lookback_days: int) -> str:
        """準備股票數據 CSV (Yahoo Finance Fallback)"""
        # 使用本地 data 目錄
        script_dir = Path(__file__).parent.parent
        data_dir = script_dir / "data" / "staging" / debate_id
        data_dir.mkdir(parents=True, exist_ok=True)
        
        csv_path = data_dir / f"{symbol}.csv"
        
        # 檢查是否已存在
        if csv_path.exists():
            print(f"[EDA Tool] CSV already exists: {csv_path.name}")
            return str(csv_path)
        
        # 拉取數據
        print(f"[EDA Tool] Downloading {symbol} data from Yahoo Finance...")
        
        try:
            import yfinance as yf
            import pandas as pd
            
            end_date = datetime.now()
            start_date = end_date - timedelta(days=lookback_days)
            
            ticker = yf.Ticker(symbol)
            df = ticker.history(start=start_date, end=end_date)
            
            if df.empty:
                print(f"[EDA Tool] No data for {symbol}")
                return None
            
            # 重置索引並選擇欄位
            df = df.reset_index()
            df = df[['Date', 'Open', 'High', 'Low', 'Close', 'Volume']]
            df.columns = ['date', 'open', 'high', 'low', 'close', 'volume']
            
            # 儲存
            df.to_csv(csv_path, index=False)
            print(f"[EDA Tool] Data saved: {len(df)} records")
            
            return str(csv_path)
            
        except Exception as e:
            print(f"[EDA Tool] Data download failed: {e}")
            return None
    
    async def _prepare_financial_data_basic(self, symbol: str, debate_id: str) -> dict:
        """
        拉取基本面財務數據
        
        整合:
        1. chinatimes.stock_fundamental - 基本面數據 (EPS, ROE, 本益比等)
        2. chinatimes.financial_ratios - 財務比率 (負債比、流動比等)
        
        Args:
            symbol: 股票代碼 (例如: 2330.TW)
            debate_id: 辯論 ID
            
        Returns:
            {
                "fundamental": {...},  # 基本面數據
                "ratios": {...},       # 財務比率
                "success": bool        # 是否成功
            }
        """
        print(f"[EDA Tool] Preparing financial data for {symbol}...")
        
        financial_data = {
            "fundamental": {},
            "ratios": {},
            "success": False
        }
        
        # 移除 .TW 後綴（ChinaTimes 使用純代碼）
        code = symbol.replace(".TW", "").replace(".TWO", "")
        
        from worker.tool_invoker import call_tool
        loop = asyncio.get_running_loop()
        
        # 並行拉取基本面和財務比率（性能優化）
        tasks = []
        
        # 1. 拉取基本面數據
        async def fetch_fundamental():
            try:
                print(f"[EDA Tool] Fetching fundamental data from ChinaTimes...")
                result = await loop.run_in_executor(
                    None, 
                    call_tool, 
                    "chinatimes.stock_fundamental", 
                    {"code": code}
                )
                
                if result and not result.get("error"):
                    fundamental_raw = result if isinstance(result, dict) else {}
                    normalized = self._normalize_chinatimes_fundamental(fundamental_raw)
                    print(f"[EDA Tool] ✓ Fundamental data fetched")
                    return normalized
                else:
                    print(f"[EDA Tool] ⚠️ Fundamental data fetch failed: {result.get('error', 'Unknown')}")
                    return {}
            except Exception as e:
                print(f"[EDA Tool] ⚠️ Fundamental data fetch error: {e}")
                return {}
        
        # 2. 拉取財務比率
        async def fetch_ratios():
            try:
                print(f"[EDA Tool] Fetching financial ratios from ChinaTimes...")
                result = await loop.run_in_executor(
                    None,
                    call_tool,
                    "chinatimes.financial_ratios",
                    {"code": code}
                )
                
                if result and not result.get("error"):
                    ratios_raw = result.get("data", {}) if isinstance(result, dict) else {}
                    normalized = self._normalize_chinatimes_ratios(ratios_raw)
                    print(f"[EDA Tool] ✓ Financial ratios fetched")
                    return normalized
                else:
                    print(f"[EDA Tool] ⚠️ Financial ratios fetch failed: {result.get('error', 'Unknown')}")
                    return {}
            except Exception as e:
                print(f"[EDA Tool] ⚠️ Financial ratios fetch error: {e}")
                return {}
        
        # 並行執行
        fundamental_task = fetch_fundamental()
        ratios_task = fetch_ratios()
        
        financial_data["fundamental"], financial_data["ratios"] = await asyncio.gather(
            fundamental_task, 
            ratios_task
        )
        
        # 判斷是否成功（至少有一個數據源）
        financial_data["success"] = bool(
            financial_data["fundamental"] or financial_data["ratios"]
        )
        
        if financial_data["success"]:
            print(f"[EDA Tool] ✓ Financial data preparation completed")
        else:
            print(f"[EDA Tool] ⚠️ Financial data preparation failed (all sources failed)")
        
        return financial_data
    
    def _normalize_chinatimes_fundamental(self, raw_data: dict) -> dict:
        """
        標準化 ChinaTimes 基本面數據
        
        Args:
            raw_data: ChinaTimes API 原始返回
            
        Returns:
            標準化後的數據字典
        """
        if not raw_data:
            return {}
        
        # 欄位映射表
        field_mapping = {
            "Code": "code",
            "Name": "name",
            "SectorName": "sector",
            "EPS": "eps",
            "ROE": "roe",
            "ROA": "roa",
            "PERatio": "pe_ratio",
            "PBRatio": "pb_ratio",
            "DividendYield": "dividend_yield",
            "MarketCap": "market_cap"
        }
        
        normalized = {}
        
        for old_key, new_key in field_mapping.items():
            value = raw_data.get(old_key)
            
            # 處理數值型欄位
            if value is not None and new_key in ["eps", "roe", "roa", "pe_ratio", "pb_ratio", "dividend_yield"]:
                try:
                    normalized[new_key] = float(value)
                except (ValueError, TypeError):
                    normalized[new_key] = None
            elif value is not None:
                normalized[new_key] = value
        
        return normalized
    
    def _normalize_chinatimes_ratios(self, raw_data: dict) -> dict:
        """
        標準化 ChinaTimes 財務比率數據
        
        Args:
            raw_data: ChinaTimes API 原始返回
            
        Returns:
            標準化後的數據字典
        """
        if not raw_data:
            return {}
        
        # 欄位映射表
        field_mapping = {
            "pe_ratio": "pe_ratio",
            "pb_ratio": "pb_ratio",
            "roe": "roe",
            "roa": "roa",
            "debt_ratio": "debt_ratio",
            "current_ratio": "current_ratio",
            "quick_ratio": "quick_ratio",
            "gross_margin": "gross_margin",
            "operating_margin": "operating_margin",
            "net_margin": "net_margin"
        }
        
        normalized = {}
        
        for old_key, new_key in field_mapping.items():
            value = raw_data.get(old_key)
            
            if value is not None:
                try:
                    normalized[new_key] = float(value)
                except (ValueError, TypeError):
                    normalized[new_key] = None
        
        return normalized

    async def _merge_financial_data_to_csv(self, csv_path: str, financial_data: dict) -> str:
        """
        將財務數據合併到價格 CSV 中
        
        Args:
            csv_path: 原始價格 CSV 路徑
            financial_data: 已準備好的財務數據
            
        Returns:
            合併後的 CSV 路徑 (會覆蓋原檔)
        """
        try:
            import pandas as pd
            import numpy as np
            
            # 讀取 CSV
            df = pd.read_csv(csv_path)
            
            # 準備要合併的欄位
            # 這裡簡單處理：因為財務數據是單點數據（最新一季/年），我們將其擴展到整個時間序列
            # 這樣 ydata-profiling 可以分析其與價格的相關性（雖然是常數，但可視化上有幫助）
            # 更進階的做法是拉取歷史財報數據並根據日期 merge，但在 Option A 中先簡化處理
            
            fundamental = financial_data.get("fundamental", {})
            ratios = financial_data.get("ratios", {})
            
            # 合併數據
            merge_data = {**fundamental, **ratios}
            
            # 過濾掉非數值和 None
            valid_data = {}
            for k, v in merge_data.items():
                if isinstance(v, (int, float)) and not pd.isna(v):
                    valid_data[k] = v
                    
            if not valid_data:
                print(f"[EDA Tool] No valid financial data to merge")
                return csv_path
                
            # 將財務數據加入 DataFrame (作為常數欄位)
            # 雖然是常數，但在短期回測 (120天) 中，季報數據通常是不變的
            for col, val in valid_data.items():
                df[col] = val
                
            # 儲存回 CSV
            df.to_csv(csv_path, index=False)
            print(f"[EDA Tool] Merged {len(valid_data)} financial columns to CSV")
            
            return csv_path
            
        except Exception as e:
            print(f"[EDA Tool] Failed to merge financial data: {e}")
            return csv_path
    
    async def _calculate_technical_indicators(self, csv_path: str) -> str:
        """
        使用 pandas-ta-classic 計算技術指標
        
        指標包含:
        - SMA (20, 50)
        - RSI (14)
        - MACD (12, 26, 9)
        - Bollinger Bands (20, 2)
        """
        try:
            import pandas as pd
            
            df = pd.read_csv(csv_path)
            
            # 確保有必要的價格欄位
            required = ['open', 'high', 'low', 'close', 'volume']
            if not all(col in df.columns for col in required):
                print(f"[EDA Tool] Missing price columns for technical indicators calculation")
                return csv_path
            
            # 使用 pandas_ta 擴展
            # 簡單移動平均線
            df.ta.sma(length=20, append=True)
            df.ta.sma(length=50, append=True)
            
            # 相對強弱指標
            df.ta.rsi(length=14, append=True)
            
            # MACD
            df.ta.macd(append=True)
            
            # 布林通道
            df.ta.bbands(append=True)
            
            # 儲存回 CSV
            df.to_csv(csv_path, index=False)
            print(f"[EDA Tool] Technical indicators calculated and saved to CSV")
            
            return csv_path
            
        except Exception as e:
            print(f"[EDA Tool] Failed to calculate technical indicators: {e}")
            import traceback
            traceback.print_exc()
            return csv_path
    
    async def _invoke_eda_service(self, csv_path: str) -> dict:
        """調用 ODS EDA 服務"""
        print(f"[EDA Tool] Invoking EDA service...")
        
        try:
            from worker.tool_invoker import call_tool
            
            params = {
                "csv_path": csv_path,
                "include_cols": [
                    "date", "close", "volume", "high", "low", 
                    "pe_ratio", "pb_ratio", "roe", "eps", "dividend_yield",
                    "SMA_20", "SMA_50", "RSI_14", 
                    "MACDH_12_26_9", "MACD_12_26_9", "MACDs_12_26_9",
                    "BBL_20_2.0", "BBM_20_2.0", "BBU_20_2.0"
                ],
                "sample": 50000,
                "lang": "zh"
            }
            
            # 使用 tool_invoker 調用 ODS adapter
            loop = asyncio.get_running_loop()
            result = await loop.run_in_executor(None, call_tool, "ods.eda_describe", params)
            
            if result.get("success") and result.get("data"):
                return result["data"]
            else:
                print(f"[EDA Tool] EDA service error: {result.get('error', 'Unknown')}")
                return None
                
        except Exception as e:
            print(f"[EDA Tool] EDA service invocation failed: {e}")
            return None
    
    def _validate_artifacts(self, artifacts: dict) -> dict:
        """驗證 EDA artifacts 品質"""
        print(f"[EDA Tool] Validating artifacts...")
        
        from worker.eda_gate_checker import EDAGateChecker
        
        checker = EDAGateChecker(min_rows=30, max_age_hours=24)
        result = checker.check(artifacts)
        
        if result['passed']:
            print(f"[EDA Tool] Validation passed")
        else:
            print(f"[EDA Tool] Validation failed: {len(result['issues'])} issues")
        
        return result
    
    def _ingest_artifacts(self, artifacts: dict, debate_id: str) -> list:
        """將 EDA artifacts 攝取到 Evidence 系統"""
        print(f"[EDA Tool] Ingesting artifacts to Evidence system...")
        
        from worker.evidence_lifecycle import EvidenceLifecycle
        
        lc = EvidenceLifecycle(debate_id)
        evidence_docs = []
        
        try:
            # 攝取 HTML 報表
            report_doc = lc.ingest_eda_artifact(
                agent_id="chairman",
                artifact_type="report",
                file_path=artifacts['report_path'],
                metadata=artifacts['metadata']
            )
            evidence_docs.append(report_doc)
            
            # 攝取圖表
            for plot_path in artifacts.get('plot_paths', []):
                doc = lc.ingest_eda_artifact(
                    agent_id="chairman",
                    artifact_type="plot",
                    file_path=plot_path,
                    metadata=artifacts['metadata']
                )
                evidence_docs.append(doc)
            
            # 攝取表格
            for table_path in artifacts.get('table_paths', []):
                doc = lc.ingest_eda_artifact(
                    agent_id="chairman",
                    artifact_type="table",
                    file_path=table_path,
                    metadata=artifacts['metadata']
                )
                evidence_docs.append(doc)
            
            print(f"[EDA Tool] Ingested {len(evidence_docs)} evidence documents")
            
        except Exception as e:
            print(f"[EDA Tool] Evidence ingestion partially failed: {e}")
        
        return evidence_docs
    
    def _format_summary(self, artifacts: dict, evidence_docs: list, symbol: str, financial_data: dict = None) -> str:
        """格式化 EDA 摘要文本（包含財務數據）"""
        meta = artifacts.get('metadata', {})
        
        # 建立 Evidence 引用
        evidence_refs = []
        for i, doc in enumerate(evidence_docs[:5], 1):
            evidence_refs.append(f"[E{i}] {doc.artifact_type.upper()} (ID: {doc.id})")
        
        # 基礎摘要
        summary = f"""
### EDA 自動分析報告

**分析標的**: {symbol}  
**數據期間**: {meta.get('rows', 'N/A')} 個交易日  
**數據品質**: 缺失率 {meta.get('missing_rate', 0) * 100:.2f}%  
**生成時間**: {meta.get('generated_at', 'N/A')}

**價格分析**:
- 完整統計報表已生成 [E1]
- 價格分布圖表 [E2]
- 相關性分析 [E3]
"""
        
        # 新增財務分析（如果有）
        if financial_data and financial_data.get("success"):
            fundamental = financial_data.get("fundamental", {})
            ratios = financial_data.get("ratios", {})
            
            if fundamental or ratios:
                summary += "\n**基本面分析**:\n"
                
                # 基本面指標
                if fundamental:
                    if fundamental.get("eps") is not None:
                        summary += f"- EPS（每股盈餘）: ${fundamental['eps']:.2f}\n"
                    if fundamental.get("roe") is not None:
                        summary += f"- ROE（股東權益報酬率）: {fundamental['roe']:.2f}%\n"
                    if fundamental.get("pe_ratio") is not None:
                        summary += f"- 本益比 (P/E): {fundamental['pe_ratio']:.2f}x\n"
                    if fundamental.get("dividend_yield") is not None:
                        summary += f"- 股息殖利率: {fundamental['dividend_yield']:.2f}%\n"
                
                # 財務比率
                if ratios:
                    summary += "\n**財務健康度**:\n"
                    if ratios.get("debt_ratio") is not None:
                        health = "健康" if ratios['debt_ratio'] < 50 else "偏高"
                        summary += f"- 負債比率: {ratios['debt_ratio']:.2f}% ({health})\n"
                    if ratios.get("current_ratio") is not None:
                        health = "良好" if ratios['current_ratio'] > 1.5 else "普通"
                        summary += f"- 流動比率: {ratios['current_ratio']:.2f} ({health})\n"
                    if ratios.get("gross_margin") is not None:
                        summary += f"- 毛利率: {ratios['gross_margin']:.2f}%\n"
        
        # Evidence 引用
        summary += f"""

**Evidence 引用**:
{chr(10).join(evidence_refs)}

**報表位置**: {artifacts.get('report_path', 'N/A')}

*註：詳細數據請參閱 HTML 報表與圖表。主席將基於此實證分析進行總結。*
"""
        
        return summary
