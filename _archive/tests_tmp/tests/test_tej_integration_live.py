import os
import pytest

from adapters.tej_adapter import TEJAdapter

TEJ_KEY = os.getenv("TEJ_API_KEY")

requires_key = pytest.mark.skipif(not TEJ_KEY, reason="TEJ_API_KEY not set; skipping live integration test")


@requires_key
def test_teJ_trail_taiacc_live_small_limit():
    adapter = TEJAdapter(api_key=TEJ_KEY)
    out = adapter.invoke({
        "db": "TRAIL",
        "table": "TAIACC",
        "limit": 1,
        "offset": 0,
    })
    assert out.data["db"] == "TRAIL"
    assert out.data["table"] == "TAIACC"
    assert out.data["limit"] == 1
    assert isinstance(out.data.get("rows"), (list, dict))
