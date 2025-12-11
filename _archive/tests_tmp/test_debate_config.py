from fastapi.testclient import TestClient
from api.main import app
import uuid

client = TestClient(app)

def test_debate_configuration_flow():
    # 1. Create Agents (for teams)
    agent1 = client.post("/api/v1/agents", json={
        "name": "Pro Agent 1", "role": "debater", "system_prompt": "Prompt 1"
    }).json()
    
    agent2 = client.post("/api/v1/agents", json={
        "name": "Con Agent 1", "role": "debater", "system_prompt": "Prompt 2"
    }).json()
    
    chairman = client.post("/api/v1/agents", json={
        "name": "Chairman", "role": "chairman", "system_prompt": "Chairman Prompt"
    }).json()

    # 2. Create Debate Configuration
    config_payload = {
        "topic": "Is AI good?",
        "chairman_id": chairman["id"],
        "rounds": 2,
        "enable_cross_examination": False,
        "teams": [
            {
                "name": "Team Pro",
                "side": "pro",
                "agent_ids": [agent1["id"]]
            },
            {
                "name": "Team Con",
                "side": "con",
                "agent_ids": [agent2["id"]]
            }
        ]
    }
    
    response = client.post("/api/v1/debates/config", json=config_payload)
    assert response.status_code == 201
    config_data = response.json()
    print(f"Created Config ID: {config_data['id']}")
    
    # Verify Config Data
    assert config_data["topic"] == "Is AI good?"
    assert len(config_data["teams"]) == 2
    
    # 3. Launch Debate (Mock launch)
    # We are not checking Celery execution here, just the API response
    launch_response = client.post(f"/api/v1/debates/launch?config_id={config_data['id']}")
    assert launch_response.status_code == 201
    launch_data = launch_response.json()
    assert launch_data["status"] == "Debate launched"
    assert "task_id" in launch_data
    
    print("✅ Debate Configuration and Launch API tests passed!")

if __name__ == "__main__":
    try:
        test_debate_configuration_flow()
    except AssertionError as e:
        print(f"❌ Tests failed: {e}")
    except Exception as e:
        print(f"❌ An error occurred: {e}")