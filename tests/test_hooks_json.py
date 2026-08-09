"""Verify hooks.json is valid JSON and contains the expected telemetry entry."""

from __future__ import annotations

import json
from pathlib import Path

PLUGIN_ROOT = Path(__file__).parent.parent
HOOKS_JSON = PLUGIN_ROOT / "plugins" / "hooks" / "hooks" / "hooks.json"


def test_hooks_json_parses() -> None:
    data = json.loads(HOOKS_JSON.read_text())
    assert "hooks" in data


def test_collector_entry_in_pre_tool_use() -> None:
    data = json.loads(HOOKS_JSON.read_text())
    pre = data["hooks"]["PreToolUse"]
    collector_entries = [
        entry
        for entry in pre
        if any(
            "telemetry_collector.py" in h.get("command", "")
            for h in entry.get("hooks", [])
        )
    ]
    assert len(collector_entries) == 1
    assert collector_entries[0]["matcher"] == "Edit|Write|MultiEdit|Read|Bash"
    hook = collector_entries[0]["hooks"][0]
    assert hook["async"] is True
    assert hook["timeout"] == 200


def test_collector_entry_in_post_tool_use() -> None:
    data = json.loads(HOOKS_JSON.read_text())
    post = data["hooks"]["PostToolUse"]
    collector_entries = [
        entry
        for entry in post
        if any(
            "telemetry_collector.py" in h.get("command", "")
            for h in entry.get("hooks", [])
        )
    ]
    assert len(collector_entries) == 1


def test_existing_hooks_preserved() -> None:
    data = json.loads(HOOKS_JSON.read_text())
    pre_commands = [
        h["command"]
        for entry in data["hooks"]["PreToolUse"]
        for h in entry.get("hooks", [])
    ]
    assert any("fast_gate.py" in c for c in pre_commands)
    post_commands = [
        h["command"]
        for entry in data["hooks"]["PostToolUse"]
        for h in entry.get("hooks", [])
    ]
    for expected in [
        "stale_dep_intercept.py",
        "forbidden_pattern_scanner.py",
        "drift_detector.py",
        "lookup_gate.py",
    ]:
        assert any(expected in c for c in post_commands), f"missing {expected}"
