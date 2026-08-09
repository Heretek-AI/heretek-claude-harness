# Mixed-Tactical Sprint — Execution Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship 7 mixed-tactical items (1 CI + 6 tech-debt) via 7 PRs, all FF-merged to main. Closes #150, #169, #170, #171, #172, #173, #174.

**Architecture:** One subagent per issue, one PR per issue, FF-merge to `main`. Issues are self-describing — no per-issue code transcription needed (unlike the v3.5 collector sprint where the per-issue plan had full code). Each subagent reads the issue body, implements the requirements, runs tests, commits, opens PR.

**Tech Stack:** Python 3.10+, git, GitHub MCP tools, gh CLI, pytest, shellcheck (for #150), GitHub Actions (for #150).

## Global Constraints

- Each task's deliverable = one merged PR + one auto-closed issue. NOT one commit.
- All PRs FF-merge to `main`. No squash, no merge commits.
- Branch name pattern: `feat/<issue-number>-<short-slug>` (e.g., `feat/150-shellcheck-ci`).
- PR body MUST contain `Closes #<issue-number>` for auto-close.
- `pytest -q` must stay green throughout the entire sprint (308 baseline).
- D11 invariant: `python scripts/validate.py` exits clean; `git diff --exit-code .claude-plugin/marketplace.json` empty.
- Pre-commit (ruff + ruff-format + heretek fast-gate + new shellcheck if #150 lands first) must pass.
- SonarCloud quality gate must show `success` AND `output.summary.newIssues == 0` (per [[sonarcloud-quality-gate-semantics]]).
- Merge authorization: requested once at sprint start per merge-and-push skill protocol.

## File Structure

This plan creates no new shared files. Each task creates its own files:

```
#150 (shellcheck):              .github/workflows/shellcheck.yml  (new)
                                plugins/hooks/.pre-commit-config.yaml  (modify)
                                tests/scripts/.shellcheckrc  (new, optional)
                                various .sh files  (fix findings if any)

#169 (config.properties):       scripts/heretek_cli.py  (modify)
                                tests/test_heretek_cli.py  (modify)

#170 (retention test):          tests/test_telemetry_retention.py  (modify)
                                plugins/hooks/scripts/telemetry_collector.py  (modify, if retention logic refactored)

#171 (CLI UX):                  scripts/heretek_cli.py  (modify)
                                tests/test_heretek_cli.py  (modify)

#172 (JSONDecodeError):         scripts/heretek_cli.py  (modify)
                                tests/test_heretek_cli.py  (modify)

#173 (polish bundle):           tests/test_hooks_manifest.py  (modify)
                                plugins/hooks/scripts/telemetry_collector.py  (modify)
                                scripts/heretek_cli.py  (modify)

#174 (ADR lifecycle):           catalog/reviews/0000-template.md  (modify)
                                docs/superpowers/specs/  (or similar)  (decision doc)
```

The sprint plan itself adds:

```
docs/superpowers/plans/2026-08-09-mixed-tactical-sprint.md   # this file
```

---

### Task 0: Pre-flight verification

**Files:** none modified.

- [ ] **Step 1: Confirm clean main branch**

Run: `git status --short --branch`
Expected: clean working tree, on `main` branch tracking `origin/main`.

- [ ] **Step 2: Read sprint spec**

Read: `docs/superpowers/specs/2026-08-09-mixed-tactical-sprint-design.md`
Expected: confirmed file exists and is current.

- [ ] **Step 3: Verify environment green**

Run: `pytest -q && python scripts/validate.py`
Expected: both exit 0. Baseline: 308 passed.

- [ ] **Step 4: Confirm no blocking PRs**

Run: `gh pr list --state open --limit 20` (fallback to GitHub MCP `list_pull_requests` if `gh` hangs).
Expected: no open PRs that would conflict with the 7-issue work.

- [ ] **Step 5: Request merge authorization**

Ask user once: pre-authorize all 7 merges, ask per PR, or pause after review?
Default: pre-authorize (matches prior sprint pattern).

Done: environment ready for subagent dispatch.

---

### Task 1: Issue #150 — ShellCheck CI integration

**Issue:** #150 — `Integrate ShellCheck into CI + pre-commit for shell-script sanity`
**Files (created/modified by subagent):**
- `.github/workflows/shellcheck.yml` (new — GitHub Actions per D20 SHA-pinning)
- Pre-commit hook config (`.pre-commit-config.yaml` or `plugins/hooks/.pre-commit-config.yaml`)
- Optional: `.shellcheckrc` for repo-wide shellcheck config
- Any `.sh` files that need shellcheck fixes (subagent decides inline if ≤3 findings, split into follow-up issue if >3)

- [ ] **Step 1: Spawn executor subagent (sonnet)**

Dispatch an `executor` subagent (`model=sonnet`) with:
- Issue #150 body (via `mcp__github__github-issue_read`)
- Constraint: D20 SHA-pinning for any new GitHub workflow
- Constraint: pre-commit hook install per project pattern (check existing `.pre-commit-config.yaml` if present)
- Instruction: install shellcheck locally if missing, run on all `*.sh` files, fix findings inline if ≤3 or split into a follow-up issue if >3
- Instruction: PR body MUST contain `Closes #150`

- [ ] **Step 2: Subagent reports back**

Expected return: PR URL, commit SHA, summary noting shellcheck findings count + fixes applied (or follow-up issue link if split).

- [ ] **Step 3: Verify PR + CI**

- PR body contains `Closes #150`
- PR title mentions shellcheck
- CI green: new shellcheck workflow passes; existing workflows unchanged
- SonarCloud: success + 0 new issues

- [ ] **Step 4: Run merge-and-push skill**

Inputs: `feat/150-shellcheck-ci`, PR number.
Expected: FF-merge to `main`, branch + worktree cleaned up, push to origin.

- [ ] **Step 5: Verify close**

`git log --oneline main -3` shows merge commit. `mcp__github__github-issue_read 150` shows state=closed.

- [ ] **Step 6: Local sanity**

Run: `pytest -q && python scripts/validate.py`
Expected: 308+ passed; validate OK.

Done: #150 closed. Advance to Task 2.

---

### Task 2: Issue #169 — config.properties format consistency

**Issue:** #169 — `Follow-up: config.properties format consistency for sub-spec 3`
**Files (modified by subagent):**
- `scripts/heretek_cli.py` (decide keep/migrate, update if needed)
- `tests/test_heretek_cli.py` (update tests)

- [ ] **Step 1: Verify Task 1 merged**

`git log --oneline main -3` shows #150 merge.

- [ ] **Step 2: Spawn executor subagent (haiku)**

Dispatch `executor` (`model=haiku`) with:
- Issue #169 body
- Subagent decides: keep simple format (add doc comment) OR migrate to real YAML using PyYAML (already in `requirements.lock.txt`)
- Subagent keeps the change minimal; document the decision in the issue comment

- [ ] **Step 3: Subagent reports back**

Expected: PR URL, commit SHA, decision summary.

- [ ] **Step 4: Verify PR + CI**

- PR body: `Closes #169`
- CI green; SonarCloud: success + 0 new issues

- [ ] **Step 5: Run merge-and-push skill**

Inputs: `feat/169-config-properties-format`, PR number.

- [ ] **Step 6: Verify close**

Issue #169 state=closed. Merge commit on `main`.

- [ ] **Step 7: Local sanity**

Run: `pytest -q tests/test_heretek_cli.py -v`
Expected: 9+ passed; config tests still green.

Done: #169 closed. Advance to Task 3.

---

### Task 3: Issue #170 — retention test simulation hardening

**Issue:** #170 — `Follow-up: retention test simulation hardening`
**Files (modified by subagent):**
- `tests/test_telemetry_retention.py` (replace simulation with true integration test)
- `plugins/hooks/scripts/telemetry_collector.py` (if retention logic needs refactor to be callable)

- [ ] **Step 1: Verify Task 2 merged**

`git log --oneline main -3` shows #169 merge.

- [ ] **Step 2: Spawn executor subagent (sonnet)**

Dispatch `executor` (`model=sonnet`) with:
- Issue #170 body
- Subagent: refactor retention logic into a callable function (if not already)
- Subagent: write a true integration test that verifies old sessions are compressed into `~/.heretek/telemetry/archive/<YYYY-MM-DD>.tar.zst`, fresh sessions remain in `~/.heretek/telemetry/sessions/`, and tar+zstd compression produces smaller output than raw JSONL
- Subagent: use `pytest.skip("zstandard not installed")` if zstd unavailable

- [ ] **Step 3: Subagent reports back**

Expected: PR URL, commit SHA, retention test result.

- [ ] **Step 4: Verify PR + CI**

- PR body: `Closes #170`
- CI green; SonarCloud: success + 0 new issues

- [ ] **Step 5: Run merge-and-push skill**

Inputs: `feat/170-retention-test-hardening`, PR number.

- [ ] **Step 6: Verify close**

Issue #170 state=closed. Merge commit on `main`.

- [ ] **Step 7: Local sanity**

Run: `pytest -q tests/test_telemetry_retention.py -v`
Expected: 2+ passed (skip ok if zstd unavailable).

Done: #170 closed. Advance to Task 4.

---

### Task 4: Issue #171 — CLI substring match help note + diff error message clarity

**Issue:** #171 — `Follow-up: CLI substring match help note + diff error message clarity`
**Files (modified by subagent):**
- `scripts/heretek_cli.py` (update help text + diff error message)
- `tests/test_heretek_cli.py` (add regression tests)

- [ ] **Step 1: Verify Task 3 merged**

`git log --oneline main -3` shows #170 merge.

- [ ] **Step 2: Spawn executor subagent (haiku)**

Dispatch `executor` (`model=haiku`) with:
- Issue #171 body
- Subagent: update `cmd_telemetry_show --session` help text to mention substring match behavior
- Subagent: update `cmd_telemetry_diff` error message to identify which session is missing (per-session check)
- Subagent: add regression tests for both behaviors

- [ ] **Step 3: Subagent reports back**

Expected: PR URL, commit SHA, test summary.

- [ ] **Step 4: Verify PR + CI**

- PR body: `Closes #171`
- CI green; SonarCloud: success + 0 new issues

- [ ] **Step 5: Run merge-and-push skill**

Inputs: `feat/171-cli-ux-polish`, PR number.

- [ ] **Step 6: Verify close**

Issue #171 state=closed. Merge commit on `main`.

- [ ] **Step 7: Local sanity**

Run: `pytest -q tests/test_heretek_cli.py -v`
Expected: 10+ passed.

Done: #171 closed. Advance to Task 5.

---

### Task 5: Issue #172 — JSONDecodeError stderr count in heretek_cli.py

**Issue:** #172 — `Follow-up: JSONDecodeError stderr count in heretek_cli.py`
**Files (modified by subagent):**
- `scripts/heretek_cli.py` (track dropped_lines counter + emit warning)
- `tests/test_heretek_cli.py` (add regression test)

- [ ] **Step 1: Verify Task 4 merged**

`git log --oneline main -3` shows #171 merge.

- [ ] **Step 2: Spawn executor subagent (haiku)**

Dispatch `executor` (`model=haiku`) with:
- Issue #172 body
- Subagent: track `dropped_lines` count in `_read_events`
- Subagent: print `"warning: {n} malformed JSONL line(s) skipped"` to stderr if `n > 0`
- Subagent: add regression test that writes a JSONL file with one malformed line and confirms the warning is emitted

- [ ] **Step 3: Subagent reports back**

Expected: PR URL, commit SHA, test summary.

- [ ] **Step 4: Verify PR + CI**

- PR body: `Closes #172`
- CI green; SonarCloud: success + 0 new issues

- [ ] **Step 5: Run merge-and-push skill**

Inputs: `feat/172-jsondecode-count`, PR number.

- [ ] **Step 6: Verify close**

Issue #172 state=closed. Merge commit on `main`.

- [ ] **Step 7: Local sanity**

Run: `pytest -q tests/test_heretek_cli.py -v`
Expected: 11+ passed.

Done: #172 closed. Advance to Task 6.

---

### Task 6: Issue #173 — minor final-review polish (4 sub-items)

**Issue:** #173 — `Follow-up: minor final-review polish (comment + matcher + reorder + dead-branch)`
**Files (modified by subagent):**
- `tests/test_hooks_manifest.py:183, 185` (replace `(Task 3)` comment + refactor length assertion to matcher-based)
- `plugins/hooks/scripts/telemetry_collector.py:166` (move `_derive_decision` above `_build_event`)
- `scripts/heretek_cli.py:135-150` (drop dead-branch `if args.subcommand == "set":`)

- [ ] **Step 1: Verify Task 5 merged**

`git log --oneline main -3` shows #172 merge.

- [ ] **Step 2: Spawn executor subagent (sonnet)**

Dispatch `executor` (`model=sonnet`) with:
- Issue #173 body
- Subagent: commit all 4 fixes in one PR per the polish-bundle approach
- Subagent: if review fails on any sub-item, subagent should fix forward in same PR or split into a follow-up
- Subagent: verify the comment change (`(Task 3)` → invariant description) and the matcher-based refactor

- [ ] **Step 3: Subagent reports back**

Expected: PR URL, commit SHA, summary of all 4 fixes.

- [ ] **Step 4: Verify PR + CI**

- PR body: `Closes #173`
- CI green; SonarCloud: success + 0 new issues

- [ ] **Step 5: Run merge-and-push skill**

Inputs: `feat/173-polish-bundle`, PR number.

- [ ] **Step 6: Verify close**

Issue #173 state=closed. Merge commit on `main`.

- [ ] **Step 7: Local sanity**

Run: `pytest -q tests/test_hooks_manifest.py tests/test_telemetry_collector.py tests/test_heretek_cli.py -v`
Expected: all green.

Done: #173 closed. Advance to Task 7.

---

### Task 7: Issue #174 — ADR proposed/ratified lifecycle standardization

**Issue:** #174 — `Follow-up: ADR proposed/ratified lifecycle standardization`
**Files (modified/created by subagent):**
- `catalog/reviews/0000-template.md` (modify — decide based on outcome)
- Decision doc (e.g., in `docs/superpowers/specs/` or similar)
- Possibly: per-ADR frontmatter updates for existing ADRs if standardization is chosen

- [ ] **Step 1: Verify Task 6 merged**

`git log --oneline main -3` shows #173 merge.

- [ ] **Step 2: Spawn executor subagent (haiku)**

Dispatch `executor` (`model=haiku`) with:
- Issue #174 body
- Subagent: investigate how many existing ADRs (in `catalog/reviews/`) use Proposed vs Approved/Rejected two-state
- Subagent: decide standardize to three-state (update template + possibly existing ADRs) OR revert observability sub-spec 1 ADR to two-state
- Subagent: document the decision in a short doc; if changing template, ensure existing ADRs are still conformant

- [ ] **Step 3: Subagent reports back**

Expected: PR URL, commit SHA, decision summary.

- [ ] **Step 4: Verify PR + CI**

- PR body: `Closes #174`
- CI green; SonarCloud: success + 0 new issues

- [ ] **Step 5: Run merge-and-push skill**

Inputs: `feat/174-adr-lifecycle`, PR number.

- [ ] **Step 6: Verify close**

Issue #174 state=closed. Merge commit on `main`.

- [ ] **Step 7: Local sanity**

Run: `pytest -q && python scripts/validate.py`
Expected: 308+ passed; validate OK.

Done: #174 closed. Advance to Task 8 (sprint close-out).

---

### Task 8: Sprint close-out (DoD verification)

**Files:** none modified.

- [ ] **Step 1: Verify all 7 issues closed**

Run: `mcp__github__github-issue_read <n> method=get` for n in 150, 169, 170, 171, 172, 173, 174.
Expected: all state=closed, reason=completed, closed_by PR.

- [ ] **Step 2: Verify 7 merge commits on main**

Run: `git log --oneline main -10`
Expected: 7 new merge commits.

- [ ] **Step 3: Run full local test suite**

Run: `pytest -q && python scripts/validate.py`
Expected: 308+ passed; coverage unchanged or improved.

- [ ] **Step 4: Verify D11 invariant**

Run: `git diff --exit-code .claude-plugin/marketplace.json`
Expected: no diff (regenerated file is byte-identical).

- [ ] **Step 5: Verify #150 integration**

- Run pre-commit locally: shellcheck should run on any new `.sh` files
- GitHub Actions: `shellcheck.yml` workflow exists and is enabled
- Confirm: `.github/workflows/shellcheck.yml` is in main

- [ ] **Step 6: Comment on parent issue #126 with progress**

Use `mcp__github__github-add_issue_comment` on issue #126 with body:

```
Sub-spec 2 + 3 still pending. Mixed-tactical sprint shipped via PRs closing #150, #169-#174:

- #150: ShellCheck CI integration (sub-spec 1 collector + shell scripts now linted in CI)
- #169: config.properties format consistency
- #170: retention test true integration (caught bugs in simulation)
- #171: CLI substring match + diff error clarity
- #172: JSONDecodeError stderr count
- #173: minor final-review polish bundle
- #174: ADR lifecycle standardization

Tech-debt batch cleared. Next sprint candidates: v3.5 sub-spec 2 (test pipeline, #114-#118) or sub-spec 3 (eval harness, #119-#124), security batch (#157-#168).
```

Done: sprint complete.

---

## Self-Review

**1. Spec coverage (sprint spec §1-7):**
- §1 Goal — Tasks 1-7 implement the 7 issues; Task 8 verifies
- §2 Scope — 7 issues in; v3.5 sub-specs, security batch, v2 backlog out (explicit)
- §3 Sequence — Tasks 1-7 match; all file-independent
- §4 Execution mechanics — pre-flight, per-issue model selection, post-merge verification, special-case #150
- §5 DoD — Task 8 verifies all 9 criteria
- §6 Risk register — R1 (shellcheck findings) covered in #150 step 2; R2 (sequential enforced) implicit; R3 (template conflict) covered in #174 step 2; R4 (polish bundle) covered in #173 step 2; R5 (version drift) covered in #150 step 2
- §7 Re-evaluation triggers — out of scope for plan (operational decision per session)

**2. Placeholder scan:** No "TBD", "TODO", "implement later", "appropriate error handling", "similar to Task N", "fill in details". All steps have concrete commands, exact paths, or explicit subagent instructions.

**3. Type/identifier consistency:**
- Branch names: `feat/150-...`, `feat/169-...`, etc. — consistent pattern
- PR body marker: `Closes #<n>` — consistent
- Subagent invocation: `executor` with `model=sonnet` or `model=haiku` — consistent
- Issue references: #150, #169-#174 — all consistent
- File paths reference per-issue cleanly

No fixes needed.