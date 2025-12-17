from typing import Tuple, List
from .topic_validator import validate_topic


def pre_round_gate(topic: dict) -> Tuple[bool, List[str]]:
    ok, errors = validate_topic(topic)
    if not ok:
        # emit SSE: TopicClarificationRequired (placeholder)
        return False, errors
    return True, []
