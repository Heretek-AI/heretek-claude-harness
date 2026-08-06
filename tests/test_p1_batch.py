"""Tests for issue #96 P1 batch fixes.

Items:
1. refresh_pins uses HEAD ref instead of latest release SHA.
2. refresh_pins license drift fires on missing-license items.
3. stale_dep_intercept off-by-one (fires on 1-minor-behind).
4. security_scan relative_to crashes when catalog outside repo_root.
5. security_scan hardcoded `git checkout main` ignores default branch.
"""
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from scripts import refresh_pins, security_scan  # noqa: E402
from scripts import stale_dep_intercept  # noqa: E402


# ── Item 1: refresh_pins uses HEAD, not release SHA ─────────────────────────


def test_update_shas_pins_release_not_head(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """`update_shas` should query `/repos/{up}/releases/latest` and pin that SHA,
    not the HEAD SHA. Mock both endpoints and assert the catalog gets the
    release SHA."""
    catalog = tmp_path / "catalog.yaml"
    catalog.write_text(
        "plugins:\n"
        "  - name: p\n"
        "    items:\n"
        "      - id: foo\n"
        '        upstream: rust-lang/rust-analyzer\n'
        '        sha: "0000000000000000000000000000000000000000"\n'
        "        vetting: {}\n"
    )

    release_sha = "a" * 40
    head_sha = "f" * 40

    def fake_github_get(path: str, _tok: str) -> dict:
        if path.endswith("/releases/latest"):
            return {"target_commitish": release_sha, "tag_name": "v1.0.0"}
        if "/git/ref/heads/" in path:
            return {"object": {"sha": head_sha}}
        if path.endswith("/rust-lang/rust-analyzer"):
            return {"default_branch": "main"}
        return {}

    monkeypatch.setattr(refresh_pins, "_github_get", fake_github_get)

    updates = refresh_pins.update_shas(catalog, gh_token="t")
    assert updates == [("foo", "0" * 40, release_sha)]


# ── Item 2: license false-positive on missing-license items ────────────────


def test_check_item_license_missing_is_not_drift(monkeypatch: pytest.MonkeyPatch) -> None:
    """An item with no `license` field and upstream NOASSERTION must not be
    reported as drift (closes #96 item 2)."""
    import datetime as dt

    item = {
        "id": "rust-analyzer",
        "upstream": "rust-lang/rust-analyzer",
        "sha": "0123456789abcdef0123456789abcdef01234567",
        "vetting": {
            "status": "approved",
            "date": "2026-08-04",
            "stars": 16000,
            "last_commit": "2026-08-04",
        },
    }
    repo_meta = {"stargazers_count": 16000, "default_branch": "main",
                 "pushed_at": "2026-08-04T00:00:00Z", "license": {"spdx_id": "NOASSERTION"}}

    monkeypatch.setattr(refresh_pins, "_github_get", lambda path, tok: (
        repo_meta if path.endswith("/rust-lang/rust-analyzer") else []
    ))

    status, details = refresh_pins.check_item(item, gh_token="t")
    assert status != "stale", f"missing-license item falsely flagged: {details}"
    assert "drifted" not in (details.get("reason") or "")


# ── Item 3: stale-dep off-by-one ────────────────────────────────────────────


def test_is_stale_one_minor_behind_is_fresh() -> None:
    """Pinned 1.0.0 vs latest 1.1.0 is NOT stale (must be ≥2 minor behind)."""
    from scripts.stale_dep_intercept import _is_stale

    assert _is_stale("1.0.0", "1.1.0") is False


def test_is_stale_two_minor_behind_is_stale() -> None:
    """Pinned 1.0.0 vs latest 1.2.0 IS stale."""
    from scripts.stale_dep_intercept import _is_stale

    assert _is_stale("1.0.0", "1.2.0") is True


# ── Item 4: relative_to crash when catalog outside repo_root ────────────────


def test_commit_branch_handles_catalog_outside_repo_root(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """If catalog lives outside repo_root, `_commit_catalog_bump` must still
    produce a working `git add <relpath>` (uses os.path.relpath fallback)."""
    catalog = tmp_path / "external_catalog.yaml"
    catalog.write_text("plugins: []\n")
    repo_root = tmp_path / "repo"
    repo_root.mkdir()

    captured: list[list[str]] = []

    def fake_run(argv, **_kw):
        captured.append(list(argv))
        return _FakeCompletedProcess(0)

    monkeypatch.setattr(security_scan.subprocess, "run", fake_run)
    monkeypatch.setattr(security_scan, "bump_item_sha", lambda *a, **k: None)

    security_scan._commit_catalog_bump(
        catalog_path=catalog,
        repo_root=repo_root,
        plugin="p",
        item_id="foo",
        new_sha="deadbeef" * 5,
        vetting_date="2026-08-06",
    )

    add_argv = next(a for a in captured if a and a[0] == "git" and a[1] == "add")
    relpath = add_argv[2]
    # Must be relative to repo_root (relpath uses ../ traversal but `git add`
    # accepts that).
    assert not Path(relpath).is_absolute()


# ── Item 5: hardcoded `git checkout main` ──────────────────────────────────


def test_commit_branch_uses_actual_default_branch(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The reset-to-default step must use the repo's actual default branch,
    not the hardcoded `main`. We mock `gh repo view` via env override."""
    catalog = tmp_path / "catalog.yaml"
    catalog.write_text("plugins: []\n")
    repo_root = tmp_path / "repo"
    repo_root.mkdir()

    # Stash real subprocess so we can capture calls.
    captured: list[list[str]] = []

    def fake_run(argv, **_kw):
        captured.append(list(argv))
        return _FakeCompletedProcess(0)

    monkeypatch.setattr(security_scan.subprocess, "run", fake_run)
    monkeypatch.setattr(security_scan, "bump_item_sha", lambda *a, **k: None)
    monkeypatch.setenv("HERETEK_DEFAULT_BRANCH", "develop")

    security_scan._commit_catalog_bump(
        catalog_path=catalog,
        repo_root=repo_root,
        plugin="p",
        item_id="foo",
        new_sha="deadbeef" * 5,
        vetting_date="2026-08-06",
    )

    checkout_main = [a for a in captured if a[:2] == ["git", "checkout"] and "-b" not in a]
    assert checkout_main, "expected a reset checkout"
    # The reset must be to develop (env), not main.
    assert checkout_main[-1][-1] == "develop"


class _FakeCompletedProcess:
    def __init__(self, returncode: int) -> None:
        self.returncode = returncode
        self.stdout = ""
        self.stderr = ""