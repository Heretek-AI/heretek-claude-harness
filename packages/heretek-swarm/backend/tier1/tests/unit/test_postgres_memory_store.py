"""Tests for PostgresMemoryStore."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from tier1.memory import MemoryEntry, MemoryType
from tier1.memory.postgres_store import PostgresMemoryStore


@pytest.fixture()
def store():
    s = PostgresMemoryStore(pool=None)
    s._pool = AsyncMock()
    return s


async def test_store_inserts_entry(store):
    entry = MemoryEntry(content="test", memory_type=MemoryType.episodic)
    await store.store(entry)
    store._pool.execute.assert_called_once()


async def test_get_history_returns_entries(store):
    row = MagicMock()
    row.__getitem__ = lambda self, k: {
        "id": "1",
        "content": "hello",
        "memory_type": "semantic",
        "source": "deliberation",
        "deliberation_id": "did-1",
        "agent": "alpha",
        "created_at": "2025-01-01",
        "metadata": "{}",
    }[k]
    store._pool.fetch = AsyncMock(return_value=[row])
    results = await store.get_history("did-1")
    assert len(results) == 1
    assert results[0].content == "hello"
