"""Deterministic AI-Harness Maturity Audit & Readiness Scorecard.

Calculates the 4-Pillar Agentic Readiness Score (0-100 pts), computes PR score
deltas (+Δ%), and generates SVG status badges (harness-score.svg).
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


def calculate_readiness_score(target_dir: Path) -> dict[str, Any]:
    """Calculate the 4-Pillar Agentic Readiness Score (0-100 pts) for a repository.

    Args:
        target_dir: Absolute path to target repository root directory.

    Returns:
        Dict containing total score, pillar breakdowns, and deployed assets.
    """
    target = target_dir.resolve()
    claude_dir = target / ".claude"
    plugins_dir = claude_dir / "plugins"
    hooks_file = claude_dir / "hooks.json"
    precommit_file = target / ".pre-commit-config.yaml"

    installed_plugins: list[str] = []
    if plugins_dir.is_dir():
        installed_plugins = [d.name for d in plugins_dir.iterdir() if d.is_dir()]

    p1_score = 25 if (hooks_file.is_file() or (target / "hooks.json").is_file()) else 0
    p2_score = 25 if precommit_file.is_file() else 0
    context_files = [f for f in ("AGENTS.md", "CLAUDE.md", "README.md") if (target / f).is_file()]
    p3_score = 25 if len(context_files) >= 2 else (12 if len(context_files) == 1 else 0)
    p4_score = 25 if (
        "best-practices" in installed_plugins
        or "quality-audit" in installed_plugins
        or (target / "skills").is_dir()
        or (target / ".claude" / "skills").is_dir()
    ) else 0

    total_score = p1_score + p2_score + p3_score + p4_score

    return {
        "score": total_score,
        "pillars": {
            "p1_quality_gates": p1_score,
            "p2_precommit_guard": p2_score,
            "p3_context_density": p3_score,
            "p4_quality_packs": p4_score,
        },
        "context_files": context_files,
        "installed_plugins": installed_plugins,
        "hooks_active": p1_score > 0,
        "precommit_active": p2_score > 0,
    }


def compute_score_delta(prev_score: int, curr_score: int) -> int:
    """Compute score improvement delta between baseline and current commit."""
    return curr_score - prev_score


def generate_score_badge_svg(score: int) -> str:
    """Generate SVG badge string for harness score.

    Args:
        score: Score integer (0-100).

    Returns:
        SVG XML string representation of badge.
    """
    color = "#4c1" if score >= 80 else ("#dfb317" if score >= 50 else "#e05d44")
    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="135" height="20" role="img" aria-label="harness score: {score}/100">
  <linearGradient id="s" x2="0" y2="100%">
    <stop offset="0" stop-color="#bbb" stop-opacity=".1"/>
    <stop offset="1" stop-opacity=".1"/>
  </linearGradient>
  <clipPath id="r">
    <rect width="135" height="20" rx="3" fill="#fff"/>
  </clipPath>
  <g clip-path="url(#r)">
    <rect width="90" height="20" fill="#555"/>
    <rect x="90" width="45" height="20" fill="{color}"/>
    <rect width="135" height="20" fill="url(#s)"/>
  </g>
  <g fill="#fff" text-anchor="middle" font-family="Verdana,Geneva,DejaVu Sans,sans-serif" text-rendering="geometricPrecision" font-size="110">
    <text x="460" y="140" transform="scale(.1)" fill="#fff" textLength="800">harness score</text>
    <text x="1115" y="140" transform="scale(.1)" fill="#fff" textLength="350">{score}/100</text>
  </g>
</svg>"""  # noqa: E501


def build_arg_parser() -> argparse.ArgumentParser:
    """Build argument parser for scorecard CLI."""
    parser = argparse.ArgumentParser(prog="scorecard")
    parser.add_argument("--target", type=Path, default=Path("."))
    parser.add_argument("--prev-score", type=int, default=None)
    parser.add_argument("--badge-out", type=Path, default=None)
    parser.add_argument("--json-out", type=Path, default=None)
    return parser


def main(argv: list[str] | None = None) -> int:
    """CLI entrypoint for scorecard generator."""
    args = build_arg_parser().parse_args(argv)
    res = calculate_readiness_score(args.target)
    score = int(res["score"])

    delta_str = ""
    if args.prev_score is not None:
        delta = compute_score_delta(args.prev_score, score)
        delta_str = f" (Δ {delta:+d})"

    print(f"Harness Readiness Score: {score}/100 pts{delta_str}")

    if args.badge_out:
        args.badge_out.parent.mkdir(parents=True, exist_ok=True)
        args.badge_out.write_text(generate_score_badge_svg(score))

    if args.json_out:
        args.json_out.parent.mkdir(parents=True, exist_ok=True)
        args.json_out.write_text(json.dumps(res, indent=2) + "\n")

    return 0


if __name__ == "__main__":
    sys.exit(main())
