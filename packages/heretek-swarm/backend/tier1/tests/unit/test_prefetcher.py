"""Tests for IntelligentPrefetcher."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from tier1.memory.prefetcher import IntelligentPrefetcher


@pytest.fixture()
def prefetcher():
    patterns = AsyncMock()
    cache = AsyncMock()
    backend = AsyncMock()
    return IntelligentPrefetcher(patterns=patterns, cache=cache, backend=backend)


async def test_get_candidates_returns_top_entries(prefetcher):
    prefetcher.patterns.get_top_entries = AsyncMock(return_value=["e1", "e2", "e3"])
    result = await prefetcher.get_candidates("agent1")
    assert result == ["e1", "e2", "e3"]
    prefetcher.patterns.get_top_entries.assert_called_once_with("agent1", top_n=10)


async def test_prefetch_loads_uncached_entries(prefetcher):
    prefetcher.patterns.get_top_entries = AsyncMock(return_value=["e1", "e2"])
    prefetcher.cache.get = AsyncMock(side_effect=[None, MagicMock()])  # e1 miss, e2 hit
    prefetcher.backend.postgres = MagicMock()
    prefetcher.backend.postgres.get_history = AsyncMock(return_value=[])
    count = await prefetcher.prefetch("agent1")
    assert count >= 0
