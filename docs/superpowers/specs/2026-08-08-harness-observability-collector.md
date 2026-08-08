---
date: 2026-08-08
topic: harness-observability-collector
status: draft
parent: 2026-08-08-harness-observability-design.md (D23–D29 inherited)
---

# Harness Observability — Collector (sub-spec 1)

> Date: 2026-08-08. Sub-spec 1 of 3 under the parent harness-observability spec. Inherits D23–D29 unchanged.

## 1. Summary

Adds a hook event collector to the existing `plugins/hooks/` plugin. Captures every PreToolUse / PostToolUse event to local JSONL under `~/.heretek/telemetry/`. Ships a `heretek telemetry` CLI for local inspection. Closes issue #2 acceptance criterion 1.

## 2. Components

### 2.1 `plugins/hooks/scripts/telemetry_collector.py`

Hook script. Standalone, async, fail-open. Reads Claude Code hook payload from stdin, appends one JSONL line to the active session file.

**Captured fields (per event):**

```json
{
  "ts": "2026-08-08T12:34:56.789Z",
  "session_id": "uuid-v4",
  "event_type": "PreToolUse|PostToolUse",
  "tool_name": "Edit|Write|MultiEdit|Read|Bash",
  "tool_input_path": "plugins/hooks/README.md",
  "hook_decision": "allow|block|warn",
  "hook_latency_ms": 47,
  "hook_exit_code": 0,
  "hook_stderr_summary": "ruff: 1 violation",
  "matcher_matched": true,
  "plugin_root": "/home/john/.claude/plugins/hooks",
  "schema_version": 1
}
```

**Session file:** `~/.heretek/telemetry/sessions/<YYYY-MM-DD>/session-<uuid>.jsonl`

**Exit codes:**
- 0: success OR fail-open (drop event on disk full, log to stderr)
- 2: NEVER (collector is observability, never blocks)

### 2.2 `plugins/hooks/hooks/hooks.json` — append collector entry

Append a new entry to both `PreToolUse` and `PostToolUse` arrays:

```json
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

D29 compliance: only `plugins/hooks/` declares hooks. No other plugin touches `hooks.json`.

### 2.3 `scripts/heretek_cli.py` — `telemetry` subcommand group

Subcommands:
- `heretek telemetry show [--session <id>] [--tool Edit] [--since 1h]`
- `heretek telemetry grep <pattern>`
- `heretek telemetry diff <session-a> <session-b>`
- `heretek telemetry export [--out <path>] --i-understand-pii-implications`
- `heretek telemetry config set <key> <value>`
- `heretek telemetry schema`

**Why a heretek-level script not a plugin-level script:** Symmetric with `validate.py`, `generate_marketplace.py`. Cross-cutting heretek tooling lives at the repo root, not under any single plugin.

### 2.4 `~/.heretek/telemetry/` layout

```
~/.heretek/telemetry/
  config.yaml                    ← user preferences
  sessions/
    2026-08-08/
      session-abc123.jsonl
      session-def456.jsonl
  exports/
    2026-08-08-heretek-pr42.jsonl  ← opt-in CI exports
  archive/
    2026-07-*.tar.zst            ← rotated + compressed after retention cutoff
```

**Default retention:** 30 days. Configurable in `config.yaml`. Compression: `tar | zstd -19`. Never auto-uploads from archive.

**Default config:**
```yaml
upload_opt_in: false
ci_export: false
redact_paths: true
retention_days: 30
```

### 2.5 `tests/fixtures/telemetry_schema.json` — JSON Schema for the JSONL line format

Schema enforced at emit time. Every collector write is validated. Any drift fails the test suite.

## 3. Data flow

```
Claude Code tool call
   └─▶ PreToolUse hook fires
         └─▶ fast_gate.py (existing — 100ms budget)
         └─▶ telemetry_collector.py (NEW — 200ms budget, async)
               ├─▶ parse_payload
               ├─▶ redact_paths (always on)
               ├─▶ validate against telemetry_schema.json
               └─▶ append to session JSONL
   └─▶ tool executes
   └─▶ PostToolUse hook fires
         └─▶ stale_dep_intercept.py (existing — async)
         └─▶ forbidden_pattern_scanner.py (existing — async)
         └─▶ drift_detector.py (existing — async)
         └─▶ lookup_gate.py (existing — async)
         └─▶ telemetry_collector.py (NEW — captures decision + latency)
```

## 4. Error handling

| Failure | Response |
|---|---|
| `~/.heretek/telemetry/` not writable | Print stderr, exit 0 (fail-open) |
| Disk full | Print stderr, exit 0 (fail-open) |
| Schema validation fails | Print stderr, drop event, exit 0 |
| `CLAUDE_SESSION_ID` env missing | Generate UUID v4 from `os.urandom` |
| `redact_paths` fails | Print stderr, write path as-is (degraded but not failing) |

## 5. Testing

- `tests/test_telemetry_collector.py` — hermetic. Stubs `~/.heretek/telemetry/` to `tmp_path`. Asserts schema, opt-in, redact, fail-open.
- `tests/test_heretek_cli.py` — covers `show, grep, diff, export, config, schema` subcommands.
- `tests/test_hooks_json.py` — verifies collector hook entry parses + matches.
- `tests/fixtures/telemetry_schema.json` — JSON Schema. Test asserts emit validates.

**Coverage target:** ≥90% on `telemetry_collector.py` and the CLI subcommand group.

## 6. Phases

| Phase | Deliverable | Exit |
|---|---|---|
| 1.1 | `telemetry_collector.py` + schema + collector hook entry | local install shows events; schema validates |
| 1.2 | `heretek telemetry` CLI | `show`, `grep`, `diff`, `export`, `config`, `schema` all work |
| 1.3 | Retention + compression + redact-paths hardening | 30-day retention enforced; archive works; PII redacted |

## 7. References

- `docs/superpowers/specs/2026-08-08-harness-observability-design.md` — parent spec
- `plugins/hooks/scripts/fast_gate.py` — existing pattern for hook scripts
- `plugins/hooks/hooks/hooks.json` — current hook manifest
- Issue #2 — v2 Monitor plugins
