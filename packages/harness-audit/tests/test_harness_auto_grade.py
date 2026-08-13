"""Layer 1 auto-grade tests against recorded eval_input fixtures."""

from __future__ import annotations

import pytest
from harness_auto_grade import auto_grade, compute_sha256


def test_auto_grade_passes_when_diff_under_max() -> None:
    eval_input = {
        "fixture": "fixture-1-ruff-lint",
        "expected": {
            "auto_grade": {"patch_diff_max_bytes": 200, "files_changed_required": ["src/app.py"]}
        },
    }
    patch = (
        "--- a/src/app.py\n+++ b/src/app.py\n@@ -1,4 +1,4 @@\n-import os\n+from pathlib import Path\n"  # noqa: E501
    )
    result = auto_grade(eval_input, patch_diff=patch)
    assert result["verdict"] == "pass"
    assert "patch_diff_bytes" in result["checks"]


def test_auto_grade_fails_when_diff_too_large() -> None:
    eval_input = {
        "fixture": "fixture-1-ruff-lint",
        "expected": {"auto_grade": {"patch_diff_max_bytes": 10}},
    }
    patch = "x" * 100
    result = auto_grade(eval_input, patch_diff=patch)
    assert result["verdict"] == "fail"


def test_auto_grade_fails_when_required_file_missing() -> None:
    eval_input = {
        "fixture": "fixture-1-ruff-lint",
        "expected": {"auto_grade": {"files_changed_required": ["src/app.py"]}},
    }
    patch = "--- a/src/other.py\n+++ b/src/other.py\n@@ -1,1 +1,1 @@\n-x\n+y\n"
    result = auto_grade(eval_input, patch_diff=patch)
    assert result["verdict"] == "fail"
    assert "src/app.py" in result["checks"]["files_changed_missing"]


def test_auto_grade_refuses_mismatched_sha() -> None:
    eval_input = {"fixture": "x", "expected": {"auto_grade": {}}}
    patch = "actual diff content"
    actual_sha = compute_sha256(patch)
    with pytest.raises(ValueError, match="sha256 mismatch"):
        auto_grade(
            eval_input,
            patch_diff=patch,
            expected_sha="0000000000000000000000000000000000000000000000000000000000000000",
        )
    assert actual_sha != "0000000000000000000000000000000000000000000000000000000000000000"
