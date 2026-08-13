"""Renderer for .claude/skills/ artifacts."""

from __future__ import annotations

import json
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, StrictUndefined

_TEMPLATE_DIR = Path(__file__).parents[2] / "templates"


def _env() -> Environment:
    return Environment(
        loader=FileSystemLoader(str(_TEMPLATE_DIR)),
        undefined=StrictUndefined,
        keep_trailing_newline=True,
    )


def render_skills(skills: list[dict]) -> dict[str, str]:
    files: dict[str, str] = {}
    env = _env()

    manifest_payload = [
        {
            "name": s["name"],
            "description": s["description"],
            "allowed-tools": s.get("allowed_tools") or [],
            "requiredSkills": s.get("required_skills") or [],
        }
        for s in skills
    ]
    files[".claude/skills/manifest.json"] = env.get_template(
        ".claude/skills/manifest.json.j2"
    ).render(skills_json=json.dumps(manifest_payload, indent=2))

    for s in skills:
        rel = f".claude/skills/{s['name']}/SKILL.md"
        files[rel] = env.get_template(".claude/skills/SKILL.md.j2").render(
            name=s["name"],
            description=s["description"],
            allowed_tools=s.get("allowed_tools") or [],
            required_skills=s.get("required_skills") or [],
            body=s["body"],
        )
    return files
