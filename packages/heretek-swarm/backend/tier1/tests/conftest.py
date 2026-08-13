"""Shared pytest fixtures."""

from __future__ import annotations

import os

import pytest
from fastapi.testclient import TestClient

from tier1.api.app import create_app


@pytest.fixture(scope="session")
def app():
    from unittest.mock import patch

    with patch("tier1.observability._init_otel"):
        return create_app()


@pytest.fixture()
def client(app):
    with TestClient(app) as c:
        yield c


@pytest.fixture(autouse=True)
def _clear_settings_cache(monkeypatch):
    """Each test sees a fresh Settings (env-vars set via monkeypatch)."""
    from tier1.config import get_settings

    get_settings.cache_clear()
    yield
    get_settings.cache_clear()
