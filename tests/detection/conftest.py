"""Pytest config for detection tests."""
import shutil
import pytest


def pytest_collection_modifyitems(config, items):
    """Skip detection tests if ast-grep is not installed."""
    if not shutil.which("ast-grep"):
        skip = pytest.mark.skip(reason="ast-grep CLI not on PATH")
        for item in items:
            if "detection" in str(item.fspath):
                item.add_marker(skip)
