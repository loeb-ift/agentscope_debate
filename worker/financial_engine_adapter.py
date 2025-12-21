"""
Unified Financial Engine Adapter

This module provides a standardized interface for financial metrics (ROIC, FCF, etc.)
across different markets (US via SEC EDGAR, TW via ChinaTimes/MOPS).
"""

from typing import Dict, Any, Optional, List
import pandas as pd
import numpy as np
import structlog
try:
    from .metrics_engine_dcf import run_ai_valuation_engine
except ImportError:
    from metrics_engine_dcf import run_ai_valuation_engine

from worker.utils.symbol_utils import normalize_symbol

logger = structlog.get_logger()

class UnifiedFinancialAdapter:
    def get_metrics_engine(self, symbol: str, market: Optional[str] = None, **kwargs) -> Dict[str, Any]:
        """
        Unified entry point for Agents to drive the Python Metrics Engine.
        Automatically detects market and entity type (Listed/OTC).
        """
        # 1. 自動偵測與標準化符號
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
            return self._get_tw_metrics_via_mops(norm, **kwargs)
        else:
            return {"success": False, "error": f"Unsupported market: {mkt}"}

    def _get_tw_metrics_via_mops(self, norm: Dict[str, Any], **kwargs) -> Dict[str, Any]:
        """
        TW Implementation: Supporting TSE/OTC routing for MOPS tables.
        """
        stock_no = norm["coid"]
        # 使用 symbol_utils 中的 exchange 資訊進行精確導航
        # exchange: 'TWSE' -> stk_tw, 'TPEx' -> stk_otc
        mkt_tag = "stk_otc" if norm["exchange"] == "TPEx" else "stk_tw"
        
        return {
            "success": True,
            "market": "TW",
            "stock_no": stock_no,
            "exchange": norm["exchange"],
            "mops_route": mkt_tag,
            "instruction": f"Entity detected on {norm['exchange']}. Use route '{mkt_tag}' for MOPS tables t164sb03/04/05.",
            "engine_analysis": {
                "industry_roic_baseline": 0.12, 
                "macro_rf": 0.016,
                "terminal_growth_cap": 0.02
            }
        }

def get_financial_audit(symbol: str, market: Optional[str] = None, **kwargs) -> Dict[str, Any]:
    adapter = UnifiedFinancialAdapter()
    return adapter.get_metrics_engine(symbol, market, **kwargs)
