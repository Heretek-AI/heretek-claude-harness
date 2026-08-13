"""Renderer for .mcp.json.

Server names are validated against `^[a-z][a-z0-9-]{2,32}$`. The output
is a JSON string with a stable key order (github first, then alphabetical).
"""

from __future__ import annotations

import json
import re

from jinja2 import Environment, FileSystemLoader, StrictUndefined

_NAME_RE = re.compile(r"^[a-z][a-z0-9-]{2,32}$")
_TEMPLATE_DIR = "__INJECT_ROOT__"  # replaced at import time


def _env() -> Environment:
    from pathlib import Path

    return Environment(
        loader=FileSystemLoader(str(Path(__file__).parents[2] / "templates")),
        undefined=StrictUndefined,
        keep_trailing_newline=True,
    )


def render_mcp_named(servers: dict[str, dict]) -> str:
    """`servers` is a mapping from name to server payload."""
    for name in servers:
        if not _NAME_RE.match(name):
            raise ValueError(f"server name '{name}' must match {_NAME_RE.pattern}")
    ordered = {"github": servers.get("github")} if "github" in servers else {}
    for name in sorted(servers):
        if name not in ordered:
            ordered[name] = servers[name]
    body = json.dumps(ordered, indent=2)
    return _env().get_template(".mcp.json.j2").render(servers_json=body)
