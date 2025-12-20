import pytest

def test_runtime_and_deny_flows(test_client):
    client = test_client
    # init global
    r = client.post("/api/v1/toolsets/initialize-global")
    assert r.status_code in (200, 201)

    # create agent
    agent_payload = {
        "name": "m2-agent",
        "role": "analyst",
        "system_prompt": "You are an analyst.",
        "config_json": {}
    }
    r = client.post("/api/v1/agents", json=agent_payload)
    assert r.status_code == 201
    agent = r.json()

    # request runtime tool
    req_payload = {"tool_name": "duckduckgo.search", "reason": "need web search"}
    r = client.post(f"/api/v1/agents/{agent['id']}/runtime-tools/request", json=req_payload)
    assert r.status_code == 201
    request_obj = r.json()

    # approve runtime tool
    approve_payload = {"approved_by": "admin"}
    r = client.post(f"/api/v1/agents/{agent['id']}/runtime-tools/{request_obj['id']}/approve", json=approve_payload)
    assert r.status_code == 200

    # effective should include runtime tool now
    r = client.get(f"/api/v1/agents/{agent['id']}/tools/effective")
    assert r.status_code == 200
    names = {t.get('name') or t.get('tool_name') for t in r.json()}
    assert "duckduckgo.search" in names

    # deny a tool (if exists in registry); we'll deny the same runtime tool
    deny_payload = {"tool_name": "duckduckgo.search", "reason": "restricted for this agent"}
    r = client.post(f"/api/v1/agents/{agent['id']}/tools/deny", json=deny_payload)
    assert r.status_code == 201

    # effective should not contain denied tool
    r = client.get(f"/api/v1/agents/{agent['id']}/tools/effective")
    assert r.status_code == 200
    names = {t.get('name') or t.get('tool_name') for t in r.json()}
    assert "duckduckgo.search" not in names
