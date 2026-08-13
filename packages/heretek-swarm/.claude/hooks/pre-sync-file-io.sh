#!/usr/bin/env bash
# pre-sync-file-io.sh — Phase 1 antipattern blocker.
#
# Hook event: PreToolUse (Edit|Write|MultiEdit)
# Matcher:    Edit|Write|MultiEdit (configured in .claude/settings.json)
# Source of truth: docs/superpowers/specs/2026-06-22-hooks-audit.md row 37
#                  + .claude/rules/antipatterns.md:11
#
# Rule: synchronous fs APIs (fs.readFileSync / fs.writeFileSync / fs.appendFileSync /
# fs.existsSync / fs.statSync / fs.mkdirSync / fs.rmSync / fs.readdirSync) must not
# appear in app code. Block the tool call and point at the async alternative.
#
# Scope: only files under apps/{web,backend}/src/**, backend/src/**, web/src/**.
# Excludes scripts/, tools/, .claude/, *.sh, *.test.ts, *.spec.ts.
#
# Protocol: exit 0 = allow, exit 2 + stderr reason = block, exit 0 + stderr warning = soft warn.
# Source is read from $CLAUDE_TOOL_FILE_PATH; for Write we also scan stdin-supplied content.

set -euo pipefail

# Read the PreToolUse JSON envelope from stdin FIRST — Claude Code passes the
# tool call as JSON on stdin, not via env vars.
INPUT="$(cat || true)"

# Extract a JSON string field (first match) from the stdin envelope. No jq.
json_field() {
  local field="$1" raw
  raw="$(printf '%s' "$INPUT" \
    | { grep -oE "\"${field}\"[[:space:]]*:[[:space:]]*\"[^\"]*\"" || true; } \
    | { head -n1 || true; })"
  [[ -z "$raw" ]] && return 1
  printf '%s' "$raw" | sed -E "s/^\"${field}\"[[:space:]]*:[[:space:]]*\"(.*)\"$/\\1/"
}

TOOL_NAME="$(json_field tool_name 2>/dev/null || echo "")"
[ -z "$TOOL_NAME" ] && TOOL_NAME="${CLAUDE_TOOL_NAME:-}"
FILE_PATH="$(json_field file_path 2>/dev/null || echo "")"
[ -z "$FILE_PATH" ] && FILE_PATH="${CLAUDE_TOOL_FILE_PATH:-}"

# Tools we care about.
case "$TOOL_NAME" in
  Edit|Write|MultiEdit) ;;
  *) exit 0 ;;
esac

# Empty path = nothing to scan.
[ -z "$FILE_PATH" ] && exit 0

# Scope: only app source code. Match by path segment (handles both absolute and
# project-relative paths Claude Code may pass via tool_input.file_path).
case "$FILE_PATH" in
  *apps/web/src/*|*apps/backend/src/*|*backend/src/*|*web/src/*) ;;
  *) exit 0 ;;
esac

# Skip test files and shell scripts (test scaffolding often touches fs sync).
case "$FILE_PATH" in
  *.test.*|*.spec.*|*.sh) exit 0 ;;
esac

# Read content: existing file for Edit, stdin for Write, existing for MultiEdit.
get_content() {
  if [ "$TOOL_NAME" = "Write" ]; then
    # Claude Code writes a fresh file; we have nothing to scan until the write lands.
    # The next read/edit will catch the sync API. Exit 0 here (best-effort).
    return 1
  fi
  [ -f "$FILE_PATH" ] || return 1
  cat "$FILE_PATH"
}

CONTENT="$(get_content || true)"
[ -z "$CONTENT" ] && exit 0

# Match the antipatterns. Order matters — list each rule with a precise regex
# and its async alternative in the block message.
declare -a HITS=()
declare -a ALTS=()

if grep -qE '\bfs\.readFileSync\b' <<<"$CONTENT"; then
  HITS+=('fs.readFileSync')
  ALTS+=('await fs.promises.readFile(path, "utf8")')
fi
if grep -qE '\bfs\.writeFileSync\b' <<<"$CONTENT"; then
  HITS+=('fs.writeFileSync')
  ALTS+=('await fs.promises.writeFile(path, data)')
fi
if grep -qE '\bfs\.appendFileSync\b' <<<"$CONTENT"; then
  HITS+=('fs.appendFileSync')
  ALTS+=('await fs.promises.appendFile(path, data)')
fi
if grep -qE '\bfs\.existsSync\b' <<<"$CONTENT"; then
  HITS+=('fs.existsSync')
  ALTS+=('await fs.promises.access(path) (try/catch ENOENT)')
fi
if grep -qE '\bfs\.statSync\b' <<<"$CONTENT"; then
  HITS+=('fs.statSync')
  ALTS+=('await fs.promises.stat(path)')
fi
if grep -qE '\bfs\.mkdirSync\b' <<<"$CONTENT"; then
  HITS+=('fs.mkdirSync')
  ALTS+=('await fs.promises.mkdir(path, { recursive: true })')
fi
if grep -qE '\bfs\.rmSync\b' <<<"$CONTENT"; then
  HITS+=('fs.rmSync')
  ALTS+=('await fs.promises.rm(path, { recursive: true, force: true })')
fi
if grep -qE '\bfs\.readdirSync\b' <<<"$CONTENT"; then
  HITS+=('fs.readdirSync')
  ALTS+=('await fs.promises.readdir(path)')
fi

[ "${#HITS[@]}" -eq 0 ] && exit 0

# Build block message.
{
  echo "BLOCKED: synchronous fs API in app code ($FILE_PATH)"
  echo "Antipattern: .claude/rules/antipatterns.md:11 (sync file I/O → async)"
  for i in "${!HITS[@]}"; do
    echo "  - ${HITS[$i]}  →  ${ALTS[$i]}"
  done
  echo "Fix: replace with fs.promises.* (or fs.promises.readFile/writeFile) and await the call."
} >&2

exit 2
