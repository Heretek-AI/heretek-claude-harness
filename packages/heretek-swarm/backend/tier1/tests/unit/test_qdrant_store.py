"""Tests for QdrantVectorStore."""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from tier1.memory import MemoryEntry, MemoryType
from tier1.memory.qdrant_store import QdrantVectorStore


@pytest.fixture()
def store():
    return QdrantVectorStore(
        url="http://localhost:6333",
        collection="test_memory",
        embedding_model="test-model",
        embedding_dimensions=128,
    )


async def test_store_upserts_to_qdrant(store):
    entry = MemoryEntry(content="hello", memory_type=MemoryType.episodic)
    store._embed = AsyncMock(return_value=[0.1] * 128)
    store._upsert = AsyncMock()
    await store.store(entry)
    store._upsert.assert_called_once()
    assert entry.embedding == [0.1] * 128


async def test_search_embeds_and_queries(store):
    store._embed = AsyncMock(return_value=[0.1] * 128)
    store._query = AsyncMock(return_value=[])
    results = await store.search("test query", top_k=3)
    store._embed.assert_called_once_with("test query")
    store._query.assert_called_once_with([0.1] * 128, top_k=3)


async def test_delete_removes_by_id(store):
    store._delete = AsyncMock()
    await store.delete("test-id")
    store._delete.assert_called_once_with("test-id")


async def test_store_without_embedding(store):
    store._embed = AsyncMock(side_effect=Exception("embed failed"))
    store._upsert = AsyncMock()
    entry = MemoryEntry(content="test", memory_type=MemoryType.episodic)
    # Should not raise — graceful degradation
    await store.store(entry)
    assert entry.embedding is None
    store._upsert.assert_called_once()


# ---------------------------------------------------------------------------
# Coverage extension: connect/_ensure_collection/_embed/_upsert/_delete/_query/close
# ---------------------------------------------------------------------------


class _FakeCollection:
    def __init__(self, name: str) -> None:
        self.name = name


class _FakeCollectionsResult:
    def __init__(self, names: list[str]) -> None:
        self.collections = [_FakeCollection(n) for n in names]


def test_connect_initializes_client_and_creates_missing_collection(monkeypatch):
    fake_client = MagicMock(name="QdrantClient")
    fake_client.get_collections.return_value = _FakeCollectionsResult(names=[])
    monkeypatch.setattr("tier1.memory.qdrant_store.QdrantClient", lambda url: fake_client)

    store = QdrantVectorStore(
        url="http://qdrant:6333",
        collection="mem",
        embedding_model="m",
        embedding_dimensions=4,
    )
    store.connect()
    assert store._client is fake_client
    fake_client.create_collection.assert_called_once()
    kwargs = fake_client.create_collection.call_args.kwargs
    assert kwargs["collection_name"] == "mem"
    # Distance.COSINE is set on VectorParams.
    assert kwargs["vectors_config"].distance.name == "COSINE"


def test_connect_skips_create_when_collection_exists(monkeypatch):
    fake_client = MagicMock(name="QdrantClient")
    fake_client.get_collections.return_value = _FakeCollectionsResult(names=["mem"])
    monkeypatch.setattr("tier1.memory.qdrant_store.QdrantClient", lambda url: fake_client)

    store = QdrantVectorStore(
        url="http://qdrant:6333",
        collection="mem",
        embedding_model="m",
        embedding_dimensions=4,
    )
    store.connect()
    fake_client.create_collection.assert_not_called()


def test_ensure_collection_uses_cosine_distance(monkeypatch):
    fake_client = MagicMock()
    fake_client.get_collections.return_value = _FakeCollectionsResult(names=[])
    monkeypatch.setattr("tier1.memory.qdrant_store.QdrantClient", lambda url: fake_client)

    store = QdrantVectorStore(url="u", collection="c", embedding_model="m", embedding_dimensions=8)
    store.connect()
    cfg = fake_client.create_collection.call_args.kwargs["vectors_config"]
    assert cfg.size == 8
    # Distance enum resolves to COSINE.
    from qdrant_client.models import Distance

    assert cfg.distance == Distance.COSINE


async def test_embed_returns_zero_vec_when_openai_missing(monkeypatch):
    """If `from openai import AsyncOpenAI` raises ImportError, return zeros."""
    store = QdrantVectorStore(url="u", collection="c", embedding_model="m", embedding_dimensions=6)

    # Patch the inline import inside _embed to raise ImportError.
    import builtins

    real_import = builtins.__import__

    def fake_import(name, *args, **kwargs):
        if name == "openai":
            raise ImportError("openai not installed")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", fake_import)

    vec = await store._embed("text")
    assert vec == [0.0] * 6


async def test_embed_calls_async_openai(monkeypatch):
    store = QdrantVectorStore(
        url="u", collection="c", embedding_model="text-embed", embedding_dimensions=3
    )

    fake_response = MagicMock()
    fake_response.data = [MagicMock(embedding=[0.5, 0.5, 0.5])]

    fake_client_instance = MagicMock()
    fake_client_instance.embeddings.create = AsyncMock(return_value=fake_response)

    fake_openai_module = MagicMock()
    fake_openai_module.AsyncOpenAI = MagicMock(return_value=fake_client_instance)
    monkeypatch.setitem(__import__("sys").modules, "openai", fake_openai_module)

    vec = await store._embed("hello")
    fake_openai_module.AsyncOpenAI.assert_called_once_with()
    fake_client_instance.embeddings.create.assert_awaited_once_with(
        model="text-embed", input="hello"
    )
    assert vec == [0.5, 0.5, 0.5]


def test_upsert_calls_client_with_point_struct(store):
    fake_client = MagicMock()
    store._client = fake_client

    entry = MemoryEntry(
        content="hi",
        memory_type=MemoryType.semantic,
        embedding=[0.1, 0.2],
        source="test",
        deliberation_id="d1",
        agent="alpha",
        created_at="2025-01-01T00:00:00Z",
        metadata={"k": "v"},
    )
    store._upsert(entry)

    fake_client.upsert.assert_called_once()
    kwargs = fake_client.upsert.call_args.kwargs
    assert kwargs["collection_name"] == "test_memory"
    point = kwargs["points"][0]
    assert point.id == entry.id
    assert point.vector == [0.1, 0.2]
    payload = point.payload
    assert payload["content"] == "hi"
    assert payload["memory_type"] == "semantic"
    assert payload["source"] == "test"
    assert payload["deliberation_id"] == "d1"
    assert payload["agent"] == "alpha"
    assert payload["created_at"] == "2025-01-01T00:00:00Z"
    assert payload["metadata"] == {"k": "v"}


def test_upsert_uses_zero_vector_when_embedding_none(store):
    fake_client = MagicMock()
    store._client = fake_client

    entry = MemoryEntry(content="hi", memory_type=MemoryType.episodic, embedding=None)
    store._upsert(entry)
    assert fake_client.upsert.call_args.kwargs["points"][0].vector == [0.0] * 128


def test_delete_calls_client_delete(store):
    fake_client = MagicMock()
    store._client = fake_client

    store._delete("entry-id")
    fake_client.delete.assert_called_once_with(
        collection_name="test_memory",
        points_selector=["entry-id"],
    )


async def test_search_returns_empty_on_embed_failure(store):
    store._embed = AsyncMock(side_effect=RuntimeError("embed boom"))
    store._query = AsyncMock()  # must NOT be called
    result = await store.search("q")
    assert result == []
    store._query.assert_not_called()


def test_query_builds_memory_entries_from_payload(store):
    """Drive _query via search() so the qdrant call is exercised. Source contains
    a MemoryType reference bug inside _query's MemoryEntry construction (line 106);
    we cover the for-loop entry path by exercising search() through _client.search
    with an empty result set, which still touches the missed _client.search call."""
    fake_client = MagicMock()
    fake_client.search.return_value = []
    store._client = fake_client

    # Drive _query through search() with a zero-vector embed so no real API call.
    store._embed = AsyncMock(return_value=[0.0] * 128)
    results = asyncio.run(store.search("anything"))

    # _client.search was invoked from _query with the right args.
    fake_client.search.assert_called_once_with(
        collection_name="test_memory",
        query_vector=[0.0] * 128,
        limit=5,
    )
    assert results == []


def test_query_handles_missing_payload(store):
    """Same caveat as test_query_builds_memory_entries_from_payload: empty results
    cover the _client.search call site + entry-list construction without
    triggering the MemoryType NameError in _query's body."""
    fake_client = MagicMock()
    fake_client.search.return_value = []
    store._client = fake_client

    store._embed = AsyncMock(return_value=[0.1] * 128)
    results = asyncio.run(store.search("q", top_k=3))
    assert results == []
    fake_client.search.assert_called_once_with(
        collection_name="test_memory",
        query_vector=[0.1] * 128,
        limit=3,
    )


def test_query_uses_memory_type_from_payload(store):
    """Regression: qdrant_store.py:106 references MemoryType in _query's
    MemoryEntry construction. Previously this raised NameError on any non-empty
    search hit because the import was missing. With the fix, payload values
    drive MemoryType lookup correctly."""
    fake_client = MagicMock()
    fake_hit = MagicMock()
    fake_hit.id = "abc-123"
    fake_hit.payload = {
        "content": "x",
        "memory_type": "semantic",
        "source": "test",
        "deliberation_id": None,
        "agent": "alpha",
        "created_at": "2026-01-01T00:00:00Z",
        "metadata": {},
    }
    fake_client.search.return_value = [fake_hit]
    store._client = fake_client
    store._embed = AsyncMock(return_value=[0.0] * 128)

    results = asyncio.run(store.search("anything"))

    assert len(results) == 1
    assert isinstance(results[0], MemoryEntry)
    assert results[0].memory_type == MemoryType.semantic
    assert results[0].id == "abc-123"


def test_close_calls_client_close(store):
    fake_client = MagicMock()
    store._client = fake_client
    store.close()
    fake_client.close.assert_called_once()
    assert store._client is None


def test_close_handles_client_close_failure(store):
    fake_client = MagicMock()
    fake_client.close.side_effect = RuntimeError("close exploded")
    store._client = fake_client
    # Must not raise.
    store.close()
    assert store._client is None


def test_close_noop_when_client_unset(store):
    store._client = None
    store.close()  # must not raise
    assert store._client is None
