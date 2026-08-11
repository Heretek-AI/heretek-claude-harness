"""Render a comparison Markdown report from two agent result bundles.

Reads ${results_dir}/agent-a/summary.json and ${results_dir}/agent-b/summary.json,
computes a diff, renders a Markdown comparison, and writes it to --output.

Usage:
    python scripts/comparison_report.py \\
        --results-dir ./results \\
        --commit-sha $GITHUB_SHA \\
        --trigger push \\
        --actor $GITHUB_ACTOR \\
        --tier quick \\
        --model "$ANTHROPIC_MODEL" \\
        --base-url "$ANTHROPIC_BASE_URL" \\
        --output /tmp/comparison.md
"""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from pathlib import Path


@dataclass
class PerTaskResult:
    task_id: str
    verdict: str  # "pass" | "fail"
    wall_clock_sec: int
    tokens: int


@dataclass
class Summary:
    agent: str
    model: str
    commit_sha: str
    heretek_harness: bool
    n_tasks: int
    passed: int
    failed: int
    pass_rate: float
    wall_clock_sec_total: int
    wall_clock_sec_p50: int
    tokens_total: int
    per_task: list[PerTaskResult]


def load_summary(path: Path) -> Summary:
    """Load a summary.json file. Raises FileNotFoundError if missing."""
    if not path.exists():
        raise FileNotFoundError(f"summary not found: {path}")
    payload = json.loads(path.read_text())
    return Summary(
        agent=payload["agent"],
        model=payload["model"],
        commit_sha=payload["commit_sha"],
        heretek_harness=payload["heretek_harness"],
        n_tasks=payload["n_tasks"],
        passed=payload["passed"],
        failed=payload["failed"],
        pass_rate=payload["pass_rate"],
        wall_clock_sec_total=payload["wall_clock_sec_total"],
        wall_clock_sec_p50=payload["wall_clock_sec_p50"],
        tokens_total=payload["tokens_total"],
        per_task=[PerTaskResult(**t) for t in payload["per_task"]],
    )


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="comparison_report")
    parser.add_argument("--results-dir", type=Path, required=True)
    parser.add_argument("--commit-sha", required=True)
    parser.add_argument("--trigger", choices=["push", "workflow_dispatch"], required=True)
    parser.add_argument("--actor", required=True)
    parser.add_argument("--tier", choices=["quick", "full", "custom"], required=True)
    parser.add_argument("--model", required=True)
    parser.add_argument("--base-url", required=True)
    parser.add_argument("--output", type=Path, required=True)
    return parser


if __name__ == "__main__":
    # Surface the CLI surface for `python -m scripts.comparison_report --help`.
    build_arg_parser().parse_args()
