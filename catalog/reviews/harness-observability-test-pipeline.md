# ADR: Harness test pipeline (sub-spec 2)

**Date:** 2026-08-11
**Status:** Accepted
**Closes:** #117, #118

## Context

Sub-spec 2 of the v3.5 observability roadmap adds a weekly test pipeline
that runs canonical harness fixtures against the harness runner
(`scripts/harness_test.py`). The pipeline must surface regressions in
the harness-eval loop before they reach production. Schedule and trigger
decisions shape how often feedback arrives and how invasive CI is.

## Decision

Use **weekly cron (Sunday 02:00 UTC) + `pull_request` label trigger**
named `harness-test` + manual `workflow_dispatch`.

Fixtures run in parallel via matrix strategy, one job per fixture.
Failure on any single fixture does not halt the others (`fail-fast:
false`).

## Alternatives considered

1. **Cron only** — rejected: no on-demand signal for PRs that want a
   pre-merge harness check.
2. **`pull_request` trigger only** — rejected: no weekly regression
   sweep to catch silent drift.
3. **Daily cron** — rejected: each fixture takes ~3-5 min × 5 in
   parallel = ~5 min wall-clock daily. Weekly cadence is enough for
   the regression-detection goal.
4. **Push-to-main trigger** — rejected: pollutes commit history with
   fixture-run churn; PR label is opt-in by maintainer.

## Trade-offs

- Sunday 02:00 UTC chosen to minimize GitHub Actions peak contention
  (Sunday is the lowest-traffic day for Actions runners).
- Matrix parallelism gives ~5 min wall-clock for all 5 fixtures.
- `fail-fast: false` ensures every fixture's result is recorded even
  if one fails (regression triage needs the full picture).
- Label-triggered PR runs require maintainer action — manual but
  intentional; harness runs are heavier than lint.

## Reject signal

If a fixture fails 3 consecutive weekly runs, mark it `harness-flaky`
and either disable in the matrix or move to `@pytest.mark.integration`
to skip in CI.

## References

- Spec: `docs/superpowers/specs/2026-08-08-harness-observability-test-pipeline.md`
- Plan: `docs/superpowers/plans/2026-08-08-harness-observability-test-pipeline.md`
- Workflow: `.github/workflows/harness-test.yml`
