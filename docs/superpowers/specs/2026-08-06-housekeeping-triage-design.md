---
date: 2026-08-06
topic: housekeeping-triage
status: accepted
parent: docs/superpowers/specs/2026-08-03-heretek-marketplace-design.md
---

# Housekeeping Triage — Design Spec

> Date: 2026-08-06. Captures the v1.0.1 housekeeping pass: file 11 flat issues (one per item) covering working-tree hygiene, `.gitignore` gaps, code TODOs, deferred items, ADR wart, smoke-test CI inclusion, Tier-2 ADR batch, and a D7 reject finalization. Triage only — no implementation in this spec.

## 1. Summary

The v1.0 marketplace shipped on 2026-08-05 with 11 first-party plugins and 67+ tests passing. A working-tree + deferred-items review surfaced **11 actionable housekeeping items** that fall outside the v1 launch scope but should be tracked before v1.0.1 to keep the repo clean, the spec/impl drift-free, and the v2 backlog honest. This spec captures the **plan to file 11 flat GitHub issues** — one per item — without implementing any of them.

The triage is filed in this session. Implementation lives behind the issue → branch → PR loop and is out of scope here.

## 2. Goals and non-goals

### Goals

- File 11 flat GitHub issues on `Heretek-AI/heretek-claude-harness` with consistent structure (title, labels, body, cross-links, DoD).
- Priority-order the issue list so triage signal is explicit (correctness → user-visible polish → internal hygiene).
- Reuse only existing repo labels (`bug`, `enhancement`, `tech-debt`, `help wanted`, `documentation`, `question`, `chore`); no new labels created.
- Cross-link every issue to the spec/plan/review section that originated it, so future maintainers don't re-derive the rationale.
- Capture this spec as the audit trail so the triage pass is reproducible.

### Non-goals

- Fixing any of the 11 items. Implementation is a later session.
- Modifying `catalog/catalog.yaml`, `scripts/`, or any code. Filing issues does not require code changes.
- Creating new labels (P0/P1/P2, `housekeeping`, etc.).
- A parent tracking umbrella issue. User chose flat list — no umbrella.
- v1.0.1 release planning. This is housekeeping, not release management.
- v2 backlog items (#1–#8, #17–#20). Already filed; aspirational, not housekeeping.
- The 4 v2-code-quality spec issues (#17–#20). Already filed in the prior session per `2026-08-05-v2-code-quality-issue-set-design.md`.
- The Action E comment on #8 (Tier-2 shortlist). Already posted 2026-08-05 by BillyOutlast; this session added a 2026-08-06 follow-up.
- Cleanup of the duplicate Action E comment. Out of scope; spec notes that future maintainers can decide.

## 3. The issue set (priority-ordered, 11 items)

| # | Issue title | Labels | Originates from | Priority |
|---|---|---|---|---|
| 1 | `chore: add .coverage to .gitignore + configure coverage.xml for CI` | `chore`, `tech-debt` | `docs/superpowers/specs/2026-08-05-v1-launch-remediation-design.md` §9 (verification) | P1 — user-visible (clean working tree) |
| 2 | `fix: mirror find-skills skill to .agents/skills/ (or document why not)` | `bug`, `help wanted` | working-tree hygiene (untracked `.agents/skills/find-skills/SKILL.md` + `.claude/skills/find-skills`) | P1 — sync parity violation |
| 3 | `chore: commit untracked tests/fixtures/fast_gate/ files (post-#15 SP3 fix artifacts)` | `chore`, `tech-debt` | working-tree hygiene (7 untracked fixture files: bad_sample.{js,py,rs}, good_sample.{js,py,rs}, sample.md) | P1 — test fixtures must be in git |
| 4 | `docs: fix 'Target plugin' label on 3 heretek-* ADRs (skills ship at top-level, not skills-pack)` | `documentation`, `tech-debt` | `docs/superpowers/reviews/2026-08-05-heretek-maintenance-skills-review.md` §ADR cross-references | P2 — labeling wart, non-blocking |
| 5 | `chore: clean up empty reports/baseline/ directory` | `chore`, `tech-debt` | working-tree hygiene (empty `reports/baseline/` exists locally; `reports/` is gitignored) | P2 — empty artifact |
| 6 | `enhancement: add catalog/tests/smoke_test.sh (referenced by catalog SKILL.md, never created)` | `enhancement`, `help wanted` | `docs/superpowers/reviews/2026-08-05-heretek-maintenance-skills-review.md` §Smoke status + `docs/superpowers/specs/2026-08-05-heretek-maintenance-skills-design.md` §4.4 | P2 — spec drift between skill and repo |
| 7 | `question: keep or delete catalog/raw/ref.text? (BillyOutlast's #8 comment said keep; needs formal ADR)` | `question`, `documentation` | `docs/superpowers/plans/2026-08-03-sp2-hooks-flagship.md` §1461 + comment on #8 (2026-08-05, BillyOutlast) | P3 — long-term repo narrative |
| 8 | `enhancement: verify .github/dependabot.yml exists for security-scan.yml weekly digest cadence` | `enhancement`, `help wanted` | `docs/superpowers/specs/2026-08-05-security-monitoring-pipeline-design.md` §5.7 (action-pinning migration) | P3 — spec said add it; verify presence |
| 9 | `enhancement: include tests/smoke/fast_gate_smoke.sh + catalog/tests/smoke_test.sh in standard CI gate` | `enhancement`, `help wanted` | `docs/superpowers/reviews/2026-08-05-heretek-maintenance-skills-review.md` §Smoke status | P3 — CI inclusion follow-up |
| 10 | `chore: file per-item ADRs for 6 D7-passing Tier-2 candidates (agent-skills, wondelai, headroom, taste-skill, claude-mem, CLI-Anything)` | `chore`, `enhancement`, `help wanted` | comment on #8 (2026-08-05, BillyOutlast — Tier-2 shortlist) + comment on #8 (2026-08-06, this session — D7 passes confirmed) | P3 — skills-pack expansion |
| 11 | `chore: append mksglu/context-mode to catalog/rejected.md (D7 fail: Elastic License 2.0 not OSI-approved)` | `chore`, `documentation` | comment on #8 (2026-08-06, this session — context-mode license definitively identified as ELv2) | P3 — D7 reject finalization |

**Excluded by prior agreement:** the `scripts/scanners/lsp.py:15` TODO comment about LSP `sha` field is mentioned in this spec under §6 Out-of-scope — too minor for its own issue.

**Note on the "Priority" column:** P1/P2/P3 here is a **body-signal ranking for triage ordering** (correctness/data-integrity first → user-visible polish → internal hygiene), not a GitHub label. The user explicitly chose "Reuse existing labels only" so P1/P2/P3 do NOT appear as issue labels. The ranking lives in the issue body text and in the §5 sequencing, so a maintainer scanning the open issue list can still see priority without new labels.

## 4. Issue body template

Every issue uses this template, with fields filled per the specific item. Consistent structure lets the maintainer triage by skimming structure, not re-parsing free-form bodies.

```markdown
## Problem

<1-3 sentence concrete description of what's wrong / drifted / missing.
Reference the symptom (working-tree state, CI failure, spec drift) directly.>

## Origin / cross-references

<Bullet list of originating spec/plan/review sections. Always link to the
local file path; link to GitHub issue/PR only if it exists.>

- `docs/superpowers/specs/2026-08-05-v1-launch-remediation-design.md` §9
- `docs/superpowers/reviews/2026-08-05-heretek-maintenance-skills-review.md` §70
- Comment on #8 (2026-08-05, BillyOutlast) — keep ref.text
- Comment on #8 (2026-08-06, this session) — Action E follow-up

## Recommended fix sketch

<2-4 bullet points describing the concrete change. Not a full plan —
just enough that the implementer doesn't re-derive the approach.>

- Edit `.gitignore` to add `.coverage` and `coverage.xml`
- Edit `pyproject.toml` `[tool.coverage]` to set `xml_output = "coverage.xml"`
- Verify: `git status` clean after `coverage report`
- Re-run `pytest --cov` and confirm `coverage.xml` is produced

## Definition of done

<Checkbox list, 3-6 items, each independently verifiable.>

- [ ] File/script change in place
- [ ] `python scripts/validate.py` exits 0
- [ ] `pytest -q` exits 0
- [ ] `git status` shows no new untracked artifacts
- [ ] Cross-link / comment on originating issue if applicable
```

### Conventions

- **Issue titles** use a mix of conventional-commit prefixes (`chore:`, `fix:`, `docs:`) and label-derived prefixes (`enhancement:`, `question:`). Lowercase after the colon. Title fits in ~70 chars. The label-derived prefixes mirror the issue's primary label so the title and labels read coherently: an `enhancement` label is paired with an `enhancement:` prefix, a `question` label with `question:`.
- **Cross-links** always include the local `docs/superpowers/...` path. GitHub issue/PR links included only when the issue/PR already exists. No external URLs in the body unless the upstream is the source of truth (e.g., licenses).
- **DoD** items are concrete and verifiable. No "tests pass" without specifying which tests; no "works" without specifying how to confirm.
- **Labels** reused only. Mapping:
  - `chore` + `tech-debt` → internal hygiene (#1, #3, #5)
  - `bug` + `help wanted` → sync/contract violation (#2)
  - `documentation` + `tech-debt` → doc wart (#4)
  - `enhancement` + `help wanted` → spec drift / CI inclusion (#6, #8, #9)
  - `question` + `documentation` → ADR-needed decision (#7)
  - `chore` + `enhancement` + `help wanted` → ADR-writing batch (#10)
  - `chore` + `documentation` → D7 reject finalization (#11)

## 5. Sequencing (filing order)

The 11 issues are filed in this order to minimize context-switching and surface blockers early.

| Step | Issue | Rationale |
|---|---|---|
| 1 | #1 `.coverage` gitignore + coverage.xml | Mechanical fix; sets up clean working tree before all other steps |
| 2 | #2 find-skills mirror parity | One discoverable question: is `find-skills` intentional? Resolves by either committing mirror or documenting why not |
| 3 | #3 commit untracked test fixtures | Mechanical; depends on #1 (clean tree) |
| 4 | #4 ADR labeling wart | Mechanical doc edit; quick win |
| 5 | #5 clean empty `reports/baseline/` | Trivial cleanup |
| 6 | #6 add `catalog/tests/smoke_test.sh` | Spec drift fix; needs creation, not just discovery |
| 7 | #7 ref.text keep/delete decision | ADR-worthy; needs a maintainer call before the issue closes |
| 8 | #8 Dependabot for security-scan | Verification issue: is `.github/dependabot.yml` already configured? |
| 9 | #9 smoke-test CI inclusion | Spec follow-up; can be combined with #6 |
| 10 | #10 file per-item ADRs (Tier-2) | 6 ADRs as one issue with checklist |
| 11 | #11 reject context-mode in `catalog/rejected.md` | Finalizes Action E from #8 comment |

### Error handling / discovery during filing

If while filing issue N I discover item N+1 is already done (e.g., `.github/dependabot.yml` exists in #8), I do NOT file a redundant issue — instead I add a note to this spec's §6 Out-of-scope section noting "item N+1 was already implemented; not filing a redundant issue" so future maintainers see the trail.

If while filing an issue the recommended fix sketch turns out to be wrong (e.g., the actual problem is different from what I diagnosed from context alone), I update the body before filing — better to file a correct issue than to discover it during the fix.

## 6. Out of scope (deferred)

| Item | Why excluded |
|---|---|
| `scripts/scanners/lsp.py:15` TODO comment about LSP `sha` field | Too minor for its own issue; mention only in this spec |
| Fixing any of the 11 items | User chose "Triage + file issues" — implementation is a later session |
| Modifying `catalog/catalog.yaml`, `scripts/`, or any code | Filing issues does not require code changes |
| Creating new labels (P0/P1/P2, `housekeeping`, etc.) | User chose "Reuse existing labels only" |
| A parent tracking umbrella issue | User chose "Flat list, no parent" |
| v1.0.1 release planning | Out of scope; this is housekeeping, not release management |
| v2 backlog items (#1–#8, #17–#20) | Already filed; aspirational, not housekeeping |
| The 4 v2-code-quality spec issues (#17–#20) | Already filed in prior session per `2026-08-05-v2-code-quality-issue-set-design.md` |
| New issues for #30–#34 (security hardening) | Already filed; in-flight as v1.1 work |
| New issue for #12 (security mailbox) | Already filed; awaiting human action |
| Action E comment duplication cleanup on #8 | Out of scope; future maintainers can decide |
| Per-issue implementation plans | Each issue's body carries its own "Recommended fix sketch"; per-issue plans live behind the issue → branch → PR loop |
| Verification of `.github/dependabot.yml` presence (if it already exists at filing time) | Becomes part of issue #8's body — "verify or create" rather than "create" |

## 7. Verification (post-filing)

After all 11 issues are filed in this session:

1. `gh issue list --repo Heretek-AI/heretek-claude-harness --state open --limit 50` confirms the open-issue count has increased by 11 (count delta vs. pre-filing snapshot)
2. Spot-check 2-3 issues via `gh issue view <num> --repo ...` to confirm body rendered correctly with template sections (Problem, Origin, Recommended fix sketch, DoD)
3. Confirm label set is exactly {chore, tech-debt, bug, help wanted, documentation, enhancement, question} — no new labels created
4. No `gh` write operations outside `gh issue create` (no comments, no edits, no label creation, no project edits)
5. This spec file committed to git on the current branch with conventional-commit message

## 8. References

- `docs/superpowers/specs/2026-08-03-heretek-marketplace-design.md` — parent spec (D1–D17)
- `docs/superpowers/specs/2026-08-05-v1-launch-remediation-design.md` — §9 verification (calls for `.coverage` gitignore)
- `docs/superpowers/specs/2026-08-05-heretek-maintenance-skills-design.md` — §4.4 catalog smoke test
- `docs/superpowers/specs/2026-08-05-security-monitoring-pipeline-design.md` — §5.7 dependabot for actions
- `docs/superpowers/specs/2026-08-05-v2-code-quality-issue-set-design.md` — §3 Action E + Tier-2 shortlist
- `docs/superpowers/reviews/2026-08-05-heretek-maintenance-skills-review.md` — ADR cross-references labeling wart + smoke-test CI inclusion
- `docs/superpowers/plans/2026-08-03-sp2-hooks-flagship.md` — §1461 (ref.text disposition)
- Issue #8 — Action E comment thread (BillyOutlast 2026-08-05 + this session 2026-08-06)
- Issues #1–#8, #12, #17–#20, #30–#34 — pre-existing open issues that inform the triage

---

## Appendix A: Pre-filing discovery checklist

For each item in §3, the body author should verify the following before writing the body:

| # | Pre-filing discovery |
|---|---|
| 1 | Confirm `.coverage` file exists in working tree (already verified this session) |
| 2 | Read `.claude/skills/find-skills/SKILL.md` to determine if `find-skills` is a real skill vs stray artifact |
| 3 | Inspect each untracked fixture file in `tests/fixtures/fast_gate/` to confirm they are test inputs (not generated artifacts) |
| 4 | Read all 3 `catalog/reviews/heretek-{catalog,refresh-pins,merge-and-push}.md` to capture exact current wording |
| 5 | Confirm `reports/baseline/` is empty before recommending removal |
| 6 | Re-read `docs/superpowers/specs/2026-08-05-heretek-maintenance-skills-design.md` §4.4 to confirm the smoke test was specified but never created |
| 7 | Re-read comment on #8 (2026-08-05) to capture the "keep" rationale |
| 8 | `ls .github/dependabot.yml` to confirm presence/absence before filing |
| 9 | Re-read `docs/superpowers/reviews/2026-08-05-heretek-maintenance-skills-review.md` §Smoke status to capture the exact follow-up recommendation |
| 10 | Pull the 6 D7-passing candidates from comment on #8 (this session) — `agent-skills`, `wondelai`, `headroom`, `taste-skill`, `claude-mem`, `CLI-Anything` |
| 11 | Verify `catalog/rejected.md` does not already list `mksglu/context-mode` |