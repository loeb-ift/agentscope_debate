import sys
import os
import json

# Add current directory to path so we can import from worker
sys.path.append(os.path.join(os.getcwd(), "worker"))

try:
    from sec_edgar_tool import get_sec_company_facts
    from agent_tool_registry import call_tool
    
    print("--- 測試 1: 直接調用 sec_edgar_tool ---")
    # Apple CIK: 0000320193
    apple_result = get_sec_company_facts("320193", limit=3)
    print(json.dumps(apple_result, indent=2, ensure_ascii=False))
    
    print("\n--- 測試 2: 通過 agent_tool_registry 調用 ---")
    registry_result = call_tool("sec.company_facts", cik="0001318605", limit=3) # Tesla CIK
    print(f"公司名稱: {registry_result.get('entity')}")
    print(f"成功狀態: {registry_result.get('success')}")
    if registry_result.get('success'):
        engine_res = registry_result.get('valuation_engine', {})
        metrics = engine_res.get('metrics', {})
        eva_data = metrics.get('EVA', [])
        print(f"獲取到 {len(eva_data)} 筆 EVA 指標數據")
        if len(eva_data) > 0:
            latest_eva = eva_data[-1]
            print(f"最新年度 EVA (經濟利益): {latest_eva/1e9:.2f} Billion USD")
            print(f"EVA 狀態: {'創造價值 (Value Creator)' if latest_eva > 0 else '價值毀損 (Value Destroyer)'}")

except Exception as e:
    print(f"測試失敗: {str(e)}")
    import traceback
    traceback.print_exc()
