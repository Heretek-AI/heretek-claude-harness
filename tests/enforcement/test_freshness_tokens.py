"""Tests for freshness_tokens.py (#46)."""

from datetime import datetime, timezone
from pathlib import Path

import pytest

from scripts.freshness_tokens import render, _format_token_line


def test_render_includes_tracked_libs():
    """#46: render() emits one line per tracked lib."""
    if not list(Path("catalog/freshness").glob("*.yaml")):
        pytest.skip("populate catalog/freshness/ first")

    # qwen3.6-27b profile has mandatory_lookup populated (claude-opus-4 is off by default).
    output = render("qwen3.6-27b")
    # At minimum, requests and pyyaml should be tracked
    assert "requests" in output or "pyyaml" in output
    assert "TTL" in output
    assert "Refreshed" in output


def test_render_handles_missing_profile_gracefully():
    """#46: render() with unknown profile uses defaults."""
    output = render("nonexistent-model-xyz")
    assert "TTL" in output
    assert "default" in output.lower() or "24h" in output


def test_format_token_line_includes_metadata():
    """#46: token line has lib, version, fetched date, refresh hint."""
    fetched_at = datetime(2026, 8, 6, 12, 0, tzinfo=timezone.utc)
    line = _format_token_line("requests", "2.34.0", fetched_at, ttl_hours=24)
    assert "requests" in line
    assert "2.34.0" in line
    assert "2026-08-06" in line
    assert "24" in line
