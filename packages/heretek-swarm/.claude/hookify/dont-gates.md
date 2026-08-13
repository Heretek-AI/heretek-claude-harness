# Don't Gates — Phase 1 hookify rule

Single hook script enforcing the four "Don't" rules from `CLAUDE.md` that are
genuinely useful NOW (no app-code dependency):

| Row | Rule | Source | Tool(s) gated |
|---|---|---|---|
| 64 | don't port code from `review/pax-historia/` or `review/Phos/` (Q1) | CLAUDE.md:123 | Edit \| Write \| MultiEdit (Read allowed) |
| 66 | don't merge `rebuild/*` outside milestone gate (Q9) | CLAUDE.md:125 | Bash (`git merge …`) |
| 68 | don't use binary-RE agents (wrong domain: web app) | CLAUDE.md:127 | Agent (subagent_type regex) |
| 69 | don't auto-push to submodules (manual commits only) | CLAUDE.md:128 | Bash (`git push` in submodule dirs) |

## Wiring

`.claude/settings.json` → `hooks.PreToolUse[0]` → matcher
`Edit|Write|Bash|Agent` → `bash .claude/hooks/pre-dont-gates.sh`.

The hook reads the PreToolUse JSON envelope from stdin and dispatches to one
of four gates based on `tool_name` and the relevant field.

## Gate details

### Gate 64 — Q1 reference-only

- **Trigger:** `Edit|Write|MultiEdit` and `file_path` contains
  `review/pax-historia/` or `review/Phos/`.
- **Allows:** `Read` (reference is fine, copying is not).
- **Block message:** reference-only reminder + suggest extracting the
  pattern into a `Reverse-Engineering/` note.
- **Exit code:** 2.

### Gate 66 — Q9 milestone-batch merge

- **Trigger:** `Bash` and command contains `git merge <something>` where
  `<something>` matches `\brebuild/[A-Za-z0-9._/-]+`.
- **Allows:** merges outside the rebuild/ namespace, or when
  `MILESTONE_MERGE=1` is exported OR `.claude/state/MILESTONE` file
  exists (one of the two opens the gate).
- **Block message:** lists the branch + explains milestone-batch policy.
- **Exit code:** 2.

### Gate 68 — binary-RE agent block

- **Trigger:** `Agent` and `subagent_type` matches
  `/(reverse-engine|reverse-engineer|agent-reverse)/`.
- **Allows:** any other subagent_type.
- **Block message:** points at Explore / `ecc:code-explorer` /
  `feature-dev:code-explorer` as the project-fit alternatives, with link
  to `.claude/rules/agent-routing.md`.
- **Exit code:** 2.

### Gate 69 — submodule auto-push block

- **Trigger:** `Bash` and command contains `git push`, AND cwd is inside
  one of `backend/`, `web/`, `docs/`, `presets/`, `tools/pax-ripper/`
  (detected as path segment, so submodule worktrees outside the parent
  also match).
- **Allows:** pushes from the parent repo or non-submodule worktrees;
  any non-`git push` command in submodules.
- **Block message:** explains the manual-commit-only policy + points at
  parent-repo worktree flow.
- **Exit code:** 2.

## Why four-in-one

These four rules are one logical change ("enforce the Don't section of
CLAUDE.md"). One worktree + one commit is correct, not four — mirrors the
spec's one-cohesive-cluster pattern (Q9 batch merge, not per-rule
fragmentation).

## Out of scope (deferred)

- **Row 65** (don't edit `DEFINITIVE_GOALS.md` without drift evidence) —
  PreToolUse cannot inspect conversation message history to verify drift
  evidence. Enforced via human review at Phase 2 drift protocol.
- **Rows 14–28** (subagent routing for project-fit agents) — high
  false-positive risk on the 15-entry wrong-stack list; needs Phase 2
  live validation.
- **Rows 33–36, 38, 39** (other antipatterns) — no app code exists yet;
  scanner has nothing to guard. Resolves in Phase 4 when rebuild creates
  the guarded app code.
- **Rows 29–32** (review-gate auto-invocations) — depend on agent-routing
  gates (14–28) being resolved first to avoid wrong-stack review agents.
- **Row 40** (worktree enforcement) — heuristic unproven; live in Phase 4.
- **Rows 71, 72** (rule-file SessionStart loads) — low value; rules
  already load via CLAUDE.md import.
