"""PostToolUse multiplexer for the heretek hooks plugin.

Reads a Claude Code hook payload from stdin, dispatches to the async
PostToolUse analyzers (stale_dep_intercept, forbidden_pattern_scanner,
drift_detector, lookup_gate, telemetry_collector), gathers their
`additionalContext` JSON outputs, and emits one consolidated envelope.

Replaces the original 5 separate PostToolUse hook entries in
hooks.json with a single dispatcher entry. Cuts hook-process startup
from 5x to 1x per Edit/Write.

Each child is subprocessed with the same stdin payload, with a per-child
timeout. A child timeout or crash is logged to stderr and skipped — the
dispatcher never blocks on a single analyzer.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

# Per-child timeout (seconds). Aggregated across all 4-5 children below
# 2s total — the dispatcher's hook timeout is 2000ms.
CHILD_TIMEOUT_S = 0.4

# Repo root for resolving child script paths. The dispatcher lives at
# plugins/hooks/scripts/post_tool_dispatcher.py — parents[3] = repo root.
_REPO_ROOT = Path(__file__).resolve().parents[3]

# Child scripts (relative to repo root). Order doesn't matter.
CHILDREN: list[str] = [
    "plugins/hooks/scripts/stale_dep_intercept.py",
    "plugins/hooks/scripts/forbidden_pattern_scanner.py",
    "plugins/hooks/scripts/drift_detector.py",
    "plugins/hooks/scripts/lookup_gate.py",
    "plugins/hooks/scripts/telemetry_collector.py",
]

# Children whose stdout we parse as JSON envelopes. telemetry_collector
# writes to the telemetry directory and exits silently — it must NOT be
# in PARSE_JSON_CHILDREN or we'll choke on empty stdout.
PARSE_JSON_CHILDREN: set[str] = {
    "plugins/hooks/scripts/stale_dep_intercept.py",
    "plugins/hooks/scripts/forbidden_pattern_scanner.py",
    "plugins/hooks/scripts/drift_detector.py",
    "plugins/hooks/scripts/lookup_gate.py",
}


def _read_payload() -> dict:
    """Read the Claude Code hook payload from stdin. Empty dict on EOF."""
    raw = sys.stdin.read()
    if not raw.strip():
        return {}
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return {}


def _run_child(script_path: str, payload_text: str) -> tuple[int, str, str]:
    """Run one child script with the payload; return (rc, stdout, stderr)."""
    try:
        proc = subprocess.run(
            [sys.executable, str(_REPO_ROOT / script_path)],
            input=payload_text,
            capture_output=True,
            text=True,
            timeout=CHILD_TIMEOUT_S,
            check=False,
            env={**os.environ, "PYTHONPATH": str(_REPO_ROOT)},
        )
    except subprocess.TimeoutExpired:
        return (-1, "", f"timeout after {CHILD_TIMEOUT_S}s")
    except FileNotFoundError:
        return (-2, "", f"script not found: {script_path}")
    return (proc.returncode, proc.stdout, proc.stderr)


def _collect_warnings(stdout: str) -> list[str]:
    """Pull the `additionalContext` string out of a child's JSON envelope.

    Returns [] if the child emitted no JSON or no additionalContext.
    Children that don't emit JSON (e.g. telemetry_collector) return [].
    """
    if not stdout.strip():
        return []
    try:
        envelope = json.loads(stdout)
    except json.JSONDecodeError:
        return []
    output = envelope.get("hookSpecificOutput") or {}
    context = output.get("additionalContext")
    if not context:
        return []
    return [line for line in context.splitlines() if line.strip()]


def main() -> int:  # nosonar — egress aggregator; always exits 0
    payload = _read_payload()
    payload_text = json.dumps(payload) if payload else ""

    all_warnings: list[str] = []
    for script in CHILDREN:
        rc, stdout, stderr = _run_child(script, payload_text)
        if stderr.strip():
            print(f"post_tool_dispatcher: {script}: {stderr}", file=sys.stderr)
        if script in PARSE_JSON_CHILDREN:
            all_warnings.extend(_collect_warnings(stdout))

    if all_warnings:
        print(
            json.dumps(
                {
                    "hookSpecificOutput": {
                        "hookEventName": "PostToolUse",
                        "additionalContext": "\n".join(all_warnings),
                    }
                }
            )
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
