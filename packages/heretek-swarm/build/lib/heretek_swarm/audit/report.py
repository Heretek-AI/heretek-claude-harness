"""Audit report generation."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class AuditFinding:
    """A single audit finding."""

    file: str
    line: int
    pattern_name: str
    severity: str
    description: str

    def __post_init__(self) -> None:
        self.severity = self.severity.upper()


def group_by_severity(findings: list[AuditFinding]) -> dict[str, list[AuditFinding]]:
    """Group findings by severity level.

    Returns a dict with keys: CRITICAL, WARNING, INFO.
    """
    groups: dict[str, list[AuditFinding]] = {
        "CRITICAL": [],
        "WARNING": [],
        "INFO": [],
    }
    for finding in findings:
        groups.setdefault(finding.severity, []).append(finding)
    return groups


def _format_finding(f: AuditFinding) -> str:
    return f"- `{f.file}:{f.line}` — **{f.pattern_name}**: {f.description}"


def generate_report(findings: list[AuditFinding], title: str = "Audit Report") -> str:
    """Generate a markdown audit report from findings.

    Report format: header -> Critical section -> Warning section ->
    Info section -> summary table.
    """
    if not findings:
        return f"# {title}\n\nNo findings.\n"

    groups = group_by_severity(findings)
    lines: list[str] = []

    lines.append(f"# {title}\n")
    lines.append(f"**Total findings:** {len(findings)}\n")

    # Critical section
    critical = groups.get("CRITICAL", [])
    lines.append("\n## CRITICAL\n")
    if critical:
        lines.append(f"Found {len(critical)} critical issue(s).\n")
        lines.extend(_format_finding(f) for f in critical)
    else:
        lines.append("No critical issues.\n")

    # Warning section
    warning = groups.get("WARNING", [])
    lines.append("\n## WARNING\n")
    if warning:
        lines.append(f"Found {len(warning)} warning(s).\n")
        lines.extend(_format_finding(f) for f in warning)
    else:
        lines.append("No warnings.\n")

    # Info section
    info = groups.get("INFO", [])
    lines.append("\n## INFO\n")
    if info:
        lines.append(f"Found {len(info)} informational item(s).\n")
        lines.extend(_format_finding(f) for f in info)
    else:
        lines.append("No informational items.\n")

    # Summary table
    lines.append("\n## Summary\n")
    lines.append("| Severity | Count |")
    lines.append("| --- | --- |")
    lines.append(f"| CRITICAL | {len(critical)} |")
    lines.append(f"| WARNING | {len(warning)} |")
    lines.append(f"| INFO | {len(info)} |")

    return "\n".join(lines) + "\n"
