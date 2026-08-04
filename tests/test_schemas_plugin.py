"""Tests for the plugin.json JSON Schema."""
import json
from pathlib import Path

import jsonschema
import pytest


def test_valid_plugin_passes(schemas_dir: Path, fixtures_dir: Path) -> None:
    schema = json.loads((schemas_dir / "plugin.schema.json").read_text())
    example = json.loads((fixtures_dir / "plugin" / "valid.json").read_text())
    jsonschema.validate(instance=example, schema=schema)


def test_invalid_plugin_fails(schemas_dir: Path, fixtures_dir: Path) -> None:
    schema = json.loads((schemas_dir / "plugin.schema.json").read_text())
    bad = json.loads((fixtures_dir / "plugin" / "invalid.json").read_text())
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(instance=bad, schema=schema)