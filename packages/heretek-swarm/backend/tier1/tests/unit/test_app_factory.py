"""Tests for tier1.api.app: create_app factory + lifespan."""

from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from tier1.api.app import create_app
from tier1.config import Settings, get_settings


def _new_settings(**overrides) -> Settings:
    """Build a fresh Settings without environment lookup (each test isolation)."""
    get_settings.cache_clear()
    s = Settings(**overrides)
    return s


def test_create_app_default_settings(monkeypatch):
    """create_app() with no args falls back to get_settings() result."""
    get_settings.cache_clear()
    expected = _new_settings()
    monkeypatch.setattr("tier1.api.app.get_settings", lambda: expected)
    with patch("tier1.observability.init_telemetry"):
        app = create_app()
    assert isinstance(app, FastAPI)
    assert app.state.settings is expected


def test_create_app_with_explicit_settings():
    """create_app(settings=...) stores the passed instance on app.state."""
    s = _new_settings(minimax_api_key="explicit-test", redis_url="redis://explicit:6379")
    with patch("tier1.observability.init_telemetry"):
        app = create_app(settings=s)
    assert app.state.settings is s
    assert app.state.settings.redis_url == "redis://explicit:6379"


def _all_paths(app):
    """Walk app.routes (which may include _IncludedRouter) and return every route path."""
    out = set()
    for r in app.routes:
        if hasattr(r, "path"):
            out.add(r.path)
        elif hasattr(r, "original_router"):
            for sr in r.original_router.routes:
                if hasattr(sr, "path"):
                    out.add(sr.path)
    return out


def test_create_app_includes_routers():
    """The three routers (health, deliberations, ws) must be mounted."""
    with patch("tier1.observability.init_telemetry"):
        app = create_app(settings=_new_settings())
    paths = _all_paths(app)
    assert "/health" in paths
    assert any(p.startswith("/api/deliberations") for p in paths)
    assert any(p.startswith("/ws/deliberations") for p in paths)


def test_create_app_mounts_dashboard_when_path_provided(tmp_path):
    """dashboard_path arg drives mount_static(app, dashboard_path)."""
    # Build a real dashboard dir with index.html so mount_static wires routes
    (tmp_path / "index.html").write_text("<html>ok</html>")
    with patch("tier1.observability.init_telemetry") as ot_mock:
        with patch("tier1.api.app.mount_static") as mount_mock:
            app = create_app(settings=_new_settings(), dashboard_path=tmp_path)
    mount_mock.assert_called_once()
    call_args = mount_mock.call_args
    # First positional arg is the app, second (positional or keyword) is the path
    assert call_args.args[0] is app
    assert Path(call_args.args[1]) == tmp_path
    # init_telemetry still got called
    ot_mock.assert_called_once()


def test_create_app_no_dashboard_when_path_none():
    """dashboard_path=None → mount_static is NOT called."""
    with patch("tier1.observability.init_telemetry"):
        with patch("tier1.api.app.mount_static") as mount_mock:
            create_app(settings=_new_settings(), dashboard_path=None)
    mount_mock.assert_not_called()


@asynccontextmanager
async def _fake_lifespan(app):
    """Replaces lifespan to control startup with custom hooks but then runs normal logic by patching connects/closes."""
    yield


def _make_async_client(cls_name="PostgresPool"):
    """Return an AsyncMock double for a client with .connect() and .close()."""
    client = AsyncMock()
    client.connect = AsyncMock(return_value=None)
    client.close = AsyncMock(return_value=None)
    return client


def test_lifespan_opens_all_clients_then_closes_in_reverse():
    """All four connect() calls succeed; close() is called in reverse order."""
    pg, redis, nats, qdrant, garage = (
        AsyncMock(),
        AsyncMock(),
        AsyncMock(),
        MagicMock(),
        MagicMock(),
    )
    qdrant.connect = MagicMock(return_value=None)
    for c in (pg, redis, nats):
        c.connect = AsyncMock(return_value=None)
        c.close = AsyncMock(return_value=None)
    qdrant.close = MagicMock(return_value=None)

    patches = [
        patch("tier1.observability.init_telemetry"),
        patch("tier1.api.app.PostgresPool", return_value=pg),
        patch("tier1.api.app.RedisCache", return_value=redis),
        patch("tier1.api.app.NatsClient", return_value=nats),
        patch("tier1.api.app.QdrantStore", return_value=qdrant),
        patch("tier1.api.app.ModelGarage", return_value=garage),
    ]
    for p in patches:
        p.start()
    try:
        app = create_app(settings=_new_settings())
        with TestClient(app):
            pass
    finally:
        for p in reversed(patches):
            p.stop()

    pg.connect.assert_awaited_once()
    redis.connect.assert_awaited_once()
    nats.connect.assert_awaited_once()
    qdrant.connect.assert_called_once()

    pg.close.assert_awaited_once()
    redis.close.assert_awaited_once()
    nats.close.assert_awaited_once()
    qdrant.close.assert_called_once()


def test_lifespan_closes_partial_set_on_failure():
    """If the 3rd connect (qdrant) raises, the first 3 must close in reverse before re-raise."""
    pg, redis, nats, qdrant = AsyncMock(), AsyncMock(), AsyncMock(), MagicMock()
    pg.connect = AsyncMock(return_value=None)
    pg.close = AsyncMock(return_value=None)
    redis.connect = AsyncMock(return_value=None)
    redis.close = AsyncMock(return_value=None)
    nats.connect = AsyncMock(return_value=None)
    nats.close = AsyncMock(return_value=None)
    qdrant.connect = MagicMock(side_effect=RuntimeError("boom"))
    qdrant.close = MagicMock(return_value=None)
    garage = MagicMock()

    patches = [
        patch("tier1.observability.init_telemetry"),
        patch("tier1.api.app.PostgresPool", return_value=pg),
        patch("tier1.api.app.RedisCache", return_value=redis),
        patch("tier1.api.app.NatsClient", return_value=nats),
        patch("tier1.api.app.QdrantStore", return_value=qdrant),
        patch("tier1.api.app.ModelGarage", return_value=garage),
    ]
    for p in patches:
        p.start()
    try:
        app = create_app(settings=_new_settings())
        with pytest.raises(RuntimeError, match="boom"):
            with TestClient(app):
                pass
    finally:
        for p in reversed(patches):
            p.stop()

    pg.close.assert_awaited_once()
    redis.close.assert_awaited_once()
    nats.close.assert_awaited_once()
    qdrant.close.assert_not_called()


def test_lifespan_stores_clients_in_state():
    """After successful startup, the app.state.* attributes hold the (mocked) clients."""
    import asyncio

    pg, redis, nats, qdrant, garage = (
        AsyncMock(),
        AsyncMock(),
        AsyncMock(),
        MagicMock(),
        MagicMock(),
    )
    for c in (pg, redis, nats):
        c.connect = AsyncMock(return_value=None)
        c.close = AsyncMock(return_value=None)
    qdrant.connect = MagicMock(return_value=None)
    qdrant.close = MagicMock(return_value=None)

    patches = [
        patch("tier1.observability.init_telemetry"),
        patch("tier1.api.app.PostgresPool", return_value=pg),
        patch("tier1.api.app.RedisCache", return_value=redis),
        patch("tier1.api.app.NatsClient", return_value=nats),
        patch("tier1.api.app.QdrantStore", return_value=qdrant),
        patch("tier1.api.app.ModelGarage", return_value=garage),
    ]
    for p in patches:
        p.start()
    try:
        app = create_app(settings=_new_settings())

        async def _drive():
            async with app.router.lifespan_context(app):
                return {
                    "pg": app.state.pg,
                    "redis": app.state.redis,
                    "nats": app.state.nats,
                    "qdrant": app.state.qdrant,
                    "garage": app.state.garage,
                }

        state_map = asyncio.run(_drive())
    finally:
        for p in reversed(patches):
            p.stop()

    assert state_map["pg"] is pg
    assert state_map["redis"] is redis
    assert state_map["nats"] is nats
    assert state_map["qdrant"] is qdrant
    assert state_map["garage"] is garage
