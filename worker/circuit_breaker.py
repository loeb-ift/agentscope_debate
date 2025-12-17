from dataclasses import dataclass
from time import monotonic

@dataclass
class CircuitBreaker:
    failure_threshold: int = 5
    reset_timeout_s: float = 30.0

    _state: str = "closed"  # closed | open | half_open
    _failures: int = 0
    _opened_at: float = 0.0

    def allow(self) -> bool:
        if self._state == "open":
            if monotonic() - self._opened_at >= self.reset_timeout_s:
                self._state = "half_open"
                return True
            return False
        return True

    def on_success(self) -> None:
        self._failures = 0
        self._state = "closed"

    def on_failure(self) -> None:
        self._failures += 1
        if self._failures >= self.failure_threshold:
            self._state = "open"
            self._opened_at = monotonic()
