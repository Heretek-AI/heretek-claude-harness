"""Tests for AccessPatternAnalyzer."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from tier1.memory.access_patterns import AccessPatternAnalyzer


@pytest.fixture()
def analyzer():
    a = AccessPatternAnalyzer(pool=None)
    a._pool = AsyncMock()
    return a


async def test_record_access_inserts_row(analyzer):
    await analyzer.record_access("agent1", "entry-1")
    analyzer._pool.execute.assert_called_once()


async def test_get_top_entries_returns_ids(analyzer):
    row = MagicMock()
    row.__getitem__ = lambda self, k: {"entry_id": "e1", "count": 5}[k]
    analyzer._pool.fetch = AsyncMock(return_value=[row])
    result = await analyzer.get_top_entries("agent1", top_n=3)
    assert result == ["e1"]


async def test_get_patterns_returns_frequency(analyzer):
    row = MagicMock()
    row.__getitem__ = lambda self, k: {"entry_id": "e1", "count": 3, "last_accessed": "2025-01-01"}[
        k
    ]
    analyzer._pool.fetch = AsyncMock(return_value=[row])
    result = await analyzer.get_patterns("agent1", window_s=3600)
    assert len(result) == 1
    assert result[0]["entry_id"] == "e1"
