"""MCP-server scanner wrapper. Runs SkillSpector on the content AND looks
up the upstream tarball in VirusTotal. Severity is the worst of the two.

CLI usage: see scan_mcp().
"""

from __future__ import annotations

import hashlib
import json
import logging
from pathlib import Path

import requests

from .base import Finding, ScannerReport, Severity
from .skills import scan_skill

log = logging.getLogger(__name__)

VT_API = "https://www.virustotal.com/api/v3"
_SEVERITY_ORDER = ["clean", "info", "warn", "block"]


def _worse(a: Severity, b: Severity) -> Severity:
    return a if _SEVERITY_ORDER.index(a) >= _SEVERITY_ORDER.index(b) else b


def _tarball_candidate(path: Path) -> Path | None:
    """Pick the file in `path` to hash for VT lookup.

    Preference order: server.<ext>, index.<ext>, package.json. None if no
    obvious candidate.
    """
    for name in ("server.js", "server.ts", "server.py", "index.js", "package.json"):
        p = path / name
        if p.exists():
            return p
    return None


def _vt_lookup(file_sha256: str, *, token: str | None) -> ScannerReport:
    """VirusTotal v3 lookup by file SHA-256. Soft-fails if no record."""
    if not token:
        return ScannerReport(
            item_id=file_sha256[:12],
            scanner="virustotal",
            severity="info",
            findings=[
                Finding(path="*", line=None, message="no VT_TOKEN; skipped", rule_id="vt-skipped")
            ],
        )
    try:
        r = requests.get(
            f"{VT_API}/files/{file_sha256}",
            headers={"x-apikey": token},
            timeout=10,
        )
    except requests.RequestException as e:
        return ScannerReport(
            item_id=file_sha256[:12],
            scanner="virustotal",
            severity="info",
            findings=[
                Finding(
                    path="*", line=None, message=f"VT request error: {e}", rule_id="vt-unreachable"
                )
            ],
        )

    if r.status_code == 404:
        return ScannerReport(
            item_id=file_sha256[:12],
            scanner="virustotal",
            severity="info",
            findings=[
                Finding(
                    path="*", line=None, message="no VT record (common)", rule_id="vt-no-record"
                )
            ],
        )

    if r.status_code != 200:
        return ScannerReport(
            item_id=file_sha256[:12],
            scanner="virustotal",
            severity="info",
            findings=[
                Finding(
                    path="*", line=None, message=f"VT HTTP {r.status_code}", rule_id="vt-http-error"
                )
            ],
        )

    try:
        data = r.json()
    except json.JSONDecodeError:
        return ScannerReport(
            item_id=file_sha256[:12],
            scanner="virustotal",
            severity="warn",
            findings=[
                Finding(path="*", line=None, message="VT invalid JSON", rule_id="vt-invalid-json")
            ],
        )

    stats = data.get("data", {}).get("attributes", {}).get("last_analysis_stats", {})
    malicious = int(stats.get("malicious", 0))
    suspicious = int(stats.get("suspicious", 0))

    if malicious >= 5:
        severity: Severity = "block"
    elif malicious >= 1 or suspicious >= 3:
        severity = "warn"
    else:
        severity = "clean"

    return ScannerReport(
        item_id=file_sha256[:12],
        scanner="virustotal",
        severity=severity,
        findings=[
            Finding(
                path="*",
                line=None,
                message=f"VT verdict: malicious={malicious}, suspicious={suspicious}",
                rule_id="vt-verdict",
            )
        ],
        raw=data,
    )


def scan_mcp(path: Path, *, item_id: str, vt_token: str | None = None) -> ScannerReport:
    """Run SkillSpector on content + VirusTotal on the tarball candidate."""
    skill_report = scan_skill(path, item_id=item_id)

    if vt_token is None:
        vt_report = ScannerReport(
            item_id=item_id,
            scanner="virustotal",
            severity="info",
            findings=[
                Finding(path="*", line=None, message="no VT_TOKEN; skipped", rule_id="vt-skipped")
            ],
        )
    else:
        candidate = _tarball_candidate(path)
        if candidate is None:
            vt_report = ScannerReport(
                item_id=item_id,
                scanner="virustotal",
                severity="info",
                findings=[
                    Finding(
                        path="*",
                        line=None,
                        message="no tarball candidate in MCP dir",
                        rule_id="vt-no-candidate",
                    )
                ],
            )
        else:
            digest = hashlib.sha256(candidate.read_bytes()).hexdigest()
            vt_report = _vt_lookup(file_sha256=digest, token=vt_token)

    # VT "info" severity represents a soft-fail (no record, network error, etc.)
    # and should NOT escalate the combined severity.
    vt_for_combination: Severity = "clean" if vt_report.severity == "info" else vt_report.severity
    combined_severity = _worse(skill_report.severity, vt_for_combination)

    return ScannerReport(
        item_id=item_id,
        scanner="mcp-combined",
        severity=combined_severity,
        findings=skill_report.findings + vt_report.findings,
        raw={"skill": skill_report.raw, "vt": vt_report.raw},
    )


class McpScanner:
    def scan(self, path: Path, *, item_id: str | None = None) -> ScannerReport:
        return scan_mcp(path, item_id=item_id or path.name)
