"""Common scanner interface — Severity enum, Finding + ScannerReport dataclasses,
and the `scan()` Protocol that every per-kind wrapper implements.

This module has no third-party dependencies; the per-kind wrappers in
skills.py / mcp.py / lsp.py import from here.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal, Protocol

Severity = Literal["clean", "info", "warn", "block"]


@dataclass(frozen=True)
class Finding:
    """One scanner finding. `path` is repo-relative; `line` may be None."""

    path: str
    line: int | None
    message: str
    rule_id: str | None = None
    cve_id: str | None = None


@dataclass(frozen=True)
class ScannerReport:
    """Uniform output shape across all per-kind wrappers."""

    item_id: str
    scanner: str
    severity: Severity = "clean"
    findings: list[Finding] = field(default_factory=list)
    raw: dict = field(default_factory=dict)


class Scanner(Protocol):
    """The interface every wrapper in this package implements."""

    def scan(self, path: Path, *, token: str | None = None) -> ScannerReport: ...