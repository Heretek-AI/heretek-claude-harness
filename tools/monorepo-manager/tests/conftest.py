"""Pytest fixtures shared across the umbrella test suite."""

from __future__ import annotations

import pathlib
import sys

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]


@pytest.fixture(scope="session")
def repo_root() -> pathlib.Path:
    return ROOT


@pytest.fixture(scope="session")
def scripts_dir() -> pathlib.Path:
    return ROOT / "scripts"


@pytest.fixture(scope="session")
def schemas_dir() -> pathlib.Path:
    return ROOT / "schemas"


@pytest.fixture(scope="session")
def templates_dir() -> pathlib.Path:
    return ROOT / "templates"


@pytest.fixture(scope="session")
def tests_dir() -> pathlib.Path:
    return ROOT / "tests"


# Make `scripts.lib` importable as a top-level package.
sys.path.insert(0, str(ROOT / "scripts"))
