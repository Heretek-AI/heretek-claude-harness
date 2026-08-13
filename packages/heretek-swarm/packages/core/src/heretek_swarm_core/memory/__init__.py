"""
Heretek Swarm Memory Package

This package provides the memory subsystem built on Cognee (knowledge graph +
vector memory engine) plus access-pattern optimization and intelligent pre-fetching.

Public modules:
    cognee_reader   — Read-only async client for Cognee's search API.
    cognee_writer   — Write-path async client for Cognee's add/cognify API.
    mem0_backend    — Mem0ai embedded backend (Qdrant + OpenAI).
    store           — MemoryStore Protocol + get_default_store() resolver
                      (Phase 1.1 of PLAN.md; canonical entry point for new code).
    access_patterns — Access pattern analysis, tier classification, reporting.
    prefetcher      — LRU/LFU caches and pattern-based pre-fetch scheduling.
    eliza_memory    — Importance-decay memory manager (elizaOS pattern).
"""

from __future__ import annotations

import structlog

# ---------------------------------------------------------------------------
# Access-pattern analysis & tiering
# ---------------------------------------------------------------------------
from heretek_swarm_core.memory.access_patterns import (
    AccessPattern,
    AccessPatternAnalyzer,
    AccessPatternReport,
    AccessStatistics,
    AccessTier,
    MemoryAccessProfile,
    MemoryAccessRecord,
)

# ---------------------------------------------------------------------------
# Cognee-backed read/write clients
# ---------------------------------------------------------------------------
from heretek_swarm_core.memory.cognee_reader import CogneeMemoryReader
from heretek_swarm_core.memory.cognee_writer import CogneeMemoryWriter

# ---------------------------------------------------------------------------
# Mem0 backend
# ---------------------------------------------------------------------------
from heretek_swarm_core.memory.mem0_backend import MEM0_AVAILABLE, Mem0Backend, Mem0Config

# ---------------------------------------------------------------------------
# Canonical MemoryStore Protocol + resolver (Phase 1.1)
# ---------------------------------------------------------------------------
from heretek_swarm_core.memory.store import (
    MemoryEntry,
    MemoryStore,
    MemoryType,
    get_default_store,
    reset_default_store,
)

# ---------------------------------------------------------------------------
# Eliza-style importance-decay memory manager
# ---------------------------------------------------------------------------
from heretek_swarm_core.memory.eliza_memory import (
    ElizaMemoryEntry,
    MemoryManager,
    MemoryManagerConfig,
    create_memory_manager,
)

# ---------------------------------------------------------------------------
# Intelligent pre-fetching & caching
# ---------------------------------------------------------------------------
from heretek_swarm_core.memory.prefetcher import (
    IntelligentPrefetcher,
    LFUCache,
    LRUCache,
    PreFetchPriority,
    PreFetchRequest,
    PreFetchResult,
    PreFetchScheduler,
    PreFetchStrategy,
)

logger = structlog.get_logger(__name__)

__all__ = sorted(
    [
        # Access-pattern analysis
        "AccessPattern",
        "AccessPatternAnalyzer",
        "AccessPatternReport",
        "AccessStatistics",
        "AccessTier",
        # Cognee-backed clients
        "CogneeMemoryReader",
        "CogneeMemoryWriter",
        # Mem0 backend
        "MEM0_AVAILABLE",
        "Mem0Backend",
        "Mem0Config",
        # Canonical MemoryStore Protocol (Phase 1.1)
        "MemoryEntry",
        "MemoryStore",
        "MemoryType",
        "get_default_store",
        "reset_default_store",
        # Eliza-style memory manager
        "ElizaMemoryEntry",
        # Pre-fetching & caching
        "IntelligentPrefetcher",
        "LFUCache",
        "LRUCache",
        "MemoryAccessProfile",
        "MemoryAccessRecord",
        "MemoryManager",
        "MemoryManagerConfig",
        "PreFetchPriority",
        "PreFetchRequest",
        "PreFetchResult",
        "PreFetchScheduler",
        "PreFetchStrategy",
        "create_memory_manager",
    ]
)
