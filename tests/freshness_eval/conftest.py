"""Pytest config for freshness_eval (#38)."""
import pytest


@pytest.fixture(autouse=True)
def freshness_cache_dir():
    """Ensure tests run against the real catalog/freshness/ dir; cleanup is per-test."""
    pass
