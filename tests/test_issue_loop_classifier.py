"""Tests for scripts/issue_loop/classifier.py."""

from __future__ import annotations

import typing

from scripts.issue_loop.classifier import Path, classify
from scripts.issue_loop.ledger import IssueRef


def test_fix_path_when_body_has_file_line_and_small_fix_words():
    issue = IssueRef(
        number=158,
        title="Security: yaml.load without Loader in scripts/catalog_updater.py:81",
        files=["scripts/catalog_updater.py"],
    )
    body = (
        "Found `yaml.load(...)` call at `scripts/catalog_updater.py:81`. Fix: use yaml.safe_load."
    )
    assert classify(issue, body=body) == "fix"


def test_fix_path_requires_both_anchor_and_fix_keyword():
    issue = IssueRef(number=1, title="x", files=[])
    # anchor but no fix keyword
    assert classify(issue, body="see `scripts/x.py:42` for context") == "investigate"
    # fix keyword but no anchor
    assert classify(issue, body="please patch the catalog parser") == "investigate"


def test_spec_path_when_body_has_design_keywords_no_anchor():
    issue = IssueRef(number=176, title="docs(research): MVP-1 Codegen fan-out", files=[])
    body = "Deep research shows two MCP targets. Design a plugin scaffolding flow with audit and research scope."
    assert classify(issue, body=body) == "spec"


def test_break_down_path_when_body_has_phase_or_checklist():
    issue = IssueRef(number=89, title="v2: hooks hardening + security", files=[])
    body = "Phase scope with sub-tasks: graceful truncation, JSON parsing, checkpoint commits. Split into phases."
    assert classify(issue, body=body) == "break-down"


def test_skip_path_when_body_marks_duplicate_or_wontfix():
    issue = IssueRef(number=99, title="duplicate of #50", files=[])
    body = "Won't fix, by design. Duplicate of #50."
    assert classify(issue, body=body) == "skip"


def test_default_path_is_investigate():
    issue = IssueRef(number=200, title="Improve error message in CLI", files=[])
    body = "When the user passes a bad flag, the error is unclear."
    assert classify(issue, body=body) == "investigate"


def test_path_enum_values_are_stable():
    values = set(typing.get_args(Path))
    assert values == {"fix", "investigate", "spec", "break-down", "skip"}


def test_empty_body_classifies_as_investigate():
    issue = IssueRef(number=1, title="x", files=[])
    assert classify(issue, body="") == "investigate"
