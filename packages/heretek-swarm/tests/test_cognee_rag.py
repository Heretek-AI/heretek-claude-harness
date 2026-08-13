"""
Tests for CogneeRAGRetriever + the get_rag_retriever factory.

Per M-arch PR #4: verify the Cognee-backed RAG retriever behaves
correctly when Cognee is enabled, disabled, or unreachable; and verify
the factory selects the right backend based on env.
"""

from __future__ import annotations

import importlib.util
import os
from unittest.mock import AsyncMock, MagicMock

import pytest


def _load_cognee_rag_module():
    """Load cognee_rag.py without triggering the heavy heretek_swarm package import."""
    spec = importlib.util.spec_from_file_location(
        "cognee_rag_under_test",
        "backend/heretek_swarm/rag/cognee_rag.py",
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture
def cognee_rag_mod():
    return _load_cognee_rag_module()


@pytest.fixture
def enabled_reader():
    """A pre-configured CogneeMemoryReader that is enabled with a mocked client."""
    r = MagicMock()
    r.enabled = True
    r.api_url = "http://cognee:8000"
    r.read = AsyncMock(return_value=[])
    r.health = AsyncMock(return_value=True)
    r.close = AsyncMock()
    return r


class TestCogneeRAGRetriever:
    """Behavioral tests for CogneeRAGRetriever."""

    def test_default_construction(self, cognee_rag_mod) -> None:
        """CogneeRAGRetriever can be constructed with no args."""
        os.environ["COGNEE_ENABLED"] = "false"
        retriever = cognee_rag_mod.CogneeRAGRetriever()
        assert retriever._reader is not None
        assert retriever._reader.enabled is False
        del os.environ["COGNEE_ENABLED"]

    def test_register_chunks_disabled_returns_zero(
        self, cognee_rag_mod, enabled_reader
    ) -> None:
        """register_chunks is a no-op when the underlying reader is disabled."""
        enabled_reader.enabled = False
        r = cognee_rag_mod.CogneeRAGRetriever(enabled_reader)

        class FakeChunk:
            chunk_id = "c1"
            document_id = "d1"

        assert r.register_chunks([FakeChunk(), FakeChunk()]) == 0

    def test_register_chunks_counts_when_enabled(
        self, cognee_rag_mod, enabled_reader
    ) -> None:
        """register_chunks returns the count of chunks forwarded."""
        r = cognee_rag_mod.CogneeRAGRetriever(enabled_reader)

        class FakeChunk:
            chunk_id = "c1"
            document_id = "d1"

        assert r.register_chunks([FakeChunk(), FakeChunk(), FakeChunk()]) == 3

    @pytest.mark.asyncio
    async def test_retrieve_returns_empty_when_disabled(
        self, cognee_rag_mod, enabled_reader
    ) -> None:
        """retrieve returns [] when the underlying reader is disabled."""
        enabled_reader.enabled = False
        r = cognee_rag_mod.CogneeRAGRetriever(enabled_reader)
        result = await r.retrieve("test query")
        assert result == []
        enabled_reader.read.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_retrieve_passes_top_k(
        self, cognee_rag_mod, enabled_reader
    ) -> None:
        """retrieve forwards top_k to the reader."""
        r = cognee_rag_mod.CogneeRAGRetriever(enabled_reader)
        await r.retrieve("test query", top_k=10)
        enabled_reader.read.assert_awaited_once_with(query="test query", top_k=10, dataset=None)

    @pytest.mark.asyncio
    async def test_retrieve_extracts_dataset_from_filters(
        self, cognee_rag_mod, enabled_reader
    ) -> None:
        """retrieve extracts the dataset filter and passes it to the reader."""
        r = cognee_rag_mod.CogneeRAGRetriever(enabled_reader)
        await r.retrieve("test query", filters={"dataset": "agents"})
        enabled_reader.read.assert_awaited_once_with(
            query="test query", top_k=5, dataset="agents"
        )

    @pytest.mark.asyncio
    async def test_retrieve_maps_hits_to_search_results(
        self, cognee_rag_mod, enabled_reader
    ) -> None:
        """retrieve maps Cognee hits to SearchResult dataclass instances."""
        enabled_reader.read = AsyncMock(
            return_value=[
                {
                    "id": "h1",
                    "content": "Some context",
                    "score": 0.87,
                    "metadata": {"source": "doc1"},
                }
            ]
        )
        r = cognee_rag_mod.CogneeRAGRetriever(enabled_reader)
        results = await r.retrieve("test query")
        assert len(results) == 1
        assert results[0].id == "h1"
        assert results[0].content == "Some context"
        assert results[0].score == 0.87
        assert results[0].metadata == {"source": "doc1"}

    @pytest.mark.asyncio
    async def test_retrieve_handles_missing_fields(
        self, cognee_rag_mod, enabled_reader
    ) -> None:
        """retrieve handles hits with missing optional fields gracefully."""
        enabled_reader.read = AsyncMock(
            return_value=[
                {"content": "no id, no score, no metadata"},
                {},
            ]
        )
        r = cognee_rag_mod.CogneeRAGRetriever(enabled_reader)
        results = await r.retrieve("test query")
        assert len(results) == 2
        assert results[0].id == ""
        assert results[0].content == "no id, no score, no metadata"
        assert results[0].score == 0.0
        assert results[0].metadata == {}
        assert results[1].content == ""

    @pytest.mark.asyncio
    async def test_retrieve_increments_recent_count(
        self, cognee_rag_mod, enabled_reader
    ) -> None:
        """retrieve increments the recent_retrievals counter."""
        r = cognee_rag_mod.CogneeRAGRetriever(enabled_reader)
        await r.retrieve("q1")
        await r.retrieve("q2")
        await r.retrieve("q3")
        assert r._recent_retrievals == 3

    @pytest.mark.asyncio
    async def test_health_delegates_to_reader(
        self, cognee_rag_mod, enabled_reader
    ) -> None:
        """health() returns the reader's health() result."""
        enabled_reader.health = AsyncMock(return_value=True)
        r = cognee_rag_mod.CogneeRAGRetriever(enabled_reader)
        assert await r.health() is True
        enabled_reader.health.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_close_delegates_to_reader(
        self, cognee_rag_mod, enabled_reader
    ) -> None:
        """close() delegates to the reader's close()."""
        r = cognee_rag_mod.CogneeRAGRetriever(enabled_reader)
        await r.close()
        enabled_reader.close.assert_awaited_once()

    def test_get_statistics_includes_backend(
        self, cognee_rag_mod, enabled_reader
    ) -> None:
        """get_statistics reports the backend as 'cognee'."""
        r = cognee_rag_mod.CogneeRAGRetriever(enabled_reader)
        stats = r.get_statistics()
        assert stats["backend"] == "cognee"
        assert stats["cognee_enabled"] is True
        assert stats["cognee_api_url"] == "http://cognee:8000"
        assert stats["recent_retrievals"] == 0
        assert "uptime_seconds" in stats


class TestGetRagRetrieverFactory:
    """Factory: get_rag_retriever always returns CogneeRAGRetriever."""

    def test_default_returns_cognee(
        self, cognee_rag_mod, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Default (HERETEK_USE_COGNEE_RAG unset) returns CogneeRAGRetriever."""
        monkeypatch.delenv("HERETEK_USE_COGNEE_RAG", raising=False)
        backend = cognee_rag_mod.get_rag_retriever()
        assert isinstance(backend, cognee_rag_mod.CogneeRAGRetriever)

    def test_false_returns_cognee(
        self, cognee_rag_mod, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """HERETEK_USE_COGNEE_RAG=false still returns CogneeRAGRetriever (env var ignored)."""
        monkeypatch.setenv("HERETEK_USE_COGNEE_RAG", "false")
        assert isinstance(cognee_rag_mod.get_rag_retriever(), cognee_rag_mod.CogneeRAGRetriever)

    def test_true_returns_cognee(
        self, cognee_rag_mod, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """HERETEK_USE_COGNEE_RAG=true returns CogneeRAGRetriever."""
        monkeypatch.setenv("HERETEK_USE_COGNEE_RAG", "true")
        backend = cognee_rag_mod.get_rag_retriever()
        assert isinstance(backend, cognee_rag_mod.CogneeRAGRetriever)

    def test_yes_returns_cognee(
        self, cognee_rag_mod, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """HERETEK_USE_COGNEE_RAG=yes returns CogneeRAGRetriever."""
        monkeypatch.setenv("HERETEK_USE_COGNEE_RAG", "yes")
        assert isinstance(cognee_rag_mod.get_rag_retriever(), cognee_rag_mod.CogneeRAGRetriever)

    def test_one_returns_cognee(
        self, cognee_rag_mod, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """HERETEK_USE_COGNEE_RAG=1 returns CogneeRAGRetriever."""
        monkeypatch.setenv("HERETEK_USE_COGNEE_RAG", "1")
        assert isinstance(cognee_rag_mod.get_rag_retriever(), cognee_rag_mod.CogneeRAGRetriever)
