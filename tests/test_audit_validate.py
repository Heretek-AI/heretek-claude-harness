"""Tests for scripts/audit/validate.py."""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
from audit import validate  # noqa: E402


def _load_yaml(p: Path) -> dict:
    from ruamel.yaml import YAML

    return YAML(typ="safe").load(p.read_text())


def test_validate_finding_accepts_valid_card(
    schemas_dir: Path, fixtures_dir: Path
) -> None:
    validate.SCHEMA_PATH = schemas_dir / "audit_finding.schema.json"
    valid = _load_yaml(fixtures_dir / "audit" / "valid_finding.yaml")
    errors = validate.validate_finding(valid)
    assert errors == [], f"expected no errors, got: {errors}"


def test_validate_finding_rejects_missing_severity(
    schemas_dir: Path, fixtures_dir: Path
) -> None:
    validate.SCHEMA_PATH = schemas_dir / "audit_finding.schema.json"
    bad = _load_yaml(fixtures_dir / "audit" / "invalid_finding_missing_severity.yaml")
    errors = validate.validate_finding(bad)
    assert len(errors) >= 1
    assert any("severity" in e for e in errors)


def test_validate_finding_rejects_bad_enum(
    schemas_dir: Path, fixtures_dir: Path
) -> None:
    validate.SCHEMA_PATH = schemas_dir / "audit_finding.schema.json"
    bad = _load_yaml(fixtures_dir / "audit" / "invalid_finding_bad_enum.yaml")
    errors = validate.validate_finding(bad)
    assert len(errors) >= 1


def test_validate_findings_indexes_errors(
    schemas_dir: Path, fixtures_dir: Path
) -> None:
    validate.SCHEMA_PATH = schemas_dir / "audit_finding.schema.json"
    findings = [
        _load_yaml(fixtures_dir / "audit" / "valid_finding.yaml"),
        _load_yaml(fixtures_dir / "audit" / "invalid_finding_bad_enum.yaml"),
    ]
    indexed = validate.validate_findings(findings)
    assert indexed == [] or all(isinstance(t, tuple) for t in indexed)
    # The bad one at index 1 should produce errors.
    bad_index, bad_errors = next(iter([t for t in indexed if t[1]]))
    assert bad_index == 1
    assert len(bad_errors) >= 1


def test_cli_exits_zero_on_valid(
    schemas_dir: Path,
    fixtures_dir: Path,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    validate.SCHEMA_PATH = schemas_dir / "audit_finding.schema.json"
    # Write a single-finding YAML file the CLI can read.
    single = tmp_path / "single.yaml"
    single.write_text((fixtures_dir / "audit" / "valid_finding.yaml").read_text())
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "validate.py",
            "--schema",
            str(schemas_dir / "audit_finding.schema.json"),
            str(single),
        ],
    )
    assert validate.main() == 0


def test_cli_exits_one_on_invalid(
    schemas_dir: Path,
    fixtures_dir: Path,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    validate.SCHEMA_PATH = schemas_dir / "audit_finding.schema.json"
    single = tmp_path / "bad.yaml"
    single.write_text(
        (fixtures_dir / "audit" / "invalid_finding_bad_enum.yaml").read_text()
    )
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "validate.py",
            "--schema",
            str(schemas_dir / "audit_finding.schema.json"),
            str(single),
        ],
    )
    assert validate.main() == 1
