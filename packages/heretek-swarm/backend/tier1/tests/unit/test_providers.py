"""Tests for real LLM provider implementations in garage.py.

These tests mock the HTTP layer to test the actual provider
code paths, including SDK import, API key validation, streaming,
and error handling.
"""

from __future__ import annotations

import sys
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import httpx

from tier1.config import Settings
from tier1.deliberation.state import AgentName
from tier1.llm.errors import LLMTimeout, LLMUnavailable
from tier1.llm.garage import ModelGarage


def _settings(**overrides) -> Settings:
    defaults = dict(
        minimax_api_key="sk-test",
        minimax_base_url="https://api.minimaxi.com/v1",
        minimax_model="test-model",
        anthropic_api_key="sk-anthropic-test",
        anthropic_model="test-claude",
        openai_api_key="sk-openai-test",
        openai_model="test-gpt",
        ollama_base_url="http://localhost:11434/v1",
        local_model="test-llama",
        llm_timeout_s=10.0,
    )
    defaults.update(overrides)
    return Settings(**defaults)


class _MockOpenAIStreamResponse:
    """Mock async iterator for openai streaming response."""

    def __init__(self, chunks: list[str]) -> None:
        self._chunks = chunks

    def __aiter__(self):
        async def gen():
            for token in self._chunks:
                delta = AsyncMock()
                delta.content = token
                choice = AsyncMock()
                choice.delta = delta
                chunk = AsyncMock()
                chunk.choices = [choice]
                yield chunk

        return gen()


class _MockAnthropicStream:
    """Mock context manager for anthropic client.messages.stream."""

    def __init__(self, chunks: list[str]) -> None:
        self._chunks = chunks

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        pass

    @property
    def text_stream(self):
        async def gen():
            for token in self._chunks:
                yield token

        return gen()


class _StreamCM:
    """Sync wrapper so async with receives _MockAnthropicStream."""

    def __init__(self, stream: _MockAnthropicStream) -> None:
        self._stream = stream

    async def __aenter__(self):
        return self._stream

    async def __aexit__(self, *args):
        pass


@pytest.fixture
def garage() -> ModelGarage:
    return ModelGarage(_settings())


# -------------------------------------------------------------------
# _stream_from_provider dispatch
# -------------------------------------------------------------------


async def test_dispatch_minimax_calls_stream_openai(garage, monkeypatch):
    called = {"provider": None}

    async def fake_openai(prompt, agent, provider):
        called["provider"] = provider
        from tier1.llm.garage import StreamChunk

        yield StreamChunk(token="x", agent=agent, seq=0)

    monkeypatch.setattr(garage, "_stream_openai_provider", fake_openai)
    chunks = []
    async for c in garage._stream_from_provider("minimax", "hi", "alpha"):
        chunks.append(c)
    assert called["provider"] == "minimax"


async def test_dispatch_unknown_provider_raises(garage):
    with pytest.raises(LLMUnavailable, match="unknown provider"):
        async for _ in garage._stream_from_provider("nonexistent", "hi", "alpha"):
            pass


# -------------------------------------------------------------------
# Missing API keys
# -------------------------------------------------------------------


async def test_minimax_missing_key_raises_unavailable(garage):
    garage.settings = _settings(minimax_api_key="")
    with pytest.raises(LLMUnavailable, match="no API key for minimax"):
        async for _ in garage._stream_openai_provider("hi", "alpha", "minimax"):
            pass


async def test_openai_missing_key_raises_unavailable(garage):
    garage.settings = _settings(openai_api_key="")
    with pytest.raises(LLMUnavailable, match="no API key for openai"):
        async for _ in garage._stream_openai_provider("hi", "alpha", "openai"):
            pass


async def test_anthropic_missing_key_raises_unavailable(garage):
    garage.settings = _settings(anthropic_api_key="")
    with pytest.raises(LLMUnavailable, match="no API key for anthropic"):
        async for _ in garage._stream_anthropic_provider("hi", "alpha"):
            pass


# -------------------------------------------------------------------
# OpenAI provider (MiniMax/OpenAI/Ollama)
# -------------------------------------------------------------------


async def test_openai_provider_yields_tokens(garage):
    mock_response = _MockOpenAIStreamResponse(["hello", " ", "world"])
    mock_client = AsyncMock()
    mock_client.chat.completions.create.return_value = mock_response

    with patch("openai.AsyncOpenAI", return_value=mock_client):
        chunks = []
        async for c in garage._stream_openai_provider("hi", "alpha", "minimax"):
            chunks.append(c)

    assert [c.token for c in chunks] == ["hello", " ", "world"]
    assert [c.agent for c in chunks] == ["alpha", "alpha", "alpha"]
    assert [c.seq for c in chunks] == [0, 1, 2]


async def test_openai_provider_monotonic_seq(garage):
    mock_response = _MockOpenAIStreamResponse(["a", "b", "c", "d", "e"])
    mock_client = AsyncMock()
    mock_client.chat.completions.create.return_value = mock_response

    with patch("openai.AsyncOpenAI", return_value=mock_client):
        chunks = []
        async for c in garage._stream_openai_provider("hi", "beta", "openai"):
            chunks.append(c)

    seqs = [c.seq for c in chunks]
    assert seqs == sorted(seqs)


async def test_openai_provider_empty_stream(garage):
    mock_response = _MockOpenAIStreamResponse([])
    mock_client = AsyncMock()
    mock_client.chat.completions.create.return_value = mock_response

    with patch("openai.AsyncOpenAI", return_value=mock_client):
        chunks = []
        async for c in garage._stream_openai_provider("hi", "alpha", "minimax"):
            chunks.append(c)

    assert chunks == []


async def test_openai_provider_passes_correct_config(garage):
    mock_response = _MockOpenAIStreamResponse([])
    mock_client = AsyncMock()
    mock_client.chat.completions.create.return_value = mock_response

    with patch("openai.AsyncOpenAI", return_value=mock_client) as cls:
        async for _ in garage._stream_openai_provider("hi", "alpha", "minimax"):
            pass

    call_kwargs = cls.call_args
    assert call_kwargs.kwargs["api_key"] == "sk-test"
    assert call_kwargs.kwargs["base_url"] == "https://api.minimaxi.com/v1"


async def test_openai_provider_sdk_not_installed_raises(garage, monkeypatch):
    import builtins

    real_import = builtins.__import__

    def no_openai(name, *args, **kwargs):
        if name == "openai":
            raise ImportError("no openai")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr("builtins.__import__", no_openai)
    with pytest.raises(LLMUnavailable, match="openai package not installed"):
        async for _ in garage._stream_openai_provider("hi", "alpha", "minimax"):
            pass


# -------------------------------------------------------------------
# Anthropic provider
# -------------------------------------------------------------------


async def test_anthropic_provider_yields_tokens(garage):
    mock_stream = _MockAnthropicStream(["hello", " ", "world"])

    # Build a mock module that replaces sys.modules["anthropic"]
    mock_anthropic = type(sys)("")  # noqa: F821
    mock_anthropic.__name__ = "anthropic"
    mock_anthropic.__package__ = "anthropic"
    mock_anthropic.__path__ = []

    mock_anthropic_client = MagicMock()
    mock_anthropic_client.messages.stream.return_value = _StreamCM(mock_stream)
    mock_anthropic.AsyncAnthropic = lambda **kw: mock_anthropic_client

    with patch.dict("sys.modules", {"anthropic": mock_anthropic}):
        chunks = []
        async for c in garage._stream_anthropic_provider("hi", "alpha"):
            chunks.append(c)

    assert [c.token for c in chunks] == ["hello", " ", "world"]
    assert [c.seq for c in chunks] == [0, 1, 2]


async def test_anthropic_provider_passes_correct_config(garage):
    mock_stream = _MockAnthropicStream([])

    mock_anthropic = type(sys)("")  # noqa: F821
    mock_anthropic.__name__ = "anthropic"
    mock_anthropic.__package__ = "anthropic"
    mock_anthropic.__path__ = []

    mock_anthropic_client = MagicMock()
    mock_anthropic_client.messages.stream.return_value = _StreamCM(mock_stream)
    mock_anthropic.AsyncAnthropic = MagicMock(side_effect=lambda **kw: mock_anthropic_client)

    with patch.dict("sys.modules", {"anthropic": mock_anthropic}):
        async for _ in garage._stream_anthropic_provider("hi", "alpha"):
            pass

    assert mock_anthropic.AsyncAnthropic.call_args.kwargs["api_key"] == "sk-anthropic-test"


async def test_anthropic_provider_sdk_not_installed_raises(garage):
    with patch.dict("sys.modules", {"anthropic": None}):
        with pytest.raises(LLMUnavailable, match="anthropic package not installed"):
            async for _ in garage._stream_anthropic_provider("hi", "alpha"):
                pass


# -------------------------------------------------------------------
# Local (Ollama) provider
# -------------------------------------------------------------------


async def test_local_provider_uses_ollama_base_url(garage):
    mock_response = _MockOpenAIStreamResponse([])
    mock_client = AsyncMock()
    mock_client.chat.completions.create.return_value = mock_response

    with patch("openai.AsyncOpenAI", return_value=mock_client) as cls:
        async for _ in garage._stream_openai_provider("hi", "alpha", "local"):
            pass

    call_kwargs = cls.call_args
    assert call_kwargs.kwargs["api_key"] == "ollama"
    assert call_kwargs.kwargs["base_url"] == "http://localhost:11434/v1"


# -------------------------------------------------------------------
# Integration: stream_chat with real dispatch
# -------------------------------------------------------------------


async def test_stream_chat_uses_real_dispatch(garage):
    mock_response = _MockOpenAIStreamResponse(["token1", "token2"])
    mock_client = AsyncMock()
    mock_client.chat.completions.create.return_value = mock_response

    with patch("openai.AsyncOpenAI", return_value=mock_client):
        chunks = []
        async for c in garage.stream_chat("test prompt", agent="alpha"):
            chunks.append(c)

    assert [c.token for c in chunks] == ["token1", "token2"]


async def test_stream_chat_fallback_uses_real_dispatch(garage):
    call_count = {"n": 0}

    async def mock_create(**kwargs):
        call_count["n"] += 1
        if call_count["n"] == 1:
            raise httpx.TimeoutException("timeout")
        return _MockOpenAIStreamResponse(["ok"])

    mock_client = AsyncMock()
    mock_client.chat.completions.create = mock_create

    with patch("openai.AsyncOpenAI", return_value=mock_client):
        chunks = []
        async for c in garage.stream_chat("test", agent="alpha"):
            chunks.append(c)

    assert [c.token for c in chunks] == ["ok"]
    assert call_count["n"] == 2
