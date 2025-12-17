from worker.debate_gate_sample import pre_round_gate


def test_pre_round_gate_rejects_invalid_topic():
    ok, errors = pre_round_gate({"title": "x"})
    assert not ok and errors
