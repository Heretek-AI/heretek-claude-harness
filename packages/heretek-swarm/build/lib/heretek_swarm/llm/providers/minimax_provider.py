"""
MiniMax LLM Provider

Implementation of the LLM provider interface for MiniMax (abab models).
MiniMax provides Chinese language models including abab6.5, abab5.5.

Reference: https://api.minimax.chat/document/guides/chat-pro
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
)

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

logger = structlog.get_logger("llm.providers.minimax")


class MiniMaxProvider(LLMProviderBase):
    """
    MiniMax LLM Provider implementation.

    Supports:
    - abab6.5, abab6.5s, abab5.5
    - Streaming completions
    - Function calling
    - Chinese and English languages

    Example:
        provider = MiniMaxProvider(
            api_key="your_api_key",
            group_id="your_group_id",
            default_model="abab6.5"
        )
    """

    def __init__(
        self,
        api_key: str,
        group_id: str,
        base_url: str = "https://api.minimax.chat/v1",
        default_model: str | None = None,
        extra_config: dict[str, Any] | None = None,
    ):
        """
        Initialize the MiniMax provider.

        Args:
            api_key: MiniMax API key
            group_id: MiniMax group ID (required for authentication)
            base_url: Base URL (default: https://api.minimax.chat/v1)
            default_model: Default model to use
            extra_config: Additional configuration
        """
        if not api_key:
            raise ProviderAuthenticationError("MiniMax API key is required")
        if not group_id:
            raise ProviderAuthenticationError("MiniMax group_id is required")

        super().__init__(
            provider_name="minimax",
            base_url=base_url,
            api_key=api_key,
            default_model=default_model or "abab6.5",
            extra_config=extra_config,
        )

        self.group_id = group_id
        self._client: InstrumentedAsyncClient | None = None

    def _init_capabilities(self) -> ProviderCapabilities:
        """Initialize provider capabilities."""
        return ProviderCapabilities(
            supports_streaming=True,
            supports_function_calling=True,
            supports_vision=False,
            supports_json_mode=False,
            max_context_length=245760,  # abab6.5 supports up to 245K tokens
            max_output_tokens=16384,
            default_temperature=0.7,
            temperature_range=(0.0, 1.0),
        )

    async def _get_client(self) -> InstrumentedAsyncClient:
        """Get or create the instrumented HTTP client."""
        if self._client is None or self._client.is_closed:
            headers = {
                "Content-Type": "application/json",
            }

            base_client = httpx.AsyncClient(
                base_url=self.base_url,
                headers=headers,
                timeout=httpx.Timeout(60.0, connect=10.0),
                params={
                    "api_key": self.api_key,
                    "group_id": self.group_id,
                },
            )
            self._client = instrumented_httpx_client(client=base_client, call_type="llm_minimax")
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

        # Convert messages to MiniMax format
        messages = []
        for msg in request.messages:
            messages.append(  # noqa: PERF401
                {
                    "sender_type": msg.role,
                    "text": msg.content,
                }
            )

        # Build MiniMax-specific payload
        payload = {
            "model": model,
            "messages": messages,
            "temperature": request.temperature,
            "top_p": request.top_p,
            "stream": False,
        }

        if request.max_tokens:
            payload["tokens_to_generate"] = request.max_tokens

        if request.stop:
            payload["stop"] = request.stop

        # Add any extra parameters
        if request.extra_body:
            payload.update(request.extra_body)

        logger.debug(
            "Sending MiniMax completion request",
            model=model,
            message_count=len(messages),
        )

        try:
            response = await client.post(
                "/chat/completions",
                json=payload,
            )

            if response.status_code == 401:
                raise ProviderAuthenticationError(
                    "Invalid MiniMax API key or group_id",
                    provider="minimax",
                )
            if response.status_code >= 500:
                raise ProviderUnavailableError(
                    "MiniMax service unavailable",
                    provider="minimax",
                )
            if response.status_code != 200:
                error_data = (
                    response.json()
                    if response.headers.get("content-type", "").startswith("application/json")
                    else {"text": response.text}
                )
                raise ProviderError(
                    f"MiniMax API error: {response.status_code} - {error_data}",
                    provider="minimax",
                )

            data = response.json()
            latency_ms = (time.time() - start_time) * 1000

            # MiniMax response format
            choices = data.get("choices", [])
            if not choices:
                raise ProviderError(
                    "No choices in MiniMax response",
                    provider="minimax",
                )

            choice = choices[0]
            message_data = choice.get("message", {})

            return LLMResponse(
                content=message_data.get("text", ""),
                model=data.get("model", model),
                usage=data.get("usage", {}),
                finish_reason=choice.get("finish_reason"),
                raw_response=data,
                latency_ms=latency_ms,
            )

        except httpx.RequestError as e:
            raise ProviderUnavailableError(
                f"Request failed: {e}",
                provider="minimax",
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

        # Convert messages to MiniMax format
        messages = []
        for msg in request.messages:
            messages.append(  # noqa: PERF401
                {
                    "sender_type": msg.role,
                    "text": msg.content,
                }
            )

        payload = {
            "model": model,
            "messages": messages,
            "temperature": request.temperature,
            "top_p": request.top_p,
            "stream": True,
        }

        if request.max_tokens:
            payload["tokens_to_generate"] = request.max_tokens

        logger.debug(
            "Sending MiniMax streaming request",
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
                        "Invalid MiniMax API key or group_id",
                        provider="minimax",
                    )
                elif response.status_code != 200:
                    raise ProviderError(
                        f"MiniMax API error: {response.status_code}",
                        provider="minimax",
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
                                content = delta.get("text", "")
                                if content:
                                    yield content
                        except json.JSONDecodeError:
                            continue

        except httpx.RequestError as e:
            raise ProviderUnavailableError(
                f"Stream request failed: {e}",
                provider="minimax",
                cause=e,
            ) from e

    async def list_models(self) -> list[str]:
        """List available MiniMax models."""
        return [
            "abab6.5",
            "abab6.5s",
            "abab5.5",
            "abab5.5s",
        ]

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Cleanup HTTP client."""
        if self._client and not self._client.is_closed:
            await self._client.aclose()


# Import at module level for type annotation
from heretek_swarm.infrastructure.otel import InstrumentedAsyncClient  # noqa: E402
