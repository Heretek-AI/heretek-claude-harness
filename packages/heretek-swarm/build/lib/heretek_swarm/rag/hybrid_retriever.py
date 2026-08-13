"""
Hybrid Retriever for Heretek Swarm RAG System.

This module provides a unified hybrid retrieval interface that combines
multiple retrieval strategies for optimal search results.

Features:
- Unified interface for hybrid retrieval
- Dynamic weight adjustment based on query characteristics
- Result fusion with configurable methods
- Performance monitoring and optimization
- Rate limiting and caching support

Usage:
    from heretek_swarm.rag.hybrid_retriever import HybridRetriever, HybridRetrieverConfig

    config = HybridRetrieverConfig()
    retriever = HybridRetriever(config)
    await retriever.initialize()

    results = await retriever.retrieve(
        query="What is the capital of France?",
        top_k=5,
    )
"""

import asyncio
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

import structlog

from .strategies import (
    QueryClassifier,
    QueryType,
    RAGStrategyConfig,
    ReRankingStrategy,
    RetrievalResult,
    RetrievalStrategyType,
    StrategySelector,
    create_strategy_selector,
)

logger = structlog.get_logger(__name__)


class FusionMethod(StrEnum):
    """Methods for fusing retrieval results."""

    RECIPROCAL_RANK = "reciprocal_rank"  # RRF
    WEIGHTED_SUM = "weighted_sum"
    NORMALIZED_SUM = "normalized_sum"
    MAX_SCORE = "max_score"
    MIN_SCORE = "min_score"


class RetrieverState(StrEnum):
    """Retriever lifecycle states."""

    UNINITIALIZED = "uninitialized"
    INITIALIZING = "initializing"
    READY = "ready"
    DEGRADED = "degraded"
    ERROR = "error"


@dataclass
class HybridRetrieverConfig:
    """
    Configuration for the Hybrid Retriever.

    Attributes:
        dense_weight: Weight for dense retrieval scores (0-1)
        sparse_weight: Weight for sparse retrieval scores (0-1)
        fusion_method: Method for combining results
        rrf_k: Constant for reciprocal rank fusion
        enable_reranking: Whether to apply cross-encoder re-ranking
        rerank_top_k: Number of candidates for re-ranking
        enable_multihop: Whether to enable multi-hop retrieval
        max_hops: Maximum retrieval hops
        cache_enabled: Enable query caching
        cache_ttl_seconds: Cache time-to-live
        rate_limit_queries_per_minute: Rate limit for queries
        normalize_scores: Whether to normalize scores before fusion
        min_score_threshold: Minimum score threshold for results
        query_classification_enabled: Enable automatic query classification
    """

    dense_weight: float = 0.5
    sparse_weight: float = 0.5
    fusion_method: FusionMethod = FusionMethod.RECIPROCAL_RANK
    rrf_k: int = 60
    enable_reranking: bool = True
    rerank_top_k: int = 50
    enable_multihop: bool = True
    max_hops: int = 3
    cache_enabled: bool = True
    cache_ttl_seconds: int = 300
    rate_limit_queries_per_minute: int = 60
    normalize_scores: bool = True
    min_score_threshold: float = 0.0
    query_classification_enabled: bool = True


@dataclass
class RetrievalMetrics:
    """Metrics for retrieval operations."""

    total_queries: int = 0
    successful_queries: int = 0
    failed_queries: int = 0
    cache_hits: int = 0
    cache_misses: int = 0
    avg_latency_ms: float = 0.0
    p95_latency_ms: float = 0.0
    p99_latency_ms: float = 0.0
    avg_results_count: float = 0.0
    rate_limit_hits: int = 0
    last_query_time: datetime | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "total_queries": self.total_queries,
            "successful_queries": self.successful_queries,
            "failed_queries": self.failed_queries,
            "cache_hit_rate": self.cache_hits / max(1, self.cache_hits + self.cache_misses),
            "avg_latency_ms": self.avg_latency_ms,
            "p95_latency_ms": self.p95_latency_ms,
            "p99_latency_ms": self.p99_latency_ms,
            "avg_results_count": self.avg_results_count,
            "rate_limit_hits": self.rate_limit_hits,
            "last_query_time": self.last_query_time.isoformat() if self.last_query_time else None,
        }


@dataclass
class QueryHistoryEntry:
    """Entry in query history for rate limiting and analytics."""

    query: str
    timestamp: datetime
    latency_ms: float
    results_count: int
    strategy_used: str
    cache_hit: bool


class RateLimiter:
    """
    Token bucket rate limiter for query throttling.

    Implements a sliding window rate limiter to prevent
    excessive query rates.
    """

    def __init__(self, queries_per_minute: int):
        self.queries_per_minute = queries_per_minute
        self._queries: list[datetime] = []
        self._lock = asyncio.Lock()

    async def acquire(self) -> bool:
        """
        Try to acquire a rate limit token.

        Returns:
            True if token acquired, False if rate limited
        """
        async with self._lock:
            now = datetime.now(UTC)
            window_start = now.timestamp() - 60  # 1 minute window

            # Remove old queries outside the window
            self._queries = [q for q in self._queries if q.timestamp() > window_start]

            # Check if under limit
            if len(self._queries) < self.queries_per_minute:
                self._queries.append(now)
                return True

            return False

    async def wait_for_token(self, timeout: float = 60.0) -> bool:  # noqa: ASYNC109
        """
        Wait for a rate limit token with timeout.

        Args:
            timeout: Maximum time to wait in seconds

        Returns:
            True if token acquired, False if timeout
        """
        start_time = time.time()

        while time.time() - start_time < timeout:
            if await self.acquire():
                return True
            await asyncio.sleep(0.1)

        return False

    def get_remaining(self) -> int:
        """Get remaining queries in current window."""
        now = datetime.now(UTC)
        window_start = now.timestamp() - 60
        current_count = sum(1 for q in self._queries if q.timestamp() > window_start)
        return max(0, self.queries_per_minute - current_count)


class HybridRetriever:
    """
    Hybrid Retriever combining multiple retrieval strategies.

    This class provides a unified interface for hybrid retrieval,
    combining dense (vector) and sparse (BM25) retrieval with
    configurable fusion methods and optional re-ranking.

    Features:
    - Multi-strategy retrieval with configurable weights
    - Reciprocal rank fusion and weighted combination
    - Cross-encoder re-ranking
    - Query caching and rate limiting
    - Performance metrics and monitoring
    - Zero-trust authentication support
    """

    def __init__(
        self,
        config: HybridRetrieverConfig | None = None,
        embedding_provider: Any | None = None,
        vector_store: Any | None = None,
        sparse_index: Any | None = None,
        cross_encoder: Any | None = None,
    ):
        self.config = config or HybridRetrieverConfig()
        self.embedding_provider = embedding_provider
        self.vector_store = vector_store
        self.sparse_index = sparse_index
        self.cross_encoder = cross_encoder

        self._state = RetrieverState.UNINITIALIZED
        self._strategy_selector: StrategySelector | None = None
        self._reranker: ReRankingStrategy | None = None
        self._classifier = QueryClassifier()
        self._rate_limiter = RateLimiter(self.config.rate_limit_queries_per_minute)
        self._metrics = RetrievalMetrics()
        self._query_history: list[QueryHistoryEntry] = []
        self._max_history = 1000

        # Cache
        self._query_cache: dict[str, tuple[list[RetrievalResult], datetime]] = {}

    @property
    def state(self) -> RetrieverState:
        """Get current retriever state."""
        return self._state

    async def initialize(self) -> None:
        """
        Initialize the hybrid retriever.

        Sets up strategy selector, reranker, and validates dependencies.
        """
        self._state = RetrieverState.INITIALIZING

        try:
            # Create strategy config
            strategy_config = RAGStrategyConfig(
                dense_enabled=self.embedding_provider is not None,
                sparse_enabled=self.sparse_index is not None,
                hybrid_enabled=True,
                dense_weight=self.config.dense_weight,
                sparse_weight=self.config.sparse_weight,
                fusion_method=self.config.fusion_method.value,
                rrf_k=self.config.rrf_k,
                multi_hop_enabled=self.config.enable_multihop,
                max_hops=self.config.max_hops,
                re_ranking_enabled=self.config.enable_reranking,
                re_rank_limit=self.config.rerank_top_k,
                cache_enabled=self.config.cache_enabled,
                cache_ttl_seconds=self.config.cache_ttl_seconds,
            )

            # Create strategy selector
            self._strategy_selector = create_strategy_selector(
                config=strategy_config,
                embedding_provider=self.embedding_provider,
                vector_store=self.vector_store,
                sparse_index=self.sparse_index,
                cross_encoder=self.cross_encoder,
            )

            # Create dedicated reranker
            if self.config.enable_reranking and self.cross_encoder:
                self._reranker = ReRankingStrategy(
                    cross_encoder=self.cross_encoder,
                    re_rank_limit=self.config.rerank_top_k,
                )

            self._state = RetrieverState.READY
            logger.info(
                "hybrid_retriever_initialized",
                dense_enabled=self.embedding_provider is not None,
                sparse_enabled=self.sparse_index is not None,
                reranking_enabled=self.config.enable_reranking,
            )

        except Exception as e:
            self._state = RetrieverState.ERROR
            logger.error("hybrid_retriever_initialization_failed", error=str(e))
            raise

    def _hash_query(self, query: str) -> str:
        """Create hash of query for caching."""
        import hashlib

        return hashlib.md5(query.lower().strip().encode(), usedforsecurity=False).hexdigest()

    def _get_from_cache(self, query_hash: str) -> list[RetrievalResult] | None:
        """Get cached results if available and not expired."""
        if not self.config.cache_enabled:
            return None

        entry = self._query_cache.get(query_hash)
        if entry:
            results, created_at = entry
            age = (datetime.now(UTC) - created_at).total_seconds()
            if age < self.config.cache_ttl_seconds:
                self._metrics.cache_hits += 1
                return results

        self._metrics.cache_misses += 1
        return None

    def _store_in_cache(self, query_hash: str, results: list[RetrievalResult]) -> None:
        """Store results in cache."""
        if not self.config.cache_enabled:
            return

        self._query_cache[query_hash] = (results, datetime.now(UTC))

        # Clean old cache
        if len(self._query_cache) > 1000:
            now = datetime.now(UTC)
            expired = [
                k
                for k, (_, created_at) in self._query_cache.items()
                if (now - created_at).total_seconds() > self.config.cache_ttl_seconds
            ]
            for k in expired:
                del self._query_cache[k]

    def _normalize_scores(self, results: list[RetrievalResult]) -> list[RetrievalResult]:
        """Normalize scores to 0-1 range using min-max normalization."""
        if not results:
            return results

        scores = [r.score for r in results]
        min_score = min(scores)
        max_score = max(scores)
        score_range = max_score - min_score if max_score > min_score else 1.0

        for result in results:
            result.score = (result.score - min_score) / score_range

        return results

    def _fuse_results(
        self,
        dense_results: list[RetrievalResult],
        sparse_results: list[RetrievalResult],
    ) -> list[RetrievalResult]:
        """
        Fuse results from dense and sparse retrieval.

        Args:
            dense_results: Results from dense retrieval
            sparse_results: Results from sparse retrieval

        Returns:
            Fused and ranked results
        """
        if not dense_results and not sparse_results:
            return []

        if not dense_results:
            return sparse_results

        if not sparse_results:
            return dense_results

        if self.config.fusion_method == FusionMethod.RECIPROCAL_RANK:
            return self._reciprocal_rank_fusion(dense_results, sparse_results)
        if self.config.fusion_method == FusionMethod.WEIGHTED_SUM:
            return self._weighted_sum_fusion(dense_results, sparse_results)
        if self.config.fusion_method == FusionMethod.NORMALIZED_SUM:
            return self._normalized_sum_fusion(dense_results, sparse_results)
        if self.config.fusion_method == FusionMethod.MAX_SCORE:
            return self._max_score_fusion(dense_results, sparse_results)
        return self._reciprocal_rank_fusion(dense_results, sparse_results)

    def _reciprocal_rank_fusion(
        self,
        dense_results: list[RetrievalResult],
        sparse_results: list[RetrievalResult],
    ) -> list[RetrievalResult]:
        """Apply Reciprocal Rank Fusion (RRF)."""
        # Build rank maps
        dense_ranks: dict[str, int] = {r.source: i + 1 for i, r in enumerate(dense_results)}
        sparse_ranks: dict[str, int] = {r.source: i + 1 for i, r in enumerate(sparse_results)}

        # Calculate RRF scores
        all_sources = set(dense_ranks.keys()) | set(sparse_ranks.keys())
        rrf_scores: dict[str, float] = {}
        source_to_result: dict[str, RetrievalResult] = {}

        for source in all_sources:
            dense_rank = dense_ranks.get(source, len(dense_results) + 1)
            sparse_rank = sparse_ranks.get(source, len(sparse_results) + 1)

            rrf_score = 0.0
            if dense_rank <= len(dense_results):
                rrf_score += self.config.dense_weight / (self.config.rrf_k + dense_rank)
            if sparse_rank <= len(sparse_results):
                rrf_score += self.config.sparse_weight / (self.config.rrf_k + sparse_rank)

            rrf_scores[source] = rrf_score

            # Keep reference to result
            if source in dense_ranks:
                for r in dense_results:
                    if r.source == source:
                        source_to_result[source] = r
                        r.strategy = RetrievalStrategyType.HYBRID
                        break
            elif source in sparse_ranks:
                for r in sparse_results:
                    if r.source == source:
                        source_to_result[source] = r
                        r.strategy = RetrievalStrategyType.HYBRID
                        break

        # Sort and build fused results
        sorted_sources = sorted(rrf_scores.keys(), key=lambda s: rrf_scores[s], reverse=True)
        fused_results = []

        for source in sorted_sources:
            result = source_to_result.get(source)
            if result:
                result.score = rrf_scores[source]
                fused_results.append(result)

        return fused_results

    def _weighted_sum_fusion(
        self,
        dense_results: list[RetrievalResult],
        sparse_results: list[RetrievalResult],
    ) -> list[RetrievalResult]:
        """Apply weighted sum fusion with score normalization."""
        # Normalize scores
        dense_normalized = self._normalize_scores(dense_results.copy())
        sparse_normalized = self._normalize_scores(sparse_results.copy())

        # Build score maps
        dense_scores: dict[str, float] = {r.source: r.score for r in dense_normalized}
        sparse_scores: dict[str, float] = {r.source: r.score for r in sparse_normalized}

        # Combine scores
        all_sources = set(dense_scores.keys()) | set(sparse_scores.keys())
        combined_scores: dict[str, float] = {}
        source_to_result: dict[str, RetrievalResult] = {}

        for source in all_sources:
            combined_score = self.config.dense_weight * dense_scores.get(
                source, 0
            ) + self.config.sparse_weight * sparse_scores.get(source, 0)
            combined_scores[source] = combined_score

            # Keep reference to result
            for r in dense_results + sparse_results:
                if r.source == source:
                    source_to_result[source] = r
                    r.strategy = RetrievalStrategyType.HYBRID
                    break

        # Sort and build results
        sorted_sources = sorted(
            combined_scores.keys(), key=lambda s: combined_scores[s], reverse=True
        )
        fused_results = []

        for source in sorted_sources:
            result = source_to_result.get(source)
            if result:
                result.score = combined_scores[source]
                fused_results.append(result)

        return fused_results

    def _normalized_sum_fusion(
        self,
        dense_results: list[RetrievalResult],
        sparse_results: list[RetrievalResult],
    ) -> list[RetrievalResult]:
        """Apply normalized sum fusion (equal weights)."""
        self.config.dense_weight = 0.5
        self.config.sparse_weight = 0.5
        return self._weighted_sum_fusion(dense_results, sparse_results)

    def _max_score_fusion(
        self,
        dense_results: list[RetrievalResult],
        sparse_results: list[RetrievalResult],
    ) -> list[RetrievalResult]:
        """Apply max score fusion (take maximum score from either method)."""
        all_results = {}

        for result in dense_results + sparse_results:
            if result.source not in all_results:
                result.strategy = RetrievalStrategyType.HYBRID
                all_results[result.source] = result
            else:
                # Keep the result with higher score
                if result.score > all_results[result.source].score:
                    result.strategy = RetrievalStrategyType.HYBRID
                    all_results[result.source] = result

        # Sort by score
        return sorted(all_results.values(), key=lambda r: r.score, reverse=True)

    async def _apply_reranking(
        self,
        query: str,
        results: list[RetrievalResult],
        top_k: int,
    ) -> list[RetrievalResult]:
        """Apply cross-encoder re-ranking to results."""
        if not self._reranker or not results:
            return results[:top_k]

        return await self._reranker.retrieve(
            query=query,
            top_k=top_k,
            initial_results=results,
        )

    def _record_query(
        self,
        query: str,
        latency_ms: float,
        results_count: int,
        strategy: str,
        cache_hit: bool,
    ) -> None:
        """Record query in history and update metrics."""
        now = datetime.now(UTC)

        # Update metrics
        self._metrics.total_queries += 1
        self._metrics.last_query_time = now

        if cache_hit:
            self._metrics.cache_hits += 1
        else:
            self._metrics.cache_misses += 1

        # Update latency stats (simple moving average)
        n = self._metrics.total_queries
        self._metrics.avg_latency_ms = (self._metrics.avg_latency_ms * (n - 1) + latency_ms) / n

        # Update results count avg
        self._metrics.avg_results_count = (
            self._metrics.avg_results_count * (n - 1) + results_count
        ) / n

        # Record history entry
        entry = QueryHistoryEntry(
            query=query,
            timestamp=now,
            latency_ms=latency_ms,
            results_count=results_count,
            strategy_used=strategy,
            cache_hit=cache_hit,
        )
        self._query_history.append(entry)

        # Trim history
        if len(self._query_history) > self._max_history:
            self._query_history = self._query_history[-self._max_history :]

    async def retrieve(
        self,
        query: str,
        top_k: int = 5,
        filters: dict[str, Any] | None = None,
        use_multihop: bool | None = None,
        apply_reranking: bool | None = None,
        authenticated: bool = True,
    ) -> list[RetrievalResult]:
        """
        Retrieve relevant documents using hybrid retrieval.

        Args:
            query: Search query
            top_k: Number of results to return
            filters: Optional metadata filters
            use_multihop: Override multi-hop setting
            apply_reranking: Override re-ranking setting
            authenticated: Whether request is authenticated (for rate limiting)

        Returns:
            List of retrieval results

        Raises:
            RateLimitExceeded: If rate limit is exceeded
            RetrieverNotReady: If retriever is not initialized
        """
        if self._state != RetrieverState.READY:
            raise RetrieverNotReady(f"Retriever state: {self._state.value}")

        start_time = time.time()
        cache_hit = False

        # Check rate limit (skip for authenticated requests if configured)
        if not authenticated and not await self._rate_limiter.acquire():
            self._metrics.rate_limit_hits += 1
            raise RateLimitExceeded(
                f"Rate limit exceeded: {self.config.rate_limit_queries_per_minute} queries/minute"
            )

        # Check cache
        query_hash = self._hash_query(query)
        cached_results = self._get_from_cache(query_hash)
        if cached_results:
            cache_hit = True
            latency_ms = (time.time() - start_time) * 1000
            self._record_query(query, latency_ms, len(cached_results), "cache", True)
            return cached_results[:top_k]

        try:
            # Determine strategy
            strategy = RetrievalStrategyType.HYBRID

            if self.config.query_classification_enabled:
                query_type = self._classifier.classify(query)
                if query_type == QueryType.MULTI_STEP and (use_multihop is not False):
                    strategy = RetrievalStrategyType.MULTI_HOP

            # Get strategy from selector
            if not self._strategy_selector:
                raise RetrieverError("Strategy selector not initialized")

            # Execute retrieval
            results = await self._strategy_selector.retrieve(
                query=query,
                top_k=self.config.rerank_top_k if apply_reranking else top_k,
                strategy=strategy,
                filters=filters,
            )

            # Apply re-ranking if enabled
            if (apply_reranking or self.config.enable_reranking) and self._reranker and results:
                results = await self._apply_reranking(query, results, top_k)

            # Apply score threshold
            if self.config.min_score_threshold > 0:
                results = [r for r in results if r.score >= self.config.min_score_threshold]

            # Limit to top_k
            results = results[:top_k]

            # Normalize scores if configured
            if self.config.normalize_scores and results:
                results = self._normalize_scores(results)

            # Cache results
            self._store_in_cache(query_hash, results)

            # Record metrics
            latency_ms = (time.time() - start_time) * 1000
            self._metrics.successful_queries += 1
            self._record_query(query, latency_ms, len(results), strategy.value, cache_hit)

            logger.debug(
                "hybrid_retrieval_completed",
                query=query[:50] if len(query) > 50 else query,
                results_count=len(results),
                latency_ms=latency_ms,
                strategy=strategy.value,
                cache_hit=cache_hit,
            )

            return results

        except Exception as e:
            self._metrics.failed_queries += 1
            latency_ms = (time.time() - start_time) * 1000
            self._record_query(query, latency_ms, 0, "error", cache_hit)

            logger.error(
                "hybrid_retrieval_error",
                query=query[:50] if len(query) > 50 else query,
                error=str(e),
            )
            raise RetrieverError(f"Retrieval failed: {e!s}") from e

    async def retrieve_with_context(
        self, query: str, context: str | None = None, top_k: int = 5, **kwargs
    ) -> tuple[str, list[RetrievalResult]]:
        """
        Retrieve and format results with context.

        Args:
            query: Search query
            context: Optional additional context
            top_k: Number of results
            **kwargs: Additional arguments for retrieve()

        Returns:
            Tuple of (formatted context string, retrieval results)
        """
        results = await self.retrieve(query, top_k, **kwargs)

        # Format context from results
        context_parts = []
        if context:
            context_parts.append(f"Context: {context}")

        for i, result in enumerate(results, 1):
            context_parts.append(f"[{i}] {result.content}")

        formatted_context = "\n\n".join(context_parts)

        return formatted_context, results

    def get_metrics(self) -> RetrievalMetrics:
        """Get retrieval metrics."""
        return self._metrics

    def get_stats(self) -> dict[str, Any]:
        """Get detailed retriever statistics."""
        return {
            "state": self._state.value,
            "metrics": self._metrics.to_dict(),
            "config": {
                "fusion_method": self.config.fusion_method.value,
                "dense_weight": self.config.dense_weight,
                "sparse_weight": self.config.sparse_weight,
                "cache_enabled": self.config.cache_enabled,
                "reranking_enabled": self.config.enable_reranking,
            },
            "rate_limit": {
                "remaining": self._rate_limiter.get_remaining(),
                "limit": self.config.rate_limit_queries_per_minute,
            },
            "cache_size": len(self._query_cache),
        }

    def export_prometheus_metrics(self) -> str:
        """Export metrics in Prometheus format."""
        lines = [
            "# HELP heretek_rag_total_queries Total RAG queries",
            "# TYPE heretek_rag_total_queries counter",
            f"heretek_rag_total_queries {self._metrics.total_queries}",
            "",
            "# HELP heretek_rag_successful_queries Successful RAG queries",
            "# TYPE heretek_rag_successful_queries counter",
            f"heretek_rag_successful_queries {self._metrics.successful_queries}",
            "",
            "# HELP heretek_rag_failed_queries Failed RAG queries",
            "# TYPE heretek_rag_failed_queries counter",
            f"heretek_rag_failed_queries {self._metrics.failed_queries}",
            "",
            "# HELP heretek_rag_cache_hits RAG cache hits",
            "# TYPE heretek_rag_cache_hits counter",
            f"heretek_rag_cache_hits {self._metrics.cache_hits}",
            "",
            "# HELP heretek_rag_cache_misses RAG cache misses",
            "# TYPE heretek_rag_cache_misses counter",
            f"heretek_rag_cache_misses {self._metrics.cache_misses}",
            "",
            "# HELP heretek_rag_avg_latency_ms Average RAG query latency",
            "# TYPE heretek_rag_avg_latency_ms gauge",
            f"heretek_rag_avg_latency_ms {self._metrics.avg_latency_ms}",
            "",
            "# HELP heretek_rag_rate_limit_hits Rate limit hits",
            "# TYPE heretek_rag_rate_limit_hits counter",
            f"heretek_rag_rate_limit_hits {self._metrics.rate_limit_hits}",
            "",
        ]
        return "\n".join(lines)

    async def close(self) -> None:
        """Close the retriever and release resources."""
        self._state = RetrieverState.UNINITIALIZED
        self._query_cache.clear()
        self._query_history.clear()
        logger.info("hybrid_retriever_closed")


class RetrieverError(Exception):
    """Base exception for retriever errors."""


class RetrieverNotReady(RetrieverError):
    """Exception raised when retriever is not ready."""


class RateLimitExceeded(RetrieverError):
    """Exception raised when rate limit is exceeded."""


# Convenience function for creating configured retriever
def create_hybrid_retriever(
    config: HybridRetrieverConfig | None = None,
    embedding_provider: Any | None = None,
    vector_store: Any | None = None,
    sparse_index: Any | None = None,
    cross_encoder: Any | None = None,
) -> HybridRetriever:
    """
    Create and initialize a hybrid retriever.

    Args:
        config: Retriever configuration
        embedding_provider: Embedding provider instance
        vector_store: Vector store instance
        sparse_index: Sparse index instance
        cross_encoder: Cross-encoder model instance

    Returns:
        Initialized HybridRetriever instance
    """
    return HybridRetriever(
        config=config,
        embedding_provider=embedding_provider,
        vector_store=vector_store,
        sparse_index=sparse_index,
        cross_encoder=cross_encoder,
    )
