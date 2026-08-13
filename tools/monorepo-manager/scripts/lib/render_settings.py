"""Renderer for .claude/settings.json."""

from __future__ import annotations

from pathlib import Path

from jinja2 import Environment, FileSystemLoader, StrictUndefined

from scripts.lib.lockfile import compute_lockfile_hash

_TEMPLATE_DIR = Path(__file__).parents[2] / "templates"


def _env() -> Environment:
    return Environment(
        loader=FileSystemLoader(str(_TEMPLATE_DIR)),
        undefined=StrictUndefined,
        keep_trailing_newline=True,
    )


def render_settings(stack: str, default_model: str = "sonnet") -> dict[str, str]:
    files: dict[str, str] = {}
    files[".claude/settings.json"] = (
        _env().get_template(".claude/settings.json.j2").render(default_model=default_model)
    )
    # The lockfile is computed over the hook files that ship with the
    # harness. We embed the hash here so the harness loader can verify
    # at agent startup.
    files[".claude/hooks/.lockfile"] = compute_lockfile_hash()
    return files
