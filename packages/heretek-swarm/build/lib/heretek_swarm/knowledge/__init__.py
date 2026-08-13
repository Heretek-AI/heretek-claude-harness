"""
Knowledge Access Layer for Heretek Swarm

Provides unified interface for querying memory and RAG systems
with intelligent result merging and MMR reranking.
"""

from heretek_swarm.knowledge.unified_access import (
    KnowledgeEntry,
    KnowledgeQueryBuilder,
    KnowledgeQueryResult,
    UnifiedKnowledgeAccess,
)

__all__ = [
    "KnowledgeEntry",
    "KnowledgeQueryBuilder",
    "KnowledgeQueryResult",
    "UnifiedKnowledgeAccess",
]
