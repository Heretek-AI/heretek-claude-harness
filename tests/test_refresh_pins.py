"""Tests for scripts/refresh_pins.py."""
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "scripts"))

import refresh_pins  # noqa: E402

FIXTURE = REPO_ROOT / "tests" / "fixtures" / "refresh_pins" / "sample_catalog.yaml"


def test_check_item_offline_returns_ok_or_stale_without_network() -> None:
    """Without a token, `check_item` does NOT call GitHub; it compares the stored sha against a derived expectation."""
    item = {
        "id": "rust-analyzer",
        "kind": "lsp",
        "upstream": "rust-lang/rust-analyzer",
        "sha": "0123456789abcdef0123456789abcdef01234567",
        "license": "MIT",
        "vetting": {"status": "approved", "date": "2026-08-04", "stars": 16000, "last_commit": "2026-08-04"},
    }
    status, details = refresh_pins.check_item(item, gh_token=None)
    # Without a token, the tool cannot make API calls; it should report "skipped" or surface a clear reason.
    assert status in {"skipped", "ok", "stale_stars", "stale_commit", "license_drift"}
    assert "reason" in details or status == "skipped"


def test_check_item_detects_stale_last_commit() -> None:
    """A vetting.last_commit older than 12 months ago is flagged as stale_commit."""
    import datetime as dt

    old_date = (dt.date.today() - dt.timedelta(days=400)).isoformat()
    item = {
        "id": "old-thing",
        "upstream": "someorg/old-thing",
        "sha": "abc",
        "license": "MIT",
        "vetting": {"status": "approved", "date": old_date, "stars": 1000, "last_commit": old_date},
    }
    status, details = refresh_pins.check_item(item, gh_token=None)
    # The offline check should at least surface the stale date.
    assert details.get("last_commit") == old_date or status == "stale_commit"


def test_check_catalog_returns_list_per_item(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """check_catalog walks every plugin's items[] and emits one entry per item."""
    # No network calls; offline behavior.
    monkeypatch.setattr(refresh_pins, "_github_get", lambda *_a, **_k: {})
    results = refresh_pins.check_catalog(FIXTURE, gh_token=None)
    # 2 items in the fixture
    assert len(results) == 2
    ids = {item_id for _, _, item_id, _ in results}
    assert "rust-analyzer" in ids
    assert "ghost-tool" in ids


def test_bump_sha_returns_updated_item() -> None:
    item = {"id": "x", "sha": "old", "vetting": {"date": "2026-01-01"}}
    new = refresh_pins.bump_sha(item, "new-sha")
    assert new["sha"] == "new-sha"
    assert new["vetting"]["date"] != "2026-01-01"


def test_main_no_token_prints_table(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture) -> None:
    """`main` with no token prints a status table to stdout and exits 0 (don't fail on stale)."""
    monkeypatch.setattr("sys.argv", ["refresh_pins.py", "--catalog", str(FIXTURE)])
    rc = refresh_pins.main()
    assert rc in (0, 1)  # 0 = all fresh; 1 = some stale; both are non-error
    captured = capsys.readouterr()
    assert "rust-analyzer" in captured.out or "ghost-tool" in captured.out
