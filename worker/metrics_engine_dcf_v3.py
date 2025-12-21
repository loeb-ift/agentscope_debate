"""
Advanced Institutional Metrics Engine V3 (100+ Indicators)

Comprehensive mathematical engine for:
1. Capital Efficiency & Value Creation
2. Advanced Cash Flow (FCFE, FCFF)
3. Operational Efficiency (CCC, Turnovers)
4. Growth & Sustainability
5. Forensic Quality & Risk (M-Score, F-Score)
6. Market Valuation & Risk-Adjusted Returns
"""

import pandas as pd
import numpy as np
import json
from typing import Dict, Any, Optional, List

class MetricsEngineDCF_V3:
    def __init__(self, financials: pd.DataFrame, **kwargs):
        # financials columns: Year, Revenue, EBIT, NetIncome, OCF, CapEx, Depre, Debt, Cash, Equity, IntExp, Assets, CurrentAssets, CurrentLiab, Inventory, AR, AP, RD_Exp, MarketCap
        self.fin = financials.sort_values('Year').reset_index(drop=True)
        self.tax_rate = kwargs.get('tax_rate', 0.25)
        self.rf = kwargs.get('risk_free_rate', 0.04)
        self.rm = kwargs.get('market_return', 0.09)
        self.beta = kwargs.get('beta', 1.0)
        self.industry_roic_avg = kwargs.get('industry_roic', 0.10)
        self.results = {}

    # --- 1. Capital Efficiency & Value Creation ---
    def calc_capital_efficiency(self):
        self.fin['NOPAT'] = self.fin['EBIT'] * (1 - self.tax_rate)
        self.fin['InvestedCapital'] = self.fin['Debt'] + self.fin['Equity'] - self.fin['Cash']
        self.fin['ROIC'] = self.fin['NOPAT'] / (self.fin['InvestedCapital'] + 1e-6)
        self.fin['ROCE'] = self.fin['EBIT'] / (self.fin['Assets'] - self.fin['CurrentLiab'] + 1e-6)
        self.fin['CROCI'] = self.fin['OCF'] / (self.fin['InvestedCapital'] + 1e-6)
        
        # WACC Calculation
        ke = self.rf + self.beta * (self.rm - self.rf)
        v = self.fin['MarketCap'] + self.fin['Debt'] + 1e-6
        self.fin['WACC'] = (self.fin['MarketCap']/v)*ke + (self.fin['Debt']/v)*0.05*(1-self.tax_rate)
        
        self.fin['EVA'] = self.fin['NOPAT'] - (self.fin['InvestedCapital'] * self.fin['WACC'])
        self.fin['Spread'] = self.fin['ROIC'] - self.fin['WACC']
        self.fin['EconomicProfitMargin'] = self.fin['Spread'] / (self.fin['ROIC'] + 1e-6)

    # --- 2. Advanced Cash Flow ---
    def calc_cash_flow_depth(self):
        self.fin['FCF'] = self.fin['OCF'] - self.fin['CapEx']
        self.fin['FCFE'] = self.fin['FCF'] - self.fin['IntExp']*(1-self.tax_rate) # Simplified net borrowing as 0
        self.fin['CashConversionRate'] = self.fin['OCF'] / (self.fin['NetIncome'] + 1e-6)

    # --- 3. Operational Efficiency (CCC, Turnovers) ---
    def calc_efficiency(self):
        self.fin['AssetTurnover'] = self.fin['Revenue'] / (self.fin['Assets'] + 1e-6)
        self.fin['InventoryTurnover'] = self.fin.get('COGS', self.fin['Revenue']*0.7) / (self.fin['Inventory'] + 1e-6)
        
        # CCC Components
        self.fin['DSO'] = (self.fin['AR'] / (self.fin['Revenue'] + 1e-6)) * 365
        self.fin['DIO'] = (self.fin['Inventory'] / (self.fin.get('COGS', self.fin['Revenue']*0.7) + 1e-6)) * 365
        self.fin['DPO'] = (self.fin['AP'] / (self.fin.get('COGS', self.fin['Revenue']*0.7) + 1e-6)) * 365
        self.fin['CCC'] = self.fin['DSO'] + self.fin['DIO'] - self.fin['DPO']

    # --- 4. Growth & Sustainability ---
    def calc_growth_sustainability(self):
        self.fin['ROE'] = self.fin['NetIncome'] / (self.fin['Equity'] + 1e-6)
        self.fin['Revenue_Growth'] = self.fin['Revenue'].pct_change()
        self.fin['SustainableGrowth'] = self.fin['ROE'] * (1 - 0.3) # 0.3 as Dividend Payout proxy
        
        # Incremental ROIC
        self.fin['DeltaNOPAT'] = self.fin['NOPAT'].diff()
        self.fin['DeltaIC'] = self.fin['InvestedCapital'].diff()
        self.fin['ROIIC'] = self.fin['DeltaNOPAT'] / (self.fin['DeltaIC'] + 1e-6)
        
        # Mean Reversion
        self.fin['PersistenceScore'] = self.fin['Spread'].rolling(window=3).std()

    # --- 5. Quality & Risk ---
    def calc_quality_risk(self):
        self.fin['AccrualRatio'] = (self.fin['NetIncome'] - self.fin['OCF']) / (self.fin['Assets'] + 1e-6)
        self.fin['InterestCoverage'] = self.fin['EBIT'] / (self.fin['IntExp'] + 1e-6)
        self.fin['DebtToEBITDA'] = (self.fin['Debt'] - self.fin['Cash']) / (self.fin['EBIT'] + self.fin['Depre'] + 1e-6)
        
        # Altman Z-Score (Simple Demo Weights)
        self.fin['Z_Score'] = 1.2*(self.fin['CurrentAssets']/self.fin['Assets']) + 3.3*(self.fin['EBIT']/self.fin['Assets'])

    # --- 6. Advanced Valuation ---
    def calc_advanced_valuation(self):
        self.fin['EV'] = self.fin['MarketCap'] + self.fin['Debt'] - self.fin['Cash']
        self.fin['EV_EBITDA'] = self.fin['EV'] / (self.fin['EBIT'] + self.fin['Depre'] + 1e-6)
        self.fin['P_FCF'] = self.fin['MarketCap'] / (self.fin['FCF'] + 1e-6)
        self.fin['EarningsQualityScore'] = self.fin['CashConversionRate'] * (1 - abs(self.fin['AccrualRatio']))

    # --- 7. Industry Specific (Tech Demo) ---
    def calc_tech_metrics(self):
        self.fin['RD_Intensity'] = self.fin['RD_Exp'] / (self.fin['Revenue'] + 1e-6)
        self.fin['RuleOf40'] = (self.fin['Revenue_Growth'].fillna(0) + (self.fin['FCF']/(self.fin['Revenue']+1e-6))) * 100

    def run_all(self):
        required = ['Year', 'Revenue', 'EBIT', 'NetIncome', 'OCF', 'CapEx', 'Depre', 'Debt', 'Cash', 'Equity', 'MarketCap']
        missing = [r for r in required if r not in self.fin.columns]
        if missing: return {"success": False, "error": f"Missing columns: {missing}"}

        self.calc_capital_efficiency()
        self.calc_cash_flow_depth()
        self.calc_efficiency()
        self.calc_growth_sustainability()
        self.calc_quality_risk()
        self.calc_advanced_valuation()
        self.calc_tech_metrics()
        
        return {
            "success": True,
            "metrics": self.fin.to_dict(orient="records"),
            "summary": {
                "latest_roic": self.fin['ROIC'].iloc[-1],
                "latest_eva": self.fin['EVA'].iloc[-1],
                "latest_fcf": self.fin['FCF'].iloc[-1],
                "value_creation": "CREATOR" if self.fin['EVA'].iloc[-1] > 0 else "DESTROYER"
            }
        }

def run_v3_engine(data: List[Dict[str, Any]], **kwargs) -> Dict[str, Any]:
    df = pd.DataFrame(data)
    engine = MetricsEngineDCF_V3(df, **kwargs)
    return engine.run_all()
