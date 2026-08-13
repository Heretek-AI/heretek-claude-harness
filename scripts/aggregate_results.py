"""Aggregate Harbor per-trial result.json files into a summary.json.

Walks `<jobs-dir>/<job-name>/<trial-name>/result.json` for each trial in
the most recent job directory, extracts verdict, tokens, and wall-clock time
from Harbor's TrialResult schema, and writes a single `summary.json` matching
the `Summary` schema consumed by `scripts/comparison_report.py`.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path
from statistics import median
from typing import Any, cast


def _log(msg: str) -> None:
    """Write a warning to stderr without breaking JSON output."""
    print(f"aggregate_results: {msg}", file=sys.stderr)


def _parse_iso(s: str | None) -> datetime | None:
    """Parse an ISO 8601 timestamp string; return None on any failure."""
    if not s:
        return None
    try:
        return datetime.fromisoformat(s.replace("Z", "+00:00"))
    except ValueError:
        return None


def _extract_trial(result_path: Path) -> dict[str, Any] | None:
    """Extract per-trial fields from a Harbor TrialResult result.json file.

    Args:
        result_path: Path to trial's result.json file.

    Returns:
        Dict with keys (task_id, verdict, wall_clock_sec, tokens), or None if skipped.
    """
    try:
        raw: Any = json.loads(result_path.read_text())
    except (OSError, json.JSONDecodeError) as e:
        _log(f"trial {result_path.parent.name}: malformed JSON ({e}), skipping")
        return None

    if not isinstance(raw, dict):
        return None

    trial = cast("dict[str, Any]", raw)
    task_name = trial.get("task_name")
    if not isinstance(task_name, str) or not task_name:
        _log(f"trial {result_path.parent.name}: no task_name, skipping")
        return None

    verifier_raw = trial.get("verifier_result")
    verifier = cast("dict[str, Any]", verifier_raw) if isinstance(verifier_raw, dict) else {}
    rewards_raw = verifier.get("rewards")
    rewards = cast("dict[str, Any]", rewards_raw) if isinstance(rewards_raw, dict) else {}
    if not rewards:
        _log(f"trial {task_name}: no verifier_result.rewards, skipping")
        return None

    verdict = "pass" if any(rewards.get(k) == 1.0 for k in rewards) else "fail"

    agent_result = trial.get("agent_result")
    ctx = cast("dict[str, Any]", agent_result) if isinstance(agent_result, dict) else {}
    n_input = ctx.get("n_input_tokens", 0) if ctx else 0
    n_output = ctx.get("n_output_tokens", 0) if ctx else 0

    tokens = (int(n_input) if isinstance(n_input, (int, float)) else 0) + (
        int(n_output) if isinstance(n_output, (int, float)) else 0
    )

    started_str = trial.get("started_at")
    finished_str = trial.get("finished_at")
    started = _parse_iso(str(started_str)) if isinstance(started_str, str) else None
    finished = _parse_iso(str(finished_str)) if isinstance(finished_str, str) else None
    if ctx and started and finished:
        wall_clock_sec = max(0, int((finished - started).total_seconds()))
    else:
        wall_clock_sec = 0

    return {
        "task_id": task_name,
        "verdict": verdict,
        "wall_clock_sec": wall_clock_sec,
        "tokens": tokens,
    }


def _latest_job_dir(jobs_dir: Path) -> Path | None:
    """Pick the most recently modified subdirectory of jobs_dir."""
    subdirs = [p for p in jobs_dir.iterdir() if p.is_dir()]
    if not subdirs:
        return None
    return max(subdirs, key=lambda p: p.stat().st_mtime)


def aggregate_jobs_dir(
    jobs_dir: Path,
    *,
    agent_label: str,
    model: str,
    commit_sha: str,
) -> dict[str, Any]:
    """Aggregate Harbor per-trial result.json files into a summary dictionary.

    Args:
        jobs_dir: Path to directory containing Harbor job outputs.
        agent_label: Human-readable label for agent (e.g. 'agent-a-with-heretek').
        model: Model name string.
        commit_sha: Commit SHA string.

    Returns:
        Summary dict containing overall metrics and per-task results.
    """
    per_task: list[dict[str, Any]] = []

    if jobs_dir.is_dir():
        job_dir = _latest_job_dir(jobs_dir)
        if job_dir is not None:
            for trial_dir in sorted(job_dir.iterdir()):
                if not trial_dir.is_dir():
                    continue
                result_path = trial_dir / "result.json"
                if not result_path.is_file():
                    continue
                record = _extract_trial(result_path)
                if record is not None:
                    per_task.append(record)

    n_tasks = len(per_task)
    passed = sum(1 for t in per_task if t["verdict"] == "pass")
    failed = n_tasks - passed
    pass_rate = passed / n_tasks if n_tasks else 0.0
    wall_clocks: list[int] = [int(t["wall_clock_sec"]) for t in per_task]

    return {
        "agent": agent_label,
        "model": model,
        "commit_sha": commit_sha,
        "heretek_harness": agent_label.endswith("with-heretek"),
        "n_tasks": n_tasks,
        "passed": passed,
        "failed": failed,
        "pass_rate": pass_rate,
        "wall_clock_sec_total": sum(wall_clocks),
        "wall_clock_sec_p50": int(median(wall_clocks)) if wall_clocks else 0,
        "tokens_total": sum(int(t["tokens"]) for t in per_task),
        "per_task": per_task,
    }


def build_arg_parser() -> argparse.ArgumentParser:
    """Build argument parser for aggregate_results CLI."""
    parser = argparse.ArgumentParser(prog="aggregate_results")
    parser.add_argument("--jobs-dir", type=Path, required=True)
    parser.add_argument("--agent-label", required=True)
    parser.add_argument("--model", required=True)
    parser.add_argument("--commit-sha", required=True)
    parser.add_argument("--output", type=Path, required=True)
    return parser


def main(argv: list[str] | None = None) -> int:
    """CLI entrypoint for aggregate_results."""
    args = build_arg_parser().parse_args(argv)
    summary = aggregate_jobs_dir(
        args.jobs_dir,
        agent_label=args.agent_label,
        model=args.model,
        commit_sha=args.commit_sha,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(summary, indent=2) + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
