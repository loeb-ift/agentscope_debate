import sys
import os
import asyncio
import json
sys.path.append(os.getcwd())

from worker.llm_utils import call_llm_async
from api.tool_registry import tool_registry

async def test_agent_tool_usage():
    print("Testing Agent Tool Usage Logic...")
    
    # Mock Tools Description (as seen by Agent)
    tools_desc = """
- tej.stock_price: 查詢台灣股票歷史價格資料。參數: coid (e.g. 2330), start_date (YYYY-MM-DD), end_date (YYYY-MM-DD)
- twse.stock_day: 查詢台灣證交所個股日成交資訊。參數: symbol (e.g. 2330), date (YYYYMMDD)
- yahoo.stock_price: 查詢 Yahoo Finance 股價。參數: symbol (e.g. 2330.TW), start_date (YYYY-MM-DD), end_date (YYYY-MM-DD)
- financial.get_verified_price: 獲取經多源驗證的股價。參數: symbol (e.g. 2330.TW), date (YYYY-MM-DD)
    """

    # 1. Test Pro Agent (Expected: Prefer TEJ)
    print("\n--- Test 1: Pro Agent (TEJ Preference) ---")
    system_prompt_pro = "你是專業分析師 (Pro)。請優先使用高精度數據源 (TEJ)。"
    user_prompt_pro = f"請查詢台積電 (2330) 在 2024年11月1日 的股價。\n可使用工具:\n{tools_desc}"
    
    # We mock the tools list for Ollama
    tools_schema = [
        {"type": "function", "function": {"name": "tej.stock_price", "parameters": {"type": "object", "properties": {"coid": {"type": "string"}, "start_date": {"type": "string"}, "end_date": {"type": "string"}}}}},
        {"type": "function", "function": {"name": "twse.stock_day", "parameters": {"type": "object", "properties": {"symbol": {"type": "string"}, "date": {"type": "string"}}}}},
        {"type": "function", "function": {"name": "financial.get_verified_price", "parameters": {"type": "object", "properties": {"symbol": {"type": "string"}, "date": {"type": "string"}}}}}
    ]
    
    res_pro = await call_llm_async(user_prompt_pro, system_prompt=system_prompt_pro, tools=tools_schema)
    print(f"Pro Agent Response: {res_pro}")

    # 2. Test Neutral Agent (Expected: Prefer Verified/TWSE)
    print("\n--- Test 2: Neutral Agent (Verification Preference) ---")
    system_prompt_neutral = "你是公正審計員 (Neutral)。請優先使用官方驗證數據源 (TWSE/Verified)。"
    user_prompt_neutral = f"請查證台積電 (2330) 2024年11月1日 的收盤價。\n可使用工具:\n{tools_desc}"
    
    res_neutral = await call_llm_async(user_prompt_neutral, system_prompt=system_prompt_neutral, tools=tools_schema)
    print(f"Neutral Agent Response: {res_neutral}")

    # 3. Test Fallback (Simulate Failure)
    print("\n--- Test 3: Fallback Logic (Simulated) ---")
    # This logic is inside DebateCycle loop usually.
    # Here we simulate an agent receiving an error.
    history = f"User: Check 2330 price.\nAgent: Call tej.stock_price...\nSystem: Error: TEJ API Key missing.\n"
    user_prompt_fallback = f"{history}請嘗試其他備援工具查詢。\n可使用工具:\n{tools_desc}"
    
    res_fallback = await call_llm_async(user_prompt_fallback, system_prompt="你是分析師。", tools=tools_schema)
    print(f"Fallback Response: {res_fallback}")

if __name__ == "__main__":
    asyncio.run(test_agent_tool_usage())