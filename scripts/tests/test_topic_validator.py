import pytest
from worker.topic_validator import validate_topic


def test_topic_validator_ok():
    topic = {
        "title": "某股票為何下跌",
        "timeframe": "1m",
        "metric": "abs_price",
        "question_type": "attribution",
        "acceptance_criteria": ["需覆蓋短期驅動因素"]
    }
    ok, errors = validate_topic(topic)
    assert ok, f"should pass schema, errors: {errors}"


def test_topic_validator_missing_fields():
    topic = {"title": "不完整辯題"}
    ok, errors = validate_topic(topic)
    assert not ok and errors
