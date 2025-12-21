"""
Advanced Financial Reader for Agents

Implements logic for:
- Ratio calculations (Gross/Operating/Net Margin, FCF)
- Trend detection (Up/Down/Stable)
- Industry benchmarking
- Plain English interpretation and basic investment advice
"""

import pandas as pd
import json
from typing import Dict, Any, Optional, List

class AdvancedFinancialReader:
    def __init__(self, financials: pd.DataFrame, industry_avg: dict = None):
        """
        financials: DataFrame with columns:
            ['Year','Revenue','GrossProfit','EBIT','NetIncome','OperatingCashFlow','CapEx']
        """
        self.fin = financials.sort_values('Year').reset_index(drop=True)
        self.industry_avg = industry_avg or {}
        self.analysis = {}

    def calc_ratios(self):
        self.fin['GrossMargin'] = self.fin['GrossProfit'] / (self.fin['Revenue'] + 1e-6)
        self.fin['OperatingMargin'] = self.fin['EBIT'] / (self.fin['Revenue'] + 1e-6)
        self.fin['NetIncomeMargin'] = self.fin['NetIncome'] / (self.fin['Revenue'] + 1e-6)
        self.fin['FreeCashFlow'] = self.fin['OperatingCashFlow'] - self.fin['CapEx']
        return self.fin

    def calc_trends(self, col):
        values = self.fin[col].values
        trends = []
        for i in range(len(values)):
            if i == 0:
                trends.append('→')
            else:
                if values[i] > values[i-1]:
                    trends.append('↑')
                elif values[i] < values[i-1]:
                    trends.append('↓')
                else:
                    trends.append('→')
        return trends

    def compare_industry(self, col):
        avg = self.industry_avg.get(col, None)
        comparison = []
        if avg is not None:
            for val in self.fin[col]:
                if val > avg:
                    comparison.append('高於行業平均')
                elif val < avg:
                    comparison.append('低於行業平均')
                else:
                    comparison.append('持平行業平均')
        else:
            comparison = ['N/A'] * len(self.fin)
        return comparison

    def interpret_value(self, value, threshold_high=0.2, threshold_low=0.1):
        if value >= threshold_high:
            return "良好"
        elif value <= threshold_low:
            return "偏低"
        else:
            return "正常"

    def generate_analysis(self):
        self.calc_ratios()
        indicators = ['Revenue','GrossMargin','OperatingMargin','NetIncomeMargin','FreeCashFlow']
        for idx, row in self.fin.iterrows():
            year = int(row['Year'])
            self.analysis[year] = {}
            for col in indicators:
                trend = self.calc_trends(col)[idx]
                industry_comp = self.compare_industry(col)[idx]
                if col in ['GrossMargin','OperatingMargin','NetIncomeMargin']:
                    interp = self.interpret_value(row[col])
                elif col == 'FreeCashFlow':
                    interp = "充足" if row[col] > 0 else "偏低"
                else:
                    interp = "增長" if trend=='↑' else "下降" if trend=='↓' else "持平"
                
                self.analysis[year][col] = {
                    "value": float(row[col]),
                    "formatted_value": f"{row[col]:.2%}" if "Margin" in col else f"{row[col]/1e8:.2f} 億",
                    "trend": trend,
                    "industry_comparison": industry_comp,
                    "interpretation": interp
                }
            
            # Simple advice based on revenue trend and FCF
            rev_trend = self.analysis[year]['Revenue']['trend']
            fcf_status = self.analysis[year]['FreeCashFlow']['interpretation']
            if rev_trend=='↑' and fcf_status=='充足':
                advice = "建議持有"
            elif rev_trend=='↓' or fcf_status=='偏低':
                advice = "警示/觀望"
            else:
                advice = "中性"
            self.analysis[year]['InvestmentAdvice'] = advice
        return self.analysis

    def export_dict(self):
        return self.analysis

def run_advanced_reader(financial_data: List[Dict[str, Any]], industry_avg: Optional[Dict[str, float]] = None) -> Dict[str, Any]:
    df = pd.DataFrame(financial_data)
    reader = AdvancedFinancialReader(df, industry_avg=industry_avg)
    return reader.generate_analysis()
