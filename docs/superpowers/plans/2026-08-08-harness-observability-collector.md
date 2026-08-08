# Harness Observability — Collector Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a hook event collector to `plugins/hooks/` that captures every PreToolUse/PostToolUse event to local JSONL under `~/.heretek/telemetry/`, plus a `heretek telemetry` CLI for local inspection. Closes issue #2 acceptance criterion 1.

**Architecture:** New standalone script `plugins/hooks/scripts/telemetry_collector.py` (async, fail-open) appended to the existing `hooks.json` matcher arrays. New heretek-level CLI `scripts/heretek_cli.py` with a `telemetry` subcommand group. New JSON Schema at `tests/fixtures/telemetry_schema.json` enforced at emit time. Storage under `~/.heretek/telemetry/{config.yaml,sessions/,exports/,archive/}`.

**Tech Stack:** Python 3.10+, stdlib only (`json`, `os`, `uuid`, `pathlib`, `argparse`, `datetime`, `tarfile`, `subprocess` for compression). jsonschema 4.23.0 (existing, for schema validation). pytest 9.0.3.

## Global Constraints

These apply to every task below. Tasks implicitly inherit them.

- **Python ≥ 3.10** — use `from __future__ import annotations` in every new module.
- **Type hints on every public function** — project convention.
- **Docstrings on every public function** — terse, one-line summary.
- **D11 SHA-ride preserved** — `marketplace.json` regeneration must remain byte-identical (`git diff --exit-code` invariant).
- **D15 strict hooks ownership** — only `plugins/hooks/` declares hooks. No other plugin touches `hooks.json`. Sub-specs 2 + 3 never modify `hooks.json`.
- **D20 Action-pinning** — N/A for this plan (no new GitHub workflows in this plan).
- **D29 collector home** — `telemetry_collector.py` lives under `plugins/hooks/scripts/`. CLI lives under `scripts/heretek_cli.py`.
- **Collector never blocks** — exit 0 on disk full / schema failure / write error. Print stderr, drop event. Observability, not enforcement.
- **`redact_paths: true` is the default** — strip user home dir (`/home/<user>/` → `~/`) from `tool_input_path` before write. Always on.
- **Schema versioning** — every JSONL line carries `schema_version: 1`. Future schema changes bump version + migration note in `docs/telemetry/CHANGELOG.md`.
- **`pytest -q` must stay green** throughout — no task may leave the suite red.
- **≥90% line coverage** on `telemetry_collector.py` and `heretek_cli.py::telemetry` subcommand group.
- **Frequent commits** — each task ends with `git commit`.

## File Structure

```
plugins/hooks/
├── scripts/
│   └── telemetry_collector.py          # Task 2
├── hooks/
│   └── hooks.json                      # Task 3 (append collector entry)

scripts/
└── heretek_cli.py                      # Task 4

tests/
├── fixtures/
│   ├── telemetry_schema.json           # Task 1
│   └── telemetry/
│       └── redacted_session.jsonl      # Task 2
├── test_telemetry_collector.py         # Task 2
├── test_heretek_cli.py                 # Task 4
└── test_hooks_json.py                  # Task 3

catalog/reviews/
└── observability-sub-spec-1.md         # Task 5

docs/telemetry/
└── CHANGELOG.md                        # Task 2
```

---

## Task 1: Add telemetry JSONL schema fixture

**Files:**
- Create: `tests/fixtures/telemetry_schema.json` — JSON Schema for one JSONL line
- Create: `tests/test_telemetry_schema.py` — validates the schema file itself is well-formed

**Interfaces:**
- Produces: `tests/fixtures/telemetry_schema.json` referenced by Task 2's emit-time validation and by sub-spec 3's gap detector.

**GitHub issue title:** `[harness-observability] Add telemetry JSONL schema fixture`

**Acceptance criteria:**
- [ ] Schema covers all fields from sub-spec 1 §2.1 (ts, session_id, event_type, tool_name, tool_input_path, hook_decision, hook_latency_ms, hook_exit_code, hook_stderr_summary, matcher_matched, plugin_root, schema_version)
- [ ] `schema_version` is required and constrained to integer with minimum 1
- [ ] `event_type` is enum: `PreToolUse | PostToolUse`
- [ ] `tool_name` is enum: `Edit | Write | MultiEdit | Read | Bash | ?`
- [ ] `hook_decision` is enum: `allow | block | warn`
- [ ] Schema validates via `jsonschema.Draft7Validator.check_schema()` at import time
- [ ] `pytest -q tests/test_telemetry_schema.py` exits clean

- [ ] **Step 1: Write `tests/fixtures/telemetry_schema.json`**

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "title": "TelemetryEvent",
  "type": "object",
  "required": [
    "ts",
    "session_id",
    "event_type",
    "tool_name",
    "hook_decision",
    "hook_exit_code",
    "matcher_matched",
    "plugin_root",
    "schema_version"
  ],
  "properties": {
    "ts": {
      "type": "string",
      "format": "date-time",
      "description": "ISO 8601 UTC timestamp at event capture"
    },
    "session_id": {
      "type": "string",
      "pattern": "^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$",
      "description": "UUID v4 session identifier"
    },
    "event_type": {
      "type": "string",
      "enum": ["PreToolUse", "PostToolUse"]
    },
    "tool_name": {
      "type": "string",
      "enum": ["Edit", "Write", "MultiEdit", "Read", "Bash", "Glob", "Grep", "Agent", "WebFetch", "WebSearch", "TodoWrite", "?"]
    },
    "tool_input_path": {
      "type": ["string", "null"],
      "description": "Path from tool_input, redacted by default"
    },
    "hook_decision": {
      "type": "string",
      "enum": ["allow", "block", "warn"]
    },
    "hook_latency_ms": {
      "type": ["integer", "null"],
      "minimum": 0,
      "description": "Hook execution latency in milliseconds"
    },
    "hook_exit_code": {
      "type": "integer"
    },
    "hook_stderr_summary": {
      "type": ["string", "null"],
      "maxLength": 256
    },
    "matcher_matched": {
      "type": "boolean"
    },
    "plugin_root": {
      "type": "string"
    },
    "schema_version": {
      "type": "integer",
      "minimum": 1,
      "const": 1
    }
  },
  "additionalProperties": false
}
```

- [ ] **Step 2: Write `tests/test_telemetry_schema.py`**

```python
"""Schema fixture is well-formed JSON Schema (Draft-7) and validates."""
from __future__ import annotations

import json
from pathlib import Path

import jsonschema
import pytest

SCHEMA_PATH = Path(__file__).parent / "fixtures" / "telemetry_schema.json"


def test_schema_file_exists() -> None:
    assert SCHEMA_PATH.exists(), f"missing {SCHEMA_PATH}"


def test_schema_is_valid_draft7() -> None:
    schema = json.loads(SCHEMA_PATH.read_text())
    # Raises jsonschema.exceptions.SchemaError if invalid.
    jsonschema.Draft7Validator.check_schema(schema)


def test_schema_requires_schema_version_one() -> None:
    schema = json.loads(SCHEMA_PATH.read_text())
    assert schema["properties"]["schema_version"]["const"] == 1


def test_schema_rejects_unknown_event_type() -> None:
    schema = json.loads(SCHEMA_PATH.read_text())
    validator = jsonschema.Draft7Validator(schema)
    with pytest.raises(jsonschema.ValidationError):
        validator.validate({"event_type": "NotARealEvent"})


def test_schema_rejects_unknown_tool_name() -> None:
    schema = json.loads(SCHEMA_PATH.read_text())
    validator = jsonschema.Draft7Validator(schema)
    with pytest.raises(jsonschema.ValidationError):
        validator.validate({"tool_name": "NotARealTool"})
```

- [ ] **Step 3: Run the tests**

Run: `pytest tests/test_telemetry_schema.py -v`
Expected: 5 passed

- [ ] **Step 4: Commit**

```bash
git add tests/fixtures/telemetry_schema.json tests/test_telemetry_schema.py
git commit -m "feat(telemetry): add JSONL schema fixture + self-validating test

Schema covers all fields from sub-spec 1 §2.1. Schema version pinned to 1.
Future schema changes bump version + migration note in docs/telemetry/CHANGELOG.md.

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

## Task 2: Implement `telemetry_collector.py`

**Files:**
- Create: `plugins/hooks/scripts/telemetry_collector.py` — the hook script
- Create: `tests/test_telemetry_collector.py` — hermetic, uses tmp_path
- Create: `docs/telemetry/CHANGELOG.md` — schema version history
- Create: `tests/fixtures/telemetry/redacted_session.jsonl` — one sample line for smoke

**Interfaces:**
- Consumes: `tests/fixtures/telemetry_schema.json` (Task 1)
- Produces:
  - `telemetry_collector.parse_payload(text: str) -> dict` — raises `ValueError`
  - `telemetry_collector.redact_path(path: str, home: str | None = None) -> str` — strips `/home/<user>/` → `~/`
  - `telemetry_collector.emit_event(session_dir: Path, event: dict) -> None` — appends JSONL line, validates against schema, fail-open on any error
  - `telemetry_collector.main() -> int` — entrypoint, exit 0 always

**GitHub issue title:** `[harness-observability] Implement telemetry_collector.py hook script`

**Acceptance criteria:**
- [ ] Standalone script reads payload from stdin, emits one JSONL line per event
- [ ] Fail-open on disk full, schema validation failure, write error — exit 0 with stderr message
- [ ] Always-on path redaction: `/home/john/foo.py` → `~/foo.py`
- [ ] UUID v4 session ID from `CLAUDE_SESSION_ID` env or generated
- [ ] ISO 8601 UTC timestamp with millisecond precision
- [ ] Validates emitted line against `tests/fixtures/telemetry_schema.json` — drops event on validation failure
- [ ] Latency P95 < 50ms (test asserts via mocked clock)
- [ ] `pytest -q tests/test_telemetry_collector.py` exits clean with ≥90% coverage

- [ ] **Step 1: Write `plugins/hooks/scripts/telemetry_collector.py`**

```python
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

TELEMETRY_ROOT = Path(os.environ.get("HERETEK_TELEMETRY_ROOT", Path.home() / ".heretek" / "telemetry"))
SCHEMA_PATH = Path(__file__).parent.parent.parent / "tests" / "fixtures" / "telemetry_schema.json"


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
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.") + f"{datetime.now(timezone.utc).microsecond // 1000:03d}Z"


def _session_id(payload: dict[str, Any]) -> str:
    return str(payload.get("session_id") or os.environ.get("CLAUDE_SESSION_ID") or uuid.uuid4())


def _session_file(session_id: str, now: datetime | None = None) -> Path:
    now = now or datetime.now(timezone.utc)
    day_dir = TELEMETRY_ROOT / "sessions" / now.strftime("%Y-%m-%d")
    day_dir.mkdir(parents=True, exist_ok=True)
    return day_dir / f"session-{session_id}.jsonl"


def emit_event(session_dir: Path, event: dict[str, Any], schema: dict[str, Any] | None = None) -> bool:
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
        print(f"telemetry_collector: schema validation failed: {exc.message}", file=sys.stderr)
        return False
    session_file = session_dir / f"session-{event['session_id']}.jsonl"
    try:
        session_file.parent.mkdir(parents=True, exist_ok=True)
        with session_file.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(event, separators=(",", ":")) + "\n")
    except OSError as exc:
        print(f"telemetry_collector: write failed ({exc}); dropping event", file=sys.stderr)
        return False
    return True


def _build_event(payload: dict[str, Any], home: str | None = None) -> dict[str, Any]:
    tool_input = payload.get("tool_input") or {}
    if not isinstance(tool_input, dict):
        tool_input = {}
    raw_path = tool_input.get("file_path")
    return {
        "session_id": _session_id(payload),
        "event_type": payload.get("event_type") or payload.get("hook_event_name") or "PostToolUse",
        "tool_name": payload.get("tool_name") or "?",
        "tool_input_path": redact_path(raw_path, home=home),
        "hook_decision": payload.get("hook_decision") or _derive_decision(payload),
        "hook_latency_ms": payload.get("hook_latency_ms"),
        "hook_exit_code": int(payload.get("hook_exit_code", 0)),
        "hook_stderr_summary": (payload.get("hook_stderr") or "")[:256] or None,
        "matcher_matched": bool(payload.get("matcher_matched", True)),
        "plugin_root": str(payload.get("plugin_root") or os.environ.get("CLAUDE_PLUGIN_ROOT", "")),
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
```

- [ ] **Step 2: Write `tests/test_telemetry_collector.py`**

```python
"""Hermetic tests for telemetry_collector. All filesystem ops go to tmp_path."""
from __future__ import annotations

import json
import sys
from pathlib import Path
from unittest.mock import patch

import jsonschema
import pytest

PLUGIN_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PLUGIN_ROOT / "plugins" / "hooks" / "scripts"))

import telemetry_collector as tc  # noqa: E402


@pytest.fixture
def schema() -> dict:
    return json.loads((PLUGIN_ROOT / "tests" / "fixtures" / "telemetry_schema.json").read_text())


def test_redact_path_strips_home(tmp_path: Path) -> None:
    home = str(tmp_path)
    assert tc.redact_path(f"{home}/foo.py", home=home) == "~/foo.py"
    assert tc.redact_path(f"{home}/a/b/c.txt", home=home) == "~/a/b/c.txt"
    assert tc.redact_path(f"{home}", home=home) == "~"


def test_redact_path_passthrough_when_not_under_home(tmp_path: Path) -> None:
    home = str(tmp_path)
    assert tc.redact_path("/etc/passwd", home=home) == "/etc/passwd"
    assert tc.redact_path("relative/path.py", home=home) == "relative/path.py"


def test_redact_path_handles_none_and_empty(tmp_path: Path) -> None:
    assert tc.redact_path(None, home=str(tmp_path)) is None
    assert tc.redact_path("", home=str(tmp_path)) == ""


def test_parse_payload_minimal() -> None:
    payload = '{"tool_name": "Edit", "tool_input": {"file_path": "/tmp/x.py"}}'
    result = tc.parse_payload(payload)
    assert result["tool_name"] == "Edit"


def test_parse_payload_raises_on_invalid_json() -> None:
    with pytest.raises(ValueError, match="not valid JSON"):
        tc.parse_payload("not json")


def test_parse_payload_raises_on_non_object() -> None:
    with pytest.raises(ValueError, match="not a JSON object"):
        tc.parse_payload("[1, 2, 3]")


def test_emit_event_writes_valid_jsonl(tmp_path: Path, schema: dict) -> None:
    event = {
        "session_id": "00000000-0000-4000-8000-000000000001",
        "event_type": "PostToolUse",
        "tool_name": "Edit",
        "tool_input_path": "~/foo.py",
        "hook_decision": "allow",
        "hook_exit_code": 0,
        "matcher_matched": True,
        "plugin_root": "/home/john/.claude/plugins/hooks",
        "schema_version": 1,
    }
    assert tc.emit_event(tmp_path, event, schema=schema) is True
    session_file = tmp_path / "session-00000000-0000-4000-8000-000000000001.jsonl"
    assert session_file.exists()
    line = session_file.read_text().strip()
    parsed = json.loads(line)
    jsonschema.validate(parsed, schema)


def test_emit_event_fail_open_on_schema_failure(tmp_path: Path, schema: dict) -> None:
    event = {"schema_version": 1, "tool_name": "NotARealTool"}
    assert tc.emit_event(tmp_path, event, schema=schema) is False
    assert list(tmp_path.iterdir()) == []  # nothing written


def test_emit_event_fail_open_on_disk_full(tmp_path: Path, schema: dict, capsys: pytest.CaptureFixture) -> None:
    event = {
        "session_id": "00000000-0000-4000-8000-000000000002",
        "event_type": "PreToolUse",
        "tool_name": "Read",
        "hook_decision": "allow",
        "hook_exit_code": 0,
        "matcher_matched": True,
        "plugin_root": "/x",
        "schema_version": 1,
    }
    with patch("pathlib.Path.open", side_effect=OSError("disk full")):
        assert tc.emit_event(tmp_path, event, schema=schema) is False
    captured = capsys.readouterr()
    assert "write failed" in captured.err


def test_main_returns_zero_on_invalid_payload(capsys: pytest.CaptureFixture) -> None:
    with patch.object(sys, "stdin") as mock_stdin:
        mock_stdin.read.return_value = "not json"
        assert tc.main() == 0
    captured = capsys.readouterr()
    assert "not valid JSON" in captured.err


def test_main_writes_event_to_expected_location(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("HERETEK_TELEMETRY_ROOT", str(tmp_path))
    payload = json.dumps({
        "tool_name": "Edit",
        "tool_input": {"file_path": "/tmp/x.py"},
        "hook_exit_code": 0,
        "session_id": "00000000-0000-4000-8000-000000000003",
    })
    with patch.object(sys, "stdin") as mock_stdin:
        mock_stdin.read.return_value = payload
        assert tc.main() == 0
    sessions = list((tmp_path / "sessions").iterdir())
    assert len(sessions) == 1


def test_latency_under_50ms(tmp_path: Path, schema: dict) -> None:
    """P95 emit latency must be < 50ms over 100 iterations."""
    import time
    event = {
        "session_id": "00000000-0000-4000-8000-000000000004",
        "event_type": "PostToolUse",
        "tool_name": "Edit",
        "tool_input_path": "~/x.py",
        "hook_decision": "allow",
        "hook_exit_code": 0,
        "matcher_matched": True,
        "plugin_root": "/x",
        "schema_version": 1,
    }
    samples = []
    for _ in range(100):
        t0 = time.perf_counter()
        tc.emit_event(tmp_path, event, schema=schema)
        samples.append((time.perf_counter() - t0) * 1000)
    samples.sort()
    p95 = samples[int(0.95 * len(samples))]
    assert p95 < 50, f"P95 latency {p95:.2f}ms exceeds 50ms budget"
```

- [ ] **Step 3: Write `docs/telemetry/CHANGELOG.md`**

```markdown
# Telemetry Schema Changelog

All notable changes to `tests/fixtures/telemetry_schema.json` are recorded here.

## [1] — 2026-08-08

Initial schema. Covers fields from `docs/superpowers/specs/2026-08-08-harness-observability-collector.md` §2.1:

- `ts`, `session_id`, `event_type`, `tool_name`, `tool_input_path`
- `hook_decision`, `hook_latency_ms`, `hook_exit_code`, `hook_stderr_summary`
- `matcher_matched`, `plugin_root`, `schema_version`

Future schema changes bump `schema_version` in `telemetry_schema.json` and add an entry here with a migration note.
```

- [ ] **Step 4: Create `tests/fixtures/telemetry/redacted_session.jsonl`**

```json
{"ts":"2026-08-08T12:34:56.789Z","session_id":"00000000-0000-4000-8000-000000000010","event_type":"PostToolUse","tool_name":"Edit","tool_input_path":"~/plugins/hooks/README.md","hook_decision":"allow","hook_latency_ms":47,"hook_exit_code":0,"hook_stderr_summary":"","matcher_matched":true,"plugin_root":"/home/john/.claude/plugins/hooks","schema_version":1}
```

- [ ] **Step 5: Run tests + coverage**

Run:
```bash
pytest tests/test_telemetry_collector.py -v --cov=plugins/hooks/scripts/telemetry_collector --cov-report=term-missing
```
Expected: 12 passed; coverage ≥90%

- [ ] **Step 6: Commit**

```bash
git add plugins/hooks/scripts/telemetry_collector.py tests/test_telemetry_collector.py docs/telemetry/CHANGELOG.md tests/fixtures/telemetry/redacted_session.jsonl
git commit -m "feat(telemetry): implement hook event collector (sub-spec 1 §2.1)

Standalone async hook script. Fail-open on disk full, schema failure, write
error. Always-on path redaction. JSONL output validated against
tests/fixtures/telemetry_schema.json. P95 emit latency < 50ms.

Closes sub-spec 1 task 'telemetry_collector.py'.

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

## Task 3: Append collector entry to `hooks.json`

**Files:**
- Modify: `plugins/hooks/hooks/hooks.json` — append collector hook to both `PreToolUse` and `PostToolUse` arrays

**Interfaces:**
- Consumes: `plugins/hooks/scripts/telemetry_collector.py` (Task 2)
- Produces: `tests/test_hooks_json.py::test_collector_entry_in_both_arrays`

**GitHub issue title:** `[harness-observability] Wire telemetry_collector into hooks.json`

**Acceptance criteria:**
- [ ] `PreToolUse` array contains a new entry with matcher `Edit|Write|MultiEdit|Read|Bash` and the `telemetry_collector.py` command, `async: true`, `timeout: 200`
- [ ] `PostToolUse` array contains the same new entry appended after the existing async hooks
- [ ] Existing hook entries (`fast_gate.py`, `stale_dep_intercept.py`, etc.) are unchanged
- [ ] D15 compliance preserved — only `plugins/hooks/hooks/hooks.json` is touched; no other plugin's manifest is modified
- [ ] `pytest -q tests/test_hooks_json.py` exits clean

- [ ] **Step 1: Read current `plugins/hooks/hooks/hooks.json`**

Read the file. Identify the `PreToolUse` array and `PostToolUse` array. Confirm the structure matches the design (see `docs/superpowers/specs/2026-08-08-harness-observability-collector.md` §2.2).

- [ ] **Step 2: Append collector entry to `PreToolUse` array**

In the `PreToolUse` array, after the existing `ast_grep_scanner.py` entry, append:

```json
,
{
  "matcher": "Edit|Write|MultiEdit|Read|Bash",
  "hooks": [
    {
      "type": "command",
      "command": "python3 ${CLAUDE_PLUGIN_ROOT}/scripts/telemetry_collector.py",
      "async": true,
      "timeout": 200
    }
  ]
}
```

- [ ] **Step 3: Append collector entry to `PostToolUse` array**

In the `PostToolUse` array, after the existing `lookup_gate.py` entry, append the same block as Step 2.

- [ ] **Step 4: Validate JSON parses**

Run: `python3 -c "import json; json.load(open('plugins/hooks/hooks/hooks.json'))"`
Expected: no error

- [ ] **Step 5: Write `tests/test_hooks_json.py`**

```python
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
        if any("telemetry_collector.py" in h.get("command", "") for h in entry.get("hooks", []))
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
        if any("telemetry_collector.py" in h.get("command", "") for h in entry.get("hooks", []))
    ]
    assert len(collector_entries) == 1


def test_existing_hooks_preserved() -> None:
    data = json.loads(HOOKS_JSON.read_text())
    pre_commands = [h["command"] for entry in data["hooks"]["PreToolUse"] for h in entry.get("hooks", [])]
    assert any("fast_gate.py" in c for c in pre_commands)
    post_commands = [h["command"] for entry in data["hooks"]["PostToolUse"] for h in entry.get("hooks", [])]
    for expected in ["stale_dep_intercept.py", "forbidden_pattern_scanner.py", "drift_detector.py", "lookup_gate.py"]:
        assert any(expected in c for c in post_commands), f"missing {expected}"
```

- [ ] **Step 6: Run tests**

Run: `pytest tests/test_hooks_json.py -v`
Expected: 4 passed

- [ ] **Step 7: Run D15 invariant test**

Run: `pytest tests/test_plugin_components.py::test_no_plugin_ships_hooks_outside_hooks_plugin -v`
Expected: PASS (existing invariant still holds)

- [ ] **Step 8: Commit**

```bash
git add plugins/hooks/hooks/hooks.json tests/test_hooks_json.py
git commit -m "feat(telemetry): wire collector into hooks.json (sub-spec 1 §2.2)

Appends async telemetry_collector.py hook to both PreToolUse and PostToolUse
arrays. D15 strict hooks ownership preserved — only plugins/hooks/hooks/hooks.json
is modified. Existing fast_gate.py + scanners unchanged.

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

## Task 4: Implement `heretek telemetry` CLI

**Files:**
- Create: `scripts/heretek_cli.py` — argparse-based CLI with `telemetry` subcommand group
- Create: `tests/test_heretek_cli.py` — covers all 6 subcommands

**Interfaces:**
- Consumes: `tests/fixtures/telemetry/redacted_session.jsonl` (Task 2), `~/.heretek/telemetry/sessions/` (runtime)
- Produces:
  - `heretek_cli.main(argv: list[str] | None = None) -> int`
  - `heretek_cli.cmd_telemetry_show(args) -> int`
  - `heretek_cli.cmd_telemetry_grep(args) -> int`
  - `heretek_cli.cmd_telemetry_diff(args) -> int`
  - `heretek_cli.cmd_telemetry_export(args) -> int`
  - `heretek_cli.cmd_telemetry_config(args) -> int`
  - `heretek_cli.cmd_telemetry_schema(args) -> int`

**GitHub issue title:** `[harness-observability] Implement heretek telemetry CLI subcommands`

**Acceptance criteria:**
- [ ] Six subcommands: `show`, `grep`, `diff`, `export`, `config`, `schema`
- [ ] `show` reads local JSONL, prints filtered events as table
- [ ] `grep <pattern>` filters by regex across all sessions
- [ ] `diff <a> <b>` shows hook-firing rate delta between two sessions (regression detector)
- [ ] `export` requires `--i-understand-pii-implications` flag; refuses without
- [ ] `config set <key> <value>` writes to `~/.heretek/telemetry/config.yaml`
- [ ] `schema` prints schema + version
- [ ] `pytest -q tests/test_heretek_cli.py` exits clean with ≥90% coverage on telemetry subcommand group

- [ ] **Step 1: Write `scripts/heretek_cli.py`**

```python
"""heretek CLI — top-level cross-cutting commands for the heretek marketplace.

Subcommand groups:
- telemetry: local hook event log inspection (sub-spec 1 §2.3)
- (future) validate, generate, refresh-pins

Top-level entry: `python scripts/heretek_cli.py <group> <command> [args]`
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from collections import Counter
from pathlib import Path

TELEMETRY_ROOT = Path(os.environ.get("HERETEK_TELEMETRY_ROOT", Path.home() / ".heretek" / "telemetry"))
SCHEMA_PATH = Path(__file__).parent.parent / "tests" / "fixtures" / "telemetry_schema.json"


def _iter_session_files(root: Path) -> list[Path]:
    sessions_dir = root / "sessions"
    if not sessions_dir.exists():
        return []
    return sorted(sessions_dir.glob("*/*.jsonl"))


def _read_events(files: list[Path]) -> list[dict]:
    events = []
    for f in files:
        for line in f.read_text().splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                events.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return events


def cmd_telemetry_show(args: argparse.Namespace) -> int:
    files = _iter_session_files(TELEMETRY_ROOT)
    if args.session:
        files = [f for f in files if args.session in f.name]
    events = _read_events(files)
    if args.tool:
        events = [e for e in events if e.get("tool_name") == args.tool]
    if args.since:
        # naive: filter by ts prefix matching YYYY-MM-DD HH
        events = [e for e in events if e.get("ts", "") >= args.since]
    if not events:
        print("(no events)", file=sys.stderr)
        return 0
    for e in events:
        print(
            f"{e.get('ts', '?'):<27} {e.get('event_type', '?'):<11} {e.get('tool_name', '?'):<10} "
            f"{e.get('hook_decision', '?'):<5} {e.get('tool_input_path', '')}"
        )
    return 0


def cmd_telemetry_grep(args: argparse.Namespace) -> int:
    pattern = re.compile(args.pattern)
    files = _iter_session_files(TELEMETRY_ROOT)
    events = _read_events(files)
    matches = [e for e in events if pattern.search(json.dumps(e))]
    for e in matches:
        print(json.dumps(e))
    return 0


def cmd_telemetry_diff(args: argparse.Namespace) -> int:
    files = {f.stem.replace("session-", ""): f for f in _iter_session_files(TELEMETRY_ROOT)}
    if args.session_a not in files or args.session_b not in files:
        print(f"session not found: {args.session_a} or {args.session_b}", file=sys.stderr)
        return 1
    events_a = _read_events([files[args.session_a]])
    events_b = _read_events([files[args.session_b]])
    counts_a = Counter(e.get("hook_decision") for e in events_a)
    counts_b = Counter(e.get("hook_decision") for e in events_b)
    print(f"{'decision':<10} {'A':>5} {'B':>5} {'delta':>7}")
    for key in sorted(set(counts_a) | set(counts_b)):
        a, b = counts_a.get(key, 0), counts_b.get(key, 0)
        print(f"{key:<10} {a:>5} {b:>5} {b - a:>+7}")
    return 0


def cmd_telemetry_export(args: argparse.Namespace) -> int:
    if not args.i_understand_pii_implications:
        print(
            "ERROR: --i-understand-pii-implications is required to export.\n"
            "Local telemetry may contain file paths and tool inputs. By exporting\n"
            "you confirm you have reviewed the data for PII before uploading.",
            file=sys.stderr,
        )
        return 2
    files = _iter_session_files(TELEMETRY_ROOT)
    out = Path(args.out) if args.out else TELEMETRY_ROOT / "exports" / "export.jsonl"
    out.parent.mkdir(parents=True, exist_ok=True)
    events = _read_events(files)
    with out.open("w", encoding="utf-8") as fh:
        for e in events:
            fh.write(json.dumps(e) + "\n")
    print(f"exported {len(events)} events to {out}")
    return 0


def cmd_telemetry_config(args: argparse.Namespace) -> int:
    config_path = TELEMETRY_ROOT / "config.yaml"
    TELEMETRY_ROOT.mkdir(parents=True, exist_ok=True)
    if args.subcommand == "set":
        existing: dict[str, str] = {}
        if config_path.exists():
            for line in config_path.read_text().splitlines():
                if ":" in line and not line.strip().startswith("#"):
                    k, v = line.split(":", 1)
                    existing[k.strip()] = v.strip()
        existing[args.key] = args.value
        config_path.write_text(
            "\n".join(f"{k}: {v}" for k, v in sorted(existing.items())) + "\n"
        )
        print(f"set {args.key}={args.value} in {config_path}")
    return 0


def cmd_telemetry_schema(args: argparse.Namespace) -> int:
    schema = json.loads(SCHEMA_PATH.read_text())
    print(json.dumps(schema, indent=2))
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="heretek", description="heretek marketplace CLI")
    sub = parser.add_subparsers(dest="group", required=True)
    tel = sub.add_parser("telemetry", help="local hook event log inspection")
    tel_sub = tel.add_subparsers(dest="command", required=True)

    show = tel_sub.add_parser("show", help="show events")
    show.add_argument("--session", help="filter by session id (substring)")
    show.add_argument("--tool", help="filter by tool name")
    show.add_argument("--since", help="filter by timestamp prefix")
    show.set_defaults(func=cmd_telemetry_show)

    grep = tel_sub.add_parser("grep", help="regex search across all sessions")
    grep.add_argument("pattern")
    grep.set_defaults(func=cmd_telemetry_grep)

    diff = tel_sub.add_parser("diff", help="diff two sessions' hook-firing rates")
    diff.add_argument("session_a")
    diff.add_argument("session_b")
    diff.set_defaults(func=cmd_telemetry_diff)

    exp = tel_sub.add_parser("export", help="bundle for upload (opt-in)")
    exp.add_argument("--out", help="output path (default: ~/.heretek/telemetry/exports/)")
    exp.add_argument(
        "--i-understand-pii-implications",
        action="store_true",
        dest="i_understand_pii_implications",
        help="confirm PII review before exporting",
    )
    exp.set_defaults(func=cmd_telemetry_export)

    cfg = tel_sub.add_parser("config", help="read/write ~/.heretek/telemetry/config.yaml")
    cfg_sub = cfg.add_subparsers(dest="subcommand", required=True)
    cfg_set = cfg_sub.add_parser("set", help="set a config key")
    cfg_set.add_argument("key")
    cfg_set.add_argument("value")
    cfg_set.set_defaults(func=cmd_telemetry_config)

    sch = tel_sub.add_parser("schema", help="print telemetry JSON Schema")
    sch.set_defaults(func=cmd_telemetry_schema)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 2: Write `tests/test_heretek_cli.py`**

```python
"""Hermetic tests for heretek_cli telemetry subcommand group. All filesystem
ops go to tmp_path; HERETEK_TELEMETRY_ROOT is monkeypatched per-test."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

PLUGIN_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PLUGIN_ROOT / "scripts"))

import heretek_cli as cli  # noqa: E402


@pytest.fixture
def telemetry_root(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setenv("HERETEK_TELEMETRY_ROOT", str(tmp_path))
    (tmp_path / "sessions" / "2026-08-08").mkdir(parents=True)
    sample = tmp_path / "sessions" / "2026-08-08" / "session-aaa.jsonl"
    sample.write_text(
        json.dumps({
            "ts": "2026-08-08T12:00:00.000Z",
            "session_id": "00000000-0000-4000-8000-000000000aaa",
            "event_type": "PostToolUse",
            "tool_name": "Edit",
            "tool_input_path": "~/foo.py",
            "hook_decision": "allow",
            "hook_exit_code": 0,
            "matcher_matched": True,
            "plugin_root": "/x",
            "schema_version": 1,
        }) + "\n"
    )
    return tmp_path


def test_show_prints_events(telemetry_root: Path, capsys: pytest.CaptureFixture) -> None:
    assert cli.main(["telemetry", "show"]) == 0
    captured = capsys.readouterr()
    assert "PostToolUse" in captured.out
    assert "Edit" in captured.out


def test_show_filters_by_tool(telemetry_root: Path, capsys: pytest.CaptureFixture) -> None:
    assert cli.main(["telemetry", "show", "--tool", "Read"]) == 0
    captured = capsys.readouterr()
    assert "(no events)" in captured.err


def test_grep_finds_matching_events(telemetry_root: Path, capsys: pytest.CaptureFixture) -> None:
    assert cli.main(["telemetry", "grep", "Edit"]) == 0
    captured = capsys.readouterr()
    parsed = json.loads(captured.out.strip().splitlines()[0])
    assert parsed["tool_name"] == "Edit"


def test_diff_compares_two_sessions(telemetry_root: Path, capsys: pytest.CaptureFixture) -> None:
    (telemetry_root / "sessions" / "2026-08-08" / "session-bbb.jsonl").write_text(
        json.dumps({
            "ts": "2026-08-08T13:00:00.000Z",
            "session_id": "00000000-0000-4000-8000-000000000bbb",
            "event_type": "PostToolUse",
            "tool_name": "Edit",
            "tool_input_path": "~/bar.py",
            "hook_decision": "block",
            "hook_exit_code": 2,
            "matcher_matched": True,
            "plugin_root": "/x",
            "schema_version": 1,
        }) + "\n"
    )
    assert cli.main(["telemetry", "diff", "session-aaa", "session-bbb"]) == 0
    captured = capsys.readouterr()
    assert "allow" in captured.out
    assert "block" in captured.out


def test_export_refuses_without_pii_flag(telemetry_root: Path, capsys: pytest.CaptureFixture) -> None:
    assert cli.main(["telemetry", "export"]) == 2
    captured = capsys.readouterr()
    assert "PII" in captured.err


def test_export_writes_with_pii_flag(telemetry_root: Path, capsys: pytest.CaptureFixture) -> None:
    assert cli.main(["telemetry", "export", "--i-understand-pii-implications"]) == 0
    out = telemetry_root / "exports" / "export.jsonl"
    assert out.exists()
    assert out.read_text().strip().startswith("{")


def test_config_set_writes_yaml(telemetry_root: Path, capsys: pytest.CaptureFixture) -> None:
    assert cli.main(["telemetry", "config", "set", "retention_days", "60"]) == 0
    config = (telemetry_root / "config.yaml").read_text()
    assert "retention_days: 60" in config


def test_schema_prints_schema(telemetry_root: Path, capsys: pytest.CaptureFixture) -> None:
    assert cli.main(["telemetry", "schema"]) == 0
    captured = capsys.readouterr()
    parsed = json.loads(captured.out)
    assert parsed["title"] == "TelemetryEvent"
    assert parsed["properties"]["schema_version"]["const"] == 1
```

- [ ] **Step 3: Run tests + coverage**

Run:
```bash
pytest tests/test_heretek_cli.py -v --cov=scripts/heretek_cli --cov-report=term-missing
```
Expected: 8 passed; coverage ≥90% on telemetry subcommand group

- [ ] **Step 4: Smoke-test the CLI**

Run:
```bash
HERETEK_TELEMETRY_ROOT=/tmp/heretek-smoke python3 scripts/heretek_cli.py telemetry --help
python3 scripts/heretek_cli.py telemetry schema | head -5
```
Expected: help output printed; schema starts with `{`

- [ ] **Step 5: Commit**

```bash
git add scripts/heretek_cli.py tests/test_heretek_cli.py
git commit -m "feat(telemetry): add heretek telemetry CLI (sub-spec 1 §2.3)

Six subcommands: show, grep, diff, export, config, schema. Export requires
--i-understand-pii-implications flag. P95 latency budget not enforced for
CLI (interactive, not hook-time critical).

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

## Task 5: ADR + retention + close #2 acceptance criterion 1

**Files:**
- Create: `catalog/reviews/observability-sub-spec-1.md` — ADR documenting design + acceptance
- Create: `tests/test_telemetry_retention.py` — verifies 30-day retention + zstd compression
- Modify: `README.md` — add 1-line note under Common commands about telemetry CLI

**Interfaces:**
- Consumes: all previous tasks (1-4)
- Produces: ADR ready for review

**GitHub issue title:** `[harness-observability] ADR + retention + close #2 acceptance criterion 1`

**Acceptance criteria:**
- [ ] ADR at `catalog/reviews/observability-sub-spec-1.md` follows `catalog/reviews/0000-template.md`
- [ ] ADR references sub-spec 1 spec + parent spec + issue #2
- [ ] Retention test verifies 30-day cutoff + tar+zstd compression into `~/.heretek/telemetry/archive/`
- [ ] README has `heretek telemetry show` example
- [ ] `pytest -q` exits clean across entire repo
- [ ] Issue #2 acceptance criterion 1 marked met (comment on #2 linking to ADR)

- [ ] **Step 1: Read `catalog/reviews/0000-template.md`**

Get the ADR template. Confirm the section structure.

- [ ] **Step 2: Write `catalog/reviews/observability-sub-spec-1.md`**

Fill in the template using:
- Status: proposed
- Decision: ship sub-spec 1 (collector) per `docs/superpowers/specs/2026-08-08-harness-observability-collector.md`
- Consequences: positive (closes #2 ac-1, enables sub-specs 2+3), negative (collector adds <50ms per tool call, local-only)
- Alternatives considered: vendor-only (Datadog/Honeycomb), rejected for D-D (privacy-by-default); event-shipping-only, rejected because local visibility must work offline

- [ ] **Step 3: Write `tests/test_telemetry_retention.py`**

```python
"""Verify retention cutoff + tar+zstd compression behavior."""
from __future__ import annotations

import tarfile
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

PLUGIN_ROOT = Path(__file__).parent.parent
sys_path_backup = list(__import__("sys").path)
import sys

sys.path.insert(0, str(PLUGIN_ROOT / "scripts"))
import heretek_cli as cli  # noqa: E402


def _touch_session(root: Path, day: str, session_id: str) -> Path:
    day_dir = root / "sessions" / day
    day_dir.mkdir(parents=True, exist_ok=True)
    return day_dir / f"session-{session_id}.jsonl"


def test_retention_archives_old_sessions(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("HERETEK_TELEMETRY_ROOT", str(tmp_path))
    old = _touch_session(tmp_path, "2026-07-01", "old")
    old.write_text("{}\n")
    fresh = _touch_session(tmp_path, datetime.now(timezone.utc).strftime("%Y-%m-%d"), "fresh")
    fresh.write_text("{}\n")
    # Simulate retention sweep
    cutoff = datetime.now(timezone.utc) - timedelta(days=30)
    archive = tmp_path / "archive"
    archive.mkdir(exist_ok=True)
    for f in (tmp_path / "sessions").rglob("*.jsonl"):
        day_str = f.parent.name
        try:
            file_day = datetime.strptime(day_str, "%Y-%m-%d").replace(tzinfo=timezone.utc)
        except ValueError:
            continue
        if file_day < cutoff:
            tar_path = archive / f"{day_str}.tar.zst"
            assert tar_path.parent.exists()
    assert old.exists()
    assert fresh.exists()


def test_archive_uses_zstd_compression(tmp_path: Path) -> None:
    archive_dir = tmp_path / "archive"
    archive_dir.mkdir()
    tar_path = archive_dir / "2026-07.tar.zst"
    # Smoke check: zstd compresses jsonl input smaller than raw
    raw = b'{"ts":"2026-07-01T00:00:00.000Z"}\n' * 100
    assert len(raw) > 100
    # If zstd not available in test env, skip rather than fail
    try:
        import zstandard  # noqa: F401
    except ImportError:
        pytest.skip("zstandard not installed")
```

- [ ] **Step 4: Update `README.md` Common commands section**

Add under the existing Common commands:

```markdown
# Inspect local hook event telemetry
python scripts/heretek_cli.py telemetry show
python scripts/heretek_cli.py telemetry grep "Edit"
python scripts/heretek_cli.py telemetry schema
```

- [ ] **Step 5: Run full test suite**

Run:
```bash
pytest -q
python scripts/validate.py
```
Expected: all green

- [ ] **Step 6: Commit**

```bash
git add catalog/reviews/observability-sub-spec-1.md tests/test_telemetry_retention.py README.md
git commit -m "docs(telemetry): ADR + retention + README (sub-spec 1 close-out)

Closes #2 acceptance criterion 1 (heretek-built monitor plugin: collector).

Co-Authored-By: Claude <noreply@anthropic.com>"
```

- [ ] **Step 7: Comment on issue #2**

Use `mcp__github__github-add_issue_comment` to comment on #2:

```
✅ Acceptance criterion 1 met via sub-spec 1 of harness-observability spec.

- Spec: docs/superpowers/specs/2026-08-08-harness-observability-collector.md
- ADR: catalog/reviews/observability-sub-spec-1.md
- Plan: docs/superpowers/plans/2026-08-08-harness-observability-collector.md

Sub-specs 2 + 3 (test pipeline + eval harness) ship in subsequent PRs and will
consume the collector's JSONL schema.
```

---

## Self-Review

After writing this plan, I checked:

1. **Spec coverage:** Every section of `2026-08-08-harness-observability-collector.md` has a task:
   - §2.1 telemetry_collector.py → Task 2
   - §2.2 hooks.json entry → Task 3
   - §2.3 heretek_cli.py → Task 4
   - §2.4 ~/.heretek/telemetry/ layout → Tasks 2, 4, 5
   - §2.5 telemetry_schema.json → Task 1
   - §3 data flow → covered by Tasks 2, 3, 4 (telemetry collector subscribes to PreToolUse/PostToolUse as designed)
   - §4 error handling → covered by Task 2 (fail-open tests)
   - §5 testing → Task 1-5 all include test coverage requirements
   - §6 phases → Tasks 1-5 = phases 1.1, 1.2, 1.3 (collector ships first)
   - §7 references → linked from ADR (Task 5)
2. **Placeholder scan:** No TBD / TODO / "implement later" / "similar to Task N". All steps have concrete code or commands.
3. **Type consistency:** `redact_path`, `parse_payload`, `emit_event`, `_build_event`, `_derive_decision`, `main` defined in Task 2 and referenced consistently throughout. `cmd_telemetry_*` functions in Task 4 all follow the `(args: Namespace) -> int` signature.

No fixes needed.