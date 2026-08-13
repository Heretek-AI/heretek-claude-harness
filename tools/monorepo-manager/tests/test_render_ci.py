"""Tests for the CI workflow renderer."""

from __future__ import annotations

import yaml

from scripts.lib.render_ci import render_ci


def test_render_ci_returns_four_workflows():
    files = render_ci("python", test_cmd="pytest")
    assert set(files.keys()) == {
        ".github/workflows/super-linter.yml",
        ".github/workflows/pre-commit.yml",
        ".github/workflows/sonarcloud.yml",
        ".github/workflows/secret-scan.yml",
    }


def test_render_ci_python_enables_python_linter():
    files = render_ci("python", test_cmd="pytest")
    parsed = yaml.safe_load(files[".github/workflows/super-linter.yml"])
    assert parsed["jobs"]["super-linter"]["steps"][1]["env"]["VALIDATE_PYTHON"] == "true"


def test_render_ci_node_enables_javascript_linter():
    files = render_ci("node", test_cmd="npm test")
    parsed = yaml.safe_load(files[".github/workflows/super-linter.yml"])
    env = parsed["jobs"]["super-linter"]["steps"][1]["env"]
    assert env["VALIDATE_JAVASCRIPT"] == "true"
    assert env["VALIDATE_TYPESCRIPT"] == "true"


def test_render_ci_sonarcloud_workflow_runs_test_cmd():
    files = render_ci("python", test_cmd="pytest")
    parsed = yaml.safe_load(files[".github/workflows/sonarcloud.yml"])
    text = yaml.safe_dump(parsed)
    assert "pytest" in text
