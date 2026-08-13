"""Tests for the seed renderer (templates → seeds/*.yaml + scripts/seed-issues.sh)."""

from __future__ import annotations

from scripts.lib import render_seed


def test_render_labels_returns_canonical_labels_yaml():
    files = render_seed.render_labels()
    # Per spec §10: render_labels only emits the child-side copy. The
    # umbrella's seeds/labels.yaml is checked in directly (canonical source).
    assert "seeds/labels.yaml" not in files
    assert ".github/labels/labels.yaml" in files
    text = files[".github/labels/labels.yaml"]
    assert "schema_version: 1" in text
    for label in (
        "phase/1-ci-setup",
        "phase/2-cli-runtime",
        "phase/3-webui",
        "phase/4-matrix-pkg",
        "phase/meta",
        "component/ci",
        "component/manifest",
        "component/auditor",
        "component/symlink",
        "component/upstream-sync",
        "component/webui",
        "component/api",
        "component/store",
        "component/infra",
        "component/manager",
        "component/docs",
        "status/backlog",
        "status/in-progress",
        "status/blocked",
        "status/review",
        "status/done",
    ):
        assert label in text, f"missing label: {label}"


def test_render_labels_is_byte_identical_on_repeat():
    a = render_seed.render_labels()
    b = render_seed.render_labels()
    assert a == b


def test_render_repo_seed_llama_builds_has_at_least_25_issues():
    files = render_seed.render_repo_seed("llama-builds")
    assert "seeds/llama-builds.yaml" in files
    text = files["seeds/llama-builds.yaml"]
    # Crude count: one "- id:" per issue entry.
    assert text.count("- id:") >= 25, f"expected ≥25 issues, got {text.count('- id:')}"
    assert "schema_version: 1" in text
    assert "repo: Heretek-AI/llama-builds" in text


def test_render_repo_seed_heretek_manager_has_at_least_25_issues():
    files = render_seed.render_repo_seed("heretek-manager")
    assert "seeds/heretek-manager.yaml" in files
    text = files["seeds/heretek-manager.yaml"]
    assert text.count("- id:") >= 25
    assert "repo: Heretek-AI/heretek-manager" in text


def test_render_repo_seed_uses_correct_id_prefix():
    lb = render_seed.render_repo_seed("llama-builds")
    hm = render_seed.render_repo_seed("heretek-manager")
    assert "id: lb-" in lb["seeds/llama-builds.yaml"]
    assert "id: hm-" in hm["seeds/heretek-manager.yaml"]


def test_render_seed_issues_script_is_a_bash_script_with_correct_defaults():
    files = render_seed.render_seed_issues_script(
        org="Heretek-AI", repo="llama-builds", slug="llama-builds"
    )
    assert "scripts/seed-issues.sh" in files
    text = files["scripts/seed-issues.sh"]
    assert text.startswith("#!/usr/bin/env bash")
    assert "set -euo pipefail" in text
    assert "Heretek-AI/llama-builds" in text
    assert "seed-issues.sh" in text


def test_render_seed_issues_script_uses_one_shot_discovery_with_limit_1000():
    """Fix #8: discovery must hoist to a single `gh issue list --limit 1000`."""
    files = render_seed.render_seed_issues_script(
        org="Heretek-AI", repo="llama-builds", slug="llama-builds"
    )
    text = files["scripts/seed-issues.sh"]
    # Single hoisted call (not a per-issue loop).
    assert "--limit 1000" in text


def test_render_seed_issues_script_accepts_labels_file_flag():
    """Fix #3: --labels-file flag for label sync, defaulting to .github/labels/labels.yaml."""
    files = render_seed.render_seed_issues_script(
        org="Heretek-AI", repo="llama-builds", slug="llama-builds"
    )
    text = files["scripts/seed-issues.sh"]
    assert "--labels-file" in text
    assert ".github/labels/labels.yaml" in text


def test_render_seed_issues_script_is_self_contained_no_python_seed_loader_import():
    """Fix #2: generated child scripts must not import scripts.lib.seed_loader."""
    files = render_seed.render_seed_issues_script(
        org="Heretek-AI", repo="llama-builds", slug="llama-builds"
    )
    text = files["scripts/seed-issues.sh"]
    assert "from scripts.lib.seed_loader" not in text
    assert "python -m scripts.lib.seed_loader" not in text


def test_render_repo_seed_source_doc_uses_design_doc_for_phases_1_to_3_and_meta():
    """Fix #9: source.doc references the design doc for phases 1-3 + meta."""
    import re

    files = render_seed.render_repo_seed("llama-builds")
    text = files["seeds/llama-builds.yaml"]
    # Slice the file into per-phase blocks using the actual `phase: phase/N`
    # entries so the phase-comment headers don't get confused for the body.
    sections = re.split(r"^  - id:", text, flags=re.MULTILINE)
    phase_1_block = "\n- id:".join(sections[1:8])  # 6 phase 1 issues
    phase_4_block = "\n- id:".join(sections[8:])  # remaining issues (phase 4 + meta)
    assert (
        "Write out a design doc for the project.md" in phase_1_block
    ), "phase 1 issues must reference the project design doc"
    assert (
        "Llama Ecosystem Repository Analysis.md" in phase_4_block
    ), "phase 4 issues must reference the ecosystem analysis doc"
    assert (
        "Write out a design doc for the project.md" in phase_4_block
    ), "phase/meta issues must also reference the project design doc"
