"""Tests for the .lsp.json JSON Schema."""

import json
from pathlib import Path

import jsonschema
import pytest


def test_valid_lsp_passes(schemas_dir: Path, fixtures_dir: Path) -> None:
    schema = json.loads((schemas_dir / "lsp.schema.json").read_text())
    example = json.loads((fixtures_dir / "lsp" / "valid.json").read_text())
    jsonschema.validate(instance=example, schema=schema)


def test_invalid_lsp_fails(schemas_dir: Path, fixtures_dir: Path) -> None:
    schema = json.loads((schemas_dir / "lsp.schema.json").read_text())
    bad = json.loads((fixtures_dir / "lsp" / "invalid.json").read_text())
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(instance=bad, schema=schema)
