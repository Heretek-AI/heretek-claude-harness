"""Tests for Layer-2 quality_gate.py."""
import sys
from pathlib import Path
from unittest import mock

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "plugins" / "hooks" / "scripts"))
import quality_gate  # noqa: E402


def test_parse_scope_repo() -> None:
    assert quality_gate.parse_scope("repo") == {"scope": "repo"}


def test_parse_scope_diff() -> None:
    assert quality_gate.parse_scope("diff") == {"scope": "diff"}


def test_parse_scope_path() -> None:
    assert quality_gate.parse_scope("src/foo") == {"scope": "path", "path": "src/foo"}


def test_parse_scope_empty_defaults_to_repo() -> None:
    assert quality_gate.parse_scope("") == {"scope": "repo"}


def test_resolve_tools_returns_subset_of_known() -> None:
    tools = quality_gate.resolve_tools()
    for t in tools:
        assert t in {"clippy", "megalinter", "tdd-guard", "jscpd", "sonarqube"}


def test_run_repo_with_no_tools_exits_zero() -> None:
    """If no Layer-2 tools are installed, runner exits 0 (nothing to fail)."""
    # Force empty tool list by mocking.
    with mock.patch.object(quality_gate, "resolve_tools", return_value=[]):
        assert quality_gate.run({"scope": "repo"}) == 0
