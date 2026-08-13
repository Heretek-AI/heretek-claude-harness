"""
NATS Memory Synchronization for Heretek Swarm.

Provides distributed memory synchronization across agents using NATS pub/sub
with eventual consistency and vector clock-based conflict resolution.

Topics:
- swarm.memory.updates - Memory update broadcasts
- swarm.memory.sync - State synchronization requests/responses
- swarm.memory.conflicts - Conflict resolution events
"""

from __future__ import annotations

import asyncio
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from typing import TYPE_CHECKING, Any

import structlog

if TYPE_CHECKING:
    from collections.abc import Callable

    from heretek_swarm.infrastructure.nats import NATSClient
    from heretek_swarm.memory.access_patterns import AccessTier

logger = structlog.get_logger(__name__)


# =============================================================================
# NATS Topics
# =============================================================================

MEMORY_TOPIC_PREFIX = "swarm.memory"
TOPIC_UPDATES = f"{MEMORY_TOPIC_PREFIX}.updates"
TOPIC_SYNC_REQUEST = f"{MEMORY_TOPIC_PREFIX}.sync.request"
TOPIC_SYNC_RESPONSE = f"{MEMORY_TOPIC_PREFIX}.sync.response"
TOPIC_CONFLICTS = f"{MEMORY_TOPIC_PREFIX}.conflicts"


# =============================================================================
# Operation Types
# =============================================================================


class MemoryOperation(StrEnum):
    """Types of memory operations for sync."""

    CREATE = "create"
    UPDATE = "update"
    DELETE = "delete"
    TOUCH = "touch"  # Access record update


# =============================================================================
# Vector Clock
# =============================================================================


@dataclass
class VectorClock:
    """
    Vector clock for tracking causal ordering of memory updates.

    Each agent maintains its own logical clock, incremented on each operation.
    Used for conflict resolution in distributed settings.
    """

    clocks: dict[str, int] = field(default_factory=dict)

    def increment(self, agent_id: str) -> None:
        """Increment clock for an agent."""
        self.clocks[agent_id] = self.clocks.get(agent_id, 0) + 1

    def get(self, agent_id: str) -> int:
        """Get clock value for an agent."""
        return self.clocks.get(agent_id, 0)

    def merge(self, other: VectorClock) -> None:
        """Merge another vector clock into this one (take max of each)."""
        for agent_id, clock_value in other.clocks.items():
            self.clocks[agent_id] = max(self.clocks.get(agent_id, 0), clock_value)

    def is_concurrent_with(self, other: VectorClock) -> bool:
        """
        Check if this clock is concurrent with another.

        Returns True if neither clock dominates the other (concurrent updates).
        """
        self_dominates = all(self.clocks.get(a, 0) >= c for a, c in other.clocks.items())
        other_dominates = all(other.clocks.get(a, 0) >= c for a, c in self.clocks.items())
        return not self_dominates and not other_dominates

    def to_dict(self) -> dict[str, int]:
        """Serialize to dict."""
        return dict(self.clocks)

    @classmethod
    def from_dict(cls, data: dict[str, int]) -> VectorClock:
        """Deserialize from dict."""
        return cls(clocks=dict(data))


# =============================================================================
# Memory Update Message
# =============================================================================


@dataclass
class MemoryUpdate:
    """
    A memory update message broadcast across the swarm.

    Attributes:
        memory_id: Unique identifier of the memory entry
        agent_id: ID of the agent that originated the update
        operation: Type of operation (create, update, delete, touch)
        content: Memory content (optional for delete)
        tier: Access tier of the memory
        vector_clock: Vector clock state at time of update
        timestamp: ISO timestamp of the update
        metadata: Additional metadata
    """

    memory_id: str
    agent_id: str
    operation: MemoryOperation
    content: Any | None = None
    tier: str | None = None
    vector_clock: dict[str, int] = field(default_factory=dict)
    timestamp: str = field(default_factory=lambda: datetime.now(UTC).isoformat())
    metadata: dict[str, Any] = field(default_factory=dict)
    message_id: str = field(default_factory=lambda: str(uuid.uuid4()))

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dict for NATS transmission."""
        return {
            "memory_id": self.memory_id,
            "agent_id": self.agent_id,
            "operation": self.operation.value,
            "content": self.content,
            "tier": self.tier,
            "vector_clock": self.vector_clock,
            "timestamp": self.timestamp,
            "metadata": self.metadata,
            "message_id": self.message_id,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> MemoryUpdate:
        """Deserialize from dict."""
        return cls(
            memory_id=data["memory_id"],
            agent_id=data["agent_id"],
            operation=MemoryOperation(data["operation"]),
            content=data.get("content"),
            tier=data.get("tier"),
            vector_clock=data.get("vector_clock", {}),
            timestamp=data.get("timestamp", datetime.now(UTC).isoformat()),
            metadata=data.get("metadata", {}),
            message_id=data.get("message_id", str(uuid.uuid4())),
        )


# =============================================================================
# Conflict Resolution
# =============================================================================


@dataclass
class MemoryConflict:
    """Represents a conflict between concurrent memory updates."""

    memory_id: str
    local_update: MemoryUpdate
    remote_update: MemoryUpdate
    resolution_strategy: str = "latest_timestamp"
    resolved_content: Any | None = None
    resolved_at: str | None = None

    def resolve(self) -> Any:
        """
        Resolve conflict using configured strategy.

        Default strategy: latest_timestamp wins.
        Can be extended to support vector_clock_priority, merge, etc.
        """
        if self.resolved_content is not None:
            return self.resolved_content

        if self.resolution_strategy == "latest_timestamp":
            local_time = datetime.fromisoformat(self.local_update.timestamp)
            remote_time = datetime.fromisoformat(self.remote_update.timestamp)
            winner = self.remote_update if remote_time > local_time else self.local_update
            self.resolved_content = winner.content
        elif self.resolution_strategy == "vector_clock":
            local_clock = VectorClock.from_dict(self.local_update.vector_clock)
            remote_clock = VectorClock.from_dict(self.remote_update.vector_clock)
            local_clock.merge(remote_clock)
            if remote_clock.is_concurrent_with(local_clock):
                remote_clock.merge(local_clock)
            winner = (
                self.remote_update
                if sum(remote_clock.clocks.values()) > sum(local_clock.clocks.values())
                else self.local_update
            )
            self.resolved_content = winner.content
        else:
            self.resolved_content = self.local_update.content

        self.resolved_at = datetime.now(UTC).isoformat()
        return self.resolved_content


# =============================================================================
# Memory Sync
# =============================================================================


class MemorySync:
    """
    NATS-based memory synchronization across agents.

    Provides eventual consistency for distributed memory operations with
    vector clock-based conflict resolution.

    Example:
        sync = MemorySync(nats_client, agent_id="agent-1")

        # Broadcast update
        await sync.broadcast_memory_update(
            agent_id="agent-1",
            memory_id="mem-123",
            operation=MemoryOperation.CREATE,
            content={"text": "Hello world"},
        )

        # Subscribe to updates
        await sync.subscribe_memory_updates(lambda update: print(f"Updated: {update}"))

        # Sync state
        await sync.sync_state(["mem-123", "mem-456"])
    """

    def __init__(
        self,
        nats_client: NATSClient,
        agent_id: str,
        conflict_strategy: str = "latest_timestamp",
    ) -> None:
        """
        Initialize memory sync.

        Args:
            nats_client: NATS client instance
            agent_id: Unique identifier for this agent
            conflict_strategy: Strategy for resolving conflicts
                (latest_timestamp, vector_clock, merge)
        """
        self._client = nats_client
        self._agent_id = agent_id
        self._conflict_strategy = conflict_strategy
        self._vector_clock = VectorClock()
        self._subscriptions: dict[str, Any] = {}
        self._update_callbacks: list[Callable[[MemoryUpdate], None]] = []
        self._pending_syncs: dict[str, asyncio.Future[MemoryUpdate | None]] = {}
        self._local_memory_cache: dict[str, MemoryUpdate] = {}
        self._lock = asyncio.Lock()

        # Track received message IDs to avoid duplicates
        self._seen_message_ids: set[str] = set()

    @property
    def agent_id(self) -> str:
        """Get this agent's ID."""
        return self._agent_id

    @property
    def vector_clock(self) -> VectorClock:
        """Get current vector clock."""
        return self._vector_clock

    async def connect(self) -> bool:
        """
        Connect to NATS and set up subscriptions.

        Returns:
            True if connection successful
        """
        if not self._client.is_connected:
            connected = await self._client.connect()
            if not connected:
                return False

        await self._setup_subscriptions()
        return True

    async def _setup_subscriptions(self) -> None:
        """Set up NATS subscriptions for memory sync topics."""

        # Subscribe to memory updates
        sub_id = await self._client.subscribe(
            TOPIC_UPDATES,
            callback=self._handle_memory_update,
            queue="memory-sync-group",
        )
        if sub_id:
            self._subscriptions["updates"] = sub_id

        # Subscribe to sync responses
        sub_id = await self._client.subscribe(
            TOPIC_SYNC_RESPONSE,
            callback=self._handle_sync_response,
            queue=None,
        )
        if sub_id:
            self._subscriptions["sync_responses"] = sub_id

        # Subscribe to conflict notifications
        sub_id = await self._client.subscribe(
            TOPIC_CONFLICTS,
            callback=self._handle_conflict_notification,
            queue="memory-sync-group",
        )
        if sub_id:
            self._subscriptions["conflicts"] = sub_id

        logger.info(
            "memory_sync_connected",
            agent_id=self._agent_id,
            subscriptions=len(self._subscriptions),
        )

    async def _check_and_track_message(self, message_id: str) -> bool:
        """Check if message was already seen and track it. Returns False if duplicate."""
        async with self._lock:
            if message_id in self._seen_message_ids:
                return False
            self._seen_message_ids.add(message_id)
            if len(self._seen_message_ids) > 10000:
                self._seen_message_ids = set(list(self._seen_message_ids)[-5000:])
            return True

    async def _check_and_resolve_conflict(
        self, update: MemoryUpdate, local_update: MemoryUpdate | None
    ) -> MemoryUpdate | None:
        """Check for conflict and resolve if needed. Returns resolved update or original."""
        if not local_update or update.operation not in (
            MemoryOperation.UPDATE,
            MemoryOperation.CREATE,
        ):
            return update

        local_clock = VectorClock.from_dict(local_update.vector_clock)
        remote_clock = VectorClock.from_dict(update.vector_clock)

        if not local_clock.is_concurrent_with(remote_clock):
            return update

        conflict = MemoryConflict(
            memory_id=update.memory_id,
            local_update=local_update,
            remote_update=update,
            resolution_strategy=self._conflict_strategy,
        )
        resolved_content = conflict.resolve()
        update.content = resolved_content
        logger.warning(
            "memory_conflict_resolved",
            memory_id=update.memory_id,
            strategy=self._conflict_strategy,
            resolved_at=conflict.resolved_at,
        )
        await self._broadcast_conflict_resolution(conflict)
        return update

    async def _notify_callbacks(self, update: MemoryUpdate) -> None:
        """Notify all registered callbacks of an update."""
        for callback in self._update_callbacks:
            try:
                if asyncio.iscoroutinefunction(callback):
                    await callback(update)
                else:
                    callback(update)
            except Exception as e:
                logger.error(
                    "memory_update_callback_failed",
                    memory_id=update.memory_id,
                    error=str(e),
                )

    async def _handle_memory_update(self, _subject: str, data: bytes) -> None:
        """Handle incoming memory update from NATS."""
        try:
            import json

            message = json.loads(data.decode())
            update = MemoryUpdate.from_dict(message)

            if not await self._check_and_track_message(update.message_id):
                return

            if update.agent_id == self._agent_id:
                return

            remote_clock = VectorClock.from_dict(update.vector_clock)
            self._vector_clock.merge(remote_clock)

            local_update = self._local_memory_cache.get(update.memory_id)
            update = await self._check_and_resolve_conflict(update, local_update)

            if local_update is None or update.timestamp > local_update.timestamp:
                self._local_memory_cache[update.memory_id] = update

            await self._notify_callbacks(update)

        except Exception as e:
            logger.error("memory_update_handler_failed", error=str(e))

    def _handle_sync_response(self, _subject: str, data: bytes) -> None:
        """Handle sync response from another agent."""
        try:
            import json

            message = json.loads(data.decode())
            memory_id = message.get("memory_id")
            requester_id = message.get("requester_id")

            # Only process if we requested this sync
            if requester_id != self._agent_id:
                return

            if memory_id in self._pending_syncs:
                update = MemoryUpdate.from_dict(message["update"])
                self._pending_syncs[memory_id].set_result(update)

        except Exception as e:
            logger.error("sync_response_handler_failed", error=str(e))

    def _handle_conflict_notification(self, _subject: str, data: bytes) -> None:
        """Handle conflict resolution notification."""
        try:
            import json

            message = json.loads(data.decode())
            logger.info(
                "memory_conflict_notified",
                memory_id=message.get("memory_id"),
                agents=message.get("agents"),
            )
        except Exception as e:
            logger.error("conflict_notification_handler_failed", error=str(e))

    async def _broadcast_conflict_resolution(self, conflict: MemoryConflict) -> None:
        """Broadcast conflict resolution to the swarm."""
        message = {
            "memory_id": conflict.memory_id,
            "agents": [conflict.local_update.agent_id, conflict.remote_update.agent_id],
            "resolution_strategy": conflict.resolution_strategy,
            "resolved_content": conflict.resolved_content,
            "resolved_at": conflict.resolved_at,
            "local_timestamp": conflict.local_update.timestamp,
            "remote_timestamp": conflict.remote_update.timestamp,
        }
        await self._client.publish(TOPIC_CONFLICTS, message)

    async def broadcast_memory_update(
        self,
        agent_id: str,
        memory_id: str,
        operation: MemoryOperation,
        content: Any | None = None,
        tier: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> bool:
        """
        Broadcast a memory update to all agents.

        Args:
            agent_id: ID of the originating agent
            memory_id: ID of the memory entry
            operation: Type of operation
            content: Memory content (required for create/update)
            tier: Access tier of the memory
            metadata: Additional metadata

        Returns:
            True if broadcast successful
        """
        # Increment vector clock for this agent
        self._vector_clock.increment(agent_id)

        # Create update message
        update = MemoryUpdate(
            memory_id=memory_id,
            agent_id=agent_id,
            operation=operation,
            content=content,
            tier=tier,
            vector_clock=self._vector_clock.to_dict(),
            metadata=metadata or {},
        )

        # Update local cache
        self._local_memory_cache[memory_id] = update

        # Broadcast to swarm
        success = await self._client.publish(TOPIC_UPDATES, update.to_dict())

        if success:
            logger.debug(
                "memory_update_broadcast",
                agent_id=agent_id,
                memory_id=memory_id,
                operation=operation.value,
            )
        else:
            logger.warning(
                "memory_update_broadcast_failed",
                agent_id=agent_id,
                memory_id=memory_id,
            )

        return success

    def subscribe_memory_updates(self, callback: Callable[[MemoryUpdate], None]) -> None:
        """
        Subscribe to memory updates from other agents.

        Args:
            callback: Function called when a memory update is received.
                Can be sync or async.
        """
        self._update_callbacks.append(callback)
        logger.debug("memory_update_subscriber_added")

    def unsubscribe_memory_updates(self, callback: Callable[[MemoryUpdate], None]) -> None:
        """Unsubscribe from memory updates."""
        if callback in self._update_callbacks:
            self._update_callbacks.remove(callback)

    def _setup_pending_syncs(
        self, memory_ids: list[str]
    ) -> dict[str, asyncio.Future[MemoryUpdate | None]]:
        """Set up futures for pending sync requests."""
        pending_futures: dict[str, asyncio.Future[MemoryUpdate | None]] = {}
        for memory_id in memory_ids:
            future: asyncio.Future[MemoryUpdate | None] = asyncio.Future()
            self._pending_syncs[memory_id] = future
            pending_futures[memory_id] = future
        return pending_futures

    def _collect_sync_results(
        self,
        memory_ids: list[str],
        done: set[asyncio.Future],
        pending: set[asyncio.Future],
    ) -> dict[str, MemoryUpdate | None]:
        """Collect results from completed futures."""
        results: dict[str, MemoryUpdate | None] = {}
        for memory_id in memory_ids:
            future = self._pending_syncs.pop(memory_id, None)
            if future and future in done and not future.cancelled():
                try:
                    results[memory_id] = future.result()
                except Exception:
                    results[memory_id] = None
            else:
                results[memory_id] = None
        for future in pending:
            future.cancel()
        return results

    async def sync_state(
        self, memory_ids: list[str], timeout_sec: float = 5.0
    ) -> dict[str, MemoryUpdate | None]:
        """
        Request current state for specific memories.

        Sends a sync request to the swarm and waits for responses.
        Returns the most recent update for each requested memory.
        """
        if not self._client.is_connected:
            logger.warning("sync_state_not_connected")
            return dict.fromkeys(memory_ids)

        pending_futures = self._setup_pending_syncs(memory_ids)
        request = {
            "requester_id": self._agent_id,
            "memory_ids": memory_ids,
            "timestamp": datetime.now(UTC).isoformat(),
        }
        await self._client.publish(TOPIC_SYNC_REQUEST, request)

        try:
            async with asyncio.timeout(timeout_sec):
                done, pending = await asyncio.wait(
                    list(pending_futures.values()),
                )
            return await self._collect_sync_results(memory_ids, done, pending)
        except TimeoutError:
            logger.warning("sync_state_timeout", memory_ids=memory_ids)
            return dict.fromkeys(memory_ids)
        except Exception as e:
            logger.error("sync_state_failed", error=str(e))
            return dict.fromkeys(memory_ids)

    def get_local_cached_update(self, memory_id: str) -> MemoryUpdate | None:
        """
        Get the locally cached version of a memory update.

        Args:
            memory_id: ID of the memory

        Returns:
            Cached MemoryUpdate or None
        """
        return self._local_memory_cache.get(memory_id)

    def update_local_cache(self, memory_id: str, update: MemoryUpdate) -> None:
        """
        Update the local memory cache (used when local memory changes).

        Args:
            memory_id: ID of the memory
            update: Memory update to cache
        """
        self._local_memory_cache[memory_id] = update

    async def handle_sync_request(self, _subject: str, data: bytes) -> None:
        """
        Handle incoming sync request (callback for NATS subscriber).

        This should be registered as a callback for the sync request topic
        by the component that owns the actual memory store.

        Args:
            subject: NATS subject
            data: Message data
        """
        try:
            import json

            message = json.loads(data.decode())
            requester_id = message.get("requester_id")
            memory_ids = message.get("memory_ids", [])

            if requester_id == self._agent_id:
                return

            for memory_id in memory_ids:
                local_update = self._local_memory_cache.get(memory_id)
                if local_update:
                    response = {
                        "memory_id": memory_id,
                        "requester_id": requester_id,
                        "update": local_update.to_dict(),
                    }
                    await self._client.publish(TOPIC_SYNC_RESPONSE, response)

        except Exception as e:
            logger.error("sync_request_handler_failed", error=str(e))

    async def disconnect(self) -> None:
        """Disconnect and clean up subscriptions."""
        for _name, sub_id in self._subscriptions.items():
            await self._client.unsubscribe(sub_id)
        self._subscriptions.clear()
        logger.info("memory_sync_disconnected", agent_id=self._agent_id)

    def get_tier_from_access_tier(self, access_tier: AccessTier | str) -> str:
        """
        Convert AccessTier enum to tier string.

        Args:
            access_tier: AccessTier enum value

        Returns:
            Tier string
        """
        if hasattr(access_tier, "value"):
            return access_tier.value
        return str(access_tier)

    def get_stats(self) -> dict[str, Any]:
        """Get memory sync statistics."""
        return {
            "agent_id": self._agent_id,
            "vector_clock": self._vector_clock.to_dict(),
            "cached_memories": len(self._local_memory_cache),
            "subscriptions": len(self._subscriptions),
            "subscribers": len(self._update_callbacks),
            "seen_messages": len(self._seen_message_ids),
            "pending_syncs": len(self._pending_syncs),
        }
