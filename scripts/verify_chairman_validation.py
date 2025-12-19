import asyncio
import os
from unittest.mock import MagicMock, patch
from worker.chairman import Chairman

# Sync Mock Tool
def mock_call_tool(name, params):
    print(f"DEBUG: Mock Tool Call: {name} with {params}")
    
    if name == "twse.stock_day":
        if params.get("symbol") == "2330":
            # Success
            return {"data": [["2024/12/01", "10,000", "10,000,000", "1000.0", "1005.0", "995.0", "1002.0", "+2.0", "5000"]]}
        else:
            # Code exists but maybe not listed on main board or data error
            # Or force fail for testing fallback
            return {"data": []}

    if name == "tej.company_info":
        if params.get("coid") == "2330":
            # Just in case fallback happens (shouldn't for 2330 if TWSE works)
            return {"results": [{"ename": "TSMC (TEJ)", "cname": "台灣積體電路製造"}]}
        elif params.get("coid") == "6547": # Example: Only in TEJ (Emerging board? or just test case)
            return {"results": [{"ename": "High-End Tech (TEJ)", "cname": "高端疫苗"}]}
        elif params.get("coid") == "0000": # Wrong code
            return {"results": []}
            
    if name == "searxng.search":
        q = params.get("q", "")
        if "聯發科" in q:
            return "聯發科 (2454) MediaTek Inc."
        if "中華電信" in q:
            return "中華電信 (2412) Chunghwa Telecom"
        if "高端疫苗" in q:
            return "高端疫苗 (6547)"
            
    return {"results": []}

# Mock LLM Response for Extraction
async def mock_call_llm_async(prompt, system_prompt=None, **kwargs):
    # print(f"DEBUG: Mock LLM Call for prompt: {prompt[:50]}...")
    if "2454" in prompt:
        return "2454"
    if "中華電信" in prompt: 
        return "2412"
    if "6547" in prompt:
        return "6547"
    return "Unknown"

async def test_validation():
    print("=== Testing Chairman Decree Validation (with TWSE Priority) ===")
    
    with patch("worker.tool_invoker.call_tool", side_effect=mock_call_tool):
        # Patch LLM separately as it is imported as call_llm_async
        with patch("worker.chairman.call_llm_async", side_effect=mock_call_llm_async):
            
            chairman = Chairman(name="TestChairman")
            chairman._publish_log = MagicMock()
            
            # Case 1: TWSE Success (2330 -> TSMC)
            print("\n[Case 1] Verify TWSE Priority (2330)")
            decree1 = {"subject": "台積電", "code": "2330", "timeframe": "2024 Q4"}
            res1 = await chairman._validate_and_correction_decree(decree1, debate_id="test_case_1")
            print(f"Result 1: {res1}")
            # Note: My mock TWSE returns success, but doesn't return Company Name. 
            # The code logic only updates subject if it gets a name (from TEJ or TWSE logic?).
            # Let's check logic:
            #   if data_twse ... : self._publish_log(..., f"✅ (TWSE) 驗證成功...")
            #   verified = True
            # It DOES NOT update subject name from TWSE result because stock_day usually only has price.
            # So name remains "台積電". Verified should be True.
            assert res1["is_verified"] == True
            assert res1["code"] == "2330"
            
            # Case 2: TWSE Fail -> TEJ Fallback (6547)
            # 6547 in my mock fails TWSE, passes TEJ
            print("\n[Case 2] Verify TEJ Fallback (6547)")
            decree2 = {"subject": "高端疫苗", "code": "6547", "timeframe": "2024"}
            res2 = await chairman._validate_and_correction_decree(decree2, debate_id="test_case_2")
            print(f"Result 2: {res2}")
            assert res2["is_verified"] == True
            assert res2["code"] == "6547"
            assert "(TEJ)" in res2["subject"] # Because TEJ update subject name
            
            # Case 3: Missing Code (Lookup)
            print("\n[Case 3] Verify Missing Code (Lookup '聯發科')")
            decree3 = {"subject": "聯發科", "code": "Unknown", "timeframe": "2024"}
            res3 = await chairman._validate_and_correction_decree(decree3, debate_id="test_case_3")
            print(f"Result 3: {res3}")
            assert res3["code"] == "2454"

    print("\n=== Test Completed ===")

if __name__ == "__main__":
    try:
        # Patching again here to ensure it uses the sync function
        with patch("worker.tool_invoker.call_tool", side_effect=mock_call_tool):
            asyncio.run(test_validation())
    except Exception as e:
        print(f"Test failed: {e}")
        import traceback
        traceback.print_exc()
