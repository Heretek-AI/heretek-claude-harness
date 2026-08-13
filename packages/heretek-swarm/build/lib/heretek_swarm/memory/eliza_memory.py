"""
Memory Manager with importance-based decay (elizaOS pattern).

This module implements the Eliza-style memory hierarchy with:
- Short-term memory: Fast, ephemeral storage (working memory)
- Long-term memory: Persistent storage with semantic embeddings (mem0)
- Working memory: Active contexts for current tasks

Features:
- Importance-based memory decay over time
- Automatic promotion from short-term to long-term based on importance
- Merged ranking by effective_importance when recalling

Reference: elizaOS/eliza/packages/core/memory/
Based on: MiniMax Audit lines 244-337
"""

import math
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

import structlog

logger = structlog.get_logger("MemoryManager")


# Decay constants
DEFAULT_DECAY_RATE = 0.01  # Default decay per hour
MIN_IMPORTANCE = 0.1  # Minimum importance threshold
PROMOTION_THRESHOLD = 0.7  # Threshold for auto-promotion to long-term
RECALL_LIMIT = 10  # Default recall limit


@dataclass
class ElizaMemoryEntry:
    """
    A memory entry with decay tracking.

    Attributes:
        id: Unique identifier
        content: Memory content text
        agent_id: Agent that created this memory
        importance: Initial importance (0-1)
        decay_rate: How fast importance decays per hour
        created_at: Creation timestamp
        last_accessed: Last access timestamp
        access_count: Number of times accessed
        memory_type: Type - 'working', 'short_term', 'long_term'
        tags: Optional tags for filtering
        metadata: Additional metadata
    """

    id: str
    content: str
    agent_id: str
    importance: float = 0.5
    decay_rate: float = DEFAULT_DECAY_RATE
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    last_accessed: datetime = field(default_factory=lambda: datetime.now(UTC))
    access_count: int = 0
    memory_type: str = "short_term"  # working, short_term, long_term
    tags: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def effective_importance(self) -> float:
        """
        Calculate effective importance with decay.

        Returns:
            Importance adjusted for time elapsed since creation
        """
        # Hours since creation
        hours_elapsed = (datetime.now(UTC) - self.created_at).total_seconds() / 3600

        # Decay formula: importance * e^(-decay_rate * hours)
        decayed = self.importance * math.exp(-self.decay_rate * hours_elapsed)

        # Boost for recent access
        if self.access_count > 0:
            hours_since_access = (datetime.now(UTC) - self.last_accessed).total_seconds() / 3600
            access_boost = min(0.1, self.access_count * 0.02 * math.exp(-hours_since_access))
            decayed += access_boost

        return max(MIN_IMPORTANCE, min(1.0, decayed))

    def touch(self) -> None:
        """Update access time and increment count."""
        self.last_accessed = datetime.now(UTC)
        self.access_count += 1


@dataclass
class MemoryManagerConfig:
    """Configuration for Memory Manager."""

    # Short-term memory
    short_term_max_size: int = 100
    short_term_ttl_seconds: int = 3600

    # Decay settings
    default_decay_rate: float = DEFAULT_DECAY_RATE
    promotion_threshold: float = PROMOTION_THRESHOLD

    # Long-term memory (mem0)
    use_mem0: bool = True
    mem0_host: str = "localhost"
    mem0_port: int = 6333

    # Recall settings
    recall_limit: int = RECALL_LIMIT
    min_relevance: float = MIN_IMPORTANCE


class MemoryManager:
    """
    Memory Manager with three-tier storage and decay.

    Tiers:
    - working: Active context for current task (in-memory)
    - short_term: Recent memories with decay (in-memory with TTL)
    - long_term: Persistent memories with semantic embeddings (mem0)

    Features:
    - Automatic tier selection based on importance
    - Importance decay over time
    - Auto-promotion to long-term for important memories
    - Merged recall across all tiers
    """

    def __init__(
        self,
        config: MemoryManagerConfig | None = None,
        agent_id: str = "default",
    ) -> None:
        """
        Initialize Memory Manager.

        Args:
            config: Configuration options
            agent_id: Default agent identifier
        """
        self.config = config or MemoryManagerConfig()
        self.agent_id = agent_id

        # Storage tiers
        self._working: dict[str, ElizaMemoryEntry] = {}  # id -> entry
        self._short_term: dict[str, ElizaMemoryEntry] = {}  # id -> entry


        self._mem0 = None
        self._mem0_initialized = False

        # Cache for recall results
        self._recall_cache: dict[str, list[ElizaMemoryEntry]] = {}
        self._cache_ttl_seconds = 60

        self._initialized = False

    async def initialize(self) -> None:
        """Initialize the memory manager."""
        if self._initialized:
            return

        # Initialize mem0 if configured
        if self.config.use_mem0:
            try:
                from heretek_swarm.memory.persistent import PersistentMemory

                # Note: mem0 requires OpenAI API key, so we make it optional
                # If no key, we'll fall back to in-memory storage
                self._mem0 = PersistentMemory(user_id=self.agent_id)
                logger.info("memory_manager_initialized", use_mem0=True, agent_id=self.agent_id)
            except Exception as e:
                logger.warning("mem0_init_failed_falling_back", error=str(e))
                self._mem0 = None
        else:
            self._mem0 = None

        self._initialized = True
        logger.info(
            "memory_manager_initialized",
            use_mem0=self.config.use_mem0 and self._mem0 is not None,
            agent_id=self.agent_id,
        )

    async def remember(
        self,
        content: str,
        agent_id: str | None = None,
        importance: float = 0.5,
        decay_rate: float | None = None,
        memory_type: str | None = None,
        tags: list[str] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> ElizaMemoryEntry:
        """
        Store a memory with automatic tier selection.

        Args:
            content: Memory content text
            agent_id: Agent identifier (defaults to self.agent_id)
            importance: Importance score 0-1
            decay_rate: Custom decay rate (uses config default if None)
            memory_type: Force specific tier - 'working', 'short_term', 'long_term'
            tags: Optional tags
            metadata: Additional metadata

        Returns:
            Created memory entry

        The memory is automatically placed in the appropriate tier:
        - working: If memory_type='working' or importance > 0.9
        - short_term: If importance >= promotion_threshold (may be promoted later)
        - long_term: If memory_type='long_term' or importance > promotion_threshold
        """
        if not self._initialized:
            await self.initialize()

        import uuid

        agent_id = agent_id or self.agent_id
        decay_rate = decay_rate or self.config.default_decay_rate
        entry_id = str(uuid.uuid4())

        entry = ElizaMemoryEntry(
            id=entry_id,
            content=content,
            agent_id=agent_id,
            importance=importance,
            decay_rate=decay_rate,
            memory_type=memory_type or "short_term",
            tags=tags or [],
            metadata=metadata or {},
        )

        # Determine tier based on importance
        if memory_type:
            entry.memory_type = memory_type
        elif importance > 0.9:
            entry.memory_type = "working"
        elif importance > self.config.promotion_threshold:
            entry.memory_type = "long_term"

        # Store in appropriate tier
        if entry.memory_type == "working":
            self._working[entry_id] = entry
        elif entry.memory_type == "long_term":
            # Store in long-term (mem0) if available
            if self._mem0 and self._mem0.is_initialized():
                await self._mem0.store(
                    content=content,
                    user_id=agent_id,
                    agent_id=agent_id,
                    metadata={
                        "entry_id": entry_id,
                        "importance": importance,
                        "decay_rate": decay_rate,
                        **metadata,
                    },
                )
            # Also cache locally
            self._short_term[entry_id] = entry
        else:
            self._short_term[entry_id] = entry

        logger.debug(
            "memory_remembered",
            entry_id=entry_id,
            memory_type=entry.memory_type,
            importance=importance,
            agent_id=agent_id,
        )

        # Check for promotion to long-term
        await self._check_promotion(entry)

        return entry

    async def recall(
        self,
        query: str | None = None,
        agent_id: str | None = None,
        limit: int | None = None,
        min_importance: float = MIN_IMPORTANCE,
    ) -> list[ElizaMemoryEntry]:
        """
        Recall memories with merged ranking.

        Args:
            query: Semantic search query (for long-term search)
            agent_id: Filter by agent
            limit: Maximum results (defaults to config)
            min_importance: Minimum effective importance

        Returns:
            List of memories sorted by effective_importance
        """
        if not self._initialized:
            await self.initialize()

        agent_id = agent_id or self.agent_id
        limit = limit or self.config.recall_limit
        datetime.now(UTC)

        results: list[tuple[float, ElizaMemoryEntry]] = []

        # Collect from working memory
        for entry in self._working.values():
            if agent_id and entry.agent_id != agent_id:
                continue
            effective = entry.effective_importance()
            if effective >= min_importance:
                results.append((effective, entry))

        # Collect from short-term memory
        for entry in self._short_term.values():
            if agent_id and entry.agent_id != agent_id:
                continue
            effective = entry.effective_importance()
            if effective >= min_importance:
                results.append((effective, entry))

        # Search long-term (mem0) if query provided
        if query and self._mem0 and self._mem0.is_initialized():
            long_term_results = await self._mem0.search(
                query=query,
                user_id=agent_id,
                limit=limit,
            )
            for mem in long_term_results:
                # Check metadata for entry info
                meta = mem.get("metadata", {})
                entry_id = meta.get("entry_id")
                if entry_id and entry_id in self._short_term:
                    entry = self._short_term[entry_id]
                    effective = entry.effective_importance()
                    results.append((effective, entry))

        # Sort by effective importance (descending)
        results.sort(key=lambda x: x[0], reverse=True)

        # Return top results
        return [entry for _, entry in results[:limit]]

    async def get_working_context(
        self,
        agent_id: str | None = None,
        limit: int = 5,
    ) -> list[ElizaMemoryEntry]:
        """
        Get working memory context for current task.

        Args:
            agent_id: Filter by agent
            limit: Maximum results

        Returns:
            Working memory entries sorted by effective importance
        """
        agent_id = agent_id or self.agent_id

        working = [e for e in self._working.values() if e.agent_id == agent_id]

        # Sort by effective importance
        working.sort(key=lambda e: e.effective_importance(), reverse=True)

        return working[:limit]

    async def touch(self, entry_id: str) -> bool:
        """
        Touch a memory to update access time and boost importance.

        Args:
            entry_id: Memory entry ID

        Returns:
            True if found and touched
        """
        # Check working
        if entry_id in self._working:
            self._working[entry_id].touch()
            return True

        # Check short-term
        if entry_id in self._short_term:
            self._short_term[entry_id].touch()
            return True

        return False

    async def forget(self, entry_id: str) -> bool:
        """
        Delete a memory.

        Args:
            entry_id: Memory entry ID

        Returns:
            True if found and deleted
        """
        # Check working
        if entry_id in self._working:
            del self._working[entry_id]
            logger.debug("memory_forgotten", entry_id=entry_id, tier="working")
            return True

        # Check short-term
        if entry_id in self._short_term:
            entry = self._short_term[entry_id]

            # Delete from long-term if it was stored there
            if entry.memory_type == "long_term" and self._mem0:
                await self._mem0.delete(entry_id)

            del self._short_term[entry_id]
            logger.debug("memory_forgotten", entry_id=entry_id, tier="short_term")
            return True

        return False

    async def cleanup_expired(self) -> int:
        """
        Clean up expired short-term memories.

        Returns:
            Number of memories cleaned up
        """
        now = datetime.now(UTC)
        cleaned = 0
        expired_ids = []

        for entry_id, entry in self._short_term.items():
            # Check if past TTL
            age = (now - entry.created_at).total_seconds()
            if age > self.config.short_term_ttl_seconds:
                expired_ids.append(entry_id)

        for entry_id in expired_ids:
            del self._short_term[entry_id]
            cleaned += 1

        if cleaned > 0:
            logger.info("expired_memories_cleaned", count=cleaned)

        return cleaned

    def get_statistics(self) -> dict[str, Any]:
        """Get memory statistics."""
        total_short_term = sum(e.effective_importance() for e in self._short_term.values())
        total_working = sum(e.effective_importance() for e in self._working.values())

        return {
            "working_count": len(self._working),
            "short_term_count": len(self._short_term),
            "total_effective_importance_working": total_working,
            "total_effective_importance_short_term": total_short_term,
            "agent_id": self.agent_id,
        }

    async def close(self) -> None:
        """Close the memory manager."""
        if self._mem0:
            await self._mem0.close()
        self._working.clear()
        self._short_term.clear()
        self._initialized = False
        logger.info("memory_manager_closed")

    async def _check_promotion(self, entry: ElizaMemoryEntry) -> None:
        """
        Check if memory should be promoted to long-term.

        Args:
            entry: Memory entry to check
        """
        if entry.memory_type != "short_term":
            return

        # Check if importance is high enough for promotion
        if entry.effective_importance() >= self.config.promotion_threshold:
            entry.memory_type = "long_term"

            # Store in mem0 if available
            if self._mem0 and self._mem0.is_initialized():
                await self._mem0.store(
                    content=entry.content,
                    user_id=entry.agent_id,
                    agent_id=entry.agent_id,
                    metadata={
                        "entry_id": entry.id,
                        "importance": entry.importance,
                        "decay_rate": entry.decay_rate,
                        **entry.metadata,
                    },
                )

            logger.debug(
                "memory_promoted",
                entry_id=entry.id,
                new_type="long_term",
                agent_id=entry.agent_id,
            )


async def create_memory_manager(
    agent_id: str = "default",
    use_mem0: bool = True,
) -> MemoryManager:
    """
    Factory function to create a Memory Manager.

    Args:
        agent_id: Agent identifier
        use_mem0: Whether to use mem0 for long-term storage

    Returns:
        Configured MemoryManager instance
    """
    config = MemoryManagerConfig(
        use_mem0=use_mem0,
    )
    manager = MemoryManager(config=config, agent_id=agent_id)
    await manager.initialize()
    return manager
