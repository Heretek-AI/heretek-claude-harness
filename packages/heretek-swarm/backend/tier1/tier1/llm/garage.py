"""ModelGarage — pydantic-ai multi-provider wrapper with circuit breaker.

Provider chain: MiniMax (primary) -> Anthropic -> OpenAI -> local (Ollama).

Circuit breaker: each provider tracks recent failures. 3 failures within
60s -> provider marked down for 5 minutes. Calls skip down providers
and try the next in the chain. If all providers are down, raise
LLMUnavailable.
"""

from __future__ import annotations

import time
from collections import deque
from dataclasses import dataclass
from typing import AsyncIterator, Deque

import structlog

from tier1.config import Settings
from tier1.observability import get_tracer
from tier1.observability.metrics import record_provider_call
from tier1.deliberation.state import AgentName
from tier1.llm.errors import (
    LLMTimeout,
    LLMUnavailable,
)  # LLMTimeout: part of the provider contract; see _stream_from_provider docstring.

log = structlog.get_logger(__name__)

PROVIDER_NAMES = ("minimax", "anthropic", "openai", "local")

CIRCUIT_WINDOW_S = 60.0
CIRCUIT_THRESHOLD = 3
CIRCUIT_OPEN_S = 300.0


@dataclass
class StreamChunk:
    token: str
    agent: AgentName
    seq: int


class _Circuit:
    """Per-provider circuit breaker."""

    def __init__(self, name: str) -> None:
        self.name = name
        self.failures: Deque[float] = deque()
        self.open_until: float = 0.0

    def record_failure(self) -> None:
        now = time.time()
        self.failures.append(now)
        while self.failures and now - self.failures[0] > CIRCUIT_WINDOW_S:
            self.failures.popleft()
        if len(self.failures) >= CIRCUIT_THRESHOLD:
            self.open_until = now + CIRCUIT_OPEN_S
            log.warning("circuit_open", provider=self.name, until=self.open_until)
            from tier1.observability.metrics import toggle_circuit_state

            toggle_circuit_state(self.name, +1)

    def record_success(self) -> None:
        self.failures.clear()
        self.open_until = 0.0
        from tier1.observability.metrics import toggle_circuit_state

        toggle_circuit_state(self.name, -1)

    def is_open(self) -> bool:
        return time.time() < self.open_until


class ModelGarage:
    """Multi-provider LLM gateway with circuit breaker and streaming."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.circuits: dict[str, _Circuit] = {name: _Circuit(name) for name in PROVIDER_NAMES}

    def provider_order(self) -> list[str]:
        """Return provider names in priority order, skipping open circuits."""
        return [n for n in PROVIDER_NAMES if not self.circuits[n].is_open()]

    async def stream_chat(
        self,
        prompt: str,
        *,
        agent: AgentName,
    ) -> AsyncIterator[StreamChunk]:
        """Yield token chunks. Tries providers in chain until one succeeds.

        Failure semantics:
        - `LLMTimeout` / `LLMUnavailable` raised before any chunk: recorded as
          a failure, falls through to the next provider.
        - Any other exception (or a recognized exception) raised AFTER one or
          more chunks were yielded (mid-stream failure): recorded as a failure
          for the active provider, then wrapped as `LLMUnavailable` and
          propagated to the caller. Mid-stream partial output is treated as
          unrecoverable for the current call — falling through to another
          provider would double-emit tokens. The next call to `stream_chat`
          will start the chain from the top, skipping the now-open circuit
          if it tripped.
        """
        order = self.provider_order()
        if not order:
            raise LLMUnavailable("all providers down (circuit open)")

        last_exc: Exception | None = None
        for provider in order:
            yielded = 0
            try:
                async for chunk in self._stream_from_provider(provider, prompt, agent):
                    yield chunk
                    yielded += 1
                self.circuits[provider].record_success()
                return
            except Exception as exc:  # noqa: BLE001 — see failure semantics
                self.circuits[provider].record_failure()
                last_exc = exc
                if yielded == 0:
                    log.warning(
                        "provider_failed",
                        provider=provider,
                        error=str(exc),
                        error_type=type(exc).__name__,
                    )
                    continue
                # Mid-stream failure: partial output already yielded to the
                # caller. Wrap as LLMUnavailable and propagate — the caller
                # has already seen the partial response and we cannot safely
                # resume or fall through without producing a confusing mix.
                log.warning(
                    "provider_midstream_failure",
                    provider=provider,
                    chunks_yielded=yielded,
                    error=str(exc),
                    error_type=type(exc).__name__,
                )
                raise LLMUnavailable(
                    f"provider {provider} raised mid-stream after {yielded} chunks: {exc}"
                ) from exc

        raise LLMUnavailable(f"all providers failed: {last_exc}")

    async def _stream_from_provider(
        self,
        provider: str,
        prompt: str,
        agent: AgentName,
    ) -> AsyncIterator[StreamChunk]:
        """Provider-specific streaming using native SDKs.

        MiniMax/OpenAI/Local (Ollama): openai SDK with custom base_url.
        Anthropic: anthropic SDK.

        This method MUST raise LLMTimeout for timeout, or yield
        StreamChunk instances for each token. It MUST NOT raise any
        other exception type.
        """
        dispatch = {
            "minimax": lambda p, a: self._stream_openai_provider(p, a, "minimax"),
            "anthropic": self._stream_anthropic_provider,
            "openai": lambda p, a: self._stream_openai_provider(p, a, "openai"),
            "local": lambda p, a: self._stream_openai_provider(p, a, "local"),
        }
        fn = dispatch.get(provider)
        if fn is None:
            raise LLMUnavailable(f"unknown provider: {provider!r}")
        async for chunk in fn(prompt, agent):
            yield chunk

    async def _stream_openai_provider(
        self,
        prompt: str,
        agent: AgentName,
        provider_name: str,
    ) -> AsyncIterator[StreamChunk]:
        """Stream using the openai SDK (MiniMax, OpenAI, Ollama)."""
        try:
            from openai import AsyncOpenAI
        except ImportError as exc:
            raise LLMUnavailable(f"openai package not installed: {exc}") from exc

        if provider_name == "minimax":
            key = self.settings.minimax_api_key
            base = self.settings.minimax_base_url
            model = self.settings.minimax_model
        elif provider_name == "openai":
            key = self.settings.openai_api_key
            base = None
            model = self.settings.openai_model
        elif provider_name == "local":
            key = "ollama"
            base = self.settings.ollama_base_url
            model = self.settings.local_model
        else:
            raise LLMUnavailable(f"unknown openai-type provider: {provider_name!r}")

        if not key:
            raise LLMUnavailable(f"no API key for {provider_name}")

        client = AsyncOpenAI(api_key=key, base_url=base, timeout=self.settings.llm_timeout_s)
        tracer = get_tracer("tier1.llm")
        t0 = time.monotonic()
        with tracer.start_as_current_span(f"llm.{provider_name}") as span:
            span.set_attribute("provider", provider_name)
            span.set_attribute("model", model)
            try:
                response = await client.chat.completions.create(
                    model=model,
                    messages=[{"role": "user", "content": prompt}],
                    stream=True,
                )
                seq = 0
                async for chunk in response:  # type: ignore[union-attr]
                    delta = chunk.choices[0].delta if chunk.choices else None
                    if delta and delta.content:
                        yield StreamChunk(token=delta.content, agent=agent, seq=seq)
                        seq += 1
            except Exception as exc:
                if "timeout" in str(exc).lower() or "timed out" in str(exc).lower():
                    raise LLMTimeout(str(exc)) from exc
                # Wrap SDK-level errors (auth, rate-limit, etc.) as LLMUnavailable
                # so callers see a uniform provider-failure type.
                try:
                    from openai import OpenAIError
                except ImportError:
                    OpenAIError = None  # type: ignore[assignment,misc]
                if OpenAIError is not None and isinstance(exc, OpenAIError):
                    raise LLMUnavailable(str(exc)) from exc
                raise
            finally:
                record_provider_call(provider_name, time.monotonic() - t0)

    async def _stream_anthropic_provider(
        self,
        prompt: str,
        agent: AgentName,
    ) -> AsyncIterator[StreamChunk]:
        """Stream using the anthropic SDK."""
        try:
            import anthropic
        except ImportError as exc:
            raise LLMUnavailable(f"anthropic package not installed: {exc}") from exc

        if not self.settings.anthropic_api_key:
            raise LLMUnavailable("no API key for anthropic")

        client = anthropic.AsyncAnthropic(
            api_key=self.settings.anthropic_api_key,
            timeout=self.settings.llm_timeout_s,
        )
        tracer = get_tracer("tier1.llm")
        t0 = time.monotonic()
        with tracer.start_as_current_span("llm.anthropic") as span:
            span.set_attribute("provider", "anthropic")
            span.set_attribute("model", self.settings.anthropic_model)
            try:
                async with client.messages.stream(
                    model=self.settings.anthropic_model,
                    max_tokens=4096,
                    messages=[{"role": "user", "content": prompt}],
                ) as stream:
                    seq = 0
                    async for text in stream.text_stream:
                        yield StreamChunk(token=text, agent=agent, seq=seq)
                        seq += 1
            except Exception as exc:
                if "timeout" in str(exc).lower() or "timed out" in str(exc).lower():
                    raise LLMTimeout(str(exc)) from exc
                # Wrap SDK-level errors as LLMUnavailable for uniform error type.
                try:
                    from anthropic import AnthropicError
                except ImportError:
                    AnthropicError = None  # type: ignore[assignment,misc]
                if AnthropicError is not None and isinstance(exc, AnthropicError):
                    raise LLMUnavailable(str(exc)) from exc
                raise
            finally:
                record_provider_call("anthropic", time.monotonic() - t0)

    async def chat(self, prompt: str, *, agent: AgentName) -> str:
        """Non-streaming convenience: collect all tokens into one string."""
        chunks: list[str] = []
        async for chunk in self.stream_chat(prompt, agent=agent):
            chunks.append(chunk.token)
        return "".join(chunks)
