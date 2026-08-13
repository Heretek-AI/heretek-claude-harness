"""Tests for the AGENTS.md + CLAUDE.md renderer."""

from __future__ import annotations

import pytest

from scripts.lib.render_agents import render_agents


@pytest.fixture
def params() -> dict:
    return {
        "name": "llama-builds",
        "stack": "python",
        "language": "Python 3.11+",
        "package_manager": "pip, setuptools",
        "os_arch": "Linux x86_64",
        "project_summary": "CI/CD registry for llama.cpp family builds.",
        "build_cmd": "python -m build",
        "test_cmd": "pytest",
        "lint_cmd": "ruff check .",
        "run_cmd": "python -m heretek_builds --help",
        "sonar_key": "Heretek-AI_llama-builds",
        "project_url": "https://github.com/orgs/Heretek-AI/projects/1",
        "super_linter_config_path": ".github/linters/",
    }


def test_render_agents_returns_both_files(params):
    out = render_agents(params)
    assert set(out.keys()) == {"AGENTS.md", "CLAUDE.md"}


def test_render_agents_includes_all_seven_sections(params):
    md = render_agents(params)["AGENTS.md"]
    for section in [
        "Project summary",
        "Stack & runtime targets",
        "Build, test, lint, run commands",
        "Project structure",
        "Conventions",
        "Do / Don't list",
        "Pointer block",
    ]:
        assert f"## {section}" in md


def test_render_agents_substitutes_params(params):
    md = render_agents(params)["AGENTS.md"]
    assert "llama-builds" in md
    assert "Linux x86_64" in md


def test_render_agents_claude_md_references_agents_md(params):
    claude = render_agents(params)["CLAUDE.md"]
    assert "AGENTS.md" in claude


def test_render_agents_includes_seed_url_bullet_when_provided():
    files = render_agents(
        {
            "name": "llama-builds",
            "stack": "python",
            "language": "Python 3.11+",
            "package_manager": "pip, setuptools",
            "os_arch": "Linux x86_64",
            "project_summary": "CI/CD registry.",
            "build_cmd": "python -m build",
            "test_cmd": "pytest",
            "lint_cmd": "ruff check .",
            "run_cmd": "python -m heretek_builds --help",
            "sonar_key": "Heretek-AI_llama-builds",
            "project_url": "https://github.com/orgs/Heretek-AI/projects/1",
            "super_linter_config_path": ".github/linters/",
            "seed_url": "https://github.com/Heretek-AI/monorepo-manager/blob/main/seeds/llama-builds.yaml",
        }
    )
    agents = files["AGENTS.md"]
    assert (
        "Backlog seed: https://github.com/Heretek-AI/monorepo-manager/blob/main/seeds/llama-builds.yaml"
        in agents
    )


def test_render_agents_omits_seed_url_bullet_when_not_provided():
    files = render_agents(
        {
            "name": "monorepo-manager",
            "stack": "python",
            "language": "Python 3.11+",
            "package_manager": "pip, setuptools",
            "os_arch": "Linux x86_64",
            "project_summary": "Umbrella.",
            "build_cmd": "pip install -e .[dev]",
            "test_cmd": "pytest",
            "lint_cmd": "ruff check .",
            "run_cmd": "scripts/init-harness.sh",
            "sonar_key": "Heretek-AI_monorepo-manager",
            "project_url": "",
            "super_linter_config_path": ".github/linters/",
            # no seed_url
        }
    )
    assert "Backlog seed:" not in files["AGENTS.md"]
