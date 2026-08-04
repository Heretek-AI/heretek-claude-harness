"""Tests for scripts/validate.py."""
import json
import sys
from pathlib import Path

import pytest

# Make scripts/ importable as a package.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import validate  # noqa: E402


def _write(p: Path, payload: dict | list) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(payload))


def _minimal_marketplace() -> dict:
    return {
        "name": "test-mp",
        "owner": {"name": "Tester"},
        "plugins": [
            {"name": "p1", "source": "p1", "category": "task"}
        ]
    }


def _minimal_plugin(name: str = "p1") -> dict:
    return {"name": name, "description": "test plugin"}


def test_validate_clean_tree_returns_no_errors(
    tmp_path: Path, schemas_dir: Path
) -> None:
    _write(tmp_path / ".claude-plugin" / "marketplace.json", _minimal_marketplace())
    _write(tmp_path / "plugins" / "p1" / ".claude-plugin" / "plugin.json", _minimal_plugin())
    errors = validate.validate_all(tmp_path, schemas_dir=schemas_dir)
    assert errors == [], f"expected no errors, got: {errors}"


def test_validate_bad_marketplace_returns_error(
    tmp_path: Path, schemas_dir: Path
) -> None:
    bad = {"name": "", "owner": {}, "plugins": "not-an-array"}
    _write(tmp_path / ".claude-plugin" / "marketplace.json", bad)
    errors = validate.validate_all(tmp_path, schemas_dir=schemas_dir)
    assert len(errors) >= 1, "expected at least one error"


def test_validate_bad_plugin_returns_error(
    tmp_path: Path, schemas_dir: Path
) -> None:
    _write(tmp_path / ".claude-plugin" / "marketplace.json", _minimal_marketplace())
    _write(
        tmp_path / "plugins" / "p1" / ".claude-plugin" / "plugin.json",
        {"version": 12345},  # version must be string
    )
    errors = validate.validate_all(tmp_path, schemas_dir=schemas_dir)
    assert len(errors) >= 1


def test_validate_missing_marketplace_returns_error(
    tmp_path: Path, schemas_dir: Path
) -> None:
    errors = validate.validate_all(tmp_path, schemas_dir=schemas_dir)
    assert any("marketplace" in e.lower() for e in errors)


def test_main_exits_zero_on_clean(
    tmp_path: Path, schemas_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _write(tmp_path / ".claude-plugin" / "marketplace.json", _minimal_marketplace())
    _write(tmp_path / "plugins" / "p1" / ".claude-plugin" / "plugin.json", _minimal_plugin())
    monkeypatch.setattr(sys, "argv", ["validate.py", "--repo-root", str(tmp_path), "--schemas-dir", str(schemas_dir)])
    assert validate.main() == 0


def test_main_exits_nonzero_on_failure(
    tmp_path: Path, schemas_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    bad = {"name": "", "owner": {}, "plugins": "not-an-array"}
    _write(tmp_path / ".claude-plugin" / "marketplace.json", bad)
    monkeypatch.setattr(sys, "argv", ["validate.py", "--repo-root", str(tmp_path), "--schemas-dir", str(schemas_dir)])
    assert validate.main() == 1
