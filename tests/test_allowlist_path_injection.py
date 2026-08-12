"""Tests for the path-injection hardening introduced by issue #93.

`scripts/refresh_pins.py:update_shas` builds GitHub API URLs from
catalog-controlled `upstream` + `default_branch` strings without any
validation. An attacker controlling an upstream's `default_branch` field
(typo-squat or transfer) can redirect catalog SHAs to arbitrary refs.

This file enforces the allowlist at every URL/ref construction site.
"""

import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "scripts"))

import refresh_pins


def test_update_shas_rejects_evil_upstream(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """`upstream` containing path-traversal or shell metacharacters is rejected
    with ValueError before any GitHub call is made (closes #93 path #1)."""
    catalog = tmp_path / "catalog.yaml"
    catalog.write_text(
        "plugins:\n"
        "  - name: evil\n"
        "    items:\n"
        "      - id: foo\n"
        "        upstream: '../etc/passwd'\n"
        "        sha: 0123456789abcdef0123456789abcdef01234567\n"
        "        vetting: {}\n"
    )

    called = {"n": 0}

    def fake_github_get(_path: str, _token: str) -> dict:
        called["n"] += 1
        return {}

    monkeypatch.setattr(refresh_pins, "_github_get", fake_github_get)

    with pytest.raises(ValueError, match="upstream"):
        refresh_pins.update_shas(catalog, gh_token="t")
    assert called["n"] == 0, "github_get must not be called for invalid upstream"


def test_update_shas_rejects_evil_default_branch(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """`default_branch` containing path-traversal is rejected (closes #93 path #2)."""
    catalog = tmp_path / "catalog.yaml"
    catalog.write_text(
        "plugins:\n"
        "  - name: p\n"
        "    items:\n"
        "      - id: foo\n"
        "        upstream: rust-lang/rust-analyzer\n"
        "        sha: 0123456789abcdef0123456789abcdef01234567\n"
        "        vetting: {}\n"
    )

    monkeypatch.setattr(
        refresh_pins,
        "_github_get",
        lambda _path, _tok: {
            "default_branch": "../../etc/passwd",
            "object": {"sha": "deadbeef" * 5},
        },
    )

    with pytest.raises(ValueError, match="default_branch"):
        refresh_pins.update_shas(catalog, gh_token="t")


def test_update_shas_accepts_well_formed_upstream(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Normal upstream + default_branch flow through unchanged."""
    catalog = tmp_path / "catalog.yaml"
    catalog.write_text(
        "plugins:\n"
        "  - name: p\n"
        "    items:\n"
        "      - id: foo\n"
        "        upstream: rust-lang/rust-analyzer\n"
        "        sha: 0123456789abcdef0123456789abcdef01234567\n"
        "        vetting: {}\n"
    )

    new_sha = "a" * 40
    monkeypatch.setattr(
        refresh_pins,
        "_github_get",
        lambda path, _tok: (
            {"default_branch": "main"}
            if path.endswith("/rust-lang/rust-analyzer")
            else {"target_commitish": new_sha, "tag_name": "v1.0.0"}
            if path.endswith("/releases/latest")
            else {}
        ),
    )

    updates = refresh_pins.update_shas(catalog, gh_token="t")
    assert updates == [("foo", "0123456789abcdef0123456789abcdef01234567", new_sha)]
