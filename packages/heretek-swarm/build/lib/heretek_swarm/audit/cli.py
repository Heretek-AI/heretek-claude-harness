"""CLI for running audit scans and generating reports."""

from __future__ import annotations

import sys
from pathlib import Path

import click
import structlog

logger = structlog.get_logger(__name__)


# Ensure the heretek_swarm package is importable from the repo root.
# When invoked as `python audit/cli.py` from the repo root, we need to add
# `heretek-swarm/` to the path so `import heretek_swarm` works.
_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from heretek_swarm.audit import (  # noqa: E402
    AuditFinding,
    generate_report,
    scan_directory,
)


@click.command()
@click.option(
    "--directory",
    "-d",
    default="heretek-swarm/heretek_swarm",
    help="Root directory to scan (default: heretek-swarm/heretek_swarm)",
)
@click.option(
    "--output",
    "-o",
    default=None,
    help="Output file path. If not provided, prints to stdout.",
)
@click.option(
    "--severity",
    "-s",
    type=click.Choice(["CRITICAL", "WARNING", "INFO", "all"], case_sensitive=False),
    default="all",
    help="Filter findings by severity level.",
)
@click.option(
    "--format",
    "-f",
    type=click.Choice(["markdown", "json"], case_sensitive=False),
    default="markdown",
    help="Output format.",
)
@click.option(
    "--patterns",
    default=None,
    help="Comma-separated list of pattern names to run (default: all).",
)
def cli(
    directory: str,
    output: str | None,
    severity: str,
    format: str,  # noqa: A002
    patterns: str | None,
) -> None:
    """Run the stub detection audit and generate a report.

    Examples:

        python -m heretek_swarm.audit.cli -d backend/heretek_swarm

        python -m heretek_swarm.audit.cli -d backend/heretek_swarm -o report.md

        python -m heretek_swarm.audit.cli --severity CRITICAL -f json
    """
    # Resolve scan directory
    scan_root = Path(directory).resolve()
    if not scan_root.is_dir():
        click.echo(f"Error: directory not found: {scan_root}", err=True)
        sys.exit(1)

    # Parse patterns filter
    pattern_list = [p.strip() for p in patterns.split(",")] if patterns else None

    # Parse extensions
    extensions = {".py", ".js", ".ts", ".jsx", ".tsx"}

    click.echo(f"Scanning {scan_root} ...")
    findings: list[AuditFinding] = []
    findings.extend(scan_directory(scan_root, patterns=pattern_list, extensions=extensions))
    click.echo(f"Found {len(findings)} finding(s).")

    # Filter by severity if requested
    if severity.lower() != "all":
        findings = [f for f in findings if f.severity.upper() == severity.upper()]
        click.echo(f"Filtered to {len(findings)} {severity.upper()} finding(s).")

    # Generate report
    if format.lower() == "json":
        import json

        body = json.dumps(
            [
                {
                    "file": f.file,
                    "line": f.line,
                    "pattern_name": f.pattern_name,
                    "severity": f.severity,
                    "description": f.description,
                }
                for f in findings
            ],
            indent=2,
        )
        report_lines = body
    else:
        report_lines = generate_report(findings, title="Stub Detection Audit Report")

    # Output
    if output:
        Path(output).write_text(report_lines, encoding="utf-8")
        click.echo(f"Report written to: {output}")
    else:
        click.echo(report_lines)


if __name__ == "__main__":
    cli()
