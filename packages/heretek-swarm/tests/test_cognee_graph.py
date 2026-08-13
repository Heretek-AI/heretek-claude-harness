"""
Tests for CogneeGraphRetriever + the get_graph_retriever factory.

Per M-arch PR #3: verify the Cognee-backed graph retriever behaves
correctly when Cognee is enabled, disabled, or unreachable; and verify
the factory selects the right backend based on env.
"""

from __future__ import annotations

import importlib.util
import os
from unittest.mock import AsyncMock, MagicMock

import pytest


def _load_cognee_graph_module():
    """Load cognee_graph.py without triggering the heavy heretek_swarm package import."""
    spec = importlib.util.spec_from_file_location(
        "cognee_graph_under_test",
        "backend/heretek_swarm/rag/cognee_graph.py",
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture
def cognee_graph_mod():
    return _load_cognee_graph_module()


@pytest.fixture
def enabled_reader():
    """A pre-configured CogneeMemoryReader that is enabled and has a mocked client."""
    r = MagicMock()
    r.enabled = True
    r.api_url = "http://cognee:8000"
    r.read = AsyncMock(return_value=[])
    return r


class TestCogneeGraphRetriever:
    """Behavioral tests for CogneeGraphRetriever."""

    def test_default_construction(self, cognee_graph_mod) -> None:
        """CogneeGraphRetriever can be constructed with no args."""
        # Patch the CogneeMemoryReader to be disabled so we don't try to connect
        os.environ["COGNEE_ENABLED"] = "false"
        retriever = cognee_graph_mod.CogneeGraphRetriever()
        assert retriever._reader is not None
        assert retriever._reader.enabled is False
        del os.environ["COGNEE_ENABLED"]

    def test_register_chunks_disabled_returns_zero(
        self, cognee_graph_mod, enabled_reader
    ) -> None:
        """register_chunks is a no-op when the underlying reader is disabled."""
        enabled_reader.enabled = False
        r = cognee_graph_mod.CogneeGraphRetriever(enabled_reader)

        class FakeChunk:
            chunk_id = "c1"
            document_id = "d1"
            level = 0

        assert r.register_chunks([FakeChunk(), FakeChunk()]) == 0

    def test_register_chunks_counts_when_enabled(
        self, cognee_graph_mod, enabled_reader
    ) -> None:
        """register_chunks returns the count of chunks forwarded."""
        r = cognee_graph_mod.CogneeGraphRetriever(enabled_reader)

        class FakeChunk:
            chunk_id = "c1"
            document_id = "d1"
            level = 0

        assert r.register_chunks([FakeChunk(), FakeChunk(), FakeChunk()]) == 3

    @pytest.mark.asyncio
    async def test_retrieve_returns_empty_when_disabled(
        self, cognee_graph_mod, enabled_reader
    ) -> None:
        """retrieve returns [] when the reader is disabled (no Cognee call)."""
        enabled_reader.enabled = False
        enabled_reader.read = AsyncMock()
        r = cognee_graph_mod.CogneeGraphRetriever(enabled_reader)
        result = await r.retrieve("test query")
        assert result == []
        enabled_reader.read.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_retrieve_formats_hits_as_graph_results(
        self, cognee_graph_mod, enabled_reader
    ) -> None:
        """retrieve translates Cognee hits into GraphRetrievalResult instances."""
        GraphRetrievalResult = cognee_graph_mod.GraphRetrievalResult

        enabled_reader.read = AsyncMock(
            return_value=[
                {
                    "id": "chunk-1",
                    "content": "Some context",
                    "score": 0.85,
                    "metadata": {
                        "document_id": "doc-1",
                        "heading_path": ["Intro", "Background"],
                    },
                }
            ]
        )
        r = cognee_graph_mod.CogneeGraphRetriever(enabled_reader)
        results = await r.retrieve("test", top_k=3)

        assert len(results) == 1
        assert isinstance(results[0], GraphRetrievalResult)
        assert results[0].chunk_id == "chunk-1"
        assert results[0].content == "Some context"
        assert results[0].score == 0.85
        assert results[0].heading_path == ["Intro", "Background"]
        assert results[0].document_id == "doc-1"

    @pytest.mark.asyncio
    async def test_retrieve_handles_empty_cognee_response(
        self, cognee_graph_mod, enabled_reader
    ) -> None:
        """retrieve returns [] when Cognee returns no hits."""
        enabled_reader.read = AsyncMock(return_value=[])
        r = cognee_graph_mod.CogneeGraphRetriever(enabled_reader)
        results = await r.retrieve("test")
        assert results == []

    def test_structural_methods_raise_not_implemented(
        self, cognee_graph_mod, enabled_reader
    ) -> None:
        """CogneeGraphRetriever has no structural model — these raise NotImplementedError."""
        r = cognee_graph_mod.CogneeGraphRetriever(enabled_reader)
        with pytest.raises(NotImplementedError, match="no chunk-id model"):
            r.get_chunk("c1")
        with pytest.raises(NotImplementedError, match="no parent/child chunk model"):
            r.get_child_chunks("c1")
        with pytest.raises(NotImplementedError, match="no parent/child chunk model"):
            r.get_parent_chunks("c1")
        with pytest.raises(NotImplementedError, match="no heading hierarchy model"):
            r.expand_by_heading("c1")
        with pytest.raises(NotImplementedError, match="no document/heading tree"):
            r.get_document_headings("doc-1")

    def test_get_statistics_reports_backend(self, cognee_graph_mod, enabled_reader) -> None:
        """get_statistics surfaces the backend and Cognee config."""
        r = cognee_graph_mod.CogneeGraphRetriever(enabled_reader)
        stats = r.get_statistics()
        assert stats["backend"] == "cognee"
        assert stats["cognee_enabled"] is True
        assert stats["cognee_api_url"] == "http://cognee:8000"
        assert stats["recent_retrievals"] == 0
        assert "uptime_seconds" in stats

    @pytest.mark.asyncio
    async def test_register_chunks_async_disabled_returns_zero(
        self, cognee_graph_mod, enabled_reader
    ) -> None:
        """async register_chunks returns 0 when reader is disabled (no forwarding)."""
        enabled_reader.enabled = False
        r = cognee_graph_mod.CogneeGraphRetriever(enabled_reader)

        class FakeChunk:
            chunk_id = "c1"
            document_id = "d1"
            level = 0

        assert await r.register_chunks_async([FakeChunk(), FakeChunk()]) == 0

    @pytest.mark.asyncio
    async def test_retrieve_ignores_seed_chunk_ids(
        self, cognee_graph_mod, enabled_reader
    ) -> None:
        """retrieve() accepts seed_chunk_ids for interface parity but ignores it."""
        enabled_reader.read = AsyncMock(
            return_value=[
                {
                    "id": "chunk-1",
                    "content": "Some context",
                    "score": 0.85,
                    "metadata": {
                        "document_id": "doc-1",
                        "heading_path": ["Intro"],
                    },
                }
            ]
        )
        r = cognee_graph_mod.CogneeGraphRetriever(enabled_reader)

        # Without seed_chunk_ids
        result_without = await r.retrieve("test query")

        # With seed_chunk_ids — should not raise, same result
        result_with = await r.retrieve(
            "test query", seed_chunk_ids=["chunk-1", "chunk-2"]
        )

        assert len(result_without) == 1
        assert len(result_with) == 1
        assert result_with[0].chunk_id == result_without[0].chunk_id

    @pytest.mark.asyncio
    async def test_get_statistics_increments_on_retrieve(
        self, cognee_graph_mod, enabled_reader
    ) -> None:
        """recent_retrievals counter ticks up after each retrieve call."""
        enabled_reader.read = AsyncMock(return_value=[])
        r = cognee_graph_mod.CogneeGraphRetriever(enabled_reader)
        await r.retrieve("q1")
        await r.retrieve("q2")
        await r.retrieve("q3")
        assert r.get_statistics()["recent_retrievals"] == 3


class TestGetGraphRetrieverFactory:
    """Tests for the backend-selection factory."""

    def test_default_returns_in_memory(self, cognee_graph_mod, monkeypatch) -> None:
        """Without HERETEK_USE_COGNEE_GRAPH, factory returns the in-memory retriever."""
        monkeypatch.delenv("HERETEK_USE_COGNEE_GRAPH", raising=False)
        # The factory will import KnowledgeGraphRetriever from the legacy module;
        # if that module fails to import, just check the type returned
        retriever = cognee_graph_mod.get_graph_retriever()
        # If we get a KnowledgeGraphRetriever, great; if we get a CogneeGraphRetriever,
        # the env was set somewhere. Either way, check it's not the wrong one.
        assert not isinstance(retriever, cognee_graph_mod.CogneeGraphRetriever) or (
            os.getenv("HERETEK_USE_COGNEE_GRAPH", "false").lower() in ("true", "1", "yes")
        )

    def test_env_flag_returns_cognee(self, cognee_graph_mod, monkeypatch) -> None:
        """With HERETEK_USE_COGNEE_GRAPH=true, factory returns CogneeGraphRetriever."""
        monkeypatch.setenv("HERETEK_USE_COGNEE_GRAPH", "true")
        # Make sure the reader it constructs is disabled so we don't try to connect
        monkeypatch.setenv("COGNEE_ENABLED", "false")
        retriever = cognee_graph_mod.get_graph_retriever()
        assert isinstance(retriever, cognee_graph_mod.CogneeGraphRetriever)

    def test_env_variants(self, cognee_graph_mod, monkeypatch) -> None:
        """All truthy variants of HERETEK_USE_COGNEE_GRAPH enable the Cognee backend."""
        for value in ("true", "True", "TRUE", "1", "yes"):
            monkeypatch.setenv("HERETEK_USE_COGNEE_GRAPH", value)
            monkeypatch.setenv("COGNEE_ENABLED", "false")
            retriever = cognee_graph_mod.get_graph_retriever()
            assert isinstance(retriever, cognee_graph_mod.CogneeGraphRetriever), (
                f"value={value!r} should select Cognee backend"
            )

        for value in ("false", "0", "no", ""):
            monkeypatch.setenv("HERETEK_USE_COGNEE_GRAPH", value)
            retriever = cognee_graph_mod.get_graph_retriever()
            assert not isinstance(retriever, cognee_graph_mod.CogneeGraphRetriever), (
                f"value={value!r} should NOT select Cognee backend"
            )
