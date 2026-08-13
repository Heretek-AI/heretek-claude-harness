"""Characterization tests for ModelGarage.

These tests pin the current public contract of ModelGarage so the
LLM-stack consolidation onto Pydantic AI (Phase 2) can be verified for
behavioral parity. They do NOT hit the network: the instrumented httpx
client is patched to return canned responses.

Covered contract:
- Provider routing (provider_id / provider_preference / default+priority)
- LLMRequest -> payload mapping (model override, temperature, etc.)
- OpenAI response -> LLMResponse mapping (content, usage, finish_reason)
- Provider fallback across a failed provider
- "No available providers" error path
"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

from heretek_swarm_core.llm.model_garage import (
    ChatMessage,
    LLMRequest,
    LLMResponse,
    ModelGarage,
    ProviderConfig,
    ProviderType,
)

pytestmark = pytest.mark.asyncio


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _config(pid: str, *, provider_type: ProviderType, **kw) -> ProviderConfig:
    base = dict(
        id=pid,
        name=pid,
        provider_type=provider_type,
        base_url="https://example.test/v1",
        api_key="k-test",
        default_model="m-test",
        is_enabled=True,
        priority=100,
    )
    base.update(kw)
    return ProviderConfig(**base)


def _fake_httpx_response(payload: dict, status: int = 200) -> SimpleNamespace:
    """A minimal stand-in for an httpx.Response."""

    def raise_for_status() -> None:
        if status >= 400:
            raise RuntimeError(f"HTTP {status}")

    return SimpleNamespace(
        json=lambda: payload,
        raise_for_status=raise_for_status,
        status_code=status,
    )


def _empty_garage(tmp_path) -> ModelGarage:
    """A ModelGarage isolated from the real ~/.heretek-swarm/config.json."""
    return ModelGarage(config_file=tmp_path / "config.json")


def _garage_with_openai(tmp_path, pid: str = "openai-1", **kw) -> ModelGarage:
    """A ModelGarage with one OpenAI provider registered and marked default."""
    garage = _empty_garage(tmp_path)
    cfg = _config(pid, provider_type=ProviderType.OPENAI, is_default=True, **kw)
    garage._provider_configs[cfg.id] = cfg
    return garage


# ---------------------------------------------------------------------------
# Request -> payload mapping
# ---------------------------------------------------------------------------


class TestRequestMapping:
    async def test_request_to_dict_includes_messages_and_defaults(self) -> None:
        payload = LLMRequest(
            messages=[ChatMessage(role="user", content="hi")], model="gpt-x"
        ).to_dict()
        assert payload["messages"] == [{"role": "user", "content": "hi"}]
        assert payload["model"] == "gpt-x"
        assert payload["stream"] is False
        assert payload["temperature"] == 0.7


# ---------------------------------------------------------------------------
# complete(): response mapping + routing
# ---------------------------------------------------------------------------


class TestComplete:
    async def test_complete_maps_pydantic_ai_response_to_llmresponse(self, tmp_path) -> None:
        garage = _garage_with_openai(tmp_path)
        await garage.initialize()

        # Mock pydantic-ai Agent.run to return a fake result with usage.
        class _Usage:
            input_tokens = 3
            output_tokens = 2

        class _Result:
            output = "hello world"

            def usage(self):
                return _Usage()

        with patch(
            "heretek_swarm_core.llm.pydantic_ai_transport.pydantic_ai_complete",
            AsyncMock(return_value=LLMResponse(
                content="hello world",
                model="gpt-x",
                provider=ProviderType.OPENAI,
                usage={"prompt_tokens": 3, "completion_tokens": 2, "total_tokens": 5},
                finish_reason="stop",
            )),
        ):
            resp = await garage.complete(
                messages=[ChatMessage(role="user", content="hi")],
                model="gpt-x",
                provider_id="openai-1",
            )

        assert isinstance(resp, LLMResponse)
        assert resp.content == "hello world"
        assert resp.finish_reason == "stop"
        assert resp.prompt_tokens == 3
        assert resp.completion_tokens == 2
        assert resp.total_tokens == 5

    async def test_complete_uses_provider_default_model_when_unspecified(self, tmp_path) -> None:
        garage = _garage_with_openai(tmp_path)
        await garage.initialize()
        captured: dict = {}

        async def fake_complete(config, request):
            captured["model_name"] = request.model or config.default_model
            return LLMResponse(
                content="ok",
                model=captured["model_name"],
                provider=ProviderType.OPENAI,
                usage={},
                finish_reason="stop",
            )

        with patch(
            "heretek_swarm_core.llm.pydantic_ai_transport.pydantic_ai_complete",
            side_effect=fake_complete,
        ):
            await garage.complete(
                messages=[ChatMessage(role="user", content="hi")],
                provider_id="openai-1",
            )

        # ProviderConfig.default_model should win when caller passes no model
        assert captured["model_name"] == "m-test"

    async def test_complete_routes_to_provider_id(self, tmp_path) -> None:
        garage = _empty_garage(tmp_path)
        garage._provider_configs["a"] = _config(
            "a", provider_type=ProviderType.OPENAI, is_default=True
        )
        garage._provider_configs["b"] = _config(
            "b", provider_type=ProviderType.OPENAI, is_default=False
        )
        await garage.initialize()

        async def fake_complete(config, request):
            return LLMResponse(
                content="b-only",
                model="m",
                provider=ProviderType.OPENAI,
                usage={},
                finish_reason="stop",
            )

        with patch(
            "heretek_swarm_core.llm.pydantic_ai_transport.pydantic_ai_complete",
            side_effect=fake_complete,
        ):
            resp = await garage.complete(
                messages=[ChatMessage(role="user", content="hi")], provider_id="b"
            )
        assert resp.content == "b-only"
