"""Build GitHub issue payloads from audit findings.

Per spec §Auto-issue creation rules: HIGH+CRITICAL only, 5/cluster cap,
1 umbrella issue per cluster for overflow. This module only builds payloads;
the actual mcp__github__github-issue_write calls happen in the driver or
by the operator -- keeping this module network-free and testable.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List

from audit.findings import Finding

REPO: str = "Heretek-AI/heretek-claude-harness"

BASE_LABELS: List[str] = [
    "audit",
    "harness-self-audit",
    "principles-audit",
    "audit-2026-08-09",
]

_AUDITABLE_SEVERITIES: set[str] = {"critical", "high"}

# Short slug for issue title prefix, keyed by cluster name.
_CLUSTER_SHORT: dict[str, str] = {
    "Readability & quality bar": "readability",
    "Design & architecture": "design",
    "Correctness & safety": "correctness",
    "Testing & verification": "testing",
    "Operations & docs": "ops-docs",
}


@dataclass
class IssuePayload:
    """Ready-to-file GitHub issue payload."""

    title: str
    body: str
    labels: List[str] = field(default_factory=list)


def _title_for(f: Finding) -> str:
    """Build issue title from a single finding."""
    short = _CLUSTER_SHORT.get(f.cluster, f.cluster.lower().replace(" ", "-")[:20])
    return f"[audit:spec-1:{short}] {f.principle}"


def _body_for(f: Finding) -> str:
    """Build markdown issue body for a single finding."""
    priority = "P0" if f.severity == "critical" else "P1"
    lines = [
        f"**Severity:** {f.severity} (`{priority}`)",
        f"**Cluster:** {f.cluster}",
        f"**Finding ID:** {f.finding_id}",
        "",
        "## Principle",
        f"{f.principle} ({f.principle_reference})",
        "",
        "## Evidence",
        f"- File: `{f.evidence.file}` lines {f.evidence.line_range[0]}-{f.evidence.line_range[1]}",
        f"- Metric: {f.evidence.metric}",
        f"- Code refs: {', '.join(f.evidence.code_refs)}",
        "",
        "## Failure scenario",
        f.failure_scenario,
        "",
        "## Recommended action",
        f.recommended_action,
        "",
        "## Rationale",
        f.rationale,
    ]
    if f.drift_signals:
        lines += ["", "## Drift signals"] + [f"- {s}" for s in f.drift_signals]
    return "\n".join(lines)


def _umbrella_body(cluster: str, overflow_count: int) -> str:
    """Build markdown body for an umbrella issue bundling overflow findings."""
    lines = [
        f"## Umbrella issue: {cluster}",
        "",
        f"This cluster has **{overflow_count} additional findings** beyond the "
        f"5-per-cluster cap. Each finding is summarized below; the operator "
        f"should file individual issues or address them in a batch PR.",
    ]
    return "\n".join(lines)


def build_issue_payloads(
    findings: List[Finding],
    *,
    cap: int = 5,
) -> List[IssuePayload]:
    """Build GitHub issue payloads from audit findings.

    Groups HIGH+CRITICAL findings by cluster, emits up to ``cap`` individual
    issues per cluster (sorted critical-first then by file), and one umbrella
    issue per cluster for any overflow.
    """
    # Filter to auditable severities only.
    auditable = [f for f in findings if f.severity in _AUDITABLE_SEVERITIES]
    if not auditable:
        return []

    # Group by cluster.
    clusters: dict[str, list[Finding]] = {}
    for f in auditable:
        clusters.setdefault(f.cluster, []).append(f)

    result: list[IssuePayload] = []

    for cluster_name, cluster_findings in sorted(clusters.items()):
        # Rank by severity (critical first), then by file for determinism.
        cluster_findings.sort(
            key=lambda f: (
                0 if f.severity == "critical" else 1,
                f.evidence.file,
                f.evidence.line_range[0],
            )
        )

        kept = cluster_findings[:cap]
        overflow = cluster_findings[cap:]

        for f in kept:
            priority_label = "P0" if f.severity == "critical" else "P1"
            result.append(
                IssuePayload(
                    title=_title_for(f),
                    body=_body_for(f),
                    labels=BASE_LABELS + [priority_label],
                )
            )

        if overflow:
            short = _CLUSTER_SHORT.get(
                cluster_name,
                cluster_name.lower().replace(" ", "-")[:20],
            )
            result.append(
                IssuePayload(
                    title=(
                        f"[audit:spec-1:{short}] {len(overflow)} additional findings "
                        f"from harness self-audit"
                    ),
                    body=_umbrella_body(cluster_name, len(overflow)),
                    labels=BASE_LABELS + ["P1"],
                )
            )

    return result
