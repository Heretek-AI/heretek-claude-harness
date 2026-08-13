"""
Heretek Swarm Memory Package

This package provides dual-tier memory architecture with:
- Ephemeral memory layer (fast, session-based with TTL)
- Persistent memory layer (long-term vector storage with mem0)
- Memory lineage tracking
- Memory Manager with importance-based decay
- Memory optimization (Session 43): Access patterns, pre-fetching, compression, tiering
"""

# Re-export from memory package for test compatibility
# Note: Using explicit imports to avoid shadowing

# Session 43: Memory Optimization Modules
import structlog

from heretek_swarm.memory.access_patterns import (
    AccessPattern,
    AccessPatternAnalyzer,
    AccessPatternReport,
    AccessStatistics,
    AccessTier,
    MemoryAccessProfile,
)

# Core type definitions (local import)
from heretek_swarm.memory.base import (
    DualTierMemory,
    DualTierMemorySystem,
    EphemeralMemory,
    MemoryEntry,
    MemoryQuery,
    MemorySystem,
    MemoryTier,
    MemoryType,
)
from heretek_swarm.memory.base import (
    PersistentMemory as BasePersistentMemory,
)
from heretek_swarm.memory.compression import (
    ColdDataCompressor,
    CompressedMemory,
    CompressionAlgorithm,
    CompressionConfig,
    CompressionLevel,
    CompressionResult,
    DecompressionResult,
)
from heretek_swarm.memory.eliza_memory import (
    ElizaMemoryEntry,
    MemoryManager,
    MemoryManagerConfig,
    create_memory_manager,
)
from heretek_swarm.memory.persistent import (
    Mem0Config,
    PersistentMemory,
    create_memory_store,
)
from heretek_swarm.memory.prefetcher import (
    IntelligentPrefetcher,
    LFUCache,
    LRUCache,
    PreFetchPriority,
    PreFetchRequest,
    PreFetchResult,
    PreFetchStrategy,
)
from heretek_swarm.memory.tiering import (
    MemoryTieringSystem,
    MigrationPolicy,
    MigrationRecord,
    TierConfig,
    TieredMemory,
    TieringStatistics,
)

logger = structlog.get_logger(__name__)

__all__ = [
    "AccessPattern",
    # Session 43: Memory Optimization
    "AccessPatternAnalyzer",
    "AccessPatternReport",
    "AccessStatistics",
    "AccessTier",
    "BasePersistentMemory",
    "ColdDataCompressor",
    "CompressedMemory",
    "CompressionAlgorithm",
    "CompressionConfig",
    "CompressionLevel",
    "CompressionResult",
    "DecompressionResult",
    "DualTierConfig",
    "DualTierMemory",
    "DualTierMemorySystem",
    # Eliza-style memory manager
    "ElizaMemoryEntry",
    "EmbeddingConfig",
    # Embeddings
    "EmbeddingService",
    "EphemeralConfig",
    "EphemeralMemory",
    # Memory stores (for tests)
    "EphemeralMemoryStore",
    "IntelligentPrefetcher",
    "LFUCache",
    "LRUCache",
    # Mem0 integration
    "Mem0Config",
    "MemoryAccessProfile",
    "MemoryEntry",
    "MemoryManager",
    "MemoryManagerConfig",
    "MemoryQuery",
    "MemoryResult",
    # Base classes
    "MemorySystem",
    "MemoryTier",

    "MemoryTier_Base",
    "MemoryTieringSystem",
    "MemoryType",
    "MigrationPolicy",
    "MigrationRecord",
    "PersistentConfig",
    "PersistentMemory",
    "PersistentMemoryStore",
    "PreFetchPriority",
    "PreFetchRequest",
    "PreFetchResult",
    "PreFetchStrategy",
    "TierConfig",
    "TieredMemory",
    "TieringStatistics",
    "create_memory_manager",
    "create_memory_store",
]

# Compatibility exports for tests
try:
    # Import our Mem0Backend wrapper from persistent.py
    from heretek_swarm.memory.persistent import Mem0Backend

    MEM0_AVAILABLE = True
except ImportError:
    MEM0_AVAILABLE = False
    Mem0Backend = None  # type: ignore
