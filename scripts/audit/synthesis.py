"""Synthesis pass: load cluster results, dedupe, rank, write report + JSON.

Loads all 5 cluster result files (A-E) via audit.findings.load_findings
(schema-validated), filters SonarCloud exclusions, dedupes by
(file, line_range) keeping the higher-severity entry, sorts by severity,
and writes both a markdown report and JSON findings to
output_dir/audit-harness-self-<date>.{md,json}. Coverage gaps section
flags missing clusters and zero-finding clusters.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from pathlib import Path

from audit import findings


CLUSTER_LETTERS = ["A", "B", "C", "D", "E"]


@dataclass
class SynthesisResult:
    findings: list[findings.Finding]
    report_path: Path
    json_path: Path
    coverage_gaps: list[str]
    duplicate_count: int


def _load_cluster_results(cluster_results_dir: Path) -> list[findings.Finding]:
    """Load all YAML/JSON cluster result files from *cluster_results_dir*.

    Files are named <cluster_letter>.{yaml,yml,json}. Each file is
    loaded and validated via findings.load_findings.
    """
    all_findings: list[findings.Finding] = []
    for letter in CLUSTER_LETTERS:
        for ext in (".yaml", ".yml", ".json"):
            path = cluster_results_dir / f"{letter}{ext}"
            if path.exists():
                all_findings.extend(findings.load_findings(path))
                break
    return all_findings


def _dedupe(items: list[findings.Finding]) -> tuple[list[findings.Finding], int]:
    """Collapse findings with identical (file, line_range). Keep the higher-severity one."""
    seen: dict[tuple[str, tuple[int, int]], findings.Finding] = {}
    dup_count = 0
    for f in items:
        key = (f.evidence.file, tuple(f.evidence.line_range))
        if key in seen:
            dup_count += 1
            # Keep the more severe one (lower rank = more severe).
            if findings.severity_rank(f) < findings.severity_rank(seen[key]):
                seen[key] = f
        else:
            seen[key] = f
    deduped = sorted(seen.values(), key=findings.severity_rank)
    return deduped, dup_count


def _ranked_table(items: list[findings.Finding]) -> str:
    """Return a markdown table of findings sorted by severity."""
    lines = [
        "| # | ID | Severity | File | Line Range | Principle |",
        "|---|---|---|---|---|---|",
    ]
    for i, f in enumerate(items, 1):
        lr = f.evidence.line_range
        lines.append(
            f"| {i} | {f.finding_id} | {f.severity} | "
            f"`{f.evidence.file}` | {lr[0]}-{lr[1]} | {f.principle} |"
        )
    return "\n".join(lines)


def _present_cluster_files(cluster_results_dir: Path) -> set[str]:
    """Detect which cluster letters have a result file present."""
    present: set[str] = set()
    for letter in CLUSTER_LETTERS:
        for ext in (".yaml", ".yml", ".json"):
            if (cluster_results_dir / f"{letter}{ext}").exists():
                present.add(letter)
                break
    return present


def _present_cluster_findings(items: list[findings.Finding]) -> set[str]:
    """Detect which cluster letters have at least one finding (by finding_id prefix)."""
    present: set[str] = set()
    for f in items:
        for letter in CLUSTER_LETTERS:
            if f.finding_id.startswith(letter):
                present.add(letter)
                break
    return present


def _coverage_gaps_section(
    cluster_results_dir: Path, items: list[findings.Finding]
) -> list[str]:
    """Detect missing clusters and zero-finding clusters."""
    present_files = _present_cluster_files(cluster_results_dir)
    present_findings = _present_cluster_findings(items)
    gaps: list[str] = []
    for letter in CLUSTER_LETTERS:
        if letter not in present_files:
            gaps.append(f"Cluster {letter}: result file missing")
        elif letter not in present_findings:
            gaps.append(f"Cluster {letter}: zero findings")
    return gaps


def _report_markdown(
    items: list[findings.Finding],
    commit_sha: str,
    duplicate_count: int,
    coverage_gaps: list[str],
) -> str:
    """Build the full markdown report."""
    crit = sum(1 for f in items if f.severity == "critical")
    high = sum(1 for f in items if f.severity == "high")
    med = sum(1 for f in items if f.severity == "medium")
    low = sum(1 for f in items if f.severity == "low")
    info = sum(1 for f in items if f.severity == "info")

    sections = [
        "# Harness Self-Audit Report",
        "",
        f"**Snapshot:** `{commit_sha}`",
        f"**Date:** {date.today().isoformat()}",
        f"**Total findings (after dedup):** {len(items)}",
        f"**Duplicates removed:** {duplicate_count}",
        "",
        "## Severity Summary",
        "",
        f"- Critical: {crit}",
        f"- High: {high}",
        f"- Medium: {med}",
        f"- Low: {low}",
        f"- Info: {info}",
        "",
    ]

    if items:
        sections.append("## Findings")
        sections.append("")
        sections.append(_ranked_table(items))
        sections.append("")

    if coverage_gaps:
        sections.append("## Coverage Gaps")
        sections.append("")
        for gap in coverage_gaps:
            sections.append(f"- {gap}")
        sections.append("")

    sections.extend(
        [
            "## Re-verification Checklist",
            "",
            "Synthesis flagged findings that need operator review. "
            "The actual metric re-check is executed by the operator.",
            "",
            "- [ ] Every `critical` finding inspected directly at the cited file:line",
            "- [ ] Every `high` finding inspected unless numeric metric + tool output present",
            "- [ ] Severity counts reviewed and adjusted if needed",
            "",
        ]
    )

    return "\n".join(sections)


def synthesize(
    cluster_results_dir: Path,
    output_dir: Path,
    commit_sha: str,
    sonar_exclusions: set[str] | None = None,
) -> SynthesisResult:
    """Run the full synthesis pass.

    Loads cluster results, filters SonarCloud exclusions, dedupes,
    sorts by severity, writes report + JSON.
    """
    output_dir.mkdir(parents=True, exist_ok=True)

    all_findings = _load_cluster_results(cluster_results_dir)

    # Filter SonarCloud exclusions
    if sonar_exclusions:
        all_findings = [
            f for f in all_findings if f.evidence.file not in sonar_exclusions
        ]

    deduped, dup_count = _dedupe(all_findings)

    # Determine output paths
    today = date.today().isoformat()
    report_path = output_dir / f"audit-harness-self-{today}.md"
    json_path = output_dir / f"audit-harness-self-{today}.json"

    # Write JSON
    findings.save_findings(deduped, json_path)

    # Coverage gaps
    coverage_gaps = _coverage_gaps_section(cluster_results_dir, all_findings)

    # Write report
    report = _report_markdown(deduped, commit_sha, dup_count, coverage_gaps)
    report_path.write_text(report)

    return SynthesisResult(
        findings=deduped,
        report_path=report_path,
        json_path=json_path,
        coverage_gaps=coverage_gaps,
        duplicate_count=dup_count,
    )
