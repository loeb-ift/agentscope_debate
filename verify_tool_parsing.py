import asyncio
import json
from worker.llm_utils import call_llm_async

async def test_tool_calling():
    print("Testing Native Tool Calling with Ollama...")
    
    # 標準的 OpenAI 格式工具定義
    tools = [
        {
            "type": "function",
            "function": {
                "name": "get_stock_price",
                "description": "Get the current stock price for a given ticker symbol",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "ticker": {
                            "type": "string",
                            "description": "The stock ticker symbol, e.g. AAPL or 2330"
                        }
                    },
                    "required": ["ticker"]
                }
            }
        }
    ]
    
    prompt = "What is the stock price of TSMC (2330)?"
    system_prompt = "You are a helpful assistant. Use tools when necessary."
    
    print(f"Prompt: {prompt}")
    print(f"Tools provided: {json.dumps(tools, indent=2)}")
    
    try:
        # 使用新增加的 tools 參數
        response = await call_llm_async(
            prompt, 
            system_prompt=system_prompt,
            tools=tools
        )
        print(f"Response (Native Tool Call): {response}")
        
        # 驗證返回是否為我們期望的 JSON 格式 (由 llm_utils._process_tool_calls 處理過的)
        try:
            result = json.loads(response)
            if "tool" in result and "params" in result:
                print("✅ Verification PASSED: Response is in correct JSON format.")
            else:
                print("❌ Verification FAILED: Response is JSON but missing 'tool' or 'params'.")
        except json.JSONDecodeError:
            print("⚠️ Verification WARNING: Response is not JSON. Model might have chosen not to use a tool, or returned text.")

    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    asyncio.run(test_tool_calling())