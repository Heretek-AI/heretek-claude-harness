"""Behavior tests for MiniMax provider (replay via vcrpy cassettes)."""

from __future__ import annotations

import pytest

from tier1.config import Settings
from tier1.llm.garage import ModelGarage


def _settings() -> Settings:
    """Test settings — base_url pinned to production MiniMax API."""
    return Settings(minimax_api_key="sk-cassette-replay-not-live")


@pytest.fixture()
def garage() -> ModelGarage:
    return ModelGarage(_settings())


@pytest.mark.integration
async def test_minimax_stream_tokens(garage: ModelGarage, vcr_cassette):
    """Smoke shape: at least one token comes back, has agent + seq."""
    with vcr_cassette:
        chunks = []
        async for c in garage._stream_openai_provider("say hi", "alpha", "minimax"):
            chunks.append(c)
    assert len(chunks) >= 1
    assert all(c.agent == "alpha" for c in chunks)
    assert all(isinstance(c.token, str) and c.token for c in chunks)
    assert all(c.seq == i for i, c in enumerate(chunks))


@pytest.mark.integration
async def test_minimax_monotonic_seq(garage: ModelGarage, vcr_cassette):
    """seq counter increments 0, 1, 2, ... across the stream."""
    with vcr_cassette:
        seqs = []
        async for c in garage._stream_openai_provider("count to 3", "beta", "minimax"):
            seqs.append(c.seq)
    assert seqs == list(range(len(seqs)))
    assert len(seqs) >= 1


@pytest.mark.integration
async def test_minimax_empty_stream(garage: ModelGarage, vcr_cassette):
    """A response with no content chunks yields no StreamChunks."""
    with vcr_cassette:
        chunks = []
        async for c in garage._stream_openai_provider("respond-empty-marker", "alpha", "minimax"):
            chunks.append(c)
    assert chunks == []


@pytest.mark.integration
async def test_minimax_error_response(garage: ModelGarage, vcr_cassette):
    """A 401 from MiniMax raises LLMUnavailable, not a generic exception."""
    from tier1.llm.errors import LLMUnavailable

    with vcr_cassette:
        with pytest.raises(LLMUnavailable):
            async for _ in garage._stream_openai_provider("trigger-401", "alpha", "minimax"):
                pass
