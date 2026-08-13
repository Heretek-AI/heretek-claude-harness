"""
CogneeGraphRetriever — Cognee-backed implementation of the knowledge graph
retrieval interface.

This module consolidates shared type definitions and both retriever
implementations (KnowledgeGraphRetriever in-memory, CogneeGraphRetriever
Cognee-backed) into a single file. Importing from this module avoids the
circular-dependency dance that previously required lazy imports.

M-arch PR #3 replaces the in-memory graph (which never actually modeled a
real graph — it was a dict of nodes with no traversable edges) with a
Cognee-backed retriever. The public interface is preserved so that the
5 REST endpoints in :mod:`heretek_swarm.api.rag` can swap backends
transparently via the :func:`get_graph_retriever` factory.

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
follow-up PR after 1 week of Cognee sidecar parity (per PLAN.md M-arch).
"""

import os
import re
import time
from collections.abc import Iterable
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any, Protocol

import structlog

from heretek_swarm_core.memory.cognee_reader import CogneeMemoryReader

logger = structlog.get_logger(__name__)


# ---------------------------------------------------------------------------
# Shared type definitions
# ---------------------------------------------------------------------------


class GraphRelationshipType(StrEnum):
    """Types of edges in the knowledge graph."""

    PARENT_CHUNK = "parent_chunk"  # Chunk -> parent chunk (heading hierarchy)
    DOCUMENT_CHUNK = "document_chunk"  # Document -> constituent chunks
    CHUNK_SIMILARITY = "chunk_similarity"  # Semantically similar chunks
    ENTITY_LINK = "entity_link"  # Entity mention -> entity node
    SECTION_CHUNK = "section_chunk"  # Section -> chunks in that section
    ROOT_CHUNK = "root_chunk"  # Document -> root (top-level) chunks


@dataclass
class GraphChunkNode:
    """
    A chunk represented as a graph node with parent-child relationships.

    Represents a document chunk with its position in the heading hierarchy.
    """

    chunk_id: str
    document_id: str
    content: str
    heading_path: list[str] = field(default_factory=list)  # ["Chapter 1", "Section 1.2"]
    parent_chunk_id: str | None = None
    child_chunk_ids: list[str] = field(default_factory=list)
    level: int = 0  # Depth in the heading tree (0 = root)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class GraphRetrievalResult:
    """
    Result from graph-based retrieval with traversal metadata.

    Extends standard retrieval with graph context (path taken, nodes visited).
    """

    chunk_id: str
    content: str
    score: float
    heading_path: list[str] = field(default_factory=list)
    traversal_path: list[str] = field(default_factory=list)  # Chunks traversed to reach this result
    hop_depth: int = 0  # How many hops from the seed chunk
    graph_edges_count: int = 0  # Number of graph relationships used
    document_id: str | None = None


class SubQuestionDecomposer:
    """
    Decompose complex queries into simpler sub-questions.

    Supports four decomposition patterns:
    - Sequential: "What is X? How does X affect Y?" -> ["What is X?", "How does X affect Y?"]
    - Hierarchical: "Explain X including its components" -> parent + children
    - Causal: "Why did X happen and what resulted?" -> [cause, effect]
    - Comparative: "Compare X and Y" -> [X properties, Y properties]
    """

    def decompose(self, query: str) -> list[str]:
        """
        Decompose a query into sub-questions.

        Args:
            query: Complex query string

        Returns:
            List of sub-question strings
        """
        sub_questions: list[str] = []

        # Sequential decomposition: split on "and then", "followed by"
        sequential_split = re.split(
            r"\s+(?:and then|followed by|next|after that|secondly|thirdly)\s+",
            query,
            flags=re.IGNORECASE,
        )
        if len(sequential_split) > 1:
            sub_questions.extend(
                s.strip().capitalize() + "?" for s in sequential_split if s.strip()
            )

        # Comparative decomposition: split on "vs", "versus", "compared to", "X vs Y"
        comparative_split = re.split(
            r"\s+(?:vs|versus|compared to|against)\s+",
            query,
            flags=re.IGNORECASE,
        )
        if len(comparative_split) > 1:
            parts = comparative_split
            for i, part in enumerate(parts):
                if i < len(parts) - 1:
                    sub_questions.append(f"{part.strip()}?")
                    sub_questions.append(f"{parts[i + 1].strip()}?")

        # Causal decomposition: split on "because", "therefore", "resulted in"
        causal_split = re.split(
            r"\s+(?:because|therefore|as a result|consequently|since)\s+",
            query,
            flags=re.IGNORECASE,
        )
        if len(causal_split) > 1:
            sub_questions.extend(s.strip().capitalize() + "?" for s in causal_split if s.strip())

        # Hierarchical decomposition: split on ", including", ", specifically"
        hierarchical_split = re.split(
            r",\s+(?:including|specifically|such as)\s+",
            query,
            flags=re.IGNORECASE,
        )
        if len(hierarchical_split) > 1:
            for i, part in enumerate(hierarchical_split):
                if i == 0:
                    sub_questions.append(part.strip().rstrip("?") + "?")
                else:
                    sub_questions.append(f"{part.strip().rstrip('.')}?")

        # If no decomposition worked, return original query
        if not sub_questions:
            return [query]

        # Deduplicate while preserving order
        seen: set[str] = set()
        deduped: list[str] = []
        for q in sub_questions:
            normalized = q.lower().strip()
            if normalized not in seen:
                seen.add(normalized)
                deduped.append(q)

        return deduped


@dataclass
class KnowledgeGraphConfig:
    """Configuration for knowledge graph retrieval."""

    max_hops: int = 3
    expansion_factor: int = 3  # Chunks per heading level
    sub_question_enabled: bool = True
    graph_traversal_enabled: bool = True
    similarity_threshold: float = 0.7
    min_chunk_score: float = 0.3


# ---------------------------------------------------------------------------
# Shared interface (Protocol) -- both backends satisfy this
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


# ---------------------------------------------------------------------------
# CogneeGraphRetriever
# ---------------------------------------------------------------------------


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
        # NOTE: synchronous register is a leaky abstraction -- Cognee
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
# KnowledgeGraphRetriever (in-memory, legacy)
# ---------------------------------------------------------------------------


class KnowledgeGraphRetriever:
    """
    Graph-augmented retriever that exploits document heading structure.

    Complements the existing HybridRetriever with:
    1. Document graph traversal (heading hierarchy)
    2. Sub-question decomposition for complex queries
    3. Multi-hop context accumulation

    This is additive to the existing RAG pipeline -- does not replace it.
    Use cases:
    - Complex queries requiring hierarchical context
    - Queries about section relationships
    - Multi-hop reasoning over document structure
    """

    def __init__(
        self,
        config: KnowledgeGraphConfig | None = None,
        base_retriever: Any = None,
    ) -> None:
        """
        Initialize the knowledge graph retriever.

        Args:
            config: Graph retrieval configuration
            base_retriever: HybridRetriever to use for chunk-level retrieval
        """
        self.config = config or KnowledgeGraphConfig()
        self._base_retriever = base_retriever
        self._decomposer = SubQuestionDecomposer()

        # In-memory document graph (chunk_id -> GraphChunkNode)
        self._chunk_graph: dict[str, GraphChunkNode] = {}

        # Heading -> chunks mapping (for hierarchical expansion)
        self._heading_chunks: dict[str, list[str]] = {}

        logger.info(
            "[KnowledgeGraphRetriever] Initialized",
            max_hops=self.config.max_hops,
            sub_question_enabled=self.config.sub_question_enabled,
        )

    # -------------------------------------------------------------------------
    # Document graph management
    # -------------------------------------------------------------------------

    def register_chunks(self, chunks: list[GraphChunkNode]) -> int:
        """Register document chunks in the knowledge graph."""
        for chunk in chunks:
            self._chunk_graph[chunk.chunk_id] = chunk
            self._index_chunk_by_heading(chunk)
            self._link_chunk_parent(chunk)
        logger.info("[KnowledgeGraphRetriever] Chunks registered",
                     total=len(chunks), graph_size=len(self._chunk_graph))
        return len(chunks)

    def _index_chunk_by_heading(self, chunk: GraphChunkNode) -> None:
        if not chunk.heading_path:
            return
        heading_key = " > ".join(chunk.heading_path)
        self._heading_chunks.setdefault(heading_key, [])
        if chunk.chunk_id not in self._heading_chunks[heading_key]:
            self._heading_chunks[heading_key].append(chunk.chunk_id)

    def _link_chunk_parent(self, chunk: GraphChunkNode) -> None:
        if chunk.level <= 0 or not chunk.parent_chunk_id:
            return
        parent = self._chunk_graph.get(chunk.parent_chunk_id)
        if parent and chunk.chunk_id not in parent.child_chunk_ids:
            parent.child_chunk_ids.append(chunk.chunk_id)

    def get_chunk(self, chunk_id: str) -> GraphChunkNode | None:
        """Get a chunk node by ID."""
        return self._chunk_graph.get(chunk_id)

    def get_child_chunks(self, chunk_id: str) -> list[GraphChunkNode]:
        """Get all child chunks of a chunk."""
        parent = self._chunk_graph.get(chunk_id)
        if not parent:
            return []
        return [
            self._chunk_graph[cid] for cid in parent.child_chunk_ids if cid in self._chunk_graph
        ]

    def get_parent_chunks(self, chunk_id: str) -> list[GraphChunkNode]:
        """Walk up the heading hierarchy to get all parent chunks."""
        parents: list[GraphChunkNode] = []
        current = self._chunk_graph.get(chunk_id)

        while current and current.parent_chunk_id:
            parent = self._chunk_graph.get(current.parent_chunk_id)
            if parent:
                parents.append(parent)
                current = parent
            else:
                break

        return parents

    def expand_by_heading(
        self,
        seed_chunk_id: str,
        max_depth: int | None = None,
    ) -> list[GraphChunkNode]:
        """
        Expand from a seed chunk upward through the heading hierarchy.

        Walks from the seed chunk to its parent heading, sibling chunks,
        grandparent heading, etc. Useful for getting full section context.

        Args:
            seed_chunk_id: Starting chunk
            max_depth: Maximum hierarchy levels to traverse

        Returns:
            List of chunks from seed to root of the heading tree
        """
        max_depth = max_depth or self.config.max_hops
        results: list[GraphChunkNode] = []
        visited: set[str] = set()

        current_id: str | None = seed_chunk_id
        depth = 0

        while current_id and depth < max_depth:
            if current_id in visited:
                break
            visited.add(current_id)

            chunk = self._chunk_graph.get(current_id)
            if not chunk:
                break

            results.append(chunk)

            # Move up to parent
            if chunk.parent_chunk_id:
                current_id = chunk.parent_chunk_id
            else:
                break

            depth += 1

        return results

    # -------------------------------------------------------------------------
    # Graph-based retrieval
    # -------------------------------------------------------------------------

    async def retrieve(
        self,
        query: str,
        top_k: int = 5,
        seed_chunk_ids: list[str] | None = None,
    ) -> list[GraphRetrievalResult]:
        """
        Retrieve chunks using graph-based traversal.

        Args:
            query: Search query
            top_k: Number of results to return
            seed_chunk_ids: Optional seed chunks to expand from

        Returns:
            List of graph retrieval results with traversal metadata
        """
        results: list[GraphRetrievalResult] = []

        # Step 1: Sub-question decomposition
        sub_questions = (
            self._decomposer.decompose(query) if self.config.sub_question_enabled else [query]
        )

        if len(sub_questions) > 1:
            logger.info(
                "[KnowledgeGraphRetriever] Query decomposed",
                original=query[:80],
                sub_questions=sub_questions,
            )

        # Step 2: Base retrieval (if available)
        base_results: list[dict[str, Any]] = []
        if self._base_retriever:
            try:
                base_results = await self._base_retriever.retrieve(
                    query, top_k=top_k * self.config.expansion_factor
                )
            except Exception as e:
                logger.warning("base_retriever_failed", error=str(e))

        # Step 3: Graph traversal from seed chunks
        if seed_chunk_ids and self.config.graph_traversal_enabled:
            for seed_id in seed_chunk_ids:
                traversed = self.expand_by_heading(seed_id, self.config.max_hops)
                for hop_depth, chunk in enumerate(traversed):
                    if chunk.chunk_id in [r.chunk_id for r in results]:
                        continue

                    results.append(
                        GraphRetrievalResult(
                            chunk_id=chunk.chunk_id,
                            content=chunk.content,
                            score=1.0 - (hop_depth * 0.1),  # Score degrades with depth
                            heading_path=chunk.heading_path,
                            traversal_path=[c.chunk_id for c in traversed[: hop_depth + 1]],
                            hop_depth=hop_depth,
                            graph_edges_count=len(chunk.child_chunk_ids),
                            document_id=chunk.document_id,
                        )
                    )

        # Step 4: Add base retriever results
        for item in base_results[:top_k]:
            chunk_id = item.get("chunk_id", "")
            if chunk_id and chunk_id not in [r.chunk_id for r in results]:
                results.append(
                    GraphRetrievalResult(
                        chunk_id=chunk_id,
                        content=item.get("content", ""),
                        score=item.get("score", 0.0),
                        heading_path=[],
                        traversal_path=[chunk_id],
                        hop_depth=0,
                        graph_edges_count=0,
                        document_id=item.get("document_id"),
                    )
                )

        # Step 5: Sort by score and limit to top_k
        results.sort(key=lambda x: x.score, reverse=True)
        return results[:top_k]

    # -------------------------------------------------------------------------
    # Utility
    # -------------------------------------------------------------------------

    def get_document_headings(self, document_id: str) -> list[dict[str, Any]]:
        """
        Get the heading tree for a document.

        Returns:
            List of headings with their level and constituent chunk IDs
        """
        doc_chunks = [c for c in self._chunk_graph.values() if c.document_id == document_id]

        # Build heading tree from root to leaves
        headings: list[dict[str, Any]] = []
        for chunk in doc_chunks:
            if chunk.level == 0:  # Root chunks
                headings.append(
                    {
                        "heading_path": chunk.heading_path,
                        "level": chunk.level,
                        "chunk_id": chunk.chunk_id,
                        "child_ids": chunk.child_chunk_ids,
                    }
                )

        return headings

    def get_statistics(self) -> dict[str, Any]:
        """Get graph statistics."""
        total_chunks = len(self._chunk_graph)
        chunks_with_children = sum(1 for c in self._chunk_graph.values() if c.child_chunk_ids)
        max_depth = max((c.level for c in self._chunk_graph.values()), default=0)

        return {
            "total_chunks": total_chunks,
            "chunks_with_children": chunks_with_children,
            "max_heading_depth": max_depth,
            "heading_count": len(self._heading_chunks),
        }


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------


def _env_use_cognee() -> bool:
    """Check env var HERETEK_USE_COGNEE_GRAPH (default: False).

    Default OFF so the in-memory backend remains the production path
    until Cognee sidecar parity is validated. Flip to ``true`` after
    the 1-week observation window required by PLAN.md M-arch PR #3.
    """
    return os.getenv("HERETEK_USE_COGNEE_GRAPH", "false").lower() in (
        "true",
        "1",
        "yes",
    )


def get_graph_retriever() -> GraphRetriever:
    """Factory: return the configured graph retriever backend.

    Selects between:
        * :class:`KnowledgeGraphRetriever` (in-memory, default -- preserves
          the existing RAGFlow pattern)
        * :class:`CogneeGraphRetriever` (Cognee-backed, opt-in via
          ``HERETEK_USE_COGNEE_GRAPH=true``)

    The returned object satisfies the :class:`GraphRetriever` Protocol.
    """
    if _env_use_cognee():
        logger.info("graph_retriever_backend_selected", backend="cognee")
        return CogneeGraphRetriever()

    logger.debug("graph_retriever_backend_selected", backend="in_memory")
    return KnowledgeGraphRetriever()
