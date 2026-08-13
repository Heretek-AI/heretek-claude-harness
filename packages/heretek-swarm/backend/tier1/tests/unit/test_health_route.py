"""Tests for /health route — component probes + overall status."""

from __future__ import annotations

from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, MagicMock, patch

from fastapi.testclient import TestClient

from tier1.api.app import create_app


@asynccontextmanager
async def _noop_lifespan(app):
    """Bypass lifespan so TestClient skips real Postgres/Redis/NATS connect."""
    yield


def _build_app_with_state():
    """Build a FastAPI app, replace lifespan, then attach mocks to app.state."""
    with patch("tier1.observability._init_otel"):
        with patch("tier1.observability.init_telemetry"):
            app = create_app()
    app.router.lifespan_context = _noop_lifespan
    pg = AsyncMock()
    redis = AsyncMock()
    nats = AsyncMock()
    qdrant = MagicMock()
    app.state.pg = pg
    app.state.redis = redis
    app.state.nats = nats
    app.state.qdrant = qdrant
    return app, pg, redis, nats, qdrant


def _wire_pg_ok(pg):
    """Wire pg.pool.acquire() as a sync func returning an async CM with a healthy conn."""
    conn = AsyncMock()
    conn.execute = AsyncMock(return_value=None)
    pg_cm = MagicMock()
    pg_cm.__aenter__ = AsyncMock(return_value=conn)
    pg_cm.__aexit__ = AsyncMock(return_value=None)
    pg.pool.acquire = MagicMock(return_value=pg_cm)


def _wire_pg_fail(pg, exc):
    pg_cm = MagicMock()
    pg_cm.__aenter__ = AsyncMock(side_effect=exc)
    pg_cm.__aexit__ = AsyncMock(return_value=None)
    pg.pool.acquire = MagicMock(return_value=pg_cm)


def test_health_all_up():
    """All four components healthy → 200 + status=ok."""
    app, pg, redis, nats, qdrant = _build_app_with_state()
    _wire_pg_ok(pg)
    redis.client.ping = AsyncMock(return_value=True)
    nats.health = AsyncMock(return_value=True)
    qdrant.health = MagicMock(return_value=True)

    with TestClient(app) as client:
        resp = client.get("/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert body["components"]["postgres"]["status"] == "ok"
    assert body["components"]["redis"]["status"] == "ok"
    assert body["components"]["nats"]["status"] == "ok"
    assert body["components"]["qdrant"]["status"] == "ok"


def test_health_postgres_down_but_overall_degraded():
    """Postgres raises → component marked down, overall=degraded."""
    app, pg, redis, nats, qdrant = _build_app_with_state()
    _wire_pg_fail(pg, RuntimeError("pg dead"))
    redis.client.ping = AsyncMock(return_value=True)
    nats.health = AsyncMock(return_value=True)
    qdrant.health = MagicMock(return_value=True)

    with TestClient(app) as client:
        resp = client.get("/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "degraded"
    assert body["components"]["postgres"]["status"] == "down"
    assert "pg dead" in body["components"]["postgres"]["detail"]
    assert body["components"]["redis"]["status"] == "ok"
    assert body["components"]["nats"]["status"] == "ok"


def test_health_redis_down_marks_redis_status_down():
    """Redis ping raises → redis component is 'down', overall degraded."""
    app, pg, redis, nats, qdrant = _build_app_with_state()
    _wire_pg_ok(pg)
    redis.client.ping = AsyncMock(side_effect=ConnectionError("redis gone"))
    nats.health = AsyncMock(return_value=True)
    qdrant.health = MagicMock(return_value=True)

    with TestClient(app) as client:
        resp = client.get("/health")
    body = resp.json()
    assert body["components"]["redis"]["status"] == "down"
    assert "redis gone" in body["components"]["redis"]["detail"]
    assert body["status"] == "degraded"


def test_health_nats_returns_false_marks_down_without_detail():
    """nats.health() returns False → status='down' (no detail, no exception)."""
    app, pg, redis, nats, qdrant = _build_app_with_state()
    _wire_pg_ok(pg)
    redis.client.ping = AsyncMock(return_value=True)
    nats.health = AsyncMock(return_value=False)
    qdrant.health = MagicMock(return_value=True)

    with TestClient(app) as client:
        resp = client.get("/health")
    body = resp.json()
    assert body["components"]["nats"]["status"] == "down"
    assert body["components"]["nats"].get("detail") in (None, "")
    assert body["status"] == "degraded"


def test_health_qdrant_returns_false_marks_down():
    """qdrant.health() returns False → status='down' without exception."""
    app, pg, redis, nats, qdrant = _build_app_with_state()
    _wire_pg_ok(pg)
    redis.client.ping = AsyncMock(return_value=True)
    nats.health = AsyncMock(return_value=True)
    qdrant.health = MagicMock(return_value=False)

    with TestClient(app) as client:
        resp = client.get("/health")
    body = resp.json()
    assert body["components"]["qdrant"]["status"] == "down"
    assert body["status"] == "degraded"


def test_health_advisory_components_unreachable_marked_not_probed():
    """cognee / mem0 URLs unreachable → 'not_probed' (and don't degrade overall)."""
    app, pg, redis, nats, qdrant = _build_app_with_state()
    _wire_pg_ok(pg)
    redis.client.ping = AsyncMock(return_value=True)
    nats.health = AsyncMock(return_value=True)
    qdrant.health = MagicMock(return_value=True)

    with patch("tier1.api.routes.health._probe_http", new=AsyncMock(return_value=False)):
        with TestClient(app) as client:
            resp = client.get("/health")
    body = resp.json()
    assert body["components"]["cognee"]["status"] == "not_probed"
    assert body["components"]["mem0"]["status"] == "not_probed"
    assert body["status"] == "ok"


def test_health_response_shape_is_status_and_components():
    """Top-level response has exactly {status, components} keys."""
    app, pg, redis, nats, qdrant = _build_app_with_state()
    _wire_pg_ok(pg)
    redis.client.ping = AsyncMock(return_value=True)
    nats.health = AsyncMock(return_value=True)
    qdrant.health = MagicMock(return_value=True)

    with TestClient(app) as client:
        resp = client.get("/health")
    assert resp.status_code == 200
    body = resp.json()
    assert set(body.keys()) == {"status", "components"}
    assert "api" in body["components"]
    for name in ("postgres", "redis", "nats", "qdrant", "cognee", "mem0"):
        assert name in body["components"]
