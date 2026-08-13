"""
OpenAI Embedding Provider

Implementation of the embedding provider interface for OpenAI's API.
Supports text-embedding-3-small, text-embedding-3-large, and text-embedding-ada-002.
"""

from __future__ import annotations

import time
from typing import Any

import httpx
import structlog

from heretek_swarm.infrastructure.otel import instrumented_httpx_client

from .base import (
    EmbeddingAuthenticationError,
    EmbeddingProviderBase,
    EmbeddingProviderCapabilities,
    EmbeddingProviderError,
    EmbeddingRateLimitError,
    EmbeddingResponse,
    EmbeddingUnavailableError,
)

logger = structlog.get_logger("embeddings.providers.openai")


class OpenAIEmbeddingProvider(EmbeddingProviderBase):
    """
    OpenAI Embedding Provider implementation.

    Supports:
    - text-embedding-3-small (1536 dimensions)
    - text-embedding-3-large (3072 dimensions)
    - text-embedding-ada-002 (1536 dimensions)

    Example:
        provider = OpenAIEmbeddingProvider(
            api_key="sk-...",
            default_model="text-embedding-3-small"
        )
        response = await provider.embed(["Hello, world!"])
    """

    def __init__(
        self,
        api_key: str,
        base_url: str = "https://api.openai.com/v1",
        default_model: str | None = None,
        organization: str | None = None,
        extra_config: dict[str, Any] | None = None,
    ):
        """
        Initialize the OpenAI embedding provider.

        Args:
            api_key: OpenAI API key
            base_url: Base URL (default: https://api.openai.com/v1)
            default_model: Default model to use
            organization: OpenAI organization ID (optional)
            extra_config: Additional configuration
        """
        if not api_key:
            raise EmbeddingAuthenticationError("OpenAI API key is required")

        super().__init__(
            provider_name="openai",
            base_url=base_url,
            api_key=api_key,
            default_model=default_model or "text-embedding-3-small",
            extra_config=extra_config,
        )

        self.organization = organization
        self._client: InstrumentedAsyncClient | None = None

    def _init_capabilities(self) -> EmbeddingProviderCapabilities:
        """Initialize provider capabilities."""
        return EmbeddingProviderCapabilities(
            max_batch_size=2048,
            max_tokens_per_batch=8192,
            supported_formats=["float", "base64"],
            supports_dimensions_override=True,
            default_dimensions=1536,
        )

    async def _get_client(self) -> InstrumentedAsyncClient:
        """Get or create the instrumented HTTP client."""
        if self._client is None or self._client.is_closed:
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            }
            if self.organization:
                headers["OpenAI-Organization"] = self.organization

            base_client = httpx.AsyncClient(
                base_url=self.base_url,
                headers=headers,
                timeout=httpx.Timeout(60.0, connect=10.0),
            )
            self._client = instrumented_httpx_client(
                client=base_client, call_type="embeddings_openai"
            )
        return self._client

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
        """
        client = await self._get_client()
        start_time = time.time()

        model = self._get_model(model)
        inputs = self._ensure_list(texts)

        payload = {
            "model": model,
            "input": inputs,
            "encoding_format": "float",
        }

        # Add dimensions if specified and model supports it
        if dimensions and self.capabilities.supports_dimensions_override:
            payload["dimensions"] = dimensions

        logger.debug(
            "Sending OpenAI embedding request",
            model=model,
            text_count=len(inputs),
        )

        try:
            response = await client.post(
                "/embeddings",
                json=payload,
            )

            if response.status_code == 401:
                raise EmbeddingAuthenticationError(
                    "Invalid OpenAI API key",
                    provider="openai",
                )
            if response.status_code == 429:
                retry_after = response.headers.get("Retry-After")
                raise EmbeddingRateLimitError(
                    "Rate limited by OpenAI",
                    provider="openai",
                    retry_after=float(retry_after) if retry_after else None,
                )
            if response.status_code >= 500:
                raise EmbeddingUnavailableError(
                    "OpenAI service unavailable",
                    provider="openai",
                )
            if response.status_code != 200:
                raise EmbeddingProviderError(
                    f"OpenAI API error: {response.status_code}",
                    provider="openai",
                )

            data = response.json()
            latency_ms = (time.time() - start_time) * 1000

            # Extract embeddings from response
            embeddings = [item["embedding"] for item in data.get("data", [])]

            return EmbeddingResponse(
                embeddings=embeddings,
                model=data.get("model", model),
                usage=data.get("usage", {}),
                raw_response=data,
                latency_ms=latency_ms,
            )

        except httpx.RequestError as e:
            raise EmbeddingUnavailableError(
                f"Request failed: {e}",
                provider="openai",
                cause=e,
            ) from e

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Cleanup HTTP client."""
        if self._client and not self._client.is_closed:
            await self._client.aclose()


# Import at module level for type annotation
from heretek_swarm.infrastructure.otel import InstrumentedAsyncClient  # noqa: E402
