"""RLM fast-gate spike (#42) — minimal REPL + recursive LM scaffold.

This is research code, not production. Per the spike protocol, it runs on
a 50-edit corpus and measures precision/recall/latency vs #43 AST-grep.

The scaffold:
1. Receives an Edit payload (file_path + new_string) via stdin (JSON)
2. Spawns a Python REPL pre-loaded with the edit content as a variable
3. Calls a base LM to recursively inspect the edit (find deprecated APIs)
4. Returns a verdict: "deprecated" | "clean"

Per the spike protocol, this is opt-in via env var ENABLE_RLM_SPIKE=1.
"""

from __future__ import annotations

import json
import os
import sys
import time


def main() -> int:  # nosonar — false positive: hook-script entrypoint always returns 0
    if os.environ.get("ENABLE_RLM_SPIKE") != "1":
        return 0

    try:
        payload = json.loads(sys.stdin.read())
    except json.JSONDecodeError:
        return 0

    tool_input = payload.get("tool_input", {})
    _file_path = tool_input.get("file_path", "")
    _new_string = tool_input.get("new_string", "")

    start = time.time()
    # Minimal REPL: just print the edit content + a stub verdict for the spike.
    # Real recursive-LM logic lives in a follow-up commit; this is the scaffolding.
    verdict = "clean"
    latency_ms = (time.time() - start) * 1000

    print(
        json.dumps(
            {
                "hookSpecificOutput": {
                    "hookEventName": "PostToolUse",
                    "additionalContext": f"rlm-spike: verdict={verdict} latency={latency_ms:.0f}ms (stub)",
                }
            }
        )
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
