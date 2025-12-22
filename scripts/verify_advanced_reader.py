import sys
import os
import json
import pandas as pd

# Add current directory to path
sys.path.append(os.path.join(os.getcwd(), "worker"))

try:
    from advanced_financial_reader import run_advanced_reader
    
    print("--- 測試: AdvancedFinancialReader 邏輯 ---")
    
    # 模擬數據
    data = [
        {
            'Year': 2021,
            'Revenue': 1000000,
            'GrossProfit': 450000,
            'EBIT': 200000,
            'NetIncome': 150000,
            'OperatingCashFlow': 160000,
            'CapEx': 50000
        },
        {
            'Year': 2022,
            'Revenue': 1200000,
            'GrossProfit': 540000,
            'EBIT': 250000,
            'NetIncome': 180000,
            'OperatingCashFlow': 190000,
            'CapEx': 60000
        },
        {
            'Year': 2023,
            'Revenue': 1300000,
            'GrossProfit': 585000,
            'EBIT': 280000,
            'NetIncome': 200000,
            'OperatingCashFlow': 220000,
            'CapEx': 70000
        }
    ]
    
    industry_avg = {
        'GrossMargin': 0.42,
        'OperatingMargin': 0.18,
        'NetIncomeMargin': 0.13,
        'FreeCashFlow': 100000
    }
    
    analysis = run_advanced_reader(data, industry_avg=industry_avg)
    print(json.dumps(analysis, indent=2, ensure_ascii=False))

except Exception as e:
    print(f"測試失敗: {str(e)}")
    import traceback
    traceback.print_exc()
