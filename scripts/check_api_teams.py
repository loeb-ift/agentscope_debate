
import os
import requests

API_URL = "http://localhost:8000/api/v1/teams"

def check_teams_api():
    try:
        response = requests.get(API_URL)
        if response.status_code == 200:
            teams = response.json().get("items", [])
            print(f"✅ API /teams returned {len(teams)} teams.")
            for t in teams:
                print(f"   - {t['name']}")
        else:
            print(f"❌ API /teams failed with {response.status_code}: {response.text}")
    except Exception as e:
        print(f"❌ API connection failed: {e}")

if __name__ == "__main__":
    check_teams_api()
