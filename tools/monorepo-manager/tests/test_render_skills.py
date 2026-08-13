"""Tests for the skills renderer."""

from __future__ import annotations

import json

import pytest

from scripts.lib.render_skills import render_skills


@pytest.fixture
def skills():
    return [
        {
            "name": "heretek-strix-halo-audit",
            "description": "Audit host hardware and recommend backend.",
            "allowed_tools": ["Bash"],
            "required_skills": [],
            "body": "1. shell out to nvidia-smi/rocminfo/vulkaninfo\n2. parse output\n3. recommend backend",
        },
        {
            "name": "heretek-symlink-swap",
            "description": "Apply the atomic symlink swap recipe.",
            "allowed_tools": ["Bash", "Edit"],
            "required_skills": [],
            "body": "1. write to a temp symlink\n2. rename atomically",
        },
    ]


def test_render_skills_returns_manifest_and_skill_files(skills):
    files = render_skills(skills)
    assert ".claude/skills/manifest.json" in files
    assert ".claude/skills/heretek-strix-halo-audit/SKILL.md" in files
    assert ".claude/skills/heretek-symlink-swap/SKILL.md" in files


def test_render_skills_manifest_lists_names(skills):
    files = render_skills(skills)
    manifest = json.loads(files[".claude/skills/manifest.json"])
    assert {s["name"] for s in manifest["skills"]} == {
        "heretek-strix-halo-audit",
        "heretek-symlink-swap",
    }


def test_render_skills_skill_md_has_frontmatter(skills):
    files = render_skills(skills)
    md = files[".claude/skills/heretek-strix-halo-audit/SKILL.md"]
    assert md.startswith("---\n")
    assert "name: heretek-strix-halo-audit" in md
    assert "description: Audit host hardware" in md


def test_render_skills_skill_md_includes_body(skills):
    files = render_skills(skills)
    md = files[".claude/skills/heretek-symlink-swap/SKILL.md"]
    assert "temp symlink" in md
