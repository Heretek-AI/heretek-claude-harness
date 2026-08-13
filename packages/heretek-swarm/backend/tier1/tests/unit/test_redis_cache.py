"""Tests for RedisMemoryCache."""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from tier1.memory import MemoryEntry, MemoryType
from tier1.memory.redis_cache import RedisMemoryCache


@pytest.fixture()
def cache():
    c = RedisMemoryCache(url="redis://localhost:6379/1", ttl_s=60)
    c.client = AsyncMock()
    return c


async def test_set_stores_serialized_entry(cache):
    entry = MemoryEntry(content="test", memory_type=MemoryType.episodic)
    await cache.set(entry.id, entry, ttl=120)
    cache.client.set.assert_called_once()
    args = cache.client.set.call_args
    assert args.args[0] == f"tier1:memory:{entry.id}"


async def test_get_returns_deserialized_entry(cache):
    import json

    entry = MemoryEntry(content="hello", memory_type=MemoryType.semantic, id="test-id")
    cache.client.get = AsyncMock(return_value=json.dumps(entry.__dict__))
    result = await cache.get("test-id")
    assert result is not None
    assert result.content == "hello"
    assert result.memory_type == MemoryType.semantic


async def test_get_returns_none_when_missing(cache):
    cache.client.get = AsyncMock(return_value=None)
    assert await cache.get("missing") is None


async def test_delete_removes_key(cache):
    await cache.delete("test-id")
    cache.client.delete.assert_called_once_with("tier1:memory:test-id")
