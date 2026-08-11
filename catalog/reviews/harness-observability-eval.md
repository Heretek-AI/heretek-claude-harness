# ADR: Harness eval harness (sub-spec 3)

**Date:** 2026-08-11
**Status:** Accepted
**Closes:** #119, #120, #121, #122, #123, #124

## Context

Sub-spec 3 of the v3.5 observability roadmap adds three-layer scoring
over the artifact bundles produced by sub-spec 2. Layer 1 is deterministic
auto-grade. Layer 2 is LLM-judge against a rubric. Layer 3 is human-in-loop
review. Outputs include a weekly scorecard and regression detection.

## Decision

Three layers with strict escalation:

- **Layer 1** (`scripts/harness_auto_grade.py`): deterministic, sub-second.
  Reads `eval_input.json` + `patch.diff`. Verifies sha256 integrity (refuses
  mismatched). Runs auto-grade criteria from `expected.auto_grade`. Writes
  `result.json`. Refuses to grade if hashes don't match.
- **Layer 2** (`scripts/harness_judge.py`): LLM-judge, stub for v3.5.
  Real implementation will call the claude API with the rubric prompt
  from `expected.rubric.llm_judge_prompt`. Calibration is a follow-up.
- **Layer 3** (`/heretek:telemetry-review` skill): human-in-loop.
  Maintainer walks the scorecard, marks verdicts, opens regression issues.
  Skill mirrored to `.agents/skills/` for cross-platform agents.

Failures escalate upward; successes stay in lower layers.

## Alternatives considered

1. **Single-layer auto-grade** — rejected: no judgment for ambiguous cases
   (e.g., wrong-but-close diffs).
2. **LLM-judge only** — rejected: non-determinism poisons scorecards;
   can't triage Layer 1 cheap checks.
3. **Two-layer without skill** — rejected: no escape hatch for false
   positives; maintainer can't override auto+judge verdicts.

## Trade-offs

- Layer 2 stub trades real LLM-judging for deterministic testability.
  Calibration issue files in the sprint's follow-up batch.
- Layer 3 skill trades automation for human cost (acceptable for weekly
  cadence; ~5-10 min per review).
- Weekly cron (Sunday 03:00 UTC) runs after harness-test (02:00 UTC)
  finishes, so scorecards have fresh bundles to grade.

## Reject signal

If a fixture fails 3 consecutive weeks, mark it `harness-flaky` and
either disable in the matrix or move to `@pytest.mark.integration` to
skip in CI.

## References

- Spec: `docs/superpowers/specs/2026-08-08-harness-observability-eval.md`
- Plan: `docs/superpowers/plans/2026-08-08-harness-observability-eval.md`
- Parent: `catalog/reviews/harness-observability-test-pipeline.md`
