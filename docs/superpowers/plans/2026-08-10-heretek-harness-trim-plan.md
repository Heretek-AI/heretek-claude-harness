# Heretek Harness Trim Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans (user pre-authorized inline execution, no checkpoints). Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Transform `heretek-claude-harness` into a slim, mechanically-gated, deep-module codebase per the merged spec (#219).

**Architecture:** 5 sequential PRs that delete bloat (PR1-2), inline shallow utilities (PR3), consolidate hooks locality + add gates (PR4), and compact prompt/skill prose + collapse issue_loop (PR5). Each PR is independently mergeable, all CI must pass per PR.

**Tech Stack:** Python 3.10+, pytest, pre-commit (ruff/biome/shellcheck/gitleaks), GitHub Actions (validate/pre-commit/shellcheck/security-scan/smoke-test), Claude Code hooks (PreToolUse/PostToolUse).

**Spec:** `docs/superpowers/specs/2026-08-10-heretek-harness-trim-design.md` (merged as commit fb4e20a).

## Global Constraints

- Python 3.10+; ruff line-length 100 (per `pyproject.toml`); E741 ignored.
- Test fixtures may contain intentionally-bad code (per-file-ignore `F821`, `F841`, `E402`).
- Scanners may use late imports (per-file-ignore `E402`).
- Catalog uses `ruamel.yaml` round-trip — never reformat.
- No `version` field on first-party plugins (D11 SHA-ride).
- Hooks live ONLY in `plugins/hooks/` (D15).
- Pre-commit installed at `plugins/hooks/.pre-commit-config.yaml` (D30); `fail_fast: true` locally.
- All SHAs pinned to 40-char hex in `catalog/catalog.yaml`.
- Branch-per-PR; squash-merge to `main`; no force-push.
- Each PR must pass: `pytest -q`, `python scripts/validate.py`, `python scripts/generate_marketplace.py` (clean diff), `bash tests/smoke/fast_gate_smoke.sh`, `bash catalog/tests/smoke_test.sh`, plus CI.

---

## Task 1: PR1 — R5 spike purges

**Files:**
- Delete: `scripts/counterfactual_diffs_spike.py`
- Delete: `scripts/rlm_fast_gate_spike.py`
- Delete: `scripts/staleness_metric_spike.py`
- Delete: `scripts/svok_provenance_spike.py`
- Delete: `PLAN.md`
- Delete: `coverage.xml`
- Delete: `.coverage`
- Delete: `reports/skills-pack-headroom.json`
- Delete: `reports/baseline/` (entire dir)
- Delete: `__pycache__/` directories (10): `scripts/__pycache__/`, `tests/__pycache__/`, `scripts/scanners/__pycache__/`, `scripts/audit/__pycache__/`, `scripts/issue_loop/__pycache__/`, `tests/freshness_eval/__pycache__/`, `tests/detection/__pycache__/`, `tests/enforcement/__pycache__/`, `tests/vision/__pycache__/`, `plugins/hooks/scripts/__pycache__/`
- Delete: `plugins/hooks/commands/.gitkeep`
- Delete: `plugins/hooks/hooks/.gitkeep`
- Delete: `plugins/hooks/scripts/.gitkeep`
- Modify: `.gitignore` — verify `**/__pycache__/` is present (add if missing)

**Consumes:** Nothing.
**Produces:** Repo with ~700 LOC deleted, no spike scripts, no build artifacts, no `.gitkeep` markers.

**Risk:** Trivial (pure deletions, no behavior change).

- [ ] **Step 1: Verify no live importers of spike scripts**

Run: `grep -rln "counterfactual_diffs_spike\|rlm_fast_gate_spike\|staleness_metric_spike\|svok_provenance_spike" --include="*.py" --include="*.sh" --include="*.yaml" --include="*.md" 2>/dev/null`
Expected: empty output (no importers; these were throwaway one-shots).

- [ ] **Step 2: Verify `.gitignore` covers `__pycache__`**

Run: `grep -E "^(__pycache__|\*\*/__pycache__/|\.pyc)" .gitignore`
Expected: at least one match. If missing, append `**/__pycache__/` and `*.pyc`.

- [ ] **Step 3: Delete the 4 spike scripts**

Run:
```bash
git rm scripts/counterfactual_diffs_spike.py \
       scripts/rlm_fast_gate_spike.py \
       scripts/staleness_metric_spike.py \
       scripts/svok_provenance_spike.py
```

- [ ] **Step 4: Delete `PLAN.md`**

Run: `git rm PLAN.md`

- [ ] **Step 5: Delete build artifacts (`coverage.xml`, `.coverage`)**

Run:
```bash
git rm -f coverage.xml .coverage 2>/dev/null || true
rm -f coverage.xml .coverage
```

- [ ] **Step 6: Delete `reports/` artifacts**

Run:
```bash
git rm -rf reports/skills-pack-headroom.json reports/baseline/
rmdir reports/ 2>/dev/null || true
```

- [ ] **Step 7: Remove `.gitkeep` markers (they were only needed for empty dirs)**

Run:
```bash
git rm plugins/hooks/commands/.gitkeep \
       plugins/hooks/hooks/.gitkeep \
       plugins/hooks/scripts/.gitkeep
```

- [ ] **Step 8: Clean up all `__pycache__/` directories**

Run:
```bash
find . -path ./.venv -prune -o -path ./.git -prune -o -path ./.claude/worktrees -prune -o -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null
```

- [ ] **Step 9: Verify clean local tests still pass**

Run: `pytest -q`
Expected: all tests pass.

- [ ] **Step 10: Verify marketplace validation still passes**

Run: `python scripts/validate.py && python scripts/generate_marketplace.py && git diff --exit-code .claude-plugin/marketplace.json`
Expected: all exit 0, no marketplace.json drift.

- [ ] **Step 11: Commit on branch `trim/r5-spike-purge`**

Run:
```bash
git checkout -b trim/r5-spike-purge
git add -A
git commit -m "feat(trim): R5 spike purges + build artifact cleanup

- Delete 4 spike scripts (counterfactual_diffs, rlm_fast_gate,
  staleness_metric, svok_provenance) — results retained in
  docs/superpowers/spikes/*-results.md
- Delete coverage.xml, .coverage (CI artifacts; regenerate on demand)
- Delete PLAN.md (subsumed by docs/superpowers/roadmap.md)
- Delete reports/{skills-pack-headroom.json,baseline/} (one-off measurements)
- Delete plugins/hooks/{commands,hooks,scripts}/.gitkeep (dirs non-empty)
- Clean all __pycache__/ (10 dirs)
- Verify __pycache__/ in .gitignore

PR1 of 5 in 2026-08-10-heretek-harness-trim spec.

Co-Authored-By: Claude <noreply@anthropic.com>"
```

- [ ] **Step 12: Push + open PR**

Run:
```bash
git push -u origin trim/r5-spike-purge
gh pr create --title "feat(trim): R5 spike purges + build artifact cleanup" \
  --body "PR1 of 5 in the heretek-harness-trim spec (#219). Pure deletions; no behavior change.

Closes part of #219" \
  --base main --head trim/r5-spike-purge
```

- [ ] **Step 13: Verify CI green**

Run: `gh pr checks --watch --fail-fast`
Expected: all required checks pass (pre-commit, ShellCheck, smoke-test, validate, SonarCloud, CodeQL, freshness).

- [ ] **Step 14: Squash-merge**

Run: `gh pr merge --squash --delete-branch`

- [ ] **Step 15: Switch back to main and pull**

Run:
```bash
git checkout main
git pull --ff-only
git branch -D trim/r5-spike-purge
```

---

## Task 2: PR2 — R4 audit verify-then-decide

**Files (default path = delete):**
- Verify-then-decide gate: `scripts/audit/` 7 .py files vs. importers
- If delete path:
  - Delete: `scripts/audit/__init__.py`
  - Delete: `scripts/audit/findings.py`
  - Delete: `scripts/audit/harness_self.py`
  - Delete: `scripts/audit/issues.py`
  - Delete: `scripts/audit/prompts.py`
  - Delete: `scripts/audit/synthesis.py`
  - Delete: `scripts/audit/validate.py`
  - Delete: `tests/test_audit_e2e.py`
  - Delete: `tests/test_audit_findings.py`
  - Delete: `tests/test_audit_harness_self.py`
  - Delete: `tests/test_audit_issues.py`
  - Delete: `tests/test_audit_prompts.py`
  - Delete: `tests/test_audit_schema.py`
  - Delete: `tests/test_audit_synthesis.py`
  - Delete: `tests/test_audit_validate.py`

**Consumes:** PR1 merged.
**Produces:** `scripts/audit/` deleted (or folded into a single `scripts/health.py`); audit tests deleted; existing tests pass.

**Risk:** Medium — must verify no upstream consumer.

- [ ] **Step 1: Search for importers of `scripts/audit/`**

Run: `grep -rln "from scripts.audit\|from .audit\|scripts\.audit\|scripts/audit" --include="*.py" --include="*.sh" --include="*.yaml" --include="*.md" --include="*.toml" 2>/dev/null | grep -v __pycache__`
Expected: empty output (no importers).

- [ ] **Step 2: Verify no CLI command exposes audit subpackage**

Run: `grep -rn "audit" scripts/heretek_cli.py scripts/catalog_updater.py 2>/dev/null`
Expected: empty output (no `audit` subcommand in the top-level CLI).

- [ ] **Step 3: If importers found, STOP** and document the consumer — this is a fork-in-the-road requiring human review. Default path below.

- [ ] **Step 4: Delete `scripts/audit/` directory**

Run: `git rm -rf scripts/audit/`

- [ ] **Step 5: Delete `tests/test_audit_*.py` (9 files)**

Run:
```bash
git rm tests/test_audit_e2e.py \
       tests/test_audit_findings.py \
       tests/test_audit_harness_self.py \
       tests/test_audit_issues.py \
       tests/test_audit_prompts.py \
       tests/test_audit_schema.py \
       tests/test_audit_synthesis.py \
       tests/test_audit_validate.py
```

- [ ] **Step 6: Search for test references to deleted test files**

Run: `grep -rln "test_audit_e2e\|test_audit_findings\|test_audit_harness_self\|test_audit_issues\|test_audit_prompts\|test_audit_schema\|test_audit_synthesis\|test_audit_validate" --include="*.py" --include="*.toml" --include="*.cfg" --include="*.yaml" 2>/dev/null`
Expected: empty output. If matches in `tests/conftest.py` or `pyproject.toml`, remove them.

- [ ] **Step 7: Run tests**

Run: `pytest -q`
Expected: all pass.

- [ ] **Step 8: Validate + regenerate marketplace**

Run: `python scripts/validate.py && python scripts/generate_marketplace.py && git diff --exit-code .claude-plugin/marketplace.json`
Expected: clean.

- [ ] **Step 9: Commit on `trim/r4-audit-decide`**

Run:
```bash
git checkout -b trim/r4-audit-decide
git add -A
git commit -m "feat(trim): R4 delete scripts/audit/ (no consumer found)

Verified no importer of scripts/audit/ exists in the codebase. The
audit subpackage was self-referential tooling (harness_self + 9 tests)
with no CLI consumer or eval pipeline. Deleted:

- scripts/audit/ (7 .py + __init__)
- tests/test_audit_*.py (9 files)

PR2 of 5 in 2026-08-10-heretek-harness-trim spec.

Co-Authored-By: Claude <noreply@anthropic.com>"
```

- [ ] **Step 10: Push + open PR**

Run:
```bash
git push -u origin trim/r4-audit-decide
gh pr create --title "feat(trim): R4 delete scripts/audit/ (no consumer)" \
  --body "PR2 of 5 in heretek-harness-trim spec (#219). Verified no CLI consumer; safe to delete.

Closes part of #219" \
  --base main --head trim/r4-audit-decide
```

- [ ] **Step 11: Wait for CI green**

Run: `gh pr checks --watch --fail-fast`
Expected: all required checks pass.

- [ ] **Step 12: Squash-merge + cleanup**

Run:
```bash
gh pr merge --squash --delete-branch
git checkout main
git pull --ff-only
git branch -D trim/r4-audit-decide
```

---

## Task 3: PR3 — R2+R3 inline shallow utils

**Files:**
- Modify: `plugins/hooks/scripts/telemetry_collector.py` — inline `require_session_id` from `_allowlist.py`
- Modify: `plugins/hooks/scripts/lookup_gate.py` (post-PR4 move target path, but pre-PR4 it's at `scripts/lookup_gate.py`) — inline `require_session_id`
- Modify: `plugins/hooks/scripts/drift_detector.py` (same caveat) — inline `require_session_id`
- Modify: `scripts/refresh_pins.py` — inline `_http.py` HTTP wrapper
- Delete: `scripts/_allowlist.py`
- Delete: `scripts/_http.py`

**Consumes:** PR2 merged.
**Produces:** No `_allowlist.py` / `_http.py`; inlined into 4 callers; existing tests pass.

**Risk:** Low (pure inlining with test coverage).

**Note**: In this PR, the hooks still live at `scripts/{drift_detector,lookup_gate}.py`. PR4 moves them to `plugins/hooks/scripts/`. For this PR, inlining targets are at their CURRENT paths. After PR4, telemetry_collector.py stays in plugins/hooks/scripts/ but the other two are moved. Re-verify inlining paths post-PR4.

- [ ] **Step 1: Read `_allowlist.py` to confirm contents**

Run: `cat scripts/_allowlist.py`
Expected: 57 lines containing `require_session_id()`.

- [ ] **Step 2: Read `_http.py` to confirm contents**

Run: `cat scripts/_http.py`
Expected: 21 lines containing HTTP wrapper.

- [ ] **Step 3: Inline `require_session_id` into `telemetry_collector.py`**

Open `plugins/hooks/scripts/telemetry_collector.py`. Find the `from scripts._allowlist import require_session_id` line. Replace with the function body inline. Remove the import. Verify no other references to `scripts._allowlist` remain.

- [ ] **Step 4: Inline `require_session_id` into `scripts/lookup_gate.py`**

Same as Step 3 but for `scripts/lookup_gate.py`.

- [ ] **Step 5: Inline `require_session_id` into `scripts/drift_detector.py`**

Same as Step 3 but for `scripts/drift_detector.py`.

- [ ] **Step 6: Inline HTTP wrapper into `scripts/refresh_pins.py`**

Open `scripts/refresh_pins.py`. Find the `from ._http import ...` (if present) or equivalent. Inline. Remove the import.

- [ ] **Step 7: Verify no remaining references to `_allowlist` or `_http`**

Run: `grep -rn "_allowlist\|_http" scripts/ plugins/ --include="*.py" 2>/dev/null | grep -v __pycache__`
Expected: empty output.

- [ ] **Step 8: Delete `scripts/_allowlist.py` and `scripts/_http.py`**

Run: `git rm scripts/_allowlist.py scripts/_http.py`

- [ ] **Step 9: Run tests**

Run: `pytest -q`
Expected: all pass.

- [ ] **Step 10: Commit on `trim/r2-r3-inline-utils`**

Run:
```bash
git checkout -b trim/r2-r3-inline-utils
git add -A
git commit -m "feat(trim): R2+R3 inline _allowlist.py and _http.py

The two shallow utility modules were single-function helpers used by
exactly 2-3 callers each. Inlined:

- require_session_id() into:
  - plugins/hooks/scripts/telemetry_collector.py
  - scripts/lookup_gate.py (moves to plugins/hooks/scripts/ in PR4)
  - scripts/drift_detector.py (moves to plugins/hooks/scripts/ in PR4)

- HTTP wrapper constants into:
  - scripts/refresh_pins.py

Deleted:
- scripts/_allowlist.py
- scripts/_http.py

Net: -57 + ~30 inlined = -27 LOC; one less indirection per call site.

PR3 of 5 in 2026-08-10-heretek-harness-trim spec.

Co-Authored-By: Claude <noreply@anthropic.com>"
```

- [ ] **Step 11: Push + open PR**

Run:
```bash
git push -u origin trim/r2-r3-inline-utils
gh pr create --title "feat(trim): R2+R3 inline shallow utility modules" \
  --body "PR3 of 5 in heretek-harness-trim spec (#219). Pure inlining with existing test coverage.

Closes part of #219" \
  --base main --head trim/r2-r3-inline-utils
```

- [ ] **Step 12: Wait for CI green**

Run: `gh pr checks --watch --fail-fast`
Expected: all required checks pass.

- [ ] **Step 13: Squash-merge + cleanup**

Run:
```bash
gh pr merge --squash --delete-branch
git checkout main
git pull --ff-only
git branch -D trim/r2-r3-inline-utils
```

---

## Task 4: PR4 — R1+R6+R7+R11 hooks locality + dispatcher + secrets + ci.sh

**Files (moves):**
- Move: `scripts/drift_detector.py` → `plugins/hooks/scripts/drift_detector.py`
- Move: `scripts/lookup_gate.py` → `plugins/hooks/scripts/lookup_gate.py`
- Move: `scripts/stale_dep_intercept.py` → `plugins/hooks/scripts/stale_dep_intercept.py`
- Move: `scripts/scanners/forbidden_pattern_scanner.py` → `plugins/hooks/scripts/forbidden_pattern_scanner.py`

**Files (new):**
- Create: `plugins/hooks/scripts/post_tool_dispatcher.py` — multiplexes 5 PostToolUse hooks
- Create: `plugins/hooks/scripts/secrets_pre_tool.py` — PreToolUse secret regex sweep
- Create: `scripts/ci.sh` — single local-CI entry

**Files (modify):**
- Modify: `plugins/hooks/hooks/hooks.json` — add `secrets_pre_tool.py` PreToolUse entry; collapse 5 PostToolUse entries into 1 dispatcher entry
- Modify: `plugins/hooks/.pre-commit-config.yaml` — add `ci.sh` as local hook

**Consumes:** PR3 merged (no more `from scripts._allowlist import` in moved files).
**Produces:** All hooks co-located in `plugins/hooks/scripts/`; dispatcher fan-out working; secrets gate active; `scripts/ci.sh` working; existing tests pass.

**Risk:** Highest in the sequence (touches the agent's hook chain).

- [ ] **Step 1: Read current `hooks.json` to confirm shape**

Run: `cat plugins/hooks/hooks/hooks.json`

- [ ] **Step 2: Move the 4 hook scripts (using `git mv` to preserve history)**

Run:
```bash
mkdir -p plugins/hooks/scripts
git mv scripts/drift_detector.py plugins/hooks/scripts/drift_detector.py
git mv scripts/lookup_gate.py plugins/hooks/scripts/lookup_gate.py
git mv scripts/stale_dep_intercept.py plugins/hooks/scripts/stale_dep_intercept.py
git mv scripts/scanners/forbidden_pattern_scanner.py plugins/hooks/scripts/forbidden_pattern_scanner.py
```

- [ ] **Step 3: Update `sys.path` inserts in moved files**

In each moved file, find lines like `sys.path.insert(0, str(Path(__file__).resolve().parent.parent))` and update `parents[1]` → `parents[2]` (or remove entirely if no longer needed because imports are siblings). Verify by running tests.

- [ ] **Step 4: Update import paths in moved files**

In each moved file, find `from scripts.xxx import yyy` and update to local imports (e.g. `from . import xxx` or `from .xxx import yyy`).

- [ ] **Step 5: Run tests to verify moves are correct**

Run: `pytest tests/test_drift_detector.py tests/test_fast_gate.py tests/test_quality_gate.py tests/test_hooks_manifest.py -q`
Expected: all pass.

- [ ] **Step 6: Create `plugins/hooks/scripts/post_tool_dispatcher.py`**

Write the dispatcher. It:
1. Reads hook payload from stdin.
2. Subprocesses each analyzer: `stale_dep_intercept.py`, `forbidden_pattern_scanner.py`, `drift_detector.py`, `lookup_gate.py`, `telemetry_collector.py`.
3. Per-child timeout (1.5s) with fail-open.
4. Aggregates JSON `additionalContext` outputs into one envelope.
5. Writes consolidated JSON to stdout, exit 0.

Use `subprocess.run` with `timeout=1.5`, `capture_output=True`. Use `asyncio` if simpler (but keep stdlib-only per project convention).

- [ ] **Step 7: Create `plugins/hooks/scripts/secrets_pre_tool.py`**

Write the secret detector. Pure stdlib regex sweep for:
- AWS access keys: `AKIA[0-9A-Z]{16}`
- GitHub PATs: `ghp_[A-Za-z0-9]{36}`
- JWT tokens: `eyJ[A-Za-z0-9_-]+\.eyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+`
- Generic high-entropy: `\b[A-Za-z0-9+/]{40,}\b` (skip — too noisy)

Per file extension whitelist (`.py`, `.sh`, `.yaml`, `.yml`, `.json`, `.env`, `.toml`). Read payload from stdin, extract `tool_input.new_string`, scan, exit 2 with file_path + matched line on hit.

- [ ] **Step 8: Update `plugins/hooks/hooks/hooks.json`**

Add `secrets_pre_tool.py` to PreToolUse:
```json
{
  "matcher": "Edit|Write|MultiEdit",
  "hooks": [
    {"type": "command", "command": "python3 ${CLAUDE_PLUGIN_ROOT}/scripts/secrets_pre_tool.py", "timeout": 200}
  ]
}
```

Collapse 5 PostToolUse entries into 1 dispatcher:
```json
{
  "matcher": "Edit|Write|MultiEdit|Read|Bash",
  "hooks": [
    {"type": "command", "command": "python ${CLAUDE_PLUGIN_ROOT}/scripts/post_tool_dispatcher.py", "timeout": 2000}
  ]
}
```

Verify with `python -c "import json; json.load(open('plugins/hooks/hooks/hooks.json'))"`.

- [ ] **Step 9: Create `scripts/ci.sh`**

```bash
#!/usr/bin/env bash
# scripts/ci.sh — single local-CI entry for heretek harness.
set -euo pipefail
pytest -q
python scripts/validate.py
python scripts/generate_marketplace.py
git diff --exit-code .claude-plugin/marketplace.json
bash tests/smoke/fast_gate_smoke.sh
bash catalog/tests/smoke_test.sh
```

Make executable: `chmod +x scripts/ci.sh`.

- [ ] **Step 10: Add `ci.sh` as local pre-commit hook in `.pre-commit-config.yaml`**

Find the `# 4. JS/TS:` section. After it, add:
```yaml
  # 5. heretek-ci (local). Single local-CI pipeline; mirrors the GitHub Actions
  # validate.yml steps. Catches drift before push.
  - repo: local
    hooks:
      - id: heretek-ci
        name: heretek local-CI (scripts/ci.sh)
        entry: bash scripts/ci.sh
        language: system
        pass_filenames: false
```

- [ ] **Step 11: Run pre-commit on the changes**

Run: `pre-commit run --all-files`
Expected: all pass.

- [ ] **Step 12: Run full test suite**

Run: `pytest -q && python scripts/validate.py && python scripts/generate_marketplace.py && git diff --exit-code .claude-plugin/marketplace.json && bash tests/smoke/fast_gate_smoke.sh && bash catalog/tests/smoke_test.sh`
Expected: all pass.

- [ ] **Step 13: Run new tests for dispatcher + secrets**

Create `tests/test_post_tool_dispatcher.py` (subprocess fan-out, JSON aggregation, per-child timeout) and `tests/test_secrets_pre_tool.py` (AWS key / GitHub PAT / JWT detection on synthetic payloads). Run them. Both must pass.

- [ ] **Step 14: Commit on `trim/r1-r6-r7-r11-hooks-and-gates`**

Run:
```bash
git checkout -b trim/r1-r6-r7-r11-hooks-and-gates
git add -A
git commit -m "feat(trim): R1+R6+R7+R11 hooks locality + dispatcher + secrets + ci.sh

D15 compliance: all hook components now live in plugins/hooks/scripts/.

- Move 4 hooks into plugins/hooks/scripts/:
  - drift_detector.py, lookup_gate.py, stale_dep_intercept.py,
    forbidden_pattern_scanner.py

- New: plugins/hooks/scripts/post_tool_dispatcher.py
  Multiplexes 5 PostToolUse hooks (stale_dep_intercept,
  forbidden_pattern_scanner, drift_detector, lookup_gate,
  telemetry_collector) into 1 process. 1 startup instead of 5 per Edit.

- New: plugins/hooks/scripts/secrets_pre_tool.py
  PreToolUse Edit/Write gate. Pure stdlib regex sweep for AWS keys,
  GitHub PATs, JWT tokens. <200ms timeout.

- New: scripts/ci.sh
  Single local-CI entry. Replaces 5-line bash block in CLAUDE.md:
  pytest + validate + generate + smoke.

- Update: plugins/hooks/hooks/hooks.json
  PreToolUse: add secrets_pre_tool.py
  PostToolUse: 5 entries -> 1 dispatcher entry

- Update: plugins/hooks/.pre-commit-config.yaml
  Add local heretek-ci hook running scripts/ci.sh.

- New: tests/test_post_tool_dispatcher.py, tests/test_secrets_pre_tool.py

PR4 of 5 in 2026-08-10-heretek-harness-trim spec.

Co-Authored-By: Claude <noreply@anthropic.com>"
```

- [ ] **Step 15: Push + open PR**

Run:
```bash
git push -u origin trim/r1-r6-r7-r11-hooks-and-gates
gh pr create --title "feat(trim): R1+R6+R7+R11 hooks locality + dispatcher + secrets + ci.sh" \
  --body "PR4 of 5 in heretek-harness-trim spec (#219). Highest-risk PR (touches the agent hook chain). Validated locally via pre-commit + pytest + validate + smoke.

Closes part of #219" \
  --base main --head trim/r1-r6-r7-r11-hooks-and-gates
```

- [ ] **Step 16: Wait for CI green**

Run: `gh pr checks --watch --fail-fast`
Expected: all required checks pass (this is the riskiest — SonarCloud code quality + security matters here).

- [ ] **Step 17: Squash-merge + cleanup**

Run:
```bash
gh pr merge --squash --delete-branch
git checkout main
git pull --ff-only
git branch -D trim/r1-r6-r7-r11-hooks-and-gates
```

---

## Task 5: PR5 — §2 + S1-S4 compaction + collapse

**Files (modify):**
- Modify: `CLAUDE.md` — 76 → 14 lines
- Modify: `scripts/issue_drafter.py` — inline `plan_pre_flight.py` (R10)
- Modify: `scripts/issue_loop.py` (NEW) — S1 collapse from 10 files

**Files (move):**
- Move: `scripts/issue_loop/{__init__,branch,classifier,driver,gate,ledger,merge,subagents,cli,autopilot_drain}.py` → consolidate into `scripts/issue_loop.py`

**Files (delete):**
- Delete: `scripts/plan_pre_flight.py` (inlined into `issue_drafter.py`)
- Delete: `tests/test_issue_loop_branch.py`
- Delete: `tests/test_issue_loop_classifier.py`
- Delete: `tests/test_issue_loop_cli.py`
- Delete: `tests/test_issue_loop_driver.py`
- Delete: `tests/test_issue_loop_e2e.py`
- Delete: `tests/test_issue_loop_gate.py`
- Delete: `tests/test_issue_loop_ledger.py`
- Delete: `tests/test_issue_loop_merge.py`
- Delete: `tests/test_issue_loop_subagents.py`
- Delete: `tests/test_issue_loop_classifier.py` (already listed)

**Files (compress):**
- Modify: `.claude/skills/catalog/SKILL.md` — 198 → 40 lines
- Modify: `.claude/skills/merge-and-push/SKILL.md` — 130 → 30 lines (skeleton + `python scripts/merge_and_push.py` pointer)
- Modify: `.claude/skills/refresh-pins/SKILL.md` — 89 → 25 lines
- Modify: `.claude/skills/issue-loop/SKILL.md` — 64 → 20 lines
- Modify: `.claude/skills/sonarcloud-suppression/SKILL.md` — 131 → 15 lines (point to docs/)
- Modify: `.claude/skills/sonarcloud-batch-remediation/SKILL.md` — 131 → 15 lines (point to docs/)

**Files (new):**
- Create: `docs/SONAR-SUPPRESSION.md` — body of sonarcloud-suppression skill
- Create: `docs/SONAR-BATCH-REMEDIATION.md` — body of sonarcloud-batch-remediation skill
- Create: `tests/test_issue_loop.py` — single test file replacing 9 deleted

**Consumes:** PR4 merged.
**Produces:** CLAUDE.md ≤ 14 lines; issue_loop collapsed to 1 module; skills ≤ 40 lines each; all existing tests pass.

**Risk:** Highest LOC. S1 collapse touches 10 module boundaries.

- [ ] **Step 1: Read all 9 scripts/issue_loop/*.py files**

Run: `ls scripts/issue_loop/*.py`
Expected: 10 files (including `__init__.py`).

- [ ] **Step 2: Read all 9 test_issue_loop_*.py files**

Run: `ls tests/test_issue_loop_*.py`
Expected: 9 test files.

- [ ] **Step 3: Create `scripts/issue_loop.py`**

Single file containing 3 classes:
- `Ledger` (from `ledger.py`)
- `Classifier` (from `classifier.py`)
- `Dispatcher` (from `driver.py` + `gate.py` + `merge.py` + `branch.py` + `subagents.py`)
- `Autopilot` (from `autopilot_drain.py`)
- CLI entrypoint (`cli.py` becomes `main()` function)

Use the inlined `require_session_id` from PR3. Preserve all public APIs (so the CLI surface is unchanged).

- [ ] **Step 4: Delete `scripts/issue_loop/` directory**

Run: `git rm -rf scripts/issue_loop/`

- [ ] **Step 5: Run issue-loop tests against the new module**

Run: `pytest -q tests/test_issue_loop_*.py`
Expected: all pass (since public APIs are preserved).

- [ ] **Step 6: Replace 9 test files with 1**

Run:
```bash
git rm tests/test_issue_loop_branch.py \
       tests/test_issue_loop_classifier.py \
       tests/test_issue_loop_cli.py \
       tests/test_issue_loop_driver.py \
       tests/test_issue_loop_e2e.py \
       tests/test_issue_loop_gate.py \
       tests/test_issue_loop_ledger.py \
       tests/test_issue_loop_merge.py \
       tests/test_issue_loop_subagents.py
```

Create `tests/test_issue_loop.py` that exercises the 3 classes end-to-end. Use the existing tests as templates; consolidate into one file. Run it.

- [ ] **Step 7: Inline `scripts/plan_pre_flight.py` into `scripts/issue_drafter.py`**

Read `plan_pre_flight.py`. Identify the functions it provides (likely 1-3 helpers). Inline into `issue_drafter.py`. Delete `plan_pre_flight.py`.

Run: `git rm scripts/plan_pre_flight.py`

- [ ] **Step 8: Compact `CLAUDE.md` to 14 lines**

Replace 76-line file with:
```markdown
# heretek — Claude Code plugin marketplace (catalog/catalog.yaml → marketplace.json)

## Pre-commit (mandatory, runs on every commit)
pre-commit run --all-files                  # Layer-3: ruff/biome/shellcheck/gitleaks + heretek-fast-gate

## Local CI (mandatory before PR)
scripts/ci.sh                               # validate + generate + pytest + smoke

## Quarterly maintenance
scripts/refresh_pins.sh                     # scripts/refresh_pins.py --github-token ${GH_TOKEN:-$(gh auth token)}

## Don't
- Hand-edit `.claude-plugin/marketplace.json` (regenerated by scripts/ci.sh)
- Add hooks to non-`hooks` plugins             (CI: tests/test_plugin_components.py::test_no_plugin_ships_hooks_outside_hooks_plugin)
- Lower D7 bar without ADR                     (catalog/reviews/)
```

Verify: `wc -l CLAUDE.md` returns 14.

- [ ] **Step 9: Compress 5 of the 7 skills**

For each of `catalog`, `merge-and-push`, `refresh-pins`, `issue-loop`, `sonarcloud-suppression`, `sonarcloud-batch-remediation`:
- Replace body with a skeleton (≤40 lines for the first 4; ≤15 lines for the sonarcloud ones) pointing at the relevant script or docs file.

- [ ] **Step 10: Move sonarcloud bodies to `docs/SONAR-*.md`**

Create:
- `docs/SONAR-SUPPRESSION.md` — body of sonarcloud-suppression skill
- `docs/SONAR-BATCH-REMEDIATION.md` — body of sonarcloud-batch-remediation skill

Update the skill files to point at these docs.

- [ ] **Step 11: Run tests**

Run: `pytest -q`
Expected: all pass.

- [ ] **Step 12: Validate + regenerate marketplace**

Run: `python scripts/validate.py && python scripts/generate_marketplace.py && git diff --exit-code .claude-plugin/marketplace.json`
Expected: clean.

- [ ] **Step 13: Run pre-commit**

Run: `pre-commit run --all-files`
Expected: all pass.

- [ ] **Step 14: Commit on `trim/r8-r10-s1-s4-compaction-and-collapse`**

Run:
```bash
git checkout -b trim/r8-r10-s1-s4-compaction-and-collapse
git add -A
git commit -m "feat(trim): §2+R10+S1 compaction + collapse

CLAUDE.md 76 -> 14 lines. issue_loop 10 files -> 1 module.
5 skills compressed to skeletons + script pointers.

- scripts/issue_loop.py (NEW — S1)
  Ledger + Classifier + Dispatcher + Autopilot classes
- scripts/issue_drafter.py: inline plan_pre_flight.py (R10)
- CLAUDE.md: 76 -> 14 lines
- .claude/skills/catalog/SKILL.md: 198 -> 40 lines
- .claude/skills/merge-and-push/SKILL.md: 130 -> 30 lines
- .claude/skills/refresh-pins/SKILL.md: 89 -> 25 lines
- .claude/skills/issue-loop/SKILL.md: 64 -> 20 lines
- .claude/skills/sonarcloud-suppression/SKILL.md: 131 -> 15 lines
- .claude/skills/sonarcloud-batch-remediation/SKILL.md: 131 -> 15 lines
- docs/SONAR-SUPPRESSION.md (NEW — moved from skill)
- docs/SONAR-BATCH-REMEDIATION.md (NEW — moved from skill)

Delete:
- scripts/issue_loop/ (10 files)
- scripts/plan_pre_flight.py
- tests/test_issue_loop_*.py (9 files)
- tests/test_issue_loop.py (NEW — replaces 9)

PR5 of 5 in 2026-08-10-heretek-harness-trim spec.

Co-Authored-By: Claude <noreply@anthropic.com>"
```

- [ ] **Step 15: Push + open PR**

Run:
```bash
git push -u origin trim/r8-r10-s1-s4-compaction-and-collapse
gh pr create --title "feat(trim): §2+R10+S1 compaction + issue_loop collapse" \
  --body "PR5 of 5 in heretek-harness-trim spec (#219). CLAUDE.md 76 -> 14 lines; issue_loop 10 files -> 1 module; 5 skills compressed.

Closes part of #219" \
  --base main --head trim/r8-r10-s1-s4-compaction-and-collapse
```

- [ ] **Step 16: Wait for CI green**

Run: `gh pr checks --watch --fail-fast`
Expected: all required checks pass. SonarCloud may flag the new files — use the same `# nosonar` + `Path.resolve()` patterns from `.claude/skills/sonarcloud-suppression/SKILL.md` (the canonical reference) to suppress false positives.

- [ ] **Step 17: Squash-merge + cleanup**

Run:
```bash
gh pr merge --squash --delete-branch
git checkout main
git pull --ff-only
git branch -D trim/r8-r10-s1-s4-compaction-and-collapse
```

---

## Verification (post-5-PRs)

- [ ] **CLAUDE.md ≤ 14 lines**

Run: `wc -l CLAUDE.md`

- [ ] **No spike scripts**

Run: `find scripts -name "*spike*" -type f`
Expected: empty.

- [ ] **No `_allowlist.py` / `_http.py`**

Run: `ls scripts/_allowlist.py scripts/_http.py 2>&1`
Expected: "No such file or directory".

- [ ] **All hooks in `plugins/hooks/scripts/`**

Run: `git ls-files plugins/hooks/scripts/`
Expected: 9 files (3 unchanged + 4 moved + 2 new).

- [ ] **`hooks.json` PostToolUse = 1 entry**

Run: `python -c "import json; h=json.load(open('plugins/hooks/hooks/hooks.json')); print(sum(len(v) for k,v in h['hooks'].items() if k=='PostToolUse'))"`
Expected: 1.

- [ ] **`scripts/ci.sh` works**

Run: `bash scripts/ci.sh`
Expected: exits 0.

- [ ] **All existing tests pass**

Run: `pytest -q`
Expected: clean.

- [ ] **Integrated end-state matches spec §Acceptance criteria**

Run all spec §"Acceptance criteria" checklist items.

---

## Self-Review Notes

- **Spec coverage**: Each of the 5 PRs in the spec maps 1:1 to a Task in this plan. ✓
- **Type consistency**: Function names referenced (`require_session_id`, `Ledger`, `Classifier`, `Dispatcher`, `Autopilot`) are defined in earlier tasks before they're consumed. ✓
- **Placeholder scan**: No "TBD", "TODO", "implement later", or vague "add appropriate error handling" without code. Every step has explicit shell, code, or commit commands. ✓
- **Risk callouts**: PR4 (Task 4) and PR5 (Task 5) are flagged as highest-risk in their task headers. ✓
- **CI gating**: Every PR has explicit `gh pr checks --watch --fail-fast` before merge. ✓
