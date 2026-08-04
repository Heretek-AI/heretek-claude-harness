"""Tests for scripts/new_plugin.py."""
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import new_plugin  # noqa: E402


def test_scaffold_creates_plugin_dir(tmp_path: Path) -> None:
    plugin_dir = new_plugin.scaffold(tmp_path, "rust", "Rust task plugin.")
    assert plugin_dir.is_dir()
    assert plugin_dir.name == "rust"
    assert (plugin_dir / ".claude-plugin" / "plugin.json").is_file()
    assert (plugin_dir / "README.md").is_file()


def test_scaffold_plugin_json_has_required_fields(tmp_path: Path) -> None:
    plugin_dir = new_plugin.scaffold(tmp_path, "rust", "Rust task plugin.")
    data = json.loads((plugin_dir / ".claude-plugin" / "plugin.json").read_text())
    assert data["name"] == "rust"
    assert data["description"] == "Rust task plugin."
    assert data["license"] == "MIT"


def test_scaffold_refuses_existing_dir(tmp_path: Path) -> None:
    new_plugin.scaffold(tmp_path, "rust", "Rust task plugin.")
    with pytest.raises(FileExistsError):
        new_plugin.scaffold(tmp_path, "rust", "duplicate")


def test_scaffold_rejects_invalid_name(tmp_path: Path) -> None:
    with pytest.raises(ValueError):
        new_plugin.scaffold(tmp_path, "Rust Plugin!", "bad name")


def test_main_creates_and_exits_zero(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        sys,
        "argv",
        ["new_plugin.py", "--repo-root", str(tmp_path), "rust", "Rust task plugin."],
    )
    assert new_plugin.main() == 0
    assert (tmp_path / "plugins" / "rust" / ".claude-plugin" / "plugin.json").is_file()
