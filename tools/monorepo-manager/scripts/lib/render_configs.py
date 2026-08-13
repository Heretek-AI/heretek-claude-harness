"""Renderer for linter/pre-commit/Sonar/gitleaks config files."""

from __future__ import annotations

from pathlib import Path

from jinja2 import Environment, FileSystemLoader, StrictUndefined

_TEMPLATE_DIR = Path(__file__).parents[2] / "templates"

_LINTER_FILES = [
    ".github/linters/eslintrc.yml",
    ".github/linters/python-ruff.yml",
    ".github/linters/shellcheck.yml",
    ".github/linters/yamllint.yml",
    ".github/linters/markdownlint.yml",
    ".github/linters/prettierrc.yml",
]


def _env() -> Environment:
    return Environment(
        loader=FileSystemLoader(str(_TEMPLATE_DIR)),
        undefined=StrictUndefined,
        keep_trailing_newline=True,
    )


def render_configs(stack: str, sonar_key: str, project_name: str) -> dict[str, str]:
    files: dict[str, str] = {}
    for rel in _LINTER_FILES:
        files[rel] = (Path(_TEMPLATE_DIR) / rel).read_text(encoding="utf-8")

    files[".pre-commit-config.yaml"] = (
        _env().get_template(".pre-commit-config.yaml.j2").render(stack=stack)
    )

    files["sonar-project.properties"] = (
        _env()
        .get_template("sonar-project.properties.j2")
        .render(sonar_key=sonar_key, project_name=project_name, stack=stack)
    )

    files[".github/gitleaks-config.yml"] = (
        Path(_TEMPLATE_DIR) / ".github/gitleaks-config.yml"
    ).read_text(encoding="utf-8")
    files[".gitleaks-baseline.json"] = (Path(_TEMPLATE_DIR) / ".gitleaks-baseline.json").read_text(
        encoding="utf-8"
    )

    return files
