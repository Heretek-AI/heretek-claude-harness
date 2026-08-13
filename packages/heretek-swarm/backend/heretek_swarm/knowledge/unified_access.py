"""
Unified Knowledge Access Layer for Heretek Swarm

Provides a unified interface for querying both memory and RAG systems,
with intelligent result merging and reranking using MMR (Maximal Marginal Relevance).

This layer is designed for use by:
- Historian agent - Long-term memory and context retrieval
- Perceiver+ agent - Advanced analytics with combined knowledge sources
- All other agents - Standardized knowledge access pattern

Enhanced with Advanced RAG Strategies:
- Dense retrieval (vector similarity)
- Sparse retrieval (BM25)
- Hybrid retrieval (combined scoring)
- Multi-hop retrieval (chained queries)
- Re-ranking (cross-encoder scoring)
"""

from dataclasses import dataclass, field
from typing import Any, Literal, Optional

import structlog

logger = structlog.get_logger(__name__)

# Import advanced RAG strategies
try:
    from heretek_swarm.rag.hybrid_retriever import (
        FusionMethod,
        HybridRetriever,
        HybridRetrieverConfig,
    )
    from heretek_swarm.rag.strategies import (
        QueryType,
        RAGStrategyConfig,
        RetrievalResult,
        RetrievalStrategyType,
        StrategySelector,
        create_strategy_selector,
    )

    RAG_STRATEGIES_AVAILABLE = True
except ImportError:
    RAG_STRATEGIES_AVAILABLE = False
    RetrievalStrategyType = None
    RetrievalResult = None
    StrategySelector = None
    QueryType = None
    RAGStrategyConfig = None
    create_strategy_selector = None
    HybridRetriever = None
    HybridRetrieverConfig = None
    FusionMethod = None


@dataclass
class KnowledgeEntry:
    """
    Unified knowledge entry from any source.

    Attributes:
        content: The actual content (text, dict, etc.)
        source: Source type (memory, rag, merged)
        source_id: Original ID from the source system
        metadata: Additional metadata
        score: Relevance score (0-1)
        diversity_score: Diversity score for MMR (0-1)
        combined_score: Final combined score after reranking
    """

    content: Any
    source: str
    source_id: str
    metadata: dict[str, Any] = field(default_factory=dict)
    score: float = 0.0
    diversity_score: float = 0.0
    combined_score: float = 0.0
    created_at: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary representation."""
        return {
            "content": self.content,
            "source": self.source,
            "source_id": self.source_id,
            "metadata": self.metadata,
            "score": self.score,
            "diversity_score": self.diversity_score,
            "combined_score": self.combined_score,
            "created_at": self.created_at,
        }


@dataclass
class KnowledgeQueryResult:
    """
    Result of a unified knowledge query.

    Attributes:
        entries: List of knowledge entries
        total_results: Total number of results before limiting
        query_time_ms: Time taken for the query
        sources_queried: List of sources that were queried
        reranking_applied: Whether reranking was applied
        parameters: Query parameters used
    """

    entries: list[KnowledgeEntry]
    total_results: int = 0
    query_time_ms: float = 0.0
    sources_queried: list[str] = field(default_factory=list)
    reranking_applied: bool = False
    parameters: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary representation."""
        return {
            "entries": [e.to_dict() for e in self.entries],
            "total_results": self.total_results,
            "query_time_ms": self.query_time_ms,
            "sources_queried": self.sources_queried,
            "reranking_applied": self.reranking_applied,
            "parameters": self.parameters,
        }


class UnifiedKnowledgeAccess:
    """
    Unified interface for memory and RAG queries.

    Features:
    - Combined querying of memory and RAG systems
    - Intelligent result merging with MMR reranking
    - Configurable source weighting
    - Diversity-aware result selection
    - Performance metrics tracking

    Usage:
        knowledge = UnifiedKnowledgeAccess(memory_system, rag_retriever)
        result = await knowledge.query(
            query="What was the decision about X?",
            sources=["memory", "rag"],
            limit=10,
            rerank=True,
            diversity_lambda=0.5,
        )
    """

    def __init__(
        self,
        memory_system=None,
        rag_retriever=None,
        hybrid_retriever: Optional["HybridRetriever"] = None,
        strategy_selector: Optional["StrategySelector"] = None,
    ):
        self.memory = memory_system
        self.rag = rag_retriever
        self.hybrid_retriever = hybrid_retriever
        self.strategy_selector = strategy_selector
        self._query_stats: dict[str, dict] = {}

        # Initialize strategy selector if not provided but RAG strategies available
        if RAG_STRATEGIES_AVAILABLE and strategy_selector is None and hybrid_retriever is None:
            # Create default strategy selector
            try:
                config = RAGStrategyConfig()
                self.strategy_selector = create_strategy_selector(config=config)
            except Exception as e:
                logger.warning("strategy_selector_init_failed", error=str(e))

    async def query(
        self,
        query: str,
        sources: list[Literal["memory", "rag", "all"]] | None = None,
        limit: int = 10,
        rerank: bool = True,
        diversity_lambda: float = 0.5,
        source_weights: dict[str, float] | None = None,
        filters: dict[str, Any] | None = None,
    ) -> KnowledgeQueryResult:
        """
        Query knowledge from multiple sources with optional reranking.

        Args:
            query: Search query string
            sources: List of sources to query (memory, rag, all)
            limit: Maximum number of results to return
            rerank: Whether to apply MMR reranking
            diversity_lambda: MMR diversity parameter (0=similarity, 1=diversity)
            source_weights: Weight multipliers for each source
            filters: Additional filters (agent_id, workflow_id, date range, etc.)

        Returns:
            KnowledgeQueryResult with merged and optionally reranked entries
        """
        import time

        start_time = time.time()

        sources = sources or ["all"]
        if "all" in sources:
            sources = ["memory", "rag"]

        source_weights = source_weights or {"memory": 1.0, "rag": 1.0}
        filters = filters or {}

        # Query each source
        all_entries: list[KnowledgeEntry] = []
        sources_queried = []

        if "memory" in sources and self.memory:
            try:
                memory_entries = await self._query_memory(query, filters)
                for entry in memory_entries:
                    entry.score *= source_weights.get("memory", 1.0)
                all_entries.extend(memory_entries)
                sources_queried.append("memory")
            except Exception as e:
                logger.error("memory_query_error", error=str(e))

        if "rag" in sources and self.rag:
            try:
                rag_entries = await self._query_rag(query, filters)
                for entry in rag_entries:
                    entry.score *= source_weights.get("rag", 1.0)
                all_entries.extend(rag_entries)
                sources_queried.append("rag")
            except Exception as e:
                logger.error("rag_query_error", error=str(e))

        total_results = len(all_entries)

        # Apply reranking if requested
        if rerank and len(all_entries) > 1:
            all_entries = self._mmr_rerank(all_entries, diversity_lambda, limit)
        else:
            # Sort by score if no reranking
            all_entries.sort(key=lambda x: x.combined_score or x.score, reverse=True)
            all_entries = all_entries[:limit]

        # Ensure all parameters are always included in result
        _result_params = {
            "query": query,
            "sources": sources,
            "limit": limit,
            "diversity_lambda": diversity_lambda,
            "filters": filters,
        }
        if source_weights:
            _result_params["source_weights"] = source_weights

        query_time_ms = (time.time() - start_time) * 1000

        result = KnowledgeQueryResult(
            entries=all_entries,
            total_results=total_results,
            query_time_ms=query_time_ms,
            sources_queried=sources_queried,
            reranking_applied=rerank,
            parameters=_result_params,
        )

        # Track stats
        self._track_query_stats(query, result)

        logger.debug(
            "knowledge_query_completed",
            query=query[:50] if len(query) > 50 else query,
            total_results=total_results,
            returned_results=len(all_entries),
            query_time_ms=query_time_ms,
        )

        return result

    async def query_with_strategy(
        self,
        query: str,
        strategy: str | None = None,
        top_k: int = 10,
        filters: dict[str, Any] | None = None,
        use_multihop: bool = True,
        apply_reranking: bool = True,
    ) -> KnowledgeQueryResult:
        """
        Query using advanced RAG strategies.

        Args:
            query: Search query string
            strategy: Optional strategy override (dense, sparse, hybrid, multi_hop, re_ranking)
            top_k: Maximum number of results to return
            filters: Additional filters
            use_multihop: Enable multi-hop retrieval for complex queries
            apply_reranking: Apply cross-encoder re-ranking

        Returns:
            KnowledgeQueryResult with retrieved entries
        """
        import time

        start_time = time.time()

        if not RAG_STRATEGIES_AVAILABLE:
            logger.warning("rag_strategies_not_available")
            return await self.query(query, sources=["rag"], limit=top_k)

        try:
            # Use hybrid retriever if available
            if self.hybrid_retriever:
                results = await self.hybrid_retriever.retrieve(
                    query=query,
                    top_k=top_k,
                    filters=filters,
                    use_multihop=use_multihop,
                    apply_reranking=apply_reranking,
                )
            elif self.strategy_selector:
                # Use strategy selector
                results = await self.strategy_selector.retrieve(
                    query=query,
                    top_k=top_k,
                    filters=filters,
                )
            else:
                logger.warning("no_strategy_available")
                return await self.query(query, sources=["rag"], limit=top_k)

            # Convert RetrievalResult to KnowledgeEntry
            entries = []
            for result in results:
                entries.append(
                    KnowledgeEntry(
                        content=result.content,
                        source=f"rag_{result.strategy.value}",
                        source_id=result.source,
                        metadata={**result.metadata, "strategy": result.strategy.value},
                        score=result.score,
                        created_at=None,
                    )
                )

            query_time_ms = (time.time() - start_time) * 1000

            # Build complete parameters including diversity
            params = {
                "query": query,
                "strategy": strategy,
                "top_k": top_k,
                "filters": filters or {},
                "use_multihop": use_multihop,
                "apply_reranking": apply_reranking,
            }

            result = KnowledgeQueryResult(
                entries=entries,
                total_results=len(entries),
                query_time_ms=query_time_ms,
                sources_queried=["rag"],
                reranking_applied=apply_reranking,
                parameters=params,
            )

            logger.debug(
                "knowledge_query_with_strategy_completed",
                query=query[:50] if len(query) > 50 else query,
                strategy=strategy or "auto",
                results_count=len(entries),
                query_time_ms=query_time_ms,
            )

            return result

        except Exception as e:
            logger.error("query_with_strategy_error", error=str(e))
            return await self.query(query, sources=["rag"], limit=top_k)

    async def _query_memory(self, query: str, filters: dict[str, Any]) -> list[KnowledgeEntry]:
        """Query the memory system."""
        if not self.memory:
            return []

        # Build query parameters
        limit = filters.get("memory_limit", 50)

        # Query memory
        results = await self.memory.query(
            query_text=query,
            limit=limit,
        )

        entries = []
        memory_entries = results.entries if hasattr(results, "entries") else results

        for entry in memory_entries:
            entries.append(
                KnowledgeEntry(
                    content=entry.content if hasattr(entry, "content") else entry,
                    source="memory",
                    source_id=getattr(entry, "id", getattr(entry, "memory_id", "unknown")),
                    metadata=getattr(entry, "metadata", {}),
                    score=getattr(entry, "similarity", getattr(entry, "score", 0.5)),
                    created_at=getattr(entry, "created_at", None),
                )
            )

        return entries

    async def _query_rag(self, query: str, filters: dict[str, Any]) -> list[KnowledgeEntry]:
        """Query the CogneeRAGRetriever."""
        if not self.rag:
            return []

        # Build query parameters
        top_k = filters.get("rag_top_k", 50)

        # Query CogneeRAGRetriever.retrieve() returns list[SearchResult]
        results = await self.rag.retrieve(
            query=query,
            top_k=top_k,
        )

        entries = []
        for result in results:
            entries.append(
                KnowledgeEntry(
                    content=result.content,
                    source="rag",
                    source_id=result.id,
                    metadata=result.metadata,
                    score=result.score,
                    created_at=None,
                )
            )

        return entries

    def _mmr_rerank(
        self,
        entries: list[KnowledgeEntry],
        diversity_lambda: float,
        limit: int,
    ) -> list[KnowledgeEntry]:
        """
        Apply MMR (Maximal Marginal Relevance) reranking.

        MMR balances relevance and diversity by selecting items that:
        1. Are highly relevant to the query (high score)
        2. Are diverse from already-selected items (low similarity to selected)

        Formula:
            MMR = argmax [ λ * relevance(item) - (1-λ) * max_similarity(item, selected) ]

        Args:
            entries: List of knowledge entries to rerank
            diversity_lambda: Balance parameter (0=relevance, 1=diversity)
            limit: Number of results to return

        Returns:
            Reranked list of entries
        """
        if not entries or diversity_lambda < 0 or diversity_lambda > 1:
            return entries

        # Compute embeddings for similarity calculation if available
        # For now, use content-based similarity approximation

        selected: list[KnowledgeEntry] = []
        remaining = entries.copy()

        # Sort by initial score
        remaining.sort(key=lambda x: x.score, reverse=True)

        # Select first item (highest relevance)
        if remaining:
            first = remaining.pop(0)
            first.combined_score = first.score
            first.diversity_score = 1.0
            selected.append(first)

        # Iteratively select remaining items
        while len(selected) < limit and remaining:
            best_score = float("-inf")
            best_idx = 0

            for i, entry in enumerate(remaining):
                # Calculate max similarity to already selected items
                max_similarity = 0.0
                for sel in selected:
                    sim = self._compute_similarity(entry, sel)
                    max_similarity = max(max_similarity, sim)

                # MMR score
                mmr_score = diversity_lambda * entry.score - (1 - diversity_lambda) * max_similarity

                if mmr_score > best_score:
                    best_score = mmr_score
                    best_idx = i

            # Select best item
            best_entry = remaining.pop(best_idx)
            best_entry.combined_score = best_score
            best_entry.diversity_score = (
                1.0 - max(self._compute_similarity(best_entry, s) for s in selected)
                if selected
                else 1.0
            )
            selected.append(best_entry)

        return selected

    def _compute_similarity(self, entry1: KnowledgeEntry, entry2: KnowledgeEntry) -> float:
        """
        Compute similarity between two knowledge entries.

        Uses content-based similarity approximation.
        For production, use embedding-based cosine similarity.
        """
        # Get content as strings
        content1 = self._get_content_string(entry1.content)
        content2 = self._get_content_string(entry2.content)

        if not content1 or not content2:
            return 0.0

        # Simple Jaccard similarity on words
        words1 = set(content1.lower().split())
        words2 = set(content2.lower().split())

        if not words1 or not words2:
            return 0.0

        intersection = len(words1 & words2)
        union = len(words1 | words2)

        return intersection / union if union > 0 else 0.0

    def _get_content_string(self, content: Any) -> str:
        """Extract string content from various content types."""
        if isinstance(content, str):
            return content
        if isinstance(content, dict):
            # Try common text fields
            for key in ["text", "content", "body", "message"]:
                if key in content and isinstance(content[key], str):
                    return content[key]
            return str(content)
        return str(content)

    def _track_query_stats(self, _query: str, result: KnowledgeQueryResult) -> None:
        """Track query statistics for monitoring."""
        # Simple stats tracking
        key = f"{result.sources_queried}"

        if key not in self._query_stats:
            self._query_stats[key] = {
                "count": 0,
                "total_time_ms": 0.0,
                "total_results": 0,
            }

        stats = self._query_stats[key]
        stats["count"] += 1
        stats["total_time_ms"] += result.query_time_ms
        stats["total_results"] += result.total_results

    def get_stats(self) -> dict[str, dict[str, Any]]:
        """Get query statistics."""
        stats = {}
        for key, data in self._query_stats.items():
            count = data["count"]
            stats[key] = {
                "count": count,
                "avg_time_ms": data["total_time_ms"] / count if count > 0 else 0,
                "avg_results": data["total_results"] / count if count > 0 else 0,
            }
        return stats

    def get_rag_strategy_stats(self) -> dict[str, Any]:
        """Get RAG strategy statistics."""
        if not RAG_STRATEGIES_AVAILABLE:
            return {"available": False}

        stats = {
            "available": True,
            "hybrid_retriever": None,
            "strategy_selector": None,
        }

        if self.hybrid_retriever:
            stats["hybrid_retriever"] = self.hybrid_retriever.get_stats()

        if self.strategy_selector:
            stats["strategy_selector"] = self.strategy_selector.get_stats()

        return stats

    def export_prometheus_metrics(self) -> str:
        """Export RAG metrics in Prometheus format."""
        if not RAG_STRATEGIES_AVAILABLE:
            return "# RAG strategies not available\n"

        lines = ["# Heretek Swarm RAG Metrics", ""]

        if self.hybrid_retriever:
            lines.append(self.hybrid_retriever.export_prometheus_metrics())

        # Add unified knowledge access metrics
        for source_key, source_stats in self._query_stats.items():
            lines.extend(
                [
                    f"# HELP heretek_knowledge_queries_total Total knowledge queries for {source_key}",
                    "# TYPE heretek_knowledge_queries_total counter",
                    f'heretek_knowledge_queries_total{{sources="{source_key}"}} {source_stats["count"]}',
                    "",
                    f"# HELP heretek_knowledge_query_time_ms_total Total query time for {source_key}",
                    "# TYPE heretek_knowledge_query_time_ms_total counter",
                    f'heretek_knowledge_query_time_ms_total{{sources="{source_key}"}} {source_stats["total_time_ms"]}',
                    "",
                ]
            )

        return "\n".join(lines)


class KnowledgeQueryBuilder:
    """
    Fluent builder for constructing knowledge queries.

    Usage:
        result = (KnowledgeQueryBuilder(knowledge_access)
            .query("What was decided about X?")
            .from_sources("memory", "rag")
            .with_limit(10)
            .with_diversity(0.5)
            .filtered_by(agent_id="alpha")
            .execute())
    """

    def __init__(self, knowledge_access: UnifiedKnowledgeAccess):
        self._knowledge = knowledge_access
        self._query: str | None = None
        self._sources: list[str] = ["all"]
        self._limit: int = 10
        self._rerank: bool = True
        self._diversity_lambda: float = 0.5
        self._source_weights: dict[str, float] = {}
        self._filters: dict[str, Any] = {}

    def query(self, query_text: str) -> "KnowledgeQueryBuilder":
        """Set the query text."""
        self._query = query_text
        return self

    def from_sources(self, *sources: str) -> "KnowledgeQueryBuilder":
        """Set sources to query (memory, rag)."""
        self._sources = list(sources)
        return self

    def with_limit(self, limit: int) -> "KnowledgeQueryBuilder":
        """Set result limit."""
        self._limit = limit
        return self

    def with_diversity(self, diversity_lambda: float) -> "KnowledgeQueryBuilder":
        """Set MMR diversity parameter (0-1)."""
        self._diversity_lambda = max(0, min(1, diversity_lambda))
        return self

    def with_reranking(self, enabled: bool = True) -> "KnowledgeQueryBuilder":
        """Enable or disable reranking."""
        self._rerank = enabled
        return self

    def with_source_weights(
        self,
        memory: float | None = None,
        rag: float | None = None,
    ) -> "KnowledgeQueryBuilder":
        """Set source weight multipliers."""
        if memory is not None:
            self._source_weights["memory"] = memory
        if rag is not None:
            self._source_weights["rag"] = rag
        return self

    def filtered_by(self, **filters) -> "KnowledgeQueryBuilder":
        """Add query filters."""
        self._filters.update(filters)
        return self

    def with_strategy(self, strategy: str) -> "KnowledgeQueryBuilder":
        """Set RAG strategy (requires advanced strategies enabled)."""
        self._filters["rag_strategy"] = strategy
        return self

    def with_multihop(self, enabled: bool = True) -> "KnowledgeQueryBuilder":
        """Enable multi-hop retrieval."""
        self._filters["rag_multihop"] = enabled
        return self

    def with_reranking_options(
        self,
        enabled: bool = True,
        top_k: int = 50,
    ) -> "KnowledgeQueryBuilder":
        """Configure re-ranking options."""
        self._filters["rag_rerank"] = enabled
        self._filters["rag_rerank_top_k"] = top_k
        return self

    async def execute(self) -> KnowledgeQueryResult:
        """Execute the query."""
        if not self._query:
            raise ValueError("Query text is required")

        # Always use standard query to ensure all parameters are included
        result = await self._knowledge.query(
            query=self._query,
            sources=self._sources,
            limit=self._limit,
            rerank=self._rerank,
            diversity_lambda=self._diversity_lambda,
            source_weights=self._source_weights,
            filters=self._filters,
        )

        # Override parameters to include builder-specific values
        result.parameters["diversity_lambda"] = self._diversity_lambda
        if self._source_weights:
            result.parameters["source_weights"] = self._source_weights

        return result


def create_unified_knowledge_access(
    memory_system=None,
    rag_retriever=None,
    embedding_provider=None,
    vector_store=None,
    sparse_index=None,
    cross_encoder=None,
    config: Any | None = None,
) -> UnifiedKnowledgeAccess:
    """
    Create UnifiedKnowledgeAccess with advanced RAG strategies.

    Args:
        memory_system: Memory system instance
        rag_retriever: CogneeRAGRetriever instance
        embedding_provider: Embedding provider for dense retrieval
        vector_store: Vector store for dense retrieval
        sparse_index: Sparse index for BM25 retrieval
        cross_encoder: Cross-encoder for re-ranking
        config: Optional HybridRetrieverConfig

    Returns:
        Configured UnifiedKnowledgeAccess instance
    """
    if not RAG_STRATEGIES_AVAILABLE:
        logger.warning("rag_strategies_not_available_using_legacy")
        return UnifiedKnowledgeAccess(memory_system=memory_system, rag_retriever=rag_retriever)

    try:
        # Create hybrid retriever config
        retriever_config = config or HybridRetrieverConfig()

        # Create hybrid retriever
        hybrid_retriever = HybridRetriever(
            config=retriever_config,
            embedding_provider=embedding_provider,
            vector_store=vector_store,
            sparse_index=sparse_index,
            cross_encoder=cross_encoder,
        )

        # Create unified access with hybrid retriever
        knowledge_access = UnifiedKnowledgeAccess(
            memory_system=memory_system,
            rag_retriever=rag_retriever,
            hybrid_retriever=hybrid_retriever,
        )

        logger.info("unified_knowledge_access_created_with_strategies")
        return knowledge_access

    except Exception as e:
        logger.error("unified_knowledge_access_creation_failed", error=str(e))
        # Fall back to legacy
        return UnifiedKnowledgeAccess(memory_system=memory_system, rag_retriever=rag_retriever)
