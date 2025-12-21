"""FinMind Data Loader Adapter implementation.
"""
from __future__ import annotations
import os
from typing import Dict, Any, Optional, List
import pandas as pd
import requests
from .base import BaseToolAdapter, ToolResult

class FinMindAdapter(BaseToolAdapter):
    name = "finmind.data_loader"
    version = "v1"
    description = """[Tier 1] 台灣股市全功能數據載入器 (FinMind)。提供財務報表、現金流量表、財務比率、股利與月營收。"""

    def __init__(self, api_token: Optional[str] = None):
        self.api_token = api_token or os.getenv("FINMIND_API_TOKEN", "")
        self.base_url = "https://api.finmindtrade.com/api/v4/data"

    def describe(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "parameters": {
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
        stock_id = kwargs.get("stock_id")
        data_type = kwargs.get("data_type")
        start_date = kwargs.get("start_date")

        dataset_map = {
            "financial_statement": "TaiwanStockFinancialStatements",
            "cash_flow": "TaiwanStockCashFlowsStatement",
            "financial_ratio": "TaiwanStockFinancialRatios",
            "dividend": "TaiwanStockDividend",
            "month_revenue": "TaiwanStockMonthRevenue"
        }

        params = {
            "dataset": dataset_map.get(data_type),
            "data_id": stock_id,
            "start_date": start_date,
            "token": self.api_token
        }

        try:
            resp = requests.get(self.base_url, params=params, timeout=15)
            resp.raise_for_status()
            raw_data = resp.json()
            
            if raw_data.get("msg") != "success":
                return ToolResult(data={"error": raw_data.get("msg")}, raw=raw_data)

            df = pd.DataFrame(raw_data.get("data", []))
            return ToolResult(
                data=df.to_dict(orient="records"),
                raw=raw_data,
                citations=[{"source": "FinMind", "url": self.base_url}]
            )
        except Exception as e:
            return ToolResult(data={"error": str(e)}, raw={})
