"""High-signal LLM Diagnostic Translator module.

Converts verbose compiler, linter, and type checker stack traces (ruff, pyright,
cargo clippy, tsc, biome) into concise, actionable diagnostic lines tailored
for small model context windows (e.g. Qwen 3.6 27B / Claude Code).

Example output line:
    [ERROR] src/main.rs:42 - mismatched types (E0308)
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Literal

DiagnosticLevel = Literal["ERROR", "WARNING", "INFO"]


@dataclass(frozen=True)
class Diagnostic:
    file_path: str
    line: int | None
    column: int | None
    message: str
    code: str | None = None
    level: DiagnosticLevel = "ERROR"

    def format_minimal(self) -> str:
        """Format into a single high-signal line for LLM context."""
        loc = f"{self.file_path}"
        if self.line is not None:
            loc += f":{self.line}"
            if self.column is not None:
                loc += f":{self.column}"
        code_str = f" ({self.code})" if self.code else ""
        return f"[{self.level}] {loc} - {self.message}{code_str}"


# Regex patterns for popular tools
_RUFF_PATTERN = re.compile(
    r"^(?P<file>[^\s:]+):(?P<line>\d+):(?P<col>\d+):\s*(?P<code>[A-Z]\d+|[A-Z]{2,}\d+)?\s*(?P<msg>.+)$"
)

_PYRIGHT_PATTERN = re.compile(
    r"^(?P<file>[^\s:]+):(?P<line>\d+):(?P<col>\d+)\s+-\s+(?P<level>error|warning|info):\s+(?P<msg>.+?)(?:\s+\((?P<code>[a-zA-Z0-9]+)\))?$"
)

_CARGO_PATTERN = re.compile(
    r"^error(?:\[(?P<code>E\d+)\])?:\s*(?P<msg>.+)\n\s*-->\s*(?P<file>[^\s:]+):(?P<line>\d+):(?P<col>\d+)",
    re.MULTILINE,
)

_TSC_PATTERN = re.compile(
    r"^(?P<file>[^\s:]+)\((?P<line>\d+),(?P<col>\d+)\):\s*(?P<level>error|warning)\s+(?P<code>TS\d+):\s*(?P<msg>.+)$"
)


def parse_ruff_output(text: str) -> list[Diagnostic]:
    diagnostics: list[Diagnostic] = []
    for line in text.splitlines():
        line_str = line.strip()
        m = _RUFF_PATTERN.match(line_str)
        if m:
            diagnostics.append(
                Diagnostic(
                    file_path=m.group("file"),
                    line=int(m.group("line")),
                    column=int(m.group("col")),
                    message=m.group("msg").strip(),
                    code=m.group("code"),
                    level="ERROR",
                )
            )
    return diagnostics


def parse_pyright_output(text: str) -> list[Diagnostic]:
    diagnostics: list[Diagnostic] = []
    for line in text.splitlines():
        line_str = line.strip()
        m = _PYRIGHT_PATTERN.match(line_str)
        if m:
            lvl_str = m.group("level").upper()
            level: DiagnosticLevel = "WARNING" if lvl_str == "WARNING" else "ERROR"
            diagnostics.append(
                Diagnostic(
                    file_path=m.group("file"),
                    line=int(m.group("line")),
                    column=int(m.group("col")),
                    message=m.group("msg").strip(),
                    code=m.group("code"),
                    level=level,
                )
            )
    return diagnostics


def parse_cargo_output(text: str) -> list[Diagnostic]:
    diagnostics: list[Diagnostic] = []
    for m in _CARGO_PATTERN.finditer(text):
        diagnostics.append(
            Diagnostic(
                file_path=m.group("file"),
                line=int(m.group("line")),
                column=int(m.group("col")),
                message=m.group("msg").strip(),
                code=m.group("code"),
                level="ERROR",
            )
        )
    return diagnostics


def parse_tsc_output(text: str) -> list[Diagnostic]:
    diagnostics: list[Diagnostic] = []
    for line in text.splitlines():
        line_str = line.strip()
        m = _TSC_PATTERN.match(line_str)
        if m:
            lvl_str = m.group("level").upper()
            level: DiagnosticLevel = "WARNING" if lvl_str == "WARNING" else "ERROR"
            diagnostics.append(
                Diagnostic(
                    file_path=m.group("file"),
                    line=int(m.group("line")),
                    column=int(m.group("col")),
                    message=m.group("msg").strip(),
                    code=m.group("code"),
                    level=level,
                )
            )
    return diagnostics


def translate_output(raw_output: str, tool_hint: str = "generic") -> str:
    """Parse raw tool stderr/stdout and translate into concise LLM feedback."""
    if not raw_output.strip():
        return ""

    diagnostics: list[Diagnostic] = []
    tool_hint_lower = tool_hint.lower()

    if "ruff" in tool_hint_lower:
        diagnostics = parse_ruff_output(raw_output)
    elif "pyright" in tool_hint_lower:
        diagnostics = parse_pyright_output(raw_output)
    elif "cargo" in tool_hint_lower:
        diagnostics = parse_cargo_output(raw_output)
    elif "tsc" in tool_hint_lower:
        diagnostics = parse_tsc_output(raw_output)
    else:
        # Try all parsers in sequence
        diagnostics = (
            parse_ruff_output(raw_output)
            or parse_pyright_output(raw_output)
            or parse_cargo_output(raw_output)
            or parse_tsc_output(raw_output)
        )

    if not diagnostics:
        # Fallback: sanitize raw text down to max 5 essential error lines
        lines = [line.strip() for line in raw_output.splitlines() if line.strip()]
        error_lines = [
            l
            for l in lines
            if any(k in l.lower() for k in ("error", "fail", "exception", "denied"))
        ]
        target_lines = error_lines[:5] if error_lines else lines[:5]
        return "\n".join(f"[ERROR] {l}" for l in target_lines)

    return "\n".join(d.format_minimal() for d in diagnostics)
