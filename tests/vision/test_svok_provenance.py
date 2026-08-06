"""Tests for svok_provenance_spike.py (#48)."""
import pytest
from pathlib import Path

from scripts.svok_provenance_spike import emit_provenance_comments


def test_emit_provenance_for_yaml_safe_load():
    """#48: code using yaml.safe_load gets provenance comment for pyyaml."""
    code = "import yaml\ndata = yaml.safe_load(f)\n"
    if not (Path("catalog/freshness") / "pyyaml.yaml").exists():
        pytest.skip("populate catalog/freshness/pyyaml.yaml first")

    annotated = emit_provenance_comments(code)
    assert "pyyaml" in annotated
    assert "generated against" in annotated or "docs v" in annotated.lower()


def test_emit_provenance_unchanged_for_pure_stdlib():
    """#48: code with no external API gets passed through (no provenance comments)."""
    code = "x = [1, 2, 3]\nprint(sum(x))\n"
    annotated = emit_provenance_comments(code)
    # Either identical, or only minor formatting
    assert annotated == code or "generated against" not in annotated
