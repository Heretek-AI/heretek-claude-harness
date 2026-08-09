# v3.5 Collector Sprint — Execution Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship v3.5 observability collector sub-spec by closing issues #109-#113 via merged PRs, plus ADR + #2 AC-1 confirmation comment.

**Architecture:** One subagent per issue, one PR per issue, FF-merge to `main`. Per-issue code/tests/acceptance criteria live at `docs/superpowers/plans/2026-08-08-harness-observability-collector.md` — this plan orchestrates that work. Tasks 3a + 3b may run in parallel after Task 2.

**Tech Stack:** Python 3.10+, git, GitHub MCP tools, gh CLI (with MCP fallback per [[issue-30-issue-drafter-plan]]), pytest, jsonschema, merge-and-push skill.

## Global Constraints

- All per-issue code, tests, and acceptance criteria: `docs/superpowers/plans/2026-08-08-harness-observability-collector.md` (5 tasks map 1:1 to issues #109-#113).
- Sprint spec: `docs/superpowers/specs/2026-08-09-v35-collector-sprint-design.md` (goal, scope, DoD, risks).
- Each task's deliverable = one merged PR + one auto-closed issue. NOT one commit.
- All PRs FF-merge to `main`. No squash, no merge commits.
- Branch name pattern: `feat/<issue-number>-<short-slug>` (e.g., `feat/109-telemetry-schema`).
- PR body MUST contain `Closes #<issue-number>` for auto-close.
- `pytest -q` must stay green throughout the entire sprint.
- D11 invariant: `python scripts/validate.py` exits clean; `git diff --exit-code .claude-plugin/marketplace.json` empty.
- D15 invariant: only `plugins/hooks/hooks/hooks.json` modified for hook wiring (Task 3a).
- SonarCloud quality gate must show `success` AND `output.summary.newIssues == 0` (per [[sonarcloud-quality-gate-semantics]]).

## File Structure

This plan creates no new code files. The per-issue plan creates:

```
plugins/hooks/scripts/telemetry_collector.py          # Task 2
plugins/hooks/hooks/hooks.json                         # Task 3 (modified)
scripts/heretek_cli.py                                 # Task 4
tests/fixtures/telemetry_schema.json                   # Task 1
tests/fixtures/telemetry/redacted_session.jsonl        # Task 2
tests/test_telemetry_schema.py                         # Task 1
tests/test_telemetry_collector.py                      # Task 2
tests/test_hooks_json.py                               # Task 3
tests/test_heretek_cli.py                              # Task 4
tests/test_telemetry_retention.py                      # Task 5
docs/telemetry/CHANGELOG.md                            # Task 2
catalog/reviews/observability-sub-spec-1.md            # Task 5
README.md                                              # Task 5 (modified)
```

The sprint plan itself adds:

```
docs/superpowers/plans/2026-08-09-v35-collector-sprint.md   # this file
```

---

### Task 0: Pre-flight verification

**Files:** none modified.

- [ ] **Step 1: Confirm clean main branch**

Run: `git status --short --branch`
Expected: clean working tree, on `main` branch tracking `origin/main`.

- [ ] **Step 2: Read sprint spec and per-issue plan**

Read (in this order):
1. `docs/superpowers/specs/2026-08-09-v35-collector-sprint-design.md` — goal, scope, DoD, risks
2. `docs/superpowers/plans/2026-08-08-harness-observability-collector.md` — per-issue code/tests

Expected: confirmed both files exist and are current.

- [ ] **Step 3: Verify environment green**

Run: `pytest -q && python scripts/validate.py`
Expected: both exit 0.

- [ ] **Step 4: Confirm no blocking PRs**

Run: `gh pr list --state open --limit 10` (fallback to GitHub MCP `list_pull_requests` if `gh` hangs).
Expected: no open PRs that would conflict with collector work.

Done: environment ready for subagent dispatch.

---

### Task 1: Issue #109 — telemetry JSONL schema fixture

**Issue:** #109 — `[harness-observability] Add telemetry JSONL schema fixture`
**Per-issue plan:** Task 1 of `docs/superpowers/plans/2026-08-08-harness-observability-collector.md`
**Files (created by subagent):**
- `tests/fixtures/telemetry_schema.json`
- `tests/test_telemetry_schema.py`

- [ ] **Step 1: Spawn executor subagent**

Dispatch an `executor` subagent (`model=sonnet`) with:
- Issue #109 body (via `mcp__github__github-issue_read`)
- Per-issue plan Task 1 verbatim
- Global constraints from this plan
- Instruction: TDD per plan, commit, open PR with `Closes #109`

- [ ] **Step 2: Subagent reports back**

Expected return: PR URL, commit SHA, brief summary.

- [ ] **Step 3: Verify PR + CI**

- PR body contains `Closes #109` (auto-close wiring)
- PR title matches `[harness-observability] Add telemetry JSONL schema fixture`
- CI green: `gh pr checks <number>` (or GitHub MCP `pull_request_read get_check_runs`) all passing
- SonarCloud quality gate = success, new issues = 0

- [ ] **Step 4: Run merge-and-push skill**

Invoke: `/oh-my-claudecode:merge-and-push` (or `Skill` tool with `merge-and-push`)
Inputs: branch name `feat/109-telemetry-schema`, PR number.
Expected: FF-merge to `main`, branch + worktree cleaned up, push to origin.

- [ ] **Step 5: Verify close**

Run: `git log --oneline main -3` and `mcp__github__github-issue_read 109 method=get`
Expected: merge commit on `main`; issue state = closed; reason = "completed".

- [ ] **Step 6: Local sanity**

Run: `pytest -q tests/test_telemetry_schema.py -v`
Expected: 5 passed.

Done: #109 closed. Advance to Task 2.

---

### Task 2: Issue #110 — telemetry_collector.py hook script

**Issue:** #110 — `[harness-observability] Implement telemetry_collector.py hook script`
**Per-issue plan:** Task 2
**Files (created by subagent):**
- `plugins/hooks/scripts/telemetry_collector.py`
- `tests/test_telemetry_collector.py`
- `docs/telemetry/CHANGELOG.md`
- `tests/fixtures/telemetry/redacted_session.jsonl`

- [ ] **Step 1: Verify Task 1 merged**

Run: `git log --oneline main -3`
Expected: top commit is the #109 merge. If not, STOP — return to Task 1.

- [ ] **Step 2: Spawn executor subagent**

Dispatch `executor` (`model=sonnet`) with:
- Issue #110 body
- Per-issue plan Task 2 verbatim
- Subagent should consume `tests/fixtures/telemetry_schema.json` from Task 1

- [ ] **Step 3: Subagent reports back**

Expected return: PR URL, commit SHA, summary noting coverage ≥90% + P95 < 50ms.

- [ ] **Step 4: Verify PR + CI**

- PR body: `Closes #110`
- CI green; SonarCloud: success + 0 new issues
- Coverage report shows `telemetry_collector.py` ≥90% line coverage

- [ ] **Step 5: Run merge-and-push skill**

Inputs: `feat/110-telemetry-collector`, PR number.

- [ ] **Step 6: Verify close**

`git log --oneline main -3` shows merge commit. `mcp__github__github-issue_read 110` shows state=closed.

- [ ] **Step 7: Local sanity**

Run: `pytest -q tests/test_telemetry_collector.py --cov=plugins/hooks/scripts/telemetry_collector --cov-report=term-missing`
Expected: ≥12 passed; coverage ≥90%.

Done: #110 closed. Tasks 3a + 3b may now run in parallel.

---

### Task 3a: Issue #111 — wire telemetry_collector into hooks.json

**Issue:** #111 — `[harness-observability] Wire telemetry_collector into hooks.json`
**Per-issue plan:** Task 3
**Files (modified/created by subagent):**
- `plugins/hooks/hooks/hooks.json` (modified — append collector entry)
- `tests/test_hooks_json.py` (created)

**Parallel-safe with:** Task 3b. Different files, different reviewers, different subagents.

- [ ] **Step 1: Verify Task 2 merged**

Run: `git log --oneline main -3`
Expected: top commit is the #110 merge. If not, STOP.

- [ ] **Step 2: Spawn executor subagent**

Dispatch `executor` (`model=sonnet`) with:
- Issue #111 body
- Per-issue plan Task 3 verbatim
- D15 reminder: only `plugins/hooks/hooks/hooks.json` is modified

- [ ] **Step 3: Subagent reports back**

Expected: PR URL, commit SHA, summary noting D15 invariant preserved.

- [ ] **Step 4: Verify PR + CI**

- PR body: `Closes #111`
- CI green; SonarCloud: success + 0 new issues
- D15 invariant test `test_no_plugin_ships_hooks_outside_hooks_plugin` passes

- [ ] **Step 5: Run merge-and-push skill**

Inputs: `feat/111-wire-hooks-json`, PR number.

- [ ] **Step 6: Verify close**

Issue #111 state=closed. Merge commit on `main`.

- [ ] **Step 7: Local sanity**

Run: `pytest -q tests/test_hooks_json.py -v`
Expected: 4 passed.

Done: #111 closed. Task 3b may already be in flight (parallel).

---

### Task 3b: Issue #112 — heretek telemetry CLI subcommands

**Issue:** #112 — `[harness-observability] Implement heretek telemetry CLI subcommands`
**Per-issue plan:** Task 4
**Files (created by subagent):**
- `scripts/heretek_cli.py`
- `tests/test_heretek_cli.py`

**Parallel-safe with:** Task 3a. Different files, different reviewers, different subagents.

- [ ] **Step 1: Verify Task 2 merged**

Run: `git log --oneline main -3`
Expected: top commit is the #110 merge. If not, STOP.

- [ ] **Step 2: Spawn executor subagent**

Dispatch `executor` (`model=sonnet`) with:
- Issue #112 body
- Per-issue plan Task 4 verbatim
- Subagent consumes `tests/fixtures/telemetry/redacted_session.jsonl` from Task 2

- [ ] **Step 3: Subagent reports back**

Expected: PR URL, commit SHA, summary noting coverage ≥90% on telemetry subcommand group.

- [ ] **Step 4: Verify PR + CI**

- PR body: `Closes #112`
- CI green; SonarCloud: success + 0 new issues
- Coverage report: `heretek_cli.py` ≥90% line coverage on telemetry group

- [ ] **Step 5: Run merge-and-push skill**

Inputs: `feat/112-telemetry-cli`, PR number.

- [ ] **Step 6: Verify close**

Issue #112 state=closed. Merge commit on `main`.

- [ ] **Step 7: Local sanity**

Run: `pytest -q tests/test_heretek_cli.py -v --cov=scripts/heretek_cli --cov-report=term-missing`
Expected: 8 passed; coverage ≥90%.

Done: #112 closed. Advance to Task 4 (serial — depends on both 3a and 3b).

---

### Task 4: Issue #113 — ADR + retention + close #2 AC-1

**Issue:** #113 — `[harness-observability] ADR + retention + close sub-spec 1`
**Per-issue plan:** Task 5
**Files (modified/created by subagent):**
- `catalog/reviews/observability-sub-spec-1.md` (ADR, follows `catalog/reviews/0000-template.md`)
- `tests/test_telemetry_retention.py`
- `README.md` (adds `heretek telemetry show` example)

- [ ] **Step 1: Verify Tasks 3a + 3b merged**

Run: `git log --oneline main -10`
Expected: top commits include the #109, #110, #111, #112 merges (order may interleave at 3a/3b). If either 3a or 3b missing, STOP.

- [ ] **Step 2: Spawn executor subagent**

Dispatch `executor` (`model=sonnet`) with:
- Issue #113 body
- Per-issue plan Task 5 verbatim
- Instruction: ADR uses `catalog/reviews/0000-template.md` structure; references sub-spec 1 spec + parent spec + issue #2
- Instruction: retention test must call `pytest.skip("zstandard not installed")` if zstd unavailable

- [ ] **Step 3: Subagent reports back**

Expected: PR URL, commit SHA, ADR path, retention test result, README diff snippet.

- [ ] **Step 4: Verify PR + CI**

- PR body: `Closes #113`
- CI green; SonarCloud: success + 0 new issues
- Full repo test suite green: `pytest -q` exits 0

- [ ] **Step 5: Run merge-and-push skill**

Inputs: `feat/113-adr-retention`, PR number.

- [ ] **Step 6: Verify close**

Issue #113 state=closed. Merge commit on `main`.

- [ ] **Step 7: Comment on issue #2 confirming AC-1 met**

Use `mcp__github__github-add_issue_comment` on issue #2 with body:

```
✅ Acceptance criterion 1 met via sub-spec 1 of harness-observability spec.

- Spec: docs/superpowers/specs/2026-08-08-harness-observability-collector.md
- Plan: docs/superpowers/plans/2026-08-08-harness-observability-collector.md
- ADR: catalog/reviews/observability-sub-spec-1.md
- Sprint spec: docs/superpowers/specs/2026-08-09-v35-collector-sprint-design.md

Sub-specs 2 + 3 (test pipeline + eval harness) ship in subsequent sprints and
will consume the collector's JSONL schema.
```

Done: #113 closed. Advance to Task 5 (sprint close-out).

---

### Task 5: Sprint close-out (DoD verification)

**Files:** none modified.

- [ ] **Step 1: Verify all 5 issues closed**

Run: `mcp__github__github-issue_read <n> method=get` for n in 109, 110, 111, 112, 113.
Expected: all state=closed, reason=completed, closed_by PR.

- [ ] **Step 2: Verify 5 merge commits on main**

Run: `git log --oneline main -10`
Expected: 5 new merge commits in dependency order from sprint spec §3 (#111/#112 may interleave).

- [ ] **Step 3: Run full local test suite**

Run: `pytest -q && python scripts/validate.py`
Expected: both exit 0; coverage report shows ≥90% on `telemetry_collector.py` + `heretek_cli.py::telemetry`.

- [ ] **Step 4: Verify D11 invariant**

Run: `git diff --exit-code .claude-plugin/marketplace.json`
Expected: no diff (regenerated file is byte-identical).

- [ ] **Step 5: Verify ADR exists + reads correctly**

Run: `ls -la catalog/reviews/observability-sub-spec-1.md && head -30 catalog/reviews/observability-sub-spec-1.md`
Expected: file exists, follows `0000-template.md` structure.

- [ ] **Step 6: Verify issue #2 has AC-1 confirmation comment**

Run: `mcp__github__github-issue_read 2 method=get_comments`
Expected: latest comment contains "Acceptance criterion 1 met" + spec/ADR links.

- [ ] **Step 7: Verify README has telemetry example**

Run: `grep -A2 "telemetry show" README.md`
Expected: at least one `python scripts/heretek_cli.py telemetry ...` example.

- [ ] **Step 8: Comment on parent issue #126 with progress**

Use `mcp__github__github-add_issue_comment` on issue #126 with body:

```
Sub-spec 1 (collector) shipped via PRs closing #109-#113. ADR accepted.
Issue #2 AC-1 confirmed met.

Remaining v3.5 sub-specs:
- Sub-spec 2 (test pipeline): #114-#118
- Sub-spec 3 (eval harness): #119-#124

Next sprint candidates TBD.
```

Done: sprint complete.

---

## Self-Review

**1. Spec coverage (sprint spec §1-7):**
- §1 Goal — Tasks 1-4 (5 issues closed) + Task 4 step 7 (#2 AC-1 comment) + Task 5 step 6 (verify comment)
- §2 Scope — only collector work; #150 and sub-specs 2/3 explicitly excluded (Task 0 step 4)
- §3 Sequence — Tasks 1, 2, 3a, 3b, 4 follow dep graph; 3a/3b parallel-safe noted
- §4 Execution mechanics — pre-flight checklist (Task 0), subagent dispatch + PR + FF-merge per task, post-merge verification per task
- §5 DoD — Task 5 verifies each of the 7 DoD criteria
- §6 Risk register — R5 (gh CLI hang) covered in Tech Stack note; R3 (D11 drift) in global constraints; R7 (out-of-order) in each task's "Verify X merged" step
- §7 Re-evaluation triggers — out of scope for plan (operational decision per session)

**2. Placeholder scan:** No "TBD", "TODO", "implement later", "appropriate error handling", "similar to Task N", or "fill in details". All steps have concrete commands, exact paths, or explicit subagent instructions.

**3. Type/identifier consistency:**
- Branch names: `feat/109-...` through `feat/113-...` — consistent pattern across tasks
- PR body marker: `Closes #<n>` — consistent
- Subagent invocation: `executor` + `model=sonnet` — consistent
- Issue references: #109-#113 — all consistent
- File paths reference per-issue plan Task N consistently

No fixes needed.