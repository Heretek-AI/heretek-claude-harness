"""Tests for counterfactual_diffs_spike.py (#47)."""
import pytest
from pathlib import Path

from scripts.counterfactual_diffs_spike import annotate_diff


def test_annotate_diff_flags_stale_pin():
    """#47: diff pinning requests==2.34.0 produces annotation when 2.35+ exists."""
    diff = "-requests==2.34.0\n"
    if not (Path("catalog/freshness") / "requests.yaml").exists():
        pytest.skip("populate catalog/freshness/requests.yaml first")

    annotated = annotate_diff(diff)
    # Annotation should mention a newer version exists
    assert "latest stable" in annotated.lower() or "counterfactual" in annotated.lower(), \
        f"expected counterfactual annotation, got: {annotated}"


def test_annotate_diff_passes_through_unrelated_changes():
    """#47: diff that doesn't touch deps is passed through unchanged."""
    diff = "+# new comment\n+def foo(): pass\n"
    annotated = annotate_diff(diff)
    assert annotated == diff, "non-dep diff should be passed through unchanged"
