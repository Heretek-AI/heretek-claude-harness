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
import re
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


def _fmt_pct(x: float) -> str:
    return f"{x * 100:.1f}%"


def _fmt_signed(value: float, suffix: str = "") -> str:
    text = f"{abs(value):g}{suffix}"
    return text if value >= 0 else f"-{text}"


def _render_header(meta: dict, n_tasks: int) -> list[str]:
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
    text = _fmt_signed(value, suffix)
    return f"+{text}" if not text.startswith("-") else text


def _render_delta_row(diff: dict) -> list[str]:
    return [
        (
            f"| **Δ** | **{_signed(diff['delta_pass_rate'] * 100, '%')}** "
            f"| **{_signed(diff['delta_passed'], '')}** "
            f"| — | **{_signed(diff['wall_clock_delta_sec'], 's')}** "
            f"| **{_signed(diff['tokens_delta'], '')}** |"
        ),
    ]


def _format_task_cell(task: PerTaskResult | None) -> str:
    if task is None:
        return "—"
    mark = "✓" if task.verdict == "pass" else "✗"
    return f"{mark} ({task.wall_clock_sec}s)"


def _note_for(a_pass: bool, b_pass: bool) -> str:
    if a_pass and b_pass:
        return "both"
    if a_pass:
        return "A wins"
    if b_pass:
        return "B wins"
    return "both fail"


def _render_per_task_table(a: Summary, b: Summary) -> list[str]:
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


def _render_list_section(title: str, items: list, verb: str) -> list[str]:
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
    diff: dict,
    meta: dict,
) -> str:
    """Render the comparison Markdown body for the GitHub issue."""
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
    re.compile(r"sk-[A-Za-z0-9_-]{20,}"),  # sk-... (Anthropic-style)
    re.compile(r"sk-cp-[A-Za-z0-9_-]{20,}"),  # sk-cp-... (MiniMax-style)
    re.compile(r"ghp_[A-Za-z0-9]{20,}"),  # GitHub PAT
    re.compile(r"gho_[A-Za-z0-9]{20,}"),  # GitHub OAuth
    re.compile(r"xox[abprs]-[A-Za-z0-9-]{10,}"),  # Slack
)


def scan_for_secrets(markdown: str) -> list[str]:
    """Return list of token-shaped strings found in `markdown`."""
    hits: list[str] = []
    for pattern in _SECRET_PATTERNS:
        hits.extend(pattern.findall(markdown))
    return hits


def render_with_secret_check(markdown: str) -> str:
    """Raise RuntimeError if `markdown` contains token-shaped strings.

    Called by the main() flow after render_markdown. The wrapper passes
    Markdown through unchanged; the only behavior is the abort.
    """
    hits = scan_for_secrets(markdown)
    if hits:
        redacted = [h[:6] + "..." + h[-4:] for h in hits]
        raise RuntimeError(
            f"refusing to write issue body — {len(hits)} secret-shaped "
            f"string(s) detected: {redacted}"
        )
    return markdown


if __name__ == "__main__":
    args = build_arg_parser().parse_args()
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
