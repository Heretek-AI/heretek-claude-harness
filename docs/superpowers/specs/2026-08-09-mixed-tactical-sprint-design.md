# Mixed-Tactical Sprint — Design

**Date:** 2026-08-09
**Status:** Proposed (awaiting user review)
**Sprint window:** open-ended, drive until done

## 1. Goal

Ship 7 mixed-tactical items end-to-end: #150 (ShellCheck CI) + #169-#174 (tech-debt batch from v3.5 collector final review). All issues closed via merged PRs.

## 2. Scope

**In:**
- 7 issues (#150, #169, #170, #171, #172, #173, #174), one PR each, FF-merge to `main`
- No spec files needed (issues are self-describing; tech-debt items reference original PRs for context)

**Out (deferred):**
- v3.5 sub-spec 2 (test pipeline, #114-#118)
- v3.5 sub-spec 3 (eval harness, #119-#124)
- Security batch (#157-#168, 12 issues parked)
- v2 backlog, v4-v6 tracking initiatives

## 3. Sequence

| Step | Issue | Type | Depends on |
|---|---|---|---|
| 1 | #150 | ShellCheck CI | — |
| 2 | #169 | config.properties format | — |
| 3 | #170 | retention test hardening | — |
| 4 | #171 | CLI substring + diff error | — |
| 5 | #172 | JSONDecodeError count | — |
| 6 | #173 | polish bundle (4 sub-items) | — |
| 7 | #174 | ADR lifecycle | — |

All 7 are file-independent (touch different files / different domains). Sequential dispatch per subagent-driven protocol.

## 4. Execution mechanics

**Per-issue workflow:**
1. Spawn `executor` subagent with the issue body + relevant files
2. Subagent does TDD where applicable, opens one PR with `Closes #<n>`
3. Main runs `merge-and-push` after CI green (merge authorization requested once at sprint start per skill protocol)
4. Verify issue closed; advance

**Per-issue model selection:**
- **#150** — sonnet (CI + pre-commit + possible shell script fixes, multi-file)
- **#169** — haiku (decision + small change)
- **#170** — sonnet (true integration test, multi-file)
- **#171** — haiku (UX + small tests)
- **#172** — haiku (counter + warning)
- **#173** — sonnet (4 sub-items across files, bundled)
- **#174** — haiku (decision + template update)

**Pre-flight checklist per dispatch:**
- `git log --oneline main -3` confirms clean state
- Read latest issue body via `mcp__github__github-issue_read`
- Working tree clean
- `pytest -q` green

**Post-merge verification:**
- New merge commit on `main`
- Issue closed by PR (not manually)
- Local `pytest -q` still green (308 baseline)
- No SonarCloud new CRITICAL/BLOCKER (per [[sonarcloud-quality-gate-semantics]])
- For #150: also verify shellcheck runs in CI on the PR

**Special case — #150:**
- Subagent installs shellcheck locally to test before pushing
- Wire into pre-commit (`plugins/hooks/.pre-commit-config.yaml` or repo root)
- Wire into GitHub Actions (`.github/workflows/shellcheck.yml` per D20 SHA-pinning)
- Run shellcheck on all `*.sh` files in repo
- Fix findings inline if ≤3; split into follow-up issue if >3
- Verify the new CI check passes on its own PR

## 5. Definition of done

The sprint is done when **all** are true:

1. All 7 issues (#150, #169, #170, #171, #172, #173, #174) closed on GitHub via merged PRs.
2. Each close was via a merged PR (not manually closed).
3. `git log --oneline main` shows 7 new merge commits.
4. `pytest -q` exits clean locally; no regressions from the 308 baseline.
5. `python scripts/validate.py` exits clean — `marketplace.json` byte-identical (D11 invariant).
6. `python scripts/generate_marketplace.py` exits clean.
7. Pre-commit (ruff + ruff-format + heretek fast-gate + new shellcheck if #150 lands first) all pass.
8. SonarCloud quality gate: `success` AND `output.summary.newIssues == 0` (per [[sonarcloud-quality-gate-semantics]]).
9. For #150 specifically: `shellcheck` runs in GitHub Actions CI on all `*.sh` files; pre-commit hook installed.

## 6. Risk register

| # | Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|---|
| R1 | #150 shellcheck surfaces many findings, expanding scope | Med | Med | Subagent splits findings into a follow-up issue if >3; keep current PR focused on gate installation only |
| R2 | Multiple tech-debt items touch `scripts/heretek_cli.py` (#169, #171, #172) — sequential dispatch handles this safely, but a poor review could force re-PRs | Low | Low | Per skill rule: never dispatch multiple implementers in parallel; sequential is enforced |
| R3 | #174 ADR lifecycle change affects template — if `0000-template.md` is used by existing ADRs, the change could conflict | Low | Med | Subagent verifies no other ADRs depend on the current two-state format before changing the template; if any exist, the change is opt-in via per-ADR frontmatter |
| R4 | #173 polish bundle splits if a sub-item fails review | Low | Low | Subagent commits all 4 fixes in one PR; if review fails, fix forward in same PR or split into a follow-up |
| R5 | Shellcheck version drift between local and CI | Med | Low | Pin shellcheck version in CI (per D20 SHA-pinning for new workflows) |

## 7. Re-evaluation triggers

Pause the sprint and re-plan if:
- #150 shellcheck surfaces so many findings (>10) that the gate installation can't ship in a single PR → split into "install gate" PR + "fix findings" PR
- Two consecutive subagent failures on the same issue → human review
- Mid-sprint scope-creep request → defer by default, re-confirm perimeter

## 8. Cross-references

- Prior sprint: `docs/superpowers/specs/2026-08-09-v35-collector-sprint-design.md`
- Prior plan: `docs/superpowers/plans/2026-08-09-v35-collector-sprint.md`
- Memory: [[sonarcloud-quality-gate-semantics]], [[issue-30-issue-drafter-plan]]