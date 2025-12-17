from pathlib import Path
from typing import Tuple, List, Any
import json

try:
    import jsonschema
except ImportError:  # pragma: no cover
    jsonschema = None

SCHEMA_PATH = Path(__file__).resolve().parents[1] / "docs" / "schemas" / "topic.schema.json"


def validate_topic(topic: dict) -> Tuple[bool, List[str]]:
    """
    Validate topic payload against JSON schema.
    Returns: (ok, errors)
    """
    if jsonschema is None:
        return False, ["jsonschema not installed. pip install jsonschema"]

    if not SCHEMA_PATH.exists():
        return False, [f"Schema not found: {SCHEMA_PATH}"]

    schema: Any = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    validator = jsonschema.Draft202012Validator(schema)
    errors = sorted(validator.iter_errors(topic), key=lambda e: e.path)
    if errors:
        messages = [f"{'.'.join(map(str, e.path))}: {e.message}" for e in errors]
        return False, messages
    return True, []
