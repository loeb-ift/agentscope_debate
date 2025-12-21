"""
Advanced Institutional Metrics & AI Analysis Engine

Features:
- Precise Python Calculations (DCF, ROIC, EVA, FCF)
- ROIC Mean Reversion & Persistence Scoring
- Terminal Value Discount Factor
- AI Semantic Interpretation Labels
"""

import pandas as pd
import numpy as np
import json
from typing import Dict, Any, Optional, List

class MetricsEngineDCF_AI:
    def __init__(self, financials: pd.DataFrame, industry_roic: float = 0.10,
                 tax_rate: float = 0.25, risk_free_rate: float = 0.03,
                 equity_premium: float = 0.05, debt_cost: float = 0.04):
        self.fin = financials.sort_values('Year').reset_index(drop=True)
        self.industry_roic = industry_roic
        self.tax_rate = tax_rate
        self.risk_free_rate = risk_free_rate
        self.equity_premium = equity_premium
        self.debt_cost = debt_cost
        self.results = {}
        self.analysis = {}

    def calc_nopat(self):
        self.fin['NOPAT'] = self.fin['EBIT'] * (1 - self.tax_rate)
        return self.fin['NOPAT']

    def calc_invested_capital(self):
        self.fin['InvestedCapital'] = self.fin['Debt'] + self.fin['Equity'] - self.fin['Cash']
        return self.fin['InvestedCapital']

    def calc_roic(self):
        self.calc_nopat()
        self.calc_invested_capital()
        self.fin['ROIC'] = self.fin['NOPAT'] / (self.fin['InvestedCapital'] + 1e-6)
        self.results['ROIC'] = self.fin['ROIC'].tolist()
        return self.fin['ROIC']

    def calc_wacc(self, beta: float = 1.0):
        Re = self.risk_free_rate + beta * self.equity_premium
        D = self.fin['Debt']
        E = self.fin['Equity']
        V = D + E + 1e-6
        self.fin['WACC'] = (E/V) * Re + (D/V) * self.debt_cost * (1 - self.tax_rate)
        self.results['WACC'] = self.fin['WACC'].tolist()
        return self.fin['WACC']

    def calc_eva(self):
        self.calc_roic()
        self.calc_wacc()
        self.fin['EVA'] = self.fin['NOPAT'] - self.fin['InvestedCapital'] * self.fin['WACC']
        self.results['EVA'] = self.fin['EVA'].tolist()
        return self.fin['EVA']

    def calculate_persistence_discount(self):
        spread = self.fin['ROIC'] - self.fin['WACC']
        persistence_score = spread.std() if len(spread) > 1 else 0.03
        
        if len(self.fin) >= 2:
            reversion_rate = abs(self.fin['ROIC'].iloc[0] - self.fin['ROIC'].iloc[-1]) / len(self.fin)
        else:
            reversion_rate = 0.015

        discount = 1.0
        if persistence_score > 0.025: discount -= 0.15
        if reversion_rate > 0.01: discount -= 0.05
        if len(self.fin) < 5: discount -= 0.10

        self.results['TV_Discount_Factor'] = max(0.5, discount)
        return self.results['TV_Discount_Factor']

    def dcf_valuation(self, terminal_growth: float = 0.02, scenarios: dict = None):
        self.fin['FCF'] = self.fin['OperatingCashFlow'] - (self.fin['CapEx'] - self.fin.get('Depreciation', 0))
        tv_discount = self.calculate_persistence_discount()
        
        fcf = self.fin['FCF'].values
        wacc = self.fin['WACC'].mean()
        n_years = len(fcf)
        valuations = {}
        scenarios = scenarios or {'Base': terminal_growth, 'Bear': terminal_growth*0.5, 'Bull': terminal_growth*1.5}

        for name, g in scenarios.items():
            if wacc <= g: valuations[name] = 0; continue
            pv_fcf = sum([fcf[i]/((1+wacc)**(i+1)) for i in range(n_years)])
            tv = (fcf[-1]*(1+g)/(wacc - g)) * tv_discount
            tv_pv = tv / ((1+wacc)**n_years)
            valuations[name] = pv_fcf + tv_pv

        self.results['DCF_Valuation'] = valuations
        return valuations

    def run_all(self, equity_beta=1.0, persistence_factor=0.5, terminal_growth=0.02, scenarios=None):
        self.calc_eva() # This also triggers ROIC and WACC
        self.dcf_valuation(terminal_growth=terminal_growth, scenarios=scenarios)
        return {"metrics": self.results}

def run_ai_valuation_engine(financial_data: List[Dict[str, Any]], **kwargs) -> Dict[str, Any]:
    df = pd.DataFrame(financial_data)
    engine = MetricsEngineDCF_AI(df, industry_roic=kwargs.get('industry_roic', 0.10))
    return engine.run_all(
        equity_beta=kwargs.get('beta', 1.0),
        terminal_growth=kwargs.get('terminal_g', 0.02),
        scenarios=kwargs.get('scenarios')
    )
