"""
Ollama Embedding Provider

Implementation of the embedding provider interface for Ollama.
Supports local embedding generation with models like nomic-embed-text, mxbai-embed-large, etc.

Reference: https://github.com/ollama/ollama/blob/main/docs/api.md#generate-embeddings
"""

from __future__ import annotations

import time
from typing import Any

import httpx
import structlog
from heretek_swarm.infrastructure.otel import instrumented_httpx_client

from .base import (
    EmbeddingProviderBase,
    EmbeddingProviderCapabilities,
    EmbeddingProviderError,
    EmbeddingResponse,
    EmbeddingUnavailableError,
)

logger = structlog.get_logger("embeddings.providers.ollama")


class OllamaEmbeddingProvider(EmbeddingProviderBase):
    """
    Ollama Embedding Provider implementation.

    Supports:
    - nomic-embed-text (768 dimensions)
    - mxbai-embed-large (1024 dimensions)
    - all-minilm (384 dimensions)
    - Other Ollama embedding models

    Example:
        provider = OllamaEmbeddingProvider(
            base_url="http://localhost:11434",
            default_model="nomic-embed-text"
        )
        response = await provider.embed(["Hello, world!"])
    """

    def __init__(
        self,
        base_url: str = "http://localhost:11434",
        default_model: str | None = None,
        extra_config: dict[str, Any] | None = None,
    ):
        """
        Initialize the Ollama embedding provider.

        Args:
            base_url: Ollama server URL (default: http://localhost:11434)
            default_model: Default model to use
            extra_config: Additional configuration
        """
        super().__init__(
            provider_name="ollama",
            base_url=base_url,
            api_key=None,  # Ollama doesn't require authentication
            default_model=default_model or "nomic-embed-text",
            extra_config=extra_config,
        )

        self._client: InstrumentedAsyncClient | None = None

    def _init_capabilities(self) -> EmbeddingProviderCapabilities:
        """Initialize provider capabilities."""
        return EmbeddingProviderCapabilities(
            max_batch_size=32,
            max_tokens_per_batch=8192,
            supported_formats=["float"],
            supports_dimensions_override=False,
            default_dimensions=None,  # Varies by model
        )

    async def _get_client(self) -> InstrumentedAsyncClient:
        """Get or create the instrumented HTTP client."""
        if self._client is None or self._client.is_closed:
            base_client = httpx.AsyncClient(
                base_url=self.base_url,
                headers={"Content-Type": "application/json"},
                timeout=httpx.Timeout(120.0, connect=10.0),
            )
            self._client = instrumented_httpx_client(
                client=base_client, call_type="embeddings_ollama"
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
            dimensions: Optional dimensions override (not supported by Ollama)

        Returns:
            Embedding response with vectors
        """
        client = await self._get_client()
        start_time = time.time()

        model = self._get_model(model)
        inputs = self._ensure_list(texts)

        embeddings = []
        total_prompt_tokens = 0

        # Ollama processes one text at a time for embeddings
        for text in inputs:
            payload = {
                "model": model,
                "prompt": text,
            }

            logger.debug(
                "Sending Ollama embedding request",
                model=model,
                text_length=len(text),
            )

            try:
                response = await client.post(
                    "/api/embeddings",
                    json=payload,
                )

                if response.status_code == 404:
                    raise EmbeddingProviderError(
                        f"Model '{model}' not found. Try: ollama pull {model}",
                        provider="ollama",
                    )
                if response.status_code >= 500:
                    raise EmbeddingUnavailableError(
                        "Ollama service unavailable",
                        provider="ollama",
                    )
                if response.status_code != 200:
                    raise EmbeddingProviderError(
                        f"Ollama API error: {response.status_code} - {response.text[:200]}",
                        provider="ollama",
                    )

                data = response.json()
                embedding = data.get("embedding", [])
                embeddings.append(embedding)

                # Estimate tokens (Ollama doesn't return token count for embeddings)
                total_prompt_tokens += len(text) // 4  # Rough estimate

            except httpx.RequestError as e:
                raise EmbeddingUnavailableError(
                    f"Request failed: {e}. Is Ollama running? (ollama serve)",
                    provider="ollama",
                    cause=e,
                ) from e

        latency_ms = (time.time() - start_time) * 1000

        return EmbeddingResponse(
            embeddings=embeddings,
            model=model,
            usage={
                "prompt_tokens": total_prompt_tokens,
                "total_tokens": total_prompt_tokens,
            },
            latency_ms=latency_ms,
        )

    async def list_models(self) -> list[str]:
        """List available Ollama embedding models."""
        client = await self._get_client()

        try:
            response = await client.get("/api/tags")
            if response.status_code == 200:
                data = response.json()
                # Filter for embedding models (typically have "embed" in name)
                all_models = [m.get("name", "") for m in data.get("models", [])]
                embedding_models = [
                    m
                    for m in all_models
                    if "embed" in m.lower() or m in ["nomic-embed-text", "mxbai-embed-large"]
                ]
                return embedding_models if embedding_models else all_models
        except Exception as e:
            logger.warning("Failed to list Ollama models", error=str(e))

        # Return common embedding models as fallback
        return [
            "nomic-embed-text",
            "mxbai-embed-large",
            "all-minilm",
        ]

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Cleanup HTTP client."""
        if self._client and not self._client.is_closed:
            await self._client.aclose()


# Import at module level for type annotation
from heretek_swarm.infrastructure.otel import InstrumentedAsyncClient
