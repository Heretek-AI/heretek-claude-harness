"""Pytest config for freshness_eval (#38)."""

import pytest
from pathlib import Path

CACHE_DIR = Path("catalog/freshness")


def pytest_collection_modifyitems(config, items):
    """Skip freshness_eval tests if catalog/freshness/ is not populated."""
    if not any(CACHE_DIR.glob("*.yaml")):
        skip_marker = pytest.mark.skip(
            reason="catalog/freshness/ not populated; run scripts.freshness_index --all first"
        )
        for item in items:
            if "freshness_eval" in str(item.fspath):
                item.add_marker(skip_marker)
