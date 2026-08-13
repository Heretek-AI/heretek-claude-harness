"""Tests for the configs renderer (lint, pre-commit, sonar, gitleaks)."""

from __future__ import annotations

import json

import yaml

from scripts.lib.render_configs import render_configs


def test_render_configs_returns_all_expected_files():
    files = render_configs(
        "python", sonar_key="Heretek-AI_llama-builds", project_name="llama-builds"
    )
    assert ".github/linters/python-ruff.yml" in files
    assert ".pre-commit-config.yaml" in files
    assert "sonar-project.properties" in files
    assert ".github/gitleaks-config.yml" in files
    assert ".gitleaks-baseline.json" in files


def test_render_configs_sonar_properties_has_required_keys():
    files = render_configs(
        "python", sonar_key="Heretek-AI_llama-builds", project_name="llama-builds"
    )
    props = files["sonar-project.properties"]
    assert "sonar.projectKey=Heretek-AI_llama-builds" in props
    assert "sonar.organization=heretek-ai" in props


def test_render_configs_pre_commit_python_no_eslint():
    files = render_configs("python", sonar_key="x", project_name="x")
    parsed = yaml.safe_load(files[".pre-commit-config.yaml"])
    repo_ids = [h["id"] for r in parsed["repos"] for h in r["hooks"]]
    assert "eslint" not in repo_ids
    assert "ruff" in repo_ids


def test_render_configs_pre_commit_node_has_eslint():
    files = render_configs("node", sonar_key="x", project_name="x")
    parsed = yaml.safe_load(files[".pre-commit-config.yaml"])
    repo_ids = [h["id"] for r in parsed["repos"] for h in r["hooks"]]
    assert "eslint" in repo_ids


def test_render_configs_gitleaks_baseline_is_valid_json():
    files = render_configs("python", sonar_key="x", project_name="x")
    parsed = json.loads(files[".gitleaks-baseline.json"])
    assert parsed["version"] == "1"
