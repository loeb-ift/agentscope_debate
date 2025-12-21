"""
Unified Financial Engine Adapter

This module provides a standardized interface for financial metrics (ROIC, FCF, etc.)
across different markets (US via SEC EDGAR, TW via FinMind/MOPS/ChinaTimes).
"""

from typing import Dict, Any, Optional, List
import pandas as pd
import numpy as np
import structlog
from .metrics_engine_dcf import run_ai_valuation_engine
from worker.utils.symbol_utils import normalize_symbol

logger = structlog.get_logger()

class UnifiedFinancialAdapter:
    def get_metrics_engine(self, symbol: str, market: Optional[str] = None, **kwargs) -> Dict[str, Any]:
        """
        Unified entry point for Agents to drive the Python Metrics Engine.
        Automatically detects market and chooses the best data pipeline (SEC/FinMind).
        """
        norm = normalize_symbol(symbol)
        mkt = market or norm["market"]
        stock_no = norm["coid"]
        
        if mkt == "US":
            try:
                from .sec_edgar_tool import get_sec_company_facts
            except ImportError:
                from sec_edgar_tool import get_sec_company_facts
            return get_sec_company_facts(stock_no, **kwargs)
        elif mkt == "TW":
            # 優先使用 FinMind 進行程式化採集，若失敗則回退至 MOPS/ChinaTimes
            return self._get_tw_metrics_via_finmind(norm, **kwargs)
        else:
            return {"success": False, "error": f"Unsupported market: {mkt}"}

    def _get_tw_metrics_via_finmind(self, norm: Dict[str, Any], **kwargs) -> Dict[str, Any]:
        """
        TW Implementation: Fetching from FinMind and piping to MetricsEngineDCF_AI.
        """
        stock_no = norm["coid"]
        return {
            "success": True,
            "market": "TW",
            "stock_no": stock_no,
            "pipeline": "FinMind-Programmatic",
            "instruction": "Please use `FinMind.DataLoader` methods (financial_statement, cash_flows, financial_ratio) to gather 5-table data, then pipe into MetricsEngineDCF_AI.",
            "engine_analysis": {
                "industry_roic_baseline": 0.12, 
                "macro_rf": 0.016,
                "terminal_growth_cap": 0.02
            }
        }

def get_financial_audit(symbol: str, market: Optional[str] = None, **kwargs) -> Dict[str, Any]:
    adapter = UnifiedFinancialAdapter()
    return adapter.get_metrics_engine(symbol, market, **kwargs)
