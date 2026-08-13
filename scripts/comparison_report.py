"""Render a comparison Markdown report from two agent result bundles.

Reads `${results_dir}/agent-a/summary.json` and `${results_dir}/agent-b/summary.json`,
computes metric diffs (pass rate delta, wall-clock delta, token delta),
scans output for secrets, and writes the Markdown comparison to `--output`.
"""

from __future__ import annotations

import argparse
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass
class PerTaskResult:
    """Per-task trial execution result."""

    task_id: str
    verdict: str  # "pass" | "fail"
    wall_clock_sec: int
    tokens: int


@dataclass
class Summary:
    """Summary metrics of an agent evaluation run."""

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
    """Load a summary.json file. Raises FileNotFoundError if missing.

    Args:
        path: Path to summary.json file.

    Returns:
        Summary dataclass instance.
    """
    if not path.exists():
        raise FileNotFoundError(f"summary not found: {path}")
    payload: dict[str, Any] = json.loads(path.read_text())
    return Summary(
        agent=str(payload["agent"]),
        model=str(payload["model"]),
        commit_sha=str(payload["commit_sha"]),
        heretek_harness=bool(payload["heretek_harness"]),
        n_tasks=int(payload["n_tasks"]),
        passed=int(payload["passed"]),
        failed=int(payload["failed"]),
        pass_rate=float(payload["pass_rate"]),
        wall_clock_sec_total=int(payload["wall_clock_sec_total"]),
        wall_clock_sec_p50=int(payload["wall_clock_sec_p50"]),
        tokens_total=int(payload["tokens_total"]),
        per_task=[
            PerTaskResult(
                task_id=str(t["task_id"]),
                verdict=str(t["verdict"]),
                wall_clock_sec=int(t["wall_clock_sec"]),
                tokens=int(t["tokens"]),
            )
            for t in payload["per_task"]
        ],
    )


def build_arg_parser() -> argparse.ArgumentParser:
    """Build argument parser for comparison_report CLI."""
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


def compute_diff(a: Summary, b: Summary) -> dict[str, Any]:
    """Compute the comparison diff between two agent summaries.

    Args:
        a: Summary for Agent A (with Heretek plugins).
        b: Summary for Agent B (baseline).

    Returns:
        Dict containing deltas, passed/failed lists, and task comparisons.
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


def _fmt_pct(x: float) -> str:
    """Format float as percentage string."""
    return f"{x * 100:.1f}%"


def _fmt_signed(value: float, suffix: str = "") -> str:
    """Format numeric value with signed string representation."""
    text = f"{abs(value):g}{suffix}"
    return text if value >= 0 else f"-{text}"


def _render_header(meta: dict[str, str], n_tasks: int) -> list[str]:
    """Render Markdown header section."""
    n = n_tasks
    return [
        f"# Terminal-Bench A/B — `{meta['commit_sha_short']}`",
        "",
        f"**Trigger:** `{meta['trigger']}`",
        f"**Actor:** {meta['actor']}",
        f"**Tier:** `{meta['tier']}` ({n} task{'s' if n != 1 else ''})",
        f"**Model:** `{meta['model']}` (via `{meta['base_url']}`)",
        "",
    ]


def _render_headline_rows(a: Summary, b: Summary) -> list[str]:
    """Render headline summary comparison table."""
    return [
        "## Headline",
        "",
        "| Agent | Pass rate | Passed | Failed | Wall-clock | Tokens |",
        "|---|---|---|---|---|---|",
        (
            f"| **A — with heretek** | {_fmt_pct(a.pass_rate)} | {a.passed}/{a.n_tasks} "
            f"| {a.failed}/{a.n_tasks} | {a.wall_clock_sec_total}s | {a.tokens_total:,} |"
        ),
        (
            f"| **B — baseline** | {_fmt_pct(b.pass_rate)} | {b.passed}/{b.n_tasks} "
            f"| {b.failed}/{b.n_tasks} | {b.wall_clock_sec_total}s | {b.tokens_total:,} |"
        ),
    ]


def _signed(value: float, suffix: str) -> str:
    """Format signed metric text with '+' prefix on non-negative values."""
    text = _fmt_signed(value, suffix)
    return f"+{text}" if not text.startswith("-") else text


def _render_delta_row(diff: dict[str, Any]) -> list[str]:
    """Render delta row summarizing performance gains/losses."""
    return [
        (
            f"| **Δ** | **{_signed(float(diff['delta_pass_rate']) * 100, '%')}** "
            f"| **{_signed(float(diff['delta_passed']), '')}** "
            f"| — | **{_signed(float(diff['wall_clock_delta_sec']), 's')}** "
            f"| **{_signed(float(diff['tokens_delta']), '')}** |"
        ),
    ]


def _format_task_cell(task: PerTaskResult | None) -> str:
    """Format single task outcome cell."""
    if task is None:
        return "—"
    mark = "✓" if task.verdict == "pass" else "✗"
    return f"{mark} ({task.wall_clock_sec}s)"


def _note_for(a_pass: bool, b_pass: bool) -> str:
    """Return outcome comparison label for task."""
    if a_pass and b_pass:
        return "both"
    if a_pass:
        return "A wins"
    if b_pass:
        return "B wins"
    return "both fail"


def _render_per_task_table(a: Summary, b: Summary) -> list[str]:
    """Render per-task outcome matrix table."""
    a_by_id = {t.task_id: t for t in a.per_task}
    b_by_id = {t.task_id: t for t in b.per_task}
    all_ids = sorted(set(a_by_id) | set(b_by_id))
    out = [
        "## Per-task",
        "",
        "| Task | A | B | Notes |",
        "|---|---|---|---|",
    ]
    for tid in all_ids:
        a_task = a_by_id.get(tid)
        b_task = b_by_id.get(tid)
        a_pass = a_task is not None and a_task.verdict == "pass"
        b_pass = b_task is not None and b_task.verdict == "pass"
        out.append(
            f"| {tid} | {_format_task_cell(a_task)} "
            f"| {_format_task_cell(b_task)} | {_note_for(a_pass, b_pass)} |"
        )
    return out


def _render_list_section(title: str, items: list[str], verb: str) -> list[str]:
    """Render list section for helped/hurt breakdown."""
    out = [title, ""]
    if items:
        for tid in items:
            out.append(f"- `{tid}` ({verb})")
    else:
        out.append("(none)")
    out.append("")
    return out


def render_markdown(
    a: Summary,
    b: Summary,
    diff: dict[str, Any],
    meta: dict[str, str],
) -> str:
    """Render the comparison Markdown body for GitHub issue reports."""
    lines: list[str] = []
    lines.extend(_render_header(meta, a.n_tasks))
    lines.extend(_render_headline_rows(a, b))
    lines.extend(_render_delta_row(diff))
    lines.append("")
    lines.extend(_render_per_task_table(a, b))
    lines.append("")
    lines.extend(
        _render_list_section(
            "## Tasks where heretek helped",
            diff["tasks_agent_a_passed_b_failed"],
            "A pass, B fail",
        )
    )
    lines.extend(
        _render_list_section(
            "## Tasks where heretek hurt",
            diff["tasks_agent_b_passed_a_failed"],
            "A fail, B pass",
        )
    )
    return "\n".join(lines)


_SECRET_PATTERNS = (
    re.compile(r"sk-[A-Za-z0-9_-]{20,}"),
    re.compile(r"sk-cp-[A-Za-z0-9_-]{20,}"),
    re.compile(r"ghp_[A-Za-z0-9]{20,}"),
    re.compile(r"gho_[A-Za-z0-9]{20,}"),
    re.compile(r"xox[abprs]-[A-Za-z0-9-]{10,}"),
)


def scan_for_secrets(markdown: str) -> list[str]:
    """Return list of token-shaped strings found in markdown."""
    hits: list[str] = []
    for pattern in _SECRET_PATTERNS:
        hits.extend(pattern.findall(markdown))
    return hits


def render_with_secret_check(markdown: str) -> str:
    """Raise RuntimeError if markdown contains secret-shaped token strings.

    Args:
        markdown: Rendered markdown string to check.

    Returns:
        Unmodified markdown string if clean.

    Raises:
        RuntimeError: If secrets are detected in markdown output.
    """
    hits = scan_for_secrets(markdown)
    if hits:
        redacted = [h[:6] + "..." + h[-4:] for h in hits]
        raise RuntimeError(
            f"refusing to write issue body — {len(hits)} secret-shaped "
            f"string(s) detected: {redacted}"
        )
    return markdown


def main(argv: list[str] | None = None) -> int:
    """CLI entrypoint for comparison_report."""
    args = build_arg_parser().parse_args(argv)
    a = load_summary(args.results_dir / "agent-a" / "summary.json")
    b = load_summary(args.results_dir / "agent-b" / "summary.json")
    diff = compute_diff(a, b)
    md = render_markdown(
        a,
        b,
        diff,
        {
            "commit_sha_short": args.commit_sha[:7],
            "trigger": args.trigger,
            "actor": args.actor,
            "tier": args.tier,
            "model": args.model,
            "base_url": args.base_url,
        },
    )
    render_with_secret_check(md)
    args.output.write_text(md)
    return 0


if __name__ == "__main__":
    import sys

    sys.exit(main())
