#!/usr/bin/env bash
# probe.sh — manually trigger a Claude Code hook event and append to its log.
# Usage: ./probe.sh <hook-name> [extra args...]
set -euo pipefail

HOOK_NAME="${1:-}"
if [ -z "$HOOK_NAME" ]; then
  echo "usage: $0 <hook-name> [extra args...]" >&2
  exit 2
fi

LOG_DIR="$(cd "$(dirname "$0")" && pwd)/logs"
LOG_FILE="$LOG_DIR/$HOOK_NAME.log"
mkdir -p "$LOG_DIR"

TS="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
EVENT="${HOOK_EVENT:-PreToolUse}"
TOOL="${PROBE_TOOL:-manual}"
ARGS_JSON="${PROBE_ARGS:-{\}}"
DECISION="${PROBE_DECISION:-n/a}"
DURATION_MS="${PROBE_DURATION_MS:-0}"
NOTE="${PROBE_NOTE:-manual probe via probe.sh}"

printf '{"ts": "%s", "event": "%s", "tool": "%s", "args": %s, "decision": "%s", "duration_ms": %d, "note": "%s"}\n' \
  "$TS" "$EVENT" "$TOOL" "$ARGS_JSON" "$DECISION" "$DURATION_MS" "$NOTE" \
  >> "$LOG_FILE"

echo "appended to $LOG_FILE"
