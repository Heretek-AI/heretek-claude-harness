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


def compute_diff(a: Summary, b: Summary) -> dict:
    """Compute the comparison diff between two agent summaries.

    Returns a dict matching the spec's diff.json schema (spec §4).
    Positive deltas mean agent A (heretek) did better.
    """
    a_pass = {t.task_id for t in a.per_task if t.verdict == "pass"}
    b_pass = {t.task_id for t in b.per_task if t.verdict == "pass"}
    a_all = {t.task_id for t in a.per_task}
    b_all = {t.task_id for t in b.per_task}
    return {
        "commit_sha": a.commit_sha,
        "delta_pass_rate": a.pass_rate - b.pass_rate,
        "delta_passed": a.passed - b.passed,
        "tasks_agent_a_passed_b_failed": sorted(a_pass - b_pass),
        "tasks_agent_b_passed_a_failed": sorted(b_pass - a_pass),
        "tasks_both_passed": sorted(a_pass & b_pass),
        "tasks_both_failed": sorted((a_all & b_all) - (a_pass | b_pass)),
        "wall_clock_delta_sec": a.wall_clock_sec_total - b.wall_clock_sec_total,
        "tokens_delta": a.tokens_total - b.tokens_total,
    }


if __name__ == "__main__":
    # Surface the CLI surface for `python -m scripts.comparison_report --help`.
    build_arg_parser().parse_args()
