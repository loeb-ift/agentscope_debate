import sys
import os
import json

# Add current directory to path
sys.path.append(os.path.join(os.getcwd(), "worker"))

try:
    from financial_engine_adapter import get_financial_audit
    
    print("--- 測試: 跨市場與跨實體類型 (Listing) 路由測試 ---")
    
    # 測試 1: 台灣上市 (2330.TW)
    tsmc = get_financial_audit("2330.TW")
    print(f"TSMC (2330.TW) -> Market: {tsmc['market']}, Exchange: {tsmc['exchange']}, MOPS Route: {tsmc['mops_route']}")
    
    # 測試 2: 台灣上櫃 (8432.TWO)
    medfirst = get_financial_audit("8432.TWO")
    print(f"MedFirst (8432.TWO) -> Market: {medfirst['market']}, Exchange: {medfirst['exchange']}, MOPS Route: {medfirst['mops_route']}")
    
    # 測試 3: 美股 (MSFT)
    msft = get_financial_audit("MSFT")
    print(f"MSFT -> Market: {msft.get('market', 'US (from sec_edgar)')}, CIK: {msft.get('cik')}")

except Exception as e:
    print(f"測試失敗: {str(e)}")
    import traceback
    traceback.print_exc()
