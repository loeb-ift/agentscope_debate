import requests
import json
import os

def generate_openapi_json():
    try:
        response = requests.get("http://localhost:8000/openapi.json")
        if response.status_code == 200:
            with open("openapi.json", "w", encoding="utf-8") as f:
                json.dump(response.json(), f, indent=2, ensure_ascii=False)
            print("Successfully generated openapi.json")
        else:
            print(f"Failed to fetch openapi.json. Status code: {response.status_code}")
    except Exception as e:
        print(f"Error generating openapi.json: {e}")

if __name__ == "__main__":
    generate_openapi_json()
