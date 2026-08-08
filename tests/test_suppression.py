"""Tests for scripts/suppression.py — false-positive suppression per spec §8.7."""
from __future__ import annotations

from pathlib import Path

from scripts.suppression import is_suppressed, load_suppressions


def test_load_suppressions_returns_empty_when_dir_missing(tmp_path: Path) -> None:
    """No reviews dir → empty set, no errors."""
    assert load_suppressions(tmp_path / "nope") == set()


def test_load_suppressions_parses_single_file(tmp_path: Path) -> None:
    reviews = tmp_path / "reviews"
    reviews.mkdir()
    (reviews / "context7.md").write_text(
        """# ADR

`<!-- suppress: skillspector:prompt-injection -->`

This is a known false-positive.
"""
    )
    sup = load_suppressions(reviews)
    assert sup == {("skillspector", "prompt-injection")}


def test_load_suppressions_collects_multiple_files(tmp_path: Path) -> None:
    reviews = tmp_path / "reviews"
    reviews.mkdir()
    (reviews / "a.md").write_text("<!-- suppress: skillspector:R1 -->\n<!-- suppress: socket:R2 -->\n")
    (reviews / "b.md").write_text("<!-- suppress: virustotal:vt-verdict -->\n")
    sup = load_suppressions(reviews)
    assert ("skillspector", "R1") in sup
    assert ("socket", "R2") in sup
    assert ("virustotal", "vt-verdict") in sup
    assert len(sup) == 3


def test_load_suppressions_ignores_non_md_files(tmp_path: Path) -> None:
    reviews = tmp_path / "reviews"
    reviews.mkdir()
    (reviews / "ignore.txt").write_text("<!-- suppress: skillspector:R1 -->")
    (reviews / "a.md").write_text("<!-- suppress: skillspector:R2 -->")
    sup = load_suppressions(reviews)
    assert sup == {("skillspector", "R2")}


def test_load_suppressions_skips_malformed_comments(tmp_path: Path) -> None:
    """Malformed suppress comments don't crash — they're just ignored."""
    reviews = tmp_path / "reviews"
    reviews.mkdir()
    (reviews / "a.md").write_text(
        """<!-- suppress: skillspector:R1 -->
<!-- suppress: malformed-no-colon -->
<!-- suppress: another:bad char -->
<!-- suppress: skillspector:R2 -->
"""
    )
    sup = load_suppressions(reviews)
    # First and last parse; the middle ones don't match the regex.
    assert ("skillspector", "R1") in sup
    assert ("skillspector", "R2") in sup


def test_is_suppressed_matches_scanner_and_rule() -> None:
    sup = {("skillspector", "R1"), ("socket", "R2")}
    assert is_suppressed(sup, scanner="skillspector", rule_id="R1") is True
    assert is_suppressed(sup, scanner="skillspector", rule_id="OTHER") is False
    assert is_suppressed(sup, scanner="unknown", rule_id="R1") is False


def test_is_suppressed_rejects_none_rule_id() -> None:
    """Anonymous findings (rule_id=None) are NEVER silently suppressed —
    require an explicit ID to prevent accidentally dropping unknown rules."""
    sup = {("skillspector", "R1")}
    assert is_suppressed(sup, scanner="skillspector", rule_id=None) is False