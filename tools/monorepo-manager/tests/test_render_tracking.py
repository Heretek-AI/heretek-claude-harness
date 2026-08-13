"""Tests for the tracking-layer renderer."""

from __future__ import annotations

from scripts.lib.render_tracking import (
    render_contributing,
    render_issue_templates,
    render_labeler,
    render_pr_template,
    render_project_automation,
)


def test_render_issue_templates_returns_six_templates_and_config():
    files = render_issue_templates(org="Heretek-AI", repo="llama-builds")
    assert ".github/ISSUE_TEMPLATE/config.yml" in files
    for name in ("bug", "feature", "security", "refactor", "infra-tooling", "spec"):
        assert f".github/ISSUE_TEMPLATE/{name}.md" in files


def test_render_issue_templates_bug_has_required_fields():
    files = render_issue_templates(org="Heretek-AI", repo="llama-builds")
    bug = files[".github/ISSUE_TEMPLATE/bug.md"]
    assert "## Environment" in bug
    assert "## Repro" in bug
    assert "## Logs" in bug


def test_render_issue_templates_config_references_org_repo():
    files = render_issue_templates(org="Heretek-AI", repo="llama-builds")
    cfg = files[".github/ISSUE_TEMPLATE/config.yml"]
    assert "Heretek-AI/llama-builds" in cfg


def test_render_pr_template_has_checklist():
    files = render_pr_template()
    pr = files[".github/PULL_REQUEST_TEMPLATE.md"]
    for item in ("pre-commit", "Super-linter", "SonarCloud", "Gitleaks"):
        assert item in pr


def test_render_project_automation_substitutes_project_id():
    files = render_project_automation(org="Heretek-AI", repo="llama-builds", project_id="PVT_123")
    assert "PVT_123" in files[".github/projects-automation.graphql"]


def test_render_labeler_has_area_labels():
    files = render_labeler()
    text = files[".github/labeler.yml"]
    assert "area/build" in text
    assert "area/infra" in text


def test_render_contributing_references_org_repo():
    files = render_contributing(org="Heretek-AI", repo="llama-builds")
    assert "llama-builds" in files["CONTRIBUTING.md"]
