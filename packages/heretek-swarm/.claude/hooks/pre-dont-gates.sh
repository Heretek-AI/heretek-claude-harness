#!/usr/bin/env bash
# pre-dont-gates.sh — Phase 1 Don't-section enforcer.
#
# Hook event: PreToolUse (Edit|Write|Bash|Agent)
# Matcher:    Edit|Write|Bash|Agent (configured in .claude/settings.json)
# Source of truth: docs/superpowers/specs/2026-06-22-hooks-audit.md
#                  rows 64, 66, 68, 69
#                  + CLAUDE.md "Don't" section
#
# Implements four gates in one cohesive scan:
#   Gate 64 — Q1 OSS refs reference-only:
#     Block Edit/Write/MultiEdit (but allow Read) inside
#     `review/pax-historia/` or `review/Phos/`.
#   Gate 66 — Q9 milestone-batch merge:
#     Block Bash `git merge` of a `rebuild/*` branch into main unless
#     MILESTONE_MERGE=1 env or `.claude/state/MILESTONE` marker file exists.
#   Gate 68 — don't use binary-RE agents:
#     Block Agent tool calls where subagent_type matches
#     /reverse-engine|reverse-engineer|agent-reverse/.
#   Gate 69 — don't auto-push to submodules:
#     Block Bash `git push` when cwd (or any --git-dir argument) is inside
#     backend/ web/ docs/ presets/ tools/pax-ripper/ submodule worktrees.
#
# Protocol: exit 0 = allow, exit 2 + stderr reason = block, exit 0 + stderr
# warning = soft warn. Stdin is the PreToolUse JSON envelope.

set -euo pipefail

# Read the PreToolUse JSON envelope from stdin FIRST — Claude Code passes the
# tool call as JSON on stdin, not via env vars. Derive tool_name from it.
INPUT="$(cat || true)"

# Helper: extract a JSON string field via grep/sed (no jq dependency — hooks
# must be portable and run before any app code).
# Wrapped in `|| true` because `head -n1` closes the pipe early and grep
# exits 1 with SIGPIPE under `set -o pipefail`.
json_field() {
  local field="$1" raw
  raw="$(printf '%s' "$INPUT" \
    | { grep -oE "\"${field}\"[[:space:]]*:[[:space:]]*\"[^\"]*\"" || true; } \
    | { head -n1 || true; })"
  [[ -z "$raw" ]] && return 1
  printf '%s' "$raw" | sed -E "s/^\"${field}\"[[:space:]]*:[[:space:]]*\"(.*)\"$/\\1/"
}

# Helper: check if a substring appears in input.
contains() { [[ "$1" == *"$2"* ]]; }

# Derive tool_name from the stdin JSON envelope (Claude Code passes
# {"tool_name":"Edit","tool_input":{...}}). Fall back to env for the legacy
# test harness that set CLAUDE_TOOL_NAME directly.
TOOL_NAME="$(json_field tool_name 2>/dev/null || echo "")"
[ -z "$TOOL_NAME" ] && TOOL_NAME="${CLAUDE_TOOL_NAME:-}"

# Only act on the tools we care about.
case "$TOOL_NAME" in
  Edit|Write|MultiEdit|Bash|Agent) ;;
  *) exit 0 ;;
esac

# ---------- Gate 64: don't port code from review/pax-historia or review/Phos ----------
gate_64_review_paths() {
  local file_path="$1"
  # Allow Read — only Edit/Write/MultiEdit are gated.
  case "$TOOL_NAME" in
    Edit|Write|MultiEdit) ;;
    *) return 0 ;;
  esac
  case "$file_path" in
    *review/pax-historia/*|*review/Phos/*)
      {
        echo "BLOCKED: don't port code from review/pax-historia or review/Phos (Q1)"
        echo "Source: CLAUDE.md:123, docs/superpowers/specs/2026-06-22-hooks-audit.md:row 64"
        echo "Path: $file_path"
        echo "Rule: reference only — patterns/UX, never port code"
        echo "Fix: extract the pattern into a note in Reverse-Engineering/ or docs/, then implement from scratch in your own submodule."
      } >&2
      exit 2
      ;;
  esac
}

# ---------- Gate 66: don't merge rebuild items outside milestone gates ----------
gate_66_milestone_merge() {
  local cmd="$1"
  [[ "$TOOL_NAME" == "Bash" ]] || return 0
  # Only block `git merge` invocations.
  contains "$cmd" "git merge" || return 0

  # Detect `rebuild/*` branch on the command line. Patterns:
  #   git merge rebuild/foo            (branch)
  #   git merge rebuild/foo --ff-only  (branch + flags)
  #   git merge origin rebuild/foo     (origin + branch)
  #   git merge --no-ff rebuild/foo    (flag + branch)
  # We grep for "rebuild/" as a standalone token to avoid catching refs like
  # "myrebuild/foo" or "feature/rebuild-thing".
  local branch=""
  branch="$(printf '%s' "$cmd" | { grep -oE '\brebuild/[A-Za-z0-9._/-]+' || true; } | { head -n1 || true; })"
  [[ -z "$branch" ]] && return 0

  # Gate open? MILESTONE_MERGE=1 env or .claude/state/MILESTONE marker file.
  if [[ "${MILESTONE_MERGE:-}" == "1" ]]; then return 0; fi
  if [[ -f "${CLAUDE_PROJECT_DIR:-.}/.claude/state/MILESTONE" ]]; then return 0; fi

  {
    echo "BLOCKED: rebuild-branch merge outside milestone gate (Q9)"
    echo "Source: CLAUDE.md:125, docs/superpowers/specs/2026-06-22-hooks-audit.md:row 66"
    echo "Command: $cmd"
    echo "Branch: $branch"
    echo "Fix: set MILESTONE_MERGE=1 or touch .claude/state/MILESTONE; feature branches are held until P0/P1/P2/P3 milestone."
  } >&2
  exit 2
}

# ---------- Gate 68: don't use binary-RE agents ----------
gate_68_binary_re_agent() {
  local agent_type="$1"
  [[ "$TOOL_NAME" == "Agent" ]] || return 0
  # Bash regex anchored with ERE; the brief specifies these exact names.
  if [[ "$agent_type" =~ (reverse-engine|reverse-engineer|agent-reverse) ]]; then
    {
      echo "BLOCKED: binary-RE agent disabled (wrong domain: web app, not binary RE)"
      echo "Source: CLAUDE.md:127, docs/superpowers/specs/2026-06-22-hooks-audit.md:row 68"
      echo "Subagent type: $agent_type"
      echo "Fix: use a project-fit agent — Explore (built-in) for code search, ecc:code-explorer or feature-dev:code-explorer for deep architecture. See .claude/rules/agent-routing.md."
    } >&2
    exit 2
  fi
}

# ---------- Gate 69: don't auto-push to submodules ----------
gate_69_submodule_push() {
  local cmd="$1"
  [[ "$TOOL_NAME" == "Bash" ]] || return 0
  contains "$cmd" "git push" || return 0

  # Determine the cwd Claude Code is using. CLAUDE_TOOL_BASH_CWD is set by
  # the harness; fall back to $(pwd) which is the bash tool's CWD.
  local cwd="${CLAUDE_TOOL_BASH_CWD:-$(pwd)}"

  # Normalize: take the absolute path, walk until we find a submodule marker.
  # The submodule dirs themselves (when gitlinked) are real directories with
  # their own .git/. Submodule WORKTREES are clones outside the parent and
  # also contain .git/. We detect both shapes: an absolute path that contains
  # one of the submodule names as a path segment.
  local submodule_hit=""
  case "$cwd" in
    *"/backend/"*|*"/backend"|*"/web/"*|*"/web"|*"/docs/"*|*"/docs"|*"/presets/"*|*"/presets"|*"/tools/pax-ripper/"*|*"/tools/pax-ripper")
      submodule_hit="$(printf '%s' "$cwd" | { grep -oE '/(backend|web|docs|presets|tools/pax-ripper)(/|$)' || true; } | { head -n1 || true; })"
      ;;
  esac
  [[ -z "$submodule_hit" ]] && return 0

  {
    echo "BLOCKED: don't auto-push to submodules (manual commits only)"
    echo "Source: CLAUDE.md:128, docs/superpowers/specs/2026-06-22-hooks-audit.md:row 69"
    echo "Command: $cmd"
    echo "CWD: $cwd (inside $submodule_hit submodule)"
    echo "Fix: commit locally and let the user push manually. Submodule updates go through the parent repo's worktree flow."
  } >&2
  exit 2
}

# ---------- Dispatch ----------

FILE_PATH="$(json_field file_path 2>/dev/null || echo "")"
COMMAND="$(json_field command 2>/dev/null || echo "")"
AGENT_TYPE="$(json_field subagent_type 2>/dev/null || echo "")"

# Order matters only for clarity; each gate exits on its own block.
gate_64_review_paths "$FILE_PATH"
gate_66_milestone_merge "$COMMAND"
gate_68_binary_re_agent "$AGENT_TYPE"
gate_69_submodule_push "$COMMAND"

exit 0
