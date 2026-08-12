"""Tests for issue #95 path traversal hardening in scripts/drift_detector.py.

`drift_detector._session_state_path(session_id)` interpolates an
attacker-controlled session_id from stdin JSON into a path inside
`SESSION_STATE_DIR`. A malicious payload like `session_id="../../etc/passwd"`
lets an attacker write JSON content into arbitrary files in the repo tree.
"""

import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from plugins.hooks.scripts import drift_detector


def test_session_state_path_rejects_traversal(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """`session_id` containing `..` is rejected before any path operation."""
    monkeypatch.setattr(drift_detector, "SESSION_STATE_DIR", tmp_path)
    with pytest.raises(ValueError, match="session_id"):
        drift_detector._session_state_path("../../etc/passwd")


def test_session_state_path_rejects_path_separator(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """`session_id` containing `/` is rejected."""
    monkeypatch.setattr(drift_detector, "SESSION_STATE_DIR", tmp_path)
    with pytest.raises(ValueError, match="session_id"):
        drift_detector._session_state_path("foo/bar")


def test_session_state_path_rejects_too_long(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """`session_id` longer than 128 chars is rejected."""
    monkeypatch.setattr(drift_detector, "SESSION_STATE_DIR", tmp_path)
    with pytest.raises(ValueError, match="session_id"):
        drift_detector._session_state_path("a" * 129)


def test_session_state_path_accepts_well_formed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Well-formed session_id produces a path inside SESSION_STATE_DIR."""
    monkeypatch.setattr(drift_detector, "SESSION_STATE_DIR", tmp_path)
    p = drift_detector._session_state_path("abc-123_DEF")
    assert p == tmp_path / "abc-123_DEF.json"
    assert p.resolve().parent == tmp_path.resolve()
