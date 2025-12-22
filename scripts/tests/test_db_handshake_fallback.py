import pytest
from api.config import Config
from unittest.mock import patch, MagicMock
import asyncio
import sys
import types


def _ensure_agentscope_stub():
    if "agentscope.agent" not in sys.modules:
        mod = types.ModuleType("agentscope.agent")
        class AgentBase:
            pass
        mod.AgentBase = AgentBase
        sys.modules["agentscope.agent"] = mod


if "agentscope.agent" not in sys.modules:
    mod = types.ModuleType("agentscope.agent")
    class AgentBase:
        pass
    mod.AgentBase = AgentBase
    sys.modules["agentscope.agent"] = mod


if "pandas_ta_classic" not in sys.modules:
    sys.modules["pandas_ta_classic"] = types.ModuleType("pandas_ta_classic")


if "pandas_datareader" not in sys.modules:
    pandas_datareader_pkg = types.ModuleType("pandas_datareader")
    pandas_datareader_pkg.__path__ = []
    sys.modules["pandas_datareader"] = pandas_datareader_pkg

if "pandas_datareader.data" not in sys.modules:
    sys.modules["pandas_datareader.data"] = types.ModuleType("pandas_datareader.data")


if "tenacity" not in sys.modules:
    tenacity_mod = types.ModuleType("tenacity")

    def retry(*dargs, **dkwargs):
        def decorator(fn):
            return fn
        return decorator

    def stop_after_attempt(*args, **kwargs):
        return None

    def wait_fixed(*args, **kwargs):
        return None

    def wait_exponential(*args, **kwargs):
        return None

    class RetryError(Exception):
        pass

    def retry_if_exception_type(*args, **kwargs):
        return None

    tenacity_mod.retry = retry
    tenacity_mod.stop_after_attempt = stop_after_attempt
    tenacity_mod.wait_fixed = wait_fixed
    tenacity_mod.wait_exponential = wait_exponential
    tenacity_mod.RetryError = RetryError
    tenacity_mod.retry_if_exception_type = retry_if_exception_type
    sys.modules["tenacity"] = tenacity_mod


if "tiktoken" not in sys.modules:
    sys.modules["tiktoken"] = types.ModuleType("tiktoken")

try:
    from api.main import app
    from fastapi.testclient import TestClient

    client = TestClient(app)
except Exception:
    app = None
    client = None


def test_db_handshake_fallback_path(monkeypatch):
    if client is None:
        pytest.skip("API app not available in test environment")

    monkeypatch.setenv("ENABLE_TEJ_TOOLS", "false")

    r = client.post("/api/v1/toolsets/initialize-global")
    assert r.status_code in (200, 201)

    payload = {"name": "probe-agent", "role": "analyst", "system_prompt": "-", "config_json": {}}
    r = client.post("/api/v1/agents", json=payload)
    assert r.status_code == 201

    r = client.get(f"/api/v1/agents/{r.json()['id']}/tools/effective")
    assert r.status_code == 200


def test_db_handshake_tej_empty_data_triggers_fallback(monkeypatch):
    Config.ENABLE_TEJ_TOOLS = True

    async def run():
        with patch("api.redis_client.get_redis_client") as mock_redis, \
             patch("worker.memory.HippocampalMemory") as MockHippocampus, \
             patch("worker.tool_invoker.call_tool") as mock_call:
            mock_redis.return_value = MagicMock()
            MockHippocampus.return_value = MagicMock()

            _ensure_agentscope_stub()
            from worker.debate_cycle import DebateCycle
            from worker.chairman import Chairman
            from agentscope.agent import AgentBase

            chairman = MagicMock(spec=Chairman)
            agent = MagicMock(spec=AgentBase)
            agent.name = "TestAgent"
            teams = [{"name": "Team", "side": "pro", "agents": [agent]}]

            cycle = DebateCycle("test_db_fallback", "Topic", chairman, teams, 1)

            def side_effect(name, params):
                if name == "tej.stock_price":
                    return {"data": []}
                if name == "financial.get_verified_price":
                    return {"data": []}
                if name == "twse.stock_day":
                    return {"data": [{"date": "2024-12-01"}]}
                if name == "yahoo.stock_info":
                    return {"date": "2024-12-01"}
                return {}

            mock_call.side_effect = side_effect

            await cycle._check_db_date_async()

            assert cycle.latest_db_date == "2024-12-01"
            assert cycle.latest_db_date_meta.get("from_fallback") is True
            assert cycle.latest_db_date_meta.get("source") in ("financial.get_verified_price", "twse.stock_day", "yahoo.stock_info")

            called_tools = [c.args[0] for c in mock_call.call_args_list]
            assert "tej.stock_price" in called_tools

    asyncio.run(run())
