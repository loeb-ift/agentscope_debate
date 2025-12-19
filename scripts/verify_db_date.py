import asyncio
import os
import sys
from datetime import datetime, timedelta

# Add project root to path
sys.path.append(os.getcwd())

from worker.tool_invoker import call_tool

async def main():
    print("=== TEJ Database Date Verification ===")
    
    # 1. Try querying recent data (2025)
    today = datetime.now()
    start_2025 = "2025-01-01"
    end_2025 = today.strftime("%Y-%m-%d")
    
    print(f"Querying 2025 data ({start_2025} ~ {end_2025})...")
    params_2025 = {
        "coid": "2330.TW",
        "mdate.gte": start_2025,
        "mdate.lte": end_2025,
        "opts.limit": 5,
        "sort": "mdate.desc"
    }
    
    try:
        res_2025 = call_tool("tej.stock_price", params_2025)
        if isinstance(res_2025, dict) and res_2025.get("data"):
            print(f"✅ Found 2025 data! Latest: {res_2025['data'][0]['mdate']}")
        else:
            print("❌ No data found for 2025.")
            if isinstance(res_2025, dict):
                 print(f"Response: {res_2025}")
    except Exception as e:
        print(f"Error querying 2025: {e}")

    # 2. Try querying 2024 data (Late 2024)
    print("\nQuerying Late 2024 data (2024-10-01 ~ 2024-12-31)...")
    params_2024 = {
        "coid": "2330.TW",
        "mdate.gte": "2024-10-01",
        "mdate.lte": "2024-12-31",
        "opts.limit": 5,
        "sort": "mdate.desc"
    }
    
    try:
        res_2024 = call_tool("tej.stock_price", params_2024)
        if isinstance(res_2024, dict) and res_2024.get("data"):
            print(f"✅ Found 2024 data! Latest: {res_2024['data'][0]['mdate']}")
        else:
            print("❌ No data found for Late 2024.")
    except Exception as e:
        print(f"Error querying 2024: {e}")

if __name__ == "__main__":
    asyncio.run(main())