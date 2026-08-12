"""Aggregate harbor per-trial result.json files into a summary.json.

Walks <jobs-dir>/<job-name>/<trial-name>/result.json for each trial in
the most recent job directory, extracts verdict + tokens + wall_clock
from harbor's TrialResult schema, and writes a single summary.json
matching scripts.comparison_report.Summary.

Usage:
    python scripts/aggregate_results.py \\
        --jobs-dir ./results/agent-a/jobs \\
        --agent-label agent-a-with-heretek \\
        --model "$ANTHROPIC_MODEL" \\
        --commit-sha "$GITHUB_SHA" \\
        --output ./results/agent-a/summary.json

Token counting policy: tokens = agent_result.n_input_tokens +
agent_result.n_output_tokens. The n_input_tokens field already includes
cache reads per harbor's docstring; matches harbor's own cost_usd basis.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path
from statistics import median


def _log(msg: str) -> None:
    """Write a warning to stderr without breaking JSON output."""
    print(f"aggregate_results: {msg}", file=sys.stderr)


def _parse_iso(s: str | None) -> datetime | None:
    """Parse an ISO 8601 timestamp; return None on any failure."""
    if not s:
        return None
    try:
        # harbor writes 'Z' suffix; normalize for fromisoformat.
        return datetime.fromisoformat(s.replace("Z", "+00:00"))
    except ValueError:
        return None


def _extract_trial(result_path: Path) -> dict | None:
    """Extract per-trial fields from a harbor TrialResult result.json.

    Returns a dict with keys: task_id, verdict, wall_clock_sec, tokens.
    Returns None if the trial should be skipped (missing rewards, malformed JSON).
    """
    try:
        trial = json.loads(result_path.read_text())
    except (OSError, json.JSONDecodeError) as e:
        _log(f"trial {result_path.parent.name}: malformed JSON ({e}), skipping")
        return None

    task_name = trial.get("task_name")
    if not task_name:
        _log(f"trial {result_path.parent.name}: no task_name, skipping")
        return None

    rewards = (trial.get("verifier_result") or {}).get("rewards") or {}
    if not rewards:
        _log(f"trial {task_name}: no verifier_result.rewards, skipping")
        return None

    verdict = "pass" if any(v == 1.0 for v in rewards.values()) else "fail"

    ctx = trial.get("agent_result") or {}
    tokens = (ctx.get("n_input_tokens") or 0) + (ctx.get("n_output_tokens") or 0)

    # Wall-clock is only meaningful when an agent actually executed; gate it
    # on agent_result being present so trials without agent metadata don't
    # contribute phantom runtime.
    if ctx:
        started = _parse_iso(trial.get("started_at"))
        finished = _parse_iso(trial.get("finished_at"))
        if started and finished:
            wall_clock_sec = max(0, int((finished - started).total_seconds()))
        else:
            wall_clock_sec = 0
    else:
        wall_clock_sec = 0

    return {
        "task_id": task_name,
        "verdict": verdict,
        "wall_clock_sec": wall_clock_sec,
        "tokens": tokens,
    }


def _latest_job_dir(jobs_dir: Path) -> Path | None:
    """Pick the most recently modified subdir of jobs_dir (harbor resume support)."""
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
) -> dict:
    """Aggregate harbor's per-trial result.json into a Summary dict.

    Returns a dict matching the Summary dataclass in
    scripts.comparison_report (load_summary can read it back).
    """
    per_task: list[dict] = []

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
    wall_clocks = [t["wall_clock_sec"] for t in per_task]

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
        "tokens_total": sum(t["tokens"] for t in per_task),
        "per_task": per_task,
    }


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="aggregate_results")
    parser.add_argument("--jobs-dir", type=Path, required=True)
    parser.add_argument("--agent-label", required=True)
    parser.add_argument("--model", required=True)
    parser.add_argument("--commit-sha", required=True)
    parser.add_argument("--output", type=Path, required=True)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_arg_parser().parse_args(argv)
    summary = aggregate_jobs_dir(
        args.jobs_dir,
        agent_label=args.agent_label,
        model=args.model,
        commit_sha=args.commit_sha,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
