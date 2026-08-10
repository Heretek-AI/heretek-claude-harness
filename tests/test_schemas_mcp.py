"""Tests for the .mcp.json JSON Schema."""

import json
from pathlib import Path

import jsonschema
import pytest


def test_valid_mcp_passes(schemas_dir: Path, fixtures_dir: Path) -> None:
    schema = json.loads((schemas_dir / "mcp.schema.json").read_text())
    example = json.loads((fixtures_dir / "mcp" / "valid.json").read_text())
    jsonschema.validate(instance=example, schema=schema)


def test_invalid_mcp_fails(schemas_dir: Path, fixtures_dir: Path) -> None:
    schema = json.loads((schemas_dir / "mcp.schema.json").read_text())
    bad = json.loads((fixtures_dir / "mcp" / "invalid.json").read_text())
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(instance=bad, schema=schema)
