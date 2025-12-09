"""
Verify that migrated TEJ tools work correctly via ToolRegistry.
This script simulates the runtime environment:
1. Loads tool definitions from the Database.
2. Converts them into HTTPToolAdapters.
3. Registers them with ToolRegistry.
4. Invokes a sample tool (tej.stock_price) to ensure real API calls work.
"""
import sys
import os
import json
from dotenv import load_dotenv

sys.path.insert(0, os.getcwd())
load_dotenv()

from api.database import SessionLocal
from api import models
from api.tool_registry import ToolRegistry
from adapters.http_tool_adapter import HTTPToolAdapter

def test_new_tools():
    print("🚀 Starting Verification of Migrated TEJ Tools...")
    
    # 1. Initialize Registry
    registry = ToolRegistry()
    db = SessionLocal()
    
    try:
        # 2. Load Tools from DB
        print("📥 Loading tools from Database...")
        db_tools = db.query(models.Tool).filter(models.Tool.provider == "tej").all()
        print(f"Found {len(db_tools)} TEJ tools in DB.")
        
        for tool_model in db_tools:
            # Construct API Config from OpenAPI Spec
            spec = tool_model.openapi_spec
            path = list(spec["paths"].keys())[0]
            method = list(spec["paths"][path].keys())[0].upper()
            base_url = spec["servers"][0]["url"]
            full_url = f"{base_url}{path}"
            
            api_config = {
                "url": full_url,
                "method": method,
                "headers": {"User-Agent": "AgentScope/1.0"} # Good practice
            }
            
            # Create Adapter
            adapter = HTTPToolAdapter(
                name=tool_model.name,
                description=tool_model.description,
                api_config=api_config,
                schema=tool_model.json_schema,
                version=tool_model.version
            )
            
            # Inject Auth (Simulated here, in real app this is handled by registry/auth middleware or similar)
            # For this test, we need to inject the API Key if present in env
            # The HTTPToolAdapter implementation provided doesn't auto-handle auth_config yet, 
            # so we'll patch it for this test if needed or rely on 'params' injection.
            
            registry.register(adapter, version=tool_model.version, group=tool_model.group)
            
        print("✅ Tools registered successfully.")
        
        # 3. Test Invoke: tej.stock_price
        target_tool = "tej.stock_price"
        print(f"\n🧪 Testing invocation of: {target_tool}")
        
        # Get API Key
        api_key = os.getenv("TEJ_API_KEY")
        if not api_key:
            print("⚠️ TEJ_API_KEY not found in environment. Cannot perform real API call.")
            return

        params = {
            "coid": "2330", # TSMC
            "mdate.gte": "2024-01-01",
            "mdate.lte": "2024-01-05",
            "opts.limit": 10,  # TEJ API requires pagination params; defaulting to 10 here
            "api_key": api_key # Explicitly passing API key as HTTPToolAdapter is generic
        }
        
        print(f"Arguments: {json.dumps({k:v for k,v in params.items() if k!='api_key'}, indent=2)}")
        
        result = registry.invoke_tool(target_tool, params)
        
        if "error" in result:
            print(f"❌ Invocation Failed: {result['error']}")
        elif "result" in result: # HTTPAdapter fallback for non-json
             print(f"⚠️ Raw Result (Text): {result['result'][:200]}...")
        else:
            # Success: TEJ may return under datatable.data or data
            rows = None
            if isinstance(result.get("data"), list):
                rows = result.get("data")
            elif isinstance(result.get("datatable", {}).get("data"), list):
                rows = result["datatable"]["data"]
            else:
                rows = []
            print(f"✅ Invocation Successful!")
            print(f"Records retrieved: {len(rows)}")
            if rows:
                # print the first row defensively
                try:
                    print(f"Sample Row: {rows[0]}")
                except Exception:
                    print("Sample Row: <unprintable>")
            else:
                 print("⚠️ No data returned (but call was successful). If this persists, try adding opts.offset, verifying coid, or widening date range.")

    except Exception as e:
        print(f"❌ Error during verification: {e}")
        import traceback
        traceback.print_exc()
    finally:
        db.close()

if __name__ == "__main__":
    test_new_tools()