# v3.5 Collector Sprint — Design

**Date:** 2026-08-09
**Status:** Proposed (awaiting user review)
**Sprint window:** open-ended, drive until done

## 1. Goal

Ship the v3.5 observability **collector** sub-spec end-to-end: issues #109-#113 closed via merged PRs, ADR accepted, issue #2 acceptance criterion 1 confirmed met.

## 2. Scope

**In:**
- 5 issues (#109-#113), one PR each, FF-merge to `main`
- `catalog/reviews/observability-sub-spec-1.md` ADR
- Comment on issue #2 confirming AC-1 met

**Out (deferred):**
- Sub-spec 2 (test pipeline, #114-#118)
- Sub-spec 3 (eval harness, #119-#124)
- #150 ShellCheck and any other lane

## 3. Sequence

```
#109 schema  ──►  #110 collector hook  ──►  ┬─► #111 wire into hooks.json
                                             └─► #112 heretek telemetry CLI
                          │
                          ▼
                       #113 ADR + retention + close #2 ac-1
```

| Step | Issue | Depends on | Parallel-safe with |
|---|---|---|---|
| 1 | #109 schema fixture | — | — |
| 2 | #110 collector hook | #109 | — |
| 3a | #111 wire to `hooks.json` | #110 | #112 |
| 3b | #112 `heretek telemetry` CLI | #110 | #111 |
| 4 | #113 ADR + retention + close #2 | #109-#112 | — |

## 4. Execution mechanics

**Per-issue workflow:**
1. Spawn `executor` subagent (`model=sonnet`) with issue body + spec section + plan task.
2. Subagent does TDD: red → impl → green → refactor → commit → open PR.
3. Subagent returns PR URL + summary.
4. Main runs `merge-and-push` skill after CI green.
5. Verify issue state = closed; advance to next step.

**Parallelization:** Step 3a and 3b can run concurrently after #110 lands. Different files, different tests, different subagents.

**Branching:** each PR off fresh `feat/<issue>-<slug>` from `main`. No long-lived branches. FF-merge only.

**Pre-flight checklist per subagent spawn:**
- `git log --oneline main -5` confirms dependency PR merged
- Read latest spec section + plan task (no stale copy)
- `pytest -q` green; working tree clean

**Post-merge verification:**
- New merge commit on `main`
- Issue closed by PR (not manually)
- Local `pytest -q` still green
- No SonarCloud new CRITICAL/BLOCKER (per [[sonarcloud-quality-gate-semantics]])

**Tooling fallback:** if `gh` CLI hangs (>90s per [[issue-30-issue-drafter-plan]]), use `mcp__github__github-create_pull_request` + `mcp__github__github-update_pull_request`.

## 5. Definition of done

The sprint is done when **all** are true:

1. All 5 issues (#109-#113) closed on GitHub via merged PRs.
2. `git log --oneline main` shows 5 new merge commits in dependency order from §3 (parallel #111/#112 may interleave).
3. `pytest -q` clean locally, ≥90% coverage on `telemetry_collector.py` + `heretek_cli.py::telemetry`.
4. `python scripts/validate.py` clean — `marketplace.json` byte-identical (D11 invariant).
5. `catalog/reviews/observability-sub-spec-1.md` exists, follows `0000-template.md`.
6. Issue #2 has confirmation comment linking ADR + spec.
7. README has `heretek telemetry show` example.

## 6. Risk register

| # | Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|---|
| R1 | Schema under-specified → sub-specs 2/3 hit missing fields | Med | Med | Iterate schema via `docs/telemetry/CHANGELOG.md` + bump `schema_version` before #114 work |
| R2 | Collector latency > 50ms P95 budget | Low | High | Plan Task 2 test asserts; optimize (async validation) before merge if it fails |
| R3 | D11 marketplace.json drift | Low | High | `git diff --exit-code .claude-plugin/marketplace.json` invariant; CI catches it |
| R4 | D15 hooks ownership violated by other plugin | Low | High | Existing `test_no_plugin_ships_hooks_outside_hooks_plugin` invariant test |
| R5 | `gh` CLI hangs | High | Med | Fall back to GitHub MCP tools |
| R6 | Async hook 200ms timeout too tight | Low | Med | Async hook fires-and-forgets; timeout = drop event (acceptable per fail-open) |
| R7 | Subagent merges out-of-order | Med | High | Pre-flight checklist enforces dep-PR-merged gate |
| R8 | zstd unavailable in test env | Med | Low | Test calls `pytest.skip("zstandard not installed")` — non-blocking |

## 7. Re-evaluation triggers

Pause and re-plan if:
- Design flaw surfaces → spec amendment first
- 2 consecutive subagent failures on same issue → human review
- Persistent unrelated CI flake → triage separately
- Mid-sprint scope-creep request → defer by default, re-confirm perimeter

## 8. Cross-references

- Spec: `docs/superpowers/specs/2026-08-08-harness-observability-collector.md`
- Plan: `docs/superpowers/plans/2026-08-08-harness-observability-collector.md` (5 tasks map 1:1 to issues)
- Memory: [[harness-observability-issues]], [[issue-30-issue-drafter-plan]], [[sonarcloud-quality-gate-semantics]]
- Parent issue: #126 (v3.5 observability tracking)
- Target AC: #2 acceptance criterion 1