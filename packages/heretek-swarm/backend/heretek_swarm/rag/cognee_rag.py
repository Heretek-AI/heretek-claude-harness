"""
CogneeRAGRetriever — Cognee-backed implementation of the RAG retrieval
interface defined in :mod:`heretek_swarm.rag.retriever`.

Cognee is the default and only RAG retriever backend. The legacy
in-memory ``RAGPipeline`` has been removed.

Honest mapping notes
--------------------
Cognee is a knowledge graph + vector memory engine, not a structural
document pipeline. This module implements the retrieval surface:

* :meth:`retrieve` — implemented via CogneeMemoryReader.search
* :meth:`register_chunks` — best-effort: logs chunks (Cognee ingestion
  is async and goes through a separate ``cognee.add()`` path)
* :meth:`health` — implemented via CogneeMemoryReader.health
* :meth:`close` — closes the injected client if owned
* :meth:`get_statistics` — light telemetry (recent retrievals, uptime)
"""

from __future__ import annotations

import time
from collections.abc import Iterable
from typing import Any, Protocol, runtime_checkable

import structlog

from heretek_swarm_core.memory.cognee_reader import CogneeMemoryReader
from heretek_swarm.rag.retriever import SearchResult

logger = structlog.get_logger(__name__)


@runtime_checkable
class RAGRetriever(Protocol):
    """Public interface for the RAG retriever.

    :class:`CogneeRAGRetriever` implements these methods. Methods that
    are not meaningful for the Cognee backend return sensible no-ops
    (empty list / False) so callers can use a single interface without
    branching.
    """

    async def retrieve(
        self,
        query: str,
        top_k: int = 5,
        filters: dict[str, Any] | None = None,
    ) -> list[SearchResult]: ...

    def register_chunks(self, chunks: Iterable[Any]) -> int: ...

    async def health(self) -> bool: ...

    async def close(self) -> None: ...

    def get_statistics(self) -> dict[str, Any]: ...


class CogneeRAGRetriever:
    """Cognee-backed implementation of :class:`RAGRetriever`.

    Uses :class:`CogneeMemoryReader` for all network operations, so it
    inherits the same graceful-fallback contract: if Cognee is disabled
    or unreachable, reads return empty results and writes are logged
    warnings.

    Args:
        reader: Optional pre-configured :class:`CogneeMemoryReader`. If
            ``None``, a new one is constructed (env-driven config).
    """

    def __init__(self, reader: CogneeMemoryReader | None = None) -> None:
        self._reader = reader or CogneeMemoryReader()
        self._recent_retrievals: int = 0
        self._start_time: float = time.time()

    async def retrieve(
        self,
        query: str,
        top_k: int = 5,
        filters: dict[str, Any] | None = None,
    ) -> list[SearchResult]:
        """Retrieve top-k results from Cognee.

        Returns a list of :class:`SearchResult` instances. The
        ``filters`` parameter is accepted for interface parity with the
        in-memory retriever but is not used by Cognee (which has its
        own dataset-based filtering via ``cognee.search(dataset=...)``).

        Returns ``[]`` if Cognee is disabled or unreachable.
        """
        if not self._reader.enabled:
            return []
        dataset = None
        if filters and "dataset" in filters:
            dataset = str(filters["dataset"])
        hits = await self._reader.read(query=query, top_k=top_k, dataset=dataset)
        self._recent_retrievals += 1
        results: list[SearchResult] = []
        for hit in hits:
            results.append(
                SearchResult(
                    id=str(hit.get("id", "")),
                    content=str(hit.get("content", "")),
                    score=float(hit.get("score", 0.0) or 0.0),
                    metadata=dict(hit.get("metadata", {}) or {}),
                )
            )
        return results

    def register_chunks(self, chunks: Iterable[Any]) -> int:
        """Best-effort ingest: log the chunks for future Cognee ``add()`` calls.

        Cognee ingestion is async (cognee.add/cognify is async), so this
        is a stub for now. The full async ingestion path is deferred
        to a follow-up PR.
        """
        if not self._reader.enabled:
            return 0
        count = 0
        for c in chunks:
            logger.info(
                "cognee_rag_chunk_registered",
                chunk_id=getattr(c, "chunk_id", None),
                document_id=getattr(c, "document_id", None),
            )
            count += 1
        return count

    async def health(self) -> bool:
        """Return True if Cognee is reachable and healthy."""
        return await self._reader.health()

    async def close(self) -> None:
        """Close the underlying HTTP client (call on agent shutdown)."""
        await self._reader.close()

    def get_statistics(self) -> dict[str, Any]:
        """Return lightweight statistics about the Cognee retriever."""
        uptime = time.time() - self._start_time
        return {
            "backend": "cognee",
            "cognee_enabled": self._reader.enabled,
            "cognee_api_url": self._reader.api_url,
            "recent_retrievals": self._recent_retrievals,
            "uptime_seconds": round(uptime, 1),
        }


def get_rag_retriever() -> RAGRetriever:
    """Factory: return ``CogneeRAGRetriever`` (the only RAG backend).

    Cognee is now the default and only retriever. The legacy in-memory
    ``RAGPipeline`` has been removed.
    """
    logger.info("rag_retriever_backend_selected", backend="cognee")
    return CogneeRAGRetriever()
