"""Renderer for AGENTS.md and CLAUDE.md."""

from __future__ import annotations

import pathlib

from jinja2 import Environment, FileSystemLoader, StrictUndefined

_TEMPLATE_DIR = pathlib.Path(__file__).parents[2] / "templates"


def _env() -> Environment:
    return Environment(
        loader=FileSystemLoader(str(_TEMPLATE_DIR)),
        undefined=StrictUndefined,
        keep_trailing_newline=True,
    )


def render_agents(params: dict) -> dict[str, str]:
    env = _env()
    context = {**params, "seed_url": params.get("seed_url", "")}
    return {
        "AGENTS.md": env.get_template("AGENTS.md.j2").render(**context),
        "CLAUDE.md": env.get_template("CLAUDE.md.j2").render(**context),
    }
