from types import SimpleNamespace
from worker.tool_invoker_decision import decide_source, SOURCE_STM, SOURCE_L1, SOURCE_L2, SOURCE_LTM, SOURCE_TOOL


def test_decision_stm_first():
    ctx = SimpleNamespace(stm={"k1": {"v": 1}})
    src, payload = decide_source({"key": "k1"}, ctx)
    assert src == SOURCE_STM


def test_decision_falls_to_tool():
    ctx = SimpleNamespace()
    src, payload = decide_source({"key": "k2"}, ctx)
    assert src == SOURCE_TOOL
