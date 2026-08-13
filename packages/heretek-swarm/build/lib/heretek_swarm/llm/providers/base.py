"""
LLM Provider Base Class

Abstract base class for all LLM providers in Heretek Swarm.
Defines the interface that all providers must implement.
"""

from __future__ import annotations

import time
from abc import ABC, abstractmethod
from collections.abc import AsyncIterator, Callable
from dataclasses import dataclass, field
from typing import Any

import structlog

logger = structlog.get_logger("llm.providers.base")

# Type alias for streaming callback
StreamingCallback = Callable[[str], None]


@dataclass
class Message:
    """A chat message for LLM interaction."""

    role: str  # "system", "user", "assistant", "tool"
    content: str
    name: str | None = None
    tool_calls: list[dict[str, Any]] | None = None
    tool_call_id: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert message to dictionary."""
        result = {"role": self.role, "content": self.content}
        if self.name:
            result["name"] = self.name
        if self.tool_calls:
            result["tool_calls"] = self.tool_calls
        if self.tool_call_id:
            result["tool_call_id"] = self.tool_call_id
        return result


@dataclass
class LLMRequest:
    """Request parameters for LLM completion."""

    messages: list[Message]
    model: str | None = None
    temperature: float = 0.7
    max_tokens: int | None = None
    top_p: float = 1.0
    frequency_penalty: float = 0.0
    presence_penalty: float = 0.0
    stop: list[str] | None = None
    stream: bool = False
    n: int = 1
    tools: list[dict[str, Any]] | None = None
    tool_choice: str | dict[str, Any] | None = None
    response_format: dict[str, Any] | None = None
    seed: int | None = None
    extra_body: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert request to dictionary for API calls."""
        result = {
            "messages": [m.to_dict() for m in self.messages],
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
            "top_p": self.top_p,
            "frequency_penalty": self.frequency_penalty,
            "presence_penalty": self.presence_penalty,
            "stream": self.stream,
            "n": self.n,
        }

        if self.model:
            result["model"] = self.model
        if self.stop:
            result["stop"] = self.stop
        if self.tools:
            result["tools"] = self.tools
        if self.tool_choice:
            result["tool_choice"] = self.tool_choice
        if self.response_format:
            result["response_format"] = self.response_format
        if self.seed is not None:
            result["seed"] = self.seed
        if self.extra_body:
            result.update(self.extra_body)

        return result


@dataclass
class ToolCall:
    """A tool call from the LLM."""

    id: str
    name: str
    arguments: dict[str, Any]


@dataclass
class LLMResponse:
    """Response from an LLM completion."""

    content: str
    model: str
    usage: dict[str, int] = field(default_factory=dict)
    finish_reason: str | None = None
    tool_calls: list[ToolCall] = field(default_factory=list)
    raw_response: dict[str, Any] | None = None
    latency_ms: float = 0.0

    @property
    def prompt_tokens(self) -> int:
        """Get the number of prompt tokens used."""
        return self.usage.get("prompt_tokens", 0)

    @property
    def completion_tokens(self) -> int:
        """Get the number of completion tokens used."""
        return self.usage.get("completion_tokens", 0)

    @property
    def total_tokens(self) -> int:
        """Get the total tokens used."""
        return self.usage.get("total_tokens", 0)


@dataclass
class ProviderCapabilities:
    """Capabilities of an LLM provider."""

    supports_streaming: bool = True
    supports_function_calling: bool = False
    supports_vision: bool = False
    supports_json_mode: bool = False
    max_context_length: int | None = None
    max_output_tokens: int | None = None
    default_temperature: float = 0.7
    temperature_range: tuple = (0.0, 2.0)


class LLMProviderBase(ABC):
    """
    Abstract base class for all LLM providers.

    All provider implementations must inherit from this class and implement
    the required abstract methods.

    Example usage:
        provider = OpenAIProvider(api_key="sk-...", base_url="...")
        response = await provider.complete(messages=[...])

        async for chunk in provider.stream(messages=[...]):
            print(chunk, end="")
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
        Initialize the LLM provider.

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
            "LLM provider initialized",
            provider_name=provider_name,
            base_url=base_url,
            has_api_key=api_key is not None,
        )

    @abstractmethod
    def _init_capabilities(self) -> ProviderCapabilities:
        """Initialize provider capabilities. Must be implemented by subclasses."""

    @property
    def capabilities(self) -> ProviderCapabilities:
        """Get the provider's capabilities."""
        return self._capabilities

    @abstractmethod
    async def complete(self, request: LLMRequest) -> LLMResponse:
        """
        Complete a chat request non-streaming.

        Args:
            request: The LLM request parameters

        Returns:
            The LLM response

        Raises:
            ProviderError: If the request fails
        """

    @abstractmethod
    async def stream(
        self,
        request: LLMRequest,
    ) -> AsyncIterator[str]:
        """
        Stream a chat completion.

        Args:
            request: The LLM request parameters with stream=True

        Yields:
            Chunks of the completion text

        Raises:
            ProviderError: If the request fails
        """

    async def complete_with_retry(
        self,
        request: LLMRequest,
        max_retries: int = 3,
        retry_delay: float = 1.0,
    ) -> LLMResponse:
        """
        Complete a request with automatic retries.

        Args:
            request: The LLM request parameters
            max_retries: Maximum number of retry attempts
            retry_delay: Delay between retries in seconds

        Returns:
            The LLM response

        Raises:
            ProviderError: If all retries fail
        """
        last_error = None

        for attempt in range(max_retries):
            try:
                return await self.complete(request)
            except Exception as e:
                last_error = e
                if attempt < max_retries - 1:
                    logger.warning(
                        "LLM request failed, retrying",
                        provider=self.provider_name,
                        attempt=attempt + 1,
                        max_retries=max_retries,
                        error=str(e),
                    )
                    await asyncio.sleep(retry_delay * (attempt + 1))

        raise ProviderError(
            f"Failed after {max_retries} attempts",
            provider=self.provider_name,
            cause=last_error,
        )

    async def test_connectivity(self, model: str | None = None) -> ConnectivityTestResult:
        """
        Test connectivity to the provider.

        Args:
            model: Optional model to test with

        Returns:
            Connectivity test result
        """
        start_time = time.time()

        try:
            test_request = LLMRequest(
                messages=[Message(role="user", content="Hello, this is a connectivity test.")],
                model=model or self.default_model,
                max_tokens=10,
            )

            response = await self.complete(test_request)
            latency_ms = (time.time() - start_time) * 1000

            return ConnectivityTestResult(
                success=True,
                provider_name=self.provider_name,
                model_used=response.model,
                response_text=response.content,
                latency_ms=latency_ms,
            )

        except Exception as e:
            latency_ms = (time.time() - start_time) * 1000
            return ConnectivityTestResult(
                success=False,
                provider_name=self.provider_name,
                model_used=model or self.default_model,
                latency_ms=latency_ms,
                error=str(e),
            )

    async def list_models(self) -> list[str]:
        """
        List available models for this provider.

        Returns:
            List of model names
        """
        if self.config.available_models:
            return self.config.available_models
        if self.config.default_model:
            return [self.config.default_model]
        return []

    def _get_model(self, model: str | None) -> str:
        """Get the model to use, falling back to default if needed."""
        if model:
            return model
        if self.default_model:
            return self.default_model
        raise ValueError("No model specified and no default model configured")

    async def __aenter__(self):
        """Async context manager entry."""
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):  # noqa: B027
        """Async context manager exit."""


@dataclass
class ConnectivityTestResult:
    """Result of a connectivity test."""

    success: bool
    provider_name: str
    model_used: str | None
    latency_ms: float
    response_text: str | None = None
    error: str | None = None


class ProviderError(Exception):
    """Exception raised for provider-related errors."""

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


class ProviderConfigurationError(ProviderError):
    """Exception raised for configuration errors."""


class ProviderAuthenticationError(ProviderError):
    """Exception raised for authentication errors."""


class ProviderRateLimitError(ProviderError):
    """Exception raised when rate limited."""

    def __init__(
        self,
        message: str,
        provider: str | None = None,
        retry_after: float | None = None,
    ):
        self.retry_after = retry_after
        super().__init__(message, provider)


class ProviderUnavailableError(ProviderError):
    """Exception raised when provider is unavailable."""


# Import asyncio for retry logic
import asyncio  # noqa: E402
