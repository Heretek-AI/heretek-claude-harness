"""AGENTS.md contract validation."""

from __future__ import annotations

import textwrap

from scripts.lib.validate_agents import validate_agents


def _write(tmp_path, body: str) -> str:
    p = tmp_path / "AGENTS.md"
    p.write_text(textwrap.dedent(body))
    return str(p)


def _valid_body() -> str:
    return """\
    # sample

    ## Project summary
    one paragraph

    ## Stack & runtime targets
    python 3.11

    ## Build, test, lint, run commands
    pytest

    ## Project structure
    tree

    ## Conventions
    ruff

    ## Do / Don't list
    do this

    ## Pointer block
    links
    """


def test_validate_agents_accepts_well_formed(tmp_path):
    v = validate_agents(_write(tmp_path, _valid_body()))
    assert v == []


def test_validate_agents_rejects_missing_section(tmp_path):
    body = textwrap.dedent(_valid_body()).replace("## Do / Don't list\ndo this\n", "")
    v = validate_agents(_write(tmp_path, body))
    assert any("Do / Don't list" in s for s in v)


def test_validate_agents_rejects_duplicate_section(tmp_path):
    body = textwrap.dedent(_valid_body()) + "\n## Project summary\ndup\n"
    v = validate_agents(_write(tmp_path, body))
    assert any("duplicate" in s.lower() for s in v)


def test_validate_agents_rejects_empty_section(tmp_path):
    body = textwrap.dedent(_valid_body()).replace(
        "## Pointer block\nlinks\n", "## Pointer block\n\n"
    )
    v = validate_agents(_write(tmp_path, body))
    assert any("Pointer block" in s for s in v)
