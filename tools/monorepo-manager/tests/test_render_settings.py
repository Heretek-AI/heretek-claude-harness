"""Tests for the .claude/settings.json renderer."""

from __future__ import annotations

import json

from scripts.lib.render_settings import render_settings


def test_render_settings_returns_settings_and_lockfile():
    files = render_settings("python")
    assert ".claude/settings.json" in files
    assert ".claude/hooks/.lockfile" in files


def test_render_settings_is_valid_json():
    files = render_settings("python")
    parsed = json.loads(files[".claude/settings.json"])
    assert "permissions" in parsed
    assert "rm -rf" in "\n".join(parsed["permissions"]["deny"])


def test_render_settings_lockfile_is_hex():
    files = render_settings("python")
    lockfile = files[".claude/hooks/.lockfile"]
    assert len(lockfile.strip()) == 64
    int(lockfile.strip(), 16)
