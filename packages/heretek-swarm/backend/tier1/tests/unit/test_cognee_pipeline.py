"""Tests for CogneePipeline (Kùzu implementation)."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from tier1.memory import MemoryEntry, MemoryType
from tier1.memory.cognee_store import CogneePipeline


def _make_memory_backend():
    mem = MagicMock()
    mem.store = AsyncMock(return_value="entry-id")
    mem.search = AsyncMock(return_value=[])
    return mem


def test_add_stores_to_memory_backend():
    backend = _make_memory_backend()
    pipeline = CogneePipeline(backend)
    # Drive synchronously since add() is async but memory is mocked.
    import asyncio

    entry_id = asyncio.run(pipeline.add("hello world", metadata={"k": "v"}))
    assert entry_id == "entry-id"
    backend.store.assert_awaited_once()
    stored = backend.store.await_args.args[0]
    assert stored.content == "hello world"
    assert stored.memory_type == MemoryType.semantic
    assert stored.source == "cognee"
    assert stored.metadata == {"k": "v"}


async def test_add_async():
    backend = _make_memory_backend()
    pipeline = CogneePipeline(backend)
    entry_id = await pipeline.add("hello async")
    assert entry_id == "entry-id"


async def test_cognify_stub_returns_zero():
    backend = _make_memory_backend()
    pipeline = CogneePipeline(backend)
    assert await pipeline.cognify() == 0
    assert await pipeline.cognify(batch_size=20) == 0


async def test_search_delegates_to_memory_backend():
    backend = _make_memory_backend()
    entry = MagicMock(spec=MemoryEntry)
    backend.search = AsyncMock(return_value=[entry])
    pipeline = CogneePipeline(backend)
    results = await pipeline.search("query", top_k=3)
    assert results == [entry]
    backend.search.assert_awaited_once_with("query", top_k=3)


async def test_improve_is_noop():
    backend = _make_memory_backend()
    pipeline = CogneePipeline(backend)
    # No exception means it ran cleanly.
    await pipeline.improve()


def test_constructor_preserves_public_surface():
    """Constructor signature must match what the spec mandates."""
    backend = _make_memory_backend()
    pipeline = CogneePipeline(backend, graph_path="/tmp/x", llm_provider="minimax")
    assert pipeline.memory is backend
    assert pipeline.graph_path == "/tmp/x"
    assert pipeline.llm_provider == "minimax"
    assert pipeline._conn is None  # not opened yet
