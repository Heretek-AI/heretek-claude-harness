"""Provider registry interface for lazy resolution.

This module provides the abstract registry interface that enables
lazy loading of providers and breaks circular dependencies.
"""

from abc import ABC, abstractmethod
from typing import Any

from .providers import EmbeddingProviderInterface, LLMProviderInterface


class ProviderRegistryInterface(ABC):
    """Abstract registry for provider management.

    This interface defines how providers are registered and retrieved,
    enabling loose coupling between the API layer and provider implementations.
    """

    @abstractmethod
    def get_llm_provider(self, name: str) -> LLMProviderInterface | None:
        """Get an LLM provider by name.

        Args:
            name: Provider name identifier

        Returns:
            LLM provider instance or None if not found
        """

    @abstractmethod
    def get_embedding_provider(self, name: str) -> EmbeddingProviderInterface | None:
        """Get an embedding provider by name.

        Args:
            name: Provider name identifier

        Returns:
            Embedding provider instance or None if not found
        """

    @abstractmethod
    def list_llm_providers(self) -> list[str]:
        """List available LLM provider names.

        Returns:
            List of available LLM provider identifiers
        """

    @abstractmethod
    def list_embedding_providers(self) -> list[str]:
        """List available embedding provider names.

        Returns:
            List of available embedding provider identifiers
        """

    @abstractmethod
    def register_llm_provider(self, name: str, provider_class: type[LLMProviderInterface]) -> None:
        """Register an LLM provider class.

        Args:
            name: Provider identifier
            provider_class: Provider class implementing LLMProviderInterface
        """

    @abstractmethod
    def register_embedding_provider(
        self, name: str, provider_class: type[EmbeddingProviderInterface]
    ) -> None:
        """Register an embedding provider class.

        Args:
            name: Provider identifier
            provider_class: Provider class implementing EmbeddingProviderInterface
        """

    @abstractmethod
    def get_provider_info(self, name: str) -> dict[str, Any] | None:
        """Get provider information.

        Args:
            name: Provider name

        Returns:
            Provider info dict or None if not found
        """
