# Hook Evidence Logs

One JSONL file per hook: `<hook-name>.log`. Append-only.

## Schema (one event per line)

```json
{"ts": "<ISO-8601 UTC>", "event": "<PreToolUse|PostToolUse|UserPromptSubmit|Stop|SessionStart|SessionEnd|SubagentStart|SubagentStop|Notification|PreCompact>", "tool": "<tool name or null>", "args": {...}, "decision": "allow|deny|ask|n/a", "duration_ms": <int>, "note": "<free text>"}
```

## Rotation

Before the next pass starts, rename the previous log: `mv <name>.log <name>.log.<YYYY-MM-DD>.old`. Never delete.

## Capture method

Use `.claude/hooks/probe.sh <hook-name>` to trigger and capture one event.
