"""Renderer for the tracking layer seeds and the seed-issues.sh script."""

from __future__ import annotations

from pathlib import Path

from jinja2 import Environment, FileSystemLoader, StrictUndefined

_TEMPLATE_DIR = Path(__file__).parents[2] / "templates" / "seeds"


def _env() -> Environment:
    return Environment(
        loader=FileSystemLoader(str(_TEMPLATE_DIR)),
        undefined=StrictUndefined,
        keep_trailing_newline=True,
    )


def render_labels() -> dict[str, str]:
    """Render the child-side labels copy at .github/labels/labels.yaml.

    Per spec §10: the umbrella's seeds/labels.yaml is checked in directly
    and is the canonical source. The child repos only need their own copy
    at ``.github/labels/labels.yaml`` so ``seed-issues.sh --only-labels`` can
    read labels without network access.
    """
    text = _env().get_template("labels.yaml.j2").render()
    return {".github/labels/labels.yaml": text}


_REPO_SEED_SLUGS = ("llama-builds", "heretek-manager")


def render_repo_seed(slug: str) -> dict[str, str]:
    """Render the per-repo seed YAML for the given slug."""
    if slug not in _REPO_SEED_SLUGS:
        raise ValueError(f"unknown repo slug: {slug!r}; expected one of {_REPO_SEED_SLUGS}")
    rendered = _env().get_template(f"{slug}.yaml.j2").render()
    return {f"seeds/{slug}.yaml": rendered}


def render_seed_issues_script(org: str, repo: str, slug: str) -> dict[str, str]:
    """Render the per-child copy of scripts/seed-issues.sh."""
    if slug not in _REPO_SEED_SLUGS:
        raise ValueError(f"unknown repo slug: {slug!r}")
    text = (
        _env()
        .get_template("seed-issues.sh.j2")
        .render(
            org=org,
            repo=repo,
            slug=slug,
        )
    )
    return {"scripts/seed-issues.sh": text}
