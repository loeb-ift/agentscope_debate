import requests
import json
import os

API_URL = os.getenv("API_URL", "http://localhost:8000/api/v1")

def check_endpoint(name, url):
    print(f"Checking {name} ({url})...")
    try:
        resp = requests.get(url, timeout=5)
        resp.raise_for_status()
        data = resp.json()
        
        print(f"  ✅ Status {resp.status_code}")
        if isinstance(data, list):
            print(f"  ✅ Type: List (len={len(data)})")
            if len(data) > 0:
                print(f"  Sample type: {type(data[0])}")
        elif isinstance(data, dict):
            print(f"  ✅ Type: Dict (keys={list(data.keys())[:5]})")
        else:
            print(f"  ⚠️ Unknown type: {type(data)}")
            
    except Exception as e:
        print(f"  ❌ Failed: {e}")
        try:
            print(f"  Response text: {resp.text[:200]}")
        except:
            pass

if __name__ == "__main__":
    endpoints = [
        ("Sectors", f"{API_URL}/internal/sectors"),
        ("Industry Tree", f"{API_URL}/internal/industry-tree"),
        ("Companies", f"{API_URL}/internal/companies?limit=1"),
        ("Agents", f"{API_URL}/agents"),
    ]
    
    for name, url in endpoints:
        check_endpoint(name, url)
