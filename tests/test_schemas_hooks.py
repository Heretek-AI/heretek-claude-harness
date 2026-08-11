"""Tests for the hooks.json JSON Schema."""

import json
from pathlib import Path

import jsonschema
import pytest


def test_valid_hooks_passes(schemas_dir: Path, fixtures_dir: Path) -> None:
    schema = json.loads((schemas_dir / "hooks.schema.json").read_text())
    example = json.loads((fixtures_dir / "hooks" / "valid.json").read_text())
    jsonschema.validate(instance=example, schema=schema)


def test_invalid_hooks_fails(schemas_dir: Path, fixtures_dir: Path) -> None:
    schema = json.loads((schemas_dir / "hooks.schema.json").read_text())
    bad = json.loads((fixtures_dir / "hooks" / "invalid.json").read_text())
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(instance=bad, schema=schema)
