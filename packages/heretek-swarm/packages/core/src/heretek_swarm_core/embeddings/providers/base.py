"""
Embedding Provider Base Class

Abstract base class for all embedding providers in Heretek Swarm.
Defines the interface that all embedding providers must implement.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

import structlog

logger = structlog.get_logger("embeddings.providers.base")


@dataclass
class EmbeddingRequest:
    """Request parameters for embedding generation."""

    inputs: str | list[str]
    model: str | None = None
    encoding_format: str = "float"  # "float" or "base64"
    dimensions: int | None = None
    user: str | None = None
    extra_body: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert request to dictionary for API calls."""
        result = {
            "input": self.inputs,
            "encoding_format": self.encoding_format,
        }

        if self.model:
            result["model"] = self.model
        if self.dimensions is not None:
            result["dimensions"] = self.dimensions
        if self.user:
            result["user"] = self.user
        if self.extra_body:
            result.update(self.extra_body)

        return result


@dataclass
class EmbeddingResponse:
    """Response from an embedding generation request."""

    embeddings: list[list[float]]
    model: str
    usage: dict[str, int] = field(default_factory=dict)
    raw_response: dict[str, Any] | None = None
    latency_ms: float = 0.0

    @property
    def dimensions(self) -> int:
        """Get the embedding dimensions."""
        if self.embeddings and len(self.embeddings) > 0:
            return len(self.embeddings[0])
        return 0

    @property
    def prompt_tokens(self) -> int:
        """Get the number of prompt tokens used."""
        return self.usage.get("prompt_tokens", 0)

    @property
    def total_tokens(self) -> int:
        """Get the total tokens used."""
        return self.usage.get("total_tokens", 0)


@dataclass
class EmbeddingProviderCapabilities:
    """Capabilities of an embedding provider."""

    max_batch_size: int = 32
    max_tokens_per_batch: int = 8192
    supported_formats: list[str] = field(default_factory=lambda: ["float"])
    supports_dimensions_override: bool = False
    default_dimensions: int | None = None


class EmbeddingProviderBase(ABC):
    """
    Abstract base class for all embedding providers.

    All provider implementations must inherit from this class and implement
    the required abstract methods.

    Example usage:
        provider = OpenAIEmbeddingProvider(api_key="sk-...")
        response = await provider.embed(texts=["Hello, world!"])
    """

    def __init__(
        self,
        provider_name: str,
        base_url: str,
        api_key: str | None = None,
        default_model: str | None = None,
        extra_config: dict[str, Any] | None = None,
    ):
        """
        Initialize the embedding provider.

        Args:
            provider_name: Name identifier for this provider
            base_url: Base URL for the API
            api_key: API key for authentication (optional for some providers)
            default_model: Default model to use
            extra_config: Additional provider-specific configuration
        """
        self.provider_name = provider_name
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.default_model = default_model
        self.extra_config = extra_config or {}

        self._capabilities = self._init_capabilities()

        logger.debug(
            "Embedding provider initialized",
            provider_name=provider_name,
            base_url=base_url,
        )

    @abstractmethod
    def _init_capabilities(self) -> EmbeddingProviderCapabilities:
        """Initialize provider capabilities. Must be implemented by subclasses."""

    @property
    def capabilities(self) -> EmbeddingProviderCapabilities:
        """Get the provider's capabilities."""
        return self._capabilities

    @abstractmethod
    async def embed(
        self,
        texts: str | list[str],
        model: str | None = None,
        dimensions: int | None = None,
    ) -> EmbeddingResponse:
        """
        Generate embeddings for texts.

        Args:
            texts: Single text or list of texts to embed
            model: Optional model override
            dimensions: Optional dimensions override

        Returns:
            Embedding response with vectors

        Raises:
            ProviderError: If the request fails
        """

    async def embed_with_retry(
        self,
        texts: str | list[str],
        model: str | None = None,
        dimensions: int | None = None,
        max_retries: int = 3,
        retry_delay: float = 1.0,
    ) -> EmbeddingResponse:
        """
        Generate embeddings with automatic retries.

        Args:
            texts: Single text or list of texts to embed
            model: Optional model override
            dimensions: Optional dimensions override
            max_retries: Maximum number of retry attempts
            retry_delay: Delay between retries in seconds

        Returns:
            Embedding response

        Raises:
            ProviderError: If all retries fail
        """
        import asyncio

        last_error = None

        for attempt in range(max_retries):
            try:
                return await self.embed(texts, model, dimensions)
            except Exception as e:
                last_error = e
                if attempt < max_retries - 1:
                    logger.warning(
                        "Embedding request failed, retrying",
                        provider=self.provider_name,
                        attempt=attempt + 1,
                        max_retries=max_retries,
                        error=str(e),
                    )
                    await asyncio.sleep(retry_delay * (attempt + 1))

        raise EmbeddingProviderError(
            f"Failed after {max_retries} attempts",
            provider=self.provider_name,
            cause=last_error,
        )

    def _get_model(self, model: str | None) -> str:
        """Get the model to use, falling back to default if needed."""
        if model:
            return model
        if self.default_model:
            return self.default_model
        raise ValueError("No model specified and no default model configured")

    def _ensure_list(self, texts: str | list[str]) -> list[str]:
        """Ensure texts is a list."""
        if isinstance(texts, str):
            return [texts]
        return list(texts)

    async def __aenter__(self):
        """Async context manager entry."""
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""


class EmbeddingProviderError(Exception):
    """Exception raised for embedding provider-related errors."""

    def __init__(
        self,
        message: str,
        provider: str | None = None,
        cause: Exception | None = None,
    ):
        self.message = message
        self.provider = provider
        self.cause = cause
        super().__init__(self.format_message())

    def format_message(self) -> str:
        """Format the error message."""
        msg = self.message
        if self.provider:
            msg = f"[{self.provider}] {msg}"
        if self.cause:
            msg = f"{msg} (caused by: {self.cause})"
        return msg


class EmbeddingConfigurationError(EmbeddingProviderError):
    """Exception raised for configuration errors."""


class EmbeddingAuthenticationError(EmbeddingProviderError):
    """Exception raised for authentication errors."""


class EmbeddingRateLimitError(EmbeddingProviderError):
    """Exception raised when rate limited."""

    def __init__(
        self,
        message: str,
        provider: str | None = None,
        retry_after: float | None = None,
    ):
        self.retry_after = retry_after
        super().__init__(message, provider)


class EmbeddingUnavailableError(EmbeddingProviderError):
    """Exception raised when provider is unavailable."""
