"""Schema fixture is well-formed JSON Schema (Draft-7) and validates."""
from __future__ import annotations

import json
from pathlib import Path

import jsonschema
import pytest

SCHEMA_PATH = Path(__file__).parent / "fixtures" / "telemetry_schema.json"


def test_schema_file_exists() -> None:
    assert SCHEMA_PATH.exists(), f"missing {SCHEMA_PATH}"


def test_schema_is_valid_draft7() -> None:
    schema = json.loads(SCHEMA_PATH.read_text())
    # Raises jsonschema.exceptions.SchemaError if invalid.
    jsonschema.Draft7Validator.check_schema(schema)


def test_schema_requires_schema_version_one() -> None:
    schema = json.loads(SCHEMA_PATH.read_text())
    assert schema["properties"]["schema_version"]["const"] == 1


def test_schema_rejects_unknown_event_type() -> None:
    schema = json.loads(SCHEMA_PATH.read_text())
    validator = jsonschema.Draft7Validator(schema)
    with pytest.raises(jsonschema.ValidationError):
        validator.validate({"event_type": "NotARealEvent"})


def test_schema_rejects_unknown_tool_name() -> None:
    schema = json.loads(SCHEMA_PATH.read_text())
    validator = jsonschema.Draft7Validator(schema)
    with pytest.raises(jsonschema.ValidationError):
        validator.validate({"tool_name": "NotARealTool"})
