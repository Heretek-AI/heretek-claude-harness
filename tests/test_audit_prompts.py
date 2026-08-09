"""Tests for scripts/audit/prompts.py."""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

from audit import prompts  # noqa: E402


def test_all_five_clusters_present() -> None:
    assert set(prompts.CLUSTERS.keys()) == {"A", "B", "C", "D", "E"}


@pytest.mark.parametrize("letter", ["A", "B", "C", "D", "E"])
def test_each_cluster_has_required_fields(letter: str) -> None:
    cp = prompts.CLUSTERS[letter]
    assert cp.letter == letter
    assert cp.title
    assert len(cp.principles) >= 1
    assert cp.evidence_strategy
    assert cp.template
    # Template must mention {repo_root} and {commit_sha}.
    assert "{repo_root}" in cp.template
    assert "{commit_sha}" in cp.template


def test_render_prompt_substitutes_placeholders(tmp_path: Path) -> None:
    rendered = prompts.render_prompt("A", tmp_path, "deadbeef")
    assert str(tmp_path) in rendered
    assert "deadbeef" in rendered


def test_render_prompt_rejects_unknown_letter(tmp_path: Path) -> None:
    with pytest.raises(KeyError):
        prompts.render_prompt("Z", tmp_path, "deadbeef")


def test_cli_prints_prompt(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture
) -> None:
    monkeypatch.setattr(
        sys,
        "argv",
        ["prompts.py", "A", "--repo-root", str(tmp_path), "--commit-sha", "deadbeef"],
    )
    assert prompts.main() == 0
    out = capsys.readouterr().out
    assert "deadbeef" in out
    assert "{repo_root}" not in out  # substituted
