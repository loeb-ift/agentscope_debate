
import asyncio
import os
import sys

# 確保可以導入 adapters 模組
sys.path.append(os.getcwd())

from adapters.alpha_vantage_mcp_adapter import AlphaVantageMCPAdapter

async def verify_alpha_vantage():
    print("=== Verifying Alpha Vantage MCP Integration ===")
    
    # Check Environment
    api_key = os.getenv("ALPHA_VANTAGE_API_KEY")
    if not api_key:
        print("❌ Error: ALPHA_VANTAGE_API_KEY not found in env.")
        return

    adapter = AlphaVantageMCPAdapter()
    
    try:
        # 1. Connect (Stateless - No OP)
        # await adapter.connect()
        
        # 2. List Tools
        print("\n--- Listing Tools ---")
        tools = await adapter.list_tools()
        for tool in tools:
            print(f"- {tool['name']}: {tool['description'][:50]}...")
            
        if not tools:
            print("❌ Warning: No tools found!")
            return

        # 3. Test Simple Tools First
        print("\n--- Testing PING ---")
        try:
            ping_res = await adapter.invoke_tool("PING", {})
            print(f"PING Result: {ping_res}")
        except Exception as e:
            print(f"PING Failed: {e}")

        # 4. Inspect & Invoke TIME_SERIES_DAILY
        # Find the tool and print schema
        candidate = next((t for t in tools if t['name'] == "TIME_SERIES_DAILY"), None)
        
        if candidate:
            print(f"\n--- Tool Schema: {candidate['name']} ---")
            import json
            print(json.dumps(candidate.get("inputSchema"), indent=2))
            
            print(f"\n--- Invoking Tool: SYMBOL_SEARCH ---")
            args = {"keywords": "2330"} 
            
            try:
                result = await adapter.invoke_tool("SYMBOL_SEARCH", args)
                print("Result Preview (First 500 chars):")
                print(result[:500])
            except Exception as e:
                print(f"Invocation Failed: {e}")
        else:
            print("\n⚠️ TIME_SERIES_DAILY not found.")

    except Exception as e:
        print(f"\n❌ Error during verification: {e}")
        import traceback
        traceback.print_exc()
    finally:
        await adapter.close()

if __name__ == "__main__":
    asyncio.run(verify_alpha_vantage())
