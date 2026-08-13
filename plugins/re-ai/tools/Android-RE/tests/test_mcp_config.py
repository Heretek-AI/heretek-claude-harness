"""Regression tests for the 6th MCP server (``re-library``) in ``.mcp.json``.

These tests load ``.mcp.json`` from the repo root and assert that the
peer MCP integration added by the
``docs/research/2026-06-05-revanced-input-survey.md`` work is wired
correctly end-to-end:

- The 6th server entry is well-formed.
- The server name and command/args match the convention documented
  in ``CLAUDE.md`` and the ``Justfile``.
- The peer is read-only (no destructive flag).
- ``CLAUDE.md`` and ``bin/install.sh`` reference the peer.
- All 5 high-traffic skill SKILL.md files carry the
  "Background reading (peer MCP)" heading.

No network calls. No device. Runs under ``just test``.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
MCP_JSON = REPO_ROOT / ".mcp.json"
CLAUDE_MD = REPO_ROOT / "CLAUDE.md"
INSTALL_SH = REPO_ROOT / "bin" / "install.sh"

EXPECTED_SERVERS = {
    "android-re-static",
    "android-re-native",
    "android-re-dynamic",
    "android-re-triage",
    "android-re-bridge",
    "re-library",
}

FIVE_SKILLS_WITH_BACKGROUND_READING = (
    "android-re-triage-orchestrator",
    "android-re-static-triage",
    "android-re-native-triage",
    "android-re-masvs-report",
    "android-re-secrets-scan",
)

BACKGROUND_READING_HEADING = "## Background reading (peer MCP)"


def _load_mcp_config() -> dict[str, Any]:
    with MCP_JSON.open() as f:
        return json.load(f)


def test_mcp_json_is_valid_json() -> None:
    """``.mcp.json`` parses as JSON."""
    config = _load_mcp_config()
    assert isinstance(config, dict)
    assert "mcpServers" in config


def test_mcp_json_has_six_servers() -> None:
    """All 6 expected servers are present, with no extras."""
    config = _load_mcp_config()
    servers = config["mcpServers"]
    assert set(servers.keys()) == EXPECTED_SERVERS, (
        f"Expected exactly {sorted(EXPECTED_SERVERS)}; got {sorted(servers.keys())}"
    )


def test_re_library_entry_is_well_formed() -> None:
    """The 6th server entry uses the documented ``uv tool run`` shape."""
    config = _load_mcp_config()
    entry = config["mcpServers"]["re-library"]
    assert entry["command"] == "uv", f"expected command=uv, got {entry.get('command')!r}"
    args = entry["args"]
    assert isinstance(args, list)
    # ``uv tool run --from re-library-mcp python -m re_library_mcp``
    assert "tool" in args
    assert "run" in args
    assert "--from" in args
    assert "re-library-mcp" in args
    assert "re_library_mcp" in args


def test_re_library_entry_fqn_matches_table() -> None:
    """The server name (``re-library``) is the FQN prefix documented in CLAUDE.md.

    The FQN prefix is ``mcp__re-library__``; the table row in
    ``CLAUDE.md`` must use the same prefix.
    """
    config = _load_mcp_config()
    assert "re-library" in config["mcpServers"]
    text = CLAUDE_MD.read_text()
    assert "mcp__re-library__" in text, "CLAUDE.md must reference the FQN prefix mcp__re-library__"


def test_no_unused_confirm_arg_in_re_library_entry() -> None:
    """The read-only peer has no destructive flag in its entry."""
    config = _load_mcp_config()
    entry = config["mcpServers"]["re-library"]
    # The peer is read-only by design; the entry must not carry any
    # confirm-gated or destructive flag.
    assert "confirm" not in entry
    assert "env" not in entry or "DESTRUCTIVE" not in str(entry.get("env", ""))


def test_claude_md_mentions_re_library() -> None:
    """``CLAUDE.md`` documents the peer in at least one section."""
    text = CLAUDE_MD.read_text()
    # At minimum: the FQN prefix and the server name.
    assert "re-library" in text
    assert "mcp__re-library__" in text


def test_install_sh_references_re_library() -> None:
    """``bin/install.sh`` knows about the opt-in install step."""
    text = INSTALL_SH.read_text()
    assert "re-library-mcp" in text
    assert "SKIP_RE_LIBRARY" in text


def test_five_skills_have_background_reading() -> None:
    """All 5 high-traffic skills carry the Background reading heading."""
    missing: list[str] = []
    for skill_name in FIVE_SKILLS_WITH_BACKGROUND_READING:
        skill_md = REPO_ROOT / "skills" / skill_name / "SKILL.md"
        if not skill_md.exists():
            missing.append(f"{skill_name}/SKILL.md (file not found)")
            continue
        text = skill_md.read_text()
        if BACKGROUND_READING_HEADING not in text:
            missing.append(f"{skill_name}/SKILL.md (no '{BACKGROUND_READING_HEADING}' heading)")
    assert not missing, (
        "The following skills are missing the Background reading subsection: " + "; ".join(missing)
    )


def test_justfile_has_install_re_library_recipe() -> None:
    """The ``Justfile`` has the opt-in install recipe."""
    text = (REPO_ROOT / "Justfile").read_text()
    assert "install-re-library:" in text
    assert "uv tool install re-library-mcp" in text
    assert "dev-re-library:" in text


@pytest.mark.parametrize(
    "skill_name",
    FIVE_SKILLS_WITH_BACKGROUND_READING,
    ids=FIVE_SKILLS_WITH_BACKGROUND_READING,
)
def test_each_skill_links_re_library_tools(skill_name: str) -> None:
    """Each cross-linked skill lists the 3 ``mcp__re-library__*`` tools it uses."""
    skill_md = REPO_ROOT / "skills" / skill_name / "SKILL.md"
    if not skill_md.exists():
        pytest.skip(f"{skill_name}/SKILL.md not present")
    text = skill_md.read_text()
    for tool in (
        "mcp__re-library__list_categories()",
        "mcp__re-library__search_re(",
        "mcp__re-library__get_entry(",
    ):
        assert tool in text, f"{skill_name}/SKILL.md must reference {tool!r}"


def test_research_review_document_exists() -> None:
    """The survey review document is committed alongside the implementation."""
    review = REPO_ROOT / "docs" / "research" / "2026-06-05-revanced-input-survey.md"
    assert review.exists(), f"expected review document at {review}"
    text = review.read_text()
    # Smoke check: the document is substantive, not a stub.
    assert len(text) > 4000, "review document looks like a stub"
    assert "clean-room" in text
    assert "RE-Library" in text
