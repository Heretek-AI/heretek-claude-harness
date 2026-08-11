"""Verify hooks.json is valid JSON and contains the expected hook entries.

Architecture (post-PR4): telemetry collector fires once on PreToolUse
(matches Edit/Write/MultiEdit/Read/Bash). PostToolUse is collapsed to
a single dispatcher (post_tool_dispatcher.py) that fans out to the
4 async analyzers (stale_dep_intercept, forbidden_pattern_scanner,
drift_detector, lookup_gate). secrets_pre_tool.py gates PreToolUse.
"""

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
        if any("telemetry_collector.py" in h.get("command", "") for h in entry.get("hooks", []))
    ]
    assert len(collector_entries) == 1
    assert collector_entries[0]["matcher"] == "Edit|Write|MultiEdit|Read|Bash"
    hook = collector_entries[0]["hooks"][0]
    assert hook["async"] is True
    assert hook["timeout"] == 200


def test_collector_not_in_post_tool_use() -> None:
    """PostToolUse telemetry was removed in PR4 (dispatcher handles fan-out).

    The dispatcher subprocesses telemetry_collector itself; the hooks.json
    PostToolUse entry is now ONLY the dispatcher.
    """
    data = json.loads(HOOKS_JSON.read_text())
    post = data["hooks"]["PostToolUse"]
    for entry in post:
        for h in entry.get("hooks", []):
            assert "telemetry_collector.py" not in h.get("command", ""), (
                "telemetry_collector must not be a top-level PostToolUse entry; "
                "dispatcher subprocesses it"
            )


def test_secrets_pre_tool_in_pre_tool_use() -> None:
    """PR4: secrets_pre_tool.py is a new PreToolUse gate on Edit/Write/MultiEdit."""
    data = json.loads(HOOKS_JSON.read_text())
    pre = data["hooks"]["PreToolUse"]
    secrets_entries = [
        entry
        for entry in pre
        if any("secrets_pre_tool.py" in h.get("command", "") for h in entry.get("hooks", []))
    ]
    assert len(secrets_entries) == 1
    assert secrets_entries[0]["matcher"] == "Edit|Write|MultiEdit"


def test_dispatcher_collapsed_post_tool_use() -> None:
    """PostToolUse = 1 dispatcher entry; not the 4 individual analyzers."""
    data = json.loads(HOOKS_JSON.read_text())
    post = data["hooks"]["PostToolUse"]
    assert len(post) == 1, f"expected 1 PostToolUse entry, got {len(post)}"
    cmd = post[0]["hooks"][0]["command"]
    assert "post_tool_dispatcher.py" in cmd


def test_existing_hooks_preserved() -> None:
    data = json.loads(HOOKS_JSON.read_text())
    pre_commands = [
        h["command"] for entry in data["hooks"]["PreToolUse"] for h in entry.get("hooks", [])
    ]
    assert any("fast_gate.py" in c for c in pre_commands)
    assert any("secrets_pre_tool.py" in c for c in pre_commands)
    assert any("telemetry_collector.py" in c for c in pre_commands)
    post_commands = [
        h["command"] for entry in data["hooks"]["PostToolUse"] for h in entry.get("hooks", [])
    ]
    # Dispatcher fans out to the 4 analyzers (verify they are referenced
    # inside the dispatcher module, not in hooks.json directly).
    assert any("post_tool_dispatcher.py" in c for c in post_commands)
