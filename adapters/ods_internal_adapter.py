"""
ODS (Open Data Scientist) Internal Adapter.

This adapter provides access to the internal EDA service for automated
exploratory data analysis. It wraps the /api/eda/describe endpoint.
"""
from adapters.tool_adapter import ToolAdapter
from typing import Dict, Any, Optional, List
import httpx
import os
import hashlib
import json
from tenacity import retry, stop_after_attempt, wait_exponential


class ODSInternalAdapter(ToolAdapter):
    """
    Adapter for ODS-internal EDA service.
    
    This tool allows agents (especially Chairman) to request automated
    exploratory data analysis on CSV datasets.
    """
    
    def __init__(self, base_url: str = None):
        """
        Initialize ODS adapter.
        
        Args:
            base_url: Base URL of the API service. If None, uses localhost.
        """
        # 優先使用傳入的 base_url，其次是環境變數，最後預設為 http://api:8000 (Docker 內部服務名稱)
        self.base_url = base_url or os.getenv("API_BASE_URL", "http://api:8000")
        self.timeout = 120.0  # EDA can take time for large datasets
        print(f"[ODSAdapter] Initialized with base_url: {self.base_url}")
    
    @property
    def name(self) -> str:
        return "ods.eda_describe"
    
    @property
    def version(self) -> str:
        return "v1"
    
    @property
    def description(self) -> str:
        return """
        自動化探索性數據分析 (EDA) 工具。
        
        功能：
        - 生成完整的 ydata-profiling HTML 報表
        - 產生基礎統計圖表 (直方圖、相關矩陣、箱型圖)
        - 提取摘要統計數據
        
        適用場景：
        - 主席需要對股票價格數據進行量化分析
        - 需要驗證辯手提出的數據聲明
        - 生成實證報告以支持總結
        
        注意：此工具需要 CSV 檔案已存在於 /data/staging 目錄下。
        """
    
    @property
    def cache_ttl(self) -> int:
        # EDA reports are expensive to generate, cache for 1 hour
        return 3600
    
    @property
    def schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "csv_path": {
                    "type": "string",
                    "description": "CSV 檔案的絕對路徑 (例如: /data/staging/debate_001/2330.TW.csv)"
                },
                "include_cols": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "可選：要分析的欄位列表。若未指定，分析所有欄位。"
                },
                "sample": {
                    "type": "integer",
                    "description": "可選：樣本數。若數據集超過此數量，將隨機抽樣。建議值：50000"
                },
                "lang": {
                    "type": "string",
                    "enum": ["zh", "en"],
                    "default": "zh",
                    "description": "報表語言"
                }
            },
            "required": ["csv_path"]
        }
    
    def describe(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "version": self.version,
            "description": self.description,
            "schema": self.schema
        }
    
    @retry(
        stop=stop_after_attempt(2),
        wait=wait_exponential(multiplier=1, min=2, max=10)
    )
    def _call_api(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Call the internal EDA API with retry logic.
        
        Args:
            payload: Request payload
            
        Returns:
            API response
            
        Raises:
            httpx.HTTPError: If API call fails after retries
        """
        url = f"{self.base_url}/api/eda/describe"
        
        with httpx.Client(timeout=self.timeout) as client:
            response = client.post(url, json=payload)
            response.raise_for_status()
            return response.json()
    
    def invoke(self, **kwargs: Any) -> Dict[str, Any]:
        """
        Execute EDA analysis.
        
        Args:
            csv_path: Path to CSV file
            include_cols: Optional column filter
            sample: Optional sample size
            lang: Report language
            
        Returns:
            Dictionary with:
                - report_path: Path to HTML report
                - plot_paths: List of plot image paths
                - table_paths: List of summary table paths
                - meta: Metadata (rows, cols, missing_rate, etc.)
        """
        csv_path = kwargs.get("csv_path")
        include_cols = kwargs.get("include_cols")
        sample = kwargs.get("sample")
        lang = kwargs.get("lang", "zh")
        
        if not csv_path:
            raise ValueError("csv_path is required")
        
        # Prepare request payload
        payload = {
            "csv_path": csv_path,
            "lang": lang
        }
        
        if include_cols:
            payload["include_cols"] = include_cols
        
        if sample:
            payload["sample"] = sample
        
        try:
            # Call API
            result = self._call_api(payload)
            
            # Format response
            return {
                "data": {
                    "report_path": result["report_path"],
                    "plot_paths": result["plot_paths"],
                    "table_paths": result["table_paths"],
                    "metadata": result["meta"]
                },
                "success": True
            }
            
        except httpx.HTTPError as e:
            error_msg = f"ODS EDA API call failed: {str(e)}"
            if hasattr(e, 'response') and e.response is not None:
                try:
                    error_detail = e.response.json().get("detail", str(e))
                    error_msg = f"ODS EDA API error: {error_detail}"
                except:
                    pass
            
            return {
                "error": error_msg,
                "success": False
            }
        
        except Exception as e:
            return {
                "error": f"Unexpected error in ODS adapter: {str(e)}",
                "success": False
            }
    
    def cache_key(self, params: Dict) -> str:
        """
        Generate cache key based on CSV path and parameters.
        
        Args:
            params: Tool parameters
            
        Returns:
            Cache key string
        """
        # Normalize params for consistent caching
        csv_path = params.get("csv_path", "")
        include_cols = sorted(params.get("include_cols", []))
        sample = params.get("sample")
        
        key_data = {
            "csv_path": csv_path,
            "include_cols": include_cols,
            "sample": sample
        }
        
        key_str = json.dumps(key_data, sort_keys=True)
        return f"ods_eda:{hashlib.md5(key_str.encode()).hexdigest()}"
