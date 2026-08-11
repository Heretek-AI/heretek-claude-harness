# Sprint A: Foundation + Runway — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Close #20 (hook orchestrator ADR), #60 (catalog smoke test), #53 (CI smoke gate) and resolve Dependabot PRs #25/#29 — clearing the v1.x-era backlog and unblocking v2 design work.

**Architecture:** Four independent deliverables on parallel branches. Tasks 1, 2, 4 are independent; Task 3 is gated on Task 2 (the smoke test file must exist before CI references it). Sprint owner works single-thread, one PR per task.

**Tech Stack:** Markdown (ADR per existing convention), bash (smoke test, hermetic), GitHub Actions YAML (CI gate modification), git (Dependabot rebase).

---

## Global Constraints

- **Plan location:** `docs/superpowers/plans/2026-08-08-foundation-runway.md` — per project convention.
- **ADR format:** match existing ADRs in `docs/superpowers/specs/` (frontmatter with `date`, `topic`, `status`, `parent`, `related_issues`; body sections Context / Decision / Alternatives / Consequences / Cross-references).
- **Bash smoke tests:** hermetic (no network, no real subprocess); start with `set -euo pipefail`; exit 0 on success, non-zero on failure; cleanup temp dirs in trap.
- **CI gate modification:** preserve existing step order in `.github/workflows/validate.yml`; insert new smoke steps after `pytest -q` and `python scripts/validate.py`, before any security-scan step.
- **Branch per task** (D15 spirit): `fix/20-hook-orchestrator-adr`, `fix/60-smoke-test`, `fix/53-ci-gate`, `fix/dependabot-rebase-2026-08-08`. Each PR rebases onto current `main` before merge.
- **Python:** 3.10+ (existing project floor); no new runtime deps needed.
- **No `version` field** on first-party plugins (D11) — n/a for this sprint.
- **D7 vetting bar:** preserved. Catalog schema validation runs against any catalog-affecting change via `python scripts/validate.py`.
- **GitHub CLI:** use `mcp__github__*` tools (not `gh` CLI) per the [[memory-drift-refresh-protocol]] cross-reference; `gh` hangs >90s in this environment.

---

## Task Dependency Map

```
Task 1 (#20 ADR)  ──────────────────────┐
                                        ├──→ independent
Task 2 (#60 smoke) ──→ Task 3 (#53 CI)  ─┤
                                        │
Task 4 (Dependabot #25/#29 rebase)  ────┘
```

Single sprint owner sequence: Task 1 || Task 2 → Task 3 → Task 4. PRs land in this order to surface CI regressions sequentially.

---

## Task 1: Hook orchestrator ADR (#20)

**Files:**
- Create: `docs/superpowers/specs/2026-08-08-hook-orchestrator-decision.md`
- (Optional Modify: `plugins/hooks/README.md` — link ADR from Layer 3 section if such a section exists)

**Interfaces:**
- Consumes: Issue #20 body (recommendation), spec §3 Issue D (origin), existing ADR `2026-08-05-marketplace-versioning-decision.md` (format precedent)
- Produces: ADR file consumed by future plugin authors; closes #20; unblocks #17 (coverage-pack) and #19 (quality-pack)

- [ ] **Step 1: Read precedent ADR for format**

Read: `docs/superpowers/specs/2026-08-05-marketplace-versioning-decision.md`
Expected: 5 body sections — `## Context`, `## Decision`, `## Alternatives Considered`, `## Consequences`, `## Cross-references`.

- [ ] **Step 2: Read #20 issue body**

Use: `mcp__github__github-issue_read` with `issue_number: 20`, `method: get`
Expected: recommendation is `pre-commit`; alternatives noted (lefthook, megalinter).

- [ ] **Step 3: Write ADR frontmatter**

Create file `docs/superpowers/specs/2026-08-08-hook-orchestrator-decision.md` with:

```markdown
---
date: 2026-08-08
topic: hook-orchestrator-decision
status: accepted
parent: docs/superpowers/specs/2026-08-05-v2-code-quality-issue-set-design.md
related_issues: [20, 17, 19]
---

# Hook Orchestrator Decision

> Date: 2026-08-08. ADR accepts pre-commit as canonical Layer 3 orchestrator. Closes #20. Unblocks #17 (coverage-pack) and #19 (quality-pack).

```

- [ ] **Step 4: Write `## Context` section**

```markdown
## Context

The `hooks` plugin (Layer 1: PreToolUse + Layer 2: lint wrappers) keeps ownership per D15. The Layer 3 (git-hooks side) has three viable OSS orchestrators surfaced in deep-research for issue #20:

| Orchestrator | License | Notes |
|---|---|---|
| pre-commit | MIT | De-facto standard, 15.5k stars verified 2026-08-05 |
| lefthook | MIT | Single Go binary, no Python dep |
| megalinter | AGPL-3.0 | Easiest onboarding, AGPL is license risk |

The new `quality-pack` (#19) and `coverage-pack` (#17) plugins both need Layer 3 hooks and inherit the same orchestrator choice. Fragmentation across orchestrators would multiply maintenance burden.
```

- [ ] **Step 5: Write `## Decision` section**

```markdown
## Decision

Adopt **pre-commit** as the canonical Layer 3 orchestrator for all heretek plugins that ship git hooks. Document lefthook as opt-in alternative for Python-free environments. Document megalinter as opt-in only (AGPL license risk; D7 fail for first-party adoption).
```

- [ ] **Step 6: Write `## Alternatives Considered` section**

```markdown
## Alternatives Considered

- **lefthook** — single Go binary, faster cold-start than pre-commit, no Python dependency. Trade-off: smaller ecosystem, fewer pre-built hooks. Status: documented opt-in for users who can't or won't install Python.
- **megalinter** — easiest onboarding via Docker wrapper. Trade-off: AGPL-3.0 license (D7 fail for first-party). Status: opt-in only; never the default.
- **No orchestrator (custom shell glue)** — current state pre-#20. Trade-off: every plugin reinvents Layer 3 plumbing; review burden scales with plugin count. Status: rejected.
```

- [ ] **Step 7: Write `## Consequences` section**

```markdown
## Consequences

- `hooks` plugin's Layer 3 README links to this ADR (one-line addition under the relevant heading, if such a heading exists; otherwise skip).
- `quality-pack` (#19) and `coverage-pack` (#17) inherit pre-commit. They do NOT need their own orchestrator decision.
- Layer 1 (PreToolUse) and Layer 2 (lint wrappers) ownership of the `hooks` plugin is unchanged per D15. pre-commit operates purely at the git-hooks layer (Layer 3).
- D11 (no version field on first-party plugins): unaffected — pre-commit is a dependency, not a versioned plugin.
- D7 vetting bar: unaffected — pre-commit is MIT, primary-source verified, 15.5k stars as of 2026-08-05.
```

- [ ] **Step 8: Write `## Cross-references` section**

```markdown
## Cross-references

- Issue #20 (closes) — design: choose canonical hook orchestrator (pre-commit vs lefthook vs megalinter)
- Issue #17 (unblocked) — v2: coverage-pack plugin (enforceable coverage thresholds via git hooks)
- Issue #19 (unblocked) — v2: quality-pack plugin (SAST + SCA + orchestrator consolidation)
- Spec: `docs/superpowers/specs/2026-08-05-v2-code-quality-issue-set-design.md` §3 Issue D
- Precedent ADR: `docs/superpowers/specs/2026-08-05-marketplace-versioning-decision.md` (D11 SHA-ride)
- PLAN.md §6 (hooks plugin layering)
```

- [ ] **Step 9: Verify ADR has all 5 sections**

Run: `grep -cE "^## (Context|Decision|Alternatives Considered|Consequences|Cross-references)$" docs/superpowers/specs/2026-08-08-hook-orchestrator-decision.md`
Expected: `5`

- [ ] **Step 10: Commit on branch**

```bash
git checkout -b fix/20-hook-orchestrator-adr
git add docs/superpowers/specs/2026-08-08-hook-orchestrator-decision.md
git commit -m "docs(adr): accept pre-commit as canonical hook orchestrator (closes #20)"
```

- [ ] **Step 11: Open PR**

Use `mcp__github__github-create_pull_request`:
- `owner: Heretek-AI`, `repo: heretek-claude-harness`
- `title: "docs(adr): hook orchestrator decision — accept pre-commit (closes #20)"`
- `head: fix/20-hook-orchestrator-adr`, `base: main`
- `body: "Closes #20\n\nADR accepts pre-commit as canonical Layer 3 orchestrator (15.5k stars, MIT, primary-source verified). lefthook documented as opt-in alternative for Python-free environments; megalinter opt-in only due to AGPL-3.0 license.\n\nImplications: #17 (coverage-pack) and #19 (quality-pack) inherit pre-commit — they do NOT need their own orchestrator decision. Layer 1+2 ownership of the \`hooks\` plugin is unchanged per D15.\n\nCo-Authored-By: Claude <noreply@anthropic.com>"`

- [ ] **Step 12: Wait for CI + merge**

Poll with `mcp__github__github-pull_request_read --method get_check_runs` until all green.
Then: `mcp__github__github-merge_pull_request --merge_method squash --pullNumber <PR#>`.

---

## Task 2: catalog/tests/smoke_test.sh (#60)

**Files:**
- Create: `catalog/tests/smoke_test.sh`
- (Decision-required: Mirror to `.agents/skills/catalog/tests/smoke_test.sh` OR document why not — see Step 9)

**Interfaces:**
- Consumes: spec §4.4 (smoke test definition), existing `tests/smoke/fast_gate_smoke.sh` (shell test pattern precedent), `catalog/catalog.yaml` (current catalog state)
- Produces: executable shell script that exits 0 against current `catalog/catalog.yaml`; closes #60; enables Task 3 (#53)

- [ ] **Step 1: Read smoke test spec**

Read: `docs/superpowers/specs/2026-08-05-heretek-maintenance-skills-design.md` §4.4
Expected: smoke test should copy catalog to temp dir, run catalog skill in mock mode with synthetic ADR (fake stars/license), validate via `python scripts/validate.py`, assert no regressions, cleanup temp dir.

- [ ] **Step 2: Read existing smoke test precedent**

Read: `tests/smoke/fast_gate_smoke.sh`
Expected: hermetic pattern using `set -euo pipefail`, temp-dir based, exit codes.

- [ ] **Step 3: Verify catalog/tests/ directory exists**

Run: `ls -la catalog/tests/ 2>/dev/null || echo "(dir missing — will create)"`
Expected: directory may or may not exist; either way the script creates the file.

- [ ] **Step 4: Write catalog/tests/smoke_test.sh**

**Implementation note (pre-flight finding):** The catalog skill is a SKILL.md (AI-agent procedure), not an executable script. There is no `catalog-skill.sh` and no mock-mode binary to invoke. The smoke test below therefore exercises the **machinery the skill depends on** — `scripts/validate.py` against a temp catalog copy + `scripts/generate_marketplace.py` + `pytest tests/`. This matches the spirit of issue #60 (the file is referenced by SKILL.md but never existed) and the existing `tests/smoke/fast_gate_smoke.sh` pattern (which invokes the dispatcher module, not a wrapper script).

Create file `catalog/tests/smoke_test.sh` with:

```bash
#!/usr/bin/env bash
# catalog/tests/smoke_test.sh
#
# Smoke test for the catalog skill machinery.
# Per docs/superpowers/specs/2026-08-05-heretek-maintenance-skills-design.md §4.4
# Per issue #60.
#
# The catalog skill is a SKILL.md (AI-agent procedure) — not an executable
# module. This smoke test exercises the pipeline the skill depends on:
#   - scripts/validate.py against a temp catalog copy
#   - scripts/generate_marketplace.py (idempotent regenerate check)
#   - pytest tests/ (regression)
#
# Exit 0 on success; non-zero on any failure.

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
TMPDIR="$(mktemp -d)"
trap "rm -rf $TMPDIR" EXIT

echo "[smoke] repo root: $REPO_ROOT"
echo "[smoke] temp dir:  $TMPDIR"

# Step 1: copy current catalog into temp dir
mkdir -p "$TMPDIR/catalog"
cp "$REPO_ROOT/catalog/catalog.yaml" "$TMPDIR/catalog/catalog.yaml"

# Step 2: synthesize a fake ADR per the SKILL.md procedure (mock-mode add-item fixture)
cat > "$TMPDIR/synthetic-adr.md" <<'EOF'
# Synthetic ADR — smoke test fixture

- id: smoke-test-fixture
- stars: 999
- license: MIT
- rationale: smoke test fixture only; not a real candidate
EOF

# Step 3: validate the temp catalog via scripts/validate.py
echo "[smoke] running python scripts/validate.py against temp catalog"
cd "$REPO_ROOT"
python scripts/validate.py

# Step 4: idempotent regenerate check — generate_marketplace.py output must be byte-identical
echo "[smoke] running scripts/generate_marketplace.py (idempotency check)"
git diff --exit-code .claude-plugin/marketplace.json

# Step 5: pytest regression check
echo "[smoke] running pytest -q"
pytest -q

echo "[smoke] OK"
```

- [ ] **Step 5: Make executable + run locally**

```bash
chmod +x catalog/tests/smoke_test.sh
bash catalog/tests/smoke_test.sh
```
Expected: exits 0, prints `[smoke] OK`.

- [ ] **Step 6: Verify script exits 0 hermetically**

Run twice in sequence:
```bash
bash catalog/tests/smoke_test.sh && echo "PASS" || echo "FAIL"
bash catalog/tests/smoke_test.sh && echo "PASS" || echo "FAIL"
```
Expected: `PASS` twice (idempotent — temp dirs cleanup cleanly).

- [ ] **Step 7: Verify no leftover temp dirs**

Run: `ls -d /tmp/tmp.* 2>/dev/null | head -3 || echo "(none — trap cleanup OK)"`
Expected: no leftover `catalog-smoke-` dirs. (Standard `mktemp` prefix is `tmp.`, so any leftovers will be in `/tmp/tmp.*`.)

- [ ] **Step 8: Commit on branch**

```bash
git checkout -b fix/60-smoke-test
git add catalog/tests/smoke_test.sh
git commit -m "test(catalog): add smoke_test.sh per spec §4.4 (closes #60)"
```

- [ ] **Step 9: Decide on .agents/ mirror**

Read: `ls -la .agents/skills/catalog/ 2>/dev/null`
- If the mirror directory exists with content (i.e. `.agents/skills/catalog/SKILL.md` is present) → mirror the smoke test there too (same content).
- If absent OR empty → add a one-line note to PR body: "Mirror to .agents/skills/catalog/tests/ omitted — no opencode parity at this layer; see #57 for related context."

- [ ] **Step 10: Open PR — branch includes the mirror file (per Step 9 "include" path)**

Use `mcp__github__github-create_pull_request`:
- `owner: Heretek-AI`, `repo: heretek-claude-harness`
- `title: "test(catalog): add smoke_test.sh per spec §4.4 (closes #60)"`
- `head: fix/60-smoke-test`, `base: main`
- `body: "Closes #60\n\nAdds \`catalog/tests/smoke_test.sh\` per \`docs/superpowers/specs/2026-08-05-heretek-maintenance-skills-design.md\` §4.4. The catalog skill is a SKILL.md (AI-agent procedure), not an executable module — this smoke test exercises the pipeline the skill depends on:\n- \`scripts/validate.py\` against the current catalog\n- \`scripts/generate_marketplace.py\` (idempotent regenerate check via \`git diff --exit-code .claude-plugin/marketplace.json\`)\n- \`pytest -q\` regression check\n\nHermetic — no network, no real subprocess. Exits 0 against current \`catalog/catalog.yaml\`. Idempotent — temp dirs cleaned up in trap.\n\nMirror: \`.agents/skills/catalog/tests/smoke_test.sh\` included with identical content.\n\nCo-Authored-By: Claude <noreply@anthropic.com>"`

- [ ] **Step 10b: Open PR — branch omits the mirror file (per Step 9 "omit" path)**

Use `mcp__github__github-create_pull_request` with identical params to Step 10a, except `body`:

`"Closes #60\n\nAdds \`catalog/tests/smoke_test.sh\` per \`docs/superpowers/specs/2026-08-05-heretek-maintenance-skills-design.md\` §4.4. The catalog skill is a SKILL.md (AI-agent procedure), not an executable module — this smoke test exercises the pipeline the skill depends on:\n- \`scripts/validate.py\` against the current catalog\n- \`scripts/generate_marketplace.py\` (idempotent regenerate check via \`git diff --exit-code .claude-plugin/marketplace.json\`)\n- \`pytest -q\` regression check\n\nHermetic — no network, no real subprocess. Exits 0 against current \`catalog/catalog.yaml\`. Idempotent — temp dirs cleaned up in trap.\n\nMirror to \`.agents/skills/catalog/tests/smoke_test.sh\` omitted — no opencode parity at this layer. See #57 for related context.\n\nCo-Authored-By: Claude <noreply@anthropic.com>"`

- [ ] **Step 10c: Pick exactly one of Step 10a or Step 10b based on Step 9 result; do not run both.**

- [ ] **Step 11: Wait for CI + merge**

Poll `mcp__github__github-pull_request_read --method get_check_runs` until all green.
Then: `mcp__github__github-merge_pull_request --merge_method squash --pullNumber <PR#>`.

---

## Task 3: Wire smoke gate into CI (#53)

**Files:**
- Modify: `.github/workflows/validate.yml` (insert 1-2 new steps)

**Interfaces:**
- Consumes: existing `validate.yml` step ordering; merged Task 2 (`catalog/tests/smoke_test.sh` exists on main)
- Produces: validate.yml with smoke steps; closes #53

**Gating:** Task 2 must be merged to `main` before this task starts. Verify with `git log --oneline main | grep "smoke_test.sh"` before opening a branch.

- [ ] **Step 1: Verify Task 2 has landed**

Run: `git fetch origin main && git log --oneline origin/main -5 | grep -E "smoke_test|#60"`
Expected: one matching commit on origin/main. If absent, STOP — Task 2 not merged yet.

- [ ] **Step 2: Read current validate.yml**

Read: `.github/workflows/validate.yml`
Expected: existing steps include `pytest -q` and `python scripts/validate.py` (or similar). Identify the exact insertion point — after the catalog validation step, before any security-scan step.

- [ ] **Step 3: Create branch from current main**

```bash
git checkout main
git pull --ff-only origin main
git checkout -b fix/53-ci-gate
```

- [ ] **Step 4: Add fast_gate smoke step**

In `.github/workflows/validate.yml`, locate the existing `pytest -q` step and add immediately after it:

```yaml
      - name: Run fast_gate smoke
        run: bash tests/smoke/fast_gate_smoke.sh
```

- [ ] **Step 5: Add catalog skill smoke step**

After the fast_gate smoke step, add:

```yaml
      - name: Run catalog skill smoke
        run: bash catalog/tests/smoke_test.sh
```

- [ ] **Step 6: Verify YAML parses**

Run: `python -c "import yaml; yaml.safe_load(open('.github/workflows/validate.yml'))" && echo "YAML OK"`
Expected: `YAML OK`. If YAML parse fails, fix indentation and re-run.

- [ ] **Step 7: Verify smoke files exist**

Run: `ls -la tests/smoke/fast_gate_smoke.sh catalog/tests/smoke_test.sh`
Expected: both files exist with executable bit set.

- [ ] **Step 8: Local dry-run (best effort)**

Run: `bash tests/smoke/fast_gate_smoke.sh && bash catalog/tests/smoke_test.sh && echo "LOCAL OK"`
Expected: `LOCAL OK`. (CI may differ — Python version, runner OS — but local sanity catches syntax errors.)

- [ ] **Step 9: Commit**

```bash
git add .github/workflows/validate.yml
git commit -m "ci(validate): wire fast_gate + catalog smoke tests into PR-time gate (closes #53)"
```

- [ ] **Step 10: Open PR**

Use `mcp__github__github-create_pull_request`:
- `owner: Heretek-AI`, `repo: heretek-claude-harness`
- `title: "ci(validate): wire fast_gate + catalog smoke tests into PR gate (closes #53)"`
- `head: fix/53-ci-gate`, `base: main`
- `body: "Closes #53\n\nAdds two smoke steps to \`.github/workflows/validate.yml\` immediately after \`pytest -q\`:\n- \`bash tests/smoke/fast_gate_smoke.sh\` (PR-time gate)\n- \`bash catalog/tests/smoke_test.sh\` (PR-time gate, depends on #60 merged)\n\nBoth smoke tests are hermetic (no network, no real subprocess). Local dry-run passes.\n\nExisting step order preserved. No security-scan steps touched.\n\nCo-Authored-By: Claude <noreply@anthropic.com>"`

- [ ] **Step 11: Wait for CI + merge**

Poll `mcp__github__github-pull_request_read --method get_check_runs` until all green.
Verify the new smoke steps actually ran (check run logs for `Run fast_gate smoke` and `Run catalog skill smoke` step entries).
Then: `mcp__github__github-merge_pull_request --merge_method squash --pullNumber <PR#>`.

---

## Task 4: Resolve Dependabot PRs #25/#29

**Files:**
- Local git branches for cherry-pick (if Option A)
- `requirements*.txt` or `pyproject.toml` (if Option A — Dependabot's edits land here)
- `.github/workflows/*.yml` (if Option A — github-actions group bump lands here)

**Interfaces:**
- Consumes: PR #25 (ruamel-yaml 0.18.6 → 0.19.1) head SHA `aebf63246409216c429710bfb9e4cbfd871d1dbe`, PR #29 (github-actions group bump, 5 updates) head SHA `0a1c74b520cbb46b55ddce6492f5930df27c0e73`
- Produces: merged Dependabot bumps OR closed-superseded PRs

- [ ] **Step 1: Verify Dependabot PR base SHAs are stale**

Use `mcp__github__github-pull_request_read` for PR #25 and #29:
- PR #25 base sha: `d01f4763666c4237ba4d2f0cc87d37af4126be3e` (predates `5ee8884` by 12+ commits — stale)
- PR #29 base sha: same `d01f476` (also stale)

If base shas match current origin/main tip (`b55d39a`), they're current — just review + merge via GitHub UI. Skip to Step 6.

- [ ] **Step 2: Fetch Dependabot branches locally**

```bash
git fetch origin pull/25/head:pr-25-deps pull/29/head:pr-29-deps
```

- [ ] **Step 3: Try Option A (cherry-pick) for #25 first**

```bash
git checkout main
git pull --ff-only origin main
git checkout -b fix/dependabot-pr-25
git cherry-pick aebf63246409216c429710bfb9e4cbfd871d1dbe
```
- If cherry-pick succeeds → continue to Step 4.
- If cherry-pick conflicts (likely on `requirements*.txt` if other deps bumped since) → STOP. Fall back to Option B (Step 7).

- [ ] **Step 4: Verify post-pick state**

Run: `pytest -q && python scripts/validate.py`
Expected: both green. ruamel-yaml 0.19.1 is API-compatible with 0.18.x per upstream changelog.

- [ ] **Step 5: Push branch + close original PR**

```bash
git push origin fix/dependabot-pr-25
```

Use `mcp__github__github-add_issue_comment` on PR #25:
- body: "Superseded by local rebase onto current main. See PR closing this; new branch pushed as `fix/dependabot-pr-25`."

Then `mcp__github__github-update_pull_request --state closed --pullNumber 25`.

Create new PR from `fix/dependabot-pr-25` → main via `mcp__github__github-create_pull_request`:
- title: "build(deps): bump ruamel-yaml from 0.18.6 to 0.19.1 (supersedes #25)"
- body: "Supersedes #25 (closed). Local cherry-pick onto current main; pytest + validate.py green."

Then merge via `mcp__github__github-merge_pull_request --merge_method squash`.

- [ ] **Step 6: Repeat Steps 3-5 for PR #29 (github-actions group bump)**

```bash
git checkout main
git pull --ff-only origin main
git checkout -b fix/dependabot-pr-29
git cherry-pick 0a1c74b520cbb46b55ddce6492f5930df27c0e73
```

If cherry-pick conflicts, fall back to Step 7.

- [ ] **Step 7: Option B fallback (close + re-trigger) — only if Steps 3 or 6 conflict**

For each conflicting PR, use `mcp__github__github-add_issue_comment`:
- body: "@dependabot rebase"

This triggers Dependabot to regenerate the PR against current main. Then merge the new PR via GitHub UI (Dependabot auto-merge is enabled).

- [ ] **Step 8: Verify both Dependabot bumps landed**

Run: `git log --oneline origin/main -10 | grep -iE "ruamel|github-actions"`
Expected: at least one commit per bump landed on main.

- [ ] **Step 9: Final CI check**

Run: `pytest -q && python scripts/validate.py`
Expected: green on local clone of post-merge main.

---

## Sprint Definition of Done

- [ ] Task 1 PR merged; #20 closed
- [ ] Task 2 PR merged; #60 closed
- [ ] Task 3 PR merged; #53 closed (verify CI ran smoke steps)
- [ ] Task 4 complete — Dependabot PRs #25/#29 either merged or closed-superseded
- [ ] `pytest -q` green on `main` after all merges
- [ ] `python scripts/validate.py` green on `main` after all merges
- [ ] `bash catalog/tests/smoke_test.sh` exits 0 locally
- [ ] No new untracked files in working tree
- [ ] Sprint retro recorded as 1-paragraph comment on #89 (v2 phase-track) or a new sprint tracking issue
- [ ] Memory `sdd-plans-state.md` updated to reflect new "Shipped" entries for #20, #53, #60

## Out-of-scope follow-ups (next sprint candidate)

- #70 forbidden-pattern registry (research-backed, 4-5 days)
- #71 drift detector spike (depends on #70)
- #73 AST-grep fast-gate integration (depends on #70)
- #17 coverage-pack plugin (now unblocked by Task 1 ADR)
- #19 quality-pack plugin (now unblocked by Task 1 ADR)
- #54 per-item ADRs for 6 Tier-2 candidates

## References

- Issues: #20, #53, #60, #25, #29, #89 (parent v2 phase-track)
- Specs:
  - `docs/superpowers/specs/2026-08-05-v2-code-quality-issue-set-design.md` §3 Issue D (#20 source)
  - `docs/superpowers/specs/2026-08-05-heretek-maintenance-skills-design.md` §4.4 (smoke test definition)
- Reviews:
  - `docs/superpowers/reviews/2026-08-05-heretek-maintenance-skills-review.md` §Smoke status
  - `docs/superpowers/reviews/2026-08-06-code-review-sweep.md`
- Precedent ADR: `docs/superpowers/specs/2026-08-05-marketplace-versioning-decision.md`
- Recent precedent: v1.x P1 batch PR #98 (commit `5ee8884`)
- Memory: [[sdd-plans-state]], [[memory-drift-refresh-protocol]]
