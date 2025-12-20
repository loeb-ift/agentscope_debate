from fastapi.testclient import TestClient
import pytest

from api.main import app

client = TestClient(app)


def test_effective_tools_precedence_and_prompt(monkeypatch):
    # init global
    r = client.post("/api/v1/toolsets/initialize-global")
    assert r.status_code in (200, 201)

    # create agent with prompt allow/deny
    payload = {
        "name": "precedence-agent",
        "role": "analyst",
        "system_prompt": "You are an analyst.",
        "config_json": {
            "tools": {
                "allow": ["duckduckgo.search"],
                "deny": ["web.fetch"]
            }
        }
    }
    r = client.post("/api/v1/agents", json=payload)
    assert r.status_code == 201
    agent = r.json()

    # approve runtime for a denied-by-prompt tool -> deny should win
    req = {"tool_name": "web.fetch", "reason": "need http"}
    r = client.post(f"/api/v1/agents/{agent['id']}/runtime-tools/request", json=req)
    assert r.status_code == 201
    rid = r.json()["id"]
    r = client.post(f"/api/v1/agents/{agent['id']}/runtime-tools/{rid}/approve", json={"approved_by": "admin"})
    assert r.status_code == 200

    # effective: web.fetch should NOT appear; duckduckgo.search should appear with prompt precedence if annotated
    r = client.get(f"/api/v1/agents/{agent['id']}/tools/effective", params={"include_precedence": True})
    assert r.status_code == 200
    tools = r.json()
    names = {t.get('name') or t.get('tool_name') for t in tools}
    assert "web.fetch" not in names
    assert "duckduckgo.search" in names
    # find duckduckgo and check precedence=="prompt"
    ddg = next(t for t in tools if (t.get('name') or t.get('tool_name')) == 'duckduckgo.search')
    assert ddg.get('precedence') in ("prompt", "runtime", "agent_toolset", "global")
    # expected prompt if not overridden
