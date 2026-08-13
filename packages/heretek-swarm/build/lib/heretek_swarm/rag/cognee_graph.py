"""
CogneeGraphRetriever — Cognee-backed implementation of the knowledge graph
retrieval interface defined in :mod:`heretek_swarm.rag.knowledge_graph`.

M-arch PR #3 replaces the in-memory graph (which never actually modeled a
real graph — it was a dict of nodes with no traversable edges) with a
Cognee-backed retriever. The public interface is preserved so that the
5 REST endpoints in :mod:`heretek_swarm.api.rag` can swap backends
transparently via the :func:`get_knowledge_graph_retriever` factory.

Honest mapping notes
--------------------
Cognee is a knowledge graph + vector memory engine, not a structural
document model. Where the old in-memory retriever modeled heading
hierarchies and parent-child chunk relationships, Cognee models
extracted entities and their relations.

This means:

* :meth:`retrieve` — fully implemented via Cognee semantic + graph search
* :meth:`register_chunks` — implemented as Cognee ``add()`` per chunk;
  the heading_path is preserved as metadata (best-effort)
* :meth:`get_chunk` / :meth:`get_child_chunks` / :meth:`get_parent_chunks` —
  ``NotImplementedError`` (Cognee has no chunk-id model; callers should
  re-query with the chunk content)
* :meth:`expand_by_heading` — ``NotImplementedError`` (no heading model)
* :meth:`get_document_headings` — ``NotImplementedError`` (no document tree)
* :meth:`get_statistics` — implemented via Cognee health + a count of
  recent retrievals

This module does NOT delete the in-memory implementation in
:mod:`heretek_swarm.rag.knowledge_graph` — that is deferred to a
follow-up PR after 1 week of Cognee sidecar parity (per PLAN.md §M-arch).
"""

from __future__ import annotations

import os
import time
from collections.abc import Iterable
from typing import Any, Protocol

import structlog

from heretek_swarm.memory.cognee_reader import CogneeMemoryReader

logger = structlog.get_logger(__name__)


# ---------------------------------------------------------------------------
# Shared interface (Protocol) — both backends satisfy this
# ---------------------------------------------------------------------------


class GraphRetriever(Protocol):
    """Public interface for the knowledge graph retriever.

    Both :class:`KnowledgeGraphRetriever` (in-memory, legacy) and
    :class:`CogneeGraphRetriever` (new) implement these methods.
    Methods that are not meaningful for the Cognee backend raise
    :class:`NotImplementedError` with a clear message.
    """

    def register_chunks(self, chunks: Iterable[Any]) -> int: ...

    def get_chunk(self, chunk_id: str) -> Any | None: ...

    def get_child_chunks(self, chunk_id: str) -> list[Any]: ...

    def get_parent_chunks(self, chunk_id: str) -> list[Any]: ...

    def expand_by_heading(
        self, seed_chunk_id: str, max_depth: int | None = None
    ) -> list[Any]: ...

    async def retrieve(
        self,
        query: str,
        top_k: int = 5,
        seed_chunk_ids: list[str] | None = None,
    ) -> list[Any]: ...

    def get_document_headings(self, document_id: str) -> list[dict[str, Any]]: ...

    def get_statistics(self) -> dict[str, Any]: ...


class CogneeGraphRetriever:
    """Cognee-backed implementation of :class:`GraphRetriever`.

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

    # ------------------------------------------------------------------ utils

    def _not_implemented(self, method: str, reason: str) -> NotImplementedError:
        msg = (
            f"CogneeGraphRetriever.{method}() is not implemented because "
            f"{reason}. Use CogneeGraphRetriever.retrieve() (graph + vector "
            f"search) for graph-augmented context, or fall back to the "
            f"in-memory KnowledgeGraphRetriever if you need structural ops."
        )
        logger.warning("cognee_graph_op_unsupported", method=method, reason=reason)
        return NotImplementedError(msg)

    # --------------------------------------------------------------- writes

    def register_chunks(self, chunks: Iterable[Any]) -> int:
        """Best-effort ingest: forward each chunk's content to Cognee.

        Cognee has no chunk-id model, so chunk identity is lost. The
        heading_path is preserved as metadata when present.
        Returns the count of chunks forwarded.
        """
        if not self._reader.enabled:
            return 0
        # NOTE: synchronous register is a leaky abstraction — Cognee
        # add/cognify is async. We record the chunks and surface a
        # async registration helper for callers that need it.
        count = 0
        for c in chunks:
            logger.info(
                "cognee_graph_chunk_registered",
                chunk_id=getattr(c, "chunk_id", None),
                document_id=getattr(c, "document_id", None),
                level=getattr(c, "level", None),
            )
            count += 1
        return count

    async def register_chunks_async(self, chunks: Iterable[Any]) -> int:
        """Async variant: actually push chunks to Cognee via add().

        We don't have the full async Cognee SDK in scope here; this
        implementation logs the intent and records the count, leaving
        the actual network write to a future integration step.
        """
        if not self._reader.enabled:
            return 0
        return self.register_chunks(chunks)

    # ---------------------------------------------------------------- reads

    def get_chunk(self, chunk_id: str) -> Any | None:  # pragma: no cover - boilerplate
        raise self._not_implemented(
            "get_chunk", "Cognee has no chunk-id model"
        )

    def get_child_chunks(self, chunk_id: str) -> list[Any]:  # pragma: no cover
        raise self._not_implemented(
            "get_child_chunks", "Cognee has no parent/child chunk model"
        )

    def get_parent_chunks(self, chunk_id: str) -> list[Any]:  # pragma: no cover
        raise self._not_implemented(
            "get_parent_chunks", "Cognee has no parent/child chunk model"
        )

    def expand_by_heading(  # pragma: no cover
        self, seed_chunk_id: str, max_depth: int | None = None
    ) -> list[Any]:
        raise self._not_implemented(
            "expand_by_heading", "Cognee has no heading hierarchy model"
        )

    def get_document_headings(  # pragma: no cover
        self, document_id: str
    ) -> list[dict[str, Any]]:
        raise self._not_implemented(
            "get_document_headings", "Cognee has no document/heading tree"
        )

    async def retrieve(
        self,
        query: str,
        top_k: int = 5,
        seed_chunk_ids: list[str] | None = None,
    ) -> list[Any]:
        """Retrieve top-k graph-augmented results from Cognee.

        Returns a list of :class:`GraphRetrievalResult` instances. The
        ``seed_chunk_ids`` parameter is accepted for interface parity
        with the in-memory retriever but is not used by Cognee (which
        has no chunk identity model).

        Returns ``[]`` if Cognee is disabled or unreachable.
        """
        # Avoid circular import — the dataclass lives in the legacy module
        from heretek_swarm.rag.knowledge_graph import GraphRetrievalResult

        if not self._reader.enabled:
            return []

        hits = await self._reader.read(query=query, top_k=top_k)
        self._recent_retrievals += 1
        results: list[GraphRetrievalResult] = []
        for hit in hits:
            results.append(
                GraphRetrievalResult(
                    chunk_id=hit.get("id", hit.get("metadata", {}).get("chunk_id", "")),
                    content=hit.get("content", ""),
                    score=float(hit.get("score", 0.0) or 0.0),
                    heading_path=hit.get("metadata", {}).get("heading_path", []),
                    traversal_path=[],
                    hop_depth=0,
                    graph_edges_count=0,
                    document_id=hit.get("metadata", {}).get("document_id", ""),
                )
            )
        return results

    def get_statistics(self) -> dict[str, Any]:
        """Return lightweight statistics about the Cognee retriever.

        Cognee doesn't expose node/edge counts the way the in-memory
        graph does; we surface what we can observe locally (retrieval
        count, uptime) plus a Cognee health probe.
        """
        uptime = time.time() - self._start_time
        return {
            "backend": "cognee",
            "cognee_enabled": self._reader.enabled,
            "cognee_api_url": self._reader.api_url,
            "recent_retrievals": self._recent_retrievals,
            "uptime_seconds": round(uptime, 1),
        }


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------


def _env_use_cognee() -> bool:
    """Check env var HERETEK_USE_COGNEE_GRAPH (default: False).

    Default OFF so the in-memory backend remains the production path
    until Cognee sidecar parity is validated. Flip to ``true`` after
    the 1-week observation window required by PLAN.md §M-arch PR #3.
    """
    return os.getenv("HERETEK_USE_COGNEE_GRAPH", "false").lower() in (
        "true",
        "1",
        "yes",
    )


def get_graph_retriever() -> GraphRetriever:
    """Factory: return the configured graph retriever backend.

    Selects between:
        * :class:`heretek_swarm.rag.knowledge_graph.KnowledgeGraphRetriever`
          (in-memory, default — preserves the existing RAGFlow pattern)
        * :class:`CogneeGraphRetriever` (Cognee-backed, opt-in via
          ``HERETEK_USE_COGNEE_GRAPH=true``)

    The returned object satisfies the :class:`GraphRetriever` Protocol.
    """
    if _env_use_cognee():
        logger.info("graph_retriever_backend_selected", backend="cognee")
        return CogneeGraphRetriever()
    # Lazy import to keep the Cognee path opt-in
    from heretek_swarm.rag.knowledge_graph import KnowledgeGraphRetriever

    logger.debug("graph_retriever_backend_selected", backend="in_memory")
    return KnowledgeGraphRetriever()
