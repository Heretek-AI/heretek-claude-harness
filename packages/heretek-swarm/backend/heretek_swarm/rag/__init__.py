"""
RAG (Retrieval-Augmented Generation) package for Heretek Swarm.

Provides vector search, document retrieval, and context augmentation capabilities.
"""

from heretek_swarm.rag.hybrid_retriever import HybridRetriever, HybridRetrieverConfig
from heretek_swarm.rag.cognee_rag import CogneeRAGRetriever, get_rag_retriever

__all__ = [
    "HybridRetriever",
    "HybridRetrieverConfig",
    "CogneeRAGRetriever",
    "get_rag_retriever",
]
