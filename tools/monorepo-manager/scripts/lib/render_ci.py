"""Renderer for the four CI workflow files."""

from __future__ import annotations

from pathlib import Path

from jinja2 import Environment, FileSystemLoader, StrictUndefined

_TEMPLATE_DIR = Path(__file__).parents[2] / "templates"

_WORKFLOW_NAMES = [
    "super-linter.yml",
    "pre-commit.yml",
    "sonarcloud.yml",
    "secret-scan.yml",
]


def _env() -> Environment:
    return Environment(
        loader=FileSystemLoader(str(_TEMPLATE_DIR / ".github" / "workflows")),
        undefined=StrictUndefined,
        keep_trailing_newline=True,
    )


def render_ci(stack: str, test_cmd: str) -> dict[str, str]:
    files: dict[str, str] = {}
    for name in _WORKFLOW_NAMES:
        text = _env().get_template(name + ".j2").render(stack=stack, test_cmd=test_cmd)
        files[f".github/workflows/{name}"] = text
    return files
