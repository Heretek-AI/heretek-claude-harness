"""
Advanced RAG Retrieval Strategies for Heretek Swarm.

This module implements multiple retrieval strategies for the RAG system:
- Dense retrieval (vector similarity)
- Sparse retrieval (BM25)
- Hybrid retrieval (combined scoring)
- Multi-hop retrieval (chained queries)
- Re-ranking (cross-encoder scoring)

Source Pattern: AgenticRAG-Survey (advanced retrieval strategies)

Usage:
    from heretek_swarm.rag.strategies import (
        DenseRetrievalStrategy,
        SparseRetrievalStrategy,
        HybridRetrievalStrategy,
        MultiHopRetrievalStrategy,
        ReRankingStrategy,
        StrategySelector,
    )

    # Use strategy selector for automatic selection
    selector = StrategySelector()
    results = await selector.retrieve(query, top_k=5)
"""

import hashlib
import math
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

import structlog

logger = structlog.get_logger(__name__)


class RetrievalStrategyType(StrEnum):
    """Types of retrieval strategies."""

    DENSE = "dense"
    SPARSE = "sparse"
    HYBRID = "hybrid"
    MULTI_HOP = "multi_hop"
    RE_RANKING = "re_ranking"


class QueryType(StrEnum):
    """Types of queries for strategy selection."""

    FACTUAL = "factual"  # Specific fact lookup
    EXPLANATORY = "explanatory"  # How/why questions
    COMPARATIVE = "comparative"  # Comparison questions
    PROCEDURAL = "procedural"  # How-to questions
    EXPLORATORY = "exploratory"  # Broad topic exploration
    MULTI_STEP = "multi_step"  # Requires multiple hops


@dataclass
class RetrievalResult:
    """
    Result from a retrieval strategy.

    Attributes:
        content: Retrieved content
        score: Relevance score (0-1)
        source: Source document/chunk ID
        metadata: Additional metadata
        strategy: Strategy that produced this result
        latency_ms: Time taken for retrieval
    """

    content: str
    score: float
    source: str
    metadata: dict[str, Any] = field(default_factory=dict)
    strategy: RetrievalStrategyType = RetrievalStrategyType.DENSE
    latency_ms: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary representation."""
        return {
            "content": self.content,
            "score": self.score,
            "source": self.source,
            "metadata": self.metadata,
            "strategy": self.strategy.value,
            "latency_ms": self.latency_ms,
        }


@dataclass
class QueryCacheEntry:
    """Cached query result."""

    query_hash: str
    results: list[RetrievalResult]
    created_at: datetime
    access_count: int = 1
    last_accessed: datetime = field(default_factory=lambda: datetime.now(UTC))

    def is_expired(self, ttl_seconds: int) -> bool:
        """Check if cache entry has expired."""
        age = (datetime.now(UTC) - self.created_at).total_seconds()
        return age > ttl_seconds


class BaseRetrievalStrategy(ABC):
    """
    Abstract base class for retrieval strategies.

    All retrieval strategies must implement this interface.
    """

    def __init__(self, name: str):
        self.name = name
        self._stats: dict[str, Any] = {
            "queries_executed": 0,
            "avg_latency_ms": 0.0,
            "total_latency_ms": 0.0,
        }

    @abstractmethod
    async def retrieve(self, query: str, top_k: int = 5, **kwargs) -> list[RetrievalResult]:
        """
        Retrieve relevant documents for a query.

        Args:
            query: Search query
            top_k: Number of results to return
            **kwargs: Strategy-specific parameters

        Returns:
            List of retrieval results
        """

    @property
    @abstractmethod
    def strategy_type(self) -> RetrievalStrategyType:
        """Return the strategy type."""

    def _track_latency(self, start_time: float, results: list[RetrievalResult]) -> None:
        """Track latency statistics."""
        latency_ms = (time.time() - start_time) * 1000
        self._stats["queries_executed"] += 1
        self._stats["total_latency_ms"] += latency_ms
        self._stats["avg_latency_ms"] = (
            self._stats["total_latency_ms"] / self._stats["queries_executed"]
        )

        # Add latency to results
        for result in results:
            result.latency_ms = latency_ms

    def get_stats(self) -> dict[str, Any]:
        """Get strategy statistics."""
        return self._stats.copy()


class DenseRetrievalStrategy(BaseRetrievalStrategy):
    """
    Dense retrieval using vector similarity.

    Uses embedding vectors and cosine similarity for semantic search.
    Best for: Semantic similarity, concept matching, paraphrase detection.

    Features:
    - Vector embedding similarity (cosine, dot product, Euclidean)
    - Support for multiple embedding providers
    - Configurable similarity thresholds
    """

    def __init__(
        self,
        embedding_provider: Any | None = None,
        vector_store: Any | None = None,
        similarity_metric: str = "cosine",
        similarity_threshold: float = 0.0,
    ):
        super().__init__("dense_retrieval")
        self.embedding_provider = embedding_provider
        self.vector_store = vector_store
        self.similarity_metric = similarity_metric
        self.similarity_threshold = similarity_threshold

    @property
    def strategy_type(self) -> RetrievalStrategyType:
        return RetrievalStrategyType.DENSE

    async def retrieve(
        self, query: str, top_k: int = 5, filters: dict[str, Any] | None = None, **kwargs
    ) -> list[RetrievalResult]:
        """
        Retrieve using dense vector similarity.

        Args:
            query: Search query
            top_k: Number of results
            filters: Metadata filters
            **kwargs: Additional parameters

        Returns:
            List of retrieval results
        """
        start_time = time.time()

        if not self.embedding_provider or not self.vector_store:
            logger.warning(
                "dense_retrieval_unavailable",
                reason="embedding_provider or vector_store not configured",
            )
            return []

        try:
            # Generate query embedding
            query_embedding = await self.embedding_provider.embed(query)

            # Search vector store
            results = await self.vector_store.search(
                query_vector=query_embedding,
                top_k=top_k,
                filters=filters,
                similarity_metric=self.similarity_metric,
            )

            # Convert to RetrievalResult
            retrieval_results = []
            for doc in results:
                score = doc.get("score", doc.get("similarity", 0.5))
                if score >= self.similarity_threshold:
                    retrieval_results.append(
                        RetrievalResult(
                            content=doc.get("content", ""),
                            score=score,
                            source=doc.get("id", doc.get("source", "unknown")),
                            metadata=doc.get("metadata", {}),
                            strategy=self.strategy_type,
                        )
                    )

            self._track_latency(start_time, retrieval_results)

            logger.debug(
                "dense_retrieval_completed",
                query=query[:50] if len(query) > 50 else query,
                results_count=len(retrieval_results),
                latency_ms=retrieval_results[0].latency_ms if retrieval_results else 0,
            )

            return retrieval_results[:top_k]

        except Exception as e:
            logger.error("dense_retrieval_error", error=str(e))
            self._track_latency(start_time, [])
            return []


class SparseRetrievalStrategy(BaseRetrievalStrategy):
    """
    Sparse retrieval using BM25 (Best Matching 25).

    Traditional keyword-based retrieval using term frequency and inverse document frequency.
    Best for: Exact keyword matching, technical terms, named entities.

    Features:
    - BM25 scoring with configurable k1 and b parameters
    - TF-IDF fallback option
    - Token normalization and stemming
    """

    def __init__(
        self,
        index: Any | None = None,
        k1: float = 1.5,
        b: float = 0.75,
        min_term_frequency: int = 1,
    ):
        super().__init__("sparse_retrieval")
        self.index = index
        self.k1 = k1  # BM25 term frequency saturation
        self.b = b  # BM25 document length normalization
        self.min_term_frequency = min_term_frequency
        self._document_lengths: dict[str, int] = {}
        self._avg_doc_length: float = 0.0
        self._num_documents: int = 0
        self._term_document_freq: dict[str, int] = {}
        self._idf_cache: dict[str, float] = {}

    @property
    def strategy_type(self) -> RetrievalStrategyType:
        return RetrievalStrategyType.SPARSE

    def _tokenize(self, text: str) -> list[str]:
        """Tokenize text into terms."""
        import re

        # Simple tokenization - can be enhanced with stemming, lemmatization
        return re.findall(r"\b[a-zA-Z][a-zA-Z0-9-]*[a-zA-Z0-9]\b|\b[a-zA-Z]\b", text.lower())

    def _register_document(self, doc_id: str, content: str) -> None:
        """Update corpus statistics for BM25 IDF from a document."""
        if doc_id in self._document_lengths:
            return
        tokens = self._tokenize(content)
        self._document_lengths[doc_id] = len(tokens)
        self._num_documents = len(self._document_lengths)
        if self._num_documents:
            self._avg_doc_length = sum(self._document_lengths.values()) / self._num_documents
        unique_terms = set(tokens)
        for term in unique_terms:
            self._term_document_freq[term] = self._term_document_freq.get(term, 0) + 1
        self._idf_cache.clear()

    def _calculate_bm25_score(
        self,
        term: str,
        doc_id: str,
        term_frequency: int,
        doc_length: int,
    ) -> float:
        """
        Calculate BM25 score for a term in a document.

        BM25 formula:
        score = IDF(q_i) * (f(q_i, d) * (k1 + 1)) / (f(q_i, d) + k1 * (1 - b + b * |d|/avgdl))

        Where:
        - f(q_i, d): term frequency of query term q_i in document d
        - |d|: document length
        - avgdl: average document length
        - k1, b: free parameters
        """
        if self._num_documents == 0:
            return 0.0

        # Calculate IDF using Robertson–Spark Jones BM25 IDF
        if term not in self._idf_cache:
            df = self._term_document_freq.get(term, 0)
            n = max(self._num_documents, 1)
            self._idf_cache[term] = math.log((n - df + 0.5) / (df + 0.5) + 1.0)

        idf = self._idf_cache[term]

        # BM25 term score
        numerator = term_frequency * (self.k1 + 1)
        denominator = term_frequency + self.k1 * (
            1 - self.b + self.b * doc_length / self._avg_doc_length
        )

        return idf * (numerator / denominator) if denominator > 0 else 0.0

    async def retrieve(
        self, query: str, top_k: int = 5, filters: dict[str, Any] | None = None, **kwargs
    ) -> list[RetrievalResult]:
        """
        Retrieve using BM25 sparse retrieval.

        Args:
            query: Search query
            top_k: Number of results
            filters: Metadata filters
            **kwargs: Additional parameters

        Returns:
            List of retrieval results
        """
        start_time = time.time()

        if not self.index:
            logger.warning("sparse_retrieval_unavailable", reason="index not configured")
            return []

        try:
            # Tokenize query
            query_terms = self._tokenize(query)

            if not query_terms:
                return []

            # Search index
            results = await self.index.search(
                query_terms=query_terms,
                top_k=top_k,
                filters=filters,
                k1=self.k1,
                b=self.b,
            )

            # Convert to RetrievalResult and refresh corpus stats from hits
            retrieval_results = []
            for doc in results:
                content = doc.get("content", "")
                doc_id = doc.get("id", doc.get("source", "unknown"))
                self._register_document(doc_id, content)
                retrieval_results.append(
                    RetrievalResult(
                        content=doc.get("content", ""),
                        score=doc.get("bm25_score", doc.get("score", 0.5)),
                        source=doc.get("id", doc.get("source", "unknown")),
                        metadata=doc.get("metadata", {}),
                        strategy=self.strategy_type,
                    )
                )

            self._track_latency(start_time, retrieval_results)

            logger.debug(
                "sparse_retrieval_completed",
                query=query[:50] if len(query) > 50 else query,
                results_count=len(retrieval_results),
                latency_ms=retrieval_results[0].latency_ms if retrieval_results else 0,
            )

            return retrieval_results[:top_k]

        except Exception as e:
            logger.error("sparse_retrieval_error", error=str(e))
            self._track_latency(start_time, [])
            return []


class HybridRetrievalStrategy(BaseRetrievalStrategy):
    """
    Hybrid retrieval combining dense and sparse methods.

    Combines vector similarity (dense) with BM25 (sparse) using reciprocal rank fusion (RRF)
    or weighted score combination for improved retrieval quality.

    Best for: General purpose retrieval, combining semantic and keyword matching.

    Features:
    - Reciprocal Rank Fusion (RRF)
    - Weighted score combination
    - Configurable dense/sparse balance
    - Normalization options
    """

    def __init__(
        self,
        dense_strategy: DenseRetrievalStrategy | None = None,
        sparse_strategy: SparseRetrievalStrategy | None = None,
        dense_weight: float = 0.5,
        sparse_weight: float = 0.5,
        fusion_method: str = "rrf",  # "rrf" or "weighted"
        rrf_k: int = 60,  # RRF constant
    ):
        super().__init__("hybrid_retrieval")
        self.dense_strategy = dense_strategy
        self.sparse_strategy = sparse_strategy
        self.dense_weight = dense_weight
        self.sparse_weight = sparse_weight
        self.fusion_method = fusion_method
        self.rrf_k = rrf_k

    @property
    def strategy_type(self) -> RetrievalStrategyType:
        return RetrievalStrategyType.HYBRID

    def _reciprocal_rank_fusion(
        self,
        dense_results: list[RetrievalResult],
        sparse_results: list[RetrievalResult],
    ) -> list[RetrievalResult]:
        """
        Apply Reciprocal Rank Fusion (RRF) to combine results.

        RRF formula: score(d) = sum(1 / (k + rank_i(d))) for each result list i

        Where k is a constant (typically 60) that controls the impact of rank.
        """
        # Build rank maps
        dense_ranks: dict[str, int] = {}
        sparse_ranks: dict[str, int] = {}

        for i, result in enumerate(dense_results):
            dense_ranks[result.source] = i + 1

        for i, result in enumerate(sparse_results):
            sparse_ranks[result.source] = i + 1

        # Calculate RRF scores
        all_sources = set(dense_ranks.keys()) | set(sparse_ranks.keys())
        rrf_scores: dict[str, float] = {}
        source_to_result: dict[str, RetrievalResult] = {}

        for source in all_sources:
            dense_rank = dense_ranks.get(source, len(dense_results) + 1)
            sparse_rank = sparse_ranks.get(source, len(sparse_results) + 1)

            rrf_score = 0.0
            if dense_rank <= len(dense_results):
                rrf_score += 1.0 / (self.rrf_k + dense_rank)
            if sparse_rank <= len(sparse_results):
                rrf_score += 1.0 / (self.rrf_k + sparse_rank)

            rrf_scores[source] = rrf_score

            # Keep reference to result (prefer dense if available)
            if source in dense_ranks:
                for r in dense_results:
                    if r.source == source:
                        source_to_result[source] = r
                        break
            elif source in sparse_ranks:
                for r in sparse_results:
                    if r.source == source:
                        source_to_result[source] = r
                        break

        # Sort by RRF score
        sorted_sources = sorted(rrf_scores.keys(), key=lambda s: rrf_scores[s], reverse=True)

        # Build fused results
        fused_results = []
        for source in sorted_sources:
            result = source_to_result.get(source)
            if result:
                result.score = rrf_scores[source]
                fused_results.append(result)

        return fused_results

    def _weighted_combination(
        self,
        dense_results: list[RetrievalResult],
        sparse_results: list[RetrievalResult],
    ) -> list[RetrievalResult]:
        """
        Combine results using weighted score combination.

        Normalizes scores from both methods and combines with weights.
        """

        # Normalize scores (min-max normalization)
        def normalize_scores(results: list[RetrievalResult]) -> dict[str, float]:
            if not results:
                return {}

            scores = [r.score for r in results]
            min_score = min(scores)
            max_score = max(scores)
            score_range = max_score - min_score if max_score > min_score else 1.0

            return {r.source: (r.score - min_score) / score_range for r in results}

        dense_normalized = normalize_scores(dense_results)
        sparse_normalized = normalize_scores(sparse_results)

        # Combine scores
        all_sources = set(dense_normalized.keys()) | set(sparse_normalized.keys())
        combined_scores: dict[str, float] = {}
        source_to_result: dict[str, RetrievalResult] = {}

        for source in all_sources:
            dense_score = dense_normalized.get(source, 0.0)
            sparse_score = sparse_normalized.get(source, 0.0)

            combined_score = self.dense_weight * dense_score + self.sparse_weight * sparse_score
            combined_scores[source] = combined_score

            # Keep reference to result
            for r in dense_results + sparse_results:
                if r.source == source:
                    source_to_result[source] = r
                    r.strategy = self.strategy_type
                    break

        # Sort by combined score
        sorted_sources = sorted(
            combined_scores.keys(), key=lambda s: combined_scores[s], reverse=True
        )

        # Build combined results
        combined_results = []
        for source in sorted_sources:
            result = source_to_result.get(source)
            if result:
                result.score = combined_scores[source]
                combined_results.append(result)

        return combined_results

    async def retrieve(
        self, query: str, top_k: int = 5, filters: dict[str, Any] | None = None, **kwargs
    ) -> list[RetrievalResult]:
        """
        Retrieve using hybrid dense + sparse combination.

        Args:
            query: Search query
            top_k: Number of results
            filters: Metadata filters
            **kwargs: Additional parameters

        Returns:
            List of retrieval results
        """
        start_time = time.time()

        # Execute both strategies in parallel
        dense_task = (
            self.dense_strategy.retrieve(query, top_k * 2, filters) if self.dense_strategy else None
        )
        sparse_task = (
            self.sparse_strategy.retrieve(query, top_k * 2, filters)
            if self.sparse_strategy
            else None
        )

        dense_results = await dense_task if dense_task else []
        sparse_results = await sparse_task if sparse_task else []

        # Fuse results
        if self.fusion_method == "rrf":
            fused_results = self._reciprocal_rank_fusion(dense_results, sparse_results)
        else:
            fused_results = self._weighted_combination(dense_results, sparse_results)

        # Limit to top_k
        final_results = fused_results[:top_k]

        self._track_latency(start_time, final_results)

        logger.debug(
            "hybrid_retrieval_completed",
            query=query[:50] if len(query) > 50 else query,
            dense_count=len(dense_results),
            sparse_count=len(sparse_results),
            fused_count=len(final_results),
            latency_ms=final_results[0].latency_ms if final_results else 0,
        )

        return final_results


class MultiHopRetrievalStrategy(BaseRetrievalStrategy):
    """
    Multi-hop retrieval for complex queries requiring chained lookups.

    Breaks down complex queries into multiple retrieval steps, using results
    from earlier hops to inform subsequent retrievals.

    Best for: Multi-step reasoning, bridging information gaps, complex queries.

    Features:
    - Query decomposition
    - Iterative retrieval with context accumulation
    - Hop limiting and early termination
    - Bridge entity detection
    """

    def __init__(
        self,
        base_strategy: BaseRetrievalStrategy | None = None,
        max_hops: int = 3,
        bridge_threshold: float = 0.3,
        query_decomposer: Any | None = None,
    ):
        super().__init__("multi_hop_retrieval")
        self.base_strategy = base_strategy
        self.max_hops = max_hops
        self.bridge_threshold = bridge_threshold
        self.query_decomposer = query_decomposer
        self._hop_stats: dict[str, int] = {}

    @property
    def strategy_type(self) -> RetrievalStrategyType:
        return RetrievalStrategyType.MULTI_HOP

    def _extract_bridge_entities(
        self,
        query: str,
        retrieved_content: str,
    ) -> list[str]:
        """
        Extract potential bridge entities from retrieved content.

        Bridge entities are terms that connect the query to additional information.
        """
        import re

        # Simple entity extraction - can be enhanced with NER
        # Look for capitalized terms, quoted terms, technical terms
        patterns = [
            r"\b[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*\b",  # Capitalized phrases
            r'"[^"]+"',  # Quoted terms
            r"\b[A-Z]{2,}\b",  # Acronyms
        ]

        entities = []
        for pattern in patterns:
            matches = re.findall(pattern, retrieved_content)
            entities.extend(matches)

        # Filter out query terms (we want NEW information)
        query_terms = set(query.lower().split())
        bridge_entities = [e for e in entities if e.lower() not in query_terms and len(e) > 2]

        return bridge_entities[:5]  # Limit entities

    def _generate_follow_up_query(
        self,
        original_query: str,
        bridge_entity: str,
        hop_number: int,
    ) -> str:
        """Generate a follow-up query based on bridge entity."""
        # Simple template-based query generation
        templates = [
            f"{original_query} {bridge_entity}",
            f"What is the relationship between {bridge_entity} and {original_query}?",
            f"Tell me more about {bridge_entity} in context of {original_query}",
        ]
        return templates[hop_number % len(templates)]

    async def retrieve(
        self, query: str, top_k: int = 5, filters: dict[str, Any] | None = None, **kwargs
    ) -> list[RetrievalResult]:
        """
        Retrieve using multi-hop chained queries.

        Args:
            query: Search query
            top_k: Number of results
            filters: Metadata filters
            **kwargs: Additional parameters

        Returns:
            List of retrieval results
        """
        start_time = time.time()

        if not self.base_strategy:
            logger.warning("multi_hop_retrieval_unavailable", reason="base_strategy not configured")
            return []

        all_results: list[RetrievalResult] = []
        current_query = query
        seen_sources: set = set()

        for hop in range(self.max_hops):
            # Execute retrieval for current hop
            hop_results = await self.base_strategy.retrieve(
                query=current_query,
                top_k=top_k,
                filters=filters,
            )

            # Track hop statistics
            self._hop_stats[f"hop_{hop + 1}"] = len(hop_results)

            # Add new results (avoid duplicates)
            new_results = []
            for result in hop_results:
                if result.source not in seen_sources:
                    result.metadata["hop"] = hop + 1
                    result.metadata["query_used"] = current_query
                    new_results.append(result)
                    seen_sources.add(result.source)

            all_results.extend(new_results)

            # Check for early termination
            if not new_results or len(new_results) < 2:
                logger.debug("multi_hop_early_termination", hop=hop + 1)
                break

            # Extract bridge entities for next hop
            if hop < self.max_hops - 1:
                combined_content = "\n".join(r.content for r in new_results[:3])
                bridge_entities = self._extract_bridge_entities(query, combined_content)

                if bridge_entities:
                    current_query = self._generate_follow_up_query(
                        query,
                        bridge_entities[0],
                        hop,
                    )
                else:
                    break

        # Re-rank by combined score
        all_results.sort(key=lambda r: r.score, reverse=True)
        final_results = all_results[:top_k]

        self._track_latency(start_time, final_results)

        logger.debug(
            "multi_hop_retrieval_completed",
            query=query[:50] if len(query) > 50 else query,
            hops_executed=len(self._hop_stats),
            total_results=len(all_results),
            final_results=len(final_results),
            latency_ms=final_results[0].latency_ms if final_results else 0,
        )

        return final_results

    def get_hop_stats(self) -> dict[str, int]:
        """Get statistics about hops executed."""
        return self._hop_stats.copy()


class ReRankingStrategy(BaseRetrievalStrategy):
    """
    Re-ranking using cross-encoder scoring.

    Takes initial retrieval results and re-ranks them using a more sophisticated
    (but slower) cross-encoder model that considers query-document pairs jointly.

    Best for: Final result refinement, improving precision, complex queries.

    Features:
    - Cross-encoder scoring
    - Configurable re-rank limit
    - Score calibration
    - Batch processing
    """

    def __init__(
        self,
        cross_encoder: Any | None = None,
        re_rank_limit: int = 50,
        score_threshold: float = 0.0,
        batch_size: int = 32,
    ):
        super().__init__("re_ranking")
        self.cross_encoder = cross_encoder
        self.re_rank_limit = re_rank_limit
        self.score_threshold = score_threshold
        self.batch_size = batch_size

    @property
    def strategy_type(self) -> RetrievalStrategyType:
        return RetrievalStrategyType.RE_RANKING

    async def retrieve(
        self,
        query: str,
        top_k: int = 5,
        initial_results: list[RetrievalResult] | None = None,
        **kwargs,
    ) -> list[RetrievalResult]:
        """
        Re-rank initial retrieval results using cross-encoder.

        Args:
            query: Search query
            top_k: Number of final results
            initial_results: Results from initial retrieval (required)
            **kwargs: Additional parameters

        Returns:
            Re-ranked list of retrieval results
        """
        start_time = time.time()

        if not initial_results:
            logger.warning("re_ranking_no_initial_results", reason="initial_results required")
            return []

        if not self.cross_encoder:
            # Return initial results sorted by score if no cross-encoder
            return sorted(initial_results, key=lambda r: r.score, reverse=True)[:top_k]

        try:
            # Limit candidates for re-ranking
            candidates = initial_results[: self.re_rank_limit]

            # Prepare query-document pairs for cross-encoder
            pairs = [(query, candidate.content) for candidate in candidates]

            # Score in batches
            cross_scores = []
            for i in range(0, len(pairs), self.batch_size):
                batch = pairs[i : i + self.batch_size]
                batch_scores = await self.cross_encoder.predict(batch)
                cross_scores.extend(batch_scores)

            # Apply cross-encoder scores
            for result, score in zip(candidates, cross_scores, strict=False):
                # Combine original score with cross-encoder score
                result.score = 0.5 * result.score + 0.5 * score
                result.metadata["cross_encoder_score"] = score

            # Filter by threshold and sort
            filtered = [r for r in candidates if r.score >= self.score_threshold]
            filtered.sort(key=lambda r: r.score, reverse=True)

            final_results = filtered[:top_k]

            self._track_latency(start_time, final_results)

            logger.debug(
                "re_ranking_completed",
                query=query[:50] if len(query) > 50 else query,
                candidates=len(candidates),
                final_count=len(final_results),
                latency_ms=final_results[0].latency_ms if final_results else 0,
            )

            return final_results

        except Exception as e:
            logger.error("re_ranking_error", error=str(e))
            self._track_latency(start_time, [])
            return initial_results[:top_k]


class QueryClassifier:
    """
    Classifies queries to select the best retrieval strategy.

    Uses heuristics and optionally ML-based classification to determine
    query type and recommend appropriate retrieval strategy.
    """

    # Query type indicators
    FACTUAL_INDICATORS = ["who", "what", "when", "where", "define", "meaning of"]
    EXPLANATORY_INDICATORS = ["how", "why", "explain", "reason", "cause"]
    COMPARATIVE_INDICATORS = ["compare", "difference", "better", "vs", "versus"]
    PROCEDURAL_INDICATORS = ["how to", "steps", "guide", "tutorial", "process"]
    MULTI_STEP_INDICATORS = ["first", "then", "after", "before", "relationship between"]

    def classify(self, query: str) -> QueryType:
        """
        Classify a query to determine its type.

        Args:
            query: Query text

        Returns:
            QueryType enumeration value
        """
        query_lower = query.lower()

        # Check for multi-step indicators first (highest priority)
        if any(ind in query_lower for ind in self.MULTI_STEP_INDICATORS):
            return QueryType.MULTI_STEP

        # Check other types
        if any(ind in query_lower for ind in self.EXPLANATORY_INDICATORS):
            return QueryType.EXPLANATORY

        if any(ind in query_lower for ind in self.COMPARATIVE_INDICATORS):
            return QueryType.COMPARATIVE

        if any(ind in query_lower for ind in self.PROCEDURAL_INDICATORS):
            return QueryType.PROCEDURAL

        if any(ind in query_lower for ind in self.FACTUAL_INDICATORS):
            return QueryType.FACTUAL

        # Default to exploratory
        return QueryType.EXPLORATORY

    def recommend_strategy(self, query_type: QueryType) -> RetrievalStrategyType:
        """
        Recommend retrieval strategy based on query type.

        Args:
            query_type: Classified query type

        Returns:
            Recommended RetrievalStrategyType
        """
        strategy_map = {
            QueryType.FACTUAL: RetrievalStrategyType.HYBRID,  # Need both semantic and keyword
            QueryType.EXPLANATORY: RetrievalStrategyType.DENSE,  # Semantic understanding
            QueryType.COMPARATIVE: RetrievalStrategyType.HYBRID,  # Need comprehensive results
            QueryType.PROCEDURAL: RetrievalStrategyType.SPARSE,  # Exact steps matching
            QueryType.EXPLORATORY: RetrievalStrategyType.HYBRID,  # Broad coverage
            QueryType.MULTI_STEP: RetrievalStrategyType.MULTI_HOP,  # Requires chaining
        }
        return strategy_map.get(query_type, RetrievalStrategyType.HYBRID)


class StrategySelector:
    """
    Selects and executes the best retrieval strategy for a given query.

    Features:
    - Automatic strategy selection based on query classification
    - Query caching for frequent queries
    - Fallback handling
    - Performance tracking
    """

    def __init__(
        self,
        strategies: dict[RetrievalStrategyType, BaseRetrievalStrategy] | None = None,
        cache_enabled: bool = True,
        cache_ttl_seconds: int = 300,
    ):
        self.strategies = strategies or {}
        self.cache_enabled = cache_enabled
        self.cache_ttl_seconds = cache_ttl_seconds
        self._query_cache: dict[str, QueryCacheEntry] = {}
        self._classifier = QueryClassifier()
        self._stats: dict[str, Any] = {
            "total_queries": 0,
            "cache_hits": 0,
            "cache_misses": 0,
            "strategy_usage": {},
        }

    def _hash_query(self, query: str) -> str:
        """Create a hash of the query for caching."""
        return hashlib.md5(query.lower().strip().encode(), usedforsecurity=False).hexdigest()

    def _get_from_cache(self, query_hash: str) -> list[RetrievalResult] | None:
        """Get cached results if available and not expired."""
        if not self.cache_enabled:
            return None

        entry = self._query_cache.get(query_hash)
        if entry and not entry.is_expired(self.cache_ttl_seconds):
            entry.access_count += 1
            entry.last_accessed = datetime.now(UTC)
            self._stats["cache_hits"] += 1
            return entry.results

        self._stats["cache_misses"] += 1
        return None

    def _store_in_cache(self, query_hash: str, results: list[RetrievalResult]) -> None:
        """Store results in cache."""
        if not self.cache_enabled:
            return

        self._query_cache[query_hash] = QueryCacheEntry(
            query_hash=query_hash,
            results=results,
            created_at=datetime.now(UTC),
        )

        # Clean old cache entries periodically
        if len(self._query_cache) > 1000:
            self._clean_cache()

    def _clean_cache(self) -> None:
        """Remove expired and least recently used cache entries."""
        datetime.now(UTC)
        # Remove expired
        expired = [k for k, v in self._query_cache.items() if v.is_expired(self.cache_ttl_seconds)]
        for k in expired:
            del self._query_cache[k]

        # If still too large, remove LRU entries
        if len(self._query_cache) > 1000:
            sorted_entries = sorted(
                self._query_cache.items(),
                key=lambda x: x[1].last_accessed,
                reverse=True,
            )
            for k, _ in sorted_entries[500:]:
                del self._query_cache[k]

    def add_strategy(
        self,
        strategy_type: RetrievalStrategyType,
        strategy: BaseRetrievalStrategy,
    ) -> None:
        """Add a retrieval strategy."""
        self.strategies[strategy_type] = strategy

    async def retrieve(
        self,
        query: str,
        top_k: int = 5,
        strategy: RetrievalStrategyType | None = None,
        filters: dict[str, Any] | None = None,
        **kwargs,
    ) -> list[RetrievalResult]:
        """
        Retrieve using the best strategy for the query.

        Args:
            query: Search query
            top_k: Number of results
            strategy: Optional explicit strategy (auto-selected if not provided)
            filters: Metadata filters
            **kwargs: Strategy-specific parameters

        Returns:
            List of retrieval results
        """
        self._stats["total_queries"] += 1

        # Check cache first
        query_hash = self._hash_query(query)
        cached = self._get_from_cache(query_hash)
        if cached:
            return cached

        # Determine strategy
        if strategy is None:
            query_type = self._classifier.classify(query)
            strategy = self._classifier.recommend_strategy(query_type)

        # Track strategy usage
        strategy_key = strategy.value
        self._stats["strategy_usage"][strategy_key] = (
            self._stats["strategy_usage"].get(strategy_key, 0) + 1
        )

        # Get strategy
        selected_strategy = self.strategies.get(strategy)
        if not selected_strategy:
            logger.warning("strategy_not_available", strategy=strategy.value)
            # Fallback to any available strategy
            if self.strategies:
                selected_strategy = next(iter(self.strategies.values()))
            else:
                return []

        # Execute retrieval
        results = await selected_strategy.retrieve(
            query=query,
            top_k=top_k,
            filters=filters,
            **kwargs,
        )

        # Cache results
        self._store_in_cache(query_hash, results)

        logger.debug(
            "strategy_selected",
            query=query[:50] if len(query) > 50 else query,
            strategy=strategy.value,
            results_count=len(results),
        )

        return results

    def get_stats(self) -> dict[str, Any]:
        """Get selector statistics."""
        return {
            **self._stats,
            "cache_size": len(self._query_cache),
            "available_strategies": list(self.strategies.keys()),
        }


@dataclass
class RAGStrategyConfig:
    """Configuration for RAG strategies."""

    # Dense retrieval config
    dense_enabled: bool = True
    similarity_metric: str = "cosine"
    similarity_threshold: float = 0.0

    # Sparse retrieval config
    sparse_enabled: bool = True
    bm25_k1: float = 1.5
    bm25_b: float = 0.75

    # Hybrid retrieval config
    hybrid_enabled: bool = True
    dense_weight: float = 0.5
    sparse_weight: float = 0.5
    fusion_method: str = "rrf"
    rrf_k: int = 60

    # Multi-hop retrieval config
    multi_hop_enabled: bool = True
    max_hops: int = 3
    bridge_threshold: float = 0.3

    # Re-ranking config
    re_ranking_enabled: bool = True
    re_rank_limit: int = 50
    score_threshold: float = 0.0

    # Cache config
    cache_enabled: bool = True
    cache_ttl_seconds: int = 300


def create_default_strategies(
    config: RAGStrategyConfig | None = None,
) -> dict[RetrievalStrategyType, BaseRetrievalStrategy]:
    """
    Create default strategy instances.

    Args:
        config: Optional configuration

    Returns:
        Dictionary of strategy type to strategy instance
    """
    config = config or RAGStrategyConfig()
    strategies = {}

    # Create dense strategy
    if config.dense_enabled:
        strategies[RetrievalStrategyType.DENSE] = DenseRetrievalStrategy(
            similarity_metric=config.similarity_metric,
            similarity_threshold=config.similarity_threshold,
        )

    # Create sparse strategy
    if config.sparse_enabled:
        strategies[RetrievalStrategyType.SPARSE] = SparseRetrievalStrategy(
            k1=config.bm25_k1,
            b=config.bm25_b,
        )

    # Create hybrid strategy (requires dense and sparse)
    if (
        config.hybrid_enabled
        and RetrievalStrategyType.DENSE in strategies
        and RetrievalStrategyType.SPARSE in strategies
    ):
        strategies[RetrievalStrategyType.HYBRID] = HybridRetrievalStrategy(
            dense_strategy=strategies[RetrievalStrategyType.DENSE],
            sparse_strategy=strategies[RetrievalStrategyType.SPARSE],
            dense_weight=config.dense_weight,
            sparse_weight=config.sparse_weight,
            fusion_method=config.fusion_method,
            rrf_k=config.rrf_k,
        )

    # Create multi-hop strategy
    if config.multi_hop_enabled:
        # Use hybrid as base if available, otherwise dense
        base_strategy = strategies.get(RetrievalStrategyType.HYBRID) or strategies.get(
            RetrievalStrategyType.DENSE
        )
        if base_strategy:
            strategies[RetrievalStrategyType.MULTI_HOP] = MultiHopRetrievalStrategy(
                base_strategy=base_strategy,
                max_hops=config.max_hops,
                bridge_threshold=config.bridge_threshold,
            )

    # Create re-ranking strategy
    if config.re_ranking_enabled:
        strategies[RetrievalStrategyType.RE_RANKING] = ReRankingStrategy(
            re_rank_limit=config.re_rank_limit,
            score_threshold=config.score_threshold,
        )

    return strategies


def create_strategy_selector(
    config: RAGStrategyConfig | None = None,
    embedding_provider: Any | None = None,
    vector_store: Any | None = None,
    sparse_index: Any | None = None,
    cross_encoder: Any | None = None,
) -> StrategySelector:
    """
    Create a fully configured strategy selector.

    Args:
        config: Strategy configuration
        embedding_provider: Embedding provider for dense retrieval
        vector_store: Vector store for dense retrieval
        sparse_index: Sparse index for BM25 retrieval
        cross_encoder: Cross-encoder model for re-ranking

    Returns:
        Configured StrategySelector instance
    """
    config = config or RAGStrategyConfig()

    # Create strategies
    strategies = create_default_strategies(config)

    # Inject dependencies
    if RetrievalStrategyType.DENSE in strategies and embedding_provider and vector_store:
        strategies[RetrievalStrategyType.DENSE].embedding_provider = embedding_provider
        strategies[RetrievalStrategyType.DENSE].vector_store = vector_store

    if RetrievalStrategyType.SPARSE in strategies and sparse_index:
        strategies[RetrievalStrategyType.SPARSE].index = sparse_index

    if RetrievalStrategyType.RE_RANKING in strategies and cross_encoder:
        strategies[RetrievalStrategyType.RE_RANKING].cross_encoder = cross_encoder

    # Create selector
    return StrategySelector(
        strategies=strategies,
        cache_enabled=config.cache_enabled,
        cache_ttl_seconds=config.cache_ttl_seconds,
    )
