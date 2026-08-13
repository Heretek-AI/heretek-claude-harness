"""WS replay/live handoff integration test.

Verifies the contract:
  1. Events persisted to Postgres `deliberation_events` arrive over the
     WebSocket in seq order.
  2. After all replay events are sent, the server emits `replay_done`.
  3. Live events published to NATS AFTER the WS subscribed are then
     forwarded as event frames.

Requires live infra: TIER1_TEST_PG_DSN, TIER1_TEST_NATS_URL, TIER1_TEST_REDIS_URL.
Skipped if any are missing.

Implementation note: starlette's TestClient.websocket_connect runs the
handler in a thread portal with its own event loop, which makes asyncpg
pools created in the test's main loop unusable from the handler. To
avoid that cross-loop hazard we invoke the handler directly with a
small WebSocket fake that records the JSON frames it receives.
"""

from __future__ import annotations

import asyncio
import json
import os
import uuid
from collections.abc import AsyncIterator

import pytest

from tier1.api.routes.ws import deliberation_socket
from tier1.deliberation.state import (
    DeliberationEvent,
    initial_state,
    next_seq,
    now_ts,
)
from tier1.events.channels import subject_for
from tier1.events.nats_client import NatsClient
from tier1.persistence.postgres import PostgresPool
from tier1.persistence.redis import RedisCache


PG_DSN = os.environ.get("TIER1_TEST_PG_DSN", "")
NATS_URL = os.environ.get("TIER1_TEST_NATS_URL", "")
REDIS_URL = os.environ.get("TIER1_TEST_REDIS_URL", "")


def _require_infra() -> None:
    if not (PG_DSN and NATS_URL and REDIS_URL):
        pytest.skip(
            "set TIER1_TEST_PG_DSN, TIER1_TEST_NATS_URL, TIER1_TEST_REDIS_URL "
            "to enable WS replay/live handoff tests"
        )


async def _seed(did: str, pg: PostgresPool):
    state = initial_state(deliberation_id=did, problem="ws handoff test")
    await pg.save_deliberation(state)
    e1 = DeliberationEvent(
        seq=next_seq(state["events"]),
        ts=now_ts(),
        kind="alpha_thinking",
        payload={"round": 0, "text": "first"},
    )
    e2 = DeliberationEvent(
        seq=next_seq(state["events"] + [e1]),
        ts=now_ts(),
        kind="alpha_verdict",
        payload={"position": "approve", "confidence": 0.9},
    )
    await pg.append_event(did, e1)
    await pg.append_event(did, e2)
    return [e1, e2]


async def _cleanup_pg(pg: PostgresPool) -> None:
    if pg.pool is None:  # type: ignore[union-attr]
        return
    async with pg.pool.acquire() as conn:  # type: ignore[union-attr]
        await conn.execute("DELETE FROM deliberation_events")
        await conn.execute("DELETE FROM deliberations")


class _FakeWebSocket:
    """Minimal WebSocket stand-in: records JSON frames, ends on client close."""

    def __init__(self) -> None:
        self.frames: list[dict] = []
        self._client_closed = False

    async def accept(self) -> None:
        return None

    async def send_json(self, data: dict) -> None:
        self.frames.append(data)

    async def receive_text(self) -> str:
        # Block forever until the test closes the client side.
        await asyncio.sleep(0.05)
        raise asyncio.TimeoutError

    def close_client(self) -> None:
        self._client_closed = True


class _FakeApp:
    def __init__(self, pg: PostgresPool, redis: RedisCache, nats: NatsClient) -> None:
        self.state = type("S", (), {})()
        self.state.pg = pg
        self.state.redis = redis
        self.state.nats = nats


@pytest.mark.integration
async def test_ws_replay_then_live():
    """Drive the WS handler with a fake WebSocket and assert frame order."""
    _require_infra()
    did = str(uuid.uuid4())

    pg = PostgresPool(PG_DSN)
    redis = RedisCache(REDIS_URL, 60)
    nats = NatsClient(NATS_URL)
    await pg.connect()
    await redis.connect()
    await nats.connect()
    seed = await _seed(did, pg)
    fake_app = _FakeApp(pg, redis, nats)
    fake_ws = _FakeWebSocket()
    fake_ws.app = fake_app  # type: ignore[attr-defined]

    async def driver() -> None:
        try:
            await deliberation_socket(fake_ws, did)
        except Exception:
            # Handler exits cleanly when queue.put(None) breaks the loop,
            # but we close the fake so any awaits in-flight return.
            pass

    handler_task = asyncio.create_task(driver())
    # Wait for replay frames + replay_done + a live event.
    expected_live = DeliberationEvent(
        seq=seed[1].seq + 1,
        ts=now_ts(),
        kind="beta_thinking",
        payload={"text": "live!"},
    )

    async def publish_live_after_settle() -> None:
        # Give the handler time to subscribe to NATS.
        await asyncio.sleep(0.5)
        await nats.publish(subject_for(did), expected_live.model_dump_json().encode())

    publish_task = asyncio.create_task(publish_live_after_settle())

    # Poll for the expected frame sequence.
    deadline = asyncio.get_event_loop().time() + 8.0
    while asyncio.get_event_loop().time() < deadline:
        if len(fake_ws.frames) >= 4:
            break
        await asyncio.sleep(0.1)

    publish_task.cancel()
    handler_task.cancel()
    try:
        await handler_task
    except (asyncio.CancelledError, Exception):
        pass
    await _cleanup_pg(pg)
    await nats.close()
    await redis.close()
    await pg.close()

    assert len(fake_ws.frames) >= 4, f"expected >=4 frames, got {fake_ws.frames}"
    # 1) replay: e1 then e2
    assert fake_ws.frames[0]["kind"] == "event"
    assert fake_ws.frames[0]["event"]["kind"] == seed[0].kind
    assert fake_ws.frames[0]["event"]["seq"] == seed[0].seq
    assert fake_ws.frames[1]["kind"] == "event"
    assert fake_ws.frames[1]["event"]["kind"] == seed[1].kind
    assert fake_ws.frames[1]["event"]["seq"] == seed[1].seq
    # 2) replay_done
    assert fake_ws.frames[2]["kind"] == "replay_done"
    assert fake_ws.frames[2]["count"] == 2
    # 3) live
    live_frame = fake_ws.frames[3]
    assert live_frame["kind"] == "event"
    assert live_frame["event"]["kind"] == "beta_thinking"
    assert live_frame["event"]["seq"] == expected_live.seq
    assert live_frame["event"]["payload"]["text"] == "live!"
