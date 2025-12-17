
import asyncio
import os
import json
from api.tool_registry import tool_registry
from worker.llm_utils import call_llm_async

async def verify_agent_usage():
    print("=== 1. 初始化工具註冊表 (Loading Registry) ===")
    # Force load of lazy tools via list() if needed, but registry init should have done it
    # We specifically check for 'av' tools
    
    # Debug: Check if key exists
    api_key = os.getenv("ALPHA_VANTAGE_API_KEY")
    if not api_key:
        print("❌ ALPHA_VANTAGE_API_KEY not found in env.")
        return

    # Check if AV tools are registered (registry auto-registers on import if key exists)
    # But we need to ensure registry import happened. It is imported above.
    
    tools_map = tool_registry.list_tools()
    av_tools = [t for id, t in tools_map.items() if id.startswith("av.")]
    
    if not av_tools:
        print("⚠️ No AV tools found in registry. Attempting manual registration for test...")
        from adapters.alpha_vantage_mcp_adapter import AlphaVantageMCPAdapter
        av_adapter = AlphaVantageMCPAdapter()
        tool_registry.register_mcp_adapter(av_adapter, prefix="av")
        tools_map = tool_registry.list_tools()
        av_tools = [t for id, t in tools_map.items() if id.startswith("av.")]
        
    print(f"✅ Found {len(av_tools)} Alpha Vantage tools: {[t['instance'].name for t in av_tools]}")
    
    # Construct Tools List for LLM
    # LLM expects: [{"type": "function", "function": {"name": ..., "description": ..., "parameters": ...}}]
    llm_tools = []
    for tool_data in av_tools:
        instance = tool_data["instance"]
        schema = tool_data["schema"]
        # Basic conversion (Ollama format)
        llm_tools.append({
            "type": "function",
            "function": {
                "name": instance.name,
                "description": instance.describe(),
                "parameters": schema
            }
        })
    
    print(f"DEBUG: Helper function extracted {len(llm_tools)} tools for LLM.")

    # 2. Call LLM
    prompt = "Check the daily stock price for IBM (International Business Machines)."
    print(f"\n=== 2. Simulating Agent Query: '{prompt}' ===")
    
    response = await call_llm_async(
        prompt=prompt,
        system_prompt="You are a helpful assistant with access to financial tools. Use them to answer user questions.",
        tools=llm_tools
    )
    
    print(f"\n=== 3. LLM Response ===")
    print(response)
    
    # 3. Validation
    # We expect a JSON string like {"tool": "av.TIME_SERIES_DAILY", ...} 
    # OR if using Ollama raw tool calls, call_llm_async returns parsed JSON string.
    
    try:
        if "av." in response:
            print(f"\n✅ Verification SUCCESS: Agent selected an Alpha Vantage tool: {response}")
        elif "TIME_SERIES" in response or "SEARCH" in response:
            print(f"\n✅ Verification SUCCESS: Agent selected a relevant tool (Name match): {response}")
        else:
             print("\n❌ Verification FAILED: Agent did not call expected tool.")
    except:
        pass

if __name__ == "__main__":
    # Load env
    # Assume .env is loaded or running in env where it is set
    asyncio.run(verify_agent_usage())
