"""
SEC EDGAR XBRL Global Tool - Advanced Core Metrics Engine

This module transforms raw SEC XBRL data into institutional-grade metrics
by piping data into the Python MetricsEngineDCF and AdvancedFinancialReader.
"""

import requests
import pandas as pd
import numpy as np
from typing import Dict, Any, Optional, List
import structlog

try:
    from .metrics_engine_dcf import run_ai_valuation_engine
    from .advanced_financial_reader import run_advanced_reader
except ImportError:
    from metrics_engine_dcf import run_ai_valuation_engine
    from advanced_financial_reader import run_advanced_reader

logger = structlog.get_logger()

DEFAULT_HEADERS = {
    "User-Agent": "RooAgent roo@example.com",
    "Accept-Encoding": "gzip, deflate",
    "Host": "data.sec.gov"
}

class SECEDGARClient:
    def __init__(self, user_agent: Optional[str] = None):
        self.headers = DEFAULT_HEADERS.copy()
        if user_agent: self.headers["User-Agent"] = user_agent
        self.session = requests.Session()
        self.session.headers.update(self.headers)

    def _get_fact_df(self, data: Dict[str, Any], fact_name: str) -> pd.DataFrame:
        try:
            facts = data.get("facts", {}).get("us-gaap", {})
            if fact_name not in facts: return pd.DataFrame()
            units = facts[fact_name].get("units", {})
            for unit_key in ["USD", "USD/shares", "shares"]:
                if unit_key in units: return pd.DataFrame(units[unit_key])
            return pd.DataFrame()
        except Exception: return pd.DataFrame()

    def get_company_facts(self, cik: str) -> Dict[str, Any]:
        cik_padded = cik.zfill(10)
        url = f"https://data.sec.gov/api/xbrl/companyfacts/CIK{cik_padded}.json"
        try:
            resp = self.session.get(url, timeout=15)
            resp.raise_for_status()
            return resp.json()
        except Exception as e: return {"error": str(e)}

    def map_xbrl_to_financial_df(self, data: Dict[str, Any]) -> pd.DataFrame:
        def get_clean(fact_name):
            df = self._get_fact_df(data, fact_name)
            if df.empty: return df
            df = df[df['form'] == '10-K']
            if df.empty: df = self._get_fact_df(data, fact_name)
            df = df.sort_values(["end", "filed"], ascending=[False, False])
            df = df.drop_duplicates(subset=["end"], keep="first")
            df['Year'] = pd.to_datetime(df['end']).dt.year
            df = df.drop_duplicates(subset=["Year"], keep="first")
            return df

        mapping = {
            'Revenue': ["RevenueFromContractWithCustomerExcludedFromTax", "Revenues"],
            'GrossProfit': ["GrossProfit"],
            'EBIT': ["OperatingIncomeLoss"],
            'NetIncome': ["NetIncomeLoss"],
            'OperatingCashFlow': ["NetCashProvidedByUsedInOperatingActivities"],
            'CapEx': ["PaymentsToAcquirePropertyPlantAndEquipment"],
            'Depreciation': ["DepreciationDepletionAndAmortization"],
            'Debt': ["LongTermDebt", "DebtCurrent"],
            'Cash': ["CashAndCashEquivalentsAtCarryingValue"],
            'Equity': ["StockholdersEquity"],
            'InterestExpense': ["InterestExpense"]
        }

        fin_data = {}
        all_years = set()
        for col, tags in mapping.items():
            for tag in tags:
                df = get_clean(tag)
                if not df.empty:
                    series = df.set_index('Year')['val']
                    if col not in fin_data: fin_data[col] = series
                    else: fin_data[col] = fin_data[col].add(series, fill_value=0)
                    all_years.update(series.index.tolist())
        
        final_df = pd.DataFrame(index=sorted(list(all_years)))
        for col, series in fin_data.items(): final_df[col] = series
        return final_df.reset_index().rename(columns={'index': 'Year'}).fillna(0)

def get_sec_company_facts(cik: str, **kwargs) -> Dict[str, Any]:
    client = SECEDGARClient()
    raw_data = client.get_company_facts(cik)
    if "error" in raw_data: return {"success": False, "error": raw_data["error"]}
    
    fin_df = client.map_xbrl_to_financial_df(raw_data)
    if fin_df.empty: return {"success": False, "error": "Insufficient XBRL data tags"}

    engine_input = fin_df.to_dict(orient="records")
    
    # 執行估值引擎
    valuation_results = run_ai_valuation_engine(engine_input, **kwargs)
    
    # 執行白話解讀引擎
    industry_avg = kwargs.get('industry_avg', {})
    simple_reading = run_advanced_reader(engine_input, industry_avg=industry_avg)
    
    return {
        "success": True,
        "entity": raw_data.get("entityName"),
        "cik": raw_data.get("cik"),
        "raw_financials": fin_df.tail(5).to_dict(orient="records"),
        "valuation_engine": valuation_results,
        "simple_reading": simple_reading
    }
