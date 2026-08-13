"""
Z.AI (Zhipu AI) LLM Provider

Implementation of the LLM provider interface for Zhipu AI's GLM models.
Z.AI provides Chinese and English language models including GLM-4, GLM-3-Turbo.

Reference: https://open.bigmodel.cn/dev/api
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
    ProviderUnavailableError,
    ToolCall,
)

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

logger = structlog.get_logger("llm.providers.zai")


class ZAIProvider(LLMProviderBase):
    """
    Z.AI (Zhipu AI) LLM Provider implementation.

    Supports:
    - GLM-4, GLM-4-Flash, GLM-4-Air
    - GLM-3-Turbo
    - Streaming completions
    - Function calling
    - Chinese and English languages

    Example:
        provider = ZAIProvider(
            api_key="your_api_key",
            default_model="glm-4"
        )
    """

    def __init__(
        self,
        api_key: str,
        base_url: str = "https://open.bigmodel.cn/api/paas/v4",
        default_model: str | None = None,
        extra_config: dict[str, Any] | None = None,
    ):
        """
        Initialize the Z.AI provider.

        Args:
            api_key: Zhipu AI API key
            base_url: Base URL (default: https://open.bigmodel.cn/api/paas/v4)
            default_model: Default model to use
            extra_config: Additional configuration
        """
        if not api_key:
            raise ProviderAuthenticationError("Z.AI API key is required")

        super().__init__(
            provider_name="zai",
            base_url=base_url,
            api_key=api_key,
            default_model=default_model or "glm-4",
            extra_config=extra_config,
        )

        self._client: InstrumentedAsyncClient | None = None

    def _init_capabilities(self) -> ProviderCapabilities:
        """Initialize provider capabilities."""
        return ProviderCapabilities(
            supports_streaming=True,
            supports_function_calling=True,
            supports_vision=True,  # GLM-4V supports vision
            supports_json_mode=False,
            max_context_length=128000,  # GLM-4 supports up to 128K
            max_output_tokens=4096,
            default_temperature=0.7,
            temperature_range=(0.0, 1.0),  # Z.AI uses 0-1 range
        )

    async def _get_client(self) -> InstrumentedAsyncClient:
        """Get or create the instrumented HTTP client."""
        if self._client is None or self._client.is_closed:
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            }

            base_client = httpx.AsyncClient(
                base_url=self.base_url,
                headers=headers,
                timeout=httpx.Timeout(60.0, connect=10.0),
            )
            self._client = instrumented_httpx_client(client=base_client, call_type="llm_zai")
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

        # Z.AI specific adjustments
        # Ensure temperature is within valid range (0-1)
        if payload.get("temperature", 0.7) > 1.0:
            payload["temperature"] = payload["temperature"] / 2.0

        logger.debug(
            "Sending Z.AI completion request",
            model=model,
            stream=False,
        )

        try:
            response = await client.post(
                "/chat/completions",
                json=payload,
            )

            if response.status_code == 401:
                raise ProviderAuthenticationError(
                    "Invalid Z.AI API key",
                    provider="zai",
                )
            if response.status_code == 429:
                raise ProviderError(
                    "Rate limited by Z.AI",
                    provider="zai",
                )
            if response.status_code >= 500:
                raise ProviderUnavailableError(
                    "Z.AI service unavailable",
                    provider="zai",
                )
            if response.status_code != 200:
                error_data = (
                    response.json()
                    if response.headers.get("content-type", "").startswith("application/json")
                    else {"text": response.text}
                )
                raise ProviderError(
                    f"Z.AI API error: {response.status_code} - {error_data}",
                    provider="zai",
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
                provider="zai",
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

        # Ensure temperature is within valid range
        if payload.get("temperature", 0.7) > 1.0:
            payload["temperature"] = payload["temperature"] / 2.0

        logger.debug(
            "Sending Z.AI streaming request",
            model=model,
        )

        try:
            async with client.stream(
                "POST",
                "/chat/completions",
                json=payload,
            ) as response:
                if response.status_code == 401:
                    raise ProviderAuthenticationError(
                        "Invalid Z.AI API key",
                        provider="zai",
                    )
                elif response.status_code != 200:
                    raise ProviderError(
                        f"Z.AI API error: {response.status_code}",
                        provider="zai",
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
                provider="zai",
                cause=e,
            ) from e

    async def list_models(self) -> list[str]:
        """List available Z.AI models."""
        # Common Z.AI models
        return [
            "glm-4",
            "glm-4-flash",
            "glm-4-air",
            "glm-4-airx",
            "glm-4-long",
            "glm-3-turbo",
            "glm-4v",  # Vision model
        ]

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Cleanup HTTP client."""
        if self._client and not self._client.is_closed:
            await self._client.aclose()


# Import at module level for type annotation
from heretek_swarm.infrastructure.otel import InstrumentedAsyncClient  # noqa: E402
