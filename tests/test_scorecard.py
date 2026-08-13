"""Unit tests for scorecard generator and readiness audit."""

from __future__ import annotations

from pathlib import Path

from scripts.scorecard import (
    calculate_readiness_score,
    compute_score_delta,
    generate_score_badge_svg,
)


def test_calculate_readiness_score_clean_repo(tmp_path: Path) -> None:
    """Readiness score calculates 4 pillars accurately."""
    (tmp_path / "AGENTS.md").write_text("# Agents")
    (tmp_path / "CLAUDE.md").write_text("# Claude")
    (tmp_path / ".pre-commit-config.yaml").write_text("repos: []")
    claude_dir = tmp_path / ".claude"
    claude_dir.mkdir()
    (claude_dir / "hooks.json").write_text("{}")

    res = calculate_readiness_score(tmp_path)
    assert res["score"] == 75
    assert res["hooks_active"] is True
    assert res["precommit_active"] is True


def test_compute_score_delta() -> None:
    """Score delta correctly reflects improvement."""
    assert compute_score_delta(50, 75) == 25
    assert compute_score_delta(100, 75) == -25


def test_generate_score_badge_svg() -> None:
    """Badge SVG contains score string and valid XML tag structure."""
    svg = generate_score_badge_svg(85)
    assert "<svg" in svg
    assert "85/100" in svg
    assert "#4c1" in svg
