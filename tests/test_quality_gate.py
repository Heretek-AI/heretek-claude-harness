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


def test_parse_scope_rejects_traversal() -> None:
    """`..`-traversal must raise ValueError; never become subprocess cwd (#161)."""
    with pytest.raises(ValueError, match="escapes REPO_ROOT"):
        quality_gate.parse_scope("../../etc")


def test_parse_scope_rejects_absolute_outside_repo() -> None:
    """Absolute paths outside REPO_ROOT must raise ValueError (#161)."""
    with pytest.raises(ValueError):
        quality_gate.parse_scope("/etc")


def test_parse_scope_accepts_repo_relative() -> None:
    """Valid repo-relative paths parse normally and _scope_cwd resolves under REPO_ROOT (#161)."""
    scope = quality_gate.parse_scope("plugins/hooks")
    assert scope == {"scope": "path", "path": "plugins/hooks"}
    repo_root = Path(quality_gate.__file__).resolve().parents[3]
    cwd = quality_gate._scope_cwd(scope)
    assert cwd.is_relative_to(repo_root)


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
