"""Validates that all 5 curated fixtures have the required 4-file layout
and that expected.json parses cleanly.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

FIXTURES_DIR = Path(__file__).parent / "fixtures" / "harness"
CURATED = [
    "fixture-1-ruff-lint",
    "fixture-2-pytest-coverage",
    "fixture-3-precommit-config",
    "fixture-4-catalog-yaml",
    "fixture-5-hooks-dispatch",
]


@pytest.mark.parametrize("fixture_name", CURATED)
def test_fixture_has_required_files(fixture_name: str) -> None:
    fixture = FIXTURES_DIR / fixture_name
    for f in ("task.md", "setup.sh", "expected.json", "ground-truth.patch"):
        assert (fixture / f).exists(), f"missing {f} in {fixture_name}"
    mode = (fixture / "setup.sh").stat().st_mode
    assert mode & 0o111, f"setup.sh not executable in {fixture_name} (mode={oct(mode)})"


@pytest.mark.parametrize("fixture_name", CURATED)
def test_expected_json_valid(fixture_name: str) -> None:
    expected = json.loads((FIXTURES_DIR / fixture_name / "expected.json").read_text())
    assert "auto_grade" in expected, f"{fixture_name}: missing auto_grade"
    assert "rubric" in expected, f"{fixture_name}: missing rubric"
    assert (
        "llm_judge_prompt" in expected["rubric"]
    ), f"{fixture_name}: missing llm_judge_prompt in rubric"
    assert (
        "metadata_keys_required" in expected["auto_grade"]
    ), f"{fixture_name}: missing metadata_keys_required"


@pytest.mark.parametrize("fixture_name", CURATED)
def test_ground_truth_patch_nonempty(fixture_name: str) -> None:
    patch = (FIXTURES_DIR / fixture_name / "ground-truth.patch").read_text()
    assert patch.strip(), f"{fixture_name}: empty ground-truth.patch"
    assert "+++ b/" in patch, f"{fixture_name}: ground-truth.patch lacks target file"
