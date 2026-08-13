"""Tests for the memory package — Cognee-backed memory surface.

Validates CogneeMemoryReader, CogneeMemoryWriter, access-pattern
analysis, intelligent prefetching, and package-level exports.
"""

from __future__ import annotations

import os
from unittest.mock import patch

from heretek_swarm_core.memory.cognee_reader import CogneeMemoryReader
from heretek_swarm_core.memory.cognee_writer import CogneeMemoryWriter

# ---------------------------------------------------------------------------
# CogneeMemoryReader tests
# ---------------------------------------------------------------------------

class TestCogneeMemoryReader:
    """Tests for CogneeMemoryReader instantiation and graceful fallback."""

    def test_default_config(self):
        reader = CogneeMemoryReader()
        assert reader.api_url == "http://cognee:8000"
        assert reader.enabled is False
        assert reader.timeout_seconds == 5.0

    def test_custom_api_url(self):
        reader = CogneeMemoryReader(api_url="http://localhost:9000")
        assert reader.api_url == "http://localhost:9000"

    def test_custom_enabled(self):
        reader = CogneeMemoryReader(enabled=True)
        assert reader.enabled is True

    @patch.dict(os.environ, {"COGNEE_API_URL": "http://env-host:7777"})
    def test_env_overrides_default(self):
        reader = CogneeMemoryReader()
        assert reader.api_url == "http://env-host:7777"

    async def test_read_returns_empty_when_disabled(self):
        """When Cognee is disabled, read() must return [] without HTTP calls."""
        reader = CogneeMemoryReader(enabled=False)
        results = await reader.read("test query")
        assert results == []

    async def test_read_returns_empty_on_connection_error(self):
        """When Cognee is enabled but unreachable, read() must return []."""
        reader = CogneeMemoryReader(
            api_url="http://127.0.0.1:1",  # nothing listens here
            enabled=True,
            timeout_seconds=0.1,
        )
        results = await reader.read("test query")
        assert results == []

    async def test_health_false_when_disabled(self):
        reader = CogneeMemoryReader(enabled=False)
        assert await reader.health() is False

    def test_repr(self):
        reader = CogneeMemoryReader(api_url="http://x:1", enabled=True)
        r = repr(reader)
        assert "CogneeMemoryReader" in r
        assert "http://x:1" in r


# ---------------------------------------------------------------------------
# CogneeMemoryWriter tests
# ---------------------------------------------------------------------------

class TestCogneeMemoryWriter:
    """Tests for CogneeMemoryWriter instantiation and graceful fallback."""

    def test_default_config(self):
        writer = CogneeMemoryWriter()
        assert writer.api_url == "http://cognee:8000"
        assert writer.enabled is False
        assert writer.timeout_seconds == 10.0

    def test_custom_api_url(self):
        writer = CogneeMemoryWriter(api_url="http://cognee-write:8001")
        assert writer.api_url == "http://cognee-write:8001"

    def test_custom_enabled(self):
        writer = CogneeMemoryWriter(enabled=True)
        assert writer.enabled is True

    @patch.dict(os.environ, {"COGNEE_API_URL": "http://env-writer:5555"})
    def test_env_overrides_default(self):
        writer = CogneeMemoryWriter()
        assert writer.api_url == "http://env-writer:5555"

    async def test_store_returns_false_when_disabled(self):
        """When Cognee is disabled, store() must return False without HTTP."""
        writer = CogneeMemoryWriter(enabled=False)
        result = await writer.store("test content")
        assert result is False

    async def test_add_returns_false_when_disabled(self):
        writer = CogneeMemoryWriter(enabled=False)
        result = await writer.add("test")
        assert result is False

    async def test_cognify_returns_false_when_disabled(self):
        writer = CogneeMemoryWriter(enabled=False)
        result = await writer.cognify()
        assert result is False

    async def test_store_returns_false_on_connection_error(self):
        """When Cognee is enabled but unreachable, store() must return False."""
        writer = CogneeMemoryWriter(
            api_url="http://127.0.0.1:1",
            enabled=True,
            timeout_seconds=0.1,
        )
        result = await writer.store("test content")
        assert result is False

    async def test_health_false_when_disabled(self):
        writer = CogneeMemoryWriter(enabled=False)
        assert await writer.health() is False

    def test_repr(self):
        writer = CogneeMemoryWriter(api_url="http://x:1", enabled=False)
        r = repr(writer)
        assert "CogneeMemoryWriter" in r
        assert "http://x:1" in r


# ---------------------------------------------------------------------------
# Package-level import tests
# ---------------------------------------------------------------------------

class TestMemoryPackageExports:
    """Verify heretek_swarm.memory exports the correct public surface."""

    def test_cognee_reader_importable(self):
        from heretek_swarm_core.memory import CogneeMemoryReader as Reader
        assert Reader is CogneeMemoryReader

    def test_cognee_writer_importable(self):
        from heretek_swarm_core.memory import CogneeMemoryWriter as Writer
        assert Writer is CogneeMemoryWriter

    def test_access_pattern_analyzer_importable(self):
        from heretek_swarm_core.memory import AccessPatternAnalyzer as Analyzer
        assert Analyzer is not None

    def test_intelligent_prefetcher_importable(self):
        from heretek_swarm_core.memory import IntelligentPrefetcher as Fetcher
        assert Fetcher is not None

    def test_eliza_memory_importable(self):
        from heretek_swarm_core.memory import MemoryManager as Manager
        assert Manager is not None

    def test_legacy_dual_tier_memory_not_in_all(self):
        from heretek_swarm_core.memory import __all__ as exports
        assert "DualTierMemory" not in exports

    def test_legacy_memory_entry_not_in_all(self):
        # Phase 1.1 of PLAN.md introduced a NEW canonical
        # MemoryEntry dataclass as part of the MemoryStore
        # Protocol. The old legacy MemoryEntry (the
        # pre-Protocol dataclass) was removed; the new one
        # IS in __all__ by design. This test now asserts the
        # new entry is importable from the package.
        from heretek_swarm_core.memory import MemoryEntry as Entry
        from heretek_swarm_core.memory import __all__ as exports
        assert "MemoryEntry" in exports
        assert Entry is not None
        assert hasattr(Entry, "id")
        assert hasattr(Entry, "content")
        assert hasattr(Entry, "memory_type")

    def test_legacy_persistent_memory_not_in_all(self):
        from heretek_swarm_core.memory import __all__ as exports
        assert "PersistentMemory" not in exports

    def test_all_is_sorted(self):
        from heretek_swarm_core.memory import __all__ as exports
        assert exports == sorted(exports), "__all__ must be alphabetically sorted"
