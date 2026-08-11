# v3.5 Observability Sprint Design

**Date:** 2026-08-11
**Status:** Approved (brainstorming session, all 5 sections ratified)
**Owner:** user + issue-loop autopilot

## Goal

Close the v3.5 observability phase (`#126`) by draining all 10 open
harness-observability issues (`#115`-`#124`) in 4 PRs, executed via the
existing issue-loop autopilot (`scripts/issue_loop/cli.py`).

## Scope

**In:**
- 10 issues: `#115`, `#116`, `#117`, `#118`, `#119`, `#120`, `#121`,
  `#122`, `#123`, `#124`
- 4 PRs (memory-aligned grouping, see PR Breakdown below)
- ADR + integration smoke + phase close-out **only at sub-spec 2 and
  3 boundaries** (PR3 and PR4); PR1 and PR2 are pre-boundary setup
- Three follow-up issues filed after the sprint (one per risk-mitigation item)

**Out:**
- Mechanical-gate rollout (`#210`-`#216` + `#226`)
- v2 plugin epic items (`#1`, `#3`-`#7`, `#17`-`#19`)
- v3 follow-ups (`#84`, `#85`, `#86`)
- Principles-audit (`#190`, `#191`)
- Research tracking (`#176`-`#179`)
- Phase trackers `#89`-`#92`, `#127`-`#128` (left as state-of-pattern)

## PR Breakdown

| PR | Issues | Scope | Acceptance |
|---|---|---|---|
| **PR1** | `#115` | Meta-fixture for testing harness runner | `harness_test.py` runs fixture successfully, fixtures layout documented |
| **PR2** | `#116` | 5 curated fixtures | Fixtures cover prompt eval, tool-use, hook chains, code-review, agent-loop edge cases |
| **PR3** | `#117` + `#118` | Sub-spec 2 close-out: `harness-test.yml` workflow (D20 SHA-pinned) + ADR + integration smoke | Workflow runs weekly cron; ADR records test-pipeline decisions; `#117` + `#118` closed |
| **PR4** | `#119` + `#120` + `#121` + `#122` + `#123` + `#124` | Sub-spec 3 close-out: `harness_auto_grade.py` + `harness_judge.py` + `scorecard.py` + `harness-eval.yml` + `/heretek:telemetry-review` skill + ADR + integration smoke | Three-layer scoring wired, eval workflow cron, skill deploys, ADR records eval decisions; `#119`-`#124` closed |

**Dependency chain (strict serial):**

```
PR1 (#115) → PR2 (#116) → PR3 (sub-spec 2 close) → PR4 (sub-spec 3 close)
```

## Execution Flow

**Autopilot config:**

```bash
scripts/issue_loop/cli.py run \
  --issues "#115,#116,#117,#118,#119,#120,#121,#122,#123,#124" \
  --route-mode fix \
  --group-by-pr \
  --pr-grouping 4pr-spec-2-3 \
  --branch-prefix fix/observability- \
  --close-phase '#126'
```

Flags `--pr-grouping` and `--close-phase` may not exist on the current
autopilot CLI; the implementation plan should verify and add them if
needed. If the autopilot cannot stage 4-PR groups directly, fall back
to `scripts/issue_loop/ledger.py` driving 4 sequential drivers.

**Per-PR cycle:**

1. **Triage** — issue-loop's `triage` stage reads issue body, routes to
   `fix` (code) or `spec` (ADR + skill) per issue type.
2. **Spec-first** — for issues with new components (workflows, ADRs,
   skills), spawn `executor` agent in spec-mode to draft design before
   code.
3. **TDD** — for code issues, `executor` writes tests first
   (`tests/test_harness_*.py`), then implementation.
4. **Verify** — `pre-commit run --all-files` + `scripts/ci.sh`; reject
   if smoke fails.
5. **Branch + PR** — `fix/observability-NNN-short-name`, body links
   issue + spec section.
6. **Issue close** — auto-close on merge with reference to PR + spec
   section.
7. **Ledger** — `.omc/issue-loop/ledger.jsonl` gets one row per issue
   for retrospective.

**Coordination across PRs:**

- PR1 → PR2: no shared files, can start PR2 as soon as PR1 lands
  (linear gate).
- PR2 → PR3: PR3 depends on PR2's fixture files existing in
  `tests/fixtures/harness/`.
- PR3 → PR4: PR4 needs PR3's `harness-test.yml` to exist (eval
  references it).

**Failure modes & aborts:**

- If `ci.sh` fails 2x on a PR → mark issue `needs-triage`, surface to
  user.
- If ADR is rejected → halt sub-spec close-out, do not close phase.
- If sub-spec 2 PR3 fails → halt PR4 (eval depends on it).

**Daily checkpoint:** `.omc/notepad.md` gets one entry per PR with
status + next action; user checks at will.

## Risks & Verification

**Risks (ranked):**

1. **Workflow cron + D20 SHA-pinning** (PR3, PR4) — SHA pinning a
   moving GitHub Actions version is fiddly. *Mitigation:* pin to
   specific commit SHA + ADR records choice.
2. **Eval scoring calibration** (PR4) — `harness_judge.py` Layer 2
   (LLM-judge) needs prompts calibrated against existing fixtures.
   *Mitigation:* stub judge for PR4, calibrate in next sprint via
   follow-up issue.
3. **Fixture brittleness** (PR1, PR2) — fixtures may overspecify,
   breaking on harness runner changes. *Mitigation:* PR1 meta-fixture
   covers the runner itself; fixtures in PR2 use public APIs only.
4. **Phase close-out timing** (`#126`) — closing too early if PR4
   needs re-roll. *Mitigation:* close `#126` only after PR4 merges.

**External dependencies:**

- All required inputs are in-repo:
  `docs/superpowers/plans/2026-08-08-harness-observability-{test-pipeline,eval}.md`
- Issue-loop autopilot exists (`scripts/issue_loop/cli.py`, last used
  2026-08-10 sweep).
- No new tools, no new deps.

**Verification (per PR, before merge):**

- `pre-commit run --all-files` clean
- `scripts/ci.sh` green (validate + generate + pytest + smoke)
- Issue acceptance criteria ticked (issue-loop verifies each bullet)
- ADRs include: decision + alternatives + trade-offs + reject signal
- Skills include: frontmatter + 1 example invocation

**Verification (sprint end):**

- All 10 issues closed, 4 PRs merged
- `#126` phase tracker updated to "shipped" (close with comment)
- `.omc/issue-loop/ledger.jsonl` shows 10 rows, 0 rejected
- Spec index updated at `sdd-plans-state.md` (memory file)
- Smoke test on `harness-test.yml` (manual trigger, observe workflow
  run)

**Drift check:** if any of the 10 issues closed between now and PR
start, recompute PR grouping before launching autopilot.

## Adjacent Work (Filed, Not Executed)

After the sprint lands, file three follow-up issues (not part of this
sprint):

1. **Calibrate `harness_judge.py` Layer 2 prompts against PR2 fixtures**
   — covers risk #2.
2. **Extend `harness-test.yml` to run PRs from forks** — D20
   hardening.
3. **Refresh `sdd-plans-state.md` memory + cross-link specs** — sprint
   retrospective.

**Triage queue to keep moving (no execution this sprint):**

- `#226` `security-scan failed` — emergency label; surface to user for
  immediate triage decision.
- `#210` mechanical-gate parent + `#211`-`#216` sub-issues — add
  `needs-triage` comment if not already present; queue for next
  sprint.

## Success Criteria

- 10 issues closed, 4 PRs merged into `main`.
- `#126` phase tracker marked "shipped" with cross-link to spec.
- `scripts/ci.sh` green on every PR.
- Three follow-up issues filed (risk-mitigation, fork-run, retrospective).
- Memory `sdd-plans-state.md` updated post-sprint.

## References

- Specs: `docs/superpowers/specs/2026-08-08-harness-observability-{test-pipeline,eval}.md`
- Plans: `docs/superpowers/plans/2026-08-08-harness-observability-{test-pipeline,eval}.md`
- Memory: `harness-observability-issues.md`, `issue-loop-sweep-2026-08-10.md`,
  `sdd-plans-state.md`
- Phase tracker: `#126` (v3.5: observability, in flight → shipped)
