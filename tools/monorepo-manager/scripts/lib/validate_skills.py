"""Validator for individual skill SKILL.md files.

A skill must have:
- A YAML frontmatter block delimited by '---' lines.
- A `name` field matching the parent directory.
- A `description` field (non-empty).
"""

from __future__ import annotations

import pathlib
import re
from typing import Any

import yaml

_FRONTMATTER_RE = re.compile(r"^---\n(.*?)\n---\n", re.DOTALL)
_REQUIRED = {"name", "description"}


def _parse_frontmatter(text: str) -> tuple[dict[str, Any], str]:
    m = _FRONTMATTER_RE.match(text)
    if not m:
        return {}, text
    fm = yaml.safe_load(m.group(1)) or {}
    return fm, text[m.end() :]


def validate_skill(skill_path: str) -> list[str]:
    p = pathlib.Path(skill_path)
    skill_file = p / "SKILL.md"
    if not skill_file.is_file():
        return [f"SKILL.md not found in {p}"]

    text = skill_file.read_text(encoding="utf-8")
    fm, _ = _parse_frontmatter(text)
    violations: list[str] = []

    if not fm:
        violations.append("missing frontmatter in SKILL.md")

    for key in _REQUIRED:
        val = fm.get(key)
        if val is None or not str(val).strip():
            violations.append(f"frontmatter field '{key}' is missing or empty")

    name = fm.get("name")
    if name and name != p.name:
        violations.append(
            f"frontmatter name '{name}' has a name/directory mismatch with directory '{p.name}'"
        )

    return violations
