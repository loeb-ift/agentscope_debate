
import asyncio
import json
import sys
import os

# Add project root to path
sys.path.append(os.getcwd())

from worker.tool_invoker import call_tool
from api.tool_registry import tool_registry

async def verify_fred():
    print("--- Verifying FRED Tools ---")
    
    # 1. Search for Inflation
    print("\n[1] Testing fred.search_series (keywords: 'inflation')...")
    search_res = call_tool("fred.search_series", {"search_text": "inflation", "limit": 3})
    print(json.dumps(search_res, indent=2, ensure_ascii=False))
    
    # 2. Get Observations for CPI
    print("\n[2] Testing fred.get_series_observations (ID: 'CPIAUCSL')...")
    obs_res = call_tool("fred.get_series_observations", {"series_id": "CPIAUCSL", "limit": 5})
    print(json.dumps(obs_res, indent=2, ensure_ascii=False))
    
    # 3. Get Latest Release for Fed Funds Rate
    print("\n[3] Testing fred.get_latest_release (ID: 'FEDFUNDS')...")
    latest_res = call_tool("fred.get_latest_release", {"series_id": "FEDFUNDS"})
    print(json.dumps(latest_res, indent=2, ensure_ascii=False))

    print("\n--- Verification Complete ---")

if __name__ == "__main__":
    asyncio.run(verify_fred())
