"""
lemonade-server LLM Provider

Implementation of the LLM provider interface for lemonade-server.
lemonade-server is a lightweight LLM inference server.

Reference: https://github.com/lemonade-sdk/lemonade
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

logger = structlog.get_logger("llm.providers.lemonade")


class LemonadeProvider(LLMProviderBase):
    """
    lemonade-server LLM Provider implementation.

    Supports:
    - Local LLM inference
    - Streaming completions
    - Various model backends

    Example:
        provider = LemonadeProvider(
            base_url="http://localhost:5000",
            default_model="meta-llama/Llama-2-7b-chat-hf"
        )
    """

    def __init__(
        self,
        base_url: str = "http://localhost:5000",
        default_model: str | None = None,
        extra_config: dict[str, Any] | None = None,
    ):
        """
        Initialize the lemonade-server provider.

        Args:
            base_url: lemonade-server URL (default: http://localhost:5000)
            default_model: Default model to use
            extra_config: Additional configuration
        """
        super().__init__(
            provider_name="lemonade",
            base_url=base_url,
            api_key=None,  # lemonade-server typically doesn't require authentication
            default_model=default_model,
            extra_config=extra_config,
        )

        self._client: InstrumentedAsyncClient | None = None

    def _init_capabilities(self) -> ProviderCapabilities:
        """Initialize provider capabilities."""
        return ProviderCapabilities(
            supports_streaming=self.extra_config.get("supports_streaming", True),
            supports_function_calling=self.extra_config.get("supports_function_calling", False),
            supports_vision=False,
            supports_json_mode=False,
            max_context_length=self.extra_config.get("max_context_length", 4096),
            max_output_tokens=self.extra_config.get("max_output_tokens", 1024),
            default_temperature=0.7,
            temperature_range=(0.0, 2.0),
        )

    async def _get_client(self) -> InstrumentedAsyncClient:
        """Get or create the instrumented HTTP client."""
        if self._client is None or self._client.is_closed:
            base_client = httpx.AsyncClient(
                base_url=self.base_url,
                headers={"Content-Type": "application/json"},
                timeout=httpx.Timeout(60.0, connect=10.0),
            )
            self._client = instrumented_httpx_client(client=base_client, call_type="llm_lemonade")
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

        # Convert messages to lemonade format
        # lemonade-server typically uses OpenAI-compatible format
        messages = [msg.to_dict() for msg in request.messages]

        # Build payload
        payload = {
            "model": model,
            "messages": messages,
            "temperature": request.temperature,
            "top_p": request.top_p,
            "max_tokens": request.max_tokens,
            "stream": False,
        }

        if request.stop:
            payload["stop"] = request.stop

        # Add any extra parameters
        if request.extra_body:
            payload.update(request.extra_body)

        logger.debug(
            "Sending lemonade-server completion request",
            model=model,
            message_count=len(messages),
        )

        try:
            response = await client.post(
                "/v1/chat/completions",
                json=payload,
            )

            if response.status_code >= 500:
                raise ProviderUnavailableError(
                    "lemonade-server service unavailable",
                    provider="lemonade",
                )
            if response.status_code != 200:
                error_text = (
                    response.text[:200]
                    if response.headers.get("content-type", "").startswith("text")
                    else response.json()
                )
                raise ProviderError(
                    f"lemonade-server API error: {response.status_code} - {error_text}",
                    provider="lemonade",
                )

            data = response.json()
            latency_ms = (time.time() - start_time) * 1000

            choice = data.get("choices", [{}])[0]
            message_data = choice.get("message", {})

            return LLMResponse(
                content=message_data.get("content", ""),
                model=data.get("model", model),
                usage=data.get("usage", {}),
                finish_reason=choice.get("finish_reason"),
                raw_response=data,
                latency_ms=latency_ms,
            )

        except httpx.RequestError as e:
            raise ProviderUnavailableError(
                f"Request failed: {e}. Is lemonade-server running?",
                provider="lemonade",
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

        messages = [msg.to_dict() for msg in request.messages]

        payload = {
            "model": model,
            "messages": messages,
            "temperature": request.temperature,
            "top_p": request.top_p,
            "max_tokens": request.max_tokens,
            "stream": True,
        }

        if request.stop:
            payload["stop"] = request.stop

        logger.debug(
            "Sending lemonade-server streaming request",
            model=model,
        )

        try:
            async with client.stream(
                "POST",
                "/v1/chat/completions",
                json=payload,
            ) as response:
                if response.status_code != 200:
                    raise ProviderError(
                        f"lemonade-server API error: {response.status_code}",
                        provider="lemonade",
                    )

                async for line in response.aiter_lines():
                    if line.startswith("data: "):
                        data = line[6:]  # Remove "data: " prefix

                        if data.strip() == "[DONE]":
                            break

                        try:
                            chunk = json.loads(data)
                            choices = chunk.get("choices", [])
                            if choices:
                                delta = choices[0].get("delta", {})
                                content = delta.get("content", "")
                                if content:
                                    yield content
                        except json.JSONDecodeError:
                            continue

        except httpx.RequestError as e:
            raise ProviderUnavailableError(
                f"Stream request failed: {e}",
                provider="lemonade",
                cause=e,
            ) from e

    async def list_models(self) -> list[str]:
        """List available models from lemonade-server."""
        client = await self._get_client()

        try:
            response = await client.get("/v1/models")
            if response.status_code == 200:
                data = response.json()
                return [m.get("id", m.get("name", "")) for m in data.get("data", [])]
        except Exception as e:
            logger.warning("Failed to list lemonade-server models", error=str(e))

        if self.default_model:
            return [self.default_model]
        return []

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Cleanup HTTP client."""
        if self._client and not self._client.is_closed:
            await self._client.aclose()


# Import at module level for type annotation
from heretek_swarm.infrastructure.otel import InstrumentedAsyncClient  # noqa: E402
