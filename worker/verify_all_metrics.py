import sys
import os
import json
import pandas as pd

# Add current directory to path
sys.path.append(os.path.join(os.getcwd(), "worker"))

try:
    from metrics_engine_dcf_v3 import run_v3_engine
    
    print("--- [REAL CASE TEST] 敦陽 (2480.TW) - Metrics Engine V3 ---")
    
    # 實際敦陽數據 (大約值，用於驗證邏輯)
    data_2480 = [
        {
            'Year': 2022,
            'Revenue': 6714000000,
            'EBIT': 647000000,
            'NetIncome': 528000000,
            'OCF': 720000000,
            'CapEx': 15000000,
            'Depre': 25000000,
            'Debt': 0,
            'Cash': 2400000000,
            'Equity': 2800000000,
            'MarketCap': 6500000000,
            'IntExp': 0,
            'Assets': 5600000000,
            'CurrentAssets': 4500000000,
            'CurrentLiab': 2800000000,
            'Inventory': 800000000,
            'AR': 1200000000,
            'AP': 1100000000,
            'RD_Exp': 150000000
        },
        {
            'Year': 2023,
            'Revenue': 7254000000,
            'EBIT': 732000000,
            'NetIncome': 612000000,
            'OCF': 850000000,
            'CapEx': 18000000,
            'Depre': 28000000,
            'Debt': 0,
            'Cash': 2800000000,
            'Equity': 3100000000,
            'MarketCap': 7200000000,
            'IntExp': 0,
            'Assets': 6200000000,
            'CurrentAssets': 5100000000,
            'CurrentLiab': 3100000000,
            'Inventory': 950000000,
            'AR': 1400000000,
            'AP': 1300000000,
            'RD_Exp': 180000000
        }
    ]
    
    print(f"INPUT: Loaded 2 years of 2480.TW core financial data.")

    # 執行 V3 引擎
    results = run_v3_engine(
        data_2480, 
        industry_roic=0.15
    )
    
    if results['success']:
        latest = results['metrics'][-1]
        print(f"\n[2480.TW 審計結果]")
        print(f"1. 資本回報: ROIC={latest['ROIC']:.2%}, Spread={latest['Spread']:.2%}")
        print(f"2. 現金流品質: CashConversion={latest['CashConversionRate']:.2f}, FCF={latest['FCF']/1e6:.2f} M")
        print(f"3. 營運效率: CCC={latest['CCC']:.1f} days, AssetTurnover={latest['AssetTurnover']:.2f}")
        print(f"4. 財務安全: Z-Score={latest['Z_Score']:.2f} (高分代表穩健)")
        print(f"5. 估值參考: EV/EBITDA={latest['EV_EBITDA']:.2f}, P/FCF={latest['P_FCF']:.2f}")
        print(f"6. 價值判定: {results['summary']['value_creation']}")

except Exception as e:
    print(f"VERIFICATION FAILURE: {str(e)}")
    import traceback
    traceback.print_exc()
