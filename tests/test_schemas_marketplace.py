"""Tests for the marketplace.json JSON Schema."""
import json
from pathlib import Path

import jsonschema
import pytest


def test_marketplace_schema_exists(schemas_dir: Path) -> None:
    schema_path = schemas_dir / "marketplace.schema.json"
    assert schema_path.is_file(), f"missing schema at {schema_path}"


def test_valid_marketplace_passes(schemas_dir: Path, fixtures_dir: Path) -> None:
    schema = json.loads((schemas_dir / "marketplace.schema.json").read_text())
    example = json.loads((fixtures_dir / "marketplace" / "valid.json").read_text())
    jsonschema.validate(instance=example, schema=schema)  # must not raise


def test_invalid_marketplace_fails(schemas_dir: Path, fixtures_dir: Path) -> None:
    schema = json.loads((schemas_dir / "marketplace.schema.json").read_text())
    bad = json.loads((fixtures_dir / "marketplace" / "invalid.json").read_text())
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(instance=bad, schema=schema)
