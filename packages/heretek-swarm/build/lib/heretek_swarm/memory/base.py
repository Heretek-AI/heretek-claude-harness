"""
Memory System - Base implementation for dual-tier memory.

.. deprecated::
    This module is part of the custom in-memory memory wrapper
    stack that M-arch is replacing with Cognee. It remains in place
    for backward compatibility (see PLAN.md §M-arch PR #5) and will
    be deleted in a follow-up PR after 1 week of Cognee sidecar
    parity. New code should use the Cognee-backed classes:
      * :class:`heretek_swarm.memory.cognee_reader.CogneeMemoryReader`
        (read path — added in M-arch PR #2)
      * :class:`heretek_swarm.memory.cognee_writer.CogneeMemoryWriter`
        (write path — added in M-arch PR #5)

This module provides:
- Ephemeral memory layer (fast, session-based with TTL)
- Persistent memory layer (long-term vector storage)
- Memory lineage tracking
- State snapshot/rollback capabilities
"""

import contextlib
import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from enum import StrEnum
from typing import Any

import structlog

logger = structlog.get_logger("MemorySystem")


@dataclass  # noqa: RUF049
class MemoryTier(StrEnum):
    """Memory tier classification."""

    EPHEMERAL = "ephemeral"  # Redis - short-term, TTL-based
    PERSISTENT = "persistent"  # PostgreSQL/PGVector - long-term


class MemoryType(StrEnum):
    """Types of memory entries."""

    EPISODIC = "episodic"  # Event-based memories
    SEMANTIC = "semantic"  # Facts and knowledge
    PROCEDURAL = "procedural"  # Skills and procedures
    WORKING = "working"  # Current task context


@dataclass
class MemoryEntry:
    """
    A single memory entry.

    Attributes:
        id: Unique identifier
        agent_id: Agent that created this memory
        content: Memory content
        content_type: MIME type of content
        metadata: Additional metadata
        created_at: Creation timestamp
        expires_at: Expiration timestamp (for ephemeral memory)
        lineage: Parent message/memory IDs for provenance
        embedding: Optional vector embedding
        tags: Classification tags
        importance_score: Relevance score (0-1)
    """

    content: Any
    metadata: dict[str, Any] = field(default_factory=dict)
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    agent_id: str | None = None
    content_type: str = "text/plain"
    created_at: str = field(default_factory=lambda: datetime.now(UTC).isoformat())
    memory_type: Any = None
    tier: Any = None
    access_count: int = 0
    last_accessed_at: str | None = None
    expires_at: str | None = None
    lineage: list[str] = field(default_factory=list)
    embedding: list[float] | None = None
    tags: list[str] = field(default_factory=list)
    importance_score: float = 0.5

    def __post_init__(self) -> None:
        # types are defined in this module
        if self.memory_type is None:
            self.memory_type = MemoryType.EPISODIC
        if self.tier is None:
            self.tier = MemoryTier.PERSISTENT

    def touch(self) -> None:
        """Record an access."""
        self.access_count += 1
        self.last_accessed_at = datetime.now(UTC).isoformat()


@dataclass
class MemoryQuery:
    """
    Memory query parameters.

    Attributes:
        query_text: Text to search for
        filters: Metadata filters
        limit: Maximum results to return
        similarity_threshold: Minimum similarity score (for vector search)
        include_expired: Include expired entries
    """

    query_text: str | None = None
    filters: dict[str, Any] | None = None
    limit: int = 10
    similarity_threshold: float = 0.7
    include_expired: bool = False


class MemorySystem(ABC):
    """
    Abstract base class for memory systems.

    Provides dual-tier memory architecture with:
    - Ephemeral layer: Fast, session-based working memory with TTL
    - Persistent layer: Long-term vector-based storage with semantic search
    """

    def __init__(self, name: str | None = None) -> None:
        """
        Initialize the memory system.

        Args:
            name: Memory system name
        """
        self.name = name or "MemorySystem"
        self._initialized = False

    @abstractmethod
    async def initialize(self) -> None:
        """Initialize the memory system."""

    @abstractmethod
    async def store(
        self,
        content: dict[str, Any],
        metadata: dict[str, Any] | None = None,
        ttl: int | None = None,
        lineage: list[str] | None = None,
    ) -> MemoryEntry:
        """
        Store a memory entry.

        Args:
            content: Memory content
            metadata: Additional metadata
            ttl: Time to live in seconds (for ephemeral memory)
            lineage: Parent IDs for provenance tracking

        Returns:
            Stored memory entry
        """

    @abstractmethod
    async def retrieve(self, memory_id: str) -> MemoryEntry | None:
        """
        Retrieve a memory entry by ID.

        Args:
            memory_id: Memory identifier

        Returns:
            Memory entry or None
        """

    @abstractmethod
    async def query(self, query: MemoryQuery) -> list[MemoryEntry]:
        """
        Query memory entries.

        Args:
            query: Query parameters

        Returns:
            List of matching memory entries
        """

    @abstractmethod
    async def delete(self, memory_id: str) -> bool:
        """
        Delete a memory entry.

        Args:
            memory_id: Memory identifier

        Returns:
            True if deleted, False if not found
        """

    @abstractmethod
    async def close(self) -> None:
        """Close the memory system and release resources."""


class EphemeralMemory(MemorySystem):
    """
    Ephemeral memory layer with TTL-based expiration.

    Provides fast, in-memory storage for session-based working memory.
    """

    def __init__(
        self,
        name: str = "EphemeralMemory",
        max_size: int = 10000,
        default_ttl: int = 3600,
    ) -> None:
        """
        Initialize ephemeral memory.

        Args:
            name: Memory system name
            max_size: Maximum number of entries
            default_ttl: Default time to live in seconds
        """
        super().__init__(name)
        self.max_size = max_size
        self.default_ttl = default_ttl
        self._storage: dict[str, MemoryEntry] = {}
        self._index: dict[str, list[str]] = {}  # field -> [memory_ids]

    async def initialize(self) -> None:
        """Initialize the ephemeral memory system."""
        self._initialized = True
        logger.info(f"[{self.name}] Ephemeral memory initialized")

    async def store(
        self,
        content: dict[str, Any],
        metadata: dict[str, Any] | None = None,
        ttl: int | None = None,
        lineage: list[str] | None = None,
    ) -> MemoryEntry:
        """
        Store a memory entry with TTL.

        Args:
            content: Memory content
            metadata: Additional metadata
            ttl: Time to live in seconds
            lineage: Parent IDs for provenance tracking

        Returns:
            Stored memory entry
        """
        if not self._initialized:
            await self.initialize()

        memory_id = str(uuid.uuid4())
        now = datetime.now(UTC)

        # Calculate expiration
        ttl = ttl or self.default_ttl
        expires_at = (now + timedelta(seconds=ttl)).isoformat()

        entry = MemoryEntry(
            id=memory_id,
            content=content,
            metadata=metadata or {},
            created_at=now.isoformat(),
            expires_at=expires_at,
            lineage=lineage or [],
        )

        # Check size limit
        if len(self._storage) >= self.max_size:
            await self._evict_oldest()

        # Store entry
        self._storage[memory_id] = entry

        # Update indexes
        await self._update_indexes(entry)

        logger.debug(f"[{self.name}] Stored memory {memory_id}")

        return entry

    async def retrieve(self, memory_id: str) -> MemoryEntry | None:
        """Retrieve a memory entry by ID."""
        entry = self._storage.get(memory_id)

        if entry:  # noqa: SIM102
            # Check expiration
            if self._is_expired(entry):
                await self.delete(memory_id)
                return None

        return entry

    async def query(self, query: MemoryQuery) -> list[MemoryEntry]:
        """
        Query memory entries with filters.

        Args:
            query: Query parameters

        Returns:
            List of matching memory entries
        """
        results = []

        for entry in self._storage.values():
            # Skip expired entries
            if not query.include_expired and self._is_expired(entry):
                continue

            # Apply filters
            if query.filters and not self._matches_filters(entry, query.filters):
                continue

            # Apply text search
            if query.query_text and not self._matches_text(entry, query.query_text):
                continue

            results.append(entry)

            # Apply limit
            if len(results) >= query.limit:
                break

        return results

    async def delete(self, memory_id: str) -> bool:
        """Delete a memory entry."""
        if memory_id not in self._storage:
            return False

        entry = self._storage[memory_id]
        del self._storage[memory_id]

        # Remove from indexes
        await self._remove_from_indexes(entry)

        logger.debug(f"[{self.name}] Deleted memory {memory_id}")

        return True

    async def close(self) -> None:
        """Close the ephemeral memory system."""
        self._storage.clear()
        self._index.clear()
        self._initialized = False
        logger.info(f"[{self.name}] Ephemeral memory closed")

    async def _evict_oldest(self) -> None:
        """Evict the oldest entry."""
        if not self._storage:
            return

        oldest_id = min(
            self._storage.keys(),
            key=lambda k: self._storage[k].created_at,
        )
        await self.delete(oldest_id)

    def _is_expired(self, entry: MemoryEntry) -> bool:
        """Check if an entry is expired."""
        if not entry.expires_at:
            return False

        expires_at = datetime.fromisoformat(entry.expires_at)
        return datetime.now(UTC) > expires_at

    def _matches_filters(
        self,
        entry: MemoryEntry,
        filters: dict[str, Any],
    ) -> bool:
        """Check if entry matches filters."""
        for key, value in filters.items():
            entry_value = entry.metadata.get(key)
            if entry_value != value:
                return False
        return True

    def _matches_text(self, entry: MemoryEntry, text: str) -> bool:
        """Check if entry contains text."""
        # Simple text search in content
        content_str = str(entry.content).lower()
        return text.lower() in content_str

    async def _update_indexes(self, entry: MemoryEntry) -> None:
        """Update indexes for an entry."""
        # Index by memory type
        memory_type = entry.metadata.get("type", "default")
        if memory_type not in self._index:
            self._index[memory_type] = []
        self._index[memory_type].append(entry.id)

        # Index by agent ID
        agent_id = entry.metadata.get("agent_id")
        if agent_id:
            if "agent:" + agent_id not in self._index:
                self._index["agent:" + agent_id] = []
            self._index["agent:" + agent_id].append(entry.id)

    async def _remove_from_indexes(self, entry: MemoryEntry) -> None:
        """Remove entry from indexes."""
        memory_type = entry.metadata.get("type", "default")
        if memory_type in self._index:
            with contextlib.suppress(ValueError):
                self._index[memory_type].remove(entry.id)

        agent_id = entry.metadata.get("agent_id")
        if agent_id:
            key = "agent:" + agent_id
            if key in self._index:
                with contextlib.suppress(ValueError):
                    self._index[key].remove(entry.id)

    def get_statistics(self) -> dict[str, Any]:
        """Get memory statistics."""
        datetime.now(UTC)
        expired_count = sum(1 for entry in self._storage.values() if self._is_expired(entry))

        return {
            "total_entries": len(self._storage),
            "expired_entries": expired_count,
            "active_entries": len(self._storage) - expired_count,
            "max_size": self.max_size,
            "utilization": len(self._storage) / self.max_size,
            "index_count": len(self._index),
        }


class PersistentMemory(MemorySystem):
    """
    Persistent memory layer with vector storage.

    Provides long-term storage with semantic search capabilities.
    This is a stub implementation - full implementation would use
    PGVector or similar vector database.
    """

    def __init__(
        self,
        name: str = "PersistentMemory",
        connection_string: str | None = None,
    ) -> None:
        """
        Initialize persistent memory.

        Args:
            name: Memory system name
            connection_string: Database connection string
        """
        super().__init__(name)
        self.connection_string = connection_string
        self._storage: dict[str, MemoryEntry] = {}

    async def initialize(self) -> None:
        """Initialize the persistent memory system."""
        # In a full implementation, this would connect to the database
        self._initialized = True
        logger.info(f"[{self.name}] Persistent memory initialized")

    async def store(
        self,
        content: dict[str, Any],
        metadata: dict[str, Any] | None = None,
        ttl: int | None = None,  # noqa: ARG002
        lineage: list[str] | None = None,
    ) -> MemoryEntry:
        """Store a memory entry (no TTL for persistent memory)."""
        if not self._initialized:
            await self.initialize()

        memory_id = str(uuid.uuid4())
        now = datetime.now(UTC)

        entry = MemoryEntry(
            id=memory_id,
            content=content,
            metadata=metadata or {},
            created_at=now.isoformat(),
            expires_at=None,  # No expiration for persistent memory
            lineage=lineage or [],
        )

        # In a full implementation, this would store to database
        self._storage[memory_id] = entry

        logger.debug(f"[{self.name}] Stored persistent memory {memory_id}")

        return entry

    async def retrieve(self, memory_id: str) -> MemoryEntry | None:
        """Retrieve a memory entry by ID."""
        return self._storage.get(memory_id)

    async def query(self, query: MemoryQuery) -> list[MemoryEntry]:
        """
        Query memory entries with optional vector similarity.

        In a full implementation, this would use PGVector for
        semantic search.
        """
        results = []

        for entry in self._storage.values():
            # Apply filters
            if query.filters and not self._matches_filters(entry, query.filters):
                continue

            results.append(entry)

            if len(results) >= query.limit:
                break

        return results

    async def delete(self, memory_id: str) -> bool:
        """Delete a memory entry."""
        if memory_id not in self._storage:
            return False

        del self._storage[memory_id]
        logger.debug(f"[{self.name}] Deleted persistent memory {memory_id}")

        return True

    async def close(self) -> None:
        """Close the persistent memory system."""
        # In a full implementation, this would close DB connections
        self._storage.clear()
        self._initialized = False
        logger.info(f"[{self.name}] Persistent memory closed")

    def _matches_filters(
        self,
        entry: MemoryEntry,
        filters: dict[str, Any],
    ) -> bool:
        """Check if entry matches filters."""
        for key, value in filters.items():
            entry_value = entry.metadata.get(key)
            if entry_value != value:
                return False
        return True

    async def store_embedding(
        self,
        memory_id: str,
        embedding: list[float],
    ) -> bool:
        """
        Store/update embedding for a memory entry.

        Args:
            memory_id: Memory identifier
            embedding: Vector embedding

        Returns:
            True if successful
        """
        if memory_id not in self._storage:
            return False

        self._storage[memory_id].embedding = embedding
        return True

    async def semantic_search(
        self,
        query_embedding: list[float],
        limit: int = 10,
        threshold: float = 0.7,
    ) -> list[tuple[MemoryEntry, float]]:
        """
        Perform semantic search using vector similarity.

        Args:
            query_embedding: Query vector
            limit: Maximum results
            threshold: Minimum similarity threshold

        Returns:
            List of (entry, similarity_score) tuples
        """
        # Stub implementation - would use PGVector in production
        results = []

        for entry in self._storage.values():
            if entry.embedding:
                # Cosine similarity
                similarity = self._cosine_similarity(
                    query_embedding,
                    entry.embedding,
                )
                if similarity >= threshold:
                    results.append((entry, similarity))

        # Sort by similarity
        results.sort(key=lambda x: x[1], reverse=True)

        return results[:limit]

    def _cosine_similarity(
        self,
        vec1: list[float],
        vec2: list[float],
    ) -> float:
        """Calculate cosine similarity between two vectors."""
        if len(vec1) != len(vec2):
            return 0.0

        dot_product = sum(a * b for a, b in zip(vec1, vec2, strict=False))
        norm1 = sum(a * a for a in vec1) ** 0.5
        norm2 = sum(b * b for b in vec2) ** 0.5

        if norm1 == 0 or norm2 == 0:
            return 0.0

        return dot_product / (norm1 * norm2)


class DualTierMemory:
    """
    Dual-tier memory system combining ephemeral and persistent layers.

    Provides unified interface for both memory types with automatic
    tiering based on TTL and access patterns.
    """

    def __init__(
        self,
        ephemeral: EphemeralMemory | None = None,
        persistent: PersistentMemory | None = None,
        ephemeral_config: dict[str, Any] | None = None,
        persistent_config: dict[str, Any] | None = None,
    ) -> None:
        """
        Initialize dual-tier memory.

        Args:
            ephemeral: Ephemeral memory instance (takes precedence if both ephemer* and config provided)  # noqa: E501
            persistent: Persistent memory instance (takes precedence if both persistent and config provided)  # noqa: E501
            ephemeral_config: Config dict with keys like ttl_seconds for constructing EphemeralMemory  # noqa: E501
            persistent_config: Config dict with keys like connection_string for constructing PersistentMemory  # noqa: E501
        """
        if ephemeral is not None:
            self.ephemeral = ephemeral
        elif ephemeral_config is not None:
            self.ephemeral = EphemeralMemory(
                default_ttl=ephemeral_config.get("ttl_seconds", 3600),
            )
        else:
            self.ephemeral = EphemeralMemory()

        if persistent is not None:
            self.persistent = persistent
        elif persistent_config is not None:
            self.persistent = PersistentMemory(
                connection_string=persistent_config.get("connection_string"),
            )
        else:
            self.persistent = PersistentMemory()
        self._initialized = False

    async def initialize(self) -> None:
        """Initialize both memory tiers."""
        await self.ephemeral.initialize()
        await self.persistent.initialize()
        self._initialized = True
        logger.info("Dual-tier memory initialized")

    async def store(
        self,
        content: dict[str, Any],
        metadata: dict[str, Any] | None = None,
        ttl: int | None = None,
        lineage: list[str] | None = None,
        persistent: bool = False,
    ) -> MemoryEntry:
        """
        Store a memory entry in appropriate tier.

        Args:
            content: Memory content
            metadata: Additional metadata
            ttl: Time to live in seconds
            lineage: Parent IDs for provenance tracking
            persistent: Force storage in persistent tier

        Returns:
            Stored memory entry
        """
        if not self._initialized:
            await self.initialize()

        if persistent or ttl is None:
            return await self.persistent.store(content, metadata, ttl, lineage)
        return await self.ephemeral.store(content, metadata, ttl, lineage)

    async def retrieve(self, memory_id: str) -> MemoryEntry | None:
        """
        Retrieve a memory entry from either tier.

        Args:
            memory_id: Memory identifier

        Returns:
            Memory entry or None
        """
        # Try ephemeral first
        entry = await self.ephemeral.retrieve(memory_id)
        if entry:
            return entry

        # Try persistent
        return await self.persistent.retrieve(memory_id)

    async def query(
        self,
        query_text: str | None = None,
        filters: dict[str, Any] | None = None,
        limit: int = 10,
        include_persistent: bool = True,
    ) -> list[MemoryEntry]:
        """
        Query both memory tiers.

        Args:
            query_text: Text to search for
            filters: Metadata filters
            limit: Maximum results
            include_persistent: Include persistent tier results

        Returns:
            List of matching memory entries
        """
        from heretek_swarm.memory.base import MemoryQuery

        mq = MemoryQuery(
            query_text=query_text,
            filters=filters,
            limit=limit,
        )

        results = await self.ephemeral.query(mq)

        if include_persistent:
            persistent_results = await self.persistent.query(mq)
            results.extend(persistent_results)

        return results[:limit]

    async def close(self) -> None:
        """Close both memory tiers."""
        await self.ephemeral.close()
        await self.persistent.close()
        self._initialized = False
        logger.info("Dual-tier memory closed")

    def get_statistics(self) -> dict[str, Any]:
        """Get combined statistics for both tiers."""
        ephemeral_stats = self.ephemeral.get_statistics()
        persistent_stats = {
            "persistent_total": len(self.persistent._storage),  # noqa: SLF001
        }

        return {
            "ephemeral": ephemeral_stats,
            "persistent": persistent_stats,
            "combined_total": ephemeral_stats["total_entries"]
            + persistent_stats["persistent_total"],
        }

    async def run_maintenance(self) -> dict[str, Any]:
        """
        Run maintenance tasks on both memory tiers.

        Cleans up expired entries from ephemeral memory.

        Returns:
            Maintenance statistics
        """
        if not self._initialized:
            await self.initialize()

        maintenance_stats = {
            "ephemeral_evicted": 0,
            "persistent_vacuumed": False,
        }

        # Evict expired entries from ephemeral
        ephemeral_storage = getattr(self.ephemeral, "_storage", {})
        expired_ids = [
            mid for mid, entry in ephemeral_storage.items() if self.ephemeral._is_expired(entry)  # noqa: SLF001
        ]
        for mid in expired_ids:
            await self.ephemeral.delete(mid)
            maintenance_stats["ephemeral_evicted"] += 1

        logger.debug(
            "memory_maintenance_completed",
            evicted=maintenance_stats["ephemeral_evicted"],
        )

        return maintenance_stats


class DualTierMemorySystem:
    """Dual-tier memory system stub for test compatibility."""

    def __init__(self, ephemeral_config=None, persistent_config=None):
        self.ephemeral_config = ephemeral_config
        self.persistent_config = persistent_config

    async def store(self, _content: str, _tier: str = "ephemeral") -> str:
        """Store content in memory."""
        return "memory_id"

    async def query(self, _query: str, _top_k: int = 5) -> list:
        """Query memory."""
        return []
