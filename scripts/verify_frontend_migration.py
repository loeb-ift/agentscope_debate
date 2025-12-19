import requests
import json
import sys

API_BASE = "http://localhost:8000/api/v1/internal"

def test_endpoint(name, url, params=None):
    print(f"Testing {name} ({url})...")
    try:
        response = requests.get(url, params=params)
        if response.status_code == 200:
            print(f"✅ {name}: Success")
            try:
                data = response.json()
                if isinstance(data, list):
                    print(f"   Response type: List, Length: {len(data)}")
                    if len(data) > 0:
                        print(f"   First item: {str(data[0])[:100]}...")
                elif isinstance(data, dict):
                    print(f"   Response type: Dict, Keys: {list(data.keys())[:5]}")
                else:
                    print(f"   Response: {str(data)[:100]}...")
            except json.JSONDecodeError:
                print("   Response is not JSON")
        else:
            print(f"❌ {name}: Failed (Status {response.status_code})")
            print(f"   Response: {response.text[:200]}")
    except Exception as e:
        print(f"❌ {name}: Error ({str(e)})")

def main():
    print("=== Verifying Frontend Migration Backend Support ===\n")
    
    # 1. Update Status
    test_endpoint("Last Update Check", f"{API_BASE}/companies/last-update")
    
    # 2. Industry Tree (For Map)
    test_endpoint("Industry Tree", f"{API_BASE}/industry-tree")
    
    # 3. Sector List (For Dropdown)
    test_endpoint("Sector List", f"{API_BASE}/sectors")
    
    # 4. Company List (Full)
    test_endpoint("Company List (All)", f"{API_BASE}/companies", params={"limit": 5})
    
    # 5. Company List (Filtered)
    # Get a sector first to test filter
    try:
        r = requests.get(f"{API_BASE}/sectors")
        if r.status_code == 200 and r.json():
            sector = r.json()[0]
            print(f"\nTesting filter with sector: {sector}")
            test_endpoint(f"Company List (Sector: {sector})", f"{API_BASE}/companies", params={"sector": sector, "limit": 5})
        else:
            print("\n⚠️ Skipping filter test (No sectors found)")
    except:
        print("\n⚠️ Skipping filter test (Error fetching sectors)")

if __name__ == "__main__":
    main()
