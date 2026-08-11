"""Scorecard generator + regression detector tests."""

from __future__ import annotations

import json
from pathlib import Path

from scorecard import detect_regressions, generate_scorecard


def test_generate_scorecard_with_one_week(tmp_path: Path) -> None:
    bundles = tmp_path / "bundles"
    bundles.mkdir()
    for fixture in ("fixture-1", "fixture-2"):
        b = bundles / f"harness-{fixture}"
        b.mkdir()
        (b / "result.json").write_text(
            json.dumps(
                {
                    "fixture": fixture,
                    "verdict": "pass",
                    "checks": {},
                }
            )
        )
    scorecard = generate_scorecard(bundles, week=(2026, 32))
    assert "# Harness Scorecard" in scorecard
    assert "fixture-1" in scorecard
    assert "fixture-2" in scorecard


def test_generate_scorecard_handles_missing_results(tmp_path: Path) -> None:
    bundles = tmp_path / "bundles"
    bundles.mkdir()
    scorecard = generate_scorecard(bundles, week=(2026, 32))
    assert "No result.json" in scorecard


def test_detect_regressions_finds_drop() -> None:
    prev = {"fixture-1": 0.95, "fixture-2": 0.90}
    curr = {"fixture-1": 0.85, "fixture-2": 0.92}
    regressions = detect_regressions(prev, curr, threshold=0.05)
    assert "fixture-1" in regressions
    assert "fixture-2" not in regressions


def test_detect_regressions_no_drop() -> None:
    prev = {"fixture-1": 0.95, "fixture-2": 0.90}
    curr = {"fixture-1": 0.93, "fixture-2": 0.91}
    assert detect_regressions(prev, curr, threshold=0.05) == []
