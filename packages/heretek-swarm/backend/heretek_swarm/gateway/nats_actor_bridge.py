"""
NATS-to-Actor bridge — glues the NATS event mesh to the actor model.

This module hosts the NATStoActorBridge class and the
ActorBridgeConfig dataclass. The bridge lets actors send and
receive messages via NATS while preserving the actor message
protocol. It supports both publish-subscribe and request-reply
patterns.

It was extracted from :mod:as part of Phase 2.5 of PLAN.md — the event mesh itself remains a
1,357-LOC file focused on connection / JetStream / pub-sub /
request-reply / mTLS / in-mem fallback / backoff. The bridge is
its own concern.

The module also hosts the three module-level helpers
(get_nats_bridge, init_nats_bridge, shutdown_nats_bridge)
that manage the global bridge singleton.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass

import structlog

from typing import TYPE_CHECKING, Any

from heretek_swarm.gateway.nats_types import NATSMessage, Subscription

if TYPE_CHECKING:
    from heretek_swarm.gateway.nats_event_mesh import NATSEventMesh

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from heretek_swarm.gateway.nats_event_mesh import NATSEventMesh

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
        for agent_id in list(_bridge._actor_subscriptions.keys()):
            await _bridge.unregister_actor(agent_id)
        await _bridge.mesh.disconnect()
        _bridge = None

__all__ = [
    "ActorBridgeConfig",
    "NATStoActorBridge",
    "get_nats_bridge",
    "init_nats_bridge",
    "shutdown_nats_bridge",
]
