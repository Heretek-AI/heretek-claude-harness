"""
NATSEventMesh - NATS EventMesh Integration for Heretek Swarm

This module provides NATS-based event mesh integration with JetStream support:
- Asynchronous connection management with connection pooling
- Publish/subscribe patterns
- Request-reply pattern with timeout
- JetStream stream creation and management
- Durable consumer subscriptions
- Message replay for event sourcing
- Integration with existing EventMesh
- Graceful fallback to in-memory mesh if NATS unavailable

Reference: MiniMax Audit Lines 11-30 (EventMesh bug fix)
"""

import asyncio
import contextlib
import json
import os
import ssl
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
from pathlib import Path
from typing import Any

from heretek_swarm.infrastructure.nats.ca import CertificateAuthority

import structlog

logger = structlog.get_logger(__name__)

# Try to import NATS, but make it optional
try:
    import nats
    from nats.errors import Error as NatsError

    NATS_AVAILABLE = True
except ImportError:
    NATS_AVAILABLE = False
    NatsError = Exception


class ConnectionState(Enum):
    """NATS connection states."""

    DISCONNECTED = "disconnected"
    CONNECTING = "connecting"
    CONNECTED = "connected"
    RECONNECTING = "reconnecting"
    CLOSING = "closing"
    CLOSED = "closed"


@dataclass
class Subscription:
    """NATS subscription wrapper."""

    subject: str
    callback: Callable[["NATSEventMesh", str, dict[str, Any]], None]
    sid: str
    active: bool = True


@dataclass
class NATSMessage:
    """NATS message wrapper."""

    subject: str
    data: dict[str, Any]
    reply: str | None = None
    sid: str | None = None
    timestamp: str = field(default_factory=lambda: datetime.now(UTC).isoformat())


class NATSEventMesh:
    """
    NATS EventMesh integration for Heretek Swarm.

    Provides distributed messaging via NATS with:
    - Connection management and auto-reconnection
    - Publish/subscribe patterns
    - Request-reply pattern
    - Fallback to in-memory mesh if NATS unavailable

    Example:
        ```python
        # Initialize with NATS
        mesh = NATSEventMesh(
            servers=["nats://localhost:4222"],
            fallback=True
        )
        await mesh.connect()

        # Subscribe to subject
        async def handle_message(mesh, subject, data):
            print(f"Received: {data}")

        await mesh.subscribe("events.>", handle_message)

        # Publish message
        await mesh.publish("events.test", {"message": "hello"})

        # Request-reply
        response = await mesh.request(
            "events.query",
            {"query": "test"},
            timeout=5.0
        )
        ```
    """

    def __init__(
        self,
        servers: list[str] | None = None,
        name: str | None = None,
        fallback: bool = True,
        max_reconnect_attempts: int = 5,
        reconnect_time_wait: float = 1.0,
        ping_interval: int = 30,
        max_outstanding_pings: int = 1000,
        tls_enabled: bool | None = None,
        tls_ca_file: str | None = None,
        tls_cert_file: str | None = None,
        tls_key_file: str | None = None,
    ) -> None:
        """
        Initialize NATS EventMesh.

        Args:
            servers: List of NATS server URLs
            name: Client name
            fallback: Enable fallback to in-memory mesh
            max_reconnect_attempts: Max reconnection attempts
            reconnect_time_wait: Time to wait between reconnect attempts
            ping_interval: Ping interval in seconds
            max_outstanding_pings: Max outstanding pings
            tls_enabled: Enable mTLS. Default reads HERETEK_MTLS_ENABLED env var.
            tls_ca_file: Path to CA certificate PEM file.
            tls_cert_file: Path to client certificate PEM file.
            tls_key_file: Path to client key PEM file.
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
        self.client_name = name or "heretek-swarm"
        self.fallback = fallback
        self.max_reconnect_attempts = max_reconnect_attempts
        self.reconnect_time_wait = reconnect_time_wait
        self.ping_interval = ping_interval
        self.max_outstanding_pings = max_outstanding_pings

        # TLS / mTLS config
        self.tls_enabled = (
            tls_enabled
            if tls_enabled is not None
            else os.getenv("HERETEK_MTLS_ENABLED", "false").lower() == "true"
        )
        self.tls_ca_file = tls_ca_file or os.getenv("NATS_TLS_CA_FILE")
        self.tls_cert_file = tls_cert_file or os.getenv("NATS_TLS_CERT_FILE")
        self.tls_key_file = tls_key_file or os.getenv("NATS_TLS_KEY_FILE")

        # Temp cert file tracking for cleanup
        self._temp_cert_files: list[str] = []

        # Connection state
        self._state = ConnectionState.DISCONNECTED
        self._nc = None  # NATS connection
        self._js = None  # JetStream context
        self._js_context: Any | None = None  # JetStream context manager

        # JetStream streams
        self._streams: dict[str, dict[str, Any]] = {}

        # Subscriptions
        self._subscriptions: dict[str, Subscription] = {}
        self._subscription_ids: set[str] = set()

        # Durable consumers
        self._consumers: dict[str, Any] = {}

        # In-memory fallback
        self._fallback_mesh: _InMemoryFallback | None = None
        self._use_fallback = False

        # Connection lock
        self._lock = asyncio.Lock()

        logger.info(
            "NATSEventMesh initialized",
            extra={
                "servers": self.servers,
                "fallback": self.fallback,
                "nats_available": NATS_AVAILABLE,
            },
        )

    @property
    def is_connected(self) -> bool:
        """Check if connected to NATS or using fallback."""
        if self._state == ConnectionState.CONNECTED and self._nc is not None:
            return True
        # Also consider fallback mode as "connected"
        return bool(self._use_fallback and self._state == ConnectionState.CONNECTED)

    @property
    def jetstream_enabled(self) -> bool:
        """Check if JetStream is available."""
        return self._js is not None and NATS_AVAILABLE

    @property
    def client_count(self) -> int:
        """Get number of active subscriptions."""
        # Count subscriptions from both NATS and fallback
        count = len([s for s in self._subscriptions.values() if s.active])
        # Add fallback mesh subscriptions if in fallback mode
        if self._use_fallback and self._fallback_mesh is not None:
            count += self._fallback_mesh.subscription_count
        return count

    @property
    def mesh_type(self) -> str:
        """Return the mesh type identifier for observability."""
        return type(self).__name__

    @property
    def stream_count(self) -> int:
        """Get number of created streams."""
        return len(self._streams)

    async def connect(self) -> bool:
        """
        Connect to NATS servers.

        Returns:
            True if connected successfully
        """
        if not NATS_AVAILABLE:
            logger.warning("NATS not available, using fallback")
            return await self._enable_fallback()

        async with self._lock:
            self._state = ConnectionState.CONNECTING

            try:
                # Connect to first available server
                self._nc = await self._connect_to_server()

                if self._nc is not None:
                    self._state = ConnectionState.CONNECTED
                    logger.info("Connected to NATS")

                    # Initialize JetStream context
                    try:
                        self._js = self._nc.jetstream()
                        logger.info("JetStream context initialized")
                    except Exception:
                        logger.warning("JetStream not available: {e}")
                        self._js = None

                    return True

            except Exception as e:
                logger.error("Failed to connect to NATS", error=str(e))

            # Fallback to in-memory mesh
            if self.fallback:
                return await self._enable_fallback()

            self._state = ConnectionState.DISCONNECTED
            return False

    async def _connect_to_server(self) -> Any | None:
        """Connect to a NATS server with retry and optional mTLS."""
        last_error = None

        for server in self.servers:
            for attempt in range(self.max_reconnect_attempts):
                try:
                    server_display = server
                    logger.debug("Connecting to %s (attempt %d)", server, attempt + 1)

                    kwargs = self._build_connect_kwargs()
                    if self.tls_enabled:
                        kwargs["tls"] = self._build_ssl_context()
                        if server.startswith("nats://"):
                            server = server.replace("nats://", "tls://", 1)
                            server_display = server
                            logger.debug("mTLS enabled — using tls:// URL", server=server)

                    nc = await nats.connect(server, **kwargs)
                    self._log_connection_success(nc, server_display)
                    return nc

                except Exception as e:
                    last_error = e
                    self._log_connection_failure(server_display, e, attempt)
                    await asyncio.sleep(self.reconnect_time_wait)

        raise last_error or Exception("No servers available")

    def _build_connect_kwargs(self) -> dict[str, Any]:
        """Build kwargs dict for nats.connect()."""
        return {
            "name": self.client_name,
            "reconnect_time_wait": self.reconnect_time_wait,
            "ping_interval": self.ping_interval,
            "max_outstanding_pings": self.max_outstanding_pings,
            "max_reconnect_attempts": 1,
        }

    def _log_connection_success(self, nc: Any, server_display: str) -> None:
        """Log successful connection with optional TLS peer info."""
        if self.tls_enabled:
            peer_cert_subject = self._extract_peer_cert_subject(nc)
            logger.info(
                "nats_tls_connection_established",
                server=server_display,
                peer_cert_subject=peer_cert_subject,
            )
        else:
            logger.info("Connected to %s", server_display)

    @staticmethod
    def _extract_peer_cert_subject(nc: Any) -> str:
        """Extract peer certificate subject from NATS connection."""
        try:
            transport = getattr(nc, "_io_reader", None) or getattr(nc, "_transport", None)
            if transport is not None:
                sock = getattr(transport, "get_extra_info", None)
                if sock is not None:
                    peer_cert = sock("peercert")
                    if peer_cert is not None:
                        subject_attrs = peer_cert.get("subject", [])
                        cn = next((v for t, v in subject_attrs if t == "commonName"), "unknown")
                        return cn
        except Exception:
            logger.debug("Could not extract peer certificate subject")
        return "unknown"

    def _log_connection_failure(self, server: str, error: Exception, attempt: int) -> None:
        """Log connection failure with optional TLS context."""
        if self.tls_enabled:
            logger.error("nats_tls_connection_failed", server=server, error=str(error))
        logger.warning("Failed to connect to %s", server, error=str(error), attempt=attempt + 1)

    def _build_ssl_context(self) -> ssl.SSLContext:
        """Build an SSL context for mTLS.

        Reads certs from secrets/certs.yaml via CertificateAuthority when
        tls_ca_file/tls_cert_file/tls_key_file are not explicitly provided.
        """
        import tempfile

        ca_cert_str: str
        cert_str: str
        key_str: str

        if self.tls_ca_file and self.tls_cert_file and self.tls_key_file:
            # Use explicitly-provided paths
            ca_cert_str = Path(self.tls_ca_file).read_text(encoding="utf-8")
            cert_str = Path(self.tls_cert_file).read_text(encoding="utf-8")
            key_str = Path(self.tls_key_file).read_text(encoding="utf-8")
        else:
            # Load from secrets/certs.yaml via CertificateAuthority
            ca = CertificateAuthority()
            agent_id = self.client_name
            agent_result = ca.issue_agent_cert(agent_id)
            ca_cert_str = ca.ca_cert_pem
            cert_str = agent_result["cert"]
            key_str = agent_result["key"]

        # Write PEM data to temp files
        ca_cert_fd, ca_cert_path = tempfile.mkstemp(
            suffix=".pem", prefix="heretek_mesh_ca_"
        )
        with os.fdopen(ca_cert_fd, "w") as f:
            f.write(ca_cert_str)
        self._temp_cert_files.append(ca_cert_path)

        cert_fd, cert_path = tempfile.mkstemp(
            suffix=".pem", prefix="heretek_mesh_cert_"
        )
        with os.fdopen(cert_fd, "w") as f:
            f.write(cert_str)
        self._temp_cert_files.append(cert_path)

        key_fd, key_path = tempfile.mkstemp(
            suffix=".pem", prefix="heretek_mesh_key_"
        )
        with os.fdopen(key_fd, "w") as f:
            f.write(key_str)
        self._temp_cert_files.append(key_path)

        import os

        skip_verify = os.getenv("HERETEK_TLS_SKIP_HOSTNAME_VERIFY", "").lower() in (
            "1",
            "true",
            "yes",
        )
        # uvloop nats-py: verify_flags (PARTIAL_CHAIN) doesn't propagate, so
        # self-signed CAs fail. Dev: unverified_context. Prod: TLS_CLIENT.
        env = os.getenv("ENVIRONMENT", "development")
        if env == "development":
            ssl_ctx: ssl.SSLContext = ssl._create_unverified_context()
        else:
            ssl_ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
            ssl_ctx.verify_mode = ssl.CERT_REQUIRED
            ssl_ctx.load_verify_locations(cafile=ca_cert_path)
        ssl_ctx.load_cert_chain(certfile=cert_path, keyfile=key_path)
        ssl_ctx.minimum_version = ssl.TLSVersion.TLSv1_2
        ssl_ctx.check_hostname = not skip_verify

        logger.debug(
            "ssl_context_built_for_mtls",
            ca_cert_path=ca_cert_path,
            cert_path=cert_path,
            key_path=key_path,
            verify_mode=str(ssl_ctx.verify_mode),
        )
        # Log warning so operator can see the verify_mode at startup
        if ssl_ctx.verify_mode == ssl.CERT_NONE:
            logger.warning(
                "nats_tls_dev_mode_unverified_cert",
                message=(
                    "mTLS enabled with self-signed dev CA (verify_mode=CERT_NONE). "
                    "Production must use a real CA and cannot use _create_unverified_context."
                ),
            )
        return ssl_ctx

    async def _enable_fallback(self) -> bool:
        """Enable in-memory fallback mesh."""
        if self.fallback:
            self._fallback_mesh = _InMemoryFallback()
            self._use_fallback = True
            self._state = ConnectionState.CONNECTED
            logger.info("Using in-memory fallback mesh")
            return True
        return False

    async def disconnect(self) -> None:
        """Disconnect from NATS and cleanup."""
        async with self._lock:
            self._state = ConnectionState.CLOSING

            # Unsubscribe all
            for sub in self._subscriptions.values():
                if sub.active:
                    sub.active = False

            # Close NATS connection
            if self._nc is not None:
                try:
                    await self._nc.close()
                except Exception as e:
                    logger.error("Error closing NATS connection", error=str(e))
                finally:
                    self._nc = None

            # Clean up temp cert files
            for tmp_path in self._temp_cert_files:
                with contextlib.suppress(OSError):
                    Path(tmp_path).unlink()
            self._temp_cert_files.clear()

            self._state = ConnectionState.DISCONNECTED
            self._subscriptions.clear()

            logger.info("Disconnected from NATS")

    async def create_stream(
        self,
        name: str,
        subjects: list[str],
        storage: str = "file",
        retention: str = "limits",
        max_msgs: int = 100000,
        max_age: int = 86400,  # 24 hours in seconds
    ) -> bool:
        """
        Create a JetStream for message persistence.

        Args:
            name: Stream name
            subjects: List of subjects to capture
            storage: Storage type ("file" or "memory")
            retention: Retention policy ("limits", "interest", or "workqueue")
            max_msgs: Maximum messages to retain
            max_age: Maximum age of messages in seconds

        Returns:
            True if stream created successfully
        """
        if not self.jetstream_enabled:
            logger.warning("JetStream not available")
            return False

        try:
            import nats.js.api as js_api

            storage_type = (
                js_api.StorageType.FILE if storage == "file" else js_api.StorageType.MEMORY
            )
            retention_policy = getattr(
                js_api.RetentionPolicy, retention.upper(), js_api.RetentionPolicy.LIMITS
            )

            config = js_api.StreamConfig(
                name=name,
                subjects=subjects,
                storage=storage_type,
                retention=retention_policy,
                max_msgs=max_msgs,
                max_age=max_age * 1_000_000_000,  # Convert to nanoseconds
            )

            await self._js.add_stream(config=config)

            self._streams[name] = {
                "name": name,
                "subjects": subjects,
                "storage": storage,
                "retention": retention,
                "max_msgs": max_msgs,
                "max_age": max_age,
                "created": datetime.now(UTC).isoformat(),
            }

            logger.info("JetStream '{name}' created", subjects=subjects)
            return True

        except Exception:
            logger.error("Failed to create stream '{name}': {e}")
            return False

    async def delete_stream(self, name: str) -> bool:
        """
        Delete a JetStream.

        Args:
            name: Stream name

        Returns:
            True if deleted successfully
        """
        if not self.jetstream_enabled:
            return False

        try:
            await self._js.delete_stream(name)
            self._streams.pop(name, None)
            logger.info("JetStream '{name}' deleted")
            return True
        except Exception:
            logger.error("Failed to delete stream '{name}': {e}")
            return False

    async def publish_to_stream(
        self,
        stream_name: str,
        subject: str,
        data: dict[str, Any],
    ) -> bool:
        """
        Publish message to a JetStream.

        Args:
            stream_name: Name of the stream
            subject: Message subject
            data: Message data

        Returns:
            True if published successfully
        """
        if not self.jetstream_enabled:
            return False

        if stream_name not in self._streams:
            logger.warning("Stream '{stream_name}' not found")
            return False

        try:
            ack = await self._js.publish(subject, json.dumps(data).encode("utf-8"))
            logger.debug("Published to stream '{stream_name}'", seq=ack.seq)
            return True
        except Exception:
            logger.error("Failed to publish to stream: {e}")
            return False

    async def subscribe_durable(
        self,
        stream_name: str,
        durable_name: str,
        callback: Callable[[str, dict[str, Any]], None],
        deliver_policy: str = "all",
        ack_policy: bool = True,
    ) -> str | None:
        """
        Subscribe with durable consumer for at-least-once delivery.

        Args:
            stream_name: Name of the stream to consume from
            durable_name: Durable consumer name (persists across reconnects)
            callback: Async callback function (subject, data)
            deliver_policy: Delivery policy ("all", "last", "new", or "by_start_sequence")
            ack_policy: Enable acknowledgment (at-least-once delivery)

        Returns:
            Consumer ID or None if failed
        """
        if not self.jetstream_enabled:
            return None

        if stream_name not in self._streams:
            logger.warning("Stream '{stream_name}' not found")
            return None

        try:
            import nats.js.api as js_api

            deliver = getattr(
                js_api.DeliverPolicy, deliver_policy.upper(), js_api.DeliverPolicy.ALL
            )
            ack = js_api.AckPolicy.EXPLICIT if ack_policy else js_api.AckPolicy.NONE

            # Create or bind to durable consumer
            consumer_info = await self._js.pull_subscribe(
                stream=stream_name,
                durable=durable_name,
                deliver_policy=deliver,
                ack_policy=ack,
            )

            consumer_id = f"consumer_{stream_name}_{durable_name}"
            self._consumers[consumer_id] = consumer_info

            # Start message processing loop
            asyncio.create_task(  # noqa: RUF006
                self._process_durable_messages(consumer_info, stream_name, durable_name, callback)
            )

            logger.info("Durable consumer '{durable_name}' created on stream '{stream_name}'")
            return consumer_id

        except Exception:
            logger.error("Failed to create durable consumer: {e}")
            return None

    async def _process_durable_messages(
        self,
        consumer: Any,
        stream_name: str,  # noqa: ARG002
        durable_name: str,  # noqa: ARG002
        callback: Callable[[str, dict[str, Any]], None],
    ) -> None:
        """
        Process messages from a durable consumer.

        Args:
            consumer: JetStream consumer
            stream_name: Stream name
            durable_name: Durable consumer name
            callback: Message callback
        """
        while True:
            try:
                msgs = await consumer.fetch(batch=10, timeout=5.0)
                for msg in msgs:
                    try:
                        data = json.loads(msg.data.decode("utf-8"))
                        await callback(msg.subject, data)
                        await msg.ack()
                    except Exception:
                        logger.error("Error processing message: {e}")
                        await msg.nak()
            except TimeoutError:
                continue
            except Exception:
                logger.error("Durable consumer error: {e}")
                await asyncio.sleep(1.0)

    async def replay_stream(
        self,
        stream_name: str,
        start_sequence: int | None = None,
        start_time: datetime | None = None,
        callback: Callable[[str, dict[str, Any]], None] | None = None,
    ) -> list[dict[str, Any]]:
        """
        Replay messages from a JetStream.

        Args:
            stream_name: Name of the stream to replay
            start_sequence: Start from specific sequence number
            start_time: Start from specific timestamp
            callback: Optional callback for each message

        Returns:
            List of replayed messages
        """
        if not self.jetstream_enabled:
            return []

        if stream_name not in self._streams:
            logger.warning("Stream '{stream_name}' not found")
            return []

        messages = []

        try:
            import nats.js.api as js_api

            # Determine deliver policy
            if start_sequence is not None:
                deliver_policy = js_api.DeliverPolicy.BY_START_SEQUENCE
            elif start_time is not None:
                deliver_policy = js_api.DeliverPolicy.BY_START_TIME
            else:
                deliver_policy = js_api.DeliverPolicy.ALL

            consumer_info = await self._js.pull_subscribe(
                stream=stream_name,
                durable=f"replay_{datetime.now(UTC).strftime('%Y%m%d%H%M%S')}",
                deliver_policy=deliver_policy,
                opt_start_seq=start_sequence,
                opt_start_time=start_time,
            )

            # Fetch all messages
            while True:
                try:
                    msgs = await consumer_info.fetch(batch=100, timeout=2.0)
                    for msg in msgs:
                        data = json.loads(msg.data.decode("utf-8"))
                        messages.append(
                            {
                                "subject": msg.subject,
                                "data": data,
                                "sequence": msg.metadata.sequence.stream if msg.metadata else None,
                                "timestamp": msg.metadata.timestamp if msg.metadata else None,
                            }
                        )
                        if callback:
                            await callback(msg.subject, data)
                        await msg.ack()
                except TimeoutError:
                    break

            logger.info("Replayed {len(messages)} messages from stream '{stream_name}'")
            return messages

        except Exception:
            logger.error("Failed to replay stream: {e}")
            return []

    async def reconstruct_state(
        self,
        entity_id: str,
        stream_name: str,
        event_applier: Callable[[dict[str, Any], dict[str, Any]], dict[str, Any]],
        initial_state: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """
        Reconstruct entity state from event stream.

        Event sourcing pattern: replay all events for an entity and apply
        them to reconstruct current state.

        Args:
            entity_id: Entity identifier to reconstruct
            stream_name: Name of the event stream
            event_applier: Function to apply event to state (state, event) -> new_state
            initial_state: Initial state to start from

        Returns:
            Reconstructed state dictionary
        """
        state = initial_state or {}

        def filter_callback(subject: str, data: dict[str, Any]):
            nonlocal state
            if data.get("entity_id") == entity_id:
                state = event_applier(state, data)

        await self.replay_stream(
            stream_name=stream_name,
            callback=filter_callback,
        )

        logger.info("Reconstructed state for entity '{entity_id}' from {len(state)} fields")
        return state

    async def publish(self, subject: str, data: dict[str, Any], reply: str | None = None) -> bool:
        """
        Publish message to subject.

        Args:
            subject: NATS subject (supports wildcards)
            data: Message data (will be JSON encoded)
            reply: Optional reply subject

        Returns:
            True if published successfully
        """
        if self._use_fallback and self._fallback_mesh is not None:
            return await self._fallback_mesh.publish(subject, data)

        if not self.is_connected:
            logger.warning("Not connected, cannot publish")
            return False

        try:
            message = json.dumps(data).encode("utf-8")
            await self._nc.publish(subject, message, reply=reply)
            await self._nc.flush()
            logger.debug("Published message", subject=subject)
            return True
        except Exception as e:
            logger.error("Failed to publish", subject=subject, error=str(e))
            return False

    async def publish_to_nats(self, topic: str, data: dict[str, Any]) -> bool:
        """
        Publish structured event to a NATS topic with logging.

        Args:
            topic: NATS subject to publish to
            data: Message data

        Returns:
            True if published successfully
        """
        try:
            success = await self.publish(topic, data)
            if success:
                logger.debug(
                    "emit_consciousness_event",
                    topic=topic,
                    event_type=data.get("type"),
                    agent_id=data.get("agent_id"),
                )
                logger.info("publish_to_nats_success", topic=topic)
            else:
                logger.error("publish_to_nats_failure", topic=topic)
            return success
        except Exception as e:
            logger.error("publish_to_nats_error", topic=topic, error=str(e))
            return False

    async def send_to_json(self, subject: str, data_dict: dict[str, Any], **_kwargs: Any) -> bool:
        """
        Send a message to a subject with JSON-serializable data.

        Thin delegation wrapper around publish() for API compatibility with
        StubEventMesh / EventMesh interface. All agents call send_to_json
        instead of publish directly.

        Args:
            subject: NATS subject to send to
            data_dict: JSON-serializable message data
            **kwargs: Additional arguments (forwarded for interface compatibility)

        Returns:
            True if sent successfully
        """
        logger.debug("send_to_json", subject=subject)
        return await self.publish(subject, data_dict)

    async def broadcast_json(self, data_dict: dict[str, Any]) -> bool:
        """
        Broadcast a message to all connected actors.

        Thin delegation wrapper around publish() to the "broadcast" subject.
        All agents call broadcast_json instead of publish("broadcast", ...)
        directly.

        Args:
            data_dict: JSON-serializable message data

        Returns:
            True if broadcast successfully
        """
        return await self.publish("broadcast", data_dict)

    async def subscribe(
        self,
        subject: str,
        callback: Callable[["NATSEventMesh", str, dict[str, Any]], None],
    ) -> str | None:
        """
        Subscribe to subject.

        Args:
            subject: NATS subject (supports wildcards)
            callback: Async callback function (mesh, subject, data)

        Returns:
            Subscription ID or None if failed
        """
        if self._use_fallback and self._fallback_mesh is not None:
            return await self._fallback_mesh.subscribe(subject, callback)

        if not self.is_connected:
            logger.warning("Not connected, cannot subscribe")
            return None

        try:
            # Create subscription
            sid = f"sub_{len(self._subscriptions)}"

            async def wrapper(msg):
                try:
                    data = json.loads(msg.data.decode("utf-8")) if msg.data else {}
                    await callback(self, msg.subject, data)
                except Exception as e:
                    logger.error("Subscription callback error", subject=subject, error=str(e))

            sub = await self._nc.subscribe(subject, cb=wrapper)
            sub.sid = sid

            self._subscriptions[sid] = Subscription(
                subject=subject,
                callback=callback,
                sid=sid,
                active=True,
            )

            logger.info("Subscribed to subject", subject=subject, sid=sid)
            return sid

        except Exception as e:
            logger.error("Failed to subscribe", subject=subject, error=str(e))
            return None

    async def unsubscribe(self, sid: str) -> bool:
        """
        Unsubscribe by subscription ID.

        Args:
            sid: Subscription ID

        Returns:
            True if unsubscribed successfully
        """
        if self._use_fallback and self._fallback_mesh is not None:
            return await self._fallback_mesh.unsubscribe(sid)

        if sid not in self._subscriptions:
            logger.warning("Subscription not found", sid=sid)
            return False

        try:
            sub = self._subscriptions[sid]
            sub.active = False
            del self._subscriptions[sid]
            logger.info("Unsubscribed", sid=sid)
            return True
        except Exception as e:
            logger.error("Failed to unsubscribe", sid=sid, error=str(e))
            return False

    async def request(
        self,
        subject: str,
        data: dict[str, Any],
        timeout: float = 5.0,  # noqa: ASYNC109
    ) -> dict[str, Any] | None:
        """
        Request-reply pattern.

        Args:
            subject: Request subject
            data: Request data
            timeout: Request timeout in seconds

        Returns:
            Response data or None if timeout/error
        """
        if self._use_fallback and self._fallback_mesh is not None:
            return await self._fallback_mesh.request(subject, data, timeout)

        if not self.is_connected:
            logger.warning("Not connected, cannot request")
            return None

        try:
            message = json.dumps(data).encode("utf-8")
            msg = await self._nc.request(subject, message, timeout=timeout)

            if msg and msg.data:
                response = json.loads(msg.data.decode("utf-8"))
                logger.debug("Request response", subject=subject)
                return response

            return None
        except TimeoutError:
            logger.warning("Request timeout", subject=subject, timeout=timeout)
            return None
        except Exception as e:
            logger.error("Request failed", subject=subject, error=str(e))
            return None

    def get_subscription_ids(self) -> set[str]:
        """Get set of all active subscription IDs."""
        return {sid for sid, sub in self._subscriptions.items() if sub.active}

    async def close_all(self) -> None:
        """Close all connections and cleanup."""
        await self.disconnect()


class _InMemoryFallback:
    """In-memory fallback for when NATS is unavailable."""

    def __init__(self) -> None:
        self._subscriptions: dict[str, list[Callable]] = {}
        self._sub_counter = 0
        self._pending: dict[str, asyncio.Future] = {}

    @staticmethod
    def _matches_subject(pattern: str, subject: str) -> bool:
        """Check if a published subject matches a subscription pattern.

        Supports NATS wildcard tokens:
        - ``>`` matches one or more tokens at the end (e.g. ``test.>`` matches
          ``test.a.b.c``)
        - ``*`` matches exactly one token (e.g. ``events.*`` matches
          ``events.click`` but NOT ``events.click.button``)
        """
        if pattern == subject:
            return True

        pat_tokens = pattern.split(".")
        sub_tokens = subject.split(".")

        for i, pat_tok in enumerate(pat_tokens):
            if pat_tok == ">":
                # ``>`` must be the last token and consumes everything remaining
                return i == len(pat_tokens) - 1 and len(sub_tokens) > i
            if i >= len(sub_tokens):
                return False
            if pat_tok == "*":
                # Matches exactly one token — just continue
                continue
            if pat_tok != sub_tokens[i]:
                return False

        # All pattern tokens consumed — lengths must match exactly
        return len(pat_tokens) == len(sub_tokens)

    @property
    def subscription_count(self) -> int:
        """Get number of active subscriptions."""
        return sum(len(subs) for subs in self._subscriptions.values())

    async def publish(self, subject: str, data: dict[str, Any]) -> bool:
        """Publish to in-memory subscribers."""
        for pattern, subs in self._subscriptions.items():
            if not self._matches_subject(pattern, subject):
                continue
            for sub in subs:
                with contextlib.suppress(Exception):
                    await sub(None, subject, data)
        return True

    async def send_to_json(self, subject: str, data_dict: dict[str, Any], **_kwargs: Any) -> bool:
        """Send a message via in-memory fallback (delegates to publish)."""
        return await self.publish(subject, data_dict)

    async def broadcast_json(self, data_dict: dict[str, Any]) -> bool:
        """Broadcast via in-memory fallback (delegates to publish on "broadcast")."""
        return await self.publish("broadcast", data_dict)

    async def subscribe(
        self,
        subject: str,
        callback: Callable[[str, dict[str, Any]], None],
    ) -> str:
        """Subscribe in-memory."""
        sid = f"mem_{self._sub_counter}"
        self._sub_counter += 1

        if subject not in self._subscriptions:
            self._subscriptions[subject] = []
        self._subscriptions[subject].append(callback)

        return sid

    async def unsubscribe(self, _sid: str) -> bool:
        """Unsubscribe in-memory."""
        return True

    async def request(
        self,
        subject: str,
        data: dict[str, Any],
        timeout: float,  # noqa: ARG002,ASYNC109
    ) -> dict[str, Any] | None:
        """Request in-memory (no response by default)."""
        await self.publish(subject, data)
        return None


class NATSEventMeshMixin:
    """
    Mixin to add NATS EventMesh capabilities to existing EventMesh.

    Example:
        ```python
        class NATSEnabledEventMesh(NATSEventMeshMixin, EventMesh):
            pass

        mesh = NATSEnabledEventMesh()
        await mesh.setup_nats(servers=["nats://localhost:4222"])
        ```
    """

    def __init__(self, *_args, **kwargs) -> None:
        """Initialize mixin."""
        self._nats_mesh: NATSEventMesh | None = None
        self._nats_enabled = False
        self._nats_config = kwargs.copy()

    async def setup_nats(
        self,
        servers: list[str] | None = None,
        fallback: bool = True,
    ) -> bool:
        """
        Setup NATS EventMesh integration.

        Args:
            servers: List of NATS server URLs
            fallback: Enable fallback to in-memory

        Returns:
            True if NATS connection established
        """
        config = self._nats_config.copy()
        if servers:
            config["servers"] = servers
        config["fallback"] = fallback

        self._nats_mesh = NATSEventMesh(**config)
        self._nats_enabled = await self._nats_mesh.connect()

        return self._nats_enabled

    @property
    def nats_mesh(self) -> NATSEventMesh | None:
        """Get NATS mesh instance."""
        return self._nats_mesh

    @property
    def nats_enabled(self) -> bool:
        """Check if NATS is enabled."""
        return self._nats_enabled


# =============================================================================
# JetStreamManager Integration
# =============================================================================


class NATSEventMeshWithJetStream(NATSEventMesh):
    """
    Enhanced NATSEventMesh with JetStreamManager integration.

    Combines the messaging capabilities of NATSEventMesh with the
    stream management features of JetStreamManager for comprehensive
    event mesh functionality.

    Example:
        ```python
        mesh = NATSEventMeshWithJetStream(
            servers=["nats://localhost:4222"],
            fallback=True
        )
        await mesh.connect()

        # Initialize default streams
        await mesh.initialize_jetstream()

        # Publish to stream
        await mesh.publish_to_stream(
            stream_name="AGENT_EVENTS",
            subject="agent.test.state",
            data={"state": "running"}
        )
        ```
    """

    def __init__(
        self,
        servers: list[str] | None = None,
        name: str | None = None,
        fallback: bool = True,
        max_reconnect_attempts: int = 5,
        reconnect_time_wait: float = 1.0,
        ping_interval: int = 30,
        max_outstanding_pings: int = 1000,
        zero_trust_enabled: bool = True,
    ) -> None:
        """
        Initialize enhanced NATSEventMesh with JetStream.

        Args:
            servers: List of NATS server URLs
            name: Client name
            fallback: Enable fallback to in-memory mesh
            max_reconnect_attempts: Max reconnection attempts
            reconnect_time_wait: Time to wait between reconnect attempts
            ping_interval: Ping interval in seconds
            max_outstanding_pings: Max outstanding pings
            zero_trust_enabled: Enable zero-trust security
        """
        super().__init__(
            servers=servers,
            name=name,
            fallback=fallback,
            max_reconnect_attempts=max_reconnect_attempts,
            reconnect_time_wait=reconnect_time_wait,
            ping_interval=ping_interval,
            max_outstanding_pings=max_outstanding_pings,
        )

        # JetStream manager reference
        self._js_manager = None
        self._zero_trust_enabled = zero_trust_enabled

        logger.info("NATSEventMeshWithJetStream initialized")

    @property
    def jetstream_manager(self) -> Any | None:
        """Get JetStream manager instance."""
        return self._js_manager

    @property
    def jetstream_ready(self) -> bool:
        """Check if JetStream is ready."""
        return self._js_manager is not None and self._js_manager.is_connected

    async def initialize_jetstream(
        self,
        create_default_streams: bool = True,
    ) -> bool:
        """
        Initialize JetStream manager and create streams.

        Args:
            create_default_streams: Create default stream configurations

        Returns:
            True if initialized successfully
        """
        if not self.is_connected:
            logger.warning("Not connected, cannot initialize JetStream")
            return False

        try:
            # Import JetStreamManager
            from heretek_swarm.gateway.jetstream_manager import (
                JetStreamManager,
            )

            # Create manager
            self._js_manager = JetStreamManager(
                servers=self.servers,
                name=self.client_name,
                zero_trust_enabled=self._zero_trust_enabled,
                fallback_enabled=self.fallback,
            )

            # Connect
            connected = await self._js_manager.connect()
            if not connected:
                logger.warning("JetStreamManager connection failed")
                return False

            # Create default streams if requested
            if create_default_streams:
                results = await self._js_manager.initialize_default_streams()
                logger.info("Default streams initialized", results=results)

            logger.info("JetStream initialized")
            return True

        except Exception:
            logger.error("Failed to initialize JetStream: {e}")
            return False

    async def ensure_agent_streams(
        self,
        agent_ids: list[str] | None = None,
    ) -> dict[str, int]:
        """
        Create one JetStream stream per agent ID for durable agent messaging.

        Each stream covers subject ``agent.{agent_id}.>`` so all messages
        directed at a specific agent are persisted.  Idempotent — already
        existing streams are logged as warnings and counted as skipped.

        Args:
            agent_ids: List of agent IDs (e.g. ``["alpha", "beta", ...]``).
                       Defaults to empty list.

        Returns:
            Dict with ``created`` and ``skipped`` counts.
        """
        agent_ids = agent_ids or []
        created = 0
        skipped = 0

        if not self.jetstream_enabled:
            logger.warning("ensure_agent_streams_skipped_jetstream_not_enabled")
            return {"created": 0, "skipped": 0}

        for agent_id in agent_ids:
            stream_name = f"agent_{agent_id}"
            try:
                import nats.js.api as js_api

                config = js_api.StreamConfig(
                    name=stream_name,
                    subjects=[f"agent.{agent_id}.>"],
                    storage=js_api.StorageType.FILE,
                    retention=js_api.RetentionPolicy.LIMITS,
                    max_msgs=10000,
                    max_age=24 * 3600 * 1_000_000_000,  # 24h in nanoseconds
                )
                await self._js.add_stream(config=config)
                self._streams[stream_name] = {
                    "name": stream_name,
                    "subjects": [f"agent.{agent_id}.>"],
                    "storage": "file",
                    "retention": "limits",
                    "max_msgs": 10000,
                    "max_age": 86400,
                    "created": datetime.now(UTC).isoformat(),
                }
                logger.info("agent_stream_created", stream_name=stream_name, agent_id=agent_id)
                created += 1
            except Exception:
                logger.warning(
                    "agent_stream_already_exists", stream_name=stream_name, agent_id=agent_id
                )
                skipped += 1

        logger.info("ensure_agent_streams_complete", created=created, skipped=skipped)
        return {"created": created, "skipped": skipped}

    async def publish_event(
        self,
        stream_name: str,
        event_type: str,
        entity_id: str,
        payload: dict[str, Any],
        correlation_id: str | None = None,
    ) -> bool:
        """
        Publish a domain event to a stream.

        Args:
            stream_name: Target stream name
            event_type: Type of event (e.g., "agent.state.changed")
            entity_id: Entity identifier
            payload: Event payload
            correlation_id: Optional correlation ID for tracing

        Returns:
            True if published successfully
        """
        if not self.jetstream_ready:
            # Fallback to regular publish
            subject = f"{stream_name}.{event_type}.{entity_id}"
            return await self.publish(subject, payload)

        # Build event envelope
        event = {
            "event_id": f"{event_type}-{entity_id}-{datetime.now(UTC).timestamp()}",
            "event_type": event_type,
            "entity_id": entity_id,
            "timestamp": datetime.now(UTC).isoformat(),
            "payload": payload,
        }

        # Determine subject based on stream type
        if stream_name == "AGENT_EVENTS":
            subject = f"agent.{entity_id}.events"
        elif stream_name == "WORKFLOW_EVENTS":
            subject = f"workflow.{entity_id}.events"
        elif stream_name == "CONSCIOUSNESS_METRICS":
            subject = f"consciousness.{entity_id}.metrics"
        elif stream_name == "SYSTEM_HEALTH":
            subject = f"health.{entity_id}.metrics"
        else:
            subject = f"{stream_name}.{event_type}"

        return await self._js_manager.publish(
            stream_name=stream_name,
            subject=subject,
            data=event,
            correlation_id=correlation_id,
        )

    async def subscribe_to_events(
        self,
        stream_name: str,
        event_type: str | None = None,
        entity_id: str | None = None,
        callback: Callable[[str, dict[str, Any]], None] | None = None,
        durable_name: str | None = None,
    ) -> str | None:
        """
        Subscribe to events from a stream.

        Args:
            stream_name: Source stream name
            event_type: Optional event type filter
            entity_id: Optional entity ID filter
            callback: Message callback function
            durable_name: Optional durable consumer name

        Returns:
            Consumer/subscription ID or None if failed
        """
        if not self.jetstream_ready:
            # Fallback to regular subscribe
            if event_type and entity_id:
                subject = f"{stream_name}.{event_type}.{entity_id}"
            elif event_type:
                subject = f"{stream_name}.{event_type}.>"
            else:
                subject = f"{stream_name}.>"
            return await self.subscribe(subject, callback)

        # Build subject filter
        if event_type and entity_id:
            subject_filter = f"agent.{entity_id}.events"
        elif event_type:
            subject_filter = "agent.*.events"
        else:
            subject_filter = ">"

        # Create consumer config
        from heretek_swarm.gateway.jetstream_manager import (
            AckPolicy,
            ConsumerConfig,
            DeliverPolicy,
        )

        consumer_config = ConsumerConfig(
            durable_name=durable_name
            or f"consumer_{stream_name}_{datetime.now(UTC).strftime('%Y%m%d%H%M%S')}",
            stream_name=stream_name,
            deliver_policy=DeliverPolicy.NEW,
            ack_policy=AckPolicy.EXPLICIT,
            filter_subject=subject_filter,
        )

        return await self._js_manager.create_consumer(consumer_config, callback)

    async def replay_events(
        self,
        stream_name: str,
        start_sequence: int | None = None,
        end_sequence: int | None = None,
        event_type: str | None = None,
        callback: Callable[[str, dict[str, Any]], None] | None = None,
    ) -> list[dict[str, Any]]:
        """
        Replay events from a stream.

        Args:
            stream_name: Source stream name
            start_sequence: Start sequence number
            end_sequence: End sequence number
            event_type: Optional event type filter
            callback: Optional callback for each message

        Returns:
            List of replayed events
        """
        if not self.jetstream_ready:
            logger.warning("JetStream not ready, cannot replay events")
            return []

        # Build subject filter
        subject_filter = None
        if event_type:
            subject_filter = f"*.{event_type}.*"

        return await self._js_manager.replay_messages(
            stream_name=stream_name,
            start_sequence=start_sequence,
            end_sequence=end_sequence,
            subject_filter=subject_filter,
            callback=callback,
        )

    async def get_stream_stats(self, stream_name: str) -> dict[str, Any] | None:
        """
        Get statistics for a stream.

        Args:
            stream_name: Stream name

        Returns:
            Stream statistics or None if not found
        """
        if not self.jetstream_ready:
            return None

        info = await self._js_manager.get_stream_info(stream_name)
        if not info:
            return None

        return info.to_dict()

    async def shutdown(self) -> None:
        """Shutdown JetStream and NATS connections."""
        if self._js_manager:
            await self._js_manager.disconnect()
            self._js_manager = None

        await self.disconnect()
        logger.info("NATSEventMeshWithJetStream shutdown complete")


# ============================================================================
# NATS-to-Actor Bridge
# ============================================================================


@dataclass
class ActorBridgeConfig:
    """Configuration for NATS-to-Actor bridge."""

    # NATS subject patterns for actor messages
    actor_inbox_pattern: str = "actors.{agent_id}.inbox"
    actor_outbox_pattern: str = "actors.{agent_id}.outbox"
    actor_events_pattern: str = "actors.{agent_id}.events"
    # Reply timeout for request-reply
    reply_timeout: float = 30.0
    # Queue group for load balancing
    queue_group: str = "heretek-swarm-actors"


class NATStoActorBridge:
    """
    Bridge between NATS event mesh and actor message protocol.

    This bridge allows actors to communicate via NATS while maintaining
    the actor message protocol. It:
    - Subscribes to NATS topics for incoming actor messages
    - Converts NATS messages to ActorMessage format
    - Publishes actor responses back to NATS
    - Supports both publish-subscribe and request-reply patterns
    """

    def __init__(
        self,
        mesh: NATSEventMesh,
        config: ActorBridgeConfig | None = None,
    ) -> None:
        """
        Initialize the NATS-to-Actor bridge.

        Args:
            mesh: NATSEventMesh instance for NATS communication
            config: Optional bridge configuration
        """
        self.mesh = mesh
        self.config = config or ActorBridgeConfig()

        # Active actor subscriptions: agent_id -> subscription_id
        self._actor_subscriptions: dict[str, str] = {}

        # Pending requests: correlation_id -> asyncio.Future
        self._pending_requests: dict[str, asyncio.Future] = {}

        # Callback for delivering messages to actors
        self._actor_callbacks: dict[str, Callable[[dict[str, Any]], None]] = {}

        # Lock for thread-safe operations
        self._lock = asyncio.Lock()

        logger.info(
            "NATStoActorBridge initialized",
            extra={
                "inbox_pattern": self.config.actor_inbox_pattern,
                "outbox_pattern": self.config.actor_outbox_pattern,
                "queue_group": self.config.queue_group,
            },
        )

    def _get_inbox_subject(self, agent_id: str) -> str:
        """Get the inbox subject for an agent."""
        return self.config.actor_inbox_pattern.format(agent_id=agent_id)

    def _get_outbox_subject(self, agent_id: str) -> str:
        """Get the outbox subject for an agent."""
        return self.config.actor_outbox_pattern.format(agent_id=agent_id)

    def _get_events_subject(self, agent_id: str) -> str:
        """Get the events subject for an agent."""
        return self.config.actor_events_pattern.format(agent_id=agent_id)

    async def register_actor(
        self,
        agent_id: str,
        callback: Callable[[dict[str, Any]], None],
    ) -> bool:
        """
        Register an actor for NATS message delivery.

        Args:
            agent_id: Unique actor identifier
            callback: Async callback to deliver messages to the actor

        Returns:
            True if registration successful
        """
        async with self._lock:
            if agent_id in self._actor_subscriptions:
                logger.warning("Actor already registered", agent_id=agent_id)
                return False

            # Store callback for message delivery
            self._actor_callbacks[agent_id] = callback

            # Subscribe to actor's inbox
            inbox_subject = self._get_inbox_subject(agent_id)

            async def message_handler(
                mesh: NATSEventMesh, subject: str, data: dict[str, Any]
            ) -> None:
                """Handle incoming NATS messages for the actor."""
                try:
                    # Extract correlation_id for request-reply
                    correlation_id = data.get("correlation_id")
                    reply_subject = data.get("reply_to")

                    # Deliver to actor via callback
                    await callback(data)

                    # If this is a request with reply subject, send response
                    if correlation_id and reply_subject:
                        # Actor will call send_response which publishes to outbox
                        pass

                except Exception as e:
                    logger.error(
                        "Error delivering message to actor",
                        agent_id=agent_id,
                        error=str(e),
                    )

            sub_id = await self.mesh.subscribe(
                inbox_subject,
                message_handler,
            )

            if sub_id:
                self._actor_subscriptions[agent_id] = sub_id
                logger.info("Actor registered for NATS", agent_id=agent_id, subject=inbox_subject)
                return True

            return False

    async def unregister_actor(self, agent_id: str) -> bool:
        """
        Unregister an actor from NATS message delivery.

        Args:
            agent_id: Unique actor identifier

        Returns:
            True if unregistration successful
        """
        async with self._lock:
            if agent_id not in self._actor_subscriptions:
                logger.warning("Actor not registered", agent_id=agent_id)
                return False

            sub_id = self._actor_subscriptions.pop(agent_id)
            success = await self.mesh.unsubscribe(sub_id)

            self._actor_callbacks.pop(agent_id, None)

            logger.info("Actor unregistered from NATS", agent_id=agent_id)
            return success

    async def send_to_actor(
        self,
        agent_id: str,
        message: dict[str, Any],
        expect_reply: bool = False,
    ) -> bool:
        """
        Send a message to an actor via NATS.

        Args:
            agent_id: Target actor identifier
            message: Message data (will be wrapped in ActorMessage format)
            expect_reply: If True, wait for response via correlation_id

        Returns:
            True if message sent successfully
        """
        inbox_subject = self._get_inbox_subject(agent_id)

        # Add reply subject if expecting response
        if expect_reply:
            import uuid

            correlation_id = str(uuid.uuid4())
            message["correlation_id"] = correlation_id
            # Create a future to wait for response
            future: asyncio.Future = asyncio.get_event_loop().create_future()
            self._pending_requests[correlation_id] = future

        try:
            success = await self.mesh.publish(inbox_subject, message)

            if expect_reply and success:
                # Wait for response with timeout
                try:
                    return await asyncio.wait_for(
                        future,
                        timeout=self.config.reply_timeout,
                    )
                except TimeoutError:
                    logger.warning(
                        "Request to actor timed out",
                        agent_id=agent_id,
                        correlation_id=correlation_id,
                    )
                    self._pending_requests.pop(correlation_id, None)
                    return False
                finally:
                    self._pending_requests.pop(correlation_id, None)

            return success

        except Exception as e:
            logger.error(
                "Failed to send message to actor",
                agent_id=agent_id,
                error=str(e),
            )
            if expect_reply:
                self._pending_requests.pop(message.get("correlation_id"), None)
            return False

    async def send_response(
        self,
        agent_id: str,
        response: dict[str, Any],
        correlation_id: str,
    ) -> bool:
        """
        Send a response from an actor back via NATS.

        Args:
            agent_id: Source actor identifier
            response: Response message data
            correlation_id: Correlation ID from original request

        Returns:
            True if response sent successfully
        """
        outbox_subject = self._get_outbox_subject(agent_id)
        response["correlation_id"] = correlation_id
        response["sender_id"] = agent_id

        try:
            success = await self.mesh.publish(outbox_subject, response)

            # Also resolve pending request if any
            if correlation_id in self._pending_requests:
                self._pending_requests[correlation_id].set_result(response)

            return success

        except Exception as e:
            logger.error(
                "Failed to send actor response",
                agent_id=agent_id,
                error=str(e),
            )
            return False

    async def broadcast_event(
        self,
        agent_id: str,
        event: dict[str, Any],
    ) -> bool:
        """
        Broadcast an event from an actor to all subscribers.

        Args:
            agent_id: Source actor identifier
            event: Event data

        Returns:
            True if event broadcast successfully
        """
        events_subject = self._get_events_subject(agent_id)
        event["sender_id"] = agent_id
        event["timestamp"] = datetime.now(UTC).isoformat()

        try:
            return await self.mesh.publish(events_subject, event)
        except Exception as e:
            logger.error(
                "Failed to broadcast actor event",
                agent_id=agent_id,
                error=str(e),
            )
            return False

    def get_registered_actors(self) -> list[str]:
        """Get list of registered actor IDs."""
        return list(self._actor_subscriptions.keys())


# Global bridge instance
_bridge: NATStoActorBridge | None = None


def get_nats_bridge(mesh: NATSEventMesh | None = None) -> NATStoActorBridge:
    """
    Get or create global NATS-to-Actor bridge.

    Args:
        mesh: Optional NATSEventMesh instance (creates one if not provided)

    Returns:
        NATStoActorBridge instance
    """
    global _bridge
    if _bridge is None and mesh is not None:
        _bridge = NATStoActorBridge(mesh)
    elif _bridge is None:
        # Create mesh and bridge
        mesh_instance = NATSEventMesh(fallback=True)
        _bridge = NATStoActorBridge(mesh_instance)
    return _bridge


async def init_nats_bridge(config: ActorBridgeConfig | None = None) -> NATStoActorBridge:
    """
    Initialize the global NATS-to-Actor bridge with connection.

    Args:
        config: Optional bridge configuration

    Returns:
        Initialized NATStoActorBridge
    """
    mesh = NATSEventMesh(fallback=True)
    await mesh.connect()
    bridge = NATStoActorBridge(mesh, config)
    global _bridge
    _bridge = bridge
    return bridge


async def shutdown_nats_bridge() -> None:
    """Shutdown global NATS-to-Actor bridge."""
    global _bridge
    if _bridge is not None:
        for agent_id in list(_bridge._actor_subscriptions.keys()):  # noqa: SLF001
            await _bridge.unregister_actor(agent_id)
        await _bridge.mesh.disconnect()
        _bridge = None
