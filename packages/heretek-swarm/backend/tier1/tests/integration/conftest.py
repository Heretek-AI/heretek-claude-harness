"""Shared fixtures for integration tests.

Skips smoke tests when TIER1_MINIMAX_API_KEY is unset. Behavior tests are not
skipped here — they replay cassettes and always run.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest


# pydantic-settings prefix: TIER1_MINIMAX_API_KEY
MINIMAX_ENV_VAR = "TIER1_MINIMAX_API_KEY"

CASSETTE_DIR = Path(__file__).parent / "behavior" / "cassettes"


@pytest.fixture(scope="session")
def cassette_dir() -> Path:
    """Directory where vcrpy cassettes are stored."""
    CASSETTE_DIR.mkdir(parents=True, exist_ok=True)
    return CASSETTE_DIR


@pytest.fixture(scope="session")
def record_mode() -> str:
    """`record` when RECORD_MINIMAX=1, else `none` (replay-only).

    Replay-only mode means missing cassettes fail loudly in CI rather than
    silently auto-recording against a real API.
    """
    return "once" if os.environ.get("RECORD_MINIMAX") == "1" else "none"


@pytest.fixture(scope="session")
def minimax_api_key() -> str | None:
    """The MiniMax API key, or None if not configured."""
    return os.environ.get(MINIMAX_ENV_VAR)


@pytest.fixture()
def require_minimax_key(minimax_api_key: str | None) -> str:
    """Skip the test if `TIER1_MINIMAX_API_KEY` is not set.

    Used by smoke tests that hit the live API. Behavior tests use the
    cassette fixture instead and don't need a live key.
    """
    if not minimax_api_key:
        pytest.skip(f"{MINIMAX_ENV_VAR} not set; skipping live integration test")
    return minimax_api_key
