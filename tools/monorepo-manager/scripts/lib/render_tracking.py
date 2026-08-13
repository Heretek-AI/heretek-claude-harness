"""Renderer for issue templates, PR template, and tracking config."""

from __future__ import annotations

from pathlib import Path

from jinja2 import Environment, FileSystemLoader, StrictUndefined

_TEMPLATE_DIR = Path(__file__).parents[2] / "templates"

_ISSUE_TEMPLATE_NAMES = [
    "bug",
    "feature",
    "security",
    "refactor",
    "infra-tooling",
    "spec",
]


def _env() -> Environment:
    return Environment(
        loader=FileSystemLoader(str(_TEMPLATE_DIR / ".github" / "ISSUE_TEMPLATE")),
        undefined=StrictUndefined,
        keep_trailing_newline=True,
    )


def render_issue_templates(org: str, repo: str, stack_label: str = "Stack") -> dict[str, str]:
    files: dict[str, str] = {}
    for name in _ISSUE_TEMPLATE_NAMES:
        files[f".github/ISSUE_TEMPLATE/{name}.md"] = (
            _env().get_template(f"{name}.md.j2").render(stack_label=stack_label)
        )
    files[".github/ISSUE_TEMPLATE/config.yml"] = (
        _env().get_template("config.yml.j2").render(org=org, repo=repo)
    )
    return files


def render_pr_template() -> dict[str, str]:
    env = Environment(
        loader=FileSystemLoader(str(_TEMPLATE_DIR / ".github")),
        undefined=StrictUndefined,
        keep_trailing_newline=True,
    )
    text = env.get_template("PULL_REQUEST_TEMPLATE.md.j2").render()
    return {".github/PULL_REQUEST_TEMPLATE.md": text}


def render_project_automation(org: str, repo: str, project_id: str) -> dict[str, str]:
    env = Environment(
        loader=FileSystemLoader(str(_TEMPLATE_DIR / ".github")),
        undefined=StrictUndefined,
        keep_trailing_newline=True,
    )
    text = env.get_template("projects-automation.graphql.j2").render(
        org=org, repo=repo, project_id=project_id
    )
    return {".github/projects-automation.graphql": text}


def render_labeler() -> dict[str, str]:
    return {
        ".github/labeler.yml": (Path(_TEMPLATE_DIR) / ".github/labeler.yml.j2").read_text(
            encoding="utf-8"
        )
    }


def render_contributing(org: str, repo: str) -> dict[str, str]:
    env = Environment(
        loader=FileSystemLoader(str(_TEMPLATE_DIR)),
        undefined=StrictUndefined,
        keep_trailing_newline=True,
    )
    return {"CONTRIBUTING.md": env.get_template("CONTRIBUTING.md.j2").render(org=org, repo=repo)}
