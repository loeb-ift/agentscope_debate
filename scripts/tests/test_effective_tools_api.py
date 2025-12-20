import pytest
from fastapi.testclient import TestClient

from api.main import app

client = TestClient(app)


def test_effective_tools_endpoint_smoke(monkeypatch):
    # Ensure global toolset exists via init endpoint
    r = client.post("/api/v1/toolsets/initialize-global")
    assert r.status_code in (200, 201)

    # Create a simple agent
    payload = {
        "name": "tester",
        "role": "analyst",
        "system_prompt": "You are a tester.",
        "config_json": {}
    }
    r = client.post("/api/v1/agents", json=payload)
    assert r.status_code == 201, r.text
    agent = r.json()

    # Call effective tools
    r = client.get(f"/api/v1/agents/{agent['id']}/tools/effective")
    assert r.status_code == 200, r.text
    tools = r.json()
    assert isinstance(tools, list)
    # should at least contain global tools if registry not empty
    # no strict assertion on length to keep test stable across environments
