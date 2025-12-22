"""FinMind Data Loader Adapter implementation.
"""
from __future__ import annotations
import os
from typing import Dict, Any, Optional, List
import pandas as pd
import requests
from .base import BaseToolAdapter, ToolResult

class FinMindAdapter(BaseToolAdapter):
    @property
    def name(self) -> str:
        return "finmind.data_loader"

    @property
    def version(self) -> str:
        return "v1"

    @property
    def description(self) -> str:
        return """[Tier 1] 台灣股市全功能數據載入器 (FinMind)。提供財務報表、現金流量表、財務比率、股利與月營收。"""

    def __init__(self, api_token: Optional[str] = None):
        self.api_token = api_token or os.getenv("FINMIND_API_TOKEN", "")
        self.base_url = "https://api.finmindtrade.com/api/v4/data"

    @property
    def auth_config(self) -> Dict:
        return {}

    @property
    def rate_limit_config(self) -> Dict:
        return {"tps": 1}

    @property
    def cache_ttl(self) -> int:
        return 3600

    def validate(self, params: Dict) -> None:
        # Auto-correct nested params (Hallucination fix)
        if "params" in params and isinstance(params["params"], dict):
            params.update(params["params"])

        if "stock_id" not in params:
            for alias in ["code", "symbol", "ticker", "id", "coid"]:
                if alias in params:
                    params["stock_id"] = params[alias]
                    break
        
        if "stock_id" not in params:
            raise ValueError("stock_id is required")
        if "data_type" not in params:
             raise ValueError("data_type is required")
        if "start_date" not in params:
             raise ValueError("start_date is required")

    def auth(self, req: Dict) -> Dict:
        return req

    def should_cache(self, params: Dict) -> bool:
        return True

    def cache_key(self, params: Dict) -> str:
        return f"finmind:{params.get('stock_id')}:{params.get('data_type')}"

    def map_error(self, http_status: int, body: Any) -> Exception:
        return Exception(f"FinMind Error {http_status}: {body}")

    def describe(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "version": self.version,
            "description": self.description,
            "schema": {
                "type": "object",
                "properties": {
                    "stock_id": {"type": "string", "description": "股票代碼 (e.g. '2480')"},
                    "data_type": {
                        "type": "string", 
                        "description": "數據類型",
                        "enum": ["financial_statement", "cash_flow", "financial_ratio", "dividend", "month_revenue"]
                    },
                    "start_date": {"type": "string", "description": "開始日期 (YYYY-MM-DD)"}
                },
                "required": ["stock_id", "data_type", "start_date"]
            }
        }

    def invoke(self, **kwargs) -> ToolResult:
        params = kwargs
        self.validate(params)
        stock_id = params.get("stock_id")
        data_type = params.get("data_type")
        start_date = params.get("start_date")

        dataset_map = {
            "financial_statement": "TaiwanStockFinancialStatements",
            "cash_flow": "TaiwanStockCashFlowsStatement",
            "financial_ratio": "TaiwanStockFinancialRatios",
            "dividend": "TaiwanStockDividend",
            "month_revenue": "TaiwanStockMonthRevenue"
        }

        params_api = {
            "dataset": dataset_map.get(data_type),
            "data_id": stock_id,
            "start_date": start_date,
            "token": self.api_token
        }

        try:
            resp = requests.get(self.base_url, params=params_api, timeout=15)
            resp.raise_for_status()
            raw_data = resp.json()
            
            if raw_data.get("msg") != "success":
                return ToolResult(data={"error": raw_data.get("msg")}, raw=raw_data, used_cache=False, cost=0.0, citations=[])

            df = pd.DataFrame(raw_data.get("data", []))
            return ToolResult(
                data=df.to_dict(orient="records"),
                raw=raw_data,
                used_cache=False,
                cost=0.0,
                citations=[{"source": "FinMind", "url": self.base_url}]
            )
        except Exception as e:
            return ToolResult(data={"error": str(e)}, raw={}, used_cache=False, cost=0.0, citations=[])
