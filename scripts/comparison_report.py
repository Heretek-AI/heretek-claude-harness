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


def render_markdown(
    a: Summary,
    b: Summary,
    diff: dict,
    meta: dict,
) -> str:
    """Render the comparison Markdown body for the GitHub issue."""
    lines: list[str] = []
    lines.append(f"# Terminal-Bench A/B — `{meta['commit_sha_short']}`")
    lines.append("")
    lines.append(f"**Trigger:** `{meta['trigger']}`")
    lines.append(f"**Actor:** {meta['actor']}")
    n = a.n_tasks
    lines.append(f"**Tier:** `{meta['tier']}` ({n} task{'s' if n != 1 else ''})")
    lines.append(f"**Model:** `{meta['model']}` (via `{meta['base_url']}`)")
    lines.append("")
    lines.append("## Headline")
    lines.append("")
    lines.append("| Agent | Pass rate | Passed | Failed | Wall-clock | Tokens |")
    lines.append("|---|---|---|---|---|---|")
    lines.append(
        f"| **A — with heretek** | {_fmt_pct(a.pass_rate)} | {a.passed}/{a.n_tasks} "
        f"| {a.failed}/{a.n_tasks} | {a.wall_clock_sec_total}s | {a.tokens_total:,} |"
    )
    lines.append(
        f"| **B — baseline** | {_fmt_pct(b.pass_rate)} | {b.passed}/{b.n_tasks} "
        f"| {b.failed}/{b.n_tasks} | {b.wall_clock_sec_total}s | {b.tokens_total:,} |"
    )
    sign_pct = _fmt_signed(diff["delta_pass_rate"] * 100, "%")
    sign_pct = f"+{sign_pct}" if not sign_pct.startswith("-") else sign_pct
    sign_passed = _fmt_signed(diff["delta_passed"])
    sign_passed = f"+{sign_passed}" if not sign_passed.startswith("-") else sign_passed
    sign_wall = _fmt_signed(diff["wall_clock_delta_sec"], "s")
    sign_wall = f"+{sign_wall}" if not sign_wall.startswith("-") else sign_wall
    sign_tokens = _fmt_signed(diff["tokens_delta"])
    sign_tokens = f"+{sign_tokens}" if not sign_tokens.startswith("-") else sign_tokens
    lines.append(
        f"| **Δ** | **{sign_pct}** | **{sign_passed}** | — | **{sign_wall}** | **{sign_tokens}** |"
    )
    lines.append("")
    lines.append("## Per-task")
    lines.append("")
    lines.append("| Task | A | B | Notes |")
    lines.append("|---|---|---|---|")
    a_by_id = {t.task_id: t for t in a.per_task}
    b_by_id = {t.task_id: t for t in b.per_task}
    all_ids = sorted(set(a_by_id) | set(b_by_id))
    for tid in all_ids:
        a_task = a_by_id.get(tid)
        b_task = b_by_id.get(tid)
        a_str = (
            f"✓ ({a_task.wall_clock_sec}s)"
            if a_task and a_task.verdict == "pass"
            else f"✗ ({a_task.wall_clock_sec}s)"
            if a_task
            else "—"
        )
        b_str = (
            f"✓ ({b_task.wall_clock_sec}s)"
            if b_task and b_task.verdict == "pass"
            else f"✗ ({b_task.wall_clock_sec}s)"
            if b_task
            else "—"
        )
        a_pass = a_task is not None and a_task.verdict == "pass"
        b_pass = b_task is not None and b_task.verdict == "pass"
        if a_pass and b_pass:
            note = "both"
        elif a_pass and not b_pass:
            note = "A wins"
        elif b_pass and not a_pass:
            note = "B wins"
        else:
            note = "both fail"
        lines.append(f"| {tid} | {a_str} | {b_str} | {note} |")
    lines.append("")
    helped = diff["tasks_agent_a_passed_b_failed"]
    hurt = diff["tasks_agent_b_passed_a_failed"]
    lines.append("## Tasks where heretek helped")
    lines.append("")
    if helped:
        for tid in helped:
            lines.append(f"- `{tid}` (A pass, B fail)")
    else:
        lines.append("(none)")
    lines.append("")
    lines.append("## Tasks where heretek hurt")
    lines.append("")
    if hurt:
        for tid in hurt:
            lines.append(f"- `{tid}` (A fail, B pass)")
    else:
        lines.append("(none)")
    lines.append("")
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
