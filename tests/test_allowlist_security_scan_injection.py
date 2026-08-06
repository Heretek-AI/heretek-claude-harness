"""Tests for issue #94 path injection hardening in scripts/security_scan.py.

Sites covered:
- security_scan.py:70 — `_shallow_clone` interpolates `upstream` into a git URL.
- security_scan.py:130 — `_commit_catalog_bump` interpolates `item_id` +
  `new_sha[:12]` into a git branch name.
"""
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from scripts import security_scan  # noqa: E402


def test_shallow_clone_rejects_evil_upstream(tmp_path: Path) -> None:
    """`upstream` containing `..` is rejected before any subprocess invocation."""
    target = tmp_path / "scan"
    with pytest.raises(ValueError, match="upstream"):
        security_scan._shallow_clone("../etc/passwd", "deadbeef" * 5, target)
    assert not target.exists()


def test_shallow_clone_accepts_well_formed_upstream(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Well-formed upstream proceeds (we mock `git clone` so no network)."""
    called: list[list[str]] = []

    def fake_run(argv, **_kw):
        called.append(list(argv))
        return _FakeCompletedProcess(0)

    monkeypatch.setattr(security_scan.subprocess, "run", fake_run)

    target = tmp_path / "scan"
    target.mkdir()
    security_scan._shallow_clone("rust-lang/rust-analyzer", "deadbeef" * 5, target)

    clone_argv = next(a for a in called if a and a[0] == "git" and "clone" in a)
    assert any("rust-lang/rust-analyzer" in str(arg) for arg in clone_argv)


def test_commit_branch_rejects_evil_item_id(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """`item_id` containing `/` is rejected before any git call."""
    catalog = tmp_path / "catalog.yaml"
    catalog.write_text("plugins: []\n")

    monkeypatch.setattr(security_scan.subprocess, "run", lambda *a, **k: _FakeCompletedProcess(0))
    monkeypatch.setattr(security_scan, "bump_item_sha", lambda *a, **k: None)

    with pytest.raises(ValueError, match="item_id"):
        security_scan._commit_catalog_bump(
            catalog_path=catalog,
            repo_root=tmp_path,
            plugin="p",
            item_id="foo/bar",
            new_sha="deadbeef" * 5,
            vetting_date="2026-08-06",
        )


def test_commit_branch_rejects_non_hex_sha(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """`new_sha` that isn't 40 hex chars is rejected."""
    catalog = tmp_path / "catalog.yaml"
    catalog.write_text("plugins: []\n")

    monkeypatch.setattr(security_scan.subprocess, "run", lambda *a, **k: _FakeCompletedProcess(0))

    with pytest.raises(ValueError, match="sha"):
        security_scan._commit_catalog_bump(
            catalog_path=catalog,
            repo_root=tmp_path,
            plugin="p",
            item_id="foo",
            new_sha="not-hex",
            vetting_date="2026-08-06",
        )


def test_commit_branch_constructs_safe_branch_name(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Well-formed item_id + sha produce a well-formed branch name; git calls
    use the validated branch (no extra sanitization needed)."""
    catalog = tmp_path / "catalog.yaml"
    catalog.write_text("plugins: []\n")

    called: list[list[str]] = []

    def fake_run(argv, **_kw):
        called.append(list(argv))
        return _FakeCompletedProcess(0)

    monkeypatch.setattr(security_scan.subprocess, "run", fake_run)
    monkeypatch.setattr(security_scan, "bump_item_sha", lambda *a, **k: None)

    branch = security_scan._commit_catalog_bump(
        catalog_path=catalog,
        repo_root=tmp_path,
        plugin="p",
        item_id="rust-clippy",
        new_sha="deadbeef" * 5,
        vetting_date="2026-08-06",
    )
    assert branch == "security-scan/rust-clippy-deadbeefdead"

    # Every git command that mentions a branch must use the validated name.
    # `git checkout -b <branch>` and `git push origin <branch>` both reference
    # the branch as a positional argument.
    for argv in called:
        if argv[:2] == ["git", "checkout"] and "-b" in argv:
            assert argv[-1] == "security-scan/rust-clippy-deadbeefdead"
        if argv[:2] == ["git", "push"]:
            assert "security-scan/rust-clippy-deadbeefdead" in argv


class _FakeCompletedProcess:
    def __init__(self, returncode: int) -> None:
        self.returncode = returncode
        self.stdout = ""
        self.stderr = ""