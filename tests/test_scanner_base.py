"""Tests for the ScannerReport contract — frozen, fields, defaults."""
from __future__ import annotations

import pytest

from scripts.scanners.base import Finding, ScannerReport, Severity


def test_scanner_report_default_severity_is_clean() -> None:
    r = ScannerReport(item_id="x", scanner="test")
    assert r.severity == "clean"
    assert r.findings == []
    assert r.raw == {}


def test_scanner_report_is_frozen() -> None:
    r = ScannerReport(item_id="x", scanner="test")
    with pytest.raises(Exception):
        r.severity = "block"  # type: ignore[misc]


def test_finding_minimal_fields() -> None:
    f = Finding(path="SKILL.md", line=42, message="prompt injection pattern")
    assert f.rule_id is None
    assert f.cve_id is None


def test_severity_literal_includes_block() -> None:
    # compile-time check the Literal is what downstream code expects
    s: Severity = "block"
    assert s == "block"