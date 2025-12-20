from fastapi.testclient import TestClient
from api.main import app

client = TestClient(app)


def test_cache_hit_and_invalidation():
    # init global
    r = client.post("/api/v1/toolsets/initialize-global")
    assert r.status_code in (200, 201)

    # create agent
    payload = {
        "name": "cache-agent",
        "role": "analyst",
        "system_prompt": "You are an analyst.",
        "config_json": {}
    }
    r = client.post("/api/v1/agents", json=payload)
    assert r.status_code == 201
    agent = r.json()

    # first fetch (populate cache)
    r1 = client.get(f"/api/v1/agents/{agent['id']}/tools/effective")
    assert r1.status_code == 200
    l1 = r1.json()

    # second fetch (should hit cache and be identical)
    r2 = client.get(f"/api/v1/agents/{agent['id']}/tools/effective")
    assert r2.status_code == 200
    assert r2.json() == l1

    # deny a tool to force invalidation
    deny_payload = {"tool_name": "duckduckgo.search", "reason": "test invalidate"}
    r = client.post(f"/api/v1/agents/{agent['id']}/tools/deny", json=deny_payload)
    assert r.status_code == 201

    # fetch again (should reflect removal, not equal to cached list)
    r3 = client.get(f"/api/v1/agents/{agent['id']}/tools/effective")
    assert r3.status_code == 200
    assert r3.json() != l1
