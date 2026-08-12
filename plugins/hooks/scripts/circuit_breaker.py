"""Circuit Breaker PostToolUse interceptor script.

Tracks consecutive tool execution failures in local temporary state.
If failures exceed threshold (e.g. 5 consecutive errors), returns a warning
urging human intervention or strategy pivot.
"""

from __future__ import annotations

import contextlib
import json
import sys
from pathlib import Path

STATE_FILE = Path("/tmp/heretek_circuit_breaker.json")
MAX_CONSECUTIVE_ERRORS = 5


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except Exception:
        return 0

    tool_result = payload.get("tool_result", {})
    is_error = tool_result.get("is_error", False) or payload.get("is_error", False)

    state = {"consecutive_errors": 0}
    if STATE_FILE.is_file():
        with contextlib.suppress(Exception):
            state = json.loads(STATE_FILE.read_text())

    if is_error:
        state["consecutive_errors"] = state.get("consecutive_errors", 0) + 1
    else:
        state["consecutive_errors"] = 0

    STATE_FILE.write_text(json.dumps(state))

    if state["consecutive_errors"] >= MAX_CONSECUTIVE_ERRORS:
        output = {
            "decision": "block",
            "reason": (
                f"Circuit Breaker Triggered: {state['consecutive_errors']} consecutive tool execution failures. "
                "Halt speculative retries, re-read logs, and analyze root cause before proceeding."
            ),
        }
        print(json.dumps(output))
        return 0

    return 0


if __name__ == "__main__":
    sys.exit(main())
