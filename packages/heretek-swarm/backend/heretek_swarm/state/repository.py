"""
State Persistence Repository for Heretek Swarm.

Provides PostgreSQL-backed persistence for agent states with:
- Save/load agent state
- Versioned checkpoints for schema compatibility
- State restoration after restart
- Concurrent update handling with optimistic locking
- Event sourcing integration for audit trail and state reconstruction
"""

from __future__ import annotations

import asyncio
import importlib.util
import json
import os
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any
from uuid import UUID, uuid4

import structlog

if TYPE_CHECKING:
    from collections.abc import Callable

ASYNCPG_AVAILABLE = importlib.util.find_spec("asyncpg") is not None
if ASYNCPG_AVAILABLE:
    from asyncpg import Pool, create_pool
else:
    Pool = None
    create_pool = None

logger = structlog.get_logger("state.repository")

# Import event sourcing types
try:
    from heretek_swarm.state.event_store import DomainEvent

    EVENT_SOURCING_AVAILABLE = True
except ImportError:
    EVENT_SOURCING_AVAILABLE = False
    DomainEvent = None


@dataclass
class AgentStateRecord:
    """
    Represents a persisted agent state record.

    Attributes:
        id: Unique record identifier (UUID)
        agent_id: Agent identifier
        agent_type: Type/class of the agent
        state: JSONB state data
        version: Version number for optimistic locking
        created_at: Creation timestamp
        updated_at: Last update timestamp
        is_active: Whether this state is active
    """

    agent_id: str
    agent_type: str
    state: dict[str, Any]
    version: int = 1
    id: UUID = field(default_factory=uuid4)
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    is_active: bool = True

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "id": str(self.id),
            "agent_id": self.agent_id,
            "agent_type": self.agent_type,
            "state": self.state,
            "version": self.version,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "is_active": self.is_active,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> AgentStateRecord:
        """Create from dictionary."""
        return cls(
            id=UUID(data["id"]) if isinstance(data["id"], str) else data["id"],
            agent_id=data["agent_id"],
            agent_type=data["agent_type"],
            state=data["state"],
            version=data.get("version", 1),
            created_at=(
                datetime.fromisoformat(data["created_at"])
                if isinstance(data["created_at"], str)
                else data["created_at"]
            ),
            updated_at=(
                datetime.fromisoformat(data["updated_at"])
                if isinstance(data["updated_at"], str)
                else data["updated_at"]
            ),
            is_active=data.get("is_active", True),
        )


@dataclass
class StateCheckpoint:
    """
    Represents a versioned state checkpoint.

    Used for state versioning and rollback capabilities.

    Attributes:
        checkpoint_id: Unique checkpoint identifier
        agent_id: Agent identifier
        state: State data at checkpoint
        version: Checkpoint version
        created_at: Creation timestamp
        metadata: Optional metadata about the checkpoint
    """

    checkpoint_id: UUID
    agent_id: str
    state: dict[str, Any]
    version: int
    created_at: datetime
    metadata: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "checkpoint_id": str(self.checkpoint_id),
            "agent_id": self.agent_id,
            "state": self.state,
            "version": self.version,
            "created_at": self.created_at.isoformat(),
            "metadata": self.metadata,
        }


class StateRepository:
    """
    PostgreSQL-backed state persistence repository.

    Provides CRUD operations for agent states with:
    - Optimistic locking via version numbers
    - Checkpoint management for rollback
    - Automatic retry on concurrency conflicts
    - Graceful fallback to in-memory storage

    Database Schema (agent_states table):
        CREATE TABLE agent_states (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            agent_id VARCHAR(255) NOT NULL,
            agent_type VARCHAR(255) NOT NULL,
            state JSONB NOT NULL,
            version INTEGER DEFAULT 1,
            created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
            is_active BOOLEAN DEFAULT true
        );

        CREATE INDEX idx_agent_states_agent_id ON agent_states(agent_id);
        CREATE INDEX idx_agent_states_active ON agent_states(is_active) WHERE is_active = true;

    Example:
        ```python
        # Initialize repository
        repo = StateRepository(db_pool)
        await repo.initialize()

        # Save state
        await repo.save_state("agent-1", {"key": "value"})

        # Load state
        state = await repo.load_state("agent-1")

        # Create checkpoint
        await repo.checkpoint("agent-1", {"key": "value"}, version=2)

        # Restore from checkpoint
        await repo.restore_from_checkpoint("agent-1", checkpoint_id)
        ```
    """

    # SQL queries
    SAVE_STATE_QUERY = """
        INSERT INTO agent_states (id, agent_id, agent_type, state, version, created_at, updated_at, is_active)  # noqa: E501
        VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
        ON CONFLICT (agent_id) DO UPDATE
        SET state = $4, version = $5, updated_at = $7, is_active = $8
        WHERE agent_states.version = $5 - 1
        RETURNING *
    """

    LOAD_STATE_QUERY = """
        SELECT id, agent_id, agent_type, state, version, created_at, updated_at, is_active
        FROM agent_states
        WHERE agent_id = $1 AND is_active = true
    """

    DELETE_STATE_QUERY = """
        UPDATE agent_states
        SET is_active = false, updated_at = NOW()
        WHERE agent_id = $1
    """

    LIST_ACTIVE_STATES_QUERY = """
        SELECT id, agent_id, agent_type, state, version, created_at, updated_at, is_active
        FROM agent_states
        WHERE is_active = true
        ORDER BY updated_at DESC
    """

    CHECKPOINT_QUERY = """
        INSERT INTO agent_state_checkpoints (checkpoint_id, agent_id, state, version, created_at, metadata)  # noqa: E501
        VALUES ($1, $2, $3, $4, $5, $6)
    """

    GET_CHECKPOINT_QUERY = """
        SELECT checkpoint_id, agent_id, state, version, created_at, metadata
        FROM agent_state_checkpoints
        WHERE checkpoint_id = $1
    """

    GET_CHECKPOINTS_QUERY = """
        SELECT checkpoint_id, agent_id, state, version, created_at, metadata
        FROM agent_state_checkpoints
        WHERE agent_id = $1
        ORDER BY version DESC
        LIMIT $2
    """

    def __init__(
        self,
        db_pool: Any | None = None,
        max_retries: int = 3,
        retry_delay: float = 0.1,
    ):
        """
        Initialize state repository.

        Args:
            db_pool: asyncpg connection pool
            max_retries: Maximum retries for concurrent updates
            retry_delay: Base delay between retries (seconds)
        """
        self._db_pool = db_pool
        self._max_retries = max_retries
        self._retry_delay = retry_delay

        # In-memory fallback storage
        self._memory_store: dict[str, AgentStateRecord] = {}
        self._checkpoints: dict[str, list[StateCheckpoint]] = {}

        # Statistics
        self._stats = {
            "db_saves": 0,
            "db_loads": 0,
            "memory_saves": 0,
            "memory_loads": 0,
            "concurrency_retries": 0,
            "checkpoints_created": 0,
            "checkpoints_restored": 0,
        }

        self._initialized = False

    # Pool configuration constants
    DEFAULT_MIN_SIZE = 10
    DEFAULT_MAX_SIZE = 100
    POOL_UTILIZATION_WARNING_THRESHOLD = 0.8  # 80%

    # Class-level pool for singleton pattern
    _pool: Any = None
    _pool_config: tuple[tuple[str, Any], ...] = (
        ("min_size", DEFAULT_MIN_SIZE),
        ("max_size", DEFAULT_MAX_SIZE),
        ("command_timeout", 60),
        ("max_queries", 50000),
        ("max_inactive_connection_lifetime", 300),
    )

    @classmethod
    async def create_pool(cls, database_url: str | None = None, **kwargs) -> Pool | None:
        """
        Create an asyncpg connection pool.

        Args:
            database_url: PostgreSQL connection URL
            **kwargs: Override pool configuration (min_size, max_size, etc.)

        Returns:
            asyncpg Pool instance or None if asyncpg not available
        """
        if not ASYNCPG_AVAILABLE:
            logger.warning("asyncpg not available, cannot create pool")
            return None

        url = database_url or os.environ.get("DATABASE_URL")
        if not url:
            logger.warning("DATABASE_URL not set, cannot create pool")
            return None

        # Merge configuration
        config = dict(cls._pool_config)
        config.update(kwargs)

        try:
            cls._pool = await create_pool(dsn=url, **config)
            logger.info(
                "Database connection pool created",
                min_size=config["min_size"],
                max_size=config["max_size"],
            )
            return cls._pool
        except Exception:
            logger.error("Failed to create database pool: {e}")
            return None

    @classmethod
    async def close_pool(cls) -> None:
        """Close the connection pool."""
        if cls._pool:
            await cls._pool.close()
            cls._pool = None
            logger.info("Database connection pool closed")

    @classmethod
    async def get_pool(cls) -> Pool | None:
        """
        Get the connection pool, creating it if necessary.

        Returns:
            asyncpg Pool instance or None
        """
        if cls._pool is None:
            await cls.create_pool()
        return cls._pool

    @classmethod
    def get_pool_stats(cls) -> dict[str, Any]:
        """
        Get connection pool statistics.

        Returns:
            Dict with pool size, idle count, and utilization metrics
        """
        if cls._pool is None:
            return {
                "available": False,
                "size": 0,
                "idle_size": 0,
                "utilization": 0.0,
            }

        try:
            size = cls._pool.get_size()
            idle = cls._pool.get_idle_size()
            utilized = size - idle
            utilization = utilized / size if size > 0 else 0.0

            stats = {
                "available": True,
                "size": size,
                "idle_size": idle,
                "utilized": utilized,
                "utilization": utilization,
                "utilization_percent": round(utilization * 100, 2),
                "is_healthy": utilization < cls.POOL_UTILIZATION_WARNING_THRESHOLD,
            }

            # Log warning if utilization is high
            if utilization >= cls.POOL_UTILIZATION_WARNING_THRESHOLD:
                logger.warning(
                    "Database pool utilization high",
                    utilization=stats["utilization_percent"],
                    threshold=cls.POOL_UTILIZATION_WARNING_THRESHOLD * 100,
                )

            return stats
        except Exception as e:
            logger.error("Failed to get pool stats: {e}")
            return {
                "available": True,
                "error": str(e),
            }

    @classmethod
    async def initialize(cls, database_url: str | None = None, **kwargs) -> StateRepository:
        """
        Factory method to create and initialize a repository with pool.

        Args:
            database_url: Optional database URL
            **kwargs: Pool configuration overrides

        Returns:
            Initialized StateRepository instance
        """
        # Create pool if not exists
        pool = await cls.create_pool(database_url, **kwargs)

        repo = cls(db_pool=pool)
        await repo.initialize()
        return repo

    async def initialize(self, db_pool: Any | None = None) -> None:
        """
        Initialize the repository.

        Args:
            db_pool: Optional asyncpg connection pool
        """
        if db_pool:
            self._db_pool = db_pool

        # Create checkpoint table if using database
        if self._db_pool:
            try:
                await self._create_checkpoint_table()
                self._initialized = True
                logger.info("State repository initialized with PostgreSQL")
            except (ConnectionError, OSError):
                logger.warning("PostgreSQL connection failed, using in-memory: {e}")
                self._db_pool = None
                self._initialized = True
        else:
            self._initialized = True
            logger.info("State repository initialized with in-memory storage")

    async def _create_checkpoint_table(self) -> None:
        """Create the agent_state_checkpoints table if it doesn't exist."""
        if not self._db_pool:
            return

        async with self._db_pool.acquire() as conn:
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS agent_state_checkpoints (
                    checkpoint_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                    agent_id VARCHAR(255) NOT NULL,
                    state JSONB NOT NULL,
                    version INTEGER NOT NULL,
                    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
                    metadata JSONB,
                    FOREIGN KEY (agent_id) REFERENCES agent_states(agent_id) ON DELETE CASCADE
                );
                CREATE INDEX IF NOT EXISTS idx_checkpoints_agent_id ON agent_state_checkpoints(agent_id);  # noqa: E501
                CREATE INDEX IF NOT EXISTS idx_checkpoints_version ON agent_state_checkpoints(agent_id, version DESC);  # noqa: E501
            """)

    async def save_state(
        self,
        agent_id: str,
        state: dict[str, Any],
        agent_type: str = "AgentActor",
        version: int | None = None,
    ) -> AgentStateRecord:
        """
        Save agent state to database.

        Uses optimistic locking with version numbers to handle
        concurrent updates. Retries on version conflicts.

        Args:
            agent_id: Unique agent identifier
            state: State data to persist
            agent_type: Type/class of agent
            version: Expected current version (for optimistic locking)

        Returns:
            Saved state record

        Raises:
            ConcurrencyError: If max retries exceeded due to concurrent updates
        """
        record = AgentStateRecord(
            agent_id=agent_id,
            agent_type=agent_type,
            state=state,
            version=version or 1,
        )

        if self._db_pool:
            return await self._save_to_db(record)
        return self._save_to_memory(record)

    async def _save_to_db(self, record: AgentStateRecord) -> AgentStateRecord:
        """Save record to database with retry logic."""
        attempt = 0

        while attempt < self._max_retries:
            try:
                async with self._db_pool.acquire() as conn:
                    now = datetime.now(UTC)
                    record.updated_at = now

                    row = await conn.fetchrow(
                        self.SAVE_STATE_QUERY,
                        record.id,
                        record.agent_id,
                        record.agent_type,
                        json.dumps(record.state),
                        record.version,
                        record.created_at,
                        now,
                        record.is_active,
                    )

                    if row:
                        self._stats["db_saves"] += 1
                        logger.debug(
                            f"State saved for {record.agent_id}",
                            extra={"version": record.version},
                        )
                        return record
                    # Version conflict - retry with incremented version
                    attempt += 1
                    self._stats["concurrency_retries"] += 1

                    if attempt < self._max_retries:
                        # Fetch current version and retry
                        current = await self._load_from_db(record.agent_id)
                        if current:
                            record.version = current.version + 1
                        await asyncio.sleep(self._retry_delay * (2 ** (attempt - 1)))
                    else:
                        raise ConcurrencyError(
                            f"Max retries ({self._max_retries}) exceeded for agent {record.agent_id}"
                        )

            except (ConnectionError, OSError, TimeoutError):
                attempt += 1
                if attempt < self._max_retries:
                    await asyncio.sleep(self._retry_delay * (2 ** (attempt - 1)))
                else:
                    break

        # All retries failed, fall back to memory
        logger.warning("Database save failed after {attempt} attempts, using memory: {last_error}")
        return self._save_to_memory(record)

    def _save_to_memory(self, record: AgentStateRecord) -> AgentStateRecord:
        """Save record to in-memory storage."""
        self._memory_store[record.agent_id] = record
        self._stats["memory_saves"] += 1
        logger.debug("State saved to memory for {record.agent_id}")
        return record

    async def load_state(self, agent_id: str) -> AgentStateRecord | None:
        """
        Load agent state from database.

        Args:
            agent_id: Agent identifier

        Returns:
            State record or None if not found
        """
        if self._db_pool:
            record = await self._load_from_db(agent_id)
        else:
            record = self._load_from_memory(agent_id)

        if record:
            logger.debug("State loaded for {agent_id}")

        return record

    async def _load_from_db(self, agent_id: str) -> AgentStateRecord | None:
        """Load record from database."""
        try:
            async with self._db_pool.acquire() as conn:
                row = await conn.fetchrow(
                    self.LOAD_STATE_QUERY,
                    agent_id,
                )

                if row:
                    self._stats["db_loads"] += 1
                    return AgentStateRecord(
                        id=row["id"],
                        agent_id=row["agent_id"],
                        agent_type=row["agent_type"],
                        state=json.loads(row["state"]),
                        version=row["version"],
                        created_at=row["created_at"],
                        updated_at=row["updated_at"],
                        is_active=row["is_active"],
                    )
        except (ConnectionError, OSError):
            logger.error("Database load failed: {e}")

        return None

    def _load_from_memory(self, agent_id: str) -> AgentStateRecord | None:
        """Load record from memory."""
        record = self._memory_store.get(agent_id)
        if record:
            self._stats["memory_loads"] += 1
        return record

    async def delete_state(self, agent_id: str) -> bool:
        """
        Delete (deactivate) agent state.

        Args:
            agent_id: Agent identifier

        Returns:
            True if deleted, False if not found
        """
        if self._db_pool:
            try:
                async with self._db_pool.acquire() as conn:
                    result = await conn.execute(
                        self.DELETE_STATE_QUERY,
                        agent_id,
                    )
                    self._stats["db_saves"] += 1
                    deleted = result != "DELETE 0"
                    logger.debug("State {'deleted' if deleted else 'not found'} for {agent_id}")
                    return deleted
            except (ConnectionError, OSError):
                logger.error("Database delete failed: {e}")

        # Memory fallback
        if agent_id in self._memory_store:
            del self._memory_store[agent_id]
            logger.debug("Memory state deleted for {agent_id}")
            return True

        return False

    async def list_active_states(self) -> list[AgentStateRecord]:
        """
        List all active agent states.

        Returns:
            List of active state records
        """
        if self._db_pool:
            try:
                async with self._db_pool.acquire() as conn:
                    rows = await conn.fetch(self.LIST_ACTIVE_STATES_QUERY)
                    self._stats["db_loads"] += len(rows)
                    return [
                        AgentStateRecord(
                            id=row["id"],
                            agent_id=row["agent_id"],
                            agent_type=row["agent_type"],
                            state=json.loads(row["state"]),
                            version=row["version"],
                            created_at=row["created_at"],
                            updated_at=row["updated_at"],
                            is_active=row["is_active"],
                        )
                        for row in rows
                    ]
            except (ConnectionError, OSError):
                logger.error("Database list failed: {e}")

        # Memory fallback
        self._stats["memory_loads"] += len(self._memory_store)
        return list(self._memory_store.values())

    async def checkpoint(
        self,
        agent_id: str,
        state: dict[str, Any],
        version: int,
        metadata: dict[str, Any] | None = None,
    ) -> StateCheckpoint:
        """
        Create a versioned state checkpoint.

        Checkpoints are immutable snapshots that can be used for:
        - Rollback after errors
        - State restoration after restart
        - Audit trail

        Args:
            agent_id: Agent identifier
            state: State data to checkpoint
            version: Checkpoint version number
            metadata: Optional metadata (reason, trigger, etc.)

        Returns:
            Created checkpoint
        """
        checkpoint = StateCheckpoint(
            checkpoint_id=uuid4(),
            agent_id=agent_id,
            state=state,
            version=version,
            created_at=datetime.now(UTC),
            metadata=metadata,
        )

        if self._db_pool:
            try:
                async with self._db_pool.acquire() as conn:
                    await conn.execute(
                        self.CHECKPOINT_QUERY,
                        checkpoint.checkpoint_id,
                        agent_id,
                        json.dumps(state),
                        version,
                        checkpoint.created_at,
                        json.dumps(metadata) if metadata else None,
                    )
                    self._stats["checkpoints_created"] += 1
                    logger.debug(
                        f"Checkpoint created for {agent_id}",
                        extra={"version": version},
                    )
                    return checkpoint
            except (ConnectionError, OSError):
                logger.error("Database checkpoint failed: {e}")

        # Memory fallback
        if agent_id not in self._checkpoints:
            self._checkpoints[agent_id] = []
        self._checkpoints[agent_id].append(checkpoint)
        self._stats["checkpoints_created"] += 1
        return checkpoint

    async def get_checkpoint(
        self,
        checkpoint_id: UUID,
    ) -> StateCheckpoint | None:
        """
        Get a specific checkpoint by ID.

        Args:
            checkpoint_id: Checkpoint identifier

        Returns:
            Checkpoint or None if not found
        """
        if self._db_pool:
            try:
                async with self._db_pool.acquire() as conn:
                    row = await conn.fetchrow(
                        self.GET_CHECKPOINT_QUERY,
                        checkpoint_id,
                    )
                    if row:
                        return StateCheckpoint(
                            checkpoint_id=row["checkpoint_id"],
                            agent_id=row["agent_id"],
                            state=json.loads(row["state"]),
                            version=row["version"],
                            created_at=row["created_at"],
                            metadata=row["metadata"],
                        )
            except (ConnectionError, OSError):
                logger.error("Database checkpoint get failed: {e}")

        # Memory fallback
        for checkpoints in self._checkpoints.values():
            for cp in checkpoints:
                if cp.checkpoint_id == checkpoint_id:
                    return cp

        return None

    async def get_checkpoints(
        self,
        agent_id: str,
        limit: int = 10,
    ) -> list[StateCheckpoint]:
        """
        Get checkpoints for an agent.

        Args:
            agent_id: Agent identifier
            limit: Maximum number of checkpoints to return

        Returns:
            List of checkpoints (newest first)
        """
        if self._db_pool:
            try:
                async with self._db_pool.acquire() as conn:
                    rows = await conn.fetch(
                        self.GET_CHECKPOINTS_QUERY,
                        agent_id,
                        limit,
                    )
                    return [
                        StateCheckpoint(
                            checkpoint_id=row["checkpoint_id"],
                            agent_id=row["agent_id"],
                            state=json.loads(row["state"]),
                            version=row["version"],
                            created_at=row["created_at"],
                            metadata=row["metadata"],
                        )
                        for row in rows
                    ]
            except (ConnectionError, OSError):
                logger.error("Database checkpoints list failed: {e}")

        # Memory fallback
        checkpoints = self._checkpoints.get(agent_id, [])
        return sorted(checkpoints, key=lambda c: c.version, reverse=True)[:limit]

    async def restore_from_checkpoint(
        self,
        agent_id: str,
        checkpoint_id: UUID,
    ) -> bool:
        """
        Restore agent state from a checkpoint.

        Args:
            agent_id: Agent identifier
            checkpoint_id: Checkpoint to restore from

        Returns:
            True if restored, False if checkpoint not found
        """
        checkpoint = await self.get_checkpoint(checkpoint_id)
        if not checkpoint:
            logger.warning("Checkpoint not found: {checkpoint_id}")
            return False

        # Save the checkpoint state as current state
        await self.save_state(
            agent_id=agent_id,
            state=checkpoint.state,
            version=checkpoint.version + 1,
        )

        self._stats["checkpoints_restored"] += 1
        logger.info(
            f"State restored from checkpoint for {agent_id}",
            extra={"checkpoint_id": str(checkpoint_id)},
        )
        return True

    async def get_stats(self) -> dict[str, Any]:
        """Get repository statistics."""
        return {
            **self._stats,
            "memory_records": len(self._memory_store),
            "agents_with_checkpoints": len(self._checkpoints),
            "initialized": self._initialized,
            "using_database": self._db_pool is not None,
        }


class ConcurrencyError(Exception):
    """Raised when concurrent update conflicts exceed max retries."""


# =============================================================================
# Event Sourcing Integration
# =============================================================================


class EventSourcedRepository(StateRepository):
    """
    Event-sourced state repository extending StateRepository.

    Combines traditional state persistence with event sourcing:
    - All state changes are stored as immutable events
    - Current state is stored for performance (CQRS pattern)
    - State can be reconstructed from events at any time
    - Supports snapshotting for large event streams

    Example:
        ```python
        repo = EventSourcedRepository(db_pool)
        await repo.initialize()

        # Save state with event
        await repo.save_state_with_event(
            agent_id="agent-1",
            state={"status": "running"},
            event_type="agent.state.changed",
            event_payload={"old_state": "stopped", "new_state": "running"},
        )

        # Reconstruct state from events
        state = await repo.reconstruct_state("agent-1")
        ```
    """

    def __init__(
        self,
        db_pool: Any | None = None,
        max_retries: int = 3,
        retry_delay: float = 0.1,
        snapshot_interval: int = 100,
    ):
        """
        Initialize event-sourced repository.

        Args:
            db_pool: asyncpg connection pool
            max_retries: Maximum retries for concurrent updates
            retry_delay: Base delay between retries
            snapshot_interval: Create snapshot every N events
        """
        super().__init__(db_pool, max_retries, retry_delay)

        # Event store reference
        self._event_store = None
        self._snapshot_interval = snapshot_interval

        # Event appliers
        self._event_appliers: dict[str, Callable[[dict[str, Any], DomainEvent], dict[str, Any]]] = {
            "agent.state.changed": self._apply_agent_state_changed,
            "agent.config.updated": self._apply_agent_config_updated,
            "agent.created": self._apply_agent_created,
        }

        logger.info(
            "EventSourcedRepository initialized",
            snapshot_interval=snapshot_interval,
        )

    async def initialize(self, db_pool: Any | None = None) -> None:
        """Initialize repository and event store."""
        await super().initialize(db_pool)

        # Initialize event store
        from heretek_swarm.state.event_store import get_event_store

        self._event_store = get_event_store()
        await self._event_store.initialize(db_pool)

        logger.info("EventSourcedRepository fully initialized")

    async def save_state_with_event(
        self,
        agent_id: str,
        state: dict[str, Any],
        event_type: str,
        event_payload: dict[str, Any],
        agent_type: str = "AgentActor",
        version: int | None = None,
        event_metadata: dict[str, Any] | None = None,
    ) -> AgentStateRecord:
        """
        Save state and append corresponding event.

        Args:
            agent_id: Agent identifier
            state: State data to persist
            event_type: Type of event
            event_payload: Event payload
            agent_type: Type of agent
            version: Expected current version
            event_metadata: Event metadata (correlation_id, causation_id, user_id)

        Returns:
            Saved state record
        """
        # Get current version
        current_version = (
            await self._event_store.get_last_version(agent_id) if self._event_store else 0
        )
        new_version = current_version + 1

        # Create event
        event = DomainEvent.create(
            event_type=event_type,
            aggregate_id=agent_id,
            aggregate_type=agent_type,
            payload=event_payload,
            version=new_version,
            metadata=event_metadata,
        )

        # Append event first (event sourcing)
        if self._event_store:
            await self._event_store.append(event)

        # Save current state (for performance)
        record = await self.save_state(
            agent_id=agent_id,
            state=state,
            agent_type=agent_type,
            version=new_version,
        )

        logger.info(
            "State saved with event",
            agent_id=agent_id,
            event_type=event_type,
            version=new_version,
        )

        return record

    async def reconstruct_state(self, agent_id: str) -> dict[str, Any] | None:
        """
        Reconstruct state from events.

        Args:
            agent_id: Agent identifier

        Returns:
            Reconstructed state or None if no events found
        """
        if not self._event_store:
            logger.warning("Event store not available")
            return None

        # Get current state as base
        current_record = await self.load_state(agent_id)
        initial_state = current_record.state if current_record else {}

        # Reconstruct from events
        state = await self._event_store.reconstruct_state(
            aggregate_id=agent_id,
            applier=self._apply_event,
            initial_state=initial_state,
        )

        logger.info("State reconstructed for {agent_id}")
        return state

    def _apply_event(
        self,
        state: dict[str, Any],
        event: DomainEvent,
    ) -> dict[str, Any]:
        """Apply event to state."""
        applier = self._event_appliers.get(event.event_type)

        if applier:
            return applier(state, event)
        # Default: merge payload into state
        state.update(event.payload)
        return state

    def _apply_agent_state_changed(
        self,
        state: dict[str, Any],
        event: DomainEvent,
    ) -> dict[str, Any]:
        """Apply agent.state.changed event."""
        if "new_state" in event.payload:
            state["state"] = event.payload["new_state"]
        if "status" in event.payload:
            state["status"] = event.payload["status"]
        state["last_state_change"] = event.timestamp.isoformat()
        return state

    def _apply_agent_config_updated(
        self,
        state: dict[str, Any],
        event: DomainEvent,
    ) -> dict[str, Any]:
        """Apply agent.config.updated event."""
        if "config" in event.payload:
            state["config"] = event.payload["config"]
        state["last_config_update"] = event.timestamp.isoformat()
        return state

    def _apply_agent_created(
        self,
        state: dict[str, Any],
        event: DomainEvent,
    ) -> dict[str, Any]:
        """Apply agent.created event."""
        state.update(event.payload)
        state["created_at"] = event.timestamp.isoformat()
        return state

    async def get_event_history(
        self,
        agent_id: str,
        from_version: int = 0,
    ) -> list[DomainEvent]:
        """
        Get event history for an agent.

        Args:
            agent_id: Agent identifier
            from_version: Start version (exclusive)

        Returns:
            List of events
        """
        if not self._event_store:
            return []

        return await self._event_store.get_events(agent_id, from_version=from_version)

    async def create_state_snapshot(self, agent_id: str, agent_type: str) -> bool:
        """
        Create a state snapshot.

        Args:
            agent_id: Agent identifier
            agent_type: Agent type

        Returns:
            True if snapshot created
        """
        if not self._event_store:
            return False

        # Get current state
        record = await self.load_state(agent_id)
        if not record:
            return False

        # Get current version
        version = await self._event_store.get_last_version(agent_id)

        # Create snapshot
        return await self._event_store.create_snapshot(
            aggregate_id=agent_id,
            aggregate_type=agent_type,
            state=record.state,
            version=version,
        )

    def register_event_applier(
        self,
        event_type: str,
        applier: Callable[[dict[str, Any], DomainEvent], dict[str, Any]],
    ) -> None:
        """
        Register a custom event applier.

        Args:
            event_type: Type of event
            applier: Function to apply event to state
        """
        self._event_appliers[event_type] = applier
        logger.debug("Event applier registered for {event_type}")


# Override get_event_store for event_sourced compatibility
def get_event_sourced_repository() -> EventSourcedRepository:
    """Get or create the event-sourced repository singleton."""
    # This would typically be a singleton, but for now create new instance
    return EventSourcedRepository()
