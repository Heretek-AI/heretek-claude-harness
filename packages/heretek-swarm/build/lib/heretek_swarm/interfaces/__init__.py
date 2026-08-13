"""Heretek Swarm Interfaces Module.

This module provides abstract interfaces that define contracts between
different parts of the application, enabling dependency inversion
and breaking circular dependencies.
"""

from .providers import EmbeddingProviderInterface, LLMProviderInterface
from .registry import ProviderRegistryInterface

__all__ = [
    "EmbeddingProviderInterface",
    "LLMProviderInterface",
    "ProviderRegistryInterface",
]
