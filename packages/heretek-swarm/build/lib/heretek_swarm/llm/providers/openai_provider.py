"""
OpenAI LLM Provider

Implementation of the LLM provider interface for OpenAI's API.
Supports GPT-4, GPT-4 Turbo, GPT-3.5 Turbo, and other OpenAI models.
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
    ProviderAuthenticationError,
    ProviderCapabilities,
    ProviderError,
    ProviderRateLimitError,
    ProviderUnavailableError,
    ToolCall,
)

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

logger = structlog.get_logger("llm.providers.openai")


class OpenAIProvider(LLMProviderBase):
    """
    OpenAI LLM Provider implementation.

    Supports:
    - GPT-4, GPT-4 Turbo, GPT-4o
    - GPT-3.5 Turbo
    - Streaming completions
    - Function/tool calling
    - Vision (with GPT-4 Vision)
    - JSON mode

    Example:
        provider = OpenAIProvider(
            api_key="sk-...",
            default_model="gpt-4o"
        )
        response = await provider.complete(messages=[...])
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
        Initialize the OpenAI provider.

        Args:
            api_key: OpenAI API key
            base_url: Base URL (default: https://api.openai.com/v1)
            default_model: Default model to use
            organization: OpenAI organization ID (optional)
            extra_config: Additional configuration
        """
        if not api_key:
            raise ProviderAuthenticationError("OpenAI API key is required")

        super().__init__(
            provider_name="openai",
            base_url=base_url,
            api_key=api_key,
            default_model=default_model or "gpt-4o",
            extra_config=extra_config,
        )

        self.organization = organization
        self._client: InstrumentedAsyncClient | None = None

    def _init_capabilities(self) -> ProviderCapabilities:
        """Initialize provider capabilities."""
        return ProviderCapabilities(
            supports_streaming=True,
            supports_function_calling=True,
            supports_vision=True,
            supports_json_mode=True,
            max_context_length=128000,  # GPT-4 Turbo
            max_output_tokens=4096,
            default_temperature=0.7,
            temperature_range=(0.0, 2.0),
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
            self._client = instrumented_httpx_client(client=base_client, call_type="llm_openai")
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

        payload = request.to_dict()
        model = self._get_model(request.model)
        payload["model"] = model

        logger.debug(
            "Sending OpenAI completion request",
            model=model,
            stream=False,
            message_count=len(request.messages),
        )

        try:
            response = await client.post(
                "/chat/completions",
                json=payload,
            )

            if response.status_code == 401:
                raise ProviderAuthenticationError(
                    "Invalid OpenAI API key",
                    provider="openai",
                )
            if response.status_code == 429:
                retry_after = response.headers.get("Retry-After")
                raise ProviderRateLimitError(
                    "Rate limited by OpenAI",
                    provider="openai",
                    retry_after=float(retry_after) if retry_after else None,
                )
            if response.status_code >= 500:
                raise ProviderUnavailableError(
                    "OpenAI service unavailable",
                    provider="openai",
                )
            if response.status_code != 200:
                raise ProviderError(
                    f"OpenAI API error: {response.status_code}",
                    provider="openai",
                )

            data = response.json()
            latency_ms = (time.time() - start_time) * 1000

            choice = data["choices"][0]
            message_data = choice.get("message", {})

            # Parse tool calls if present
            tool_calls = []
            if "tool_calls" in message_data:
                for tc in message_data["tool_calls"]:
                    tool_calls.append(  # noqa: PERF401
                        ToolCall(
                            id=tc["id"],
                            name=tc["function"]["name"],
                            arguments=json.loads(tc["function"]["arguments"]),
                        )
                    )

            return LLMResponse(
                content=message_data.get("content", ""),
                model=data.get("model", model),
                usage=data.get("usage", {}),
                finish_reason=choice.get("finish_reason"),
                tool_calls=tool_calls,
                raw_response=data,
                latency_ms=latency_ms,
            )

        except httpx.RequestError as e:
            raise ProviderUnavailableError(
                f"Request failed: {e}",
                provider="openai",
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

        payload = request.to_dict()
        payload["stream"] = True
        model = self._get_model(request.model)
        payload["model"] = model

        logger.debug(
            "Sending OpenAI streaming request",
            model=model,
            stream=True,
        )

        try:
            async with client.stream(
                "POST",
                "/chat/completions",
                json=payload,
            ) as response:
                if response.status_code == 401:
                    raise ProviderAuthenticationError(
                        "Invalid OpenAI API key",
                        provider="openai",
                    )
                elif response.status_code == 429:
                    raise ProviderRateLimitError(
                        "Rate limited by OpenAI",
                        provider="openai",
                    )
                elif response.status_code != 200:
                    raise ProviderError(
                        f"OpenAI API error: {response.status_code}",
                        provider="openai",
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
                provider="openai",
                cause=e,
            ) from e

    async def list_models(self) -> list[str]:
        """List available OpenAI models."""
        client = await self._get_client()

        try:
            response = await client.get("/models")
            if response.status_code == 200:
                data = response.json()
                return [m["id"] for m in data.get("data", [])]
        except Exception as e:
            logger.warning("Failed to list OpenAI models", error=str(e))

        # Return common models as fallback
        return [
            "gpt-4o",
            "gpt-4-turbo",
            "gpt-4",
            "gpt-3.5-turbo",
        ]

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Cleanup HTTP client."""
        if self._client and not self._client.is_closed:
            await self._client.aclose()


# Import at module level for type annotation
from heretek_swarm.infrastructure.otel import InstrumentedAsyncClient  # noqa: E402
