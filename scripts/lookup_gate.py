"""Lookup-gate hook (#45) — D15 async PostToolUse.

When an Edit touches a library in the active model's `mandatory_lookup`
list, checks if a freshness-index consult happened recently. If not,
emits a warning via additionalContext. Per spec §2: async-with-warning
(non-blocking; the agent receives context for the next turn).

D15 compliance: this lives in the hooks plugin only.
"""
from __future__ import annotations

import json
import os
import re
import sys
import time
from pathlib import Path

# Allow `python scripts/lookup_gate.py` to find the sibling `scripts` package.
_SCRIPTS_PARENT = str(Path(__file__).resolve().parent.parent)
if _SCRIPTS_PARENT not in sys.path:
    sys.path.insert(0, _SCRIPTS_PARENT)

from scripts.model_profile_loader import load_profile, resolve_active_model_id

CACHE_DIR = Path(__file__).resolve().parent.parent / "catalog" / "freshness"
SENTINEL_FILE = Path.cwd() / ".heretek" / "last_lookup.json"
# Default freshness TTL if not in profile
DEFAULT_TTL_HOURS = 24
# Pattern for `name==X.Y.Z` or similar pins
PIN_RE = re.compile(r"^\s*([a-zA-Z0-9_.+-]+)\s*([=<>~!]=)\s*([0-9][^,;\s]*)", re.MULTILINE)


def _tracked_libs_for_active_model() -> set[str]:
    try:
        profile = load_profile(resolve_active_model_id())
    except FileNotFoundError:
        return set()
    return set(profile.get("mandatory_lookup", []))


def _libs_in_content(content: str) -> set[str]:
    libs = set()
    for match in PIN_RE.finditer(content):
        libs.add(match.group(1).lower().replace(".", "-"))
    return libs


def _last_lookup_age_hours() -> float:
    if not SENTINEL_FILE.exists():
        return float("inf")  # never consulted
    try:
        data = json.loads(SENTINEL_FILE.read_text())
    except json.JSONDecodeError:
        return float("inf")
    last = data.get("last_lookup_at", 0)
    return (time.time() - last) / 3600.0


def main() -> int:
    try:
        payload = json.loads(sys.stdin.read())
    except json.JSONDecodeError:
        return 0

    tool_input = payload.get("tool_input", {})
    new_content = tool_input.get("new_string", "")
    if not new_content:
        return 0

    tracked = _tracked_libs_for_active_model()
    edited_libs = _libs_in_content(new_content)
    relevant = tracked & edited_libs

    if not relevant:
        return 0

    try:
        profile = load_profile(resolve_active_model_id())
        ttl = profile.get("freshness_token_ttl_hours", DEFAULT_TTL_HOURS)
    except FileNotFoundError:
        ttl = DEFAULT_TTL_HOURS

    age_hours = _last_lookup_age_hours()
    if age_hours <= ttl:
        return 0  # recent enough

    libs_str = ", ".join(sorted(relevant))
    print(json.dumps({
        "hookSpecificOutput": {
            "hookEventName": "PostToolUse",
            "additionalContext": (
                f"⚠️  lookup-gate: edit touches tracked lib(s) {libs_str}, but the "
                f"freshness index was last consulted {age_hours:.0f}h ago (TTL: {ttl}h). "
                f"Run `python -m scripts.freshness_index --lib <name>` before continuing."
            ),
        }
    }))
    return 0


if __name__ == "__main__":
    sys.exit(main())