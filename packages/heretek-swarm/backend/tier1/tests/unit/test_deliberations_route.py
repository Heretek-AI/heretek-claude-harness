"""Tests for /api/deliberations router: create, get, interject, list."""

from __future__ import annotations

from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from tier1.api.app import create_app
from tier1.deliberation.state import (
    DeliberationEvent,
    initial_state,
    next_seq,
    now_ts,
)


@asynccontextmanager
async def _noop_lifespan(app):
    yield


def _build_app_with_state():
    """Build app, bypass lifespan, attach mocks to app.state."""
    with patch("tier1.observability._init_otel"):
        with patch("tier1.observability.init_telemetry"):
            app = create_app()
    app.router.lifespan_context = _noop_lifespan
    pg = AsyncMock()
    redis = AsyncMock()
    nats = AsyncMock()
    garage = MagicMock()
    app.state.pg = pg
    app.state.redis = redis
    app.state.nats = nats
    app.state.garage = garage
    return app, pg, redis, nats, garage


def test_create_deliberation_returns_201_and_id():
    """POST /api/deliberations with valid body → 201 + id."""
    app, pg, redis, nats, garage = _build_app_with_state()
    pg.save_deliberation = AsyncMock(return_value=None)
    redis.put_state = AsyncMock(return_value=None)
    nats.publish = AsyncMock(return_value=None)
    pg.append_event = AsyncMock(return_value=None)

    with TestClient(app) as client:
        resp = client.post("/api/deliberations", json={"problem": "what is X?"})
    assert resp.status_code == 201
    body = resp.json()
    assert "id" in body and body["status"] == "started"
    did = body["id"]
    assert did and isinstance(did, str)
    # pg.save_deliberation was called with the initial state
    pg.save_deliberation.assert_awaited()
    # nats.publish was called for the started event
    nats.publish.assert_awaited()


def test_create_deliberation_rejects_empty_problem_422():
    """Empty problem fails pydantic min_length=1 → 422."""
    app, pg, redis, nats, garage = _build_app_with_state()
    with TestClient(app) as client:
        resp = client.post("/api/deliberations", json={"problem": ""})
    assert resp.status_code == 422


def test_create_deliberation_rejects_missing_problem_field_422():
    """Missing 'problem' field → 422 from pydantic."""
    app, pg, redis, nats, garage = _build_app_with_state()
    with TestClient(app) as client:
        resp = client.post("/api/deliberations", json={})
    assert resp.status_code == 422


def test_create_deliberation_500_when_pg_save_raises():
    """If pg.save_deliberation raises, the endpoint returns 500."""
    app, pg, redis, nats, garage = _build_app_with_state()
    pg.save_deliberation = AsyncMock(side_effect=RuntimeError("db down"))
    # TestClient raises server exceptions by default; use raise_server_exceptions=False
    with TestClient(app, raise_server_exceptions=False) as client:
        resp = client.post("/api/deliberations", json={"problem": "boom"})
    assert resp.status_code == 500


def test_get_deliberation_returns_state_with_events():
    """GET /api/deliberations/{id} returns id, problem, status, events."""
    app, pg, redis, nats, garage = _build_app_with_state()
    did = "abc-123"
    state = initial_state(deliberation_id=did, problem="p?")
    state["status"] = "running"
    pg.load_deliberation = AsyncMock(return_value=state)
    ev = DeliberationEvent(
        seq=next_seq(state["events"]),
        ts=now_ts(),
        kind="started",
        payload={"deliberation_id": did},
    )
    pg.get_events = AsyncMock(return_value=[ev])

    with TestClient(app) as client:
        resp = client.get(f"/api/deliberations/{did}")
    assert resp.status_code == 200
    body = resp.json()
    assert body["id"] == did
    assert body["problem"] == "p?"
    assert body["status"] == "running"
    assert len(body["events"]) == 1


def test_get_deliberation_404_when_missing():
    """Unknown deliberation_id → 404."""
    app, pg, redis, nats, garage = _build_app_with_state()
    pg.load_deliberation = AsyncMock(return_value=None)
    with TestClient(app) as client:
        resp = client.get("/api/deliberations/missing-id")
    assert resp.status_code == 404
    assert "not found" in resp.text.lower()


def test_get_deliberation_includes_final_verdict_when_present():
    """state['final_verdict'] is serialized into the response."""
    from tier1.deliberation.state import FinalVerdict, AgentVerdict

    app, pg, redis, nats, garage = _build_app_with_state()
    did = "v-1"
    state = initial_state(deliberation_id=did, problem="x")
    state["final_verdict"] = FinalVerdict(
        summary="ok",
        decision="approved",
        rounds=2,
        votes={
            "alpha": AgentVerdict(agent="alpha", position="approve", confidence=0.9, reasoning="ok")
        },
    )
    pg.load_deliberation = AsyncMock(return_value=state)
    pg.get_events = AsyncMock(return_value=[])

    with TestClient(app) as client:
        resp = client.get(f"/api/deliberations/{did}")
    body = resp.json()
    assert body["final_verdict"] is not None
    assert body["final_verdict"]["decision"] == "approved"


def test_interject_deliberation_returns_204():
    """POST /interject with text → 204 and persistence side-effects."""
    app, pg, redis, nats, garage = _build_app_with_state()
    did = "abc"
    state = initial_state(deliberation_id=did, problem="p")
    state["status"] = "running"
    pg.load_deliberation = AsyncMock(return_value=state)
    pg.save_deliberation = AsyncMock(return_value=None)
    pg.append_event = AsyncMock(return_value=None)
    redis.put_state = AsyncMock(return_value=None)
    nats.publish = AsyncMock(return_value=None)

    with TestClient(app) as client:
        resp = client.post(f"/api/deliberations/{did}/interject", json={"text": "more info"})
    assert resp.status_code == 204
    pg.save_deliberation.assert_awaited()
    pg.append_event.assert_awaited()
    nats.publish.assert_awaited()


def test_interject_404_when_deliberation_missing():
    """interject on unknown id → 404."""
    app, pg, redis, nats, garage = _build_app_with_state()
    pg.load_deliberation = AsyncMock(return_value=None)
    with TestClient(app) as client:
        resp = client.post("/api/deliberations/missing/interject", json={"text": "hi"})
    assert resp.status_code == 404


def test_interject_409_when_deliberation_not_running():
    """interject on a completed/failed deliberation → 409."""
    app, pg, redis, nats, garage = _build_app_with_state()
    did = "done-1"
    state = initial_state(deliberation_id=did, problem="p")
    state["status"] = "completed"
    pg.load_deliberation = AsyncMock(return_value=state)

    with TestClient(app) as client:
        resp = client.post(f"/api/deliberations/{did}/interject", json={"text": "x"})
    assert resp.status_code == 409


def test_interject_422_when_text_empty():
    """empty text violates min_length=1."""
    app, pg, redis, nats, garage = _build_app_with_state()
    did = "x"
    state = initial_state(deliberation_id=did, problem="p")
    state["status"] = "running"
    pg.load_deliberation = AsyncMock(return_value=state)

    with TestClient(app) as client:
        resp = client.post(f"/api/deliberations/{did}/interject", json={"text": ""})
    assert resp.status_code == 422


def test_list_deliberations_returns_summaries():
    """GET /api/deliberations returns list of summaries."""
    app, pg, redis, nats, garage = _build_app_with_state()
    pg.list_deliberations = AsyncMock(
        return_value=[
            {"id": "a", "problem": "pa", "status": "running", "created_at": 1.0},
            {"id": "b", "problem": "pb", "status": "completed", "created_at": 2.0},
        ]
    )
    with TestClient(app) as client:
        resp = client.get("/api/deliberations")
    assert resp.status_code == 200
    body = resp.json()
    assert "items" in body
    assert len(body["items"]) == 2
    assert body["items"][0]["id"] == "a"


def test_list_deliberations_passes_limit_through():
    """limit query param flows to pg.list_deliberations."""
    app, pg, redis, nats, garage = _build_app_with_state()
    pg.list_deliberations = AsyncMock(return_value=[])
    with TestClient(app) as client:
        resp = client.get("/api/deliberations?limit=5")
    assert resp.status_code == 200
    pg.list_deliberations.assert_awaited_with(5)


def test_list_deliberations_rejects_limit_out_of_range_422():
    """limit=0 (below ge=1) → 422 from pydantic query validation."""
    app, pg, redis, nats, garage = _build_app_with_state()
    with TestClient(app) as client:
        resp = client.get("/api/deliberations?limit=0")
    assert resp.status_code == 422
