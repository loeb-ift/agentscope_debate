from fastapi.testclient import TestClient
import os
from api.main import app

client = TestClient(app)


def test_flow_without_tej_tools(monkeypatch):
    # Ensure TEJ is disabled
    monkeypatch.setenv("ENABLE_TEJ_TOOLS", "false")
    # Restart config load is not trivial; assume registry honors flag at runtime for route calls.

    # 1) Available tools should not list tej.* in recommendations via API (smoke)
    r = client.post("/api/v1/toolsets/initialize-global")
    assert r.status_code in (200, 201)

    # 2) Call effective tools for a new agent (ensure not exploding)
    payload = {"name": "no-tej-agent", "role": "analyst", "system_prompt": "-", "config_json": {}}
    r = client.post("/api/v1/agents", json=payload)
    assert r.status_code == 201
    agent = r.json()

    r = client.get(f"/api/v1/agents/{agent['id']}/tools/effective")
    assert r.status_code == 200
    tools = r.json()
    assert all(not t.get('name','').startswith('tej.') for t in tools)

    # 3) Verify manual selection: if we ask for verified price, endpoint is callable
    # Note: we do not directly call worker/debate_cycle here; this is a smoke-level check
    # Additional deeper tests would require invoking internal functions.
