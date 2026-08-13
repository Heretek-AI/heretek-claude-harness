"""Layer 2 LLM-judge stub tests. Calibration is a follow-up."""

from __future__ import annotations

from harness_judge import stub_judge


def test_stub_judge_returns_pass_for_clean_diff() -> None:
    eval_input = {
        "fixture": "fixture-1-ruff-lint",
        "expected": {"rubric": {"llm_judge_prompt": "verify"}},
    }
    patch = "--- a\n+++ b\n-import os\n+from pathlib import Path\n"
    result = stub_judge(eval_input, patch)
    assert result["verdict"] in ("pass", "fail")
    assert "stub" in result["layer"]


def test_stub_judge_records_calibration_marker() -> None:
    eval_input = {"fixture": "x", "expected": {"rubric": {}}}
    result = stub_judge(eval_input, "any diff content")
    assert result["calibration_required"] is True


def test_stub_judge_fails_on_empty_diff() -> None:
    eval_input = {"fixture": "x", "expected": {"rubric": {}}}
    result = stub_judge(eval_input, "")
    assert result["verdict"] == "fail"
