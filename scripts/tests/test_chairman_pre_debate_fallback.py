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


def _get_chairman_class():
    if "agentscope.agent" not in sys.modules:
        mod = types.ModuleType("agentscope.agent")
        class AgentBase:
            pass
        mod.AgentBase = AgentBase
        sys.modules["agentscope.agent"] = mod
    from worker.chairman import Chairman
    return Chairman


def test_chairman_fallback_from_tej_price_uses_twse_first():
    async def run():
        with patch("worker.chairman.get_redis_client") as mock_redis, \
             patch("worker.tool_invoker.call_tool") as mock_call:
            mock_redis.return_value = MagicMock()

            Chairman = _get_chairman_class()
            chairman = Chairman(name="Chair", model_config_name="gpt-4")

            def side_effect(name, params):
                if name == "twse.stock_day":
                    return {"data": [{"date": "2024-12-01"}]}
                if name == "financial.get_verified_price":
                    return {"status": "ok"}
                return {}

            mock_call.side_effect = side_effect

            params = {"coid": "2330.TW"}
            res = await chairman._fallback_from_tej_price(params, debate_id="debate-1")

            assert isinstance(res, dict)
            assert res.get("data") and res["data"][0].get("date") == "2024-12-01"

            called_tools = [c.args[0] for c in mock_call.call_args_list]
            assert "twse.stock_day" in called_tools
            assert "financial.get_verified_price" not in called_tools

    asyncio.run(run())


def test_chairman_fallback_from_tej_price_uses_verified_when_twse_fails():
    async def run():
        with patch("worker.chairman.get_redis_client") as mock_redis, \
             patch("worker.tool_invoker.call_tool") as mock_call:
            mock_redis.return_value = MagicMock()

            Chairman = _get_chairman_class()
            chairman = Chairman(name="Chair", model_config_name="gpt-4")

            def side_effect(name, params):
                if name == "twse.stock_day":
                    return {"data": []}
                if name == "financial.get_verified_price":
                    return {"status": "ok", "source": "verified"}
                return {}

            mock_call.side_effect = side_effect

            params = {"coid": "2330.TW"}
            res = await chairman._fallback_from_tej_price(params, debate_id="debate-2")

            assert isinstance(res, dict)
            assert res.get("status") == "ok"
            assert res.get("source") == "verified"

            called_tools = [c.args[0] for c in mock_call.call_args_list]
            assert "twse.stock_day" in called_tools
            assert "financial.get_verified_price" in called_tools

    asyncio.run(run())
