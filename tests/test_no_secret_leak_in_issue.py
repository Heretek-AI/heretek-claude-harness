"""Verify that rendered comparison Markdown does not leak tokens.

This is the safety net: if a future change causes a token-shaped string
to appear in the issue body, this test fails before the issue is opened.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from comparison_report import (
    compute_diff,
    load_summary,
    render_markdown,
    render_with_secret_check,
    scan_for_secrets,
)


def test_scan_for_secrets_detects_sk_cp() -> None:
    # Low-entropy placeholder (matches our regex, skips gitleaks entropy heuristic).
    md = "Anthropic API key: sk-cp-aaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
    hits = scan_for_secrets(md)
    assert any("sk-cp-" in h for h in hits), f"expected sk-cp hit, got {hits}"


def test_scan_for_secrets_detects_ghp() -> None:
    # Low-entropy placeholder (matches our regex, skips gitleaks entropy heuristic).
    md = "GitHub PAT: ghp_aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
    hits = scan_for_secrets(md)
    assert any("ghp_" in h for h in hits), f"expected ghp_ hit, got {hits}"


def test_scan_for_secrets_clean_text() -> None:
    md = "All tests passed. Pass rate: 62.5%."
    hits = scan_for_secrets(md)
    assert hits == []


def test_render_with_secret_aborts() -> None:
    """A fixture that contains a token in a task_id must abort the render."""
    fixture_root = (
        Path(__file__).resolve().parent
        / "fixtures"
        / "terminal_bench_ab"
        / "case-task-id-with-secret"
    )
    a = load_summary(fixture_root / "agent-a" / "summary.json")
    b = load_summary(fixture_root / "agent-b" / "summary.json")
    diff = compute_diff(a, b)
    md = render_markdown(
        a,
        b,
        diff,
        {
            "commit_sha_short": "0000000",
            "trigger": "push",
            "actor": "test",
            "tier": "quick",
            "model": "m",
            "base_url": "u",
        },
    )
    with pytest.raises(RuntimeError, match="secret"):
        render_with_secret_check(md)
