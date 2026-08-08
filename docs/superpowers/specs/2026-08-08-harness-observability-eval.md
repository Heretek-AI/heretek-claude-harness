---
date: 2026-08-08
topic: harness-observability-eval
status: draft
parent: 2026-08-08-harness-observability-design.md (D23–D29 inherited)
---

# Harness Observability — Eval Harness (sub-spec 3)

> Date: 2026-08-08. Sub-spec 3 of 3 under the parent harness-observability spec. Inherits D23–D29 unchanged.

## 1. Summary

Adds three-layer scoring over the artifact bundles produced by sub-spec 2. Layer 1 (auto-graded, deterministic) ships first. Layer 2 (LLM-judge) ships second. Layer 3 (human-in-loop via `/heretek:telemetry-review` skill) ships third. Outputs a weekly scorecard with regression + gap detection.

## 2. Components

### 2.1 Layer 1 — `scripts/harness_auto_grade.py`

Deterministic, sub-second. Pure consumer of sub-spec 2's `eval_input.json`.

**Inputs:** `eval_input.json` (from sub-spec 2's artifact bundle).

**Output:** updates `result.json` with `auto_grade` block:

```json
{
  "auto_grade": {
    "tests_passed": true,
    "test_output_excerpt": "....",
    "diff_similarity": 0.94,
    "diff_must_contain_match": ["strict-license", "argparse"],
    "telemetry_schema_valid": true,
    "hook_firing_rate": 0.97,
    "expected_hooks_fired": 8,
    "actual_hooks_fired": 8,
    "score": 0.91
  }
}
```

**Score formula:**
```
score = 0.5 * tests_passed
      + 0.2 * diff_similarity
      + 0.2 * (telemetry_schema_valid + telemetry_complete)
      + 0.1 * (actual_hooks_fired / expected_hooks_fired)
```

Per-fixture weight tuning lives in `expected.json`. Default weights for `curated` fixtures.

**Hard pass/fail:** `tests_passed: false` ⇒ score ≤ 0.5, regardless of other fields.

### 2.2 Layer 2 — `scripts/harness_judge.py`

Rubric-aware, non-deterministic. Reads `expected.json`'s `rubric` block.

**When it runs:** Only when layer-1 score ≥ 0.6 OR explicitly triggered via `judge: all` workflow_dispatch input.

**Judge prompt (abbreviated):**
```
You are reviewing a Claude Code session where the harness was given this task:
<task.md>

The harness produced this patch:
<patch.diff>

The harness made these tool calls:
<telemetry.jsonl summary>

Score each rubric criterion 0-3:
- 0 = missed entirely
- 1 = partial / attempted
- 2 = meets criterion
- 3 = exceeds criterion

<RUBRIC>

Output JSON: { criterion: str, score: int, evidence: str }[]
```

**Output:** Appended to `result.json` as `llm_judge.criteria[]` with per-criterion scores + evidence quotes.

**Reproducibility:** `temperature: 0`, model version pinned. `result.json` includes `judge_model_version` + `judge_prompt_sha256`.

### 2.3 Layer 3 — `.claude/skills/telemetry-review/SKILL.md` + `.agents/skills/telemetry-review/SKILL.md`

Interactive human review. The `/heretek:telemetry-review` skill walks a maintainer through the artifact bundle interactively.

**Companion:** `/heretek:telemetry-review-sample <week>` skill picks N runs from the week using stratified sampling (1 from each fixture, 1 from each LLM-judge band, random fill to N).

### 2.4 `scripts/scorecard.py`

Consumes all `result.json` from a week. Emits `scorecard-YYYY-WW.md`.

**Output:**
```markdown
# Harness Scorecard — Week 32, 2026

## Summary
- Runs: 35 (5 fixtures × 7 days)
- Median auto-grade score: 0.87
- Tests-passed rate: 31/35 (88.6%)

## Per-fixture
| Fixture        | Runs | Tests Pass | Median Score | Regression vs Last Week |
|----------------|------|------------|--------------|--------------------------|
| fixture-1      | 7    | 7/7        | 0.94         | +0.02                   |
```

**Regression detector:** Compares against `scorecard-YYYY-WW-prev.md`. Any fixture whose median drops > 0.05 opens a tracking issue (label `harness-regression`).

**Gap detector:** Cross-references `telemetry.jsonl` from all runs in the week. Flags any tool/hook combo where expected-firing ≠ actual-firing > 10% of the time. Opens tracking issue (label `harness-gap`).

### 2.5 `.github/workflows/harness-eval.yml`

Runs sub-spec 3 layer 1 + 2 on every artifact bundle produced by `harness-test.yml`. Publishes `scorecard-YYYY-WW.md` as a weekly GitHub issue.

## 3. Data flow

```
[harness-test.yml artifacts uploaded]
   └─▶ harness-eval.yml triggered
         ├─▶ download artifacts (harness-fixture-1, ..., harness-fixture-5)
         ├─▶ for each artifact bundle:
         │     ├─▶ layer 1: harness_auto_grade.py
         │     │     ├─▶ validate eval_input.json SHA matches
         │     │     ├─▶ run OSS test suite on patch.diff
         │     │     ├─▶ compute diff similarity
         │     │     ├─▶ validate telemetry.jsonl against schema
         │     │     └─▶ write result.json.auto_grade
         │     └─▶ layer 2 (if score >= 0.6):
         │           └─▶ harness_judge.py
         │                 └─▶ write result.json.llm_judge
         ├─▶ scripts/scorecard.py
         │     ├─▶ aggregate result.json across week
         │     ├─▶ compare with previous week
         │     ├─▶ if regression detected → open harness-regression issue
         │     ├─▶ if gap detected → open harness-gap issue
         │     └─▶ publish scorecard-YYYY-WW.md
         └─▶ upload-artifact scorecard-YYYY-WW.md
```

## 4. Error handling

| Failure | Response |
|---|---|
| `tests_passed: false` | Auto-grade hard-fail. Fixture marked red. No escalation. |
| Auto-grade runs but LLM-judge fails | Mark `llm_judge: skipped`. Layer 3 (human) still works. |
| Scorecard comparison detects regression | Open issue. Maintainer decides whether to investigate now or batch with weekly digest. |
| Human review session crashes mid-flow | Skill is idempotent — re-invoke, resume from saved state |
| All three layers fail to produce score | Run marked `unknown`. Tracked separately. Triggers emergency issue if > 3 consecutive. |

## 5. Testing

- `tests/test_harness_auto_grade.py` — hermetic. Loads fixtures + expected.json + patch.diff, asserts deterministic score.
- `tests/test_harness_judge.py` — uses LLM-judge-cache fixtures (recorded LLM outputs). Asserts prompt construction, schema, error handling. NOT a live LLM call.
- `tests/test_scorecard.py` — simulates 2 weeks of run data, asserts regression detector opens the right issue.

**Coverage target:** ≥90% on `scripts/harness_auto_grade.py`, `scripts/harness_judge.py`, `scripts/scorecard.py`.

## 6. Phases

| Phase | Deliverable | Exit |
|---|---|---|
| 3.1 | `scripts/harness_auto_grade.py` + `tests/test_harness_auto_grade.py` | layer 1 runs deterministically on a fixture; score matches expected |
| 3.2 | `scripts/harness_judge.py` + `tests/test_harness_judge.py` (with cache fixtures) | layer 2 runs against recorded LLM output; rubric aggregation correct |
| 3.3 | `.claude/skills/telemetry-review/SKILL.md` + mirror + sample skill | maintainer can invoke `/heretek:telemetry-review` and score an artifact bundle |
| 3.4 | `scripts/scorecard.py` + `harness-eval.yml` | weekly scorecard published; regression + gap detectors open issues |

## 7. References

- `docs/superpowers/specs/2026-08-08-harness-observability-design.md` — parent spec
- `docs/superpowers/specs/2026-08-08-harness-observability-test-pipeline.md` — sub-spec 2
- `scripts/security_scan.py:_shallow_clone` — pattern for SHA-pinned artifact handling
- Issue #80 — v1 test framework: external-data triangulation (M24 outcome metric)
- Issue #82 — v1 test framework: failure-mode-driven ideation (M24 outcome metric)
- Issue #83 — v1 test framework: cross-domain transfer ideation (M24 outcome metric)
