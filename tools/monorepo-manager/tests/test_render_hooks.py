"""Tests for the hooks renderer."""

from __future__ import annotations

import pytest

from scripts.lib.render_hooks import render_hooks


def test_render_hooks_python_returns_three_files():
    files = render_hooks("python")
    assert ".claude/hooks/PreToolUse/deny-destructive.sh" in files
    assert ".claude/hooks/PostToolUse/run-pre-commit.sh" in files
    assert ".claude/hooks/Stop/verify-lint.sh" in files


def test_render_hooks_python_stop_uses_ruff():
    files = render_hooks("python")
    assert "ruff check" in files[".claude/hooks/Stop/verify-lint.sh"]


def test_render_hooks_node_stop_uses_eslint():
    files = render_hooks("node")
    assert "eslint" in files[".claude/hooks/Stop/verify-lint.sh"]


def test_render_hooks_rejects_unknown_stack():
    with pytest.raises(ValueError):
        render_hooks("ruby")
