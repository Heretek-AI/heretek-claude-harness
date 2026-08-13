"""
Ollama LLM Provider

Implementation of the LLM provider interface for Ollama.
Supports local LLM inference with models like Llama 2, Mistral, etc.

Reference: https://github.com/ollama/ollama/blob/main/docs/api.md
"""

from __future__ import annotations

import json
import time
from typing import TYPE_CHECKING, Any

import httpx
import structlog

from heretek_swarm.infrastructure.otel import instrumented_httpx_client

from .base import (
    LLMProviderBase,
    LLMRequest,
    LLMResponse,
    ProviderCapabilities,
    ProviderError,
    ProviderUnavailableError,
)

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

logger = structlog.get_logger("llm.providers.ollama")


class OllamaProvider(LLMProviderBase):
    """
    Ollama LLM Provider implementation.

    Supports:
    - Local LLM inference
    - Streaming completions
    - Various models (Llama 2, Mistral, Phi, etc.)
    - Model pulling and listing

    Example:
        provider = OllamaProvider(
            base_url="http://localhost:11434",
            default_model="llama2"
        )
    """

    def __init__(
        self,
        base_url: str = "http://localhost:11434",
        default_model: str | None = None,
        extra_config: dict[str, Any] | None = None,
    ):
        """
        Initialize the Ollama provider.

        Args:
            base_url: Ollama server URL (default: http://localhost:11434)
            default_model: Default model to use
            extra_config: Additional configuration
        """
        super().__init__(
            provider_name="ollama",
            base_url=base_url,
            api_key=None,  # Ollama doesn't require authentication
            default_model=default_model or "llama2",
            extra_config=extra_config,
        )

        self._client: InstrumentedAsyncClient | None = None

    def _init_capabilities(self) -> ProviderCapabilities:
        """Initialize provider capabilities."""
        return ProviderCapabilities(
            supports_streaming=True,
            supports_function_calling=False,  # Ollama has limited tool support
            supports_vision=False,
            supports_json_mode=True,
            max_context_length=self.extra_config.get("max_context_length", 4096),
            max_output_tokens=self.extra_config.get("max_output_tokens", 2048),
            default_temperature=0.7,
            temperature_range=(0.0, 2.0),
        )

    async def _get_client(self) -> InstrumentedAsyncClient:
        """Get or create the instrumented HTTP client."""
        if self._client is None or self._client.is_closed:
            base_client = httpx.AsyncClient(
                base_url=self.base_url,
                headers={"Content-Type": "application/json"},
                timeout=httpx.Timeout(120.0, connect=10.0),
            )
            self._client = instrumented_httpx_client(client=base_client, call_type="llm_ollama")
        return self._client

    async def complete(self, request: LLMRequest) -> LLMResponse:
        """
        Complete a chat request non-streaming.

        Args:
            request: The LLM request parameters

        Returns:
            The LLM response
        """
        client = await self._get_client()
        start_time = time.time()

        model = self._get_model(request.model)

        # Convert messages to Ollama format
        messages = []
        for msg in request.messages:
            messages.append(  # noqa: PERF401
                {
                    "role": msg.role,
                    "content": msg.content,
                }
            )

        # Build Ollama-specific payload
        payload = {
            "model": model,
            "messages": messages,
            "stream": False,
            "options": {
                "temperature": request.temperature,
                "top_p": request.top_p,
            },
        }

        if request.max_tokens:
            payload["options"]["num_predict"] = request.max_tokens

        if request.stop:
            payload["options"]["stop"] = request.stop

        # Add any extra options
        if request.extra_body:
            payload["options"].update(request.extra_body)

        logger.debug(
            "Sending Ollama completion request",
            model=model,
            message_count=len(messages),
        )

        try:
            response = await client.post(
                "/api/chat",
                json=payload,
            )

            if response.status_code == 404:
                raise ProviderError(
                    f"Model '{model}' not found. Try: ollama pull {model}",
                    provider="ollama",
                )
            if response.status_code >= 500:
                raise ProviderUnavailableError(
                    "Ollama service unavailable",
                    provider="ollama",
                )
            if response.status_code != 200:
                raise ProviderError(
                    f"Ollama API error: {response.status_code} - {response.text[:200]}",
                    provider="ollama",
                )

            data = response.json()
            latency_ms = (time.time() - start_time) * 1000

            message_data = data.get("message", {})

            # Calculate approximate token usage
            prompt_tokens = self._estimate_tokens(messages)
            completion_tokens = self._estimate_tokens(
                [{"content": message_data.get("content", "")}]
            )

            return LLMResponse(
                content=message_data.get("content", ""),
                model=model,
                usage={
                    "prompt_tokens": prompt_tokens,
                    "completion_tokens": completion_tokens,
                    "total_tokens": prompt_tokens + completion_tokens,
                },
                finish_reason="stop",
                raw_response=data,
                latency_ms=latency_ms,
            )

        except httpx.RequestError as e:
            raise ProviderUnavailableError(
                f"Request failed: {e}. Is Ollama running? (ollama serve)",
                provider="ollama",
                cause=e,
            ) from e

    async def stream(self, request: LLMRequest) -> AsyncIterator[str]:
        """
        Stream a chat completion.

        Args:
            request: The LLM request parameters with stream=True

        Yields:
            Chunks of the completion text
        """
        client = await self._get_client()

        model = self._get_model(request.model)

        # Convert messages to Ollama format
        messages = []
        for msg in request.messages:
            messages.append(  # noqa: PERF401
                {
                    "role": msg.role,
                    "content": msg.content,
                }
            )

        payload = {
            "model": model,
            "messages": messages,
            "stream": True,
            "options": {
                "temperature": request.temperature,
                "top_p": request.top_p,
            },
        }

        if request.max_tokens:
            payload["options"]["num_predict"] = request.max_tokens

        logger.debug(
            "Sending Ollama streaming request",
            model=model,
        )

        try:
            async with client.stream(
                "POST",
                "/api/chat",
                json=payload,
            ) as response:
                if response.status_code == 404:
                    raise ProviderError(
                        f"Model '{model}' not found",
                        provider="ollama",
                    )
                elif response.status_code != 200:
                    raise ProviderError(
                        f"Ollama API error: {response.status_code}",
                        provider="ollama",
                    )

                async for line in response.aiter_lines():
                    if not line.strip():
                        continue

                    try:
                        chunk = json.loads(line)
                        message_data = chunk.get("message", {})
                        content = message_data.get("content", "")
                        if content:
                            yield content
                    except json.JSONDecodeError:
                        continue

        except httpx.RequestError as e:
            raise ProviderUnavailableError(
                f"Stream request failed: {e}",
                provider="ollama",
                cause=e,
            ) from e

    async def list_models(self) -> list[str]:
        """List available Ollama models."""
        client = await self._get_client()

        try:
            response = await client.get("/api/tags")
            if response.status_code == 200:
                data = response.json()
                return [m.get("name", "") for m in data.get("models", [])]
        except Exception as e:
            logger.warning("Failed to list Ollama models", error=str(e))

        return []

    def _estimate_tokens(self, messages: list[dict[str, str]]) -> int:
        """Estimate token count from messages."""
        total_chars = sum(len(m.get("content", "")) for m in messages)
        # Rough estimate: 1 token ≈ 4 characters for English text
        return max(1, total_chars // 4)

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Cleanup HTTP client."""
        if self._client and not self._client.is_closed:
            await self._client.aclose()


# Import at module level for type annotation
from heretek_swarm.infrastructure.otel import InstrumentedAsyncClient  # noqa: E402
