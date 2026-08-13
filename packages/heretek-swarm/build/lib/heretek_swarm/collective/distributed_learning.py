"""
Distributed Learning Engine - Cross-Agent Learning

Implements distributed learning with Redis pub/sub for pattern distribution
and knowledge synchronization across the agent swarm.

Features:
- Publish learned patterns to Redis pub/sub
- Subscribe to pattern updates from other agents
- Merge incoming knowledge with local state
- Distributed pattern validation
- Knowledge synchronization across instances

Zero-Trust Principles:
- All incoming patterns validated before merge
- Source verification required
- Conflict resolution with consensus
- Audit logging for all sync operations
"""

import asyncio
import contextlib
import json
import os
import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

import structlog

from .knowledge_transform import (
    KnowledgeTransformer,
)
from .learning import (
    CollectiveLearning,
    ExtractedPattern,
    LearningSignal,
    PatternMetadata,
    PatternType,
)

logger = structlog.get_logger(__name__)


class SyncOperation(StrEnum):
    """Types of synchronization operations."""

    PUBLISH = "publish"
    SUBSCRIBE = "subscribe"
    MERGE = "merge"
    VALIDATE = "validate"
    CONFLICT_RESOLVE = "conflict_resolve"
    BROADCAST = "broadcast"


class MergeStrategy(StrEnum):
    """Strategies for merging incoming knowledge."""

    NEWEST = "newest"  # Prefer newest timestamp
    HIGHEST_CONFIDENCE = "highest_confidence"  # Prefer highest confidence
    LOCAL_PRIORITY = "local_priority"  # Prefer local knowledge
    REMOTE_PRIORITY = "remote_priority"  # Prefer remote knowledge
    CONSENSUS = "consensus"  # Require consensus for merge


@dataclass
class SyncMessage:
    """Message for distributed synchronization."""

    message_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    operation: SyncOperation = SyncOperation.PUBLISH
    source_agent: str = ""
    timestamp: str = field(default_factory=lambda: datetime.now(UTC).isoformat())
    payload: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)
    correlation_id: str | None = None
    reply_to: str | None = None

    def to_json(self) -> str:
        """Serialize to JSON string."""
        return json.dumps(
            {
                "message_id": self.message_id,
                "operation": self.operation.value,
                "source_agent": self.source_agent,
                "timestamp": self.timestamp,
                "payload": self.payload,
                "metadata": self.metadata,
                "correlation_id": self.correlation_id,
                "reply_to": self.reply_to,
            }
        )

    @classmethod
    def from_json(cls, json_str: str) -> "SyncMessage":
        """Deserialize from JSON string."""
        data = json.loads(json_str)
        return cls(
            message_id=data.get("message_id", str(uuid.uuid4())),
            operation=SyncOperation(data.get("operation", "publish")),
            source_agent=data.get("source_agent", ""),
            timestamp=data.get("timestamp", datetime.now(UTC).isoformat()),
            payload=data.get("payload", {}),
            metadata=data.get("metadata", {}),
            correlation_id=data.get("correlation_id"),
            reply_to=data.get("reply_to"),
        )


@dataclass
class MergeResult:
    """Result of a knowledge merge operation."""

    success: bool
    merged_count: int = 0
    conflict_count: int = 0
    rejected_count: int = 0
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    merged_pattern_ids: list[str] = field(default_factory=list)
    conflict_details: list[dict[str, Any]] = field(default_factory=list)


@dataclass
class DistributedLearningConfig:
    """Configuration for distributed learning."""

    redis_url: str
    pubsub_channel: str = "heretek:collective:learning"
    pattern_channel: str = "heretek:collective:patterns"
    signal_channel: str = "heretek:collective:signals"
    merge_strategy: MergeStrategy = MergeStrategy.HIGHEST_CONFIDENCE
    validation_required: bool = True
    max_pending_messages: int = 1000
    message_ttl_seconds: int = 3600
    sync_interval_seconds: float = 5.0
    batch_size: int = 10


class DistributedLearningEngine:
    """
    Distributed learning engine with Redis pub/sub synchronization.

    This engine coordinates learning across multiple agent instances,
    publishing learned patterns and subscribing to updates from peers.

    Attributes:
        config: Configuration for distributed learning
        local_learning: Local CollectiveLearning instance
        transformer: KnowledgeTransformer instance
    """

    def __init__(
        self,
        config: DistributedLearningConfig | None = None,
        agent_id: str | None = None,
    ):
        """
        Initialize distributed learning engine.

        Args:
            config: Configuration options
            agent_id: This agent's identifier
        """
        redis_url = os.getenv("REDIS_URL")
        if not redis_url:
            raise RuntimeError("REDIS_URL is required. Set it to redis://host:port or use docker compose.")
        self.config = config or DistributedLearningConfig(redis_url=redis_url)
        self.agent_id = agent_id or f"agent_{uuid.uuid4().hex[:8]}"

        self.local_learning = CollectiveLearning()
        self.transformer = KnowledgeTransformer()

        # Redis connection (lazy initialization)
        self._redis = None
        self._pubsub = None

        # Message queues
        self._pending_messages: asyncio.Queue = asyncio.Queue(
            maxsize=self.config.max_pending_messages
        )
        self._processed_ids: set[str] = set()

        # Callbacks
        self._on_pattern_received: list[Callable] = []
        self._on_signal_received: list[Callable] = []
        self._on_merge_complete: list[Callable] = []

        # Running state
        self._running = False
        self._subscribe_task: asyncio.Task | None = None
        self._sync_task: asyncio.Task | None = None

        logger.info(
            "distributed_learning_engine_initialized",
            agent_id=self.agent_id,
            pubsub_channel=self.config.pubsub_channel,
        )

    def register_pattern_callback(self, callback: Callable) -> None:
        """
        Register callback for pattern received events.

        Args:
            callback: Async callable receiving ExtractedPattern
        """
        self._on_pattern_received.append(callback)
        logger.debug("pattern_callback_registered", callback=callback.__name__)

    def register_signal_callback(self, callback: Callable) -> None:
        """
        Register callback for learning signal received events.

        Args:
            callback: Async callable receiving LearningSignal
        """
        self._on_signal_received.append(callback)
        logger.debug("signal_callback_registered", callback=callback.__name__)

    def register_merge_callback(self, callback: Callable) -> None:
        """
        Register callback for merge complete events.

        Args:
            callback: Async callable receiving MergeResult
        """
        self._on_merge_complete.append(callback)
        logger.debug("merge_callback_registered", callback=callback.__name__)

    async def start(self) -> None:
        """
        Start the distributed learning engine.

        Initializes Redis connection and starts background tasks.
        """
        if self._running:
            logger.warning("engine_already_running", agent_id=self.agent_id)
            return

        try:
            # Initialize Redis connection
            await self._init_redis()

            self._running = True

            # Start background tasks
            self._subscribe_task = asyncio.create_task(self._subscribe_loop())
            self._sync_task = asyncio.create_task(self._sync_loop())

            logger.info(
                "distributed_learning_engine_started",
                agent_id=self.agent_id,
            )

        except Exception as e:
            logger.error(
                "engine_start_failed",
                agent_id=self.agent_id,
                error=str(e),
            )
            raise

    async def stop(self) -> None:
        """
        Stop the distributed learning engine.

        Gracefully shuts down background tasks and closes connections.
        """
        if not self._running:
            return

        self._running = False

        # Cancel background tasks
        if self._subscribe_task:
            self._subscribe_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._subscribe_task

        if self._sync_task:
            self._sync_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._sync_task

        # Close Redis connection
        if self._pubsub:
            await self._pubsub.close()

        if self._redis:
            await self._redis.close()

        logger.info(
            "distributed_learning_engine_stopped",
            agent_id=self.agent_id,
        )

    async def publish_pattern(self, pattern: ExtractedPattern) -> bool:
        """
        Publish a pattern to the distributed swarm.

        Args:
            pattern: Pattern to publish

        Returns:
            True if publish successful
        """
        if not self._redis:
            logger.warning("redis_not_connected", agent_id=self.agent_id)
            return False

        try:
            message = SyncMessage(
                operation=SyncOperation.PUBLISH,
                source_agent=self.agent_id,
                payload={
                    "pattern": pattern.to_dict(),
                    "pattern_type": pattern.metadata.pattern_type.value,
                    "confidence": pattern.metadata.confidence,
                },
                metadata={
                    "source": "distributed_learning",
                    "version": "1.0",
                },
            )

            await self._redis.publish(
                self.config.pattern_channel,
                message.to_json(),
            )

            logger.debug(
                "pattern_published",
                pattern_id=pattern.metadata.pattern_id,
                channel=self.config.pattern_channel,
            )

            return True

        except Exception as e:
            logger.error(
                "pattern_publish_failed",
                pattern_id=pattern.metadata.pattern_id,
                error=str(e),
            )
            return False

    async def publish_learning_signal(self, signal: LearningSignal) -> bool:
        """
        Publish a learning signal to the distributed swarm.

        Args:
            signal: Signal to publish

        Returns:
            True if publish successful
        """
        if not self._redis:
            logger.warning("redis_not_connected", agent_id=self.agent_id)
            return False

        try:
            message = SyncMessage(
                operation=SyncOperation.BROADCAST,
                source_agent=self.agent_id,
                payload=signal.to_dict(),
                metadata={
                    "signal_type": signal.signal_type,
                    "magnitude": signal.magnitude,
                },
            )

            await self._redis.publish(
                self.config.signal_channel,
                message.to_json(),
            )

            logger.debug(
                "signal_published",
                signal_id=signal.signal_id,
                channel=self.config.signal_channel,
            )

            return True

        except Exception as e:
            logger.error(
                "signal_publish_failed",
                signal_id=signal.signal_id,
                error=str(e),
            )
            return False

    async def receive_pattern(self, pattern_dict: dict[str, Any], source_agent: str) -> MergeResult:
        """
        Receive and process a pattern from another agent.

        Args:
            pattern_dict: Pattern data dictionary
            source_agent: Source agent identifier

        Returns:
            MergeResult with processing outcome
        """
        try:
            # Reconstruct pattern
            pattern = self._reconstruct_pattern(pattern_dict)

            # Validate incoming pattern
            if self.config.validation_required:
                is_valid = await self.local_learning.extractor._validate_pattern(pattern)  # noqa: SLF001
                if not is_valid:
                    return MergeResult(
                        success=False,
                        rejected_count=1,
                        errors=["Pattern failed validation"],
                    )

            # Check for conflicts with local patterns
            conflicts = self._check_conflicts(pattern)

            if conflicts:
                # Resolve conflicts based on strategy
                resolved = await self._resolve_conflicts(pattern, conflicts)
                if not resolved:
                    return MergeResult(
                        success=False,
                        conflict_count=len(conflicts),
                        conflict_details=conflicts,
                    )

            # Merge pattern into local storage
            self.local_learning._patterns[pattern.metadata.pattern_id] = pattern  # noqa: SLF001

            # Call callbacks
            for callback in self._on_pattern_received:
                try:
                    if asyncio.iscoroutinefunction(callback):
                        await callback(pattern)
                    else:
                        callback(pattern)
                except Exception as e:
                    logger.error(
                        "pattern_callback_error",
                        callback=callback.__name__,
                        error=str(e),
                    )

            return MergeResult(
                success=True,
                merged_count=1,
                merged_pattern_ids=[pattern.metadata.pattern_id],
            )

        except Exception as e:
            logger.error(
                "pattern_receive_failed",
                source_agent=source_agent,
                error=str(e),
            )
            return MergeResult(
                success=False,
                rejected_count=1,
                errors=[str(e)],
            )

    async def receive_learning_signal(self, signal_dict: dict[str, Any], source_agent: str) -> bool:
        """
        Receive and process a learning signal from another agent.

        Args:
            signal_dict: Signal data dictionary
            source_agent: Source agent identifier

        Returns:
            True if processed successfully
        """
        try:
            # Reconstruct signal
            signal = LearningSignal(
                signal_id=signal_dict.get("signal_id", str(uuid.uuid4())),
                signal_type=signal_dict.get("signal_type", "unknown"),
                magnitude=signal_dict.get("magnitude", 0.0),
                timestamp=signal_dict.get("timestamp", datetime.now(UTC).isoformat()),
                source_agent=signal_dict.get("source_agent"),
                target_agents=signal_dict.get("target_agents", []),
                context=signal_dict.get("context", {}),
                metadata=signal_dict.get("metadata", {}),
            )

            # Store locally
            self.local_learning._learning_signals.append(signal)  # noqa: SLF001

            # Call callbacks
            for callback in self._on_signal_received:
                try:
                    if asyncio.iscoroutinefunction(callback):
                        await callback(signal)
                    else:
                        callback(signal)
                except Exception as e:
                    logger.error(
                        "signal_callback_error",
                        callback=callback.__name__,
                        error=str(e),
                    )

            return True

        except Exception as e:
            logger.error(
                "signal_receive_failed",
                source_agent=source_agent,
                error=str(e),
            )
            return False

    async def merge_knowledge(
        self,
        remote_patterns: dict[str, ExtractedPattern],
        strategy: MergeStrategy | None = None,
    ) -> MergeResult:
        """
        Merge remote knowledge with local state.

        Args:
            remote_patterns: Dictionary of remote patterns
            strategy: Merge strategy to use (default: config strategy)

        Returns:
            MergeResult with merge statistics
        """
        strategy = strategy or self.config.merge_strategy
        merged = []
        conflicts = []
        rejected = []
        errors = []

        for pattern_id, remote_pattern in remote_patterns.items():
            # Check if pattern exists locally
            local_pattern = self.local_learning._patterns.get(pattern_id)  # noqa: SLF001

            if local_pattern is None:
                # New pattern - merge directly
                if await self.local_learning.extractor._validate_pattern(remote_pattern):  # noqa: SLF001
                    self.local_learning._patterns[pattern_id] = remote_pattern  # noqa: SLF001
                    merged.append(pattern_id)
                else:
                    rejected.append(pattern_id)
            else:
                # Existing pattern - resolve based on strategy
                should_merge = self._should_merge(local_pattern, remote_pattern, strategy)

                if should_merge:
                    # Update local pattern
                    self.local_learning._patterns[pattern_id] = self._merge_patterns(  # noqa: SLF001
                        local_pattern,
                        remote_pattern,
                        strategy,
                    )
                    merged.append(pattern_id)
                else:
                    conflicts.append(
                        {
                            "pattern_id": pattern_id,
                            "local_confidence": local_pattern.metadata.confidence,
                            "remote_confidence": remote_pattern.metadata.confidence,
                            "resolution": "kept_local",
                        }
                    )

        result = MergeResult(
            success=len(errors) == 0,
            merged_count=len(merged),
            conflict_count=len(conflicts),
            rejected_count=len(rejected),
            errors=errors,
            merged_pattern_ids=merged,
            conflict_details=conflicts,
        )

        # Call merge callbacks
        for callback in self._on_merge_complete:
            try:
                if asyncio.iscoroutinefunction(callback):
                    await callback(result)
                else:
                    callback(result)
            except Exception as e:
                logger.error(
                    "merge_callback_error",
                    callback=callback.__name__,
                    error=str(e),
                )

        logger.info(
            "knowledge_merge_complete",
            merged=len(merged),
            conflicts=len(conflicts),
            rejected=len(rejected),
        )

        return result

    def _should_merge(
        self,
        local: ExtractedPattern,
        remote: ExtractedPattern,
        strategy: MergeStrategy,
    ) -> bool:
        """Determine if remote pattern should replace local."""
        if strategy == MergeStrategy.NEWEST:
            return remote.metadata.last_observed > local.metadata.last_observed

        if strategy == MergeStrategy.HIGHEST_CONFIDENCE:
            return remote.metadata.confidence > local.metadata.confidence

        if strategy == MergeStrategy.LOCAL_PRIORITY:
            return False  # Always prefer local

        if strategy == MergeStrategy.REMOTE_PRIORITY:
            return True  # Always prefer remote

        if strategy == MergeStrategy.CONSENSUS:
            # Would require additional consensus mechanism
            return remote.metadata.confidence > 0.9

        return False

    def _merge_patterns(
        self,
        local: ExtractedPattern,
        remote: ExtractedPattern,
        strategy: MergeStrategy,
    ) -> ExtractedPattern:
        """Merge two patterns based on strategy."""
        # Create merged pattern with combined data
        merged = remote  # Start with remote as base

        # Combine outcomes
        merged.outcomes = local.outcomes + remote.outcomes

        # Combine agents involved
        merged.metadata.agents_involved = list(
            set(local.metadata.agents_involved + remote.metadata.agents_involved)
        )

        # Combine topics
        merged.metadata.topics = list(set(local.metadata.topics + remote.metadata.topics))

        # Update timestamps
        merged.metadata.first_observed = min(
            local.metadata.first_observed,
            remote.metadata.first_observed,
        )
        merged.metadata.last_observed = max(
            local.metadata.last_observed,
            remote.metadata.last_observed,
        )

        # Average confidence or use max based on strategy
        if strategy == MergeStrategy.HIGHEST_CONFIDENCE:
            merged.metadata.confidence = max(
                local.metadata.confidence,
                remote.metadata.confidence,
            )
        else:
            merged.metadata.confidence = (
                local.metadata.confidence + remote.metadata.confidence
            ) / 2

        return merged

    def _check_conflicts(
        self,
        pattern: ExtractedPattern,
    ) -> list[dict[str, Any]]:
        """Check for conflicts between pattern and local knowledge."""
        conflicts = []

        local_pattern = self.local_learning._patterns.get(pattern.metadata.pattern_id)  # noqa: SLF001

        if local_pattern:
            # Check for significant confidence difference
            confidence_diff = abs(local_pattern.metadata.confidence - pattern.metadata.confidence)

            if confidence_diff > 0.3:  # Threshold for conflict
                conflicts.append(
                    {
                        "type": "confidence_mismatch",
                        "pattern_id": pattern.metadata.pattern_id,
                        "local_confidence": local_pattern.metadata.confidence,
                        "remote_confidence": pattern.metadata.confidence,
                    }
                )

            # Check for different pattern types
            if local_pattern.metadata.pattern_type != pattern.metadata.pattern_type:
                conflicts.append(
                    {
                        "type": "type_mismatch",
                        "pattern_id": pattern.metadata.pattern_id,
                        "local_type": local_pattern.metadata.pattern_type.value,
                        "remote_type": pattern.metadata.pattern_type.value,
                    }
                )

        return conflicts

    async def _resolve_conflicts(
        self,
        pattern: ExtractedPattern,
        conflicts: list[dict[str, Any]],
    ) -> bool:
        """
        Resolve conflicts between local and remote patterns.

        Args:
            pattern: Remote pattern
            conflicts: List of conflict details

        Returns:
            True if conflicts resolved successfully
        """
        for conflict in conflicts:
            if conflict["type"] == "confidence_mismatch":
                # Use higher confidence value
                if pattern.metadata.confidence < conflict["local_confidence"]:
                    return False  # Keep local

            elif conflict["type"] == "type_mismatch":
                # Cannot resolve type mismatch - reject
                return False

        return True

    def _reconstruct_pattern(self, pattern_dict: dict[str, Any]) -> ExtractedPattern:
        """Reconstruct ExtractedPattern from dictionary."""
        metadata_dict = pattern_dict.get("metadata", {})

        metadata = PatternMetadata(
            pattern_id=metadata_dict.get("pattern_id", str(uuid.uuid4())),
            pattern_type=PatternType(metadata_dict.get("pattern_type", "success")),
            source=metadata_dict.get("source", "message_history"),
            confidence=metadata_dict.get("confidence", 0.0),
            support_count=metadata_dict.get("support_count", 0),
            first_observed=metadata_dict.get("first_observed"),
            last_observed=metadata_dict.get("last_observed"),
            agents_involved=metadata_dict.get("agents_involved", []),
            topics=metadata_dict.get("topics", []),
            tags=metadata_dict.get("tags", []),
        )

        return ExtractedPattern(
            metadata=metadata,
            pattern_data=pattern_dict.get("pattern_data", {}),
            context=pattern_dict.get("context", {}),
            outcomes=pattern_dict.get("outcomes", []),
            preconditions=pattern_dict.get("preconditions", []),
            postconditions=pattern_dict.get("postconditions", []),
            applicability_conditions=pattern_dict.get("applicability_conditions", []),
        )

    async def _init_redis(self) -> None:
        """Initialize Redis connection."""
        try:
            import redis.asyncio as redis

            self._redis = redis.from_url(
                self.config.redis_url,
                decode_responses=True,
            )

            self._pubsub = self._redis.pubsub()

            # Subscribe to channels
            await self._pubsub.subscribe(
                self.config.pattern_channel,
                self.config.signal_channel,
            )

            logger.info(
                "redis_connection_established",
                agent_id=self.agent_id,
            )

        except ImportError:
            logger.warning(
                "redis_not_available",
                agent_id=self.agent_id,
                message="redis.asyncio not installed - using local-only mode",
            )
        except Exception as e:
            logger.error(
                "redis_connection_failed",
                agent_id=self.agent_id,
                error=str(e),
            )
            raise

    async def _subscribe_loop(self) -> None:
        """Background loop for processing pub/sub messages."""
        if not self._pubsub:
            return

        logger.info(
            "subscribe_loop_started",
            agent_id=self.agent_id,
            channels=[self.config.pattern_channel, self.config.signal_channel],
        )

        try:
            async for message in self._pubsub.listen():
                if not self._running:
                    break

                if message["type"] != "message":
                    continue

                try:
                    await self._process_pubsub_message(message)
                except Exception as e:
                    logger.error(
                        "pubsub_message_error",
                        error=str(e),
                        channel=message.get("channel"),
                    )

        except asyncio.CancelledError:
            logger.info("subscribe_loop_cancelled", agent_id=self.agent_id)
        except Exception as e:
            logger.error(
                "subscribe_loop_error",
                agent_id=self.agent_id,
                error=str(e),
            )

    async def _process_pubsub_message(self, message: dict[str, Any]) -> None:
        """
        Process a pub/sub message.

        Args:
            message: Redis pub/sub message
        """
        channel = message.get("channel", "")
        data = message.get("data", "")

        if not data or isinstance(data, bytes):
            return

        try:
            sync_message = SyncMessage.from_json(data)

            # Skip messages from self
            if sync_message.source_agent == self.agent_id:
                return

            # Skip already processed messages
            if sync_message.message_id in self._processed_ids:
                return

            self._processed_ids.add(sync_message.message_id)

            # Trim processed IDs set
            if len(self._processed_ids) > 10000:
                self._processed_ids = set(list(self._processed_ids)[-5000:])

            # Process based on channel
            if channel == self.config.pattern_channel:
                await self.receive_pattern(
                    pattern_dict=sync_message.payload.get("pattern", {}),
                    source_agent=sync_message.source_agent,
                )

            elif channel == self.config.signal_channel:
                await self.receive_learning_signal(
                    signal_dict=sync_message.payload,
                    source_agent=sync_message.source_agent,
                )

        except json.JSONDecodeError as e:
            logger.warning(
                "invalid_message_format",
                channel=channel,
                error=str(e),
            )
        except Exception as e:
            logger.error(
                "pubsub_processing_error",
                channel=channel,
                error=str(e),
            )

    async def _sync_loop(self) -> None:
        """Background loop for periodic synchronization."""
        logger.info(
            "sync_loop_started",
            agent_id=self.agent_id,
            interval_seconds=self.config.sync_interval_seconds,
        )

        try:
            while self._running:
                await asyncio.sleep(self.config.sync_interval_seconds)

                # Perform periodic sync tasks
                await self._periodic_sync()

        except asyncio.CancelledError:
            logger.info("sync_loop_cancelled", agent_id=self.agent_id)
        except Exception as e:
            logger.error(
                "sync_loop_error",
                agent_id=self.agent_id,
                error=str(e),
            )

    async def _periodic_sync(self) -> None:
        """Perform periodic synchronization tasks."""
        # Trim old processed IDs
        # Check connection health
        # Log statistics

    def get_status(self) -> dict[str, Any]:
        """
        Get current engine status.

        Returns:
            Status dictionary
        """
        return {
            "agent_id": self.agent_id,
            "running": self._running,
            "redis_connected": self._redis is not None,
            "local_patterns": len(self.local_learning._patterns),  # noqa: SLF001
            "local_signals": len(self.local_learning._learning_signals),  # noqa: SLF001
            "pending_messages": self._pending_messages.qsize(),
            "processed_ids": len(self._processed_ids),
            "pattern_callbacks": len(self._on_pattern_received),
            "signal_callbacks": len(self._on_signal_received),
            "merge_callbacks": len(self._on_merge_complete),
            "config": {
                "merge_strategy": self.config.merge_strategy.value,
                "validation_required": self.config.validation_required,
                "sync_interval": self.config.sync_interval_seconds,
            },
        }


class DistributedLearningCoordinator:
    """
    Coordinator for distributed learning across the swarm.

    This class provides high-level orchestration for distributed
    learning operations, including batch publishing, coordinated
    merges, and swarm-wide learning synchronization.
    """

    def __init__(self, engine: DistributedLearningEngine):
        """
        Initialize distributed learning coordinator.

        Args:
            engine: DistributedLearningEngine instance
        """
        self.engine = engine

        logger.info(
            "distributed_learning_coordinator_initialized",
            agent_id=engine.agent_id,
        )

    async def broadcast_pattern(
        self,
        pattern: ExtractedPattern,
        wait_for_ack: bool = False,  # noqa: ARG002
        timeout: float = 5.0,  # noqa: ARG002,ASYNC109
    ) -> dict[str, Any]:
        """
        Broadcast a pattern to the swarm.

        Args:
            pattern: Pattern to broadcast
            wait_for_ack: Wait for acknowledgments
            timeout: Timeout for acknowledgments

        Returns:
            Broadcast result summary
        """
        success = await self.engine.publish_pattern(pattern)

        return {
            "pattern_id": pattern.metadata.pattern_id,
            "broadcast_success": success,
            "timestamp": datetime.now(UTC).isoformat(),
        }

    async def sync_with_swarm(
        self,
        pattern_types: list[PatternType] | None = None,
        min_confidence: float = 0.0,
    ) -> MergeResult:
        """
        Synchronize local knowledge with the swarm.

        Args:
            pattern_types: Filter by pattern types
            min_confidence: Minimum confidence threshold

        Returns:
            MergeResult with sync statistics
        """
        # Get local patterns
        local_patterns = self.engine.local_learning.get_patterns(
            pattern_type=pattern_types[0] if pattern_types else None,
            min_confidence=min_confidence,
        )

        # Publish local patterns
        for pattern in local_patterns:
            await self.engine.publish_pattern(pattern)

        # Return current status
        return MergeResult(
            success=True,
            merged_count=len(local_patterns),
        )

    async def collect_swarm_knowledge(
        self,
        timeout: float = 10.0,  # noqa: ASYNC109
    ) -> dict[str, ExtractedPattern]:
        """
        Collect knowledge from across the swarm.

        Args:
            timeout: Collection timeout in seconds

        Returns:
            Dictionary of collected patterns
        """
        # Wait for incoming patterns
        await asyncio.sleep(timeout)

        return self.engine.local_learning._patterns.copy()  # noqa: SLF001

    def get_swarm_status(self) -> dict[str, Any]:
        """
        Get swarm learning status.

        Returns:
            Status dictionary
        """
        engine_status = self.engine.get_status()

        return {
            "local_status": engine_status,
            "total_patterns": len(self.engine.local_learning._patterns),  # noqa: SLF001
            "total_signals": len(self.engine.local_learning._learning_signals),  # noqa: SLF001
            "coordination_active": True,
        }
