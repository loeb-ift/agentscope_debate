"""
Verify TEJ Migration by comparing Old Adapters vs New DB Tools.
"""
import sys
import os
import inspect
import json
sys.path.insert(0, os.getcwd())

from api.database import SessionLocal
from api import models
from adapters import tej_adapter

def get_old_adapters():
    """Extract tool info from adapters/tej_adapter.py classes."""
    adapters = {}
    for name, obj in inspect.getmembers(tej_adapter):
        if inspect.isclass(obj) and issubclass(obj, tej_adapter.TEJBaseAdapter) and obj != tej_adapter.TEJBaseAdapter:
            # Create instance to get properties if needed, but here we inspect class attrs
            tool_name = getattr(obj, "name", None)
            if tool_name:
                # Extract table from source code or invoke method
                # This is a bit hacky but effective for verification: read the invoke method source
                try:
                    src = inspect.getsource(obj.invoke)
                    if '"TRAIL"' in src and '"' in src:
                        # Extract table name like "AIND" from '_execute_query("TRAIL", "AIND", ...)'
                        parts = src.split('"')
                        table_idx = -1
                        for i, p in enumerate(parts):
                            if p == "TRAIL":
                                table_idx = i + 2 # Skip " and , and " to get table name
                                break
                        table_name = parts[table_idx] if table_idx > 0 and table_idx < len(parts) else "UNKNOWN"
                    else:
                        table_name = "UNKNOWN"
                except:
                    table_name = "UNKNOWN"

                adapters[tool_name] = {
                    "class": name,
                    "description": getattr(obj, "description", "").strip(),
                    "table": table_name,
                    "schema": getattr(obj, "schema", {})
                }
    return adapters

def verify_comparison():
    print("🔍 TEJ Migration Verification: Old vs New Comparison")
    print("=" * 100)
    
    # 1. Get Old Adapters
    old_tools = get_old_adapters()
    print(f"Found {len(old_tools)} legacy Python adapters.")
    
    # 2. Get New DB Tools
    db = SessionLocal()
    new_tools_list = db.query(models.Tool).filter(models.Tool.provider == "tej").all()
    new_tools = {t.name: t for t in new_tools_list}
    print(f"Found {len(new_tools)} migrated Database tools.")
    print("-" * 100)

    # 3. Compare Side-by-Side
    all_names = sorted(list(set(old_tools.keys()) | set(new_tools.keys())))
    
    match_count = 0
    mismatch_count = 0
    
    for name in all_names:
        old = old_tools.get(name)
        new = new_tools.get(name)
        
        print(f"Tool: {name}")
        
        if not old:
            print(f"  ❌ Missing in Legacy Adapters (New only?)")
            mismatch_count += 1
            continue
        if not new:
            print(f"  ❌ Missing in Database (Migration failed?)")
            mismatch_count += 1
            continue
            
        # Compare Table/Endpoint
        new_path = list(new.openapi_spec["paths"].keys())[0] if new.openapi_spec and "paths" in new.openapi_spec else "UNKNOWN"
        old_table = old['table']
        new_table_in_path = old_table in new_path
        
        status_table = "✅" if new_table_in_path else "❌"
        print(f"  {status_table} Table/Path: Old='{old_table}' vs New='{new_path}'")
        
        # Compare Description (just check if present and similar length, likely won't match exact formatting)
        old_desc_len = len(old['description'])
        new_desc_len = len(new.description or "")
        status_desc = "✅" if abs(old_desc_len - new_desc_len) < 100 else "⚠️" # Allow some difference due to formatting
        print(f"  {status_desc} Desc Length: Old={old_desc_len} chars vs New={new_desc_len} chars")

        # Compare Parameters
        # Check if 'coid' (or 'code') is in new parameters
        new_params = new.openapi_spec["paths"][new_path]["get"].get("parameters", [])
        param_names = [p["name"] for p in new_params]
        
        required_param = "code" if name == "tej.ifrs_account_descriptions" else "coid"
        status_param = "✅" if required_param in param_names else "❌"
        print(f"  {status_param} Key Param '{required_param}': {'Found' if status_param == '✅' else 'Missing'}")

        # Check pagination
        has_limit = "opts.limit" in param_names
        status_page = "✅" if has_limit else "❌"
        print(f"  {status_page} Pagination: {'Found' if has_limit else 'Missing'}")

        if status_table == "✅" and status_param == "✅" and status_page == "✅":
            match_count += 1
        else:
            mismatch_count += 1
            
        print("-" * 50)

    print(f"\n📊 Summary:")
    print(f"  Total Tools Checked: {len(all_names)}")
    print(f"  Fully Matched: {match_count}")
    print(f"  Issues Found: {mismatch_count}")
    
    db.close()

if __name__ == "__main__":
    verify_comparison()