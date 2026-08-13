"""Tests for NATS memory subject handlers."""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from tier1.memory import MemoryBackend, MemoryEntry, MemoryType
from tier1.memory.nats_memory import setup_memory_nats


async def test_store_handler_publishes_and_stores():
    backend = MagicMock(spec=MemoryBackend)
    backend.store = AsyncMock(return_value="entry-id")
    mock_nats = AsyncMock()
    setup_memory_nats(mock_nats, backend)
    # Verify subscribe was called
    mock_nats.subscribe.assert_called()


async def test_retrieve_handler_calls_search():
    backend = MagicMock(spec=MemoryBackend)
    backend.search = AsyncMock(return_value=[])
    mock_nats = AsyncMock()
    setup_memory_nats(mock_nats, backend)
    mock_nats.subscribe.assert_called()


# ---------------------------------------------------------------------------
# Coverage extension: invoke the inner handlers bound by setup_memory_nats.
# ---------------------------------------------------------------------------


def _handlers(setup_mock_nats):
    """Return (handle_store, handle_retrieve) from the subscribe callbacks."""
    subjects = [c.args[0] for c in setup_mock_nats.subscribe.call_args_list]
    assert "swarm.internal.memory.store" in subjects
    assert "swarm.internal.memory.retrieve" in subjects
    handle_store = next(
        c.kwargs["cb"]
        for c in setup_mock_nats.subscribe.call_args_list
        if c.args[0] == "swarm.internal.memory.store"
    )
    handle_retrieve = next(
        c.kwargs["cb"]
        for c in setup_mock_nats.subscribe.call_args_list
        if c.args[0] == "swarm.internal.memory.retrieve"
    )
    return handle_store, handle_retrieve


async def test_setup_subscribes_to_both_subjects():
    backend = MagicMock(spec=MemoryBackend)
    nats = AsyncMock()
    setup_memory_nats(nats, backend)
    subjects = {c.args[0] for c in nats.subscribe.call_args_list}
    assert subjects == {
        "swarm.internal.memory.store",
        "swarm.internal.memory.retrieve",
    }


async def test_handle_store_publishes_id_on_success():
    backend = MagicMock(spec=MemoryBackend)
    backend.store = AsyncMock(return_value="abc-123")
    nats = AsyncMock()
    setup_memory_nats(nats, backend)
    handle_store, _ = _handlers(nats)

    msg = MagicMock()
    msg.data = json.dumps(
        {
            "content": "hello",
            "memory_type": "episodic",
            "source": "test",
            "deliberation_id": "d1",
            "agent": "alpha",
            "metadata": {"k": "v"},
        }
    ).encode()
    msg.reply = "inbox.42"

    await handle_store(msg)

    backend.store.assert_awaited_once()
    args = nats.publish.await_args
    assert args.args[0] == "inbox.42"
    payload = json.loads(args.args[1].decode())
    assert payload == {"id": "abc-123", "ok": True}


async def test_handle_store_defaults_memory_type_and_optional_fields():
    backend = MagicMock(spec=MemoryBackend)
    backend.store = AsyncMock(return_value="x")
    nats = AsyncMock()
    setup_memory_nats(nats, backend)
    handle_store, _ = _handlers(nats)

    msg = MagicMock()
    msg.data = json.dumps({"content": "no optionals"}).encode()
    msg.reply = "inbox.x"

    await handle_store(msg)

    stored = backend.store.await_args.args[0]
    assert stored.content == "no optionals"
    assert stored.memory_type == MemoryType.episodic
    assert stored.source == ""
    assert stored.deliberation_id is None
    assert stored.agent == ""
    assert stored.metadata == {}


async def test_handle_store_swallows_when_no_reply():
    backend = MagicMock(spec=MemoryBackend)
    backend.store = AsyncMock(return_value="abc")
    nats = AsyncMock()
    setup_memory_nats(nats, backend)
    handle_store, _ = _handlers(nats)

    msg = MagicMock()
    msg.data = json.dumps({"content": "x"}).encode()
    msg.reply = None

    await handle_store(msg)

    backend.store.assert_awaited_once()
    nats.publish.assert_not_awaited()


async def test_handle_store_logs_exception_on_store_failure():
    backend = MagicMock(spec=MemoryBackend)
    backend.store = AsyncMock(side_effect=RuntimeError("pg down"))
    nats = AsyncMock()
    setup_memory_nats(nats, backend)
    handle_store, _ = _handlers(nats)

    msg = MagicMock()
    msg.data = json.dumps({"content": "x"}).encode()
    msg.reply = "inbox"

    await handle_store(msg)

    backend.store.assert_awaited_once()
    nats.publish.assert_not_awaited()


async def test_handle_store_handles_malformed_payload():
    backend = MagicMock(spec=MemoryBackend)
    nats = AsyncMock()
    setup_memory_nats(nats, backend)
    handle_store, _ = _handlers(nats)

    msg = MagicMock()
    msg.data = b"not json"
    msg.reply = "inbox"

    await handle_store(msg)  # Must not raise.

    backend.store.assert_not_awaited()
    nats.publish.assert_not_awaited()


async def test_handle_retrieve_publishes_results():
    e1 = MemoryEntry(content="a", memory_type=MemoryType.episodic, id="1")
    e2 = MemoryEntry(content="b", memory_type=MemoryType.semantic, id="2")
    backend = MagicMock(spec=MemoryBackend)
    backend.search = AsyncMock(return_value=[e1, e2])
    nats = AsyncMock()
    setup_memory_nats(nats, backend)
    _, handle_retrieve = _handlers(nats)

    msg = MagicMock()
    msg.data = json.dumps({"query": "hello", "top_k": 7}).encode()
    msg.reply = "inbox.r"

    await handle_retrieve(msg)

    backend.search.assert_awaited_once_with("hello", top_k=7)
    args = nats.publish.await_args
    assert args.args[0] == "inbox.r"
    payload = json.loads(args.args[1].decode())
    assert payload["results"][0]["id"] == "1"
    assert payload["results"][0]["content"] == "a"
    assert payload["results"][0]["memory_type"] == "episodic"
    assert payload["results"][1]["id"] == "2"
    assert payload["results"][1]["memory_type"] == "semantic"


async def test_handle_retrieve_defaults_top_k():
    backend = MagicMock(spec=MemoryBackend)
    backend.search = AsyncMock(return_value=[])
    nats = AsyncMock()
    setup_memory_nats(nats, backend)
    _, handle_retrieve = _handlers(nats)

    msg = MagicMock()
    msg.data = json.dumps({"query": "x"}).encode()
    msg.reply = "inbox.r"

    await handle_retrieve(msg)
    backend.search.assert_awaited_once_with("x", top_k=5)


async def test_handle_retrieve_swallows_when_no_reply():
    backend = MagicMock(spec=MemoryBackend)
    backend.search = AsyncMock(return_value=[])
    nats = AsyncMock()
    setup_memory_nats(nats, backend)
    _, handle_retrieve = _handlers(nats)

    msg = MagicMock()
    msg.data = json.dumps({"query": "x"}).encode()
    msg.reply = None

    await handle_retrieve(msg)
    backend.search.assert_awaited_once()
    nats.publish.assert_not_awaited()


async def test_handle_retrieve_logs_exception_on_search_failure():
    backend = MagicMock(spec=MemoryBackend)
    backend.search = AsyncMock(side_effect=RuntimeError("qdrant down"))
    nats = AsyncMock()
    setup_memory_nats(nats, backend)
    _, handle_retrieve = _handlers(nats)

    msg = MagicMock()
    msg.data = json.dumps({"query": "x"}).encode()
    msg.reply = "inbox.r"

    await handle_retrieve(msg)  # Must not raise.
    nats.publish.assert_not_awaited()


async def test_handle_retrieve_handles_malformed_payload():
    backend = MagicMock(spec=MemoryBackend)
    nats = AsyncMock()
    setup_memory_nats(nats, backend)
    _, handle_retrieve = _handlers(nats)

    msg = MagicMock()
    msg.data = b"not json"
    msg.reply = "inbox"

    await handle_retrieve(msg)
    backend.search.assert_not_awaited()
    nats.publish.assert_not_awaited()
