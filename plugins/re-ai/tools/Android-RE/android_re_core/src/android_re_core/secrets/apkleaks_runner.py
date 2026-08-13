"""Wrapper around the apkleaks CLI for high-recall secret scanning.

apkleaks is a third-party tool (https://github.com/dwisiswant0/apkleaks)
that scans APKs for URLs, endpoints, API keys, and other secrets by
walking the smali + resources. We do not vendor it directly; the
caller is expected to install it via:

    pipx install apkleaks

or ``bin/pull-tools.sh`` (Phase 2 extension). If the binary is not
on PATH, the :func:`run_apkleaks` function returns a structured error
rather than raising, so the MCP server can degrade gracefully.
"""

from __future__ import annotations

import json
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ..errors import ToolFailed, ToolNotFound, ToolTimeout

__all__ = [
    "DEFAULT_TIMEOUT_S",
    "ApkleaksFinding",
    "ApkleaksResult",
    "run_apkleaks",
]


#: Default subprocess timeout (5 minutes).
DEFAULT_TIMEOUT_S: int = 300


@dataclass(frozen=True)
class ApkleaksFinding:
    """A single apkleaks finding."""

    rule: str
    match: str
    line: int | None = None

    def to_dict(self) -> dict[str, Any]:
        return {"rule": self.rule, "match": self.match, "line": self.line}


@dataclass(frozen=True)
class ApkleaksResult:
    """Output of an apkleaks scan."""

    apk_path: str
    findings: tuple[ApkleaksFinding, ...]
    raw_stdout: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "apk_path": self.apk_path,
            "count": len(self.findings),
            "findings": [f.to_dict() for f in self.findings],
        }


def run_apkleaks(
    apk_path: str | Path,
    *,
    timeout_s: int = DEFAULT_TIMEOUT_S,
    output_format: str = "json",
) -> ApkleaksResult:
    """Run apkleaks against an APK and return structured findings.

    Args:
        apk_path: Path to the APK to scan.
        timeout_s: Subprocess timeout in seconds.
        output_format: ``json`` (default) or ``text``.

    Raises:
        ToolNotFound: apkleaks is not installed.
        ToolTimeout: apkleaks did not complete in time.
        ToolFailed: apkleaks exited non-zero.
    """
    binary = shutil.which("apkleaks")
    if binary is None:
        raise ToolNotFound(
            "apkleaks",
            details={
                "hint": (
                    "Install with: pipx install apkleaks, "
                    "or run bin/pull-tools.sh (when extended for apkleaks)."
                )
            },
        )

    apk = Path(apk_path).expanduser().resolve()
    if not apk.exists():
        raise ToolNotFound(
            f"APK not found: {apk}",
            details={"apk_path": str(apk)},
        )

    cmd: list[str] = [
        binary,
        "-f",
        str(apk),
        "-o",
        "/dev/stdout",
        "--format",
        output_format,
    ]
    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout_s,
            check=False,
        )
    except subprocess.TimeoutExpired as e:
        raise ToolTimeout(
            f"apkleaks timed out after {timeout_s}s",
            details={"cmd": cmd},
        ) from e

    if proc.returncode != 0:
        raise ToolFailed(
            f"apkleaks failed (exit {proc.returncode})",
            details={"cmd": cmd, "stderr": proc.stderr[-2000:]},
        )

    findings: list[ApkleaksFinding] = []
    if output_format == "json":
        try:
            data = json.loads(proc.stdout) if proc.stdout.strip() else {}
            for entry in data.get("findings", []) or []:
                findings.append(
                    ApkleaksFinding(
                        rule=entry.get("rule", "<unknown>"),
                        match=entry.get("match", ""),
                        line=entry.get("line"),
                    )
                )
        except json.JSONDecodeError:
            # apkleaks may have output non-JSON even when --format=json
            findings = _parse_text(proc.stdout)
    else:
        findings = _parse_text(proc.stdout)

    return ApkleaksResult(
        apk_path=str(apk),
        findings=tuple(findings),
        raw_stdout=proc.stdout,
    )


def _parse_text(text: str) -> list[ApkleaksFinding]:
    """Best-effort parser for apkleaks's text output."""
    out: list[ApkleaksFinding] = []
    current_rule: str | None = None
    for raw in text.splitlines():
        line = raw.rstrip()
        if not line:
            current_rule = None
            continue
        if line.startswith("Rule:"):
            current_rule = line.split(":", 1)[1].strip()
        elif current_rule and line.strip():
            out.append(ApkleaksFinding(rule=current_rule, match=line.strip()))
    return out
