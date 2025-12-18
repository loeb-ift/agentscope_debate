
import requests
import json
import os

# 模擬前端請求
BASE_URL = "http://localhost:8000/api/v1"

def test_endpoints():
    endpoints = [
        "/agents",
        "/teams",
        "/replays"
    ]
    
    print(f"Testing API at {BASE_URL}...\n")
    
    for ep in endpoints:
        url = f"{BASE_URL}{ep}"
        try:
            print(f"👉 GET {ep}")
            resp = requests.get(url, timeout=5)
            print(f"   Status: {resp.status_code}")
            
            if resp.status_code == 200:
                data = resp.json()
                # 簡單分析回傳結構
                if isinstance(data, list):
                    print(f"   Type: List, Count: {len(data)}")
                    if len(data) > 0:
                        print(f"   Sample: {str(data[0])[:100]}...")
                elif isinstance(data, dict):
                    print(f"   Type: Dict, Keys: {list(data.keys())}")
                    if "items" in data:
                         print(f"   Items Count: {len(data['items'])}")
                         if len(data['items']) > 0:
                             print(f"   Sample Item: {str(data['items'][0])[:100]}...")
                else:
                    print(f"   Type: {type(data)}")
            else:
                print(f"   Error: {resp.text[:200]}")
        except Exception as e:
            print(f"   ❌ Connection Failed: {e}")
        print("-" * 30)

if __name__ == "__main__":
    test_endpoints()
