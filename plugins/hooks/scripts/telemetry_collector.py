"""Layer-1 hook event collector for the heretek telemetry pipeline.

Reads a Claude Code hook payload from stdin, captures a one-line JSONL
record to ~/.heretek/telemetry/sessions/<YYYY-MM-DD>/session-<uuid>.jsonl,
and validates the emit against tests/fixtures/telemetry_schema.json.

Exit codes:
- 0: success OR fail-open (drop event on disk full, schema failure, write error)

The script is observability, never enforcement. It never blocks tool calls.
Async-friendly: hook manifest declares `async: true` so this never gates the
agent loop.
"""

from __future__ import annotations

import json
import os
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import jsonschema

TELEMETRY_ROOT = Path(
    os.environ.get("HERETEK_TELEMETRY_ROOT", Path.home() / ".heretek" / "telemetry")
)
SCHEMA_PATH = (
    Path(__file__).parent.parent.parent.parent
    / "tests"
    / "fixtures"
    / "telemetry_schema.json"
)


def _load_schema() -> dict:
    return json.loads(SCHEMA_PATH.read_text())


def redact_path(path: str | None, home: str | None = None) -> str | None:
    """Strip user home dir from a path. /home/john/foo.py -> ~/foo.py.

    Always-on unless explicitly disabled via config (out of scope for v1).
    """
    if path is None or path == "":
        return path
    home_path = Path(home or os.environ.get("HOME", str(Path.home())))
    home_str = str(home_path)
    if path.startswith(home_str + "/"):
        return "~/" + path[len(home_str) + 1 :]
    if path == home_str:
        return "~"
    return path


def parse_payload(payload_text: str) -> dict[str, Any]:
    """Parse a Claude Code hook payload. Raises ValueError on malformed input.

    Returns: {session_id, event_type, tool_name, tool_input, hook_latency_ms,
              hook_exit_code, hook_stderr, matcher_matched, plugin_root}
    All fields that may be absent from the payload are typed Optional / default.
    """
    try:
        payload = json.loads(payload_text)
    except json.JSONDecodeError as exc:
        raise ValueError(f"payload is not valid JSON: {exc}") from exc
    if not isinstance(payload, dict):
        raise ValueError(f"payload is not a JSON object: {type(payload).__name__}")
    return payload


def _now_iso() -> str:
    now = datetime.now(timezone.utc)
    return now.strftime("%Y-%m-%dT%H:%M:%S.") + f"{now.microsecond // 1000:03d}Z"


def _session_id(payload: dict[str, Any]) -> str:
    return str(
        payload.get("session_id") or os.environ.get("CLAUDE_SESSION_ID") or uuid.uuid4()
    )


def emit_event(
    session_dir: Path, event: dict[str, Any], schema: dict[str, Any] | None = None
) -> bool:
    """Append one JSONL line to session_dir/session-<id>.jsonl.

    Validates against schema. Returns True on success, False on any failure
    (fail-open semantics). Never raises.
    """
    schema = schema if schema is not None else _load_schema()
    session_id = event.get("session_id") or str(uuid.uuid4())
    event.setdefault("session_id", session_id)
    event.setdefault("ts", _now_iso())
    event.setdefault("schema_version", 1)
    try:
        jsonschema.validate(event, schema)
    except jsonschema.ValidationError as exc:
        print(
            f"telemetry_collector: schema validation failed: {exc.message}",
            file=sys.stderr,
        )
        return False
    session_file = session_dir / f"session-{event['session_id']}.jsonl"
    try:
        session_file.parent.mkdir(parents=True, exist_ok=True)
        with session_file.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(event, separators=(",", ":")) + "\n")
    except OSError as exc:
        print(
            f"telemetry_collector: write failed ({exc}); dropping event",
            file=sys.stderr,
        )
        return False
    return True


def _build_event(payload: dict[str, Any], home: str | None = None) -> dict[str, Any]:
    tool_input = payload.get("tool_input") or {}
    if not isinstance(tool_input, dict):
        tool_input = {}
    raw_path = tool_input.get("file_path")
    return {
        "session_id": _session_id(payload),
        "event_type": payload.get("event_type")
        or payload.get("hook_event_name")
        or "PostToolUse",
        "tool_name": payload.get("tool_name") or "?",
        "tool_input_path": redact_path(raw_path, home=home),
        "hook_decision": payload.get("hook_decision") or _derive_decision(payload),
        "hook_latency_ms": payload.get("hook_latency_ms"),
        "hook_exit_code": int(payload.get("hook_exit_code", 0)),
        "hook_stderr_summary": (payload.get("hook_stderr") or "")[:256] or None,
        "matcher_matched": bool(payload.get("matcher_matched", True)),
        "plugin_root": str(
            payload.get("plugin_root") or os.environ.get("CLAUDE_PLUGIN_ROOT", "")
        ),
        "schema_version": 1,
    }


def _derive_decision(payload: dict[str, Any]) -> str:
    exit_code = int(payload.get("hook_exit_code", 0))
    if exit_code == 2:
        return "block"
    stderr = (payload.get("hook_stderr") or "").lower()
    if "warn" in stderr:
        return "warn"
    return "allow"


def main() -> int:
    payload_text = sys.stdin.read()
    try:
        payload = parse_payload(payload_text)
    except ValueError as exc:
        print(f"telemetry_collector: {exc}", file=sys.stderr)
        return 0  # fail-open
    try:
        event = _build_event(payload)
    except Exception as exc:  # noqa: BLE001 — fail-open
        print(f"telemetry_collector: build_event failed: {exc}", file=sys.stderr)
        return 0
    emit_event(TELEMETRY_ROOT / "sessions", event)
    return 0


if __name__ == "__main__":
    sys.exit(main())
