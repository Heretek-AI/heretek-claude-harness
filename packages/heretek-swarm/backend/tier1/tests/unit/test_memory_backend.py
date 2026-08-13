"""Tests for MemoryBackend facade."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from tier1.memory import MemoryBackend, MemoryEntry, MemoryType


@pytest.fixture()
def backend():
    qdrant = MagicMock()
    redis = MagicMock()
    postgres = MagicMock()
    return MemoryBackend(qdrant=qdrant, redis=redis, postgres=postgres)


async def test_store_writes_to_all_tiers(backend):
    entry = MemoryEntry(content="test", memory_type=MemoryType.episodic)
    backend.qdrant.store = AsyncMock()
    backend.redis.set = AsyncMock()
    backend.postgres.store = AsyncMock()
    result = await backend.store(entry)
    assert result == entry.id
    backend.qdrant.store.assert_called_once_with(entry)
    backend.redis.set.assert_called_once()
    backend.postgres.store.assert_called_once_with(entry)


async def test_store_survives_qdrant_failure(backend):
    entry = MemoryEntry(content="test", memory_type=MemoryType.episodic)
    backend.qdrant.store = AsyncMock(side_effect=Exception("qdrant down"))
    backend.redis.set = AsyncMock()
    backend.postgres.store = AsyncMock()
    result = await backend.store(entry)
    assert result == entry.id
    backend.postgres.store.assert_called_once()


async def test_search_calls_qdrant(backend):
    backend.qdrant.search = AsyncMock(return_value=[])
    results = await backend.search("query", top_k=3)
    backend.qdrant.search.assert_called_once_with("query", top_k=3)


async def test_get_history_calls_postgres(backend):
    backend.postgres.get_history = AsyncMock(return_value=[])
    results = await backend.get_history("did-1")
    backend.postgres.get_history.assert_called_once_with("did-1")


async def test_get_session_calls_redis(backend):
    backend.redis.get = AsyncMock(return_value=None)
    result = await backend.get_session("key")
    backend.redis.get.assert_called_once_with("key")
    assert result is None


async def test_store_calls_mem0_when_set():
    """When mem0 is passed, store() invokes mem0.add with content + metadata + agent."""
    qdrant = MagicMock()
    redis = MagicMock()
    postgres = MagicMock()
    mem0 = MagicMock()
    mem0.add = AsyncMock()
    backend = MemoryBackend(qdrant=qdrant, redis=redis, postgres=postgres, mem0=mem0)
    qdrant.store = AsyncMock()
    redis.set = AsyncMock()
    postgres.store = AsyncMock()
    entry = MemoryEntry(content="hello mem0", memory_type=MemoryType.episodic, agent="alpha")
    result = await backend.store(entry)
    assert result == entry.id
    mem0.add.assert_awaited_once()
    args, kwargs = mem0.add.call_args
    assert args == ("hello mem0",)
    assert kwargs.get("user_id") == "alpha"
    assert kwargs.get("metadata") == entry.metadata


async def test_store_calls_cognee_when_set():
    """When cognee is passed, store() invokes cognee.add with content + metadata."""
    qdrant = MagicMock()
    redis = MagicMock()
    postgres = MagicMock()
    cognee = MagicMock()
    cognee.add = AsyncMock()
    backend = MemoryBackend(qdrant=qdrant, redis=redis, postgres=postgres, cognee=cognee)
    qdrant.store = AsyncMock()
    redis.set = AsyncMock()
    postgres.store = AsyncMock()
    entry = MemoryEntry(content="hello cognee", memory_type=MemoryType.semantic)
    result = await backend.store(entry)
    assert result == entry.id
    cognee.add.assert_awaited_once()
    args, kwargs = cognee.add.call_args
    assert args == ("hello cognee",)
    assert kwargs.get("metadata") == entry.metadata


async def test_store_swallows_cognee_failure():
    """A cognee failure must not break a memory write — log and continue."""
    qdrant = MagicMock()
    redis = MagicMock()
    postgres = MagicMock()
    cognee = MagicMock()
    cognee.add = AsyncMock(side_effect=Exception("kuzu down"))
    backend = MemoryBackend(qdrant=qdrant, redis=redis, postgres=postgres, cognee=cognee)
    qdrant.store = AsyncMock()
    redis.set = AsyncMock()
    postgres.store = AsyncMock()
    entry = MemoryEntry(content="x", memory_type=MemoryType.semantic)
    result = await backend.store(entry)
    assert result == entry.id
    postgres.store.assert_awaited_once()
