"""  # noqa: INP001
Heretek Swarm - Model Garage

LiteLLM Integration for unified LLM API across all 23 agents.
Provides automatic routing, fallback, and load balancing across providers.

Supports:
- OpenAI (GPT-4, GPT-3.5, o1)
- Ollama (local models)
- MiniMax
- Z.AI (Zhipu)
- Anthropic (Claude)
- Google (Gemini)
- Groq
- Azure OpenAI
- Local llama.cpp

Configuration: ~/.heretek-swarm/config.json
"""

from __future__ import annotations

import asyncio
import json
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path
from typing import TYPE_CHECKING, Any

import httpx
import structlog

from heretek_swarm.infrastructure.otel import InstrumentedAsyncClient, instrumented_httpx_client

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

logger = structlog.get_logger("model_garage")

_DEFAULT_OPENAI_MODEL = "gpt-4o"
_DEFAULT_OLLAMA_MODEL = "llama3.1"
_DEFAULT_MINIMAX_MODEL = "abab6.5s"

# ============================================================================
# Configuration — canonical path from shared config module
# ============================================================================

_LOG_DIR = Path.home() / ".heretek-swarm" / "logs"

try:
    _LOG_DIR.mkdir(parents=True, exist_ok=True)
except PermissionError:
    # Container / restricted environment — use /tmp fallback
    import tempfile
    _LOG_DIR = Path(tempfile.gettempdir()) / ".heretek-swarm" / "logs"
    _LOG_DIR.mkdir(parents=True, exist_ok=True)

HEREKET_LOGS_DIR = _LOG_DIR

# Import shared config-path after module constants to avoid circular reference.
# This is always safe because config.__init__ only depends on its sub-modules.
import contextlib  # noqa: E402

from heretek_swarm.config import get_config_path  # noqa: E402


class ProviderType(StrEnum):
    """Supported LLM provider types."""

    OPENAI = "openai"
    OLLAMA = "ollama"
    MINIMAX = "minimax"
    ZAI = "zai"
    ANTHROPIC = "anthropic"
    GOOGLE = "google"
    GROQ = "groq"
    AZURE = "azure"
    LLAMACPP = "llamacpp"
    OPENAI_COMPATIBLE = "openai_compatible"


@dataclass
class ModelInfo:
    """Information about a model."""

    name: str
    provider: ProviderType
    max_tokens: int | None = None
    supports_streaming: bool = True
    supports_function_calling: bool = False
    supports_vision: bool = False
    context_length: int | None = None
    cost_per_1k_input: float | None = None
    cost_per_1k_output: float | None = None
    is_local: bool = False


@dataclass
class ProviderConfig:
    """Configuration for an LLM provider."""

    id: str
    name: str
    provider_type: ProviderType
    base_url: str
    api_key: str | None = None
    default_model: str | None = None
    available_models: list[str] = field(default_factory=list)
    is_enabled: bool = True
    is_default: bool = False
    priority: int = 100
    max_rpm: int | None = None
    max_tpm: int | None = None
    timeout: float = 60.0
    retry_count: int = 3
    retry_delay: float = 1.0
    health_status: str = "unknown"
    last_health_check: str | None = None
    error_message: str | None = None
    metadata: dict[str, str] = field(default_factory=dict)
    """Arbitrary metadata (e.g. group_id for MiniMax)."""

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "id": self.id,
            "name": self.name,
            "provider_type": self.provider_type.value,
            "base_url": self.base_url,
            "api_key": "***" if self.api_key else None,
            "default_model": self.default_model,
            "available_models": self.available_models,
            "is_enabled": self.is_enabled,
            "is_default": self.is_default,
            "priority": self.priority,
            "max_rpm": self.max_rpm,
            "max_tpm": self.max_tpm,
            "health_status": self.health_status,
        }


@dataclass
class ChatMessage:
    """A chat message."""

    role: str  # system, user, assistant
    content: str
    name: str | None = None
    tool_calls: list[dict[str, Any]] | None = None
    tool_call_id: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        result: dict[str, Any] = {"role": self.role, "content": self.content}
        if self.name:
            result["name"] = self.name
        if self.tool_calls:
            result["tool_calls"] = self.tool_calls
        if self.tool_call_id:
            result["tool_call_id"] = self.tool_call_id
        return result


@dataclass
class LLMRequest:
    """Request for LLM completion."""

    messages: list[ChatMessage]
    model: str | None = None
    temperature: float = 0.7
    max_tokens: int | None = None
    top_p: float = 1.0
    frequency_penalty: float = 0.0
    presence_penalty: float = 0.0
    stop: list[str] | None = None
    stream: bool = False
    tools: list[dict[str, Any]] | None = None
    tool_choice: str | dict[str, Any] | None = None
    response_format: dict[str, Any] | None = None
    seed: int | None = None
    extra_body: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        result: dict[str, Any] = {
            "messages": [m.to_dict() for m in self.messages],
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
            "top_p": self.top_p,
            "frequency_penalty": self.frequency_penalty,
            "presence_penalty": self.presence_penalty,
            "stream": self.stream,
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
class LLMResponse:
    """Response from LLM completion."""

    content: str
    model: str
    provider: ProviderType
    usage: dict[str, int] = field(default_factory=dict)
    finish_reason: str | None = None
    tool_calls: list[dict[str, Any]] = field(default_factory=list)
    raw_response: dict[str, Any] | None = None
    latency_ms: float = 0.0
    cost: float | None = None

    @property
    def prompt_tokens(self) -> int:
        return self.usage.get("prompt_tokens", 0)

    @property
    def completion_tokens(self) -> int:
        return self.usage.get("completion_tokens", 0)

    @property
    def total_tokens(self) -> int:
        return self.usage.get("total_tokens", 0)


# ============================================================================
# Base Provider Implementation
# ============================================================================


class LLMProvider(ABC):
    """Abstract base class for LLM providers."""

    def __init__(self, config: ProviderConfig):
        self.config = config
        self._client: InstrumentedAsyncClient | None = None
        self._rate_limiter = asyncio.Semaphore(10)
        self._last_request_time: float = 0

    @abstractmethod
    async def complete(self, request: LLMRequest) -> LLMResponse:
        """Complete a chat request."""

    @abstractmethod
    async def stream(self, request: LLMRequest) -> AsyncIterator[str]:
        """Stream chat completion tokens."""

    async def health_check(self) -> bool:
        """Check if the provider is healthy."""
        try:
            client = await self._get_client()
            response = await client.get("/")
            return response.status_code < 500
        except Exception as e:
            logger.debug("model_provider_health_check_failed", error=str(e))
            return False

    @staticmethod
    def _try_extract_chat_token(chunk: dict[str, Any]) -> str | None:
        """Extract a content delta token from an OpenAI-compatible chat chunk.

        Returns the token string or None.
        """
        choices: list[dict[str, Any]] = chunk.get("choices", [])
        if not choices:
            return None
        delta: dict[str, Any] = choices[0].get("delta", {})
        return delta.get("content") or None

    @staticmethod
    def _try_extract_anthropic_token(
        chunk: dict[str, Any], current_event: str | None
    ) -> str | None:
        """Extract a text delta token from an Anthropic SSE event chunk.

        Returns the token string or None.
        """
        if current_event in ("message_delta", "content_block_delta"):
            delta: dict[str, Any] = chunk.get("delta", {})
            return delta.get("text") or None
        return None

    async def close(self) -> None:
        """Close the provider."""
        if self._client:
            await self._client.aclose()
            self._client = None

    async def _get_client(self) -> InstrumentedAsyncClient:
        """Get or create the instrumented HTTP client."""
        if self._client is None or self._client.is_closed:
            headers: dict[str, str] = {"Content-Type": "application/json"}
            if self.config.api_key:
                headers["Authorization"] = f"Bearer {self.config.api_key}"

            base_client = httpx.AsyncClient(
                base_url=self.config.base_url.rstrip("/"),
                headers=headers,
                timeout=httpx.Timeout(self.config.timeout, connect=10.0),
            )
            self._client = instrumented_httpx_client(
                client=base_client,
                call_type=f"llm_{self.config.provider_type.value}",
            )
        return self._client

    async def _rate_limit(self) -> None:
        """Apply rate limiting."""
        if self.config.max_rpm:
            min_interval = 60.0 / self.config.max_rpm
            elapsed = time.time() - self._last_request_time
            if elapsed < min_interval:
                await asyncio.sleep(min_interval - elapsed)
        self._last_request_time = time.time()


# ============================================================================
# Provider Implementations
# ============================================================================


class OpenAIProvider(LLMProvider):
    """OpenAI API provider."""

    async def complete(self, request: LLMRequest) -> LLMResponse:
        await self._rate_limit()
        async with self._rate_limiter:
            client = await self._get_client()
            start_time = time.time()

            model = request.model or self.config.default_model or _DEFAULT_OPENAI_MODEL
            payload = request.to_dict()
            payload["model"] = model

            try:
                response = await client.post("/chat/completions", json=payload)
                response.raise_for_status()
                data = response.json()

                latency_ms = (time.time() - start_time) * 1000
                choice = data["choices"][0]
                message = choice.get("message", {})

                return LLMResponse(
                    content=message.get("content", ""),
                    model=data.get("model", model),
                    provider=ProviderType.OPENAI,
                    usage=data.get("usage", {}),
                    finish_reason=choice.get("finish_reason"),
                    tool_calls=message.get("tool_calls", []),
                    raw_response=data,
                    latency_ms=latency_ms,
                )
            except httpx.HTTPStatusError as e:
                logger.error(
                    "OpenAI API error", status=e.response.status_code, detail=e.response.text
                )
                raise
            except Exception as e:
                logger.error("OpenAI completion failed", error=str(e))
                raise

    async def stream(self, request: LLMRequest) -> AsyncIterator[str]:
        await self._rate_limit()
        async with self._rate_limiter:
            client = await self._get_client()
            model = request.model or self.config.default_model or _DEFAULT_OPENAI_MODEL
            payload = request.to_dict()
            payload["model"] = model
            payload["stream"] = True

            async with client.stream("POST", "/chat/completions", json=payload) as response:
                response.raise_for_status()
                async for line in response.aiter_lines():
                    if not line:
                        continue
                    try:
                        chunk = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    token = self._try_extract_chat_token(chunk)
                    if token:
                        yield token


class OllamaProvider(LLMProvider):
    """Ollama local API provider."""

    async def complete(self, request: LLMRequest) -> LLMResponse:
        await self._rate_limit()
        async with self._rate_limiter:
            client = await self._get_client()
            start_time = time.time()

            model = request.model or self.config.default_model or _DEFAULT_OLLAMA_MODEL
            payload = {
                "model": model,
                "messages": [m.to_dict() for m in request.messages],
                "stream": False,
                "options": {
                    "temperature": request.temperature,
                    "top_p": request.top_p,
                },
            }
            if request.max_tokens:
                payload["options"]["num_predict"] = request.max_tokens

            try:
                response = await client.post("/api/chat", json=payload)
                response.raise_for_status()
                data = response.json()

                latency_ms = (time.time() - start_time) * 1000
                message = data.get("message", {})

                return LLMResponse(
                    content=message.get("content", ""),
                    model=model,
                    provider=ProviderType.OLLAMA,
                    usage={"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
                    finish_reason=data.get("done_reason"),
                    raw_response=data,
                    latency_ms=latency_ms,
                    cost=0.0,
                )
            except Exception as e:
                logger.error("Ollama completion failed", error=str(e))
                raise

    async def stream(self, request: LLMRequest) -> AsyncIterator[str]:
        await self._rate_limit()
        async with self._rate_limiter:
            client = await self._get_client()
            model = request.model or self.config.default_model or _DEFAULT_OLLAMA_MODEL
            payload = {
                "model": model,
                "messages": [m.to_dict() for m in request.messages],
                "stream": True,
                "options": {"temperature": request.temperature},
            }

            async with client.stream("POST", "/api/chat", json=payload) as response:
                response.raise_for_status()
                async for line in response.aiter_lines():
                    if line:
                        try:
                            data = json.loads(line)
                            if "message" in data and "content" in data["message"]:
                                yield data["message"]["content"]
                            if data.get("done"):
                                break
                        except json.JSONDecodeError:
                            continue


class MiniMaxProvider(LLMProvider):
    """MiniMax API provider."""

    async def complete(self, request: LLMRequest) -> LLMResponse:
        await self._rate_limit()
        async with self._rate_limiter:
            client = await self._get_client()
            start_time = time.time()

            model = request.model or self.config.default_model or _DEFAULT_MINIMAX_MODEL
            payload = {
                "model": model,
                "messages": [m.to_dict() for m in request.messages],
                "temperature": request.temperature,
                "max_tokens": request.max_tokens or 2048,
            }
            if self.config.metadata.get("group_id"):
                payload["group_id"] = self.config.metadata["group_id"]

            try:
                response = await client.post("/text/chatcompletion_v2", json=payload)
                response.raise_for_status()
                data = response.json()

                latency_ms = (time.time() - start_time) * 1000
                choice = data["choices"][0]
                message = choice.get("message", {})

                return LLMResponse(
                    content=message.get("content", ""),
                    model=model,
                    provider=ProviderType.MINIMAX,
                    usage=data.get("usage", {}),
                    finish_reason=choice.get("finish_reason"),
                    raw_response=data,
                    latency_ms=latency_ms,
                )
            except Exception as e:
                logger.error("MiniMax completion failed", error=str(e))
                raise

    async def stream(self, request: LLMRequest) -> AsyncIterator[str]:
        """Stream chat completion tokens."""
        await self._rate_limit()
        async with self._rate_limiter:
            client = await self._get_client()
            model = request.model or self.config.default_model or _DEFAULT_MINIMAX_MODEL

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
            if self.config.metadata.get("group_id"):
                payload["group_id"] = self.config.metadata["group_id"]

            try:
                async with client.stream(
                    "POST", "/text/chatcompletion_v2", json=payload
                ) as response:
                    response.raise_for_status()
                    async for line in response.aiter_lines():
                        if line.startswith("data: "):
                            data = line[6:]
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
            except Exception as e:
                logger.error("MiniMax streaming failed", error=str(e))
                raise


class AnthropicProvider(LLMProvider):
    """Anthropic Claude API provider."""

    async def complete(self, request: LLMRequest) -> LLMResponse:
        await self._rate_limit()
        async with self._rate_limiter:
            client = await self._get_client()
            start_time = time.time()

            model = request.model or self.config.default_model or "claude-3-5-sonnet-20241022"

            anthropic_messages = []
            system_prompt = ""
            for msg in request.messages:
                if msg.role == "system":
                    system_prompt += msg.content + "\n"
                else:
                    anthropic_messages.append({"role": msg.role, "content": msg.content})

            payload: dict[str, Any] = {
                "model": model,
                "messages": anthropic_messages,
                "max_tokens": request.max_tokens or 4096,
                "temperature": request.temperature,
            }
            if system_prompt:
                payload["system"] = system_prompt

            try:
                response = await client.post("/v1/messages", json=payload)
                response.raise_for_status()
                data = response.json()

                latency_ms = (time.time() - start_time) * 1000

                content = data.get("content", [{"text": ""}])
                text = content[0].get("text", "") if content else ""

                return LLMResponse(
                    content=text,
                    model=model,
                    provider=ProviderType.ANTHROPIC,
                    usage=data.get("usage", {}),
                    finish_reason=data.get("stop_reason"),
                    raw_response=data,
                    latency_ms=latency_ms,
                )
            except Exception as e:
                logger.error("Anthropic completion failed", error=str(e))
                raise

    async def stream(self, request: LLMRequest) -> AsyncIterator[str]:
        """Stream chat completion tokens."""
        await self._rate_limit()
        async with self._rate_limiter:
            client = await self._get_client()
            model = request.model or self.config.default_model or "claude-3-5-sonnet-20241022"

            # Convert messages to Anthropic format
            anthropic_messages = []
            system_prompt = ""
            for msg in request.messages:
                if msg.role == "system":
                    system_prompt += msg.content + "\n"
                else:
                    anthropic_messages.append({"role": msg.role, "content": msg.content})

            payload: dict[str, Any] = {
                "model": model,
                "messages": anthropic_messages,
                "max_tokens": request.max_tokens or 4096,
                "temperature": request.temperature,
                "stream": True,
            }
            if system_prompt:
                payload["system"] = system_prompt

            try:
                async with client.stream("POST", "/v1/messages", json=payload) as response:
                    response.raise_for_status()
                    current_event = None
                    async for line in response.aiter_lines():
                        if line.startswith("event: "):
                            current_event = line[7:].strip()
                        elif line.startswith("data: "):
                            data_str = line[5:].strip()
                            if not data_str:
                                current_event = None
                                continue
                            try:
                                chunk = json.loads(data_str)
                            except json.JSONDecodeError:
                                current_event = None
                                continue
                            token = self._try_extract_anthropic_token(chunk, current_event)
                            if token:
                                yield token
                            elif current_event == "message_stop":
                                break
                            current_event = None
            except Exception as e:
                logger.error("Anthropic streaming failed", error=str(e))
                raise


class OpenAICompatibleProvider(LLMProvider):
    """Generic OpenAI-compatible API provider."""

    async def complete(self, request: LLMRequest) -> LLMResponse:
        await self._rate_limit()
        async with self._rate_limiter:
            client = await self._get_client()
            start_time = time.time()

            model = request.model or self.config.default_model
            if not model:
                raise ValueError("Model must be specified for OpenAI-compatible providers")

            payload = request.to_dict()
            payload["model"] = model

            try:
                response = await client.post("/chat/completions", json=payload)
                response.raise_for_status()
                data = response.json()

                latency_ms = (time.time() - start_time) * 1000
                choice = data["choices"][0]
                message = choice.get("message", {})

                return LLMResponse(
                    content=message.get("content", ""),
                    model=data.get("model", model),
                    provider=ProviderType.OPENAI_COMPATIBLE,
                    usage=data.get("usage", {}),
                    finish_reason=choice.get("finish_reason"),
                    tool_calls=message.get("tool_calls", []),
                    raw_response=data,
                    latency_ms=latency_ms,
                )
            except Exception as e:
                logger.error("OpenAI-compatible completion failed", error=str(e))
                raise

    async def stream(self, request: LLMRequest) -> AsyncIterator[str]:
        """Stream chat completion tokens."""
        await self._rate_limit()
        async with self._rate_limiter:
            client = await self._get_client()
            model = request.model or self.config.default_model
            if not model:
                raise ValueError("Model must be specified for OpenAI-compatible providers")

            payload = request.to_dict()
            payload["model"] = model
            payload["stream"] = True

            try:
                async with client.stream("POST", "/chat/completions", json=payload) as response:
                    response.raise_for_status()
                    async for line in response.aiter_lines():
                        if not line.startswith("data: "):
                            continue
                        data = line[6:]
                        if data.strip() == "[DONE]":
                            break
                        try:
                            chunk = json.loads(data)
                        except json.JSONDecodeError:
                            continue
                        token = self._try_extract_chat_token(chunk)
                        if token:
                            yield token
            except Exception as e:
                logger.error("OpenAI-compatible streaming failed", error=str(e))
                raise


# ============================================================================
# Provider Registry
# ============================================================================

PROVIDER_CLASSES: dict[ProviderType, type[LLMProvider]] = {
    ProviderType.OPENAI: OpenAIProvider,
    ProviderType.OLLAMA: OllamaProvider,
    ProviderType.MINIMAX: MiniMaxProvider,
    ProviderType.ANTHROPIC: AnthropicProvider,
    ProviderType.OPENAI_COMPATIBLE: OpenAICompatibleProvider,
}


def register_provider_class(provider_type: ProviderType, provider_class: type[LLMProvider]) -> None:
    """Register a custom provider class."""
    PROVIDER_CLASSES[provider_type] = provider_class


# ============================================================================
# Model Garage - Main Class
# ============================================================================


class ModelGarage:
    """
    Unified LLM interface for Heretek Swarm.

    Provides:
    - Multi-provider support with automatic routing
    - Fallback on provider failure
    - Load balancing across providers
    - Cost optimization
    - Health monitoring
    - Unified OpenAI-compatible API
    """

    # Pricing per 1K tokens: {model_substring: (input_cost, output_cost)}
    # Ordered from most-specific to least-specific for safe substring matching.
    # The first matching key wins, so longer/more specific keys must come first.
    _PRICING_TABLE: dict[str, tuple[float, float]] = {  # noqa: RUF012
        "gpt-4o-mini": (0.15, 0.60),
        "gpt-4-turbo": (10.0, 30.0),
        _DEFAULT_OPENAI_MODEL: (2.50, 10.0),
        "gpt-3.5-turbo": (0.50, 1.50),
        "o1-preview": (15.0, 60.0),
        "claude-3-5-sonnet": (3.0, 15.0),
        "claude-3-opus": (15.0, 75.0),
        "claude-3-haiku": (0.25, 1.25),
        "gemini-1.5-pro": (1.25, 5.0),
        "gemini-1.5-flash": (0.075, 0.30),
        "llama": (0.0, 0.0),
        "mistral": (0.0, 0.0),
    }

    def __init__(
        self,
        config_file: Path | None = None,
        default_provider: ProviderType | None = None,
    ):
        self.config_file = config_file or get_config_path()
        self._providers: dict[str, LLMProvider] = {}
        self._provider_configs: dict[str, ProviderConfig] = {}
        self._initialized = False
        self._default_provider = default_provider or ProviderType.OLLAMA

        self._load_config()

    def _load_config(self) -> None:
        """Load provider configuration from file."""
        try:
            if self.config_file.exists():
                with open(self.config_file) as f:  # noqa: PTH123
                    config_data = json.load(f)

                providers = config_data.get("modelProviders", [])
                for p in providers:
                    provider_type = ProviderType(p.get("type", "openai"))
                    config = ProviderConfig(
                        id=p.get("id", ""),
                        name=p.get("name", ""),
                        provider_type=provider_type,
                        base_url=p.get("baseUrl", ""),
                        api_key=p.get("apiKey"),
                        default_model=p.get("defaultModel"),
                        available_models=p.get("models", []),
                        is_enabled=p.get("isEnabled", True),
                        is_default=p.get("isDefault", False),
                        priority=p.get("priority", 100),
                    )
                    if "groupId" in p:
                        config.metadata["group_id"] = p["groupId"]
                    self._provider_configs[config.id] = config

                logger.info("Loaded provider configuration", count=len(self._provider_configs))
            else:
                self._create_default_config()
        except Exception as e:
            logger.error("Failed to load configuration", error=str(e))
            self._create_default_config()

    def _create_default_config(self) -> None:
        """Create default configuration file."""
        default_config = {
            "version": "1.0.0",
            "modelProviders": [
                {
                    "id": "default-ollama",
                    "type": "ollama",
                    "name": "Local Ollama",
                    "baseUrl": "http://localhost:11434",
                    "defaultModel": _DEFAULT_OLLAMA_MODEL,
                    "isEnabled": True,
                    "isDefault": True,
                    "priority": 1,
                }
            ],
        }

        try:
            self.config_file.parent.mkdir(parents=True, exist_ok=True)
            with open(self.config_file, "w") as f:  # noqa: PTH123
                json.dump(default_config, f, indent=2)
            logger.info("Created default configuration", path=str(self.config_file))
            self._load_config()
        except Exception as e:
            logger.error("Failed to create default configuration", error=str(e))

    def _calculate_cost(self, response: LLMResponse, model_name: str) -> float:
        """Calculate cost for a response based on model pricing table.

        Performs substring matching against ``_PRICING_TABLE`` keys, trying
        the longest (most specific) keys first.  Returns 0.0 when no table
        entry matches or when usage dict is empty (e.g. local models).
        """
        if not response.usage:
            return 0.0
        prompt_tokens = response.prompt_tokens
        completion_tokens = response.completion_tokens
        if prompt_tokens == 0 and completion_tokens == 0:
            return 0.0

        # Try most-specific (longest) keys first so "gpt-4o-mini" matches
        # before _DEFAULT_OPENAI_MODEL.
        for key in sorted(self._PRICING_TABLE, key=len, reverse=True):
            if key in model_name:
                input_rate, output_rate = self._PRICING_TABLE[key]
                cost = (prompt_tokens / 1000.0 * input_rate) + (
                    completion_tokens / 1000.0 * output_rate
                )
                return round(cost, 6)
        return 0.0

    def _save_config(self) -> None:
        """Save provider configuration to file using atomic write.

        Writes to a temp file, fsyncs, then atomically replaces the target.
        If the write fails mid-flight the original file is preserved (no
        corrupt partial write).  Last-writer-wins for concurrent access.
        """
        import os as _os  # local alias to avoid shadowing outer import

        config_data = {"version": "1.0.0", "modelProviders": []}
        for config in self._provider_configs.values():
            provider_data = {
                "id": config.id,
                "type": config.provider_type.value,
                "name": config.name,
                "baseUrl": config.base_url,
                "defaultModel": config.default_model,
                "models": config.available_models,
                "isEnabled": config.is_enabled,
                "isDefault": config.is_default,
                "priority": config.priority,
            }
            if config.api_key:
                provider_data["apiKey"] = config.api_key
            if config.metadata.get("group_id"):
                provider_data["groupId"] = config.metadata["group_id"]
            config_data["modelProviders"].append(provider_data)

        target = self.config_file
        tmp = target.with_suffix(target.suffix + ".tmp")
        try:
            # Ensure parent dir exists
            target.parent.mkdir(parents=True, exist_ok=True)

            with open(tmp, "w", encoding="utf-8") as f:  # noqa: PTH123
                json.dump(config_data, f, indent=2)
                f.flush()
                _os.fsync(f.fileno())

            # Atomic rename (Windows: replaces target if it exists)
            tmp.replace(target)
            logger.info("config_saved", path=str(target))
        except OSError as e:
            logger.error(
                "config_save_failed_atomic",
                path=str(target),
                error=e.__class__.__name__,
                detail=str(e),
            )
            # Best-effort cleanup of the temp file
            with contextlib.suppress(FileNotFoundError):
                tmp.unlink()

    async def initialize(self) -> None:
        """Initialize all enabled providers."""
        if self._initialized:
            return

        for config in self._provider_configs.values():
            if config.is_enabled and config.provider_type in PROVIDER_CLASSES:
                try:
                    provider_class = PROVIDER_CLASSES[config.provider_type]
                    provider = provider_class(config)
                    self._providers[config.id] = provider
                    logger.info(
                        "Initialized provider", name=config.name, type=config.provider_type.value
                    )
                except Exception as e:
                    logger.error("Failed to initialize provider", name=config.name, error=str(e))

        self._initialized = True
        logger.info("Model Garage initialized", provider_count=len(self._providers))

    async def close(self) -> None:
        """Close all providers."""
        for provider in self._providers.values():
            await provider.close()
        self._providers.clear()
        self._initialized = False
        logger.info("Model Garage closed")

    def add_provider(self, config: ProviderConfig) -> None:
        """Add a new provider configuration."""
        self._provider_configs[config.id] = config
        self._save_config()

    def remove_provider(self, provider_id: str) -> None:
        """Remove a provider configuration."""
        if provider_id in self._provider_configs:
            del self._provider_configs[provider_id]
        if provider_id in self._providers:
            del self._providers[provider_id]
        self._save_config()

    def reload_config(self) -> None:
        """Re-read config.json and rebuild ``_provider_configs``.

        Does NOT re-initialize ``_providers`` — provider connections are
        created lazily on the first ``complete()`` call.

        Useful when the config file is edited externally (e.g. CLI wizard,
        hand-edits) while the daemon is running.
        """
        old_count = len(self._provider_configs)
        self._provider_configs.clear()
        self._load_config()
        new_count = len(self._provider_configs)
        logger.info("config_reloaded", previous_providers=old_count, new_providers=new_count)

    def update_provider(self, provider_id: str, config: ProviderConfig) -> None:
        """Replace an existing provider's configuration.

        Args:
            provider_id: ID of the provider to update.
            config: New ``ProviderConfig`` to replace with.

        Raises:
            KeyError: If ``provider_id`` does not exist.
        """
        if provider_id not in self._provider_configs:
            raise KeyError(provider_id)

        self._provider_configs[provider_id] = config
        # If the provider is already initialized, replace it in _providers too
        if provider_id in self._providers:
            # Close old provider instance
            old_provider = self._providers[provider_id]
            # Schedule close without awaiting (fire-and-forget cleanup)
            try:
                loop = asyncio.get_running_loop()
                loop.create_task(old_provider.close())  # noqa: RUF006
            except RuntimeError:
                logger.exception(
                    "No event loop in thread, connection close deferred to next initialization"
                )
            del self._providers[provider_id]

        self._save_config()
        logger.info("provider_updated", provider_id=provider_id, name=config.name)

    async def test_provider(self, provider_id: str) -> dict[str, Any]:
        """Test connectivity to a configured provider.

        Instantiates the provider's class, calls ``health_check()``,
        measures latency, then closes the test instance.

        Args:
            provider_id: ID of the provider to test.

        Returns:
            ``{"reachable": bool, "latency_ms": float, "error": str | None}``.
            For unknown IDs returns ``{"reachable": false, "error": "..."}``.
        """
        config = self._provider_configs.get(provider_id)
        if config is None:
            return {
                "reachable": False,
                "latency_ms": 0.0,
                "error": f"Provider not found: {provider_id}",
            }

        provider_class = PROVIDER_CLASSES.get(config.provider_type)
        if provider_class is None:
            return {
                "reachable": False,
                "latency_ms": 0.0,
                "error": f"No provider class registered for type: {config.provider_type}",
            }

        t0 = time.time()
        try:
            provider = provider_class(config)
            reachable = await provider.health_check()
            latency_ms = (time.time() - t0) * 1000.0

            result = {
                "reachable": reachable,
                "latency_ms": round(latency_ms, 2),
                "error": None if reachable else "Health check failed",
            }
        except Exception as e:
            latency_ms = (time.time() - t0) * 1000.0
            result = {
                "reachable": False,
                "latency_ms": round(latency_ms, 2),
                "error": str(e),
            }
            logger.warning(
                "provider_test_failed", provider_id=provider_id, name=config.name, error=str(e)
            )
        finally:
            try:
                await provider.close()
            except Exception:
                logger.debug("provider_cleanup_error", exc_info=True)
                # best-effort cleanup

        logger.info(
            "provider_test_result",
            provider_id=provider_id,
            name=config.name,
            reachable=result["reachable"],
            latency_ms=result["latency_ms"],
        )
        return result

    def get_provider_config(self, provider_id: str) -> ProviderConfig | None:
        """Get provider configuration by ID."""
        return self._provider_configs.get(provider_id)

    def list_providers(self) -> list[dict[str, Any]]:
        """List all configured providers."""
        return [config.to_dict() for config in self._provider_configs.values()]

    async def health_check(self, provider_id: str | None = None) -> dict[str, bool]:
        """Check health of providers."""
        results = {}
        providers_to_check = (
            {provider_id: self._providers[provider_id]} if provider_id else self._providers
        )

        for pid, provider in providers_to_check.items():
            try:
                healthy = await provider.health_check()
                results[pid] = healthy
                provider.config.health_status = "healthy" if healthy else "unhealthy"
            except Exception as e:
                results[pid] = False
                provider.config.health_status = "unhealthy"
                provider.config.error_message = str(e)
                logger.error("Health check failed", provider=pid, error=str(e))

        return results

    async def complete(
        self,
        messages: list[ChatMessage],
        model: str | None = None,
        provider_id: str | None = None,
        provider_preference: list[ProviderType] | None = None,
        **kwargs,
    ) -> LLMResponse:
        """
        Complete a chat request with automatic provider routing.
        """
        if not self._initialized:
            await self.initialize()

        request = LLMRequest(
            messages=messages, model=model, **{k: v for k, v in kwargs.items() if v is not None}
        )

        if provider_id:
            providers_to_try = [provider_id] if provider_id in self._providers else []
        elif provider_preference:
            providers_to_try = [
                pid
                for pid, cfg in self._provider_configs.items()
                if cfg.provider_type in provider_preference and pid in self._providers
            ]
        else:
            providers_to_try = []
            for cfg in sorted(self._provider_configs.values(), key=lambda c: c.priority):
                if cfg.is_enabled and cfg.id in self._providers:
                    providers_to_try.append(cfg.id)
                    if cfg.is_default:
                        break

        if not providers_to_try:
            raise ValueError("No available providers")

        last_error = None
        for pid in providers_to_try:
            provider = self._providers.get(pid)
            if not provider:
                continue

            try:
                logger.debug(
                    "Attempting completion",
                    provider=pid,
                    model=model or provider.config.default_model,
                )
                response = await provider.complete(request)
                # Set cost from pricing table; will be 0.0 for local/unknown models
                response.cost = self._calculate_cost(response, response.model)
                logger.info(
                    "Completion successful",
                    provider=pid,
                    model=response.model,
                    latency_ms=response.latency_ms,
                    prompt_tokens=response.prompt_tokens,
                    completion_tokens=response.completion_tokens,
                    cost=response.cost,
                )
                return response
            except Exception as e:
                last_error = e
                logger.warning("Provider failed, trying next", provider=pid, error=str(e))

        raise last_error or RuntimeError("All providers failed")

    async def stream(
        self,
        messages: list[ChatMessage],
        model: str | None = None,
        provider_id: str | None = None,
        **kwargs,
    ) -> AsyncIterator[str]:
        """Stream chat completion tokens."""
        if not self._initialized:
            await self.initialize()

        request = LLMRequest(
            messages=messages,
            model=model,
            stream=True,
            **{k: v for k, v in kwargs.items() if v is not None},
        )

        provider = None
        if provider_id and provider_id in self._providers:
            provider = self._providers[provider_id]
        else:
            for cfg in sorted(self._provider_configs.values(), key=lambda c: c.priority):
                if cfg.is_enabled and cfg.id in self._providers:
                    provider = self._providers[cfg.id]
                    break

        if not provider:
            raise ValueError("No streaming-capable provider available")

        try:
            async for token in provider.stream(request):
                yield token
        except Exception as e:
            logger.error("Streaming failed", error=str(e))
            raise


# ============================================================================
# Global Instance
# ============================================================================

_model_garage: ModelGarage | None = None


def get_model_garage() -> ModelGarage:
    """Get the global ModelGarage instance."""
    global _model_garage
    if _model_garage is None:
        _model_garage = ModelGarage()
    return _model_garage


async def initialize_model_garage() -> ModelGarage:
    """Initialize and return the global ModelGarage instance."""
    global _model_garage
    _model_garage = ModelGarage()
    await _model_garage.initialize()
    return _model_garage


# ============================================================================
# Example Usage
# ============================================================================


async def main():
    """Example usage of ModelGarage."""
    garage = await initialize_model_garage()

    garage.list_providers()

    await garage.complete(
        messages=[
            ChatMessage(role="system", content="You are a helpful AI assistant."),
            ChatMessage(role="user", content="What is the capital of France?"),
        ]
    )

    await garage.close()


if __name__ == "__main__":
    asyncio.run(main())
