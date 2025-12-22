import asyncio
from unittest.mock import patch, MagicMock
import sys
import types


if "agentscope.agent" not in sys.modules:
    mod = types.ModuleType("agentscope.agent")
    class AgentBase:
        pass
    mod.AgentBase = AgentBase
    sys.modules["agentscope.agent"] = mod

if "tiktoken" not in sys.modules:
    sys.modules["tiktoken"] = types.ModuleType("tiktoken")

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


from api.config import Config
from worker.memory import HippocampalMemory


def test_normalize_params_tej_disabled_skips_params(monkeypatch):
    monkeypatch.setattr(Config, "ENABLE_TEJ_TOOLS", False)

    with patch("worker.memory.get_redis_client") as mock_redis, \
         patch("worker.memory.tool_registry") as mock_registry:
        mock_redis.return_value = MagicMock()
        mock_registry.get_tool_data.return_value = {
            "schema": {
                "type": "object",
                "properties": {
                    "coid": {"type": "string"}
                }
            }
        }

        mem = HippocampalMemory("debate-tej-disabled")
        params = {"ticker": "2330", "start_date": "2024-01-01", "end_date": "2024-01-31"}
        normalized = mem._normalize_params("tej.stock_price", params)

        assert normalized == {}


def test_normalize_params_tej_enabled_uses_coid(monkeypatch):
    monkeypatch.setattr(Config, "ENABLE_TEJ_TOOLS", True)

    with patch("worker.memory.get_redis_client") as mock_redis, \
         patch("worker.memory.tool_registry") as mock_registry:
        mock_redis.return_value = MagicMock()
        mock_registry.get_tool_data.return_value = {
            "schema": {
                "type": "object",
                "properties": {
                    "coid": {"type": "string"}
                }
            }
        }

        mem = HippocampalMemory("debate-tej-enabled")
        params = {"ticker": "2330", "start_date": "2024-01-01", "end_date": "2024-01-31"}
        normalized = mem._normalize_params("tej.stock_price", params)

        assert "coid" in normalized
        assert normalized["coid"] == "2330"


def test_search_shared_memory_skips_tej_when_disabled(monkeypatch):
    monkeypatch.setattr(Config, "ENABLE_TEJ_TOOLS", False)

    async def fake_search(collection_name, query, limit, filter_conditions=None):
        return [
            {
                "tool": "tej.stock_price",
                "timestamp": 1700000000,
                "date_str": "2023-11-15",
                "agent_id": "A",
                "text": "TEJ price snapshot"
            },
            {
                "tool": "financial.get_verified_price",
                "timestamp": 1700000000,
                "date_str": "2023-11-15",
                "agent_id": "B",
                "text": "Verified price snapshot"
            },
        ]

    with patch("worker.memory.get_redis_client") as mock_redis, \
         patch("worker.memory.VectorStore") as mock_vs:
        mock_redis.return_value = MagicMock()
        mock_vs.search.side_effect = fake_search

        mem = HippocampalMemory("debate-tej-disabled-search")

        async def run():
            text = await mem.search_shared_memory("台積電", limit=5)
            assert "tej.stock_price" not in text
            assert "financial.get_verified_price" in text

        asyncio.run(run())
