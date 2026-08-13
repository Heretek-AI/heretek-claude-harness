"""Tests for /api/deliberations endpoints."""

from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi.testclient import TestClient

from tier1.api.app import create_app
from tier1.deliberation.state import DeliberationEvent, initial_state, now_ts


def _make_state(did="test-did", problem="test problem", status="running"):
    state = initial_state(deliberation_id=did, problem=problem)
    state["status"] = status
    return state


@asynccontextmanager
async def _noop_lifespan(app):
    yield


@pytest.fixture()
def deliberation_client():
    from unittest.mock import patch

    with patch("tier1.observability._init_otel"):
        app = create_app()
    # Replace lifespan so TestClient doesn't try to connect to real Postgres/Redis/NATS.
    app.router.lifespan_context = _noop_lifespan
    pg = AsyncMock()
    redis = AsyncMock()
    nats = AsyncMock()
    garage = MagicMock()
    app.state.pg = pg
    app.state.redis = redis
    app.state.nats = nats
    app.state.garage = garage
    with TestClient(app) as c:
        yield c, pg, redis, nats, garage


async def test_list_deliberations(deliberation_client):
    client, pg, *_ = deliberation_client
    pg.list_deliberations = AsyncMock(return_value=[])
    resp = client.get("/api/deliberations")
    assert resp.status_code == 200
    assert resp.json()["items"] == []


async def test_get_deliberation(deliberation_client):
    client, pg, *_ = deliberation_client
    state = _make_state()
    pg.load_deliberation = AsyncMock(return_value=state)
    pg.get_events = AsyncMock(return_value=state["events"])
    resp = client.get("/api/deliberations/test-did")
    assert resp.status_code == 200
    body = resp.json()
    assert body["id"] == "test-did"
    assert body["problem"] == "test problem"
    assert body["status"] == "running"


async def test_get_deliberation_404(deliberation_client):
    client, pg, *_ = deliberation_client
    pg.load_deliberation = AsyncMock(return_value=None)
    resp = client.get("/api/deliberations/nonexistent")
    assert resp.status_code == 404


async def test_interject(deliberation_client):
    client, pg, redis, nats, *_ = deliberation_client
    state = _make_state()
    pg.load_deliberation = AsyncMock(return_value=state)
    pg.save_deliberation = AsyncMock()
    pg.append_event = AsyncMock()
    nats.publish = AsyncMock()
    resp = client.post(
        "/api/deliberations/test-did/interject",
        json={"text": "focus on cost"},
    )
    assert resp.status_code == 204
    pg.save_deliberation.assert_called_once()


async def test_interject_404(deliberation_client):
    client, pg, *_ = deliberation_client
    pg.load_deliberation = AsyncMock(return_value=None)
    resp = client.post(
        "/api/deliberations/nonexistent/interject",
        json={"text": "hi"},
    )
    assert resp.status_code == 404


async def test_interject_wrong_status(deliberation_client):
    client, pg, *_ = deliberation_client
    state = _make_state(status="completed")
    pg.load_deliberation = AsyncMock(return_value=state)
    resp = client.post(
        "/api/deliberations/test-did/interject",
        json={"text": "hi"},
    )
    assert resp.status_code == 409
