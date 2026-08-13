"""Tests for /ws/deliberations/{id} WebSocket route."""

from __future__ import annotations

import asyncio
import json
from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from tier1.api.app import create_app
from tier1.deliberation.state import DeliberationEvent, now_ts


@asynccontextmanager
async def _noop_lifespan(app):
    yield


def _build_app_with_state(ws_setup=None):
    """Build app, bypass lifespan, attach pg + nats mocks to app.state."""
    with patch("tier1.observability._init_otel"):
        with patch("tier1.observability.init_telemetry"):
            app = create_app()
    app.router.lifespan_context = _noop_lifespan
    pg = AsyncMock()
    nats = AsyncMock()
    app.state.pg = pg
    app.state.nats = nats
    if ws_setup:
        ws_setup(pg, nats)
    return app, pg, nats


def test_websocket_accepts_and_replays_no_events():
    """On connect with empty event list, client receives replay_done with count=0."""
    app, pg, nats = _build_app_with_state()
    pg.get_events = AsyncMock(return_value=[])

    with TestClient(app) as client:
        with client.websocket_connect("/ws/deliberations/d-1") as ws:
            msg = ws.receive_json()
            assert msg == {"kind": "replay_done", "count": 0}


def test_websocket_replays_persisted_events_then_signals_done():
    """Persisted events are sent as {kind: 'event'} messages then replay_done."""
    app, pg, nats = _build_app_with_state()

    ev1 = DeliberationEvent(seq=1, ts=now_ts(), kind="started", payload={"deliberation_id": "d-1"})
    ev2 = DeliberationEvent(seq=2, ts=now_ts(), kind="alpha_thinking", payload={"round": 1})
    pg.get_events = AsyncMock(return_value=[ev1, ev2])

    with TestClient(app) as client:
        with client.websocket_connect("/ws/deliberations/d-1") as ws:
            m1 = ws.receive_json()
            m2 = ws.receive_json()
            m3 = ws.receive_json()
            assert m1["kind"] == "event"
            assert m1["event"]["seq"] == 1
            assert m2["kind"] == "event"
            assert m2["event"]["seq"] == 2
            assert m3 == {"kind": "replay_done", "count": 2}


def test_websocket_handles_ping_message_and_replies_pong():
    """A {"kind": "ping"} message from the client triggers a {"kind": "pong"} reply."""
    app, pg, nats = _build_app_with_state()
    pg.get_events = AsyncMock(return_value=[])

    with TestClient(app) as client:
        with client.websocket_connect("/ws/deliberations/d-ping") as ws:
            replay = ws.receive_json()
            assert replay == {"kind": "replay_done", "count": 0}
            ws.send_text(json.dumps({"kind": "ping"}))
            pong = ws.receive_json()
            assert pong == {"kind": "pong"}


def test_websocket_route_is_registered():
    """The /ws/deliberations route is on the app router (covers routing wiring)."""
    app, pg, nats = _build_app_with_state()
    paths = set()
    for r in app.routes:
        if hasattr(r, "path"):
            paths.add(r.path)
        elif hasattr(r, "original_router"):
            for sr in r.original_router.routes:
                if hasattr(sr, "path"):
                    paths.add(sr.path)
    assert any(p.startswith("/ws/deliberations") for p in paths)


@pytest.mark.asyncio
async def test_websocket_forwards_nats_messages_as_events():
    """NATS subscription yields bytes → ws receives {kind: event} JSON for each."""
    app, pg, nats = _build_app_with_state()

    # Async iterator that yields two events then blocks
    class _AsyncIter:
        def __init__(self, items):
            self._items = list(items)
            self._i = 0

        def __aiter__(self):
            return self

        async def __anext__(self):
            if self._i >= len(self._items):
                # Block forever so the consumer task stays alive
                await asyncio.sleep(60)
            item = self._items[self._i]
            self._i += 1
            return item

    event_payload_1 = json.dumps(
        {"seq": 5, "ts": 123.0, "kind": "consensus_reached", "payload": {"verdict": "yes"}}
    )
    event_payload_2 = json.dumps(
        {"seq": 6, "ts": 124.0, "kind": "deliberation_finished", "payload": {}}
    )
    nats.subscribe = MagicMock(
        side_effect=lambda subject: _AsyncIter([event_payload_1.encode(), event_payload_2.encode()])
    )
    pg.get_events = AsyncMock(return_value=[])

    with TestClient(app) as client:
        with client.websocket_connect("/ws/deliberations/d-nats") as ws:
            # First the replay_done
            replay = ws.receive_json()
            assert replay == {"kind": "replay_done", "count": 0}
            # Then the two NATS-pushed events
            e1 = ws.receive_json()
            e2 = ws.receive_json()
            assert e1["kind"] == "event"
            assert e1["event"]["kind"] == "consensus_reached"
            assert e2["kind"] == "event"
            assert e2["event"]["kind"] == "deliberation_finished"


def test_websocket_subscribe_called_with_correct_subject():
    """NATS subscribe invoked with the subject_for(did) for this id."""
    app, pg, nats = _build_app_with_state()
    pg.get_events = AsyncMock(return_value=[])

    class _StopAsyncIter:
        def __aiter__(self):
            return self

        async def __anext__(self):
            await asyncio.sleep(60)
            raise StopAsyncIteration  # pragma: no cover

    nats.subscribe = MagicMock(return_value=_StopAsyncIter())

    from tier1.events.channels import subject_for

    with TestClient(app) as client:
        with client.websocket_connect("/ws/deliberations/subject-test") as ws:
            replay = ws.receive_json()
            assert replay == {"kind": "replay_done", "count": 0}

    nats.subscribe.assert_called()
    called_with = [c.args[0] for c in nats.subscribe.call_args_list]
    assert subject_for("subject-test") in called_with
