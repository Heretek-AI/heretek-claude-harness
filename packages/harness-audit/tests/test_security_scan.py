"""Unit tests for agent security guard and secret scanner."""

from __future__ import annotations

from pathlib import Path

from security_scan import scan_directory, scan_text_content


def test_scan_text_content_clean() -> None:
    """Clean code emits zero violations."""
    violations = scan_text_content("def add(a, b):\n    return a + b\n")
    assert violations == []


def test_scan_text_content_secret_leak() -> None:
    """Secret scanner detects Anthropic API key pattern."""
    code = 'API_KEY = "sk-ant-api03-123456789012345678901234567890"'
    violations = scan_text_content(code)
    assert len(violations) == 1
    assert violations[0]["type"] == "hardcoded_secret"
    assert violations[0]["category"] == "Anthropic API Key"


def test_scan_directory_finds_violations(tmp_path: Path) -> None:
    """Directory scanner detects secret in file."""
    bad_file = tmp_path / "config.py"
    bad_file.write_text('TOKEN = "ghp_123456789012345678901234567890123456"')
    violations = scan_directory(tmp_path)
    assert len(violations) == 1
    assert violations[0]["category"] == "GitHub Personal Access Token"
