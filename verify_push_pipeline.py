import sys
import os
import json

# Add current directory to path
sys.path.append(os.path.join(os.getcwd(), "worker"))

try:
    from agent_tool_registry import call_tool
    
    print("=== [STEP 1] Data Fetch & Calculate (Simulation) ===")
    # 模擬 TSMC 數據
    tsmc_data = [
        {'Year': 2023, 'Revenue': 2e12, 'EBIT': 9e11, 'NetIncome': 8e11, 'OperatingCashFlow': 1.4e12, 'CapEx': 9e11, 'Debt': 9e11, 'Cash': 1.4e12, 'Equity': 3e12, 'InterestExpense': 2e10}
    ]
    
    from metrics_engine_dcf import run_ai_valuation_engine
    calc_results = run_ai_valuation_engine(tsmc_data, industry_roic=0.15)
    print("CALC: Precise Metrics generated.")

    print("\n=== [STEP 2] Audit & Verdict (Simulation) ===")
    verdict = "合理價區間 1000-1100,具備安全邊際"
    confidence = 9
    
    print("\n=== [STEP 3] Consolidated Push Notification (Batch Test) ===")
    batch_payload = [
        {
            "entity": "台積電 (2330.TW)",
            "verdict": "合理價區間 1000-1100,具備安全邊際",
            "confidence": 9
        },
        {
            "entity": "聯發科 (2454.TW)",
            "verdict": "目前估值合理,關注庫存去化",
            "confidence": 7
        }
    ]
    
    consolidated_result = call_tool("delivery.push_report", report_json=json.dumps(batch_payload))
    print(f"CONSOLIDATED PUSH RESULT: {json.dumps(consolidated_result, indent=2, ensure_ascii=False)}")

except Exception as e:
    print(f"PIPELINE FAILURE: {str(e)}")
    import traceback
    traceback.print_exc()
