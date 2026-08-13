"""
JetStream Manager for Heretek Swarm Event Mesh.

This module provides comprehensive NATS JetStream management capabilities:
- Stream configuration and lifecycle management
- Consumer management with durable subscriptions
- Message retention policies
- Stream monitoring and statistics
- Zero-trust security integration

Streams Managed:
- AGENT_EVENTS - All agent state changes
- WORKFLOW_EVENTS - Workflow execution events
- CONSCIOUSNESS_METRICS - Phi, coherence, emergence metrics
- SYSTEM_HEALTH - Heartbeats, resource usage
"""

import asyncio
import builtins
import contextlib
import json
import os
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

import structlog

from heretek_swarm.security.zero_trust import LayerResult, ZeroTrustResult, ZeroTrustValidator

logger = structlog.get_logger(__name__)

# Try to import NATS
try:
    import nats
    from nats.errors import ConnectionClosedError, NatsError, TimeoutError  # noqa: A004

    NATS_AVAILABLE = True
except ImportError:
    NATS_AVAILABLE = False
    NatsError = Exception
    TimeoutError = Exception  # noqa: A001
    ConnectionClosedError = Exception


class RetentionPolicy(StrEnum):
    """Stream retention policies."""

    LIMITS = "limits"  # Retain until max messages/bytes/age
    INTEREST = "interest"  # Retain while consumers interested
    WORKQUEUE = "workqueue"  # Retain until acknowledged


class StorageType(StrEnum):
    """Stream storage types."""

    FILE = "file"
    MEMORY = "memory"


class DeliverPolicy(StrEnum):
    """Consumer delivery policies."""

    ALL = "all"  # Start from beginning
    LAST = "last"  # Start from last message
    NEW = "new"  # Only new messages
    BY_START_SEQUENCE = "by_start_sequence"  # Start from specific sequence
    BY_START_TIME = "by_start_time"  # Start from specific timestamp


class AckPolicy(StrEnum):
    """Consumer acknowledgment policies."""

    EXPLICIT = "explicit"  # Must acknowledge each message
    ALL = "all"  # Acknowledge all up to this message
    NONE = "none"  # No acknowledgment required


@dataclass
class JetStreamConfig:
    """
    JetStream configuration model.

    Attributes:
        stream_name: Unique stream identifier
        subjects: List of subjects to capture (supports wildcards)
        retention: Retention policy (limits, interest, workqueue)
        max_messages: Maximum messages to retain
        max_age: Maximum age (e.g., "72h", "7d")
        storage: Storage type (file, memory)
        replicas: Number of replicas for redundancy
        max_bytes: Maximum size in bytes
        description: Human-readable description
        metadata: Custom metadata for the stream
    """

    stream_name: str
    subjects: list[str]
    retention: RetentionPolicy = RetentionPolicy.LIMITS
    max_messages: int = 1000000
    max_age: str = "72h"
    storage: StorageType = StorageType.FILE
    replicas: int = 1
    max_bytes: int = 1073741824  # 1GB default
    description: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "stream_name": self.stream_name,
            "subjects": self.subjects,
            "retention": self.retention.value,
            "max_messages": self.max_messages,
            "max_age": self.max_age,
            "storage": self.storage.value,
            "replicas": self.replicas,
            "max_bytes": self.max_bytes,
            "description": self.description,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "JetStreamConfig":
        """Create from dictionary."""
        return cls(
            stream_name=data["stream_name"],
            subjects=data["subjects"],
            retention=RetentionPolicy(data.get("retention", "limits")),
            max_messages=data.get("max_messages", 1000000),
            max_age=data.get("max_age", "72h"),
            storage=StorageType(data.get("storage", "file")),
            replicas=data.get("replicas", 1),
            max_bytes=data.get("max_bytes", 1073741824),
            description=data.get("description"),
            metadata=data.get("metadata", {}),
        )


@dataclass
class ConsumerConfig:
    """
    JetStream consumer configuration.

    Attributes:
        durable_name: Durable consumer name (persists across reconnects)
        stream_name: Source stream name
        deliver_policy: When to start delivering messages
        ack_policy: Acknowledgment policy
        max_deliver: Maximum delivery attempts
        ack_wait: Time to wait for acknowledgment
        filter_subject: Subject filter for this consumer
        description: Human-readable description
    """

    durable_name: str
    stream_name: str
    deliver_policy: DeliverPolicy = DeliverPolicy.ALL
    ack_policy: AckPolicy = AckPolicy.EXPLICIT
    max_deliver: int = 100
    ack_wait: float = 30.0  # seconds
    filter_subject: str | None = None
    description: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "durable_name": self.durable_name,
            "stream_name": self.stream_name,
            "deliver_policy": self.deliver_policy.value,
            "ack_policy": self.ack_policy.value,
            "max_deliver": self.max_deliver,
            "ack_wait": self.ack_wait,
            "filter_subject": self.filter_subject,
            "description": self.description,
        }


@dataclass
class StreamInfo:
    """Stream information and statistics."""

    name: str
    config: JetStreamConfig
    created_at: datetime
    state: dict[str, Any]
    cluster: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "name": self.name,
            "config": self.config.to_dict(),
            "created_at": self.created_at.isoformat(),
            "state": self.state,
            "cluster": self.cluster,
        }


class JetStreamManager:
    """
    NATS JetStream Manager for Heretek Swarm.

    Provides comprehensive stream and consumer management:
    - Create/delete streams with configuration
    - Manage durable consumers
    - Monitor stream state and statistics
    - Zero-trust security integration
    - Graceful fallback to in-memory storage

    Example:
        ```python
        manager = JetStreamManager(servers=["nats://localhost:4222"])
        await manager.connect()

        # Create stream
        config = JetStreamConfig(
            stream_name="AGENT_EVENTS",
            subjects=["agent.*.events", "agent.*.state"],
            retention=RetentionPolicy.LIMITS,
            max_age="168h",  # 7 days
        )
        await manager.create_stream(config)

        # Create durable consumer
        consumer_config = ConsumerConfig(
            durable_name="agent-processor",
            stream_name="AGENT_EVENTS",
            deliver_policy=DeliverPolicy.NEW,
        )
        await manager.create_consumer(consumer_config, callback)
        ```
    """

    # Predefined stream configurations
    DEFAULT_STREAMS = {  # noqa: RUF012
        "AGENT_EVENTS": JetStreamConfig(
            stream_name="AGENT_EVENTS",
            subjects=["agent.*.events", "agent.*.state", "agent.*.lifecycle"],
            retention=RetentionPolicy.LIMITS,
            max_messages=500000,
            max_age="168h",  # 7 days
            storage=StorageType.FILE,
            replicas=1,
            max_bytes=536870912,  # 512MB
            description="All agent state changes and lifecycle events",
        ),
        "WORKFLOW_EVENTS": JetStreamConfig(
            stream_name="WORKFLOW_EVENTS",
            subjects=["workflow.*.events", "workflow.*.state", "workflow.*.execution"],
            retention=RetentionPolicy.LIMITS,
            max_messages=200000,
            max_age="72h",  # 3 days
            storage=StorageType.FILE,
            replicas=1,
            max_bytes=268435456,  # 256MB
            description="Workflow execution events and state changes",
        ),
        "CONSCIOUSNESS_METRICS": JetStreamConfig(
            stream_name="CONSCIOUSNESS_METRICS",
            subjects=["consciousness.*", "phi.*", "coherence.*", "emergence.*"],
            retention=RetentionPolicy.LIMITS,
            max_messages=100000,
            max_age="336h",  # 14 days
            storage=StorageType.FILE,
            replicas=1,
            max_bytes=134217728,  # 128MB
            description="Phi, coherence, and emergence metrics",
        ),
        "SYSTEM_HEALTH": JetStreamConfig(
            stream_name="SYSTEM_HEALTH",
            subjects=["health.*", "heartbeat.*", "resources.*", "metrics.*"],
            retention=RetentionPolicy.LIMITS,
            max_messages=1000000,
            max_age="24h",  # 1 day
            storage=StorageType.MEMORY,
            replicas=1,
            max_bytes=107374182,  # 100MB
            description="System health, heartbeats, and resource usage",
        ),
    }

    def __init__(
        self,
        servers: list[str] | None = None,
        name: str = "heretek-jetstream-manager",
        zero_trust_enabled: bool = True,
        fallback_enabled: bool = True,
    ) -> None:
        """
        Initialize JetStream Manager.

        Args:
            servers: List of NATS server URLs
            name: Client name for identification
            zero_trust_enabled: Enable zero-trust security
            fallback_enabled: Enable in-memory fallback
        """
        if servers:
            self.servers = servers
        else:
            nats_url = os.getenv("HERETEK_NATS_URL")
            if not nats_url:
                raise RuntimeError(
                    "HERETEK_NATS_URL is required. Set it to nats://host:port "
                    "or use docker compose."
                )
            self.servers = [s.strip() for s in nats_url.split(",")]
        self.client_name = name
        self.zero_trust_enabled = zero_trust_enabled
        self.fallback_enabled = fallback_enabled

        # Connection state
        self._nc = None
        self._js = None
        self._connected = False
        self._fallback_mode = False

        # Stream state
        self._streams: dict[str, StreamInfo] = {}
        self._consumers: dict[str, Any] = {}
        self._subscriptions: dict[str, Any] = {}

        # In-memory fallback storage
        self._memory_store: dict[str, list[dict[str, Any]]] = {}
        self._memory_sequences: dict[str, int] = {}

        # Zero-trust validator
        self._zero_trust = ZeroTrustValidator() if zero_trust_enabled else None

        # Statistics
        self._stats = {
            "streams_created": 0,
            "streams_deleted": 0,
            "consumers_created": 0,
            "messages_published": 0,
            "messages_consumed": 0,
            "fallback_activations": 0,
        }

        logger.info(
            "JetStreamManager initialized",
            servers=self.servers,
            zero_trust=self.zero_trust_enabled,
            fallback=self.fallback_enabled,
        )

    @property
    def is_connected(self) -> bool:
        """Check if connected to NATS with JetStream."""
        return self._connected and self._js is not None

    @property
    def is_fallback_mode(self) -> bool:
        """Check if running in fallback mode."""
        return self._fallback_mode

    @property
    def stream_names(self) -> list[str]:
        """Get list of managed stream names."""
        return list(self._streams.keys())

    async def connect(self) -> bool:
        """
        Connect to NATS servers and initialize JetStream.

        Returns:
            True if connected successfully
        """
        if not NATS_AVAILABLE:
            logger.warning("NATS not available, enabling fallback mode")
            return await self._enable_fallback()

        try:
            # Connect to NATS
            self._nc = await nats.connect(
                self.servers[0],
                name=self.client_name,
                reconnect_time_wait=1.0,
                max_reconnect_attempts=5,
            )

            # Initialize JetStream context
            self._js = self._nc.jetstream()
            self._connected = True

            logger.info("Connected to NATS with JetStream")

            # Audit logging
            if self.zero_trust_enabled:
                await self._audit_connection()

            return True

        except Exception:
            logger.error("Failed to connect to NATS: {e}")
            if self.fallback_enabled:
                return await self._enable_fallback()
            return False

    async def disconnect(self) -> None:
        """Disconnect from NATS and cleanup."""
        # Cleanup subscriptions
        for sub in self._subscriptions.values():
            with contextlib.suppress(Exception):
                await sub.unsubscribe()

        # Close NATS connection
        if self._nc:
            with contextlib.suppress(Exception):
                await self._nc.close()

        self._connected = False
        self._js = None
        self._nc = None

        logger.info("Disconnected from NATS JetStream")

    async def _enable_fallback(self) -> bool:
        """Enable in-memory fallback mode."""
        self._fallback_mode = True
        self._connected = True  # Consider "connected" for API compatibility
        self._stats["fallback_activations"] += 1

        logger.info("JetStreamManager running in fallback mode (in-memory)")
        return True

    async def _audit_connection(self) -> None:
        """Audit connection event."""
        if not self._zero_trust:
            return

        request_id = f"js-connect-{datetime.now(UTC).isoformat()}"
        result = ZeroTrustResult(
            passed=True,
            layer1=LayerResult(layer="connection", passed=True),
            request_id=request_id,
        )
        self._zero_trust.audit_logger.log(
            event_type="jetstream_connect",
            result=result,
            additional_context={"client_name": self.client_name},
        )

    async def _audit_stream_operation(
        self,
        operation: str,
        stream_name: str,
        success: bool,
    ) -> None:
        """Audit stream operation."""
        if not self._zero_trust:
            return

        request_id = f"js-{operation}-{stream_name}-{datetime.now(UTC).isoformat()}"
        result = ZeroTrustResult(
            passed=success,
            layer1=LayerResult(layer="stream_operation", passed=success),
            request_id=request_id,
        )
        self._zero_trust.audit_logger.log(
            event_type=f"jetstream_{operation}",
            result=result,
            additional_context={"stream_name": stream_name},
        )

    async def create_stream(self, config: JetStreamConfig) -> bool:
        """
        Create a JetStream with the given configuration.
        """
        if not self._connected:
            logger.error("Not connected, cannot create stream")
            return False

        if self._fallback_mode:
            return self._create_stream_fallback(config)

        try:
            import nats.js.api as js_api

            stream_config = self._build_stream_config(config, js_api)
            stream_info = await self._js.add_stream(config=stream_config)

            self._streams[config.stream_name] = StreamInfo(
                name=config.stream_name,
                config=config,
                created_at=datetime.now(UTC),
                state={
                    "messages": stream_info.state.messages if stream_info.state else 0,
                    "bytes": stream_info.state.bytes if stream_info.state else 0,
                },
            )

            self._stats["streams_created"] += 1
            logger.info("JetStream created", stream_name=config.stream_name, subjects=config.subjects)
            await self._audit_stream_operation("create_stream", config.stream_name, True)
            return True

        except Exception:
            logger.error("Failed to create stream: {e}")
            await self._audit_stream_operation("create_stream", config.stream_name, False)
            return False

    def _build_stream_config(self, config: JetStreamConfig, js_api: Any) -> Any:
        """Build a NATS StreamConfig from a JetStreamConfig."""
        storage_type = (
            js_api.StorageType.FILE
            if config.storage == StorageType.FILE
            else js_api.StorageType.MEMORY
        )
        retention_policy = getattr(
            js_api.RetentionPolicy,
            config.retention.value.upper(),
            js_api.RetentionPolicy.LIMITS,
        )
        max_age_ns = self._parse_duration_to_nanos(config.max_age)

        return js_api.StreamConfig(
            name=config.stream_name,
            subjects=config.subjects,
            storage=storage_type,
            retention=retention_policy,
            max_msgs=config.max_messages,
            max_age=max_age_ns,
            max_bytes=config.max_bytes,
            num_replicas=config.replicas,
            description=config.description,
            metadata=config.metadata,
        )

    def _create_stream_fallback(self, config: JetStreamConfig) -> bool:
        """Create stream in fallback mode."""
        self._memory_store[config.stream_name] = []
        self._memory_sequences[config.stream_name] = 0

        self._streams[config.stream_name] = StreamInfo(
            name=config.stream_name,
            config=config,
            created_at=datetime.now(UTC),
            state={"messages": 0, "bytes": 0},
        )

        self._stats["streams_created"] += 1
        logger.info("Fallback stream created: {config.stream_name}")
        return True

    async def delete_stream(self, stream_name: str) -> bool:
        """
        Delete a JetStream.

        Args:
            stream_name: Name of stream to delete

        Returns:
            True if deleted successfully
        """
        if not self._connected:
            return False

        if stream_name not in self._streams:
            logger.warning("Stream not found: {stream_name}")
            return False

        if self._fallback_mode:
            return self._delete_stream_fallback(stream_name)

        try:
            await self._js.delete_stream(stream_name)
            del self._streams[stream_name]
            self._stats["streams_deleted"] += 1

            logger.info("JetStream deleted: {stream_name}")
            await self._audit_stream_operation("delete_stream", stream_name, True)
            return True

        except Exception:
            logger.error("Failed to delete stream: {e}")
            await self._audit_stream_operation("delete_stream", stream_name, False)
            return False

    def _delete_stream_fallback(self, stream_name: str) -> bool:
        """Delete stream in fallback mode."""
        if stream_name in self._memory_store:
            del self._memory_store[stream_name]
        if stream_name in self._memory_sequences:
            del self._memory_sequences[stream_name]
        if stream_name in self._streams:
            del self._streams[stream_name]

        self._stats["streams_deleted"] += 1
        logger.info("Fallback stream deleted: {stream_name}")
        return True

    async def get_stream_info(self, stream_name: str) -> StreamInfo | None:
        """
        Get information about a stream.

        Args:
            stream_name: Name of stream

        Returns:
            StreamInfo or None if not found
        """
        if stream_name not in self._streams:
            return None

        if self._fallback_mode:
            return self._streams[stream_name]

        try:
            info = await self._js.stream_info(stream_name)

            # Update local state
            self._streams[stream_name].state = {
                "messages": info.state.messages if info.state else 0,
                "bytes": info.state.bytes if info.state else 0,
                "first_seq": info.state.first_seq if info.state else 0,
                "last_seq": info.state.last_seq if info.state else 0,
            }

            return self._streams[stream_name]

        except Exception:
            logger.error("Failed to get stream info: {e}")
            return self._streams[stream_name]

    async def list_streams(self) -> list[StreamInfo]:
        """Get list of all managed streams."""
        return list(self._streams.values())

    async def create_consumer(
        self,
        config: ConsumerConfig,
        callback: Callable[[str, dict[str, Any]], None],
    ) -> str | None:
        """
        Create a durable consumer with callback.

        Args:
            config: Consumer configuration
            callback: Async callback function (subject, data)

        Returns:
            Consumer ID or None if failed
        """
        if not self._connected:
            return None

        if config.stream_name not in self._streams:
            logger.warning("Stream not found: {config.stream_name}")
            return None

        if self._fallback_mode:
            return self._create_consumer_fallback(config, callback)

        try:
            import nats.js.api as js_api

            # Map delivery policy
            deliver_policy = getattr(
                js_api.DeliverPolicy,
                config.deliver_policy.value.upper(),
                js_api.DeliverPolicy.ALL,
            )

            # Map ack policy
            ack_policy = getattr(
                js_api.AckPolicy,
                config.ack_policy.value.upper(),
                js_api.AckPolicy.EXPLICIT,
            )

            # Create consumer
            consumer = await self._js.pull_subscribe(
                stream=config.stream_name,
                durable=config.durable_name,
                deliver_policy=deliver_policy,
                ack_policy=ack_policy,
                max_deliver=config.max_deliver,
                ack_wait=config.ack_wait,
                filter_subject=config.filter_subject,
            )

            consumer_id = f"{config.stream_name}_{config.durable_name}"
            self._consumers[consumer_id] = consumer

            # Start message processing
            asyncio.create_task(self._process_consumer_messages(consumer, callback, consumer_id))  # noqa: RUF006

            self._stats["consumers_created"] += 1

            logger.info(
                "Durable consumer created",
                consumer_id=consumer_id,
                stream=config.stream_name,
            )

            return consumer_id

        except Exception:
            logger.error("Failed to create consumer: {e}")
            return None

    def _create_consumer_fallback(
        self,
        config: ConsumerConfig,
        callback: Callable[[str, dict[str, Any]], None],
    ) -> str:
        """Create consumer in fallback mode."""
        consumer_id = f"{config.stream_name}_{config.durable_name}"
        self._consumers[consumer_id] = {
            "config": config,
            "callback": callback,
            "sequence": 0,
        }

        self._stats["consumers_created"] += 1
        logger.info("Fallback consumer created: {consumer_id}")
        return consumer_id

    async def _process_consumer_messages(
        self,
        consumer: Any,
        callback: Callable[[str, dict[str, Any]], None],
        consumer_id: str,  # noqa: ARG002
    ) -> None:
        """Process messages from a consumer."""
        while True:
            try:
                msgs = await consumer.fetch(batch=10, timeout=5.0)
                for msg in msgs:
                    try:
                        data = json.loads(msg.data.decode("utf-8"))
                        await self._invoke_callback(callback, msg.subject, data)
                        await msg.ack()
                        self._stats["messages_consumed"] += 1
                    except Exception:
                        logger.error("Error processing message: {e}")
                        await msg.nak()
            except builtins.TimeoutError:
                continue
            except Exception:
                logger.error("Consumer error: {e}")
                await asyncio.sleep(1.0)

    async def publish(
        self,
        stream_name: str,
        subject: str,
        data: dict[str, Any],
        correlation_id: str | None = None,
    ) -> bool:
        """
        Publish a message to a stream.

        Args:
            stream_name: Target stream name
            subject: Message subject
            data: Message payload
            correlation_id: Optional correlation ID for tracing

        Returns:
            True if published successfully
        """
        if not self._connected:
            return False

        if stream_name not in self._streams:
            logger.warning("Stream not found: {stream_name}")
            return False

        if self._fallback_mode:
            return self._publish_fallback(stream_name, subject, data)

        try:
            # Add metadata
            envelope = {
                "data": data,
                "metadata": {
                    "subject": subject,
                    "stream": stream_name,
                    "timestamp": datetime.now(UTC).isoformat(),
                },
            }
            if correlation_id:
                envelope["metadata"]["correlation_id"] = correlation_id

            # Publish to JetStream
            ack = await self._js.publish(subject, json.dumps(envelope).encode("utf-8"))

            self._stats["messages_published"] += 1

            logger.debug(
                "Message published",
                stream=stream_name,
                subject=subject,
                seq=ack.seq,
            )

            return True

        except Exception:
            logger.error("Failed to publish message: {e}")
            return False

    def _publish_fallback(
        self,
        stream_name: str,
        subject: str,
        data: dict[str, Any],
    ) -> bool:
        """Publish in fallback mode."""
        if stream_name not in self._memory_store:
            return False

        # Increment sequence
        self._memory_sequences[stream_name] += 1
        seq = self._memory_sequences[stream_name]

        # Store message
        message = {
            "sequence": seq,
            "subject": subject,
            "data": data,
            "timestamp": datetime.now(UTC).isoformat(),
        }
        self._memory_store[stream_name].append(message)

        self._stats["messages_published"] += 1
        logger.debug("Fallback message published: {stream_name}:{seq}")
        return True

    async def _replay_single_message(
        self,
        msg: Any,
        subject_filter: str | None,
        end_sequence: int | None,
        callback: Callable[[str, dict[str, Any]], None] | None,
    ) -> dict[str, Any] | None:
        """Process a single message during replay. Returns the message dict or None to skip."""
        try:
            envelope = json.loads(msg.data.decode("utf-8"))
            subject = msg.subject

            if subject_filter and not self._match_subject(subject, subject_filter):
                await msg.ack()
                return None

            seq = msg.metadata.sequence.stream if msg.metadata else 0
            if end_sequence and seq > end_sequence:
                await msg.ack()
                return None  # caller must break

            data = envelope.get("data", envelope)
            entry: dict[str, Any] = {
                "sequence": seq,
                "subject": subject,
                "data": data,
                "timestamp": envelope.get("metadata", {}).get("timestamp"),
            }

            if callback:
                await self._invoke_callback(callback, subject, data)

            await msg.ack()
            return entry
        except Exception:
            logger.error("Error replaying message: {e}")
            await msg.nak()
            return None

    async def replay_messages(
        self,
        stream_name: str,
        start_sequence: int | None = None,
        end_sequence: int | None = None,
        subject_filter: str | None = None,
        callback: Callable[[str, dict[str, Any]], None] | None = None,
    ) -> list[dict[str, Any]]:
        """
        Replay messages from a stream.

        Args:
            stream_name: Source stream name
            start_sequence: Start sequence number (default: beginning)
            end_sequence: End sequence number (default: end)
            subject_filter: Filter by subject pattern
            callback: Optional callback for each message

        Returns:
            List of replayed messages
        """
        if stream_name not in self._streams:
            logger.warning("Stream not found: {stream_name}")
            return []

        if self._fallback_mode:
            return self._replay_fallback(
                stream_name, start_sequence, end_sequence, subject_filter, callback
            )

        messages = []

        try:
            import nats.js.api as js_api

            # Determine deliver policy
            if start_sequence:
                deliver_policy = js_api.DeliverPolicy.BY_START_SEQUENCE
            else:
                deliver_policy = js_api.DeliverPolicy.ALL

            # Create temporary consumer
            consumer = await self._js.pull_subscribe(
                stream=stream_name,
                durable=f"replay_{datetime.now(UTC).strftime('%Y%m%d%H%M%S')}",
                deliver_policy=deliver_policy,
                opt_start_seq=start_sequence or 1,
            )

            # Fetch messages
            while True:
                try:
                    msgs = await consumer.fetch(batch=100, timeout=2.0)
                    for msg in msgs:
                        entry = await self._replay_single_message(
                            msg, subject_filter, end_sequence, callback
                        )
                        if entry is not None:
                            messages.append(entry)
                except builtins.TimeoutError:
                    break

            logger.info("Replayed {len(messages)} messages from {stream_name}")
            return messages

        except Exception:
            logger.error("Failed to replay messages: {e}")
            return []

    def _replay_fallback(
        self,
        stream_name: str,
        start_sequence: int | None,
        end_sequence: int | None,
        subject_filter: str | None,
        callback: Callable[[str, dict[str, Any]], None] | None,
    ) -> list[dict[str, Any]]:
        """Replay messages in fallback mode."""
        if stream_name not in self._memory_store:
            return []

        messages = []
        for msg in self._memory_store[stream_name]:
            seq = msg.get("sequence", 0)

            # Apply sequence filters
            if start_sequence and seq < start_sequence:
                continue
            if end_sequence and seq > end_sequence:
                break

            # Apply subject filter
            subject = msg.get("subject", "")
            if subject_filter and not self._match_subject(subject, subject_filter):
                continue

            messages.append(msg)

            if callback:
                if asyncio.iscoroutinefunction(callback):
                    callback(msg["subject"], msg["data"])
                else:
                    callback(msg["subject"], msg["data"])

        return messages

    @staticmethod
    async def _invoke_callback(
        callback: Callable[[str, dict[str, Any]], None],
        subject: str,
        data: dict[str, Any],
    ) -> None:
        """Invoke a message callback (sync or async)."""
        if asyncio.iscoroutinefunction(callback):
            await callback(subject, data)
        else:
            callback(subject, data)

    def _match_subject(self, subject: str, pattern: str) -> bool:
        """Match subject against wildcard pattern."""
        import fnmatch

        return fnmatch.fnmatch(subject, pattern)

    def _parse_duration_to_nanos(self, duration: str) -> int:
        """Parse duration string to nanoseconds."""
        # Parse formats like "72h", "7d", "168h"
        import re

        match = re.match(r"(\d+)([hdm])", duration.lower())
        if not match:
            return 0

        value = int(match.group(1))
        unit = match.group(2)

        if unit == "h":
            nanos = value * 3600 * 1_000_000_000
        elif unit == "d":
            nanos = value * 86400 * 1_000_000_000
        elif unit == "m":
            nanos = value * 30 * 86400 * 1_000_000_000
        else:
            nanos = 0

        return nanos

    async def get_stats(self) -> dict[str, Any]:
        """Get manager statistics."""
        return {
            **self._stats,
            "connected": self._connected,
            "fallback_mode": self._fallback_mode,
            "stream_count": len(self._streams),
            "consumer_count": len(self._consumers),
        }

    async def initialize_default_streams(self) -> dict[str, bool]:
        """
        Initialize all default streams.

        Returns:
            Dictionary of stream names to creation status
        """
        results = {}
        for name, config in self.DEFAULT_STREAMS.items():
            results[name] = await self.create_stream(config)
        return results


# Module singleton
_manager: JetStreamManager | None = None


def get_jetstream_manager() -> JetStreamManager:
    """Get or create the JetStream manager singleton."""
    global _manager
    if _manager is None:
        _manager = JetStreamManager()
    return _manager


async def setup_jetstream(
    servers: list[str] | None = None,
    create_default_streams: bool = True,
) -> JetStreamManager:
    """
    Setup and initialize JetStream manager.

    Args:
        servers: Optional NATS server URLs
        create_default_streams: Create default streams

    Returns:
        Initialized JetStreamManager
    """
    global _manager
    _manager = JetStreamManager(servers=servers)
    await _manager.connect()

    if create_default_streams:
        await _manager.initialize_default_streams()

    return _manager
