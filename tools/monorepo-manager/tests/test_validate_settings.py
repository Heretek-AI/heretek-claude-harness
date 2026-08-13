"""Tests for .claude/settings.json contract validation."""

from __future__ import annotations

import json
import pathlib

from scripts.lib.validate_settings import validate_settings


def _write(tmp_path: pathlib.Path, data: dict) -> str:
    p = tmp_path / "settings.json"
    p.write_text(json.dumps(data))
    return str(p)


def _valid() -> dict:
    return {
        "model": "sonnet",
        "permissions": {
            "allow": ["Bash(pytest:*)"],
            "deny": [
                "Bash(rm -rf:*)",
                "Bash(git push --force:*)",
                "Bash(git reset --hard:*)",
            ],
        },
        "hooks": {
            "PreToolUse": [{"matcher": "Bash", "hooks": [{"type": "command", "command": "true"}]}],
            "PostToolUse": [],
            "Stop": [{"matcher": "*", "hooks": [{"type": "command", "command": "true"}]}],
        },
    }


def test_validate_settings_accepts_well_formed(tmp_path):
    assert validate_settings(_write(tmp_path, _valid())) == []


def test_validate_settings_rejects_empty_allow(tmp_path):
    data = _valid()
    data["permissions"]["allow"] = []
    v = validate_settings(_write(tmp_path, data))
    assert any("allow" in s for s in v)


def test_validate_settings_rejects_missing_pre_tool_use(tmp_path):
    data = _valid()
    del data["hooks"]["PreToolUse"]
    v = validate_settings(_write(tmp_path, data))
    assert any("PreToolUse" in s for s in v)


def test_validate_settings_rejects_destructive_pattern_not_in_deny(tmp_path):
    data = _valid()
    data["permissions"]["deny"] = []
    v = validate_settings(_write(tmp_path, data))
    assert any("destructive" in s for s in v)
