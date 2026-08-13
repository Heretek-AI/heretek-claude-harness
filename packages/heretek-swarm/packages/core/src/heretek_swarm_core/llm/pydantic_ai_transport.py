"""Pydantic AI transport for ModelGarage LLMProvider.

Replaces the hand-rolled httpx + manual SSE parsing in each provider's
``complete()`` / ``stream()`` with a pydantic-ai ``Agent`` run. The
``ModelGarage`` public surface (``complete(messages, ...)`` returning
``LLMResponse``; ``stream(messages, ...)`` yielding token strings) is
preserved so callers (``actors/base/message_handling.py``,
``routing/model_router.py``) do not change.

Provider classes keep their own ``__init__`` (which still constructs the
``InstrumentedAsyncClient`` for the headroom-compression timing path),
but their ``complete()`` and ``stream()`` delegate to the helpers here.
"""

from __future__ import annotations

from collections.abc import AsyncIterator

from pydantic_ai import Agent

from heretek_swarm_core.llm.model_garage import (
    ChatMessage,
    LLMRequest,
    LLMResponse,
    ProviderConfig,
    ProviderType,
)


def _flatten_messages(messages: list[ChatMessage]) -> str:
    """Flatten multi-turn messages into a single user prompt for pydantic-ai."""
    if not messages:
        return ""
    if len(messages) == 1:
        return messages[0].content
    prior = "\n".join(f"[{m.role}] {m.content}" for m in messages[:-1])
    return f"{prior}\n[user] {messages[-1].content}"


def _build_agent(config: ProviderConfig, model_name: str) -> Agent:
    """Build a pydantic-ai ``Agent`` from a ``ProviderConfig``.

    Supports the OpenAI, openai_compatible, ollama, and anthropic
    provider types. Other types fall through to the legacy httpx
    transport in the calling provider (not migrated in this change).
    """
    if config.provider_type in (
        ProviderType.OPENAI,
        ProviderType.OPENAI_COMPATIBLE,
        ProviderType.OLLAMA,
    ):
        from pydantic_ai.models.openai import OpenAIChatModel
        from pydantic_ai.providers.openai import OpenAIProvider as _PAOpenAIProvider

        base_url = config.base_url
        if config.provider_type == ProviderType.OLLAMA and not base_url:
            base_url = "http://localhost:11434/v1"
        provider = _PAOpenAIProvider(
            base_url=base_url, api_key=config.api_key or "ollama"
        )
        model = OpenAIChatModel(model_name, provider=provider)
        return Agent(model)
    if config.provider_type == ProviderType.ANTHROPIC:
        from pydantic_ai.models.anthropic import AnthropicModel
        from pydantic_ai.providers.anthropic import AnthropicProvider

        provider = AnthropicProvider(api_key=config.api_key, base_url=config.base_url)
        model = AnthropicModel(model_name, provider=provider)
        return Agent(model)
    raise NotImplementedError(
        f"pydantic-ai transport not wired for provider_type={config.provider_type.value}"
    )


def _resolve_model_name(config: ProviderConfig, request: LLMRequest) -> str:
    return request.model or config.default_model or ""


async def pydantic_ai_complete(config: ProviderConfig, request: LLMRequest) -> LLMResponse:
    """Pydantic-AI-backed completion preserving ``LLMResponse`` shape."""
    model_name = _resolve_model_name(config, request)
    agent = _build_agent(config, model_name)
    user_prompt = _flatten_messages(request.messages)
    result = await agent.run(user_prompt)
    output = getattr(result, "output", "")
    usage_obj = result.usage()
    usage_dict: dict[str, int] = {
        "prompt_tokens": getattr(usage_obj, "input_tokens", 0) or 0,
        "completion_tokens": getattr(usage_obj, "output_tokens", 0) or 0,
    }
    usage_dict["total_tokens"] = usage_dict["prompt_tokens"] + usage_dict["completion_tokens"]
    return LLMResponse(
        content=str(output),
        model=model_name,
        provider=config.provider_type,
        usage=usage_dict,
        finish_reason="stop",
        tool_calls=[],
        raw_response={},
        latency_ms=0.0,
    )


async def pydantic_ai_stream(config: ProviderConfig, request: LLMRequest) -> AsyncIterator[str]:
    """Pydantic-AI-backed token stream."""
    model_name = _resolve_model_name(config, request)
    agent = _build_agent(config, model_name)
    user_prompt = _flatten_messages(request.messages)
    async with agent.run_stream(user_prompt) as streamed:
        async for chunk in streamed.stream_text():
            yield chunk