# Heretek Harness Trim — Design Spec

**Date**: 2026-08-10
**Status**: Approved (brainstorming session)
**Branch**: `trim/spec` → `main` after this lands
**Implementation plan**: `docs/superpowers/plans/2026-08-10-heretek-harness-trim-plan.md` (writing-plans output)
**Parent audit**: in-conversation, 2026-08-10

## Context

The `heretek-claude-harness` marketplace repo was audited on 2026-08-10 across four
dimensions: prompt architecture, skills/commands, mechanical gates, and codebase
hygiene. The audit produced four sections:

1. **Immediate Deletions** — 16 targets (4 spike scripts, build artifacts, 2 shallow
   utility modules, 1 duplicated hook entry, 9 self-referential audit files).
2. **CLAUDE.md & Skill Compaction** — `CLAUDE.md` 76 → 14 lines, `scripts/ci.sh`
   wrapper, 5 of 7 skills compressed (catalog, merge-and-push, refresh-pins,
   issue-loop, sonarcloud-*).
3. **Mechanical Gate Architecture** — 7 gaps (G1-G7) in the existing 3-layer gate.
4. **Refactoring Roadmap** — 14 actions: 6 Strong, 4 Worth Exploring, 4 Speculative.

The marketplace is on v1.0.0 (frozen 2026-08-05). v2-v6 are in flight. The audit
is pure structural; no behavior changes outside `scripts/issue_loop.py` collapse.

## Goals

1. **Mechanical gate over prompt guidance.** Replace prose rules with deterministic
   hooks, scripts, and CI checks. The agent must be physically blocked.
2. **Deep modules not shallow.** Inline `_allowlist.py`, `_http.py`. Consolidate
   the 4 hooks that currently live outside `plugins/hooks/scripts/` (D15 locality
   violation).
3. **Zero token waste.** Strip descriptive prose from `CLAUDE.md` and the 5
   prompt-heavy skills. Every byte must govern behavior or execute a command.
4. **Deterministic self-correction.** Build feedback loops around tool output
   (post_tool_dispatcher, secrets_pre_tool, ci.sh).

## Non-Goals

- No new plugins, no new features, no D7 bar changes.
- No first-party plugin source code changes (output-styles, agents, skills content
  inside plugins/ stays as-is).
- No CI workflow additions (existing 7 workflows are sufficient; we wire into
  them).
- No telemetry schema changes.

## Architecture (post-merge)

### Repository layout

```
heretek-claude-harness/
├── CLAUDE.md                           # 14 lines (was 76)
├── PLAN.md                             # DELETED (subsumed by roadmap.md)
├── scripts/
│   ├── ci.sh                           # NEW — single local-CI entry
│   ├── validate.py                     # unchanged
│   ├── generate_marketplace.py         # unchanged
│   ├── refresh_pins.py                 # _http.py inlined
│   ├── heretek_cli.py                  # unchanged
│   ├── harness_test.py                 # unchanged
│   ├── issue_drafter.py                # plan_pre_flight.py inlined
│   ├── issue_loop.py                   # NEW (S1 — 10 files collapsed into 1)
│   ├── audit/                          # verify-then-decide → DELETE or fold
│   └── __pycache__/ ...                # DELETED (gitignored)
├── plugins/hooks/
│   ├── hooks/hooks.json                # 5 PostToolUse entries → 1 dispatcher entry
│   ├── scripts/
│   │   ├── fast_gate.py                # unchanged
│   │   ├── quality_gate.py             # unchanged
│   │   ├── telemetry_collector.py      # _allowlist.py inlined
│   │   ├── post_tool_dispatcher.py     # NEW — multiplexer
│   │   ├── secrets_pre_tool.py         # NEW — PreToolUse gate
│   │   ├── drift_detector.py           # MOVED from scripts/
│   │   ├── lookup_gate.py              # MOVED from scripts/ + _allowlist.py inlined
│   │   ├── stale_dep_intercept.py      # MOVED from scripts/
│   │   └── forbidden_pattern_scanner.py# MOVED from scripts/scanners/
│   ├── .pre-commit-config.yaml         # +secrets_pre_tool +ci.sh hook
│   └── commands/.gitkeep, hooks/.gitkeep, scripts/.gitkeep  # DELETED (dirs non-empty)
├── tests/
│   ├── test_audit_* (9 files)          # DELETED if scripts/audit/ removed
│   ├── test_issue_loop_* (12 files)    # REBASED to scripts/issue_loop.py (S1)
│   └── ... existing tests preserved
├── coverage.xml, .coverage             # DELETED (CI artifacts)
└── docs/superpowers/specs/2026-08-10-heretek-harness-trim-design.md  # THIS DOC
```

### Hook chain (post-merge)

| Stage | Matcher | Commands | Timeout |
|---|---|---|---|
| PreToolUse | `Edit\|Write\|MultiEdit` | `fast_gate.py` (ruff/biome/rustfmt) | 1000 ms |
| PreToolUse | `Edit\|Write\|MultiEdit` | `secrets_pre_tool.py` (NEW — 50ms secret regex sweep) | 200 ms |
| PostToolUse | `Edit\|Write\|MultiEdit\|Read\|Bash` | `post_tool_dispatcher.py` (NEW — fans out to 4 async hooks + telemetry) | 2000 ms |
| Pre-commit | `*.py\|*.json\|*.ts\|...` | ruff, ruff-format, biome-check, shellcheck, gitleaks, heretek-fast-gate | (pre-commit framework) |
| Pre-commit | (smoke) | `scripts/ci.sh` | (pre-commit framework) |
| Manual pre-PR | n/a | `scripts/ci.sh` | n/a |

The 5-entry PostToolUse fan-out in the current `hooks.json` is replaced by a single
dispatcher that subprocesses each analyzer and aggregates their `additionalContext`
JSON outputs. This cuts hook-process startup from 5× to 1× per Edit.

### Data flow (Edit lifecycle)

```
Agent issues Edit tool call
  │
  ▼
PreToolUse: fast_gate.py
  │ exit 0  → allow (lint passed)
  │ exit 2  → block (linter violations, Claude Code reads stderr as denial reason)
  │ timeout → fail-open (allow)
  ▼
PreToolUse: secrets_pre_tool.py
  │ exit 0  → allow (no secrets detected)
  │ exit 2  → block (secret pattern matched, file_path + matched line to stderr)
  │ timeout → fail-open (allow)
  ▼
Tool executes
  ▼
PostToolUse: post_tool_dispatcher.py
  │ reads payload
  │ subprocess: stale_dep_intercept.py  (timeout 2s)
  │ subprocess: forbidden_pattern_scanner.py (timeout 2s)
  │ subprocess: drift_detector.py (timeout 500ms)
  │ subprocess: lookup_gate.py (timeout 500ms)
  │ subprocess: telemetry_collector.py (timeout 200ms, always async)
  │ aggregates JSON additionalContext outputs
  │ exit 0 with one consolidated JSON to stdout
  ▼
Agent sees aggregated warnings as additionalContext
  │
  ▼
git commit invoked
  │
  ▼
Pre-commit: ruff + ruff-format + biome-check + shellcheck + gitleaks + heretek-fast-gate + ci.sh
  │ exit 0 → commit lands
  │ exit ≠ 0 → commit blocked, stderr fed to agent
  ▼
PR opened
  │
  ▼
CI: validate.yml (pytest + validate.py + generate_marketplace.py + smoke)
```

## Components

### New files

| Path | Purpose |
|---|---|
| `scripts/ci.sh` | Single local-CI entry: `pytest -q && validate.py && generate_marketplace.py && git diff --exit-code marketplace.json && smoke`. Replaces the 5-line bash block currently in `CLAUDE.md`. |
| `scripts/worktree_gc.sh` | Weekly cron: `git worktree list` → prune detached HEADs older than 7 days. Optional — deferred to plan if cron target is uncertain. |
| `plugins/hooks/scripts/post_tool_dispatcher.py` | Reads hook payload, fans out to 4 async analyzers + telemetry via subprocess, aggregates `additionalContext` JSON. |
| `plugins/hooks/scripts/secrets_pre_tool.py` | PreToolUse secret detection. Pure stdlib regex sweep: AWS keys, GitHub PATs, JWT tokens, generic high-entropy strings. <50ms budget. |

### Modified files

| Path | Change |
|---|---|
| `CLAUDE.md` | 76 lines → 14 lines. Replaces prose tables with `scripts/ci.sh` invocations and CLI commands. |
| `plugins/hooks/hooks/hooks.json` | PreToolUse: add `secrets_pre_tool.py`. PostToolUse: 5 entries → 1 dispatcher entry. |
| `plugins/hooks/.pre-commit-config.yaml` | Add a `local` hook entry that runs `scripts/ci.sh` after the existing pre-commit stages. |
| `scripts/refresh_pins.py` | Inline `_http.py` constants. |
| `scripts/issue_drafter.py` | Inline `plan_pre_flight.py` (same domain). |
| `plugins/hooks/scripts/telemetry_collector.py` | Inline `_allowlist.py` `require_session_id()`. |
| `plugins/hooks/scripts/lookup_gate.py` (moved) | Inline `_allowlist.py` `require_session_id()`. |
| `plugins/hooks/scripts/drift_detector.py` (moved) | Inline `_allowlist.py` `require_session_id()`. |
| `plugins/hooks/scripts/forbidden_pattern_scanner.py` (moved) | Path update only — moves from `scripts/scanners/` to `plugins/hooks/scripts/`. |
| `plugins/hooks/scripts/stale_dep_intercept.py` (moved) | Path update only — moves from `scripts/` to `plugins/hooks/scripts/`. |

### Deleted files

| Path | Reason |
|---|---|
| `scripts/counterfactual_diffs_spike.py` | R5 — spike, results in docs/superpowers/spikes/. |
| `scripts/rlm_fast_gate_spike.py` | R5 |
| `scripts/staleness_metric_spike.py` | R5 |
| `scripts/svok_provenance_spike.py` | R5 |
| `scripts/_allowlist.py` | R2 — inlined into 2 callers. |
| `scripts/_http.py` | R3 — inlined into `refresh_pins.py`. |
| `scripts/plan_pre_flight.py` | R10 — inlined into `issue_drafter.py`. |
| `scripts/audit/` (entire dir, 7 .py + 9 test files) | R4 — verify-then-decide. **Default: delete** unless audit subpackage is wired to a user-facing entry-point. |
| `scripts/issue_loop/{__init__,branch,classifier,driver,gate,ledger,merge,subagents,autopilot_drain,cli}.py` | S1 — collapsed into `scripts/issue_loop.py`. |
| `tests/test_audit_*` (9 files) | R4 — if `scripts/audit/` deleted. |
| `tests/test_issue_loop_*` (12 files) | S1 — rebased onto `scripts/issue_loop.py`. |
| `PLAN.md` | Subsumed by `docs/superpowers/roadmap.md`. |
| `coverage.xml`, `.coverage` | Build artifacts. |
| `__pycache__/` (10 dirs) | Already standard gitignore; ensure it's in `.gitignore`. |
| `plugins/hooks/{commands,hooks,scripts}/.gitkeep` | Directories non-empty; markers add noise. |
| `reports/skills-pack-headroom.json` | One-off measurement. |
| `reports/baseline/` | One-off baseline. |
| `catalog/raw/skills-lock.json` | Verify use; delete if orphaned. |

## Error handling

| Failure | Action | Surface |
|---|---|---|
| `fast_gate.py` lint violation | exit 2 | stderr → Claude Code reads as denial |
| `fast_gate.py` timeout | exit 0 (fail-open) | stderr warning only |
| `secrets_pre_tool.py` match | exit 2 | stderr with file_path + matched line |
| `secrets_pre_tool.py` timeout | exit 0 (fail-open) | stderr warning only |
| `post_tool_dispatcher.py` child timeout | continue with remaining children | aggregated JSON omits timed-out child |
| `post_tool_dispatcher.py` child crash | continue with remaining children | aggregated JSON includes `{"child": "...", "error": "..."}` |
| `ci.sh` test failure | exit 1 with first failure | agent sees pytest output |
| `ci.sh` marketplace.json drift | exit 1 with diff | agent regenerates |
| pre-commit hook failure | exit non-zero | stderr → blocks commit |
| CI failure on PR | block merge | PR comment |

## Testing

### Existing tests (preserve)

- `tests/test_fast_gate.py`, `tests/test_quality_gate.py`, `tests/test_hooks_manifest.py`
  — unchanged (Layer 1 + manifest).
- `tests/test_security_scan.py`, `tests/test_aitmpl_vetting.py`,
  `tests/test_catalog_vetting.py`, `tests/test_generate_marketplace.py` — unchanged.
- `tests/test_dependencies.py`, `tests/test_validate.py`, `tests/test_workflows.py` — unchanged.
- `tests/test_precommit_config.py`, `tests/test_precommit_workflow.py` — unchanged.
- `tests/test_plugin_components.py`, `tests/test_p1_batch.py` — unchanged.
- `tests/test_telemetry_*.py`, `tests/test_scanner_*.py` — unchanged.

### New tests

| Test | Purpose |
|---|---|
| `tests/test_post_tool_dispatcher.py` | Subprocess fan-out, JSON aggregation, per-child timeout, child crash isolation. |
| `tests/test_secrets_pre_tool.py` | AWS key / GitHub PAT / JWT detection on synthetic payloads. False-positive tolerance. |
| `tests/test_ci_sh.sh` | `scripts/ci.sh` exits 1 on simulated marketplace drift; exits 0 on clean tree. |
| `tests/test_audit_subpackage_wired.py` | (PR2 only) Verify `scripts/audit/` has a user-facing entry-point before deciding to delete. |
| `tests/test_issue_loop.py` (replaces 12 files) | End-to-end exercise of the collapsed S1 module. |

### Smoke tests

- `bash tests/smoke/fast_gate_smoke.sh` — unchanged.
- `bash catalog/tests/smoke_test.sh` — unchanged.
- New: `bash scripts/ci.sh` invoked from pre-commit hook to exercise the full pipeline.

## 5-PR execution sequence

PRs are stacked: each PR merges to `main` before the next begins.

### PR1 — R5 spike deletions (pure deletions)

**Branch**: `trim/r5-spike-purge`
**Files deleted** (4): `scripts/counterfactual_diffs_spike.py`, `rlm_fast_gate_spike.py`, `staleness_metric_spike.py`, `svok_provenance_spike.py`.
**Files deleted** (build artifacts): `coverage.xml`, `.coverage`, `reports/skills-pack-headroom.json`, `reports/baseline/*`, all `__pycache__/` directories, `PLAN.md`.
**Acceptance**: `git ls-files | grep -E 'spike|coverage\.xml|\.coverage$' | wc -l` returns 0. All existing tests pass.
**Risk**: Trivial. Pure deletions, no behavior change.

### PR2 — R4 audit verify-then-decide

**Branch**: `trim/r4-audit-decide`
**Pre-condition**: Run `python -c "import scripts.audit; print(scripts.audit.__file__)"` — if it imports cleanly via any user-facing CLI command in `heretek_cli.py`, fold; else delete.
**Default path** (no consumer): delete `scripts/audit/` (7 .py + 9 tests). Update `scripts/audit/__pycache__/` and any test references in `conftest.py`.
**Acceptance**: `git ls-files scripts/audit/ | wc -l` returns 0 (or `scripts/health.py` exists with the same surface). All existing tests pass.
**Risk**: Medium — must verify no upstream consumer.

### PR3 — R2+R3 inline shallow utils

**Branch**: `trim/r2-r3-inline-utils`
**Files deleted**: `scripts/_allowlist.py`, `scripts/_http.py`.
**Files modified**: `plugins/hooks/scripts/telemetry_collector.py`, `lookup_gate.py`, `drift_detector.py` (inline `require_session_id()`); `scripts/refresh_pins.py` (inline `DEFAULT_TIMEOUT = 30`).
**Acceptance**: `grep -rn "_allowlist\|_http" scripts/ plugins/ --include="*.py"` returns nothing. All existing tests pass.
**Risk**: Low — pure inlining with test coverage.

### PR4 — R1+R6+R7+R11 hooks locality + dispatcher + secrets + ci.sh hook

**Branch**: `trim/r1-r6-r7-r11-hooks-and-gates`
**Files moved**: `scripts/{drift_detector,lookup_gate,stale_dep_intercept}.py` → `plugins/hooks/scripts/`. `scripts/scanners/forbidden_pattern_scanner.py` → `plugins/hooks/scripts/`.
**Files new**: `plugins/hooks/scripts/post_tool_dispatcher.py`, `plugins/hooks/scripts/secrets_pre_tool.py`, `scripts/ci.sh`.
**Files modified**: `plugins/hooks/hooks/hooks.json` (5 entries → 1 dispatcher + 1 secrets gate), `plugins/hooks/.pre-commit-config.yaml` (+ ci.sh hook).
**Acceptance**:
- `git ls-files plugins/hooks/scripts/ | wc -l` returns 9.
- `python plugins/hooks/scripts/post_tool_dispatcher.py < test_payload.json` exits 0 with consolidated JSON.
- `python plugins/hooks/scripts/secrets_pre_tool.py < secret_payload.json` exits 2.
- `bash scripts/ci.sh` exits 0 on clean tree.
- All existing tests pass + new tests pass.
**Risk**: Highest in the sequence. Touches the agent's hook chain. Must run pre-commit + smoke + smoke-test.yml locally before push.

### PR5 — §2 + R8-R10 + S1-S4 compaction + collapse

**Branch**: `trim/r8-r10-s1-s4-compaction-and-collapse`
**Files modified**: `CLAUDE.md` (76 → 14 lines), `scripts/issue_drafter.py` (inline `plan_pre_flight.py`), `scripts/issue_loop.py` (S1 collapse from 10 files).
**Files deleted**: 12 `tests/test_issue_loop_*.py` (rebased to single test file).
**Skill files modified**: `catalog/SKILL.md`, `merge-and-push/SKILL.md`, `refresh-pins/SKILL.md`, `issue-loop/SKILL.md`, `sonarcloud-suppression/SKILL.md`, `sonarcloud-batch-remediation/SKILL.md`.
**Files added**: `docs/SONAR-SUPPRESSION.md`, `docs/SONAR-BATCH-REMEDIATION.md` (move body out of skills, leave skeleton).
**Acceptance**:
- `wc -l CLAUDE.md` returns 14.
- `scripts/issue_loop.py` exists with `Ledger`, `Dispatcher`, `Autopilot` classes.
- All 12 `test_issue_loop_*.py` replaced with `test_issue_loop.py`.
- All 5 skills fit in ≤40 lines each.
- All existing tests pass + new tests pass.
**Risk**: Highest LOC. The S1 collapse touches 10 module boundaries.

## Acceptance criteria (per-PR exit + integrated end-state)

| PR | Entry | Exit |
|---|---|---|
| 1 | Repo clean, all tests green | 4 spike scripts + build artifacts gone, all tests green |
| 2 | PR1 merged | `scripts/audit/` deleted or folded, all tests green |
| 3 | PR2 merged | `_allowlist.py` + `_http.py` deleted, 3 callers updated, all tests green |
| 4 | PR3 merged | 4 hooks moved into `plugins/hooks/scripts/`, dispatcher + secrets gate active, ci.sh works, all tests green |
| 5 | PR4 merged | CLAUDE.md ≤ 14 lines, issue_loop collapsed, skills ≤ 40 lines each, all tests green |

**Integrated end-state** (all 5 PRs merged):
- `CLAUDE.md` ≤ 14 lines.
- `scripts/` root: 7 files (was 24).
- `plugins/hooks/scripts/`: 9 files (was 3 + 4 misplaced).
- `hooks.json` PostToolUse entries: 1 (was 5).
- `_allowlist.py` + `_http.py`: gone.
- 4 spike scripts: gone.
- `scripts/ci.sh`: present, runs green on clean tree.
- All existing tests pass.
- Zero new behavior in user-facing commands.

## Open questions

- **`scripts/audit/`** wired or not? (PR2 resolves via `scripts/audit/wired_check.py`.)
- **`scripts/worktree_gc.sh`** — add now or defer? (Default: defer to a separate spec.)
- **`catalog/raw/skills-lock.json`** — used by any scanner? (Default: delete if orphaned.)
- **`etc/passwd`** — test fixture, committed? (Verify `.gitignore`.)

## References

- Audit report (in-conversation, 2026-08-10)
- `CLAUDE.md` (current)
- `docs/superpowers/specs/2026-08-03-heretek-marketplace-design.md` (D1-D17)
- `docs/superpowers/specs/2026-08-10-precommit-mechanical-gates-design.md` (D30, D37)
- `catalog/forbidden_patterns.yaml` (scanner input)
- `.github/workflows/validate.yml`, `pre-commit.yml`, `shellcheck.yml`, `security-scan*.yml`, `smoke-test.yml`, `spec-issue-hygiene.yml`
