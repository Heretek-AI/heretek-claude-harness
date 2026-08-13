"""
RAG (Retrieval-Augmented Generation) package for Heretek Swarm.

Provides vector search, document retrieval, and context augmentation capabilities.
"""

from heretek_swarm.rag.hybrid_retriever import HybridRetriever, HybridRetrieverConfig
from heretek_swarm.rag.rag_pipeline import RAGPipeline, RAGPipelineConfig

__all__ = [
    "HybridRetriever",
    "HybridRetrieverConfig",
    "RAGPipeline",
    "RAGPipelineConfig",
]
