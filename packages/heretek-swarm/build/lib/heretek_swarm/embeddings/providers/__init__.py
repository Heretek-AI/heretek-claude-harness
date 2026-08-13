"""
Embedding Providers Package

Multi-provider embedding abstraction layer supporting:
- OpenAI
- Ollama
- OpenAI-Compatible APIs
- Local embeddings
- HuggingFace
"""

from .base import EmbeddingProviderBase, EmbeddingRequest, EmbeddingResponse
from .factory import create_embedding_provider, get_provider_class, list_available_providers

__all__ = [
    "EmbeddingProviderBase",
    "EmbeddingRequest",
    "EmbeddingResponse",
    "create_embedding_provider",
    "get_provider_class",
    "list_available_providers",
]
