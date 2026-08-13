"""AGENTS.md contract validator.

The contract requires seven top-level sections in this exact order:
Project summary, Stack & runtime targets, Build, test, lint, run commands,
Project structure, Conventions, Do / Don't list, Pointer block. Each
section must contain at least one non-blank line.
"""

from __future__ import annotations

import pathlib
import re

REQUIRED_SECTIONS = [
    "Project summary",
    "Stack & runtime targets",
    "Build, test, lint, run commands",
    "Project structure",
    "Conventions",
    "Do / Don't list",
    "Pointer block",
]

_SECTION_RE = re.compile(r"^##\s+(.+?)\s*$")


def validate_agents(path: str) -> list[str]:
    p = pathlib.Path(path)
    text = p.read_text(encoding="utf-8")
    lines = text.splitlines()
    violations: list[str] = []

    section_indices: list[tuple[str, int, int]] = []
    for i, line in enumerate(lines):
        m = _SECTION_RE.match(line)
        if m:
            section_indices.append((m.group(1), i, len(lines)))

    for j, (name, start, end) in enumerate(section_indices):
        body_end = section_indices[j + 1][1] if j + 1 < len(section_indices) else end
        body = [ln for ln in lines[start + 1 : body_end] if ln.strip()]
        section_indices[j] = (name, start, len(body))

    seen = [name for name, _, _ in section_indices]
    required = REQUIRED_SECTIONS

    for sec in required:
        if sec not in seen:
            violations.append(f"required section '{sec}' missing")
    for sec in seen:
        if sec not in required:
            violations.append(f"unexpected section '{sec}'")

    if seen != required:
        violations.append(f"sections must appear in order: {required}")

    seen_set = set()
    for sec in seen:
        if sec in seen_set:
            violations.append(f"duplicate section '{sec}'")
        seen_set.add(sec)

    for name, _, body_lines in section_indices:
        if name in required and body_lines == 0:
            violations.append(f"section '{name}' is empty")

    return violations
