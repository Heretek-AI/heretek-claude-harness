"""Tests for .claude/skills/<name>/SKILL.md contract validation."""

from __future__ import annotations

import textwrap

from scripts.lib.validate_skills import validate_skill


def _write_skill(tmp_path, body: str, name: str = "heretek-example") -> str:
    d = tmp_path / ".claude" / "skills" / name
    d.mkdir(parents=True)
    (d / "SKILL.md").write_text(textwrap.dedent(body))
    return str(d)


def _valid_body() -> str:
    return """\
    ---
    name: heretek-example
    description: Example skill.
    ---

    # heretek-example

    Use this skill when ...
    """


def test_validate_skill_accepts_well_formed(tmp_path):
    assert validate_skill(_write_skill(tmp_path, _valid_body())) == []


def test_validate_skill_rejects_missing_frontmatter(tmp_path):
    v = validate_skill(_write_skill(tmp_path, "# no frontmatter\n"))
    assert any("frontmatter" in s.lower() for s in v)


def test_validate_skill_rejects_missing_name(tmp_path):
    body = "---\ndescription: x\n---\n# n"
    v = validate_skill(_write_skill(tmp_path, body))
    assert any("name" in s for s in v)


def test_validate_skill_rejects_short_description(tmp_path):
    body = "---\nname: heretek-example\ndescription: \n---\n# n"
    v = validate_skill(_write_skill(tmp_path, body))
    assert any("description" in s for s in v)


def test_validate_skill_rejects_name_directory_mismatch(tmp_path):
    v = validate_skill(_write_skill(tmp_path, _valid_body(), name="different-name"))
    assert any("mismatch" in s.lower() for s in v)
