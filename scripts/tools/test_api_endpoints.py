"""
Manual API Smoke Test (development convenience tool)

Purpose:
- Quick manual verification of running API endpoints against a live server.
- Not part of automated pytest/CI. Use scripts/tests/* for automated coverage.

Usage:
- Ensure the server is running (e.g., uvicorn api.main:app --reload --port 8000).
- Optionally override BASE_URL via environment or by editing the constant below.

Notes:
- This script uses the requests library and hits actual network endpoints.
- It may create real entities (e.g., agents), so prefer a dev/staging environment.
- For CI-safe tests, use pytest-based tests in scripts/tests/.
"""
import os
import requests
import json
import uuid

BASE_URL = os.getenv("API_BASE_URL", "http://localhost:8000")  # override with env var if needed

def test_agent_api():
    print("=== Testing Agent API ===")
    
    # 1. Create Agent
    agent_data = {
        "name": f"Test Agent {uuid.uuid4().hex[:6]}",
        "role": "debater",
        "specialty": "Testing",
        "system_prompt": "You are a test agent.",
        "config_json": {"temperature": 0.7}
    }
    
    try:
        response = requests.post(f"{BASE_URL}/api/v1/agents", json=agent_data)
        if response.status_code == 201:
            print("✅ Create Agent: Success")
            created_agent = response.json()
            agent_id = created_agent['id']
            print(f"   Agent ID: {agent_id}")
        else:
            print(f"❌ Create Agent: Failed ({response.status_code}) - {response.text}")
            return None
    except Exception as e:
        print(f"❌ Create Agent: Connection Error - {e}")
        return None

    # 2. Get Agent
    try:
        response = requests.get(f"{BASE_URL}/api/v1/agents/{agent_id}")
        if response.status_code == 200:
            print("✅ Get Agent: Success")
        else:
            print(f"❌ Get Agent: Failed ({response.status_code})")
    except Exception as e:
        print(f"❌ Get Agent: Connection Error - {e}")

    # 3. List Agents
    try:
        response = requests.get(f"{BASE_URL}/api/v1/agents")
        if response.status_code == 200:
            print(f"✅ List Agents: Success (Count: {len(response.json()['items'])})")
        else:
            print(f"❌ List Agents: Failed ({response.status_code})")
    except Exception as e:
        print(f"❌ List Agents: Connection Error - {e}")
        
    return agent_id

def test_debate_config_api(agent_id):
    print("\n=== Testing Debate Config API ===")
    
    if not agent_id:
        print("⚠️ Skipping Debate Config test because Agent creation failed.")
        return

    # 1. Create Debate Config
    config_data = {
        "topic": "AI will replace programmers.",
        "chairman_id": None, # Optional
        "rounds": 3,
        "enable_cross_examination": True,
        "teams": [
            {
                "name": "Pro Team",
                "side": "pro",
                "agent_ids": [agent_id]
            },
            {
                "name": "Con Team",
                "side": "con",
                "agent_ids": [agent_id] # Reusing same agent for simplicity
            }
        ]
    }
    
    try:
        response = requests.post(f"{BASE_URL}/api/v1/debates/config", json=config_data)
        if response.status_code == 201:
            print("✅ Create Debate Config: Success")
            config = response.json()
            config_id = config['id']
            print(f"   Config ID: {config_id}")
            return config_id
        else:
            print(f"❌ Create Debate Config: Failed ({response.status_code}) - {response.text}")
            return None
    except Exception as e:
        print(f"❌ Create Debate Config: Connection Error - {e}")
        return None

if __name__ == "__main__":
    # Check if API is up
    try:
        requests.get(f"{BASE_URL}/health")
        print("API is accessible.")
    except:
        print(f"⚠️ API is not accessible at {BASE_URL}. Is the server running?")
        # exit() # Continue anyway just in case the check is flaky or URL is different
    
    agent_id = test_agent_api()
    if agent_id:
        test_debate_config_api(agent_id)