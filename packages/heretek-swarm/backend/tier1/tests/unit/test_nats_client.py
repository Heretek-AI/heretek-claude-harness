"""Unit tests for tier1.events.nats_client.NatsClient.

Covers all public methods + branches:
  - __init__ stores url; conn and js start as None
  - connect: success path; re-uses existing stream (stream_info OK)
  - connect: stream missing -> add_stream fallback
  - close: no-op when conn is None; drains + clears on live conn
  - publish: asserts js is set; calls js.publish
  - subscribe: yields payload bytes, acks messages
  - subscribe: sanitizes subject for durable name
  - health: True when conn live; False when conn is None or closed
"""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from tier1.events.nats_client import (
    DELIBERATION_SUBJECT_PREFIX,
    NatsClient,
    STREAM_NAME,
    STREAM_SUBJECTS,
)


def _make_connected_client(conn: MagicMock | None = None) -> tuple[NatsClient, MagicMock]:
    """Build a NatsClient pre-wired with a mocked js+conn."""
    c = NatsClient("nats://localhost:4222")
    c.conn = conn or MagicMock()
    c.conn.is_closed = False
    js = MagicMock()
    js.publish = AsyncMock()
    js.stream_info = AsyncMock()
    js.add_stream = AsyncMock()
    c.js = js
    return c, js


# ---------- __init__ ----------


def test_init_stores_url_and_none_conn():
    c = NatsClient("nats://x:4222")
    assert c.url == "nats://x:4222"
    assert c.conn is None
    assert c.js is None


# ---------- connect ----------


async def test_connect_uses_existing_stream():
    """If stream_info succeeds, no add_stream call."""
    nats_conn = MagicMock()
    js = MagicMock()
    js.stream_info = AsyncMock()
    js.add_stream = AsyncMock()
    nats_conn.jetstream = MagicMock(return_value=js)
    with patch("tier1.events.nats_client.nats") as nats_mod:
        nats_mod.connect = AsyncMock(return_value=nats_conn)
        client = NatsClient("nats://x:4222")
        await client.connect()
    assert client.conn is nats_conn
    js.stream_info.assert_awaited_once_with(STREAM_NAME)
    js.add_stream.assert_not_called()


async def test_connect_creates_stream_on_missing():
    """If stream_info raises, add_stream is called as fallback."""
    nats_conn = MagicMock()
    js = MagicMock()
    js.stream_info = AsyncMock(side_effect=Exception("not found"))
    js.add_stream = AsyncMock()
    nats_conn.jetstream = MagicMock(return_value=js)
    with patch("tier1.events.nats_client.nats") as nats_mod:
        nats_mod.connect = AsyncMock(return_value=nats_conn)
        client = NatsClient("nats://x:4222")
        await client.connect()
    js.add_stream.assert_awaited_once()
    cfg = js.add_stream.call_args.args[0]
    assert cfg.name == STREAM_NAME
    assert cfg.subjects == STREAM_SUBJECTS


# ---------- close ----------


async def test_close_when_conn_is_none_is_noop():
    c = NatsClient("nats://x:4222")
    await c.close()
    assert c.conn is None
    assert c.js is None


async def test_close_drains_and_clears():
    c, _ = _make_connected_client()
    c.conn.drain = AsyncMock()
    conn_ref = c.conn
    await c.close()
    conn_ref.drain.assert_awaited_once()
    assert c.conn is None
    assert c.js is None


# ---------- publish ----------


async def test_publish_calls_js_publish():
    c, js = _make_connected_client()
    await c.publish("subject.x", b"hello")
    js.publish.assert_awaited_once_with("subject.x", b"hello")


async def test_publish_asserts_when_js_none():
    c = NatsClient("nats://x:4222")
    c.js = None
    with pytest.raises(AssertionError):
        await c.publish("s", b"x")


# ---------- subscribe ----------


async def test_subscribe_yields_payload_bytes_and_acks():
    msg = MagicMock()
    msg.data = b"hello"
    msg.ack = AsyncMock()
    sub = MagicMock()
    sub.fetch = AsyncMock(side_effect=[[msg], []])
    js = MagicMock()
    js.pull_subscribe = AsyncMock(return_value=sub)
    c, _ = _make_connected_client()
    c.js = js
    payloads = []
    async for p in c.subscribe("tier1.deliberation.d1.events"):
        payloads.append(p)
        if payloads:
            break
    assert payloads == [b"hello"]
    msg.ack.assert_awaited_once()


async def test_subscribe_sanitizes_durable_name():
    """Subject dots/wildcards are replaced for the consumer name."""
    msg = MagicMock()
    msg.data = b"x"
    msg.ack = AsyncMock()
    sub = MagicMock()
    sub.fetch = AsyncMock(side_effect=[[msg], []])
    js = MagicMock()
    js.pull_subscribe = AsyncMock(return_value=sub)
    c, _ = _make_connected_client()
    c.js = js
    async for _ in c.subscribe("a.b.*"):
        break
    durable_arg = js.pull_subscribe.call_args.kwargs["durable"]
    assert "." not in durable_arg
    assert "*" not in durable_arg


def test_subscribe_subject_constant_format():
    """STREAM_SUBJECTS uses the documented tier1.deliberation.*.events pattern."""
    assert STREAM_SUBJECTS == [f"{DELIBERATION_SUBJECT_PREFIX}.*.events"]


# ---------- health ----------


async def test_health_true_when_conn_live():
    c, _ = _make_connected_client()
    c.conn.is_closed = False
    assert await c.health() is True


async def test_health_false_when_conn_none():
    c = NatsClient("nats://x:4222")
    assert await c.health() is False


async def test_health_false_when_conn_closed():
    c, _ = _make_connected_client()
    c.conn.is_closed = True
    assert await c.health() is False
