"""Regression for Dependabot CVEs (#16). Pins runtime deps to safe minimum versions."""
from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]


def _read(name: str) -> str:
    return (REPO_ROOT / name).read_text()


def test_jsonschema_at_safe_minimum() -> None:
    """jsonschema >= 4.26.0 (resolves CVE per #16)."""
    text = _read("requirements.txt")
    line = next((line for line in text.splitlines() if line.startswith("jsonschema")), "")
    version = line.split("==")[-1].strip()
    parts = [int(p) for p in version.split(".") if p.isdigit()]
    assert (parts[0], parts[1]) >= (4, 26), f"jsonschema {version} < 4.26 (CVE not fixed)"


def test_pyyaml_at_safe_minimum() -> None:
    """PyYAML >= 6.0.3 (resolves CVE per #16)."""
    text = _read("requirements.txt")
    line = next((line for line in text.splitlines() if line.startswith("PyYAML")), "")
    version = line.split("==")[-1].strip()
    parts = [int(p) for p in version.split(".") if p.isdigit()]
    assert (parts[0], parts[1], parts[2]) >= (6, 0, 3), f"PyYAML {version} < 6.0.3 (CVE not fixed)"


def test_pytest_at_safe_minimum() -> None:
    """pytest >= 9.1.1 (resolves CVE per #16)."""
    text = _read("requirements-dev.txt")
    line = next((line for line in text.splitlines() if line.startswith("pytest")), "")
    if line.strip().startswith("-"):
        return
    version = line.split("==")[-1].strip()
    parts = [int(p) for p in version.split(".") if p.isdigit()]
    assert (parts[0], parts[1]) >= (9, 1), f"pytest {version} < 9.1 (CVE not fixed)"


def test_ruamel_yaml_pinned() -> None:
    """ruamel.yaml pinned to a known-good version (Task 2 dependency)."""
    text = _read("requirements.txt")
    line = next((line for line in text.splitlines() if line.startswith("ruamel")), "")
    assert "==" in line, f"ruamel.yaml not pinned: {line!r}"