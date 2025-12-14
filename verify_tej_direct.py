import requests
import os
import json
from datetime import datetime

# Direct Configuration (extracted from env/code)
API_KEY = "cgEN7MsWcMQQTgN1b5OnfLJWmjg9s2" 
BASE_URL = "https://api.tej.com.tw/api/datatables/TRAIL/TAPRCD.json"

def check_tej_data(year):
    print(f"\n--- Checking TEJ (TRAIL) for {year} ---")
    
    start_date = f"{year}-01-01"
    end_date = f"{year}-12-31"
    
    params = {
        "api_key": API_KEY,
        "coid": "2330", # TSMC
        "mdate.gte": start_date,
        "mdate.lte": end_date,
        "opts.limit": 5
        # "sort": "mdate.desc" # TEJ might not support this directly or param name is wrong
    }
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }

    try:
        print(f"Requesting: {BASE_URL} with range {start_date} to {end_date}")
        response = requests.get(BASE_URL, params=params, headers=headers, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            rows = data.get("datatable", {}).get("data")
            if not rows:
                 # Check for direct data list format
                 rows = data.get("data")
            
            if rows:
                print(f"✅ Found {len(rows)} records for {year}!")
                print(f"Latest record: {rows[0]}")
            else:
                print(f"❌ No records found for {year}.")
                print(f"Response meta: {data.get('meta')}")
        else:
            print(f"❌ API Error: {response.status_code}")
            print(response.text)
            
    except Exception as e:
        print(f"❌ Exception: {e}")

if __name__ == "__main__":
    check_tej_data(2025)
    check_tej_data(2024)