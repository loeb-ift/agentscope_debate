from worker.circuit_breaker import CircuitBreaker


def test_circuit_breaker_open_and_recover(monkeypatch):
    cb = CircuitBreaker(failure_threshold=2, reset_timeout_s=0.01)
    assert cb.allow()
    cb.on_failure()
    assert cb.allow()
    cb.on_failure()
    assert not cb.allow()  # open
