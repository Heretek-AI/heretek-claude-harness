"""Tests for scripts/refresh_pins.py."""

import datetime as dt
import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "scripts"))

import refresh_pins  # noqa: E402

FIXTURE = REPO_ROOT / "tests" / "fixtures" / "refresh_pins" / "sample_catalog.yaml"


def test_check_item_offline_returns_skipped_without_network() -> None:
    """Without a token, `check_item` does NOT call GitHub and returns `skipped` for fresh items."""
    item = {
        "id": "rust-analyzer",
        "kind": "lsp",
        "upstream": "rust-lang/rust-analyzer",
        "sha": "0123456789abcdef0123456789abcdef01234567",
        "license": "MIT",
        "vetting": {
            "status": "approved",
            "date": "2026-08-04",
            "stars": 16000,
            "last_commit": "2026-08-04",
        },
    }
    status, details = refresh_pins.check_item(item, gh_token=None)
    # For a fresh item with no token, the offline branch returns "skipped" exactly.
    # A regression that re-introduces PyYAML date-object parsing will surface here as "stale_commit".
    assert status == "skipped"
    assert "reason" in details


def test_check_item_detects_stale_last_commit() -> None:
    """A vetting.last_commit older than 12 months ago is flagged as stale_commit."""
    import datetime as dt

    old_date = (dt.date.today() - dt.timedelta(days=400)).isoformat()
    item = {
        "id": "old-thing",
        "upstream": "someorg/old-thing",
        "sha": "abc",
        "license": "MIT",
        "vetting": {
            "status": "approved",
            "date": old_date,
            "stars": 1000,
            "last_commit": old_date,
        },
    }
    status, details = refresh_pins.check_item(item, gh_token=None)
    # The offline check should at least surface the stale date.
    assert details.get("last_commit") == old_date or status == "stale_commit"


def test_check_catalog_returns_list_per_item(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """check_catalog walks every plugin's items[] and emits one entry per item."""
    # No network calls; offline behavior.
    monkeypatch.setattr(refresh_pins, "_github_get", lambda *_a, **_k: {})
    results = refresh_pins.check_catalog(FIXTURE, gh_token=None)
    # 2 items in the fixture
    assert len(results) == 2
    ids = {item_id for _, _, item_id, _ in results}
    assert "rust-analyzer" in ids
    assert "ghost-tool" in ids


def test_check_catalog_fresh_yaml_entry_is_not_stale_commit() -> None:
    """Regression test for C1: PyYAML parses unquoted ISO dates as `datetime.date` objects.

    After loading `sample_catalog.yaml`, the fresh item (`rust-analyzer`, vetting.date
    2026-08-04) must NOT be flagged as `stale_commit`. With no GITHUB_TOKEN, offline
    check returns `skipped`; before the fix, the date-object parsing bug caused the
    stale-date branch to mis-fire.
    """
    import yaml as _yaml

    data = _yaml.safe_load(FIXTURE.read_text())
    # Verify the precondition that PyYAML gives us a datetime.date object here.
    fresh_item = data["plugins"][0]["items"][0]
    assert isinstance(fresh_item["vetting"]["date"], dt.date)

    results = refresh_pins.check_catalog(FIXTURE, gh_token=None)
    by_id = {item_id: (status, details) for status, _, item_id, details in results}

    status, details = by_id["rust-analyzer"]
    assert status == "skipped", (
        f"Fresh YAML-loaded item must be `skipped`, got `{status}` "
        f"(reason={details.get('reason')!r})"
    )
    assert "GITHUB_TOKEN" in details.get("reason", "")


def test_bump_sha_returns_updated_item() -> None:
    item = {"id": "x", "sha": "old", "vetting": {"date": "2026-01-01"}}
    new = refresh_pins.bump_sha(item, "new-sha")
    assert new["sha"] == "new-sha"
    assert new["vetting"]["date"] != "2026-01-01"


def test_main_no_token_prints_table(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture
) -> None:
    """`main` with no token prints a status table to stdout and exits 0 (don't fail on stale)."""
    monkeypatch.setattr("sys.argv", ["refresh_pins.py", "--catalog", str(FIXTURE)])
    rc = refresh_pins.main()
    assert rc in (0, 1)  # 0 = all fresh; 1 = some stale; both are non-error
    captured = capsys.readouterr()
    assert "rust-analyzer" in captured.out or "ghost-tool" in captured.out


def test_update_shas_writes_new_release_sha(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """--update-shas fetches upstream's latest release SHA and writes it back."""
    import shutil

    fixture = REPO_ROOT / "tests" / "fixtures" / "refresh_pins" / "sample_catalog.yaml"
    catalog = tmp_path / "catalog.yaml"
    shutil.copy(fixture, catalog)

    new_sha = "f" * 40

    def fake_get(path: str, gh_token):
        if path.endswith("/releases/latest"):
            return {"target_commitish": new_sha, "tag_name": "v1.0.0"}
        if path.startswith("/repos/") and path.count("/") == 3:
            return {"default_branch": "master"}
        return {}

    monkeypatch.setattr(refresh_pins, "_github_get", fake_get)

    updates = refresh_pins.update_shas(catalog, gh_token="test-token")
    assert any(
        item_id == "rust-analyzer" and new_sha == new for item_id, _, new in updates
    )

    # Catalog was modified on disk with the new SHA.
    import yaml as _yaml

    new_data = _yaml.safe_load(catalog.read_text())
    items = new_data["plugins"][0]["items"]
    rust = next(it for it in items if it["id"] == "rust-analyzer")
    assert rust["sha"] == new_sha


def test_update_shas_requires_token(
    tmp_path: Path, capsys: pytest.CaptureFixture
) -> None:
    """--update-shas without a GitHub token is refused."""
    fixture = REPO_ROOT / "tests" / "fixtures" / "refresh_pins" / "sample_catalog.yaml"
    catalog = tmp_path / "catalog.yaml"
    import shutil

    shutil.copy(fixture, catalog)

    with pytest.raises(SystemExit) as exc_info:
        refresh_pins.update_shas(catalog, gh_token=None)
    # Error message goes to stderr; the SystemExit carries only the exit code.
    assert exc_info.value.code == 2
    captured = capsys.readouterr()
    assert "GITHUB_TOKEN" in captured.err or "github-token" in captured.err


def test_update_shas_preserves_comments(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Round-trip preserves inline `# review` comments (regression for f60cfa2)."""
    fixture = REPO_ROOT / "tests" / "fixtures" / "refresh_pins" / "sample_catalog.yaml"
    catalog = tmp_path / "catalog.yaml"
    import shutil

    shutil.copy(fixture, catalog)

    new_sha = "a" * 40
    monkeypatch.setattr(
        refresh_pins,
        "_github_get",
        lambda *_a, **_k: {
            "default_branch": "master",
            "object": {"sha": new_sha},
        },
    )

    refresh_pins.update_shas(catalog, gh_token="t")
    text = catalog.read_text()
    # The fixture has a top-level `# heretek marketplace — source of truth.` comment;
    # ruamel.yaml must preserve it.
    assert "# heretek marketplace" in text or "# source of truth" in text


def test_update_shas_rejects_non_dict_root(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Regression for #157: update_shas rejects non-dict catalog.yaml root with ValueError.

    ruamel.yaml round-trip loads a YAML list as a Python list. Without the
    isinstance(data, dict) guard, the next line (`data.get("plugins", [])`)
    would raise AttributeError on a list — surfacing malformed catalogs with
    a confusing error. The guard promotes this to a clear ValueError.
    """
    catalog = tmp_path / "catalog.yaml"
    # Root is a YAML list, not a mapping.
    catalog.write_text("- one\n- two\n")

    # Patch _github_get to a no-op so the test stays hermetic if the guard
    # ever regresses and the code falls through to the SHA-write loop.
    monkeypatch.setattr(refresh_pins, "_github_get", lambda *_a, **_k: {})

    with pytest.raises(ValueError, match="catalog.yaml root must be a dict"):
        refresh_pins.update_shas(catalog, gh_token="fake")


# ---------------------------------------------------------------------------
# Issue #164 — HTTP response body-size guard
# ---------------------------------------------------------------------------


def test_github_get_rejects_huge_content_length(monkeypatch: pytest.MonkeyPatch) -> None:
    """Issue #164: Content-Length > 50 MB on a /repos API call is swallowed as
    `{}` (matches `_github_get`'s existing uniform fault-tolerance — any
    `Exception` inside the `try` returns `{}`). Without the guard, the
    mock's `.json()` would be called and a `MagicMock` returned — so this
    test discriminates against a regression that drops the `check_content_length`
    call."""
    import requests as _requests

    huge = MagicMock()
    huge.headers = {"Content-Length": "99999999999"}
    huge.status_code = 200  # explicitly 200, so origin/main falls into .json()
    huge.json.return_value = {"would_have_been": "leaked"}
    monkeypatch.setattr(_requests, "get", lambda *_a, **_k: huge)
    assert refresh_pins._github_get("/repos/foo/releases/latest", gh_token="fake") == {}
