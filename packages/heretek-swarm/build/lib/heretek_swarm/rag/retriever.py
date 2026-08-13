"""Retriever exports for compatibility."""

from dataclasses import dataclass, field
from typing import Any

from heretek_swarm.rag.hybrid_retriever import (
    HybridRetriever,
    HybridRetrieverConfig,
    RateLimitExceeded,
    RetrieverError,
    RetrieverNotReady,
    RetrieverState,
)


@dataclass
class RetrievalConfig:
    top_k: int = 5
    score_threshold: float = 0.0
    metadata: dict[str, Any] | None = None


@dataclass
class SearchResult:
    id: str
    content: str
    score: float = 0.0
    metadata: dict[str, Any] = field(default_factory=dict)


__all__ = [
    "HybridRetriever",
    "HybridRetrieverConfig",
    "RateLimitExceeded",
    "RetrievalConfig",
    "RetrieverError",
    "RetrieverNotReady",
    "RetrieverState",
    "SearchResult",
]
