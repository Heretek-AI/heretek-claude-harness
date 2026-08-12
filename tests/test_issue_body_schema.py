"""Verify the rendered Markdown has all required issue body sections."""

from __future__ import annotations

from pathlib import Path

from comparison_report import (
    compute_diff,
    load_summary,
    render_markdown,
)


def _load(name: str):
    root = Path(__file__).resolve().parent / "fixtures" / "terminal_bench_ab" / name
    a = load_summary(root / "agent-a" / "summary.json")
    b = load_summary(root / "agent-b" / "summary.json")
    return a, b


def test_issue_body_has_all_required_sections() -> None:
    a, b = _load("case-quick-8-pass-5")
    md = render_markdown(
        a,
        b,
        compute_diff(a, b),
        {
            "commit_sha_short": "abc1234",
            "trigger": "push",
            "actor": "alice",
            "tier": "quick",
            "model": "claude-test",
            "base_url": "http://localhost",
        },
    )
    required = [
        "# Terminal-Bench A/B",
        "**Trigger:**",
        "**Actor:**",
        "**Tier:**",
        "**Model:**",
        "## Headline",
        "## Per-task",
        "## Tasks where heretek helped",
        "## Tasks where heretek hurt",
    ]
    for section in required:
        assert section in md, f"missing section: {section}"


def test_issue_body_no_template_placeholders() -> None:
    a, b = _load("case-quick-8-pass-5")
    md = render_markdown(
        a,
        b,
        compute_diff(a, b),
        {
            "commit_sha_short": "abc1234",
            "trigger": "push",
            "actor": "alice",
            "tier": "quick",
            "model": "claude-test",
            "base_url": "http://localhost",
        },
    )
    for placeholder in ["<!--TEMPLATE-->", "{{", "}}", "TODO", "FIXME"]:
        assert placeholder not in md, f"placeholder {placeholder!r} leaked into body"
