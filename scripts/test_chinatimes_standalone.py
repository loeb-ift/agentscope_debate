import requests
import json
import sys

def test_chinatimes(code):
    url = f"https://wantrich.chinatimes.com/api/stock_check/{code}"
    print(f"Testing URL: {url}")
    try:
        response = requests.get(url, timeout=10)
        print(f"Status Code: {response.status_code}")
        if response.status_code == 200:
            data = response.json()
            print("Response Data Type:", type(data))
            
            if isinstance(data, list) and len(data) > 0:
                item = data[0]
                print("First Item Preview:")
                print(json.dumps(item, indent=2, ensure_ascii=False))
                
                # Check for keys
                sector = item.get("SectorName") or item.get("Industry") or item.get("industry") or item.get("sector")
                print(f"Sector/Industry (Guess): {sector}")
            else:
                print("Data is not a list or empty.")
        else:
            print(f"Error: {response.text}")
    except Exception as e:
        print(f"Exception: {e}")

if __name__ == "__main__":
    test_chinatimes("2480")
