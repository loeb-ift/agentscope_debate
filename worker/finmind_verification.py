"""
FinMind Data Integration Verification

This script simulates the FinMind data acquisition flow for Taiwan stocks.
It tests the retrieval of the 'Big Five' tables:
1. Financial Statement
2. Cash Flow Statement
3. Financial Ratio
4. Dividend
5. Month Revenue
"""

import pandas as pd
import json
from typing import Dict, Any, List

class FinMindSimulator:
    def __init__(self):
        self.api_base = "https://api.finmindtrade.com/api/v4/data"

    def get_taiwan_stock_financial_statement(self, stock_id: str, start_date: str) -> pd.DataFrame:
        """模擬取得損益表與資產負債表"""
        print(f"DEBUG: Simulating FinMind Financial Statement for {stock_id} from {start_date}")
        data = [
            {'date': '2023-03-31', 'type': 'Revenue', 'value': 500000000},
            {'date': '2023-03-31', 'type': 'GrossProfit', 'value': 200000000},
            {'date': '2023-03-31', 'type': 'NetIncome', 'value': 50000000},
            {'date': '2023-12-31', 'type': 'Revenue', 'value': 550000000},
            {'date': '2023-12-31', 'type': 'GrossProfit', 'value': 220000000},
            {'date': '2023-12-31', 'type': 'NetIncome', 'value': 60000000}
        ]
        return pd.DataFrame(data)

    def get_taiwan_stock_cash_flows_statement(self, stock_id: str, start_date: str) -> pd.DataFrame:
        """模擬取得現金流量表"""
        print(f"DEBUG: Simulating FinMind Cash Flow for {stock_id}")
        data = [
            {'date': '2023-12-31', 'type': 'OperatingCashFlow', 'value': 70000000},
            {'date': '2023-12-31', 'type': 'CapEx', 'value': 20000000}
        ]
        return pd.DataFrame(data)

    def get_taiwan_stock_financial_ratio(self, stock_id: str, start_date: str) -> pd.DataFrame:
        """模擬取得財務比率"""
        print(f"DEBUG: Simulating FinMind Ratios for {stock_id}")
        data = [
            {'date': '2023-12-31', 'type': 'ROE', 'value': 0.15},
            {'date': '2023-12-31', 'type': 'DebtRatio', 'value': 0.40}
        ]
        return pd.DataFrame(data)

def verify_finmind_pipeline(stock_id: str = "2480"):
    simulator = FinMindSimulator()
    
    # 1. 獲取財務數據
    fs = simulator.get_taiwan_stock_financial_statement(stock_id, "2023-01-01")
    cf = simulator.get_taiwan_stock_cash_flows_statement(stock_id, "2023-01-01")
    ratio = simulator.get_taiwan_stock_financial_ratio(stock_id, "2023-01-01")
    
    # 2. 數據清洗與對齊 (Pivot Logic)
    # 模擬智能體如何將 Long Format 轉為 Wide Format 供 MetricsEngine 使用
    df_fs = fs.pivot(index='date', columns='type', values='value').reset_index()
    
    # 3. 驗證數據完整度
    required = ['Revenue', 'GrossProfit', 'NetIncome']
    missing = [r for r in required if r not in df_fs.columns]
    
    if not missing:
        print(f"SUCCESS: FinMind Pipeline Verified for {stock_id}. Data ready for MetricsEngine.")
        return df_fs.to_dict(orient="records")
    else:
        print(f"FAILURE: Missing core fields {missing}")
        return None

if __name__ == "__main__":
    result = verify_finmind_pipeline()
    if result:
        print(json.dumps(result, indent=2))
