"""
Knowledge Graph Retriever — Graph-based Retrieval-Augmented Generation

.. deprecated::
    This module is the in-memory implementation of the knowledge graph
    retriever. It is being replaced by Cognee as part of M-arch PR #3
    (see PLAN.md §M-arch).

    New code should use :func:`heretek_swarm.rag.cognee_graph.get_graph_retriever`
    which returns either this in-memory backend (default, preserves
    existing RAGFlow pattern) or the new Cognee-backed
    :class:`CogneeGraphRetriever` (opt-in via
    ``HERETEK_USE_COGNEE_GRAPH=true``).

    This file is scheduled for **deletion** in a follow-up PR after 1
    week of Cognee sidecar parity. Do not add new code that depends on
    the in-memory implementation directly — call the factory instead.

Provides graph-augmented RAG that exploits document structure:
- Document graph: chunks as nodes with parent-child heading relationships
- Graph traversal: hierarchical expansion from chunk → heading → section → document
- Sub-question decomposition: complex queries broken into simpler sub-queries
- Knowledge graph retrieval: traverse entity/similarity edges to build context

Inspired by RAGFlow's knowledge graph retrieval patterns.
"""

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

import structlog

logger = structlog.get_logger(__name__)


class GraphRelationshipType(StrEnum):
    """Types of edges in the knowledge graph."""

    PARENT_CHUNK = "parent_chunk"  # Chunk → parent chunk (heading hierarchy)
    DOCUMENT_CHUNK = "document_chunk"  # Document → constituent chunks
    CHUNK_SIMILARITY = "chunk_similarity"  # Semantically similar chunks
    ENTITY_LINK = "entity_link"  # Entity mention → entity node
    SECTION_CHUNK = "section_chunk"  # Section → chunks in that section
    ROOT_CHUNK = "root_chunk"  # Document → root (top-level) chunks


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
    - Sequential: "What is X? How does X affect Y?" → ["What is X?", "How does X affect Y?"]
    - Hierarchical: "Explain X including its components" → parent + children
    - Causal: "Why did X happen and what resulted?" → [cause, effect]
    - Comparative: "Compare X and Y" → [X properties, Y properties]
    """

    def decompose(self, query: str) -> list[str]:
        """
        Decompose a query into sub-questions.

        Args:
            query: Complex query string

        Returns:
            List of sub-question strings
        """
        import re

        sub_questions = []

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
            # Reconstruct comparative sub-questions
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
                    # Each sub-part gets its own query
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


class KnowledgeGraphRetriever:
    """
    Graph-augmented retriever that exploits document heading structure.

    Complements the existing HybridRetriever with:
    1. Document graph traversal (heading hierarchy)
    2. Sub-question decomposition for complex queries
    3. Multi-hop context accumulation

    This is additive to the existing RAG pipeline — does not replace it.
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

        # In-memory document graph (chunk_id → GraphChunkNode)
        self._chunk_graph: dict[str, GraphChunkNode] = {}

        # Heading → chunks mapping (for hierarchical expansion)
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
                headings.append(  # noqa: PERF401
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
