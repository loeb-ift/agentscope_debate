import os
import requests
from dotenv import load_dotenv

# Load env
load_dotenv()

TEJ_API_KEY = os.getenv("TEJ_API_KEY")
if not TEJ_API_KEY:
    print("❌ TEJ_API_KEY not found in .env")
    exit(1)

def test_tej(coid):
    print(f"\n--- Testing TEJ with coid='{coid}' ---")
    url = "https://api.tej.com.tw/api/datatables/TRAIL/TAPRCD.json"
    params = {
        "api_key": TEJ_API_KEY,
        "coid": coid,
        "opts.limit": 5
    }
    try:
        resp = requests.get(url, params=params)
        data = resp.json()
        rows = data.get("data", [])
        print(f"Result Count: {len(rows)}")
        if len(rows) > 0:
            print(f"Sample: {rows[0]}")
        else:
            print("Empty result.")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    # Test with .TW
    test_tej("2480.TW")
    
    # Test without .TW
    test_tej("2480")