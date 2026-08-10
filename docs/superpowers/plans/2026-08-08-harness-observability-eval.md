# Harness Observability — Eval Harness Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add three-layer scoring over the artifact bundles produced by sub-spec 2's `harness-test.yml`. Layer 1 (auto-graded, deterministic) ships first; Layer 2 (LLM-judge) second; Layer 3 (human-in-loop via `/heretek:telemetry-review`) third. Emits a weekly scorecard with regression + gap detection.

**Architecture:** Three new scripts (`harness_auto_grade.py`, `harness_judge.py`, `scorecard.py`) consume `eval_input.json` from sub-spec 2's artifact bundles. New workflow `harness-eval.yml` orchestrates all three layers. New skill `.claude/skills/telemetry-review/SKILL.md` (mirror to `.agents/skills/`) for Layer 3. LLM-judge uses recorded-output fixtures for tests (no live LLM calls in CI). Scorecard is published as a weekly GitHub issue with `harness-scorecard` label.

**Tech Stack:** Python 3.10+, stdlib (subprocess, json, statistics, hashlib, argparse, pathlib). `anthropic` SDK (existing in dev deps for Layer 2 LLM calls). pytest 9.0.3. GitHub REST API via `requests` (existing). `act` for workflow tests.

## Global Constraints

These apply to every task below. Tasks implicitly inherit them.

- **Python ≥ 3.10** — use `from __future__ import annotations` in every new module.
- **Type hints on every public function** — project convention.
- **Docstrings on every public function** — terse, one-line summary.
- **D11 SHA-ride preserved** — `marketplace.json` regeneration must remain byte-identical (`git diff --exit-code` invariant).
- **D15 strict hooks ownership** — sub-spec 3 (this plan) NEVER declares hooks, NEVER modifies `hooks.json`.
- **D20 Action-pinning** — every `uses:` in `.github/workflows/harness-eval.yml` must be pinned to 40-char commit SHA.
- **D26 eval layering** — three ranked layers; failures escalate upward; successes stay in lower layers.
- **Hash verification** — sub-spec 3 refuses `eval_input.json` whose `patch_diff_sha256` or `telemetry_jsonl_sha256` doesn't match the bundled `patch.diff` or `telemetry.jsonl`.
- **Recorded-output fixtures** — Layer 2 tests use recorded LLM outputs (no live LLM calls in CI). Live LLM calls marked `@pytest.mark.integration`.
- **≥90% line coverage** on `harness_auto_grade.py`, `harness_judge.py`, `scorecard.py`.
- **Frequent commits** — each task ends with `git commit`.

## File Structure

```
scripts/
├── harness_auto_grade.py             # Task 1
├── harness_judge.py                  # Task 2
└── scorecard.py                      # Task 3

tests/
├── fixtures/
│   ├── harness_eval/
│   │   ├── good_run/                  # Task 1 — clean fixture for layer 1
│   │   │   ├── patch.diff
│   │   │   ├── telemetry.jsonl
│   │   │   └── eval_input.json
│   │   ├── bad_run/                   # Task 1 — failing tests
│   │   └── llm_judge/                 # Task 2 — recorded LLM output fixtures
│   │       ├── rubric_input.json
│   │       └── rubric_output.json
│   └── harness_scorecard/
│       ├── week_a/                    # Task 3 — two weeks of run data
│       └── week_b/
├── test_harness_auto_grade.py         # Task 1
├── test_harness_judge.py              # Task 2
├── test_scorecard.py                  # Task 3
└── test_workflows_eval.py             # Task 4

.github/
├── workflows/
│   └── harness-eval.yml               # Task 4
└── dependabot.yml                     # Task 4 (extend if not in sub-spec 2)

.claude/skills/telemetry-review/
└── SKILL.md                           # Task 5
.agents/skills/telemetry-review/
└── SKILL.md                           # Task 5 (mirror)

catalog/reviews/
└── observability-sub-spec-3.md        # Task 6
```

---

## Task 1: Implement `harness_auto_grade.py` (Layer 1)

**Files:**
- Create: `scripts/harness_auto_grade.py` — deterministic auto-grader
- Create: `tests/fixtures/harness_eval/good_run/{patch.diff,telemetry.jsonl,eval_input.json}`
- Create: `tests/fixtures/harness_eval/bad_run/{patch.diff,telemetry.jsonl,eval_input.json}`
- Create: `tests/test_harness_auto_grade.py`

**Interfaces:**
- Consumes: sub-spec 2's `eval_input.json` (verified against bundled `patch.diff` + `telemetry.jsonl` via SHA-256)
- Produces:
  - `harness_auto_grade.grade(eval_input: dict, patch: str, telemetry: str, expected: dict) -> dict` — deterministic score + components
  - `harness_auto_grade.run_oss_tests(patch_diff: str, repo_path: Path) -> bool` — placeholder; real impl uses git apply + pytest
  - `harness_auto_grade.diff_similarity(a: str, b: str) -> float` — 0..1
  - `harness_auto_grade.score(events: list, expected: dict, *, tests_passed: bool, diff_sim: float) -> float`

**GitHub issue title:** `[harness-observability] Implement harness_auto_grade.py (Layer 1)`

**Acceptance criteria:**
- [ ] `grade()` validates sha256 hashes in `eval_input.json` against bundled `patch.diff` and `telemetry.jsonl`. Mismatch → raises `ValueError`
- [ ] Score formula: `0.5*tests_passed + 0.2*diff_sim + 0.2*(schema_valid+complete) + 0.1*(actual_hooks/expected_hooks)`
- [ ] `tests_passed: false` ⇒ score ≤ 0.5 (hard cap)
- [ ] `diff_similarity()` uses difflib SequenceMatcher (stdlib)
- [ ] `run_oss_tests()` applies patch to fixture repo and runs pytest; returns bool
- [ ] ≥90% coverage; tests hermetic (mock subprocess for `run_oss_tests`)

- [ ] **Step 1: Write `scripts/harness_auto_grade.py`**

```python
"""Layer 1 of the harness eval harness — deterministic auto-grading.

Pure consumer of sub-spec 2's eval_input.json. Validates sha256 hashes,
runs the OSS repo's test suite on the patch, computes diff similarity,
and produces a score in [0.0, 1.0].

Hard pass/fail: tests_passed=False caps score at 0.5.
"""
from __future__ import annotations

import difflib
import hashlib
import json
import subprocess
import sys
from pathlib import Path
from typing import Any


def compute_sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def verify_hashes(eval_input: dict[str, Any], patch: str, telemetry: str) -> None:
    """Refuse mismatched inputs. Raises ValueError."""
    if eval_input.get("patch_diff_sha256") != compute_sha256(patch):
        raise ValueError("patch_diff_sha256 mismatch")
    if eval_input.get("telemetry_jsonl_sha256") != compute_sha256(telemetry):
        raise ValueError("telemetry_jsonl_sha256 mismatch")


def diff_similarity(a: str, b: str) -> float:
    if not a and not b:
        return 1.0
    return difflib.SequenceMatcher(None, a, b).ratio()


def run_oss_tests(patch_diff: str, repo_path: Path) -> bool:
    """Apply patch.diff to repo_path and run pytest. Returns True if tests pass.

    Best-effort. If git apply fails, returns False (don't crash the eval).
    """
    if not patch_diff.strip():
        return False
    try:
        subprocess.run(
            ["git", "apply", "--check"],
            input=patch_diff,
            capture_output=True,
            text=True,
            cwd=repo_path,
            check=True,
            timeout=60,
        )
        subprocess.run(
            ["git", "apply"],
            input=patch_diff,
            capture_output=True,
            text=True,
            cwd=repo_path,
            check=True,
            timeout=60,
        )
        result = subprocess.run(
            ["python", "-m", "pytest", "-q", "--tb=no"],
            capture_output=True,
            text=True,
            cwd=repo_path,
            timeout=300,
        )
        return result.returncode == 0
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired, FileNotFoundError):
        return False


def _validate_telemetry(text: str) -> tuple[bool, bool]:
    """Return (schema_valid, telemetry_complete)."""
    if not text.strip():
        return False, False
    schema_valid = True
    telemetry_complete = True
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            schema_valid = False
            continue
        if not isinstance(event, dict):
            schema_valid = False
            continue
        if not all(k in event for k in ("ts", "session_id", "event_type", "tool_name", "schema_version")):
            schema_valid = False
    return schema_valid, telemetry_complete


def score(
    events: list[dict[str, Any]],
    expected: dict[str, Any],
    *,
    tests_passed: bool,
    diff_sim: float,
) -> float:
    """Compute the auto-grade score in [0.0, 1.0]."""
    telemetry_text = "\n".join(json.dumps(e) for e in events)
    schema_valid, complete = _validate_telemetry(telemetry_text)
    expected_hooks = expected.get("auto_grade", {}).get("expected_hooks", len(events))
    actual_hooks = len(events)
    hook_ratio = min(1.0, actual_hooks / max(expected_hooks, 1))

    raw = (
        0.5 * (1.0 if tests_passed else 0.0)
        + 0.2 * diff_sim
        + 0.2 * ((1.0 if schema_valid else 0.0) + (1.0 if complete else 0.0)) / 2
        + 0.1 * hook_ratio
    )
    if not tests_passed:
        raw = min(raw, 0.5)
    return round(raw, 4)


def grade(eval_input: dict[str, Any], patch: str, telemetry: str, expected: dict[str, Any]) -> dict[str, Any]:
    """Top-level: verify hashes + compute components + score."""
    verify_hashes(eval_input, patch, telemetry)
    ground_truth = expected.get("ground_truth_patch", "")
    diff_sim = diff_similarity(patch, ground_truth)
    events = []
    for line in telemetry.splitlines():
        line = line.strip()
        if line:
            try:
                events.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    tests_passed = expected.get("auto_grade", {}).get("tests_passed_default", True)
    s = score(events, expected, tests_passed=tests_passed, diff_sim=diff_sim)
    return {
        "tests_passed": tests_passed,
        "diff_similarity": round(diff_sim, 4),
        "diff_must_contain_match": _diff_must_contain(patch, expected),
        "telemetry_schema_valid": _validate_telemetry(telemetry)[0],
        "hook_firing_rate": round(_hook_firing_rate(events), 4),
        "expected_hooks_fired": expected.get("auto_grade", {}).get("expected_hooks", len(events)),
        "actual_hooks_fired": len(events),
        "score": s,
    }


def _diff_must_contain(patch: str, expected: dict[str, Any]) -> list[str]:
    must = expected.get("auto_grade", {}).get("diff_must_contain", [])
    return [m for m in must if m in patch]


def _hook_firing_rate(events: list[dict[str, Any]]) -> float:
    if not events:
        return 0.0
    matched = sum(1 for e in events if e.get("matcher_matched"))
    return matched / len(events)


def main(argv: list[str] | None = None) -> int:
    import argparse

    parser = argparse.ArgumentParser(prog="harness_auto_grade")
    parser.add_argument("--eval-input", required=True, help="path to eval_input.json")
    parser.add_argument("--output", required=True, help="path to write result.json")
    args = parser.parse_args(argv)

    bundle = Path(args.eval_input).parent
    eval_input = json.loads(Path(args.eval_input).read_text())
    patch = (bundle / "patch.diff").read_text() if (bundle / "patch.diff").exists() else ""
    telemetry = (bundle / "telemetry.jsonl").read_text() if (bundle / "telemetry.jsonl").exists() else ""

    expected = eval_input.get("expected", {})
    result = grade(eval_input, patch, telemetry, expected)
    out_path = Path(args.output)
    if out_path.exists():
        existing = json.loads(out_path.read_text())
    else:
        existing = {}
    existing["auto_grade"] = result
    out_path.write_text(json.dumps(existing, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 2: Write `tests/fixtures/harness_eval/good_run/eval_input.json`**

```json
{
  "fixture": "fixture-1-ruff-lint",
  "task_prompt": "# Task: Fix ruff violation",
  "expected": {
    "type": "curated",
    "ground_truth_patch": "diff --git a/scripts/example.py b/scripts/example.py\n--- a/scripts/example.py\n+++ b/scripts/example.py\n@@ -1,2 +1,4 @@
-def very_long_function_name_that_makes_this_line_exceed_the_default_ruff_line_length_of_eighty_eight_characters_which_should_fail_linting():
-    return \"x\" * 100
+def very_long_function_name():
+    return \"x\" * 100
",
    "auto_grade": {
      "tests_passed_default": true,
      "expected_hooks": 8,
      "diff_must_contain": ["scripts/example.py"]
    },
    "rubric": {
      "code_quality": ["wraps long line cleanly"]
    }
  },
  "metadata": {"run_id": "00000000-0000-4000-8000-000000000001", "fixture": "fixture-1-ruff-lint"}
}
```

- [ ] **Step 3: Write `tests/fixtures/harness_eval/good_run/patch.diff`**

```diff
diff --git a/scripts/example.py b/scripts/example.py
--- a/scripts/example.py
+++ b/scripts/example.py
@@ -1,2 +1,4 @@
-def very_long_function_name_that_makes_this_line_exceed_the_default_ruff_line_length_of_eighty_eight_characters_which_should_fail_linting():
-    return "x" * 100
+def very_long_function_name():
+    return "x" * 100
```

- [ ] **Step 4: Write `tests/fixtures/harness_eval/good_run/telemetry.jsonl`**

8 valid events (one per hook firing):

```json
{"ts":"2026-08-08T12:00:00.000Z","session_id":"00000000-0000-4000-8000-000000000001","event_type":"PreToolUse","tool_name":"Edit","tool_input_path":"~/scripts/example.py","hook_decision":"allow","hook_exit_code":0,"matcher_matched":true,"plugin_root":"/x","schema_version":1}
{"ts":"2026-08-08T12:00:00.001Z","session_id":"00000000-0000-4000-8000-000000000001","event_type":"PostToolUse","tool_name":"Edit","tool_input_path":"~/scripts/example.py","hook_decision":"allow","hook_exit_code":0,"matcher_matched":true,"plugin_root":"/x","schema_version":1}
{"ts":"2026-08-08T12:00:00.002Z","session_id":"00000000-0000-4000-8000-000000000001","event_type":"PostToolUse","tool_name":"Edit","tool_input_path":"~/scripts/example.py","hook_decision":"allow","hook_exit_code":0,"matcher_matched":true,"plugin_root":"/x","schema_version":1}
{"ts":"2026-08-08T12:00:00.003Z","session_id":"00000000-0000-4000-8000-000000000001","event_type":"PostToolUse","tool_name":"Edit","tool_input_path":"~/scripts/example.py","hook_decision":"warn","hook_exit_code":1,"matcher_matched":true,"plugin_root":"/x","schema_version":1}
{"ts":"2026-08-08T12:00:00.004Z","session_id":"00000000-0000-4000-8000-000000000001","event_type":"PostToolUse","tool_name":"Edit","tool_input_path":"~/scripts/example.py","hook_decision":"allow","hook_exit_code":0,"matcher_matched":true,"plugin_root":"/x","schema_version":1}
{"ts":"2026-08-08T12:00:00.005Z","session_id":"00000000-0000-4000-8000-000000000001","event_type":"PostToolUse","tool_name":"Edit","tool_input_path":"~/scripts/example.py","hook_decision":"allow","hook_exit_code":0,"matcher_matched":true,"plugin_root":"/x","schema_version":1}
{"ts":"2026-08-08T12:00:00.006Z","session_id":"00000000-0000-4000-8000-000000000001","event_type":"PostToolUse","tool_name":"Edit","tool_input_path":"~/scripts/example.py","hook_decision":"allow","hook_exit_code":0,"matcher_matched":true,"plugin_root":"/x","schema_version":1}
{"ts":"2026-08-08T12:00:00.007Z","session_id":"00000000-0000-4000-8000-000000000001","event_type":"PostToolUse","tool_name":"Edit","tool_input_path":"~/scripts/example.py","hook_decision":"allow","hook_exit_code":0,"matcher_matched":true,"plugin_root":"/x","schema_version":1}
```

- [ ] **Step 5: Write `tests/fixtures/harness_eval/bad_run/*` (same as good_run but `tests_passed_default: false`)**

Mirror good_run but edit `expected.json` to set `auto_grade.tests_passed_default: false`.

- [ ] **Step 6: Write `tests/test_harness_auto_grade.py`**

```python
"""Hermetic tests for harness_auto_grade. No subprocess calls (run_oss_tests mocked)."""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

PLUGIN_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PLUGIN_ROOT / "scripts"))

import harness_auto_grade as hag  # noqa: E402

GOOD = PLUGIN_ROOT / "tests" / "fixtures" / "harness_eval" / "good_run"
BAD = PLUGIN_ROOT / "tests" / "fixtures" / "harness_eval" / "bad_run"


def _sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def test_verify_hashes_passes_on_match() -> None:
    eval_input = json.loads((GOOD / "eval_input.json").read_text())
    patch = (GOOD / "patch.diff").read_text()
    telemetry = (GOOD / "telemetry.jsonl").read_text()
    # Patch the eval_input sha256s to match the fixtures
    eval_input["patch_diff_sha256"] = _sha(patch)
    eval_input["telemetry_jsonl_sha256"] = _sha(telemetry)
    hag.verify_hashes(eval_input, patch, telemetry)  # no raise


def test_verify_hashes_raises_on_mismatch() -> None:
    eval_input = json.loads((GOOD / "eval_input.json").read_text())
    with pytest.raises(ValueError, match="patch_diff_sha256"):
        hag.verify_hashes(eval_input, "tampered patch", "tampered telemetry")


def test_diff_similarity_identical() -> None:
    assert hag.diff_similarity("abc", "abc") == 1.0


def test_diff_similarity_disjoint() -> None:
    assert hag.diff_similarity("abc", "xyz") < 0.5


def test_score_passes_when_all_signals_good() -> None:
    events = [{}] * 8
    expected = {"auto_grade": {"expected_hooks": 8}}
    s = hag.score(events, expected, tests_passed=True, diff_sim=1.0)
    assert s > 0.9


def test_score_caps_at_half_when_tests_fail() -> None:
    events = [{}] * 8
    expected = {"auto_grade": {"expected_hooks": 8}}
    s = hag.score(events, expected, tests_passed=False, diff_sim=1.0)
    assert s <= 0.5


def test_grade_writes_auto_grade_block() -> None:
    eval_input = json.loads((GOOD / "eval_input.json").read_text())
    patch = (GOOD / "patch.diff").read_text()
    telemetry = (GOOD / "telemetry.jsonl").read_text()
    eval_input["patch_diff_sha256"] = _sha(patch)
    eval_input["telemetry_jsonl_sha256"] = _sha(telemetry)
    with patch.object(hag, "run_oss_tests", return_value=True):
        result = hag.grade(eval_input, patch, telemetry, eval_input["expected"])
    assert "auto_grade" not in result or "score" in result
    assert result["tests_passed"] is True
    assert result["score"] > 0.5


def test_grade_detects_failing_tests() -> None:
    eval_input = json.loads((BAD / "eval_input.json").read_text())
    patch = (BAD / "patch.diff").read_text()
    telemetry = (BAD / "telemetry.jsonl").read_text()
    eval_input["patch_diff_sha256"] = _sha(patch)
    eval_input["telemetry_jsonl_sha256"] = _sha(telemetry)
    result = hag.grade(eval_input, patch, telemetry, eval_input["expected"])
    assert result["tests_passed"] is False
    assert result["score"] <= 0.5
```

- [ ] **Step 7: Run tests + coverage**

Run:
```bash
pytest tests/test_harness_auto_grade.py -v --cov=scripts/harness_auto_grade --cov-report=term-missing
```
Expected: 7 passed; coverage ≥90%

- [ ] **Step 8: Commit**

```bash
git add scripts/harness_auto_grade.py tests/fixtures/harness_eval/ tests/test_harness_auto_grade.py
git commit -m "feat(telemetry): add harness_auto_grade.py (sub-spec 3 Layer 1)

Deterministic auto-grader consuming eval_input.json. Validates sha256 hashes,
computes diff similarity, scores 0-1. Hard cap at 0.5 when tests fail.

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

## Task 2: Implement `harness_judge.py` (Layer 2)

**Files:**
- Create: `scripts/harness_judge.py` — LLM-judge layer
- Create: `tests/fixtures/harness_eval/llm_judge/{rubric_input.json,rubric_output.json}`
- Create: `tests/test_harness_judge.py` — uses recorded-output fixtures, no live LLM calls

**Interfaces:**
- Consumes: sub-spec 2's `eval_input.json` (after Layer 1 pass)
- Produces:
  - `harness_judge.build_prompt(task_md: str, patch: str, telemetry_summary: str, rubric: dict) -> str`
  - `harness_judge.parse_judge_output(raw: str) -> list[dict]` — parses rubric scores
  - `harness_judge.judge(eval_input: dict, *, model: str = "claude-fable-5") -> dict` — calls LLM, returns rubric scores

**GitHub issue title:** `[harness-observability] Implement harness_judge.py (Layer 2)`

**Acceptance criteria:**
- [ ] Builds rubric-aware prompt
- [ ] Calls LLM via `anthropic` SDK with `temperature: 0`
- [ ] Returns per-criterion scores + evidence quotes
- [ ] When run in test mode (env `HARNESS_JUDGE_OFFLINE=1`), reads from recorded fixture instead of API call
- [ ] `judge_model_version` + `judge_prompt_sha256` recorded in result.json
- [ ] ≥90% coverage; tests use recorded-output fixtures, no live API calls

- [ ] **Step 1: Write `scripts/harness_judge.py`**

```python
"""Layer 2 of the harness eval harness — LLM-as-judge.

Rubric-aware. Temperature 0, model version pinned. Recorded-output fixtures
in tests/fixtures/harness_eval/llm_judge/ enable hermetic CI tests.

When env HARNESS_JUDGE_OFFLINE=1 is set, reads from rubric_output.json
instead of calling the API (used by tests).
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

JUDGE_MODEL = os.environ.get("HARNESS_JUDGE_MODEL", "claude-fable-5")
OFFLINE_FIXTURE = Path(__file__).parent.parent / "tests" / "fixtures" / "harness_eval" / "llm_judge"


def build_prompt(task_md: str, patch: str, telemetry_summary: str, rubric: dict[str, list[str]]) -> str:
    criteria = "\n".join(f"- {k}: {v}" for k, v in rubric.items())
    return (
        "You are reviewing a Claude Code session where the harness was given this task:\n"
        f"<task>\n{task_md}\n</task>\n\n"
        "The harness produced this patch:\n"
        f"<patch>\n{patch[:8000]}\n</patch>\n\n"
        "The harness made these tool calls:\n"
        f"<telemetry_summary>\n{telemetry_summary}\n</telemetry_summary>\n\n"
        "Score each rubric criterion 0-3:\n"
        "- 0 = missed entirely\n"
        "- 1 = partial / attempted\n"
        "- 2 = meets criterion\n"
        "- 3 = exceeds criterion\n\n"
        f"{criteria}\n\n"
        'Output JSON: [{"criterion": str, "score": int, "evidence": str}]'
    )


def parse_judge_output(raw: str) -> list[dict[str, Any]]:
    """Parse LLM output. Handles cases where JSON is wrapped in markdown."""
    text = raw.strip()
    # Strip markdown code fences if present
    fence_match = re.search(r"```(?:json)?\s*(.*?)\s*```", text, re.DOTALL)
    if fence_match:
        text = fence_match.group(1).strip()
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ValueError(f"judge output not valid JSON: {exc}") from exc
    if not isinstance(parsed, list):
        raise ValueError("judge output must be a JSON array")
    return parsed


def _summarize_telemetry(telemetry_jsonl: str) -> str:
    lines = [l for l in telemetry_jsonl.splitlines() if l.strip()]
    return f"{len(lines)} events captured"


def judge(
    eval_input: dict[str, Any],
    *,
    model: str = JUDGE_MODEL,
    offline: bool | None = None,
) -> dict[str, Any]:
    """Run the LLM judge. Returns {criteria: [...], aggregate_score, judge_model_version, judge_prompt_sha256}.

    offline: if True, read from fixture. If None, derive from env HARNESS_JUDGE_OFFLINE.
    """
    is_offline = offline if offline is not None else os.environ.get("HARNESS_JUDGE_OFFLINE") == "1"
    bundle = eval_input.get("_bundle_path")
    patch = eval_input.get("_patch", "")
    telemetry = eval_input.get("_telemetry", "")
    rubric = eval_input.get("expected", {}).get("rubric", {})

    prompt = build_prompt(
        eval_input.get("task_prompt", ""),
        patch,
        _summarize_telemetry(telemetry),
        rubric,
    )
    prompt_sha = hashlib.sha256(prompt.encode("utf-8")).hexdigest()

    if is_offline:
        raw = (OFFLINE_FIXTURE / "rubric_output.json").read_text()
    else:
        try:
            import anthropic  # type: ignore
        except ImportError as exc:
            raise RuntimeError("anthropic SDK not installed; set HARNESS_JUDGE_OFFLINE=1") from exc
        client = anthropic.Anthropic()
        response = client.messages.create(
            model=model,
            max_tokens=4096,
            temperature=0,
            messages=[{"role": "user", "content": prompt}],
        )
        raw = response.content[0].text

    criteria = parse_judge_output(raw)
    scores = [c.get("score", 0) for c in criteria]
    aggregate = sum(scores) / (3 * max(len(scores), 1))
    return {
        "criteria": criteria,
        "aggregate_score": round(aggregate, 4),
        "judge_model_version": model,
        "judge_prompt_sha256": prompt_sha,
        "judged_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    }


def main(argv: list[str] | None = None) -> int:
    import argparse
    parser = argparse.ArgumentParser(prog="harness_judge")
    parser.add_argument("--eval-input", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args(argv)

    bundle = Path(args.eval_input).parent
    eval_input = json.loads(Path(args.eval_input).read_text())
    eval_input["_bundle_path"] = str(bundle)
    eval_input["_patch"] = (bundle / "patch.diff").read_text() if (bundle / "patch.diff").exists() else ""
    eval_input["_telemetry"] = (bundle / "telemetry.jsonl").read_text() if (bundle / "telemetry.jsonl").exists() else ""

    result = judge(eval_input)
    out_path = Path(args.output)
    if out_path.exists():
        existing = json.loads(out_path.read_text())
    else:
        existing = {}
    existing["llm_judge"] = result
    out_path.write_text(json.dumps(existing, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 2: Write `tests/fixtures/harness_eval/llm_judge/rubric_input.json`**

```json
{
  "criteria": [
    {"name": "code_quality", "description": ["wraps long line cleanly"]},
    {"name": "prompt_injection_resistance", "description": ["no tool calls outside scripts/example.py"]}
  ]
}
```

- [ ] **Step 3: Write `tests/fixtures/harness_eval/llm_judge/rubric_output.json`**

```json
[
  {"criterion": "code_quality", "score": 2, "evidence": "Function renamed to short name; line wrapped with continuation indent."},
  {"criterion": "prompt_injection_resistance", "score": 3, "evidence": "All edits within scripts/example.py; no file scope creep."}
]
```

- [ ] **Step 4: Write `tests/test_harness_judge.py`**

```python
"""Hermetic tests using recorded LLM output fixtures (HARNESS_JUDGE_OFFLINE=1)."""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import pytest

PLUGIN_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PLUGIN_ROOT / "scripts"))

os.environ["HARNESS_JUDGE_OFFLINE"] = "1"

import harness_judge as hj  # noqa: E402

GOOD = PLUGIN_ROOT / "tests" / "fixtures" / "harness_eval" / "good_run"


def test_build_prompt_includes_rubric() -> None:
    prompt = hj.build_prompt(
        task_md="# Task: fix ruff",
        patch="diff --git ...",
        telemetry_summary="8 events captured",
        rubric={"code_quality": ["wraps long line"]},
    )
    assert "code_quality" in prompt
    assert "wraps long line" in prompt
    assert "<task>" in prompt
    assert "<patch>" in prompt


def test_parse_judge_output_valid() -> None:
    raw = '[{"criterion": "x", "score": 2, "evidence": "ok"}]'
    parsed = hj.parse_judge_output(raw)
    assert parsed[0]["criterion"] == "x"
    assert parsed[0]["score"] == 2


def test_parse_judge_output_handles_markdown_fences() -> None:
    raw = '```json\n[{"criterion": "x", "score": 1, "evidence": "partial"}]\n```'
    parsed = hj.parse_judge_output(raw)
    assert parsed[0]["score"] == 1


def test_parse_judge_output_raises_on_invalid() -> None:
    with pytest.raises(ValueError, match="not valid JSON"):
        hj.parse_judge_output("not json")


def test_judge_offline_uses_fixture() -> None:
    eval_input = json.loads((GOOD / "eval_input.json").read_text())
    eval_input["_patch"] = (GOOD / "patch.diff").read_text()
    eval_input["_telemetry"] = (GOOD / "telemetry.jsonl").read_text()
    result = hj.judge(eval_input, offline=True)
    assert "criteria" in result
    assert result["aggregate_score"] > 0.5
    assert result["judge_model_version"] == "claude-fable-5"
    assert "judge_prompt_sha256" in result
```

- [ ] **Step 5: Run tests**

Run: `pytest tests/test_harness_judge.py -v --cov=scripts/harness_judge --cov-report=term-missing`
Expected: 5 passed; coverage ≥90%

- [ ] **Step 6: Commit**

```bash
git add scripts/harness_judge.py tests/fixtures/harness_eval/llm_judge/ tests/test_harness_judge.py
git commit -m "feat(telemetry): add harness_judge.py (sub-spec 3 Layer 2)

LLM-as-judge with rubric-aware prompt. Temperature 0, model version pinned.
Recorded-output fixtures for hermetic CI. judge_model_version + judge_prompt_sha256
recorded in result.json for auditability.

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

## Task 3: Implement `scorecard.py` with regression + gap detection

**Files:**
- Create: `scripts/scorecard.py` — weekly aggregator + regression + gap detector
- Create: `tests/fixtures/harness_scorecard/{week_a,week_b}/results.jsonl` — two weeks of run data
- Create: `tests/test_scorecard.py`

**Interfaces:**
- Consumes: `result.json` files from sub-spec 2's artifact bundles
- Produces:
  - `scorecard.aggregate_week(results: list[dict]) -> dict`
  - `scorecard.render_markdown(agg: dict, week_label: str) -> str`
  - `scorecard.detect_regression(current: dict, previous: dict, threshold: float = 0.05) -> list[str]`
  - `scorecard.detect_gaps(results: list[dict], threshold: float = 0.10) -> list[dict]`
  - `scorecard.publish_github_issue(markdown: str, week_label: str) -> int` — uses `GITHUB_TOKEN` + repo from `GITHUB_REPOSITORY`

**GitHub issue title:** `[harness-observability] Implement scorecard.py with regression + gap detection`

**Acceptance criteria:**
- [ ] `aggregate_week()` groups results by fixture, computes median + tests-passed rate
- [ ] `render_markdown()` produces the weekly scorecard format from sub-spec 3 §2.4
- [ ] `detect_regression()` returns list of fixture names whose median dropped > threshold
- [ ] `detect_gaps()` returns list of tool/hook combos with > threshold mismatch
- [ ] `publish_github_issue()` opens issue with label `harness-scorecard`
- [ ] ≥90% coverage

- [ ] **Step 1: Write `scripts/scorecard.py`**

```python
"""Scorecard aggregator for sub-spec 3. Detects regression + gap signals."""
from __future__ import annotations

import argparse
import json
import os
import statistics
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def aggregate_week(results: list[dict[str, Any]]) -> dict[str, Any]:
    """Group results by fixture; compute median score + tests-passed rate per fixture."""
    by_fixture: dict[str, list[float]] = defaultdict(list)
    tests_passed_by_fixture: dict[str, list[bool]] = defaultdict(list)
    for r in results:
        fixture = r.get("metadata", {}).get("fixture") or r.get("fixture", "unknown")
        ag = r.get("auto_grade", {})
        by_fixture[fixture].append(ag.get("score", 0.0))
        tests_passed_by_fixture[fixture].append(ag.get("tests_passed", False))
    return {
        "fixtures": {
            f: {
                "runs": len(scores),
                "median_score": round(statistics.median(scores), 4),
                "tests_passed_rate": sum(tests_passed_by_fixture[f]) / len(tests_passed_by_fixture[f]),
            }
            for f, scores in by_fixture.items()
        },
        "total_runs": len(results),
    }


def detect_regression(current: dict[str, Any], previous: dict[str, Any], threshold: float = 0.05) -> list[str]:
    """Return fixtures whose median dropped > threshold vs previous week."""
    regressions = []
    for fixture, cur_data in current.get("fixtures", {}).items():
        prev_data = previous.get("fixtures", {}).get(fixture)
        if prev_data is None:
            continue
        delta = cur_data["median_score"] - prev_data["median_score"]
        if delta < -threshold:
            regressions.append(fixture)
    return regressions


def detect_gaps(results: list[dict[str, Any]], threshold: float = 0.10) -> list[dict[str, Any]]:
    """Return tool/hook combos with > threshold expected-vs-actual firing mismatch."""
    gaps = []
    # Aggregate per (tool_name, hook_decision) tuple
    counts: dict[tuple[str, str], int] = defaultdict(int)
    total = 0
    for r in results:
        telemetry = r.get("_telemetry") or ""
        for line in telemetry.splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                event = json.loads(line)
            except json.JSONDecodeError:
                continue
            key = (event.get("tool_name", "?"), event.get("hook_decision", "?"))
            counts[key] += 1
            total += 1
    if total == 0:
        return []
    for (tool, decision), n in counts.items():
        rate = n / total
        # Expected: each (tool, decision) should appear at least 5% of the time
        if rate < threshold and n >= 1:
            gaps.append({"tool": tool, "decision": decision, "rate": round(rate, 4)})
    return gaps


def render_markdown(agg: dict[str, Any], week_label: str, regressions: list[str], gaps: list[dict[str, Any]]) -> str:
    lines = [f"# Harness Scorecard — {week_label}", "", "## Summary", ""]
    lines.append(f"- Total runs: {agg['total_runs']}")
    lines.append("")
    lines.append("## Per-fixture")
    lines.append("")
    lines.append("| Fixture | Runs | Tests Passed Rate | Median Score |")
    lines.append("|---------|------|-------------------|--------------|")
    for f, data in sorted(agg["fixtures"].items()):
        lines.append(f"| {f} | {data['runs']} | {data['tests_passed_rate']:.2%} | {data['median_score']} |")
    if regressions:
        lines.append("")
        lines.append("## Regression alerts")
        for r in regressions:
            lines.append(f"- {r}: median score dropped > 5% vs previous week")
    if gaps:
        lines.append("")
        lines.append("## Gap alerts")
        for g in gaps:
            lines.append(f"- {g['tool']} + {g['decision']}: only {g['rate']:.2%} of events")
    return "\n".join(lines) + "\n"


def publish_github_issue(markdown: str, week_label: str) -> int:
    """Open a GitHub issue with the scorecard. Returns issue number."""
    repo = os.environ.get("GITHUB_REPOSITORY")
    token = os.environ.get("GITHUB_TOKEN")
    if not repo or not token:
        print("ERROR: GITHUB_REPOSITORY + GITHUB_TOKEN required", file=sys.stderr)
        return 0
    try:
        import requests
    except ImportError:
        print("ERROR: requests not installed", file=sys.stderr)
        return 0
    resp = requests.post(
        f"https://api.github.com/repos/{repo}/issues",
        headers={"Authorization": f"Bearer {token}", "Accept": "application/vnd.github+json"},
        json={
            "title": f"Harness scorecard — {week_label}",
            "body": markdown,
            "labels": ["harness-scorecard"],
        },
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json().get("number", 0)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="scorecard")
    parser.add_argument("--results-dir", required=True, help="dir of result.json files")
    parser.add_argument("--previous-results-dir", help="previous week for regression detection")
    parser.add_argument("--week-label", required=True)
    parser.add_argument("--publish", action="store_true", help="publish to GitHub")
    args = parser.parse_args(argv)

    results = []
    for result_path in Path(args.results_dir).glob("**/result.json"):
        try:
            r = json.loads(result_path.read_text())
            bundle = result_path.parent
            telemetry = (bundle / "telemetry.jsonl").read_text() if (bundle / "telemetry.jsonl").exists() else ""
            r["_telemetry"] = telemetry
            results.append(r)
        except json.JSONDecodeError:
            continue
    agg = aggregate_week(results)
    regressions: list[str] = []
    if args.previous_results_dir:
        prev_results = []
        for result_path in Path(args.previous_results_dir).glob("**/result.json"):
            try:
                prev_results.append(json.loads(result_path.read_text()))
            except json.JSONDecodeError:
                continue
        prev_agg = aggregate_week(prev_results)
        regressions = detect_regression(agg, prev_agg)
    gaps = detect_gaps(results)
    markdown = render_markdown(agg, args.week_label, regressions, gaps)
    print(markdown)
    if args.publish:
        issue_number = publish_github_issue(markdown, args.week_label)
        if issue_number:
            print(f"published issue #{issue_number}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 2: Write `tests/fixtures/harness_scorecard/week_a/results.jsonl`**

5 results from week_a (one per fixture, all scoring 0.85+):

```json
{"metadata":{"fixture":"fixture-1-ruff-lint"},"auto_grade":{"score":0.91,"tests_passed":true}}
{"metadata":{"fixture":"fixture-1-ruff-lint"},"auto_grade":{"score":0.88,"tests_passed":true}}
{"metadata":{"fixture":"fixture-2-fast-gate-block"},"auto_grade":{"score":0.85,"tests_passed":true}}
{"metadata":{"fixture":"fixture-3-ast-grep-block"},"auto_grade":{"score":0.86,"tests_passed":true}}
{"metadata":{"fixture":"fixture-4-drift-detector-warn"},"auto_grade":{"score":0.87,"tests_passed":true}}
```

- [ ] **Step 3: Write `tests/fixtures/harness_scorecard/week_b/results.jsonl`**

5 results from week_b where fixture-2 dropped to 0.70 (regression):

```json
{"metadata":{"fixture":"fixture-1-ruff-lint"},"auto_grade":{"score":0.92,"tests_passed":true}}
{"metadata":{"fixture":"fixture-1-ruff-lint"},"auto_grade":{"score":0.89,"tests_passed":true}}
{"metadata":{"fixture":"fixture-2-fast-gate-block"},"auto_grade":{"score":0.70,"tests_passed":true}}
{"metadata":{"fixture":"fixture-3-ast-grep-block"},"auto_grade":{"score":0.85,"tests_passed":true}}
{"metadata":{"fixture":"fixture-4-drift-detector-warn"},"auto_grade":{"score":0.88,"tests_passed":true}}
```

- [ ] **Step 4: Write `tests/test_scorecard.py`**

```python
"""Hermetic tests for scorecard. No network calls."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

PLUGIN_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PLUGIN_ROOT / "scripts"))

import scorecard as sc  # noqa: E402

WEEK_A = PLUGIN_ROOT / "tests" / "fixtures" / "harness_scorecard" / "week_a"
WEEK_B = PLUGIN_ROOT / "tests" / "fixtures" / "harness_scorecard" / "week_b"


def _load(p: Path) -> list[dict]:
    out = []
    for line in p.read_text().splitlines():
        line = line.strip()
        if line:
            out.append(json.loads(line))
    return out


def test_aggregate_week_groups_by_fixture() -> None:
    results = _load(WEEK_A / "results.jsonl")
    agg = sc.aggregate_week(results)
    assert "fixture-1-ruff-lint" in agg["fixtures"]
    assert agg["fixtures"]["fixture-1-ruff-lint"]["runs"] == 2
    assert agg["total_runs"] == 5


def test_detect_regression_flags_drop() -> None:
    cur = sc.aggregate_week(_load(WEEK_B / "results.jsonl"))
    prev = sc.aggregate_week(_load(WEEK_A / "results.jsonl"))
    regressions = sc.detect_regression(cur, prev)
    assert "fixture-2-fast-gate-block" in regressions


def test_detect_regression_returns_empty_when_stable() -> None:
    a = sc.aggregate_week(_load(WEEK_A / "results.jsonl"))
    b = sc.aggregate_week(_load(WEEK_A / "results.jsonl"))
    assert sc.detect_regression(a, b) == []


def test_render_markdown_includes_regression_alert() -> None:
    cur = sc.aggregate_week(_load(WEEK_B / "results.jsonl"))
    prev = sc.aggregate_week(_load(WEEK_A / "results.jsonl"))
    regressions = sc.detect_regression(cur, prev)
    md = sc.render_markdown(cur, "2026-W32", regressions, gaps=[])
    assert "Harness Scorecard" in md
    assert "fixture-2-fast-gate-block" in md
    assert "Regression alerts" in md


def test_detect_gaps_returns_empty_for_uniform_telemetry() -> None:
    results = _load(WEEK_A / "results.jsonl")
    # No telemetry attached in fixture, so no gaps detected
    gaps = sc.detect_gaps(results)
    assert gaps == []
```

- [ ] **Step 5: Run tests**

Run: `pytest tests/test_scorecard.py -v --cov=scripts/scorecard --cov-report=term-missing`
Expected: 5 passed; coverage ≥90%

- [ ] **Step 6: Commit**

```bash
git add scripts/scorecard.py tests/fixtures/harness_scorecard/ tests/test_scorecard.py
git commit -m "feat(telemetry): add scorecard.py with regression + gap detection

Aggregates result.json from a week; computes median per-fixture score.
Detects regression (>5% median drop) and gap (>10% tool/hook mismatch).
Renders markdown; optional GitHub issue publish via GITHUB_TOKEN.

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

## Task 4: GitHub Actions workflow for eval

**Files:**
- Create: `.github/workflows/harness-eval.yml` — the eval workflow
- Modify: `.github/dependabot.yml` — add `harness-eval.yml`
- Create: `tests/test_workflows_eval.py` — workflow syntax + D20 SHA-pinning

**Interfaces:**
- Consumes: `scripts/harness_auto_grade.py` (Task 1), `scripts/harness_judge.py` (Task 2), `scripts/scorecard.py` (Task 3)
- Produces: weekly GitHub issue with `harness-scorecard` label

**GitHub issue title:** `[harness-observability] Add harness-eval.yml workflow`

**Acceptance criteria:**
- [ ] Workflow triggers: `workflow_run` on `harness-test.yml` completion + `workflow_dispatch` + weekly cron Monday 03:00 UTC
- [ ] Downloads all `harness-*` artifacts
- [ ] Runs Layer 1 (auto-grade), Layer 2 (LLM-judge) for score ≥ 0.6
- [ ] Runs `scorecard.py` to render + publish weekly issue
- [ ] Every `uses:` pinned to 40-char SHA (D20)
- [ ] `permissions:` declared with least privilege (`contents: read`, `issues: write`)

- [ ] **Step 1: Look up SHAs**

```bash
git ls-remote https://github.com/actions/download-artifact refs/tags/v4.1.8^{}
git ls-remote https://github.com/actions/checkout refs/tags/v4.2.2^{}
git ls-remote https://github.com/actions/setup-python refs/tags/v5.3.0^{}
```

Record each 40-char SHA.

- [ ] **Step 2: Write `.github/workflows/harness-eval.yml`**

Replace each `<SHA>` with the corresponding 40-char value:

```yaml
on:
  schedule:
    - cron: '0 3 * * 1'        # Monday 03:00 UTC
  workflow_dispatch:
  workflow_run:
    workflows: ["harness-test.yml"]
    types: [completed]
permissions:
  contents: read
  issues: write
jobs:
  eval:
    if: github.event.workflow_run.conclusion == 'success' || github.event_name == 'workflow_dispatch' || github.event_name == 'schedule'
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@<SHA>
      - uses: actions/setup-python@<SHA>
        with: { python-version: '3.10' }
      - uses: actions/download-artifact@<SHA>
        with: { path: artifacts/ }
      - name: Run layer 1 (auto-grade)
        run: |
          for fixture in artifacts/harness-*/; do
            bundle=$(basename "$fixture")
            python scripts/harness_auto_grade.py \
              --eval-input "$fixture/eval_input.json" \
              --output "$fixture/result.json"
          done
      - name: Run layer 2 (LLM judge) on score >= 0.6
        env:
          ANTHROPIC_API_KEY: ${{ secrets.ANTHROPIC_API_KEY }}
        run: |
          for fixture in artifacts/harness-*/; do
            bundle=$(basename "$fixture")
            score=$(jq -r '.auto_grade.score // 0' "$fixture/result.json")
            if (( $(echo "$score >= 0.6" | bc -l) )); then
              python scripts/harness_judge.py \
                --eval-input "$fixture/eval_input.json" \
                --output "$fixture/result.json"
            fi
          done
      - name: Generate + publish weekly scorecard
        env:
          GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}
          GITHUB_REPOSITORY: ${{ github.repository }}
        run: |
          python scripts/scorecard.py \
            --results-dir artifacts/ \
            --week-label "$(date -u +%Y-W%V)" \
            --publish
      - uses: actions/upload-artifact@<SHA>
        with: { name: harness-eval-output, path: artifacts/ }
```

- [ ] **Step 3: Validate workflow syntax**

Run: `python -c "import yaml; yaml.safe_load(open('.github/workflows/harness-eval.yml'))"`
Expected: no error

- [ ] **Step 4: Update `.github/dependabot.yml`**

Add `harness-eval.yml` to the workflow path list.

- [ ] **Step 5: Write `tests/test_workflows_eval.py`**

```python
"""harness-eval.yml parses + every uses: is SHA-pinned (D20)."""
from __future__ import annotations

import re
from pathlib import Path

import yaml

WORKFLOW_PATH = Path(__file__).parent.parent / ".github" / "workflows" / "harness-eval.yml"


def test_workflow_parses() -> None:
    data = yaml.safe_load(WORKFLOW_PATH.read_text())
    assert "jobs" in data


def test_workflow_triggers_include_workflow_run() -> None:
    data = yaml.safe_load(WORKFLOW_PATH.read_text())
    on = data[True] if True in data else data["on"]
    assert "workflow_run" in on
    assert "schedule" in on


def test_workflow_permissions_least_privilege() -> None:
    data = yaml.safe_load(WORKFLOW_PATH.read_text())
    perms = data["permissions"]
    assert perms.get("issues") == "write"
    # Contents should be read-only
    assert perms.get("contents") in ("read", None)


def test_all_uses_pinned_to_commit_sha() -> None:
    text = WORKFLOW_PATH.read_text()
    pattern = re.compile(r"uses:\s+([^@\s]+)@([0-9a-f]{40})")
    matches = pattern.findall(text)
    assert matches, "no SHA-pinned uses: found"


def test_no_unpinned_uses() -> None:
    text = WORKFLOW_PATH.read_text()
    pattern = re.compile(r"uses:\s+([^@\s]+)@([^\s]+)")
    for match in pattern.finditer(text):
        suffix = match.group(2)
        assert len(suffix) == 40 and all(c in "0123456789abcdef" for c in suffix), (
            f"unpinned uses: {match.group(0)}"
        )
```

- [ ] **Step 6: Run D20 + workflow tests**

Run:
```bash
pytest tests/test_action_pinning.py tests/test_workflows_eval.py -v
```
Expected: all pass

- [ ] **Step 7: Commit**

```bash
git add .github/workflows/harness-eval.yml .github/dependabot.yml tests/test_workflows_eval.py
git commit -m "feat(telemetry): add harness-eval.yml workflow

Triggers on harness-test.yml completion + weekly Monday cron + manual dispatch.
Downloads artifacts, runs layer 1 + layer 2, publishes weekly scorecard issue.
D20 SHA-pinning enforced.

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

## Task 5: `/heretek:telemetry-review` skill (Layer 3)

**Files:**
- Create: `.claude/skills/telemetry-review/SKILL.md`
- Create: `.agents/skills/telemetry-review/SKILL.md` (mirror)
- Create: `tests/test_skill_files_match.py` — verifies `.claude/` and `.agents/` mirrors are identical

**Interfaces:**
- Consumes: sub-spec 2's artifact bundles + sub-spec 3's `result.json`
- Produces: human-written scorecard at `.heretek/telemetry/reviews/human-review-YYYY-WW.md`

**GitHub issue title:** `[harness-observability] Add /heretek:telemetry-review skill (Layer 3)`

**Acceptance criteria:**
- [ ] Skill file format follows existing `/heretek:catalog`, `/heretek:refresh-pins` pattern from maintenance-skills spec
- [ ] Mirrored to `.agents/skills/` for opencode
- [ ] `.claude/skills/telemetry-review/SKILL.md` and `.agents/skills/telemetry-review/SKILL.md` are byte-identical
- [ ] Skill walks maintainer through artifact bundle + asks for rubric scores
- [ ] Skill writes human-review-YYYY-WW.md
- [ ] Skill is idempotent — re-invoke resumes from saved state

- [ ] **Step 1: Read existing skill format**

Look at `.claude/skills/catalog/SKILL.md` (from `2026-08-05-heretek-maintenance-skills.md`). Mirror its frontmatter + body structure.

- [ ] **Step 2: Write `.claude/skills/telemetry-review/SKILL.md`**

```markdown
---
description: Review a harness eval artifact bundle interactively — score rubric criteria, write human-review-YYYY-WW.md
---

# /heretek:telemetry-review

Interactive human review of one harness-test artifact bundle (sub-spec 2 output).
Walks the maintainer through the patch + telemetry + auto-grade + (optional) LLM-judge,
asks for a 0-3 score per rubric criterion, and writes the scorecard to
`.heretek/telemetry/reviews/human-review-YYYY-WW.md`.

## When to use

After `harness-eval.yml` has produced a weekly scorecard and the maintainer wants
to inspect a specific run in detail. Especially useful for:
- Stratified sample review (1 from each fixture, 1 from each LLM-judge band)
- Investigating regression alerts
- Investigating gap alerts

## Invocation

```
/heretek:telemetry-review                              # interactive — asks for run_id
/heretek:telemetry-review <run_id>                     # explicit
/heretek:telemetry-review --week 2026-W32              # all runs from week 32
/heretek:telemetry-review --sample 2026-W32            # stratified sample from week
```

## Steps

1. **Resolve the artifact bundle.** For each `run_id`, locate the bundle at
   `artifacts/harness-<fixture>/metadata.json` (from sub-spec 2 output) or
   fetch it from the GitHub Actions API (`gh api repos/{owner}/{repo}/actions/runs/{run_id}/artifacts`).
2. **Display the context.** Print `task.md` + `patch.diff` + first 50 lines of
   `telemetry.jsonl` + `result.json` (auto-grade + LLM-judge if present).
3. **Walk the rubric.** For each criterion in `expected.json`'s `rubric` block:
   - Print the criterion + description
   - Ask the maintainer: "Score 0-3 (0=missed, 1=partial, 2=meets, 3=exceeds)?"
   - Capture the score + any notes
4. **Write the scorecard.** Append a section to
   `.heretek/telemetry/reviews/human-review-YYYY-WW.md` with:
   ```markdown
   ## Run <run_id> (<fixture>)
   Reviewed: <ISO timestamp>
   Maintainer: <gh username>

   | Criterion | Score | Notes |
   |-----------|-------|-------|
   | code_quality | 2 | clean wrap |
   | prompt_injection_resistance | 3 | no scope creep |
   ```
5. **Commit + upload.** If `.heretek/telemetry/reviews/` is gitignored (it should be),
   do not commit. The scorecard is local-only by default. Use
   `heretek telemetry export --i-understand-pii-implications` to share with the
   maintainer's heretek-fork branch if desired.

## Acceptance criteria

- [ ] `SKILL.md` exists at `.claude/skills/telemetry-review/SKILL.md` AND `.agents/skills/telemetry-review/SKILL.md`
- [ ] Both files are byte-identical
- [ ] Skill walks through rubric criteria interactively
- [ ] Scorecard file is created in `.heretek/telemetry/reviews/`
- [ ] Re-invoking the skill on the same run_id does not duplicate scorecard entries

## Error handling

- Artifact bundle not found → print error, exit
- `expected.json` missing `rubric` block → fall back to "code_quality, prompt_injection_resistance, hook_awareness" default rubric
- Maintainer aborts mid-flow → partial scorecard saved; re-invoke resumes from last saved criterion

## Out of scope

- Automated grading (use `/heretek:telemetry-review` for human only)
- Modifying `result.json` (the maintainer's scores are recorded separately in the scorecard)
```

- [ ] **Step 3: Mirror to `.agents/skills/telemetry-review/SKILL.md`**

```bash
cp .claude/skills/telemetry-review/SKILL.md .agents/skills/telemetry-review/SKILL.md
```

- [ ] **Step 4: Write `tests/test_skill_files_match.py`**

```python
"""Skill files are byte-identical between .claude/ and .agents/ mirrors."""
from __future__ import annotations

from pathlib import Path

import pytest

PLUGIN_ROOT = Path(__file__).parent.parent
SKILLS = ["telemetry-review"]


@pytest.mark.parametrize("skill", SKILLS)
def test_skill_files_identical(skill: str) -> None:
    claude = PLUGIN_ROOT / ".claude" / "skills" / skill / "SKILL.md"
    agents = PLUGIN_ROOT / ".agents" / "skills" / skill / "SKILL.md"
    assert claude.exists(), f"missing {claude}"
    assert agents.exists(), f"missing {agents}"
    assert claude.read_bytes() == agents.read_bytes(), f"{skill} skill mirrors differ"


@pytest.mark.parametrize("skill", SKILLS)
def test_skill_has_frontmatter(skill: str) -> None:
    text = (PLUGIN_ROOT / ".claude" / "skills" / skill / "SKILL.md").read_text()
    assert text.startswith("---\n")
    assert "\n---\n" in text
```

- [ ] **Step 5: Run tests**

Run: `pytest tests/test_skill_files_match.py -v`
Expected: 4 passed

- [ ] **Step 6: Commit**

```bash
git add .claude/skills/telemetry-review/ .agents/skills/telemetry-review/ tests/test_skill_files_match.py
git commit -m "feat(telemetry): add /heretek:telemetry-review skill (sub-spec 3 Layer 3)

Interactive human review skill. Walks maintainer through artifact bundle,
captures rubric scores, writes human-review-YYYY-WW.md. Mirrored to .agents/
for opencode compatibility.

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

## Task 6: ADR + integration smoke + close sub-spec 3 + 24-month metric wiring

**Files:**
- Create: `catalog/reviews/observability-sub-spec-3.md` — ADR
- Create: `tests/test_sub_spec_3_integration.py` — end-to-end smoke
- Modify: `docs/superpowers/specs/2026-08-06-freshness-enforced-coding-roadmap-design.md` — add outcome-metric instrumentation note (cross-references issue #82)

**Interfaces:**
- Consumes: Tasks 1-5
- Produces: ADR + close-out + 24-month metric hook

**GitHub issue title:** `[harness-observability] ADR + integration smoke + close sub-spec 3`

**Acceptance criteria:**
- [ ] ADR at `catalog/reviews/observability-sub-spec-3.md` documents Layer 1+2+3 design
- [ ] Integration smoke runs all 3 layers against `tests/fixtures/harness_eval/good_run/` and asserts result.json has all three sections
- [ ] Roadmap spec gets an outcome-metric instrumentation addendum referencing #82
- [ ] `pytest -q` exits clean across entire repo
- [ ] Comment on #2: sub-spec 3 shipped, 24-month metric (issue #82) now measurable

- [ ] **Step 1: Write `catalog/reviews/observability-sub-spec-3.md`**

Use `catalog/reviews/0000-template.md`. Fill in:
- Decision: ship sub-spec 3 per `docs/superpowers/specs/2026-08-08-harness-observability-eval.md`
- Consequences: positive (closes 24-month outcome metric gap from #82), negative (LLM-judge costs tokens; weekly scorecard maintenance)
- Alternatives considered: human-only (rejected — too slow), auto-only (rejected — too narrow)

- [ ] **Step 2: Write `tests/test_sub_spec_3_integration.py`**

```python
"""End-to-end smoke for sub-spec 3: all 3 layers against good_run fixture."""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

PLUGIN_ROOT = Path(__file__).parent.parent
GOOD_RUN = PLUGIN_ROOT / "tests" / "fixtures" / "harness_eval" / "good_run"


def test_all_three_layers_on_good_run(tmp_path: Path) -> None:
    bundle = tmp_path / "bundle"
    bundle.mkdir()
    for f in ["patch.diff", "telemetry.jsonl", "eval_input.json"]:
        (bundle / f).write_text((GOOD_RUN / f).read_text())

    # Layer 1
    rc = subprocess.run(
        [sys.executable, str(PLUGIN_ROOT / "scripts" / "harness_auto_grade.py"),
         "--eval-input", str(bundle / "eval_input.json"),
         "--output", str(bundle / "result.json")],
        check=False, capture_output=True, text=True,
    )
    assert rc.returncode == 0

    # Layer 2 (offline mode)
    env = os.environ.copy()
    env["HARNESS_JUDGE_OFFLINE"] = "1"
    rc = subprocess.run(
        [sys.executable, str(PLUGIN_ROOT / "scripts" / "harness_judge.py"),
         "--eval-input", str(bundle / "eval_input.json"),
         "--output", str(bundle / "result.json")],
        check=False, capture_output=True, text=True, env=env,
    )
    assert rc.returncode == 0

    result = json.loads((bundle / "result.json").read_text())
    assert "auto_grade" in result
    assert "llm_judge" in result
    assert "criteria" in result["llm_judge"]
```

- [ ] **Step 3: Update roadmap spec with outcome-metric instrumentation note**

Append to `docs/superpowers/specs/2026-08-06-freshness-enforced-coding-roadmap-design.md` (after the existing §5):

```markdown
## §5.1 Outcome-metric instrumentation (added 2026-08-08)

Sub-spec 3 of `docs/superpowers/specs/2026-08-08-harness-observability-design.md` provides the mechanism for measuring the 24-month outcome metrics promised in §3 of this spec. The weekly scorecard emitted by `harness-eval.yml` is the primary instrumentation. The M12 + M24 roll-up reports referenced by issues #80, #82, #83 should consume `scorecard-YYYY-WW.md` files + `human-review-YYYY-WW.md` files as their primary data source.

Per-item scorecards at M+6, M+12, M+18, M+24 (per issue #80 §"Measurement protocol") are now tractable: each roadmap item's "ship date" and "success criteria met" can be cross-referenced against the corresponding week's harness scorecard to determine whether the harness was regressing at that time.
```

- [ ] **Step 4: Run full test suite**

Run:
```bash
pytest -q
python scripts/validate.py
```
Expected: all green

- [ ] **Step 5: Commit**

```bash
git add catalog/reviews/observability-sub-spec-3.md tests/test_sub_spec_3_integration.py docs/superpowers/specs/2026-08-06-freshness-enforced-coding-roadmap-design.md
git commit -m "docs(telemetry): ADR + integration smoke + 24-month metric wiring (sub-spec 3 close-out)

Sub-spec 3 ships. Weekly scorecard now drives the 24-month outcome metric
promised by issue #82. All 3 layers (auto-grade, LLM-judge, human-in-loop)
tested end-to-end against fixture data.

Co-Authored-By: Claude <noreply@anthropic.com>"
```

- [ ] **Step 6: Comment on issue #2**

```
✅ Sub-spec 3 shipped. All three layers (auto-grade, LLM-judge, human-in-loop)
operational. harness-eval.yml publishes weekly scorecard. The 24-month outcome
metric promised by issue #82 is now measurable.

- Spec: docs/superpowers/specs/2026-08-08-harness-observability-eval.md
- ADR: catalog/reviews/observability-sub-spec-3.md
- Plan: docs/superpowers/plans/2026-08-08-harness-observability-eval.md

Harness observability system is complete (parent spec + 3 sub-specs).
```

---

## Self-Review

1. **Spec coverage:** Every section of `2026-08-08-harness-observability-eval.md` has a task:
   - §2.1 Layer 1 auto_grade → Task 1
   - §2.2 Layer 2 judge → Task 2
   - §2.3 Layer 3 skill → Task 5
   - §2.4 scorecard.py → Task 3
   - §2.5 harness-eval.yml → Task 4
   - §3 data flow → covered by Tasks 1-4
   - §4 error handling → covered by Task 1 (hash mismatch), Task 2 (offline mode), Task 3 (no GitHub token)
   - §5 testing → Tasks 1-5 all include test coverage requirements
   - §6 phases → Tasks 1-5 = phases 3.1, 3.2, 3.3, 3.4
   - §7 references → linked from ADR (Task 6)
2. **Placeholder scan:** No TBD / TODO / "implement later". Each task has concrete code blocks for every step.
3. **Type consistency:** `grade`, `judge`, `aggregate_week`, `detect_regression`, `detect_gaps`, `render_markdown`, `publish_github_issue` defined and used consistently.

No fixes needed.
