"""
Persistent Memory Store with mem0 Integration.

.. deprecated::
    This module wraps mem0 for long-term storage. It is being replaced
    by Cognee as part of M-arch PR #5 (see PLAN.md §M-arch). It remains
    in place for backward compatibility and will be deleted in a
    follow-up PR after 1 week of Cognee sidecar parity. New code
    should use :class:`heretek_swarm.memory.cognee_reader.CogneeMemoryReader`
    and :class:`heretek_swarm.memory.cognee_writer.CogneeMemoryWriter`.

Provides long-term storage with semantic search using mem0's unified memory API.
Supports multiple vector stores (Qdrant, PostgreSQL, Chroma) and LLM providers.

Reference: mem0ai library for unified memory management
"""

import os
import time
from dataclasses import dataclass, field
from typing import Any

import structlog

from heretek_swarm.memory.base import MemoryEntry, MemoryQuery

logger = structlog.get_logger("PersistentMemory")


@dataclass
class Mem0Config:
    """Configuration for mem0 memory store."""

    # Vector store provider
    vector_store_provider: str = "qdrant"

    # Qdrant configuration
    qdrant_host: str | None = field(default_factory=lambda: os.getenv("QDRANT_HOST"))
    qdrant_port: int = field(default_factory=lambda: int(os.getenv("QDRANT_PORT", "6333")))
    qdrant_collection: str = "heretek_swarm_memories"

    def __post_init__(self) -> None:
        """Validate required configuration."""
        if not self.qdrant_host:
            raise RuntimeError(
                "QDRANT_HOST is required. Set it to the Qdrant host address or use docker compose."
            )
        if self.vector_store_provider != "qdrant":
            raise ValueError(f"Unsupported vector store provider: {self.vector_store_provider}")

    # LLM provider
    llm_provider: str = "openai"
    llm_model: str = field(default_factory=lambda: os.getenv("LLM_MODEL", "gpt-4o"))
    openai_api_key: str | None = field(default_factory=lambda: os.getenv("OPENAI_API_KEY"))

    # Embedder configuration
    embedder_provider: str = "openai"
    embedder_model: str = field(
        default_factory=lambda: os.getenv("EMBEDDER_MODEL", "text-embedding-3-small")
    )

    # PostgreSQL fallback (if using pgvector)
    postgres_host: str = field(default_factory=lambda: os.getenv("POSTGRES_HOST"))
    postgres_port: int = field(default_factory=lambda: int(os.getenv("POSTGRES_PORT", "5432")))
    postgres_user: str = field(default_factory=lambda: os.getenv("POSTGRES_USER", "heretek"))
    postgres_password: str = field(
        default_factory=lambda: os.getenv("POSTGRES_PASSWORD", "heretek")
    )
    postgres_database: str = field(default_factory=lambda: os.getenv("POSTGRES_DB", "heretek"))

    def to_dict(self) -> dict[str, Any]:
        """Convert config to mem0 format."""
        return self.get_mem0_config()

    def get_mem0_config(self) -> dict[str, Any]:
        """Convert config to mem0 format (alias for to_dict)."""
        return {
            "vector_store": {
                "provider": self.vector_store_provider,
                "config": {
                    "host": self.qdrant_host,
                    "port": self.qdrant_port,
                    "collection_name": self.qdrant_collection,
                },
            },
            "llm": {
                "provider": self.llm_provider,
                "config": {
                    "model": self.llm_model,
                    "api_key": self.openai_api_key,
                },
            },
            "embedder": {
                "provider": self.embedder_provider,
                "config": {
                    "model": self.embedder_model,
                },
            },
        }


class PersistentMemory:
    """
    Persistent memory store using mem0 for semantic memory management.

    Features:
    - Long-term storage with semantic embeddings
    - Vector similarity search via configurable provider
    - Automatic memory organization and retrieval
    - Support for multiple users/agents

    Note: Requires Qdrant or other vector store to be running.
    """

    def __init__(
        self,
        config: Mem0Config | None = None,
        user_id: str = "default",
    ) -> None:
        """
        Initialize persistent memory store.

        Args:
            config: Mem0 configuration
            user_id: Default user identifier for memories
        """
        self.config = config or Mem0Config()
        self.user_id = user_id
        self._memory = None
        self._initialized = False

    async def initialize(self) -> None:
        """Initialize the mem0 memory instance."""
        if self._initialized:
            return

        try:
            from mem0 import Memory

            self._memory = Memory.from_config(self.config.to_dict())
            self._initialized = True

            logger.info(
                "persistent_memory_initialized",
                provider=self.config.vector_store_provider,
                collection=self.config.qdrant_collection,
            )

        except ImportError:
            logger.error("mem0 package not installed. Install with: pip install mem0ai")
            raise
        except Exception as e:
            logger.error("failed_to_initialize_memory", error=str(e))
            raise

    async def store(
        self,
        content: str,
        user_id: str | None = None,
        agent_id: str | None = None,
        metadata: dict[str, Any] | None = None,
        org_id: str | None = None,
        project_id: str | None = None,
        session_id: str | None = None,
        scope: str | None = None,
    ) -> str:
        """
        Store a memory entry with semantic embedding.

        Args:
            content: Memory content text
            user_id: User identifier (defaults to self.user_id)
            agent_id: Agent identifier for the memory
            metadata: Additional metadata
            org_id: Organization identifier
            project_id: Project identifier
            session_id: Session identifier
            scope: Water's hierarchy scope (org, project, user, session, auto_learned)

        Returns:
            Memory ID if successful, empty string otherwise
        """
        if not self._initialized:
            await self.initialize()

        user_id = user_id or self.user_id
        meta = {"agent_id": agent_id} if agent_id else {}
        if org_id:
            meta["org_id"] = org_id
        if project_id:
            meta["project_id"] = project_id
        if session_id:
            meta["session_id"] = session_id
        if scope:
            meta["scope"] = scope

        if metadata:
            meta.update(metadata)

        try:
            result = self._memory.add(
                content,
                user_id=user_id,
                metadata=meta,
            )
            memory_id = result.get("id", "")
            logger.debug(
                "memory_stored",
                memory_id=memory_id,
                user_id=user_id,
                agent_id=agent_id,
                scope=scope,
            )
            return memory_id

        except Exception as e:
            logger.error("memory_store_failed", error=str(e))
            return ""

    async def store_batch(
        self,
        memories: list[dict[str, Any]],
        user_id: str | None = None,
    ) -> list[str]:
        """
        Store multiple memories efficiently.

        Args:
            memories: List of memory dicts with 'content', optional 'agent_id',
                      'metadata', 'org_id', 'project_id', 'session_id', 'scope'
            user_id: User identifier (defaults to self.user_id)

        Returns:
            List of memory IDs
        """
        if not self._initialized:
            await self.initialize()

        user_id = user_id or self.user_id
        memory_ids = []

        for mem in memories:
            content = mem.get("content", "")
            agent_id = mem.get("agent_id")
            metadata = mem.get("metadata", {})
            org_id = mem.get("org_id")
            project_id = mem.get("project_id")
            session_id = mem.get("session_id")
            scope = mem.get("scope")

            meta = {}
            if agent_id:
                meta["agent_id"] = agent_id
            if org_id:
                meta["org_id"] = org_id
            if project_id:
                meta["project_id"] = project_id
            if session_id:
                meta["session_id"] = session_id
            if scope:
                meta["scope"] = scope

            if metadata:
                meta.update(metadata)

            try:
                result = self._memory.add(
                    content,
                    user_id=user_id,
                    metadata=meta,
                )
                memory_ids.append(result.get("id", ""))
            except Exception as e:
                logger.warning("batch_memory_store_failed", error=str(e))
                memory_ids.append("")

        logger.debug("batch_memory_stored", count=len(memory_ids))
        return memory_ids

    async def search(
        self,
        query: str,
        user_id: str | None = None,
        agent_id: str | None = None,
        limit: int = 10,
        org_id: str | None = None,
        project_id: str | None = None,
        session_id: str | None = None,
        scope: str | None = None,
    ) -> list[dict[str, Any]]:
        """
        Search memories using semantic similarity.
        """
        if not self._initialized:
            await self.initialize()

        user_id = user_id or self.user_id

        try:
            filters = _build_search_filters(agent_id, org_id, project_id, session_id, scope)
            results = self._memory.search(
                query=query, user_id=user_id, limit=limit,
                filters=filters if filters else None,
            )

            if agent_id or org_id or project_id or session_id or scope:
                results = _apply_search_fallback_filters(
                    results, agent_id, org_id, project_id, session_id, scope
                )

            logger.debug("memory_searched", query=query[:50], results=len(results), user_id=user_id)
            return results

        except Exception as e:
            logger.error("memory_search_failed", error=str(e))
            return []

    async def get_all(
        self,
        user_id: str | None = None,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        """
        Get all memories for a user.

        Args:
            user_id: User identifier (defaults to self.user_id)
            limit: Maximum results to return

        Returns:
            List of all memory entries
        """
        if not self._initialized:
            await self.initialize()

        user_id = user_id or self.user_id

        try:
            results = self._memory.get_all(user_id=user_id)
            logger.debug("memory_get_all", count=len(results), user_id=user_id)
            return results[:limit]

        except Exception as e:
            logger.error("memory_get_all_failed", error=str(e))
            return []

    async def get(self, memory_id: str) -> dict[str, Any] | None:
        """
        Get a specific memory by ID.

        Args:
            memory_id: Memory identifier

        Returns:
            Memory entry or None if not found
        """
        if not self._initialized:
            await self.initialize()

        try:
            result = self._memory.get(memory_id)
            return result if result else None

        except Exception as e:
            logger.error("memory_get_failed", memory_id=memory_id, error=str(e))
            return None

    async def delete(self, memory_id: str) -> bool:
        """
        Delete a memory entry.

        Args:
            memory_id: Memory identifier

        Returns:
            True if deleted successfully
        """
        if not self._initialized:
            await self.initialize()

        try:
            self._memory.delete(memory_id)
            logger.debug("memory_deleted", memory_id=memory_id)
            return True

        except Exception as e:
            logger.error("memory_delete_failed", memory_id=memory_id, error=str(e))
            return False

    async def update(
        self,
        memory_id: str,
        content: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> bool:
        """
        Update a memory entry.

        Args:
            memory_id: Memory identifier
            content: New content (optional)
            metadata: New metadata (optional)

        Returns:
            True if updated successfully
        """
        if not self._initialized:
            await self.initialize()

        try:
            # Get existing memory
            existing = await self.get(memory_id)
            if not existing:
                return False

            # Update fields
            if content:
                existing["content"] = content
            if metadata:
                existing["metadata"] = {**existing.get("metadata", {}), **metadata}

            # Re-add to update (mem0 doesn't have direct update)
            self._memory.delete(memory_id)
            result = self._memory.add(
                existing["content"],
                user_id=existing.get("user_id", self.user_id),
                metadata=existing.get("metadata", {}),
            )

            logger.debug("memory_updated", memory_id=memory_id)
            return bool(result.get("id"))

        except Exception as e:
            logger.error("memory_update_failed", memory_id=memory_id, error=str(e))
            return False

    async def close(self) -> None:
        """Close the memory store and release resources."""
        self._initialized = False
        self._memory = None
        logger.info("persistent_memory_closed")

    def is_initialized(self) -> bool:
        """Check if memory store is initialized."""
        return self._initialized


# ---------------------------------------------------------------------------
# Shared helper functions for search filtering
# ---------------------------------------------------------------------------


def _build_search_filters(
    agent_id: str | None = None,
    org_id: str | None = None,
    project_id: str | None = None,
    session_id: str | None = None,
    scope: str | None = None,
) -> dict[str, str]:
    """Build a filters dict from optional hierarchy parameters."""
    filters: dict[str, str] = {}
    if agent_id:
        filters["agent_id"] = agent_id
    if org_id:
        filters["org_id"] = org_id
    if project_id:
        filters["project_id"] = project_id
    if session_id:
        filters["session_id"] = session_id
    if scope:
        filters["scope"] = scope
    return filters


def _apply_search_fallback_filters(
    results: list[dict[str, Any]],
    agent_id: str | None = None,
    org_id: str | None = None,
    project_id: str | None = None,
    session_id: str | None = None,
    scope: str | None = None,
) -> list[dict[str, Any]]:
    """Apply programmatic fallback filters for Water's hierarchy safety."""
    filtered: list[dict[str, Any]] = []
    for r in results:
        meta = r.get("metadata", {})
        if agent_id and meta.get("agent_id") != agent_id:
            continue
        if org_id and meta.get("org_id") != org_id:
            continue
        if project_id and meta.get("project_id") != project_id:
            continue
        if session_id and meta.get("session_id") != session_id:
            continue
        if scope and meta.get("scope") != scope:
            continue
        filtered.append(r)
    return filtered


def _metadata_matches_filters(
    meta: dict[str, Any], filters: dict[str, Any]
) -> bool:
    """Check if metadata matches all provided filters."""
    for key in ["agent_id", "org_id", "project_id", "session_id", "scope"]:
        if key in filters and meta.get(key) != filters[key]:
            return False
    return True


async def create_memory_store(
    provider: str = "qdrant",
    user_id: str = "default",
) -> PersistentMemory:
    """
    Factory function to create a persistent memory store.

    Args:
        provider: Vector store provider (qdrant, postgres, chroma)
        user_id: Default user identifier

    Returns:
        Configured PersistentMemory instance
    """
    config = Mem0Config(vector_store_provider=provider)
    memory = PersistentMemory(config=config, user_id=user_id)
    await memory.initialize()
    return memory


@dataclass
class MemoryResult:
    """Result wrapper for memory queries."""

    total_count: int = 0
    entries: list[MemoryEntry] = field(default_factory=list)


class Mem0Backend:
    """
    Wrapper for mem0 Memory providing unified API for tests.

    This class wraps mem0.Memory to provide a compatible interface
    with the Heretek Swarm memory system.
    """

    def __init__(self, config: Mem0Config | None = None) -> None:
        """
        Initialize the mem0 backend.

        Args:
            config: Mem0 configuration
        """
        self.config = config or Mem0Config()
        self._memory = None
        self._initialized = False
        self._user_id = "default"
        self._latency_stats: list[float] = []

    def initialize_sync(self) -> None:
        """Initialize the mem0 memory instance synchronously."""
        if self._initialized:
            return

        try:
            from mem0 import Memory

            self._memory = Memory.from_config(self.config.get_mem0_config())
            self._initialized = True

            logger.info(
                "mem0_backend_initialized",
                provider=self.config.vector_store_provider,
            )

        except ImportError:
            logger.error("mem0 package not installed")
            raise
        except Exception as e:
            logger.error("mem0_init_failed", error=str(e))
            raise

    async def initialize(self) -> None:
        """Initialize the mem0 memory instance asynchronously."""
        self.initialize_sync()

    async def shutdown(self) -> None:
        """Shutdown the mem0 backend."""
        self._initialized = False
        self._memory = None
        logger.info("mem0_backend_shutdown")

    async def store(self, entry: MemoryEntry) -> str:
        """
        Store a memory entry.

        Args:
            entry: MemoryEntry to store

        Returns:
            Memory ID if successful
        """
        if not self._initialized:
            self.initialize_sync()

        start = time.perf_counter()
        try:
            # Water's hierarchy metadata mapping
            metadata = {
                "agent_id": entry.agent_id,
                "memory_type": str(entry.memory_type) if entry.memory_type else None,
                "tags": entry.tags,
            }
            if entry.metadata:
                # Inherit all existing metadata fields (including org_id, project_id, etc.)
                metadata.update(entry.metadata)

            result = self._memory.add(
                entry.content if isinstance(entry.content, str) else str(entry.content),
                user_id=self._user_id,
                metadata=metadata,
            )
            memory_id = result.get("id", "")
            self._latency_stats.append(time.perf_counter() - start)
            return memory_id
        except Exception as e:
            logger.error("mem0_store_failed", error=str(e))
            return ""

    # Water's hierarchy filter keys
    _HIERARCHY_FILTER_KEYS: ClassVar[list[str]] = [
        "agent_id", "org_id", "project_id", "session_id", "scope", "memory_scope"
    ]

    def search(self, query: MemoryQuery) -> MemoryResult:
        """
        Search memories.

        Args:
            query: MemoryQuery with query_text, agent_ids, limit

        Returns:
            MemoryResult with entries and total_count
        """
        if not self._initialized:
            self.initialize_sync()

        start = time.perf_counter()
        try:
            results = self._execute_mem0_search(query)
            self._latency_stats.append(time.perf_counter() - start)

            if query.filters:
                results = self._apply_fallback_filters(results, query.filters)

            entries = self._convert_to_entries(results)
            return MemoryResult(total_count=len(entries), entries=entries)

        except Exception as e:
            logger.error("mem0_search_failed", error=str(e))
            return MemoryResult()

    def _execute_mem0_search(self, query: MemoryQuery) -> list[dict[str, Any]]:
        """Execute the raw mem0 search."""
        query_text = query.query_text if query.query_text else "*"
        filters = {}
        if query.filters:
            for key in self._HIERARCHY_FILTER_KEYS:
                if key in query.filters:
                    filters[key] = query.filters[key]

        return self._memory.search(
            query=query_text,
            user_id=self._user_id,
            limit=query.limit,
            filters=filters if filters else None,
        )

    @staticmethod
    def _apply_fallback_filters(
        results: list[dict[str, Any]], filters: dict[str, Any]
    ) -> list[dict[str, Any]]:
        """Apply programmatic fallback filters for Water's hierarchy safety."""
        filtered: list[dict[str, Any]] = []
        for r in results:
            meta = r.get("metadata", {})
            if not _metadata_matches_filters(meta, filters):
                continue
            filtered.append(r)
        return filtered

    @staticmethod
    def _convert_to_entries(results: list[dict[str, Any]]) -> list[MemoryEntry]:
        """Convert raw mem0 results to MemoryEntry objects."""
        entries: list[MemoryEntry] = []
        for r in results:
            entries.append(
                MemoryEntry(
                    id=r.get("id", ""),
                    content=r.get("content", ""),
                    metadata=r.get("metadata", {}),
                    agent_id=r.get("metadata", {}).get("agent_id"),
                    memory_type=r.get("metadata", {}).get("memory_type"),
                    tags=r.get("metadata", {}).get("tags", []),
                )
            )
        return entries

    def get_all(self, agent_id: str) -> list[MemoryEntry]:
        """
        Get all memories for an agent.

        Args:
            agent_id: Agent identifier

        Returns:
            List of MemoryEntry objects
        """
        if not self._initialized:
            self.initialize_sync()

        try:
            results = self._memory.get_all(user_id=self._user_id)
            entries = []
            for r in results:
                # Handle both dict and string returns - mem0 may return either
                if isinstance(r, str):
                    # If string, treat it as the memory id/content
                    continue
                if not isinstance(r, dict):
                    continue
                if r.get("metadata", {}).get("agent_id") == agent_id:
                    entries.append(
                        MemoryEntry(
                            id=r.get("id", ""),
                            content=r.get("content", ""),
                            metadata=r.get("metadata", {}),
                            agent_id=agent_id,
                        )
                    )
            return entries
        except Exception as e:
            logger.error("mem0_get_all_failed", error=str(e))
            return []

    def delete(self, memory_id: str) -> bool:
        """
        Delete a memory entry.

        Args:
            memory_id: Memory identifier

        Returns:
            True if deleted
        """
        if not self._initialized:
            self.initialize_sync()

        try:
            self._memory.delete(memory_id)
            return True
        except Exception as e:
            logger.error("mem0_delete_failed", error=str(e))
            return False

    def store_batch(self, entries: list[MemoryEntry]) -> list[str]:
        """
        Store multiple memory entries.

        Args:
            entries: List of MemoryEntry objects

        Returns:
            List of memory IDs
        """
        if not self._initialized:
            self.initialize_sync()

        memory_ids = []
        for entry in entries:
            memory_id = self.store(entry)
            memory_ids.append(memory_id)
        return memory_ids

    def get_latency_stats(self) -> dict[str, float]:
        """
        Get latency statistics.

        Returns:
            Dict with p50, p95, p99, avg in milliseconds
        """
        if not self._latency_stats:
            return {"p50": 0.0, "p95": 0.0, "p99": 0.0, "avg": 0.0}

        sorted_stats = sorted(self._latency_stats)
        n = len(sorted_stats)
        # Convert from seconds to milliseconds
        return {
            "p50": (sorted_stats[int(n * 0.5)] * 1000) if n > 0 else 0.0,
            "p95": (sorted_stats[int(n * 0.95)] * 1000) if n > 0 else 0.0,
            "p99": (sorted_stats[int(n * 0.99)] * 1000) if n > 0 else 0.0,
            "avg": (sum(sorted_stats) / n * 1000) if n > 0 else 0.0,
        }

    # -------------------------------------------------------------------------
    # Raw mem0 API proxy methods (sync, called by REST router)
    # -------------------------------------------------------------------------

    def add(
        self,
        messages: list[dict],
        user_id: str | None = None,
        agent_id: str | None = None,
        run_id: str | None = None,
        metadata: dict | None = None,
        infer: bool = True,
        memory_type: str | None = None,
        prompt: str | None = None,
    ) -> dict:
        """
        Add memories via raw mem0 API.

        Args:
            messages: List of message dicts with 'role' and 'content'
            user_id: User identifier
            agent_id: Agent identifier
            run_id: Run identifier
            metadata: Additional metadata
            infer: Whether to extract facts from messages
            memory_type: Type of memory to store
            prompt: Custom prompt for fact extraction

        Returns:
            Raw mem0 API response dict
        """
        if not self._initialized:
            self.initialize_sync()

        params = {
            k: v
            for k, v in {
                "user_id": user_id,
                "agent_id": agent_id,
                "run_id": run_id,
                "metadata": metadata,
                "infer": infer,
                "memory_type": memory_type,
                "prompt": prompt,
            }.items()
            if v is not None
        }
        return self._memory.add(messages=messages, **params)

    def search(  # noqa: F811
        self,
        query: str,
        user_id: str | None = None,
        run_id: str | None = None,
        agent_id: str | None = None,
        filters: dict | None = None,
        top_k: int | None = None,
        threshold: float | None = None,
    ) -> list[dict]:
        """
        Search via raw mem0 API.

        Args:
            query: Search query text
            user_id: User identifier
            run_id: Run identifier
            agent_id: Agent identifier
            filters: Additional filters
            top_k: Maximum results to return
            threshold: Minimum similarity score

        Returns:
            List of memory dicts
        """
        if not self._initialized:
            self.initialize_sync()

        params = {
            k: v
            for k, v in {
                "user_id": user_id,
                "run_id": run_id,
                "agent_id": agent_id,
                "filters": filters,
                "top_k": top_k,
                "threshold": threshold,
            }.items()
            if v is not None
        }
        return self._memory.search(query=query, **params)

    def update(self, memory_id: str, data: str, metadata: dict | None = None) -> dict:
        """
        Update a memory entry.

        Args:
            memory_id: Memory identifier
            data: New content
            metadata: Updated metadata

        Returns:
            Raw mem0 API response dict
        """
        if not self._initialized:
            self.initialize_sync()

        return self._memory.update(memory_id=memory_id, data=data, metadata=metadata)

    def get(self, memory_id: str) -> dict:
        """
        Get a specific memory.

        Args:
            memory_id: Memory identifier

        Returns:
            Raw mem0 API response dict
        """
        if not self._initialized:
            self.initialize_sync()

        return self._memory.get(memory_id)

    def get_all(  # noqa: F811
        self,
        user_id: str | None = None,
        run_id: str | None = None,
        agent_id: str | None = None,
    ) -> list[dict]:
        """
        Get all memories for an identifier (extended signature).

        Args:
            user_id: User identifier
            run_id: Run identifier
            agent_id: Agent identifier

        Returns:
            List of memory dicts
        """
        if not self._initialized:
            self.initialize_sync()

        params = {
            k: v
            for k, v in {"user_id": user_id, "run_id": run_id, "agent_id": agent_id}.items()
            if v is not None
        }
        return self._memory.get_all(**params)

    def delete_memory(self, memory_id: str) -> None:
        """
        Delete a specific memory.

        Args:
            memory_id: Memory identifier
        """
        if not self._initialized:
            self.initialize_sync()

        self._memory.delete(memory_id)

    def delete_all(
        self,
        user_id: str | None = None,
        run_id: str | None = None,
        agent_id: str | None = None,
    ) -> None:
        """
        Delete all memories for an identifier.

        Args:
            user_id: User identifier
            run_id: Run identifier
            agent_id: Agent identifier
        """
        if not self._initialized:
            self.initialize_sync()

        params = {
            k: v
            for k, v in {"user_id": user_id, "run_id": run_id, "agent_id": agent_id}.items()
            if v is not None
        }
        self._memory.delete_all(**params)

    def history(self, memory_id: str) -> list[dict]:
        """
        Get memory edit history.

        Args:
            memory_id: Memory identifier

        Returns:
            List of history entries
        """
        if not self._initialized:
            self.initialize_sync()

        return self._memory.history(memory_id=memory_id)

    def reset(self) -> None:
        """Reset ALL memories."""
        if not self._initialized:
            self.initialize_sync()

        self._memory.reset()

    async def configure(self, config: dict) -> None:
        """
        Reconfigure mem0 with new config.

        Args:
            config: New mem0 configuration dict
        """
        from mem0 import Memory

        self._memory = Memory.from_config(config)
        self._initialized = True
        logger.info("mem0_reconfigured", config_keys=list(config.keys()))
