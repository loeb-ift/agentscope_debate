import sys
import os
import json
import pandas as pd

# Add current directory to path
sys.path.append(os.path.join(os.getcwd(), "worker"))

try:
    from metrics_engine_dcf import run_valuation_engine
    
    print("--- 測試: 模擬台股 (TSMC 2330) 的 MetricsEngineDCF 調用 ---")
    
    # 模擬從 ChinaTimes 獲取的數據
    tsmc_data = [
        {
            'Year': 2021,
            'Revenue': 1587415000000,
            'EBIT': 650554000000,
            'NetIncome': 596540000000,
            'OperatingCashFlow': 1111629000000,
            'CapEx': 839196000000,
            'Depreciation': 415307000000,
            'Debt': 876356000000,
            'Cash': 1064989000000,
            'Equity': 2167909000000,
            'InterestExpense': 9102000000
        },
        {
            'Year': 2022,
            'Revenue': 2263891000000,
            'EBIT': 1121191000000,
            'NetIncome': 1016530000000,
            'OperatingCashFlow': 1610842000000,
            'CapEx': 1083431000000,
            'Depreciation': 446549000000,
            'Debt': 906231000000,
            'Cash': 1342686000000,
            'Equity': 2963177000000,
            'InterestExpense': 13540000000
        },
        {
            'Year': 2023,
            'Revenue': 2161736000000,
            'EBIT': 921469000000,
            'NetIncome': 838497000000,
            'OperatingCashFlow': 1472300000000,
            'CapEx': 949451000000,
            'Depreciation': 531289000000,
            'Debt': 951230000000,
            'Cash': 1476421000000,
            'Equity': 3381678000000,
            'InterestExpense': 24500000000
        }
    ]
    
    # 執行引擎
    results = run_valuation_engine(
        tsmc_data, 
        industry_roic=0.15, 
        beta=1.0, 
        terminal_g=0.02
    )
    
    print(f"公司: 台積電 (2330)")
    print(f"最新 ROIC: {results['ROIC'][-1]:.2%}")
    print(f"最新 EVA: {results['EVA'][-1]/1e8:.2f} 億元")
    print(f"最新 Cash Conversion: {results['CashConversion'][-1]:.2f}")
    print(f"ROIC Gate Status: {results['ROICGate'][-1]}")
    print("\nDCF 估值結果:")
    for scenario, val in results['DCF_Valuation'].items():
        print(f" - {scenario}: {val/1e12:.2f} 兆元")

except Exception as e:
    print(f"測試失敗: {str(e)}")
    import traceback
    traceback.print_exc()
