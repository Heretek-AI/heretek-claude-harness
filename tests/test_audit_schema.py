"""Tests for the audit_finding.schema.json JSON Schema."""

import json
from pathlib import Path

import jsonschema
import pytest


def test_schema_exists(schemas_dir: Path) -> None:
    schema_path = schemas_dir / "audit_finding.schema.json"
    assert schema_path.is_file(), f"missing schema at {schema_path}"


def test_valid_finding_passes(schemas_dir: Path, fixtures_dir: Path) -> None:
    schema = json.loads((schemas_dir / "audit_finding.schema.json").read_text())
    example = (fixtures_dir / "audit" / "valid_finding.yaml").read_text()
    # YAML, not JSON — we use ruamel to parse.
    from ruamel.yaml import YAML

    parsed = YAML(typ="safe").load(example)
    jsonschema.validate(instance=parsed, schema=schema)  # must not raise


def test_missing_required_field_fails(schemas_dir: Path, fixtures_dir: Path) -> None:
    schema = json.loads((schemas_dir / "audit_finding.schema.json").read_text())
    bad = (fixtures_dir / "audit" / "invalid_finding_missing_severity.yaml").read_text()
    from ruamel.yaml import YAML

    parsed = YAML(typ="safe").load(bad)
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(instance=parsed, schema=schema)


def test_bad_enum_value_fails(schemas_dir: Path, fixtures_dir: Path) -> None:
    schema = json.loads((schemas_dir / "audit_finding.schema.json").read_text())
    bad = (fixtures_dir / "audit" / "invalid_finding_bad_enum.yaml").read_text()
    from ruamel.yaml import YAML

    parsed = YAML(typ="safe").load(bad)
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(instance=parsed, schema=schema)
