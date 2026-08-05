"""SkillSpector wrapper. Shells out to `npx @nvidia/skillspector scan <path>`
and translates its JSON output into a ScannerReport.

CLI: `npx --yes @nvidia/skillspector scan <path> --format json`
Exit codes: 0 = no findings; 1 = findings present; 2 = scanner error.
Timeout: 60s (configurable).
"""
from __future__ import annotations

import json
import logging
import subprocess
from pathlib import Path

from .base import Finding, ScannerReport, Severity

log = logging.getLogger(__name__)

SKILLSPECTOR_CMD = ["npx", "--yes", "@nvidia/skillspector", "scan"]
TIMEOUT_SECONDS = 60

# Map from SkillSpector's severity strings to ours. Anything not in this
# map is treated as `warn` (safe default — never silently downgrade).
_SEVERITY_MAP: dict[str, Severity] = {
    "clean": "clean",
    "info": "info",
    "warn": "warn",
    "warning": "warn",
    "block": "block",
    "critical": "block",
}


def _map_severity(s: str) -> Severity:
    return _SEVERITY_MAP.get(s.lower(), "warn")


def scan_skill(path: Path, *, item_id: str) -> ScannerReport:
    """Run SkillSpector against `path` and return a ScannerReport."""
    cmd = [*SKILLSPECTOR_CMD, str(path), "--format", "json"]
    try:
        proc = subprocess.run(
            cmd, capture_output=True, text=True, timeout=TIMEOUT_SECONDS, check=False
        )
    except subprocess.TimeoutExpired:
        return ScannerReport(
            item_id=item_id,
            scanner="skillspector",
            severity="block",
            findings=[
                Finding(
                    path=str(path),
                    line=None,
                    message="SkillSpector timed out",
                    rule_id="timeout",
                )
            ],
        )
    except FileNotFoundError:
        return ScannerReport(
            item_id=item_id,
            scanner="skillspector",
            severity="block",
            findings=[
                Finding(
                    path=str(path),
                    line=None,
                    message="npx or @nvidia/skillspector binary unavailable",
                    rule_id="scanner-unavailable",
                )
            ],
        )

    if proc.returncode != 0 and not proc.stdout.strip():
        return ScannerReport(
            item_id=item_id,
            scanner="skillspector",
            severity="block",
            findings=[
                Finding(
                    path=str(path),
                    line=None,
                    message=f"SkillSpector exited {proc.returncode}: {proc.stderr.strip()}",
                    rule_id="scanner-unavailable",
                )
            ],
        )

    try:
        data = json.loads(proc.stdout)
    except json.JSONDecodeError as e:
        return ScannerReport(
            item_id=item_id,
            scanner="skillspector",
            severity="block",
            findings=[
                Finding(
                    path=str(path),
                    line=None,
                    message=f"SkillSpector JSON parse error: {e}",
                    rule_id="invalid-output",
                )
            ],
        )

    raw_findings = data.get("findings", [])
    findings = [
        Finding(
            path=f.get("path", ""),
            line=f.get("line"),
            message=f.get("message", ""),
            rule_id=f.get("rule_id"),
            cve_id=f.get("cve_id"),
        )
        for f in raw_findings
    ]

    # Severity is the worst finding's severity; clean if no findings.
    if not findings:
        severity: Severity = "clean"
    else:
        worst = max(
            (_map_severity(f.get("severity", "warn")) for f in raw_findings),
            key=lambda s: ["clean", "info", "warn", "block"].index(s),
        )
        severity = worst

    return ScannerReport(
        item_id=item_id,
        scanner="skillspector",
        severity=severity,
        findings=findings,
        raw=data,
    )


class SkillsScanner:
    """Object-oriented wrapper around `scan_skill` for the Protocol."""

    def scan(
        self, path: Path, *, token: str | None = None, item_id: str | None = None
    ) -> ScannerReport:
        return scan_skill(path, item_id=item_id or path.name)
