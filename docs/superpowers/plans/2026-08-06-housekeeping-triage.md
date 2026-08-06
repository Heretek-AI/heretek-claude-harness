# Housekeeping Triage Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** File 11 flat GitHub issues on `Heretek-AI/heretek-claude-harness` per `docs/superpowers/specs/2026-08-06-housekeeping-triage-design.md`, with priority ordering, template body, existing labels only, and full cross-links to originating spec/plan/review sections. The deliverable is the 11 filed issues + post-filing verification per spec §7; no implementation of the items themselves.

**Architecture:** Per-issue filing loop. Each issue gets its own task with pre-filing discovery (per spec Appendix A), template body composition (per spec §4), `gh issue create` invocation, and post-filing verification. A final task runs the spec §7 cross-cutting verification. Tasks are sequenced per spec §5 to minimize context-switching and surface blockers early.

**Tech Stack:** GitHub CLI (`gh`), GitHub Issues API, `git`, `bash`. No new dependencies.

## Global Constraints

Copied verbatim from `docs/superpowers/specs/2026-08-06-housekeeping-triage-design.md`:

- Reuse only existing repo labels: `{chore, tech-debt, bug, help wanted, documentation, enhancement, question}`. **No new labels created.**
- Issue titles use a mix of conventional-commit prefixes (`chore:`, `fix:`, `docs:`) and label-derived prefixes (`enhancement:`, `question:`). Lowercase after the colon. ≤70 chars.
- Each issue body follows §4 template: `## Problem` → `## Origin / cross-references` → `## Recommended fix sketch` → `## Definition of done`.
- Cross-links always include the local `docs/superpowers/...` path; GitHub issue/PR links included only when the issue/PR already exists. No external URLs in the body unless the upstream is the source of truth (e.g., licenses).
- P1/P2/P3 priority is a **body-signal ranking for triage ordering**, NOT a GitHub label. Mention priority rationale in the body, never as a label.
- No `gh` write operations outside `gh issue create` (no comments, edits, label creation, project edits).
- Pre-filing discovery per spec Appendix A is mandatory before composing each body. If discovery surfaces that the item is already done (e.g., `.github/dependabot.yml` exists in Task 8), do NOT file a redundant issue — instead, add the finding to this plan's task list as a "discovery note" and skip the filing.
- Cross-reference path format: `docs/superpowers/specs/...`, `docs/superpowers/plans/...`, `docs/superpowers/reviews/...`. No bare spec names.

---

### Task 1: File issue #1 — `chore: add .coverage to .gitignore + configure coverage.xml for CI`

**Issue produces:** GitHub issue with title `chore: add .coverage to .gitignore + configure coverage.xml for CI`, labels `chore` + `tech-debt`, P1 body signal.

**Files:** None locally modified. Produces one GitHub issue.

- [ ] **Step 1: Pre-filing discovery — verify `.coverage` is untracked and not gitignored**

Run:
```bash
cd /home/john/Projects/heretek-claude-harness
git ls-files --error-unmatch .coverage 2>&1 | head -1   # expect: error (untracked)
git status --short .coverage                            # expect: ?? .coverage
grep -E "^\.coverage|coverage\.xml" .gitignore           # expect: no match
```

If `.coverage` is already in `.gitignore`, skip this task — add discovery note and move to Task 2.

- [ ] **Step 2: Pre-filing discovery — confirm `coverage.xml` is not configured in `pyproject.toml`**

Run:
```bash
grep -A 5 "\[tool\.coverage" pyproject.toml 2>&1 | head -10   # expect: empty or no xml_output line
```

If `coverage.xml` is already configured, note it in the body and continue.

- [ ] **Step 3: Compose the issue body using the spec §4 template**

Use this exact body (markdown body, escaped for `gh issue create --body -` heredoc):

```markdown
## Problem

`.coverage` (SQLite coverage database produced by `pytest --cov`) is currently
untracked in the working tree and is NOT in `.gitignore`. This produces noisy
`git status` output on every test run and risks accidental commits.
`pyproject.toml` does not configure `coverage.xml` output, so CI has no
machine-readable coverage artifact to consume.

## Origin / cross-references

- `docs/superpowers/specs/2026-08-05-v1-launch-remediation-design.md` §9
  (verification step: `.coverage` gitignore + `coverage.xml` configuration)

## Recommended fix sketch

- Edit `.gitignore` to add `.coverage` and `coverage.xml`
- Edit `pyproject.toml` `[tool.coverage]` section to set `xml_output = "coverage.xml"`
- Verify: `git status` is clean after `coverage report`
- Re-run `pytest --cov` and confirm `coverage.xml` is produced alongside `.coverage`

## Definition of done

- [ ] `.gitignore` contains `.coverage` and `coverage.xml`
- [ ] `pyproject.toml` `[tool.coverage]` configures `xml_output = "coverage.xml"`
- [ ] `git status` shows no `.coverage` or `coverage.xml` after running tests
- [ ] `pytest --cov` produces both `.coverage` (SQLite) and `coverage.xml` (CI-readable)
- [ ] `python scripts/validate.py` exits 0
- [ ] `pytest -q` exits 0
```

- [ ] **Step 4: File the issue**

Run:
```bash
gh issue create \
  --repo Heretek-AI/heretek-claude-harness \
  --title "chore: add .coverage to .gitignore + configure coverage.xml for CI" \
  --label "chore,tech-debt" \
  --body "$(cat <<'BODY_EOF'
<insert Step 3 body here, verbatim>
BODY_EOF
)"
```

Record the new issue number as `ISSUE_1`.

- [ ] **Step 5: Verify the issue landed**

Run:
```bash
gh issue view "$ISSUE_1" --repo Heretek-AI/heretek-claude-harness \
  --json title,labels,body \
  | jq -r '.title, (.labels | map(.name) | join(",")), .body'
```

Expected: title matches exactly, labels are `chore,tech-debt`, body has all 4 sections (`## Problem`, `## Origin`, `## Recommended`, `## Definition`).

---

### Task 2: File issue #2 — `fix: mirror find-skills skill to .agents/skills/ (or document why not)`

**Issue produces:** GitHub issue with title `fix: mirror find-skills skill to .agents/skills/ (or document why not)`, labels `bug` + `help wanted`, P1 body signal.

**Files:** None locally modified. Produces one GitHub issue.

- [ ] **Step 1: Pre-filing discovery — read `find-skills` SKILL.md to determine if it's intentional**

Run:
```bash
test -f .agents/skills/find-skills/SKILL.md && echo "agents exists" || echo "agents missing"
test -f .claude/skills/find-skills/SKILL.md && echo "claude exists"  || echo "claude missing"
test -d .agents/skills/find-skills && echo "agents dir exists"
test -d .claude/skills/find-skills && echo "claude dir exists"
ls .claude/skills/find-skills/ 2>&1 | head
```

If `find-skills` is already mirrored (both exist with identical content per `diff -q`), skip this task — add discovery note and move to Task 3.

- [ ] **Step 2: Compose the issue body**

```markdown
## Problem

The `find-skills` skill lives at `.agents/skills/find-skills/SKILL.md` AND at
`.claude/skills/find-skills/` (directory), but neither location is committed to
the repo (`git status` shows them as untracked). The catalog skill
(`/heretek:catalog`) shipped in PR #22 mirrored all 3 maintenance skills to
both runtimes; `find-skills` follows the same pattern but was apparently added
without committing.

If intentional: document why `find-skills` is not committed (perhaps a v2
plugin awaiting ADR). If unintentional: commit the mirror copies.

## Origin / cross-references

- Working-tree hygiene: `git status` shows both `.agents/skills/find-skills/`
  and `.claude/skills/find-skills/` as untracked
- Mirror parity convention: `docs/superpowers/specs/2026-08-05-heretek-maintenance-skills-design.md`
  §3 (file layout — both `.claude/skills/` and `.agents/skills/` mirror)

## Recommended fix sketch

- If intentional: add a one-line note to a `docs/superpowers/specs/` ADR
  explaining why `find-skills` is untracked
- If unintentional: commit the mirror copies to git with a conventional-commit
  message (`feat(skills): commit find-skills skill mirror`)
- Either way: remove the entries from `git status` (commit OR add to
  `.gitignore` if truly temporary)

## Definition of done

- [ ] Decision documented (commit OR ADR note) — no more `?? .agents/skills/find-skills/` in `git status`
- [ ] `git status` shows no untracked `find-skills` paths
- [ ] If committed: `diff -q .claude/skills/find-skills/SKILL.md .agents/skills/find-skills/SKILL.md` exits 0
- [ ] `python scripts/validate.py` exits 0
- [ ] `pytest -q` exits 0
```

- [ ] **Step 3: File the issue**

Run:
```bash
gh issue create \
  --repo Heretek-AI/heretek-claude-harness \
  --title "fix: mirror find-skills skill to .agents/skills/ (or document why not)" \
  --label "bug,help wanted" \
  --body "$(cat <<'BODY_EOF'
<insert Step 2 body here, verbatim>
BODY_EOF
)"
```

Record the new issue number as `ISSUE_2`.

- [ ] **Step 4: Verify the issue landed**

Run:
```bash
gh issue view "$ISSUE_2" --repo Heretek-AI/heretek-claude-harness \
  --json title,labels,body \
  | jq -r '.title, (.labels | map(.name) | join(",")), .body' | head -3
```

Expected: title matches, labels are `bug,help wanted`, body has 4 sections.

---

### Task 3: File issue #3 — `chore: commit untracked tests/fixtures/fast_gate/ files (post-#15 SP3 fix artifacts)`

**Issue produces:** GitHub issue with title `chore: commit untracked tests/fixtures/fast_gate/ files (post-#15 SP3 fix artifacts)`, labels `chore` + `tech-debt`, P1 body signal.

**Files:** None locally modified. Produces one GitHub issue.

- [ ] **Step 1: Pre-filing discovery — inspect each untracked fixture file**

Run:
```bash
cd /home/john/Projects/heretek-claude-harness
git status --short tests/fixtures/fast_gate/
for f in tests/fixtures/fast_gate/*; do
  echo "=== $f ==="
  head -3 "$f"
done
```

Verify each file is a real test input (e.g., `bad_sample.py` contains a deliberate lint error), not a generated artifact. If they look generated, skip this task — add discovery note.

- [ ] **Step 2: Compose the issue body**

```markdown
## Problem

Seven test fixture files in `tests/fixtures/fast_gate/` are untracked:
`bad_sample.{js,py,rs}`, `good_sample.{js,py,rs}`, and `sample.md`. These
look like deliberate bad/good lint inputs for the fast-gate smoke test
(`tests/smoke/fast_gate_smoke.sh`). They were probably added as part of
the SP3 fix for the rust-clippy skill (#15, commit 02ccd83) but never
committed. Untracked fixtures cannot be referenced reliably by CI.

## Origin / cross-references

- Working-tree hygiene: `git status` shows 7 untracked fixture files
- Original context: issue #15 (SP3: rust-clippy skill file missing) closed
  in PR #40 (commit 02ccd83) — fixtures likely added then

## Recommended fix sketch

- Verify each file is a deterministic test input (not generated)
- Commit with conventional message:
  `chore(tests): add fast_gate fixture files (bad/good samples per language)`
- Update `tests/smoke/fast_gate_smoke.sh` if it expects specific fixture
  filenames (verify symlink / path references)

## Definition of done

- [ ] All 7 fixture files committed
- [ ] `git status` clean for `tests/fixtures/fast_gate/`
- [ ] `tests/smoke/fast_gate_smoke.sh` still passes
- [ ] `pytest -q` exits 0
- [ ] No new untracked artifacts in working tree
```

- [ ] **Step 3: File the issue**

Run:
```bash
gh issue create \
  --repo Heretek-AI/heretek-claude-harness \
  --title "chore: commit untracked tests/fixtures/fast_gate/ files (post-#15 SP3 fix artifacts)" \
  --label "chore,tech-debt" \
  --body "$(cat <<'BODY_EOF'
<insert Step 2 body here, verbatim>
BODY_EOF
)"
```

Record the new issue number as `ISSUE_3`.

- [ ] **Step 4: Verify the issue landed**

Run:
```bash
gh issue view "$ISSUE_3" --repo Heretek-AI/heretek-claude-harness \
  --json title,labels,body \
  | jq -r '.title, (.labels | map(.name) | join(",")), (.body | length)'
```

Expected: title matches, labels are `chore,tech-debt`, body length > 500 chars.

---

### Task 4: File issue #4 — `docs: fix 'Target plugin' label on 3 heretek-* ADRs`

**Issue produces:** GitHub issue with title `docs: fix 'Target plugin' label on 3 heretek-* ADRs (skills ship at top-level, not skills-pack)`, labels `documentation` + `tech-debt`, P2 body signal.

**Files:** None locally modified. Produces one GitHub issue.

- [ ] **Step 1: Pre-filing discovery — read the 3 ADRs to capture current wording**

Run:
```bash
cd /home/john/Projects/heretek-claude-harness
grep -n "Target plugin" catalog/reviews/heretek-catalog.md catalog/reviews/heretek-refresh-pins.md catalog/reviews/heretek-merge-and-push.md
```

Verify all 3 files mention `Target plugin: skills-pack`. If any already say something else, note it in the body and continue.

- [ ] **Step 2: Compose the issue body**

```markdown
## Problem

The 3 first-party ADRs at `catalog/reviews/heretek-{catalog,refresh-pins,merge-and-push}.md`
each list `Target plugin: skills-pack`, but the implementation actually ships
the skills at `.claude/skills/<name>/SKILL.md` and `.agents/skills/<name>/SKILL.md`
(top-level), NOT inside `plugins/skills-pack/skills/`. This matches the design
spec (`docs/superpowers/specs/2026-08-05-heretek-maintenance-skills-design.md` §3),
which states the skills live top-level so both Claude Code and opencode can
invoke them. The ADR `Target plugin` field is a labeling wart, not a correctness
issue, but should be cleaned up for grep-ability.

## Origin / cross-references

- `docs/superpowers/reviews/2026-08-05-heretek-maintenance-skills-review.md` §ADR cross-references
  (called out as a non-blocking observation)
- Design spec justification:
  `docs/superpowers/specs/2026-08-05-heretek-maintenance-skills-design.md` §3

## Recommended fix sketch

- Edit each ADR to replace `Target plugin: skills-pack` with a line like:
  `Runtime: .claude/skills/ + .agents/skills/ (Claude Code / opencode top-level)`
- Commit with conventional message:
  `docs(catalog): fix Target plugin label on 3 heretek-* ADRs (skills ship at top-level)`

## Definition of done

- [ ] All 3 ADRs updated
- [ ] `grep -l "Target plugin: skills-pack" catalog/reviews/heretek-*.md` returns no matches
- [ ] `grep -l "Runtime: .claude/skills/ + .agents/skills/" catalog/reviews/heretek-*.md` returns 3 matches
- [ ] `python scripts/validate.py` exits 0
- [ ] No new untracked artifacts
```

- [ ] **Step 3: File the issue**

Run:
```bash
gh issue create \
  --repo Heretek-AI/heretek-claude-harness \
  --title "docs: fix 'Target plugin' label on 3 heretek-* ADRs (skills ship at top-level, not skills-pack)" \
  --label "documentation,tech-debt" \
  --body "$(cat <<'BODY_EOF'
<insert Step 2 body here, verbatim>
BODY_EOF
)"
```

Record the new issue number as `ISSUE_4`.

- [ ] **Step 4: Verify the issue landed**

Run:
```bash
gh issue view "$ISSUE_4" --repo Heretek-AI/heretek-claude-harness \
  --json title,labels \
  | jq -r '.title, (.labels | map(.name) | join(","))'
```

Expected: title matches, labels are `documentation,tech-debt`.

---

### Task 5: File issue #5 — `chore: clean up empty reports/baseline/ directory`

**Issue produces:** GitHub issue with title `chore: clean up empty reports/baseline/ directory`, labels `chore` + `tech-debt`, P2 body signal.

**Files:** None locally modified. Produces one GitHub issue.

- [ ] **Step 1: Pre-filing discovery — confirm `reports/baseline/` is empty**

Run:
```bash
cd /home/john/Projects/heretek-claude-harness
ls -la reports/baseline/ 2>&1
find reports/baseline/ -type f 2>&1 | wc -l   # expect: 0
```

If the directory contains files, skip this task — add discovery note (the directory may be in active use by security-scan backfill).

- [ ] **Step 2: Compose the issue body**

```markdown
## Problem

`reports/baseline/` exists locally as an empty directory. It is implicitly
gitignored via the parent `reports/` rule (`# Security scan reports — local
artifacts, regenerated by the backfill`), so the directory itself is not
tracked, but it's also not `.gitkeep`-marked. Empty untracked directories
clutter `git status` output (some Git versions show them; some don't) and
should either be deleted locally or marked as intentional with a `.gitkeep`.

## Origin / cross-references

- Working-tree hygiene: empty `reports/baseline/` exists locally
- `.gitignore` rule for `reports/`: see project `.gitignore` (Security scan
  reports section)

## Recommended fix sketch

- If intentional (security-scan backfill baseline): add `.gitkeep` file
- If not intentional: remove the directory locally with `rmdir reports/baseline/`
- Document decision in this issue before closing

## Definition of done

- [ ] `reports/baseline/` either removed OR contains `.gitkeep`
- [ ] Decision documented in this issue's comment thread
- [ ] `git status` does not show `reports/baseline/` as ambiguous
```

- [ ] **Step 3: File the issue**

Run:
```bash
gh issue create \
  --repo Heretek-AI/heretek-claude-harness \
  --title "chore: clean up empty reports/baseline/ directory" \
  --label "chore,tech-debt" \
  --body "$(cat <<'BODY_EOF'
<insert Step 2 body here, verbatim>
BODY_EOF
)"
```

Record the new issue number as `ISSUE_5`.

- [ ] **Step 4: Verify the issue landed**

Run:
```bash
gh issue view "$ISSUE_5" --repo Heretek-AI/heretek-claude-harness \
  --json title,labels \
  | jq -r '.title, (.labels | map(.name) | join(","))'
```

Expected: title matches, labels are `chore,tech-debt`.

---

### Task 6: File issue #6 — `enhancement: add catalog/tests/smoke_test.sh (referenced by catalog SKILL.md, never created)`

**Issue produces:** GitHub issue with title `enhancement: add catalog/tests/smoke_test.sh (referenced by catalog SKILL.md, never created)`, labels `enhancement` + `help wanted`, P2 body signal.

**Files:** None locally modified. Produces one GitHub issue.

- [ ] **Step 1: Pre-filing discovery — confirm `catalog/tests/smoke_test.sh` does not exist**

Run:
```bash
cd /home/john/Projects/heretek-claude-harness
test -f catalog/tests/smoke_test.sh && echo "EXISTS" || echo "MISSING"
ls catalog/tests/ 2>&1 | head   # expect: directory missing or empty
```

If the file already exists, skip this task — add discovery note.

- [ ] **Step 2: Compose the issue body**

```markdown
## Problem

`docs/superpowers/specs/2026-08-05-heretek-maintenance-skills-design.md` §4.4
specifies a smoke test at `.claude/skills/catalog/tests/smoke_test.sh` (and
the catalog SKILL.md text references it), but the file was never created
in the repo. The maintenance-skills review packet noted this as an
"out-of-scope follow-up." Without the smoke test, the catalog skill's
mock-mode verification is theoretical, not testable.

## Origin / cross-references

- Spec definition: `docs/superpowers/specs/2026-08-05-heretek-maintenance-skills-design.md` §4.4
- Review note: `docs/superpowers/reviews/2026-08-05-heretek-maintenance-skills-review.md` §Smoke status
  ("Both should be reviewed for CI inclusion in a follow-up (out of scope for this review)")

## Recommended fix sketch

- Create `catalog/tests/smoke_test.sh` per spec §4.4 spec:
  - Temp-dir catalog copy
  - Mock-mode add-item flow (no real `gh` calls; synthetic ADR with fake
    stars/license)
  - `python scripts/validate.py` against temp catalog
  - Assert no test regressions
  - Cleanup temp dir
- Mirror to `.agents/skills/catalog/tests/smoke_test.sh` (opencode parity)
  — OR document why the mirror is unnecessary
- Add to standard CI gate OR document why not (relates to #9)

## Definition of done

- [ ] `catalog/tests/smoke_test.sh` exists and runs cleanly
- [ ] Smoke test passes against current `catalog/catalog.yaml`
- [ ] Decision documented on mirror (.agents/) and CI inclusion (#9)
- [ ] `pytest -q` exits 0
- [ ] `python scripts/validate.py` exits 0
```

- [ ] **Step 3: File the issue**

Run:
```bash
gh issue create \
  --repo Heretek-AI/heretek-claude-harness \
  --title "enhancement: add catalog/tests/smoke_test.sh (referenced by catalog SKILL.md, never created)" \
  --label "enhancement,help wanted" \
  --body "$(cat <<'BODY_EOF'
<insert Step 2 body here, verbatim>
BODY_EOF
)"
```

Record the new issue number as `ISSUE_6`.

- [ ] **Step 4: Verify the issue landed**

Run:
```bash
gh issue view "$ISSUE_6" --repo Heretek-AI/heretek-claude-harness \
  --json title,labels \
  | jq -r '.title, (.labels | map(.name) | join(","))'
```

Expected: title matches, labels are `enhancement,help wanted`.

---

### Task 7: File issue #7 — `question: keep or delete catalog/raw/ref.text?`

**Issue produces:** GitHub issue with title `question: keep or delete catalog/raw/ref.text? (BillyOutlast's #8 comment said keep; needs formal ADR)`, labels `question` + `documentation`, P3 body signal.

**Files:** None locally modified. Produces one GitHub issue.

- [ ] **Step 1: Pre-filing discovery — confirm `catalog/raw/ref.text` exists**

Run:
```bash
cd /home/john/Projects/heretek-claude-harness
test -f catalog/raw/ref.text && echo "EXISTS" || echo "MISSING"
ls -la catalog/raw/ 2>&1 | head
wc -l catalog/raw/ref.text 2>&1 | head
```

If the file does not exist, skip this task — add discovery note.

- [ ] **Step 2: Compose the issue body**

```markdown
## Problem

`catalog/raw/ref.text` was the original research source-of-truth that fed the
deep-research workflow. `docs/superpowers/plans/2026-08-03-sp1-foundation.md`
calls for deletion of `ref.text` (PLAN.md §11), but `docs/superpowers/plans/2026-08-03-sp2-hooks-flagship.md`
§1461 notes it as "SP1-deferred, parked in SP1 ledger."

BillyOutlast's comment on issue #8 (2026-08-05) recommended **keeping it for
reproducibility** ("future `refresh-pins` should consult it as the canonical
provenance"), but this decision was never formalized as an ADR or a `.gitignore`
exception.

This is a long-term repo-narrative question: the file is research provenance,
not marketplace code. Keeping it adds repo size and noise; deleting it loses
audit trail.

## Origin / cross-references

- Spec calls for deletion: `docs/superpowers/plans/2026-08-03-sp1-foundation.md` §11 / PLAN.md §11
- SP1-deferred parking: `docs/superpowers/plans/2026-08-03-sp2-hooks-flagship.md` §1461
- Keep-recommendation rationale: comment on #8 (2026-08-05, BillyOutlast)

## Recommended fix sketch

- **Option A — Keep** (recommended by BillyOutlast): add ADR at
  `docs/superpowers/specs/YYYY-MM-DD-ref-text-keep-decision.md` documenting
  the rationale; commit ADR; leave `ref.text` in place
- **Option B — Delete**: remove `catalog/raw/ref.text`; commit deletion with
  rationale in commit message; rely on `catalog/reviews/*.md` ADRs as
  sufficient audit trail

## Definition of done

- [ ] Decision made (Option A or B) and documented in an ADR
- [ ] File state matches decision (kept or deleted)
- [ ] If kept: ADR committed and linked from this issue
- [ ] If deleted: commit history shows the deletion with rationale
```

- [ ] **Step 3: File the issue**

Run:
```bash
gh issue create \
  --repo Heretek-AI/heretek-claude-harness \
  --title "question: keep or delete catalog/raw/ref.text? (BillyOutlast's #8 comment said keep; needs formal ADR)" \
  --label "question,documentation" \
  --body "$(cat <<'BODY_EOF'
<insert Step 2 body here, verbatim>
BODY_EOF
)"
```

Record the new issue number as `ISSUE_7`.

- [ ] **Step 4: Verify the issue landed**

Run:
```bash
gh issue view "$ISSUE_7" --repo Heretek-AI/heretek-claude-harness \
  --json title,labels \
  | jq -r '.title, (.labels | map(.name) | join(","))'
```

Expected: title matches, labels are `question,documentation`.

---

### Task 8: File issue #8 — `enhancement: verify .github/dependabot.yml exists for security-scan.yml weekly digest cadence`

**Issue produces:** GitHub issue with title `enhancement: verify .github/dependabot.yml exists for security-scan.yml weekly digest cadence`, labels `enhancement` + `help wanted`, P3 body signal.

**Files:** None locally modified. Produces one GitHub issue.

- [ ] **Step 1: Pre-filing discovery — check if `.github/dependabot.yml` already exists**

Run:
```bash
cd /home/john/Projects/heretek-claude-harness
test -f .github/dependabot.yml && echo "EXISTS" || echo "MISSING"
test -f .github/dependabot.yaml && echo "yaml EXISTS" || echo "yaml MISSING"
ls .github/ 2>&1 | head -20
```

If `.github/dependabot.yml` (or `.yaml`) exists, edit the body to say "verify presence" instead of "create", and note the file in the body.

- [ ] **Step 2: Compose the issue body**

```markdown
## Problem

`docs/superpowers/specs/2026-08-05-security-monitoring-pipeline-design.md` §5.7
(Action-pinning migration, P0 phase exit criteria) calls for adding
`.github/dependabot.yml` with `package-ecosystem: github-actions` to keep
third-party Action references current. The workflow
`.github/workflows/security-scan-digest.yml` (Monday weekly digest) was
added in commit `84e8b79`, but the presence/absence of `.github/dependabot.yml`
needs verification.

Without Dependabot config, third-party Action SHA pins (`D20`) will rot as
upstream Actions release new versions. Manual SHA bumps defeat the purpose
of SHA-ride.

## Origin / cross-references

- Spec requirement: `docs/superpowers/specs/2026-08-05-security-monitoring-pipeline-design.md` §5.7
- D20 invariant (every `uses:` pinned to 40-char SHA): same spec §6.1
- Related: `.github/workflows/security-scan-digest.yml` (Monday weekly digest, commit `84e8b79`)

## Recommended fix sketch

- Verify `.github/dependabot.yml` exists; if not, create with:
  ```yaml
  version: 2
  updates:
    - package-ecosystem: "github-actions"
      directory: "/"
      schedule:
        interval: "weekly"
      groups:
        github-actions:
          patterns: ["*"]
  ```
- Verify Dependabot PR appears in repo within 7 days of config commit
- Document the check in `docs/ops/dependabot-runbook.md` (new file) OR in this
  issue's comment thread

## Definition of done

- [ ] `.github/dependabot.yml` exists with `package-ecosystem: github-actions`
- [ ] Dependabot configures weekly interval
- [ ] First Dependabot PR visible within 7 days (or documented why not)
- [ ] `python scripts/validate.py` exits 0
- [ ] `pytest tests/test_action_pinning.py -q` exits 0
```

- [ ] **Step 3: File the issue**

Run:
```bash
gh issue create \
  --repo Heretek-AI/heretek-claude-harness \
  --title "enhancement: verify .github/dependabot.yml exists for security-scan.yml weekly digest cadence" \
  --label "enhancement,help wanted" \
  --body "$(cat <<'BODY_EOF'
<insert Step 2 body here, verbatim>
BODY_EOF
)"
```

Record the new issue number as `ISSUE_8`.

- [ ] **Step 4: Verify the issue landed**

Run:
```bash
gh issue view "$ISSUE_8" --repo Heretek-AI/heretek-claude-harness \
  --json title,labels \
  | jq -r '.title, (.labels | map(.name) | join(","))'
```

Expected: title matches, labels are `enhancement,help wanted`.

---

### Task 9: File issue #9 — `enhancement: include tests/smoke/fast_gate_smoke.sh + catalog/tests/smoke_test.sh in standard CI gate`

**Issue produces:** GitHub issue with title `enhancement: include tests/smoke/fast_gate_smoke.sh + catalog/tests/smoke_test.sh in standard CI gate`, labels `enhancement` + `help wanted`, P3 body signal.

**Files:** None locally modified. Produces one GitHub issue.

- [ ] **Step 1: Pre-filing discovery — confirm both smoke-test scripts exist (or note absences)**

Run:
```bash
cd /home/john/Projects/heretek-claude-harness
test -f tests/smoke/fast_gate_smoke.sh && echo "fast_gate EXISTS" || echo "fast_gate MISSING"
test -f catalog/tests/smoke_test.sh && echo "catalog EXISTS" || echo "catalog MISSING"
ls tests/smoke/ 2>&1 | head
```

If `catalog/tests/smoke_test.sh` does not exist, note this issue is blocked by #6.

- [ ] **Step 2: Compose the issue body**

```markdown
## Problem

`tests/smoke/fast_gate_smoke.sh` is run manually during local development and
in the maintenance-skills review packet, but is NOT in the standard CI gate
(`validate.yml` or `smoke-test.yml`). `catalog/tests/smoke_test.sh` is
specified in the catalog skill spec but doesn't exist yet (tracked in #6).

The maintenance-skills review packet explicitly called this out:
> "Both should be reviewed for CI inclusion in a follow-up (out of scope for
> this review)."

Without smoke tests in CI, regressions in the fast-gate dispatcher or the
catalog skill flow can land undetected.

## Origin / cross-references

- Review callout: `docs/superpowers/reviews/2026-08-05-heretek-maintenance-skills-review.md` §Smoke status
- Catalog smoke spec: `docs/superpowers/specs/2026-08-05-heretek-maintenance-skills-design.md` §4.4
- Blocker: #6 (catalog/tests/smoke_test.sh must exist before CI inclusion makes sense)

## Recommended fix sketch

- Add `bash tests/smoke/fast_gate_smoke.sh` step to `.github/workflows/validate.yml`
  (PR-time gate)
- After #6 lands: add `bash catalog/tests/smoke_test.sh` step to `validate.yml`
  AND/OR `.github/workflows/smoke-test.yml` (merge + nightly gate)
- Update `docs/superpowers/specs/2026-08-05-heretek-maintenance-skills-design.md`
  §Acceptance criteria to reflect CI inclusion

## Definition of done

- [ ] `bash tests/smoke/fast_gate_smoke.sh` runs in `validate.yml`
- [ ] After #6 lands: `bash catalog/tests/smoke_test.sh` runs in `validate.yml`
- [ ] CI green on a PR that triggers both smoke tests
- [ ] Spec acceptance criteria updated to reflect CI inclusion
- [ ] `python scripts/validate.py` exits 0
- [ ] `pytest -q` exits 0
```

- [ ] **Step 3: File the issue**

Run:
```bash
gh issue create \
  --repo Heretek-AI/heretek-claude-harness \
  --title "enhancement: include tests/smoke/fast_gate_smoke.sh + catalog/tests/smoke_test.sh in standard CI gate" \
  --label "enhancement,help wanted" \
  --body "$(cat <<'BODY_EOF'
<insert Step 2 body here, verbatim>
BODY_EOF
)"
```

Record the new issue number as `ISSUE_9`.

- [ ] **Step 4: Verify the issue landed**

Run:
```bash
gh issue view "$ISSUE_9" --repo Heretek-AI/heretek-claude-harness \
  --json title,labels \
  | jq -r '.title, (.labels | map(.name) | join(","))'
```

Expected: title matches, labels are `enhancement,help wanted`.

---

### Task 10: File issue #10 — `chore: file per-item ADRs for 6 D7-passing Tier-2 candidates`

**Issue produces:** GitHub issue with title `chore: file per-item ADRs for 6 D7-passing Tier-2 candidates (agent-skills, wondelai, headroom, taste-skill, claude-mem, CLI-Anything)`, labels `chore` + `enhancement` + `help wanted`, P3 body signal.

**Files:** None locally modified. Produces one GitHub issue.

- [ ] **Step 1: Pre-filing discovery — confirm none of the 6 candidates already have ADRs**

Run:
```bash
cd /home/john/Projects/heretek-claude-harness
for c in agent-skills wondelai headroom taste-skill claude-mem CLI-Anything; do
  echo "=== $c ==="
  ls catalog/reviews/ | grep -i "$c" 2>&1 || echo "no ADR yet"
done
```

If any ADR already exists, note it in the body and exclude from the checklist.

- [ ] **Step 2: Compose the issue body**

```markdown
## Problem

The Tier-2 candidates shortlist (Action E on issue #8) identified 6 candidates
that pass the D7 vetting bar (stars ≥ 500, last commit ≤ 12mo, OSI-approved
license, source-audit for code-executing components):

| Candidate | Repo | Stars (verified 2026-08-06) | License |
|---|---|---|---|
| agent-skills | `addyosmani/agent-skills` | 82,048 | MIT |
| wondelai | `wondelai/skills` | 1,850 | MIT |
| headroom | `headroomlabs-ai/headroom` | 65,071 | Apache-2.0 |
| taste-skill | `Leonxlnx/taste-skill` | 72,603 | MIT |
| claude-mem | `thedotmack/claude-mem` | 89,755 | Apache-2.0 |
| CLI-Anything | `HKUDS/CLI-Anything` | 46,691 | Apache-2.0 |

None of these have per-item ADRs yet. Per the catalog pattern
(D7 vetting bar), each approved item must have an ADR at
`catalog/reviews/<plugin>-<item>.md` before being added to `catalog.yaml`.

## Origin / cross-references

- Comment on #8 (2026-08-05, BillyOutlast) — Tier-2 shortlist
- Comment on #8 (2026-08-06, this session) — D7 passes confirmed
- D7 vetting bar:
  `docs/superpowers/specs/2026-08-03-heretek-marketplace-design.md` §6
- Skill to use: `/heretek:catalog add-item` (shipped in PR #22)

## Recommended fix sketch

- For each of the 6 candidates, run `/heretek:catalog add-item` with target
  plugin `skills-pack` (or `mcp-pack` for claude-mem)
- The skill enforces D7/D11/D15/D17 invariants automatically
- Each ADR must capture: real research data, scope match to skills-pack,
  stars/license/last_commit verified at filing time
- Source-audit required for code-executing items (skills with executable code,
  claude-mem as memory MCP)

## Definition of done

For each of the 6 candidates, a checked ADR at `catalog/reviews/<plugin>-<item>.md`:
- [ ] `catalog/reviews/skills-pack-agent-skills.md` (or appropriate plugin)
- [ ] `catalog/reviews/skills-pack-wondelai.md`
- [ ] `catalog/reviews/skills-pack-headroom.md` (resolve canonical owner first:
      `headroomlabs-ai/headroom` vs `chopratejas/headroom`)
- [ ] `catalog/reviews/skills-pack-taste-skill.md`
- [ ] `catalog/reviews/mcp-pack-claude-mem.md` (mcp-pack, not skills-pack)
- [ ] `catalog/reviews/skills-pack-cli-anything.md`

And:
- [ ] All 6 ADRs reviewed against D7 bar
- [ ] `python scripts/validate.py` exits 0
- [ ] `pytest -q` exits 0
- [ ] Star/license re-verified at ADR filing time (per spec note)
```

- [ ] **Step 3: File the issue**

Run:
```bash
gh issue create \
  --repo Heretek-AI/heretek-claude-harness \
  --title "chore: file per-item ADRs for 6 D7-passing Tier-2 candidates (agent-skills, wondelai, headroom, taste-skill, claude-mem, CLI-Anything)" \
  --label "chore,enhancement,help wanted" \
  --body "$(cat <<'BODY_EOF'
<insert Step 2 body here, verbatim>
BODY_EOF
)"
```

Record the new issue number as `ISSUE_10`.

- [ ] **Step 4: Verify the issue landed**

Run:
```bash
gh issue view "$ISSUE_10" --repo Heretek-AI/heretek-claude-harness \
  --json title,labels \
  | jq -r '.title, (.labels | map(.name) | join(","))'
```

Expected: title matches, labels are `chore,enhancement,help wanted`.

---

### Task 11: File issue #11 — `chore: append mksglu/context-mode to catalog/rejected.md`

**Issue produces:** GitHub issue with title `chore: append mksglu/context-mode to catalog/rejected.md (D7 fail: Elastic License 2.0 not OSI-approved)`, labels `chore` + `documentation`, P3 body signal.

**Files:** None locally modified. Produces one GitHub issue.

- [ ] **Step 1: Pre-filing discovery — confirm `catalog/rejected.md` does not already list `mksglu/context-mode`**

Run:
```bash
cd /home/john/Projects/heretek-claude-harness
grep -n "mksglu\|context-mode" catalog/rejected.md 2>&1 || echo "not yet listed"
```

If already listed, skip this task — add discovery note.

- [ ] **Step 2: Compose the issue body**

```markdown
## Problem

`mksglu/context-mode` (verified 2026-08-06: 19,650 stars) is licensed under
**Elastic License 2.0 (ELv2)**. ELv2 is **not OSI-approved** — it includes
restrictions on providing the software as a hosted/managed service. This
violates D7's OSI-license requirement.

The candidate is otherwise attractive (high stars, active repo, multi-platform
hooks/MCP support). Per D7, it cannot ship in the marketplace but should be
documented in `catalog/rejected.md` with the failing condition called out,
so future maintainers don't re-research from scratch.

## Origin / cross-references

- License identification: comment on #8 (2026-08-06, this session) — context-mode
  LICENSE file is ELv2 (verified by reading `LICENSE` in the repo at SHA
  `de53368caf1c88159bcc4f665fe87dfa1ec2b000`)
- D7 vetting bar:
  `docs/superpowers/specs/2026-08-03-heretek-marketplace-design.md` §6
  (OSI-approved license is one of the 5 required conditions)
- Prior research: comment on #8 (2026-08-05, BillyOutlast) — flagged context-mode
  as NOASSERTION needing further investigation; this session resolved to ELv2

## Recommended fix sketch

- Append an entry to `catalog/rejected.md`:
  ```markdown
  ## mksglu/context-mode (2026-08-06)

  - **Repo:** mksglu/context-mode
  - **Stars:** 19,650 (verified 2026-08-06)
  - **License:** Elastic License 2.0 (ELv2) — NOT OSI-approved
  - **D7 verdict:** Fail (license). ELv2 includes restrictions on hosted/managed
    service provision, which violates the OSI-approved license requirement.
  - **Re-evaluation trigger:** If upstream re-licenses to MIT / Apache-2.0 /
    BSD / similar OSI-approved license, re-run D7 vetting.
  ```
- Commit with conventional message:
  `chore(catalog): reject mksglu/context-mode (D7 fail: ELv2 not OSI-approved)`
- Reference this issue in the commit message body

## Definition of done

- [ ] `catalog/rejected.md` contains the new entry
- [ ] Commit message references this issue
- [ ] `python scripts/validate.py` exits 0
- [ ] `pytest -q` exits 0
- [ ] No re-vetting scheduled (D7 verdict is structural)
```

- [ ] **Step 3: File the issue**

Run:
```bash
gh issue create \
  --repo Heretek-AI/heretek-claude-harness \
  --title "chore: append mksglu/context-mode to catalog/rejected.md (D7 fail: Elastic License 2.0 not OSI-approved)" \
  --label "chore,documentation" \
  --body "$(cat <<'BODY_EOF'
<insert Step 2 body here, verbatim>
BODY_EOF
)"
```

Record the new issue number as `ISSUE_11`.

- [ ] **Step 4: Verify the issue landed**

Run:
```bash
gh issue view "$ISSUE_11" --repo Heretek-AI/heretek-claude-harness \
  --json title,labels \
  | jq -r '.title, (.labels | map(.name) | join(","))'
```

Expected: title matches, labels are `chore,documentation`.

---

### Task 12: Cross-cutting verification per spec §7

**Files:** None locally modified. Verifies the 11 issues filed in Tasks 1–11.

**Inputs (from prior tasks):** `ISSUE_1` through `ISSUE_11` issue numbers. Some may be `null` if the task was skipped due to discovery (pre-filing discovery showed the item already done). Track which.

- [ ] **Step 1: Verify open-issue count delta**

Run:
```bash
gh issue list --repo Heretek-AI/heretek-claude-harness --state open --limit 50 --json number \
  | jq 'length'
```

Expected: open issue count has increased by the number of successfully filed issues (11 minus any skipped per discovery notes).

- [ ] **Step 2: Spot-check 3 issues — confirm body structure**

Run (substitute actual issue numbers):
```bash
for n in "$ISSUE_1" "$ISSUE_5" "$ISSUE_10"; do
  echo "=== Issue #$n ==="
  gh issue view "$n" --repo Heretek-AI/heretek-claude-harness --json title,labels,body \
    | jq -r '"Title: \(.title)\nLabels: \(.labels | map(.name) | join(\",\"))\nHas Problem: \(.body | contains(\"## Problem\"))\nHas Origin: \(.body | contains(\"## Origin\"))\nHas Recommended: \(.body | contains(\"## Recommended\"))\nHas Definition: \(.body | contains(\"## Definition\"))"'
done
```

Expected: every check returns `Title: ...`, `Labels: ...` matching spec, and `Has ...: true` for all 4 sections.

- [ ] **Step 3: Confirm no new labels were created**

Run:
```bash
gh label list --repo Heretek-AI/heretek-claude-harness --json name \
  | jq -r '.[].name' | sort
```

Expected: label set is exactly `{bug, chore, documentation, enhancement, help wanted, question, tech-debt, ...existing labels...}`. No new labels like `P1`, `P2`, `housekeeping`, `P0/P1/P2` priority labels, etc.

- [ ] **Step 4: Confirm no `gh` write operations outside `gh issue create`**

Audit the session transcript for any `gh` commands that wrote: `gh issue edit`, `gh issue close`, `gh issue comment`, `gh label create`, `gh label edit`, `gh project edit`, etc. None should have been used.

If any were used unintentionally, undo them before claiming the plan complete.

- [ ] **Step 5: Confirm the spec file is committed**

Run:
```bash
git log --oneline -1 docs/superpowers/specs/2026-08-06-housekeeping-triage-design.md
```

Expected: shows commit `8d07779 docs(spec): housekeeping triage design — file 11 flat GitHub issues for v1.0.1 housekeeping` (or later).

- [ ] **Step 6: Print final summary**

Output:
```
Filed 11 housekeeping triage issues on Heretek-AI/heretek-claude-harness:
- #N+1: chore: add .coverage to .gitignore + configure coverage.xml for CI [chore, tech-debt]
- #N+2: fix: mirror find-skills skill to .agents/skills/ (or document why not) [bug, help wanted]
- #N+3: chore: commit untracked tests/fixtures/fast_gate/ files (post-#15 SP3 fix artifacts) [chore, tech-debt]
- #N+4: docs: fix 'Target plugin' label on 3 heretek-* ADRs (skills ship at top-level, not skills-pack) [documentation, tech-debt]
- #N+5: chore: clean up empty reports/baseline/ directory [chore, tech-debt]
- #N+6: enhancement: add catalog/tests/smoke_test.sh (referenced by catalog SKILL.md, never created) [enhancement, help wanted]
- #N+7: question: keep or delete catalog/raw/ref.text? (BillyOutlast's #8 comment said keep; needs formal ADR) [question, documentation]
- #N+8: enhancement: verify .github/dependabot.yml exists for security-scan.yml weekly digest cadence [enhancement, help wanted]
- #N+9: enhancement: include tests/smoke/fast_gate_smoke.sh + catalog/tests/smoke_test.sh in standard CI gate [enhancement, help wanted]
- #N+10: chore: file per-item ADRs for 6 D7-passing Tier-2 candidates (agent-skills, wondelai, headroom, taste-skill, claude-mem, CLI-Anything) [chore, enhancement, help wanted]
- #N+11: chore: append mksglu/context-mode to catalog/rejected.md (D7 fail: Elastic License 2.0 not OSI-approved) [chore, documentation]

Spec: docs/superpowers/specs/2026-08-06-housekeeping-triage-design.md
Plan: docs/superpowers/plans/2026-08-06-housekeeping-triage.md
Spec commit: 8d07779
```

If any task was skipped due to discovery, list the skipped items in the summary with the discovery note.