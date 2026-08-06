"""Tests for staleness_metric_spike.py (#49)."""
import pytest
from pathlib import Path

from scripts.staleness_metric_spike import score_for_pins


def test_score_for_pins_with_fresh_pins_is_low():
    """#49: fresh pins score near 0."""
    if not list(Path("catalog/freshness").glob("*.yaml")):
        pytest.skip("populate catalog/freshness/ first")

    pins = {"requests": "2.34.0"}  # assume latest is 2.34+
    score = score_for_pins(pins)
    assert score < 1.0, f"fresh pin should score low, got {score}"


def test_score_for_pins_with_stale_pins_is_high():
    """#49: stale pins score higher than fresh pins."""
    if not list(Path("catalog/freshness").glob("*.yaml")):
        pytest.skip("populate catalog/freshness/ first")

    fresh = score_for_pins({"requests": "2.34.0"})
    stale = score_for_pins({"requests": "2.20.0"})  # 14 minor behind
    assert stale > fresh, f"stale pin should score higher than fresh: {stale} vs {fresh}"
