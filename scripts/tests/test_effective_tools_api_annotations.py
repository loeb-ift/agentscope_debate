import pytest
from fastapi.testclient import TestClient

from api.main import app

client = TestClient(app)


def test_effective_tools_endpoint_annotations(monkeypatch):
    # Ensure global toolset exists via init endpoint
    r = client.post("/api/v1/toolsets/initialize-global")
    assert r.status_code in (200, 201)

    # Create a simple agent
    payload = {
        "name": "tester-annot",
        "role": "analyst",
        "system_prompt": "You are a tester with annotations.",
        "config_json": {}
    }
    r = client.post("/api/v1/agents", json=payload)
    assert r.status_code == 201, r.text
    agent = r.json()

    # By default include_sources=True
    r = client.get(f"/api/v1/agents/{agent['id']}/tools/effective")
    assert r.status_code == 200
    tools = r.json()
    assert isinstance(tools, list)
    if tools:
        assert 'source' in tools[0]  # annotated by default

    # When include_sources=False, strip annotations
    r = client.get(f"/api/v1/agents/{agent['id']}/tools/effective", params={"include_sources": False})
    assert r.status_code == 200
    tools = r.json()
    assert isinstance(tools, list)
    if tools:
        assert 'source' not in tools[0]
        assert 'toolset_name' not in tools[0]
