"""Live MiniMax smoke tests. Skip when TIER1_MINIMAX_API_KEY is unset.

These tests prove the SDK + key + base_url still work against the real API.
They're slow and incur cost — only run on main-merge or manual trigger.
"""

from __future__ import annotations

import pytest

from tier1.config import Settings
from tier1.llm.garage import ModelGarage


def _settings(key: str) -> Settings:
    return Settings(minimax_api_key=key)


@pytest.fixture()
def garage(require_minimax_key: str) -> ModelGarage:
    """Garage with the live key from the env var."""
    return ModelGarage(_settings(require_minimax_key))


@pytest.mark.integration
async def test_smoke_returns_tokens(garage: ModelGarage):
    """A trivial prompt yields at least one token chunk with the expected shape."""
    chunks = []
    async for c in garage._stream_openai_provider("say hi", "alpha", "minimax"):
        chunks.append(c)
    assert len(chunks) >= 1, "no tokens returned from MiniMax"
    first = chunks[0]
    assert isinstance(first.token, str) and first.token
    assert first.agent == "alpha"
    assert first.seq == 0
    # Monotonic seq
    assert all(c.seq == i for i, c in enumerate(chunks))


@pytest.mark.integration
async def test_smoke_uses_minimax_url(garage: ModelGarage):
    """Verify base_url in the live client matches the configured MiniMax URL."""
    # Patch AsyncOpenAI to capture the constructed client and inspect its base_url.
    from openai import AsyncOpenAI

    captured: dict[str, object] = {}

    real_init = AsyncOpenAI.__init__

    def spy_init(self, **kwargs):
        captured.update(kwargs)
        real_init(self, **kwargs)

    AsyncOpenAI.__init__ = spy_init  # type: ignore[method-assign]
    try:
        async for _ in garage._stream_openai_provider("ping", "alpha", "minimax"):
            pass
    finally:
        AsyncOpenAI.__init__ = real_init  # type: ignore[method-assign]

    settings = garage.settings
    assert captured.get("api_key") == settings.minimax_api_key
    assert captured.get("base_url") == settings.minimax_base_url
    assert "minimax.io" in str(captured.get("base_url"))
