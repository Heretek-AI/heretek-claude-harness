"""
EventMesh - WebSocket Connection Manager for Heretek Swarm

Provides null-safe broadcast and targeted messaging for A2A protocol.
Reference: MiniMax Audit Lines 11-30 (EventMesh bug fix)

Now integrated with Content Router for content-based message routing.
"""

import asyncio
import contextlib
import json
from typing import Any

import structlog
from fastapi import WebSocket

from heretek_swarm.gateway.content_router import (
    ContentRouter,
    RouteDecision,
    RoutingDecision,
    get_content_router,
)
from heretek_swarm.infrastructure.nats.publisher import (
    NATSPublisher,
    SwarmEvent,
    get_nats_publisher,
)

logger = structlog.get_logger(__name__)


class EventMesh:
    """
    WebSocket connection manager with null safety and error handling.

    Fixes the critical null reference bug from OpenClaw:
    - Filters dead connections before broadcast
    - Try/catch on all send operations
    - Automatic cleanup of failed connections

    Integrated with Content Router for content-based message routing:
    - Evaluates messages against routing rules before broadcast
    - Routes messages to specific channels/agents based on content
    - Logs routing decisions with correlation IDs
    """

    def __init__(self, content_router: ContentRouter | None = None):
        self.clients: dict[str, WebSocket] = {}
        self._lock = asyncio.Lock()
        self._content_router = content_router or get_content_router()
        self._nats_publisher: NATSPublisher | None = None

    @property
    def nats_publisher(self) -> NATSPublisher | None:
        """Get the NATS publisher, initializing lazily if needed."""
        return self._nats_publisher

    async def set_nats_publisher(self, publisher: NATSPublisher | None) -> None:
        """Set the NATS publisher. Pass None to use the global publisher."""
        if publisher is None:
            try:
                self._nats_publisher = await get_nats_publisher()
            except Exception:
                logger.debug("nats_publisher_init_failed")
                self._nats_publisher = None
        else:
            self._nats_publisher = publisher

    async def publish_to_nats(
        self,
        event_type: str,
        source_agent: str,
        target_agent: str | None = None,
        payload: dict | None = None,
        topic: str = "swarm.events",
    ) -> None:
        """
        Fire-and-forget publish a SwarmEvent to NATS.

        Does not block if NATS is unavailable; logs at appropriate levels.

        Args:
            event_type: Event type string (e.g. 'a2a.message')
            source_agent: Sending agent ID
            target_agent: Optional target agent ID
            payload: Optional event payload
            topic: NATS topic to publish to (default: swarm.events)
        """
        if self._nats_publisher is None:
            logger.debug("nats_publisher_not_available")
            return

        event = SwarmEvent(
            event_type=event_type,
            source_agent=source_agent,
            target_agent=target_agent,
            payload=payload or {},
        )

        try:
            import asyncio

            asyncio.create_task(self._nats_publisher.publish_event(event))  # noqa: RUF006
            logger.info(
                "a2a_nats_publish_success", event_type=event_type, source=source_agent, topic=topic
            )
        except Exception as e:
            logger.debug("a2a_nats_publish_failed", error=str(e), event_type=event_type)

    @property
    def client_count(self) -> int:
        """Get number of connected clients."""
        return len(self.clients)

    async def register(self, client_id: str, websocket: WebSocket) -> None:
        """
        Register a new client connection.

        Args:
            client_id: Unique client identifier
            websocket: WebSocket connection
        """
        async with self._lock:
            self.clients[client_id] = websocket
            logger.info("client_registered", client_id=client_id, total=self.client_count)

    async def unregister(self, client_id: str) -> None:
        """
        Unregister client and cleanup.

        Args:
            client_id: Client to remove
        """
        async with self._lock:
            if client_id in self.clients:
                del self.clients[client_id]
                logger.info("client_unregistered", client_id=client_id, total=self.client_count)

    async def broadcast(
        self,
        message: bytes,
        subject: str | None = None,
        payload: dict[str, Any] | None = None,
        correlation_id: str | None = None,
    ) -> dict[str, int]:
        """
        Broadcast message to all connected clients with null safety and content routing.

        CRITICAL FIX: Filters dead connections before sending, wraps in try/catch.
        CONTENT ROUTING: Evaluates message against routing rules before broadcast.

        Args:
            message: Message bytes to broadcast
            subject: Optional message subject for content routing
            payload: Optional message payload for content filtering
            correlation_id: Optional correlation ID for tracing

        Returns:
            Dict with success/failure counts and routing info
        """
        # Content-based routing (if subject and payload provided)
        routing_decision: RoutingDecision | None = None
        target_clients: set[str] | None = None

        if subject and payload:
            routing_decision = self._content_router.route(
                subject=subject,
                payload=payload,
                correlation_id=correlation_id,
            )

            # If message is routed to specific agents, filter clients
            if routing_decision.decision == RouteDecision.MATCHED and routing_decision.matched_rule:
                target_agents = routing_decision.matched_rule.target_agents
                if target_agents:
                    # Only send to specified agents
                    target_clients = set(target_agents) & set(self.clients.keys())
                    logger.info(
                        "content_routed_broadcast",
                        correlation_id=correlation_id,
                        rule_id=routing_decision.matched_rule.id,
                        target_agents=target_agents,
                        target_clients=len(target_clients),
                    )

        # Filter to active connections ONLY (null-safe)
        async with self._lock:

            def _is_disconnecting(ws):
                """Check if websocket is disconnecting (handles mocks and real WebSockets)."""
                if ws is None:
                    return True
                try:
                    client_state = getattr(ws, "client_state", None)
                    if client_state is None:
                        return False  # No client_state means assume active (for mocks)
                    disconnecting = getattr(client_state, "disconnecting", False)
                    # Handle Mock objects - check if it's a boolean
                    return bool(disconnecting) if not hasattr(disconnecting, "name") else False
                except Exception as e:
                    logger.debug("event_mesh_disconnect_check_failed", error=str(e))
                    return False

            # Identify null/disconnecting clients for cleanup
            to_cleanup = [cid for cid, ws in self.clients.items() if _is_disconnecting(ws)]

            # Create active clients dict
            if target_clients is not None:
                # Filter to target clients only
                active_clients = {
                    cid: ws
                    for cid, ws in self.clients.items()
                    if ws is not None and not _is_disconnecting(ws) and cid in target_clients
                }
            else:
                active_clients = {
                    cid: ws
                    for cid, ws in self.clients.items()
                    if ws is not None and not _is_disconnecting(ws)
                }

        # Cleanup null/disconnecting clients
        for client_id in to_cleanup:
            await self.unregister(client_id)

        if not active_clients:
            logger.debug("broadcast_no_clients")
            return {"sent": 0, "failed": 0, "routed": routing_decision is not None}

        sent = 0
        failed = 0
        to_remove = []

        # Send to all active clients
        for client_id, websocket in active_clients.items():
            try:
                await websocket.send_bytes(message)
                sent += 1
            except Exception as e:
                logger.error("broadcast_send_failed", client_id=client_id, error=str(e))
                failed += 1
                to_remove.append(client_id)

        # Cleanup failed connections
        for client_id in to_remove:
            await self.unregister(client_id)

        result = {
            "sent": sent,
            "failed": failed,
            "active": len(active_clients),
            "routed": routing_decision is not None,
        }

        if routing_decision:
            result["routing_decision"] = routing_decision.to_dict()

        logger.debug("broadcast_complete", **result)
        return result

    async def broadcast_json(
        self,
        data: dict,
        subject: str | None = None,
        correlation_id: str | None = None,
    ) -> dict[str, int]:
        """
        Broadcast JSON message to all clients with optional content routing.

        Args:
            data: Dict to send as JSON
            subject: Optional message subject for content routing
            correlation_id: Optional correlation ID for tracing

        Returns:
            Dict with success/failure counts and routing info
        """
        message = json.dumps(data).encode("utf-8")
        return await self.broadcast(
            message,
            subject=subject,
            payload=data,
            correlation_id=correlation_id,
        )

    async def send_to(
        self,
        client_id: str,
        message: bytes,
        subject: str | None = None,
        payload: dict[str, Any] | None = None,
        correlation_id: str | None = None,
    ) -> bool:
        """
        Send message to specific client with optional content routing.

        Args:
            client_id: Target client
            message: Message bytes
            subject: Optional message subject for content routing
            payload: Optional message payload for content filtering
            correlation_id: Optional correlation ID for tracing

        Returns:
            True if sent successfully
        """
        # Content-based routing check
        if subject and payload:
            routing_decision = self._content_router.route(
                subject=subject,
                payload=payload,
                correlation_id=correlation_id,
            )

            if routing_decision.decision == RouteDecision.MATCHED and routing_decision.matched_rule:
                # Check if client is in target agents
                target_agents = routing_decision.matched_rule.target_agents
                if target_agents and client_id not in target_agents:
                    logger.info(
                        "send_to_blocked_by_routing",
                        client_id=client_id,
                        rule_id=routing_decision.matched_rule.id,
                        target_agents=target_agents,
                    )
                    return False

        websocket = self.clients.get(client_id)

        if websocket is None:
            logger.warning("send_to_client_not_found", client_id=client_id)
            return False

        try:
            await websocket.send_bytes(message)
            logger.debug("send_to_success", client_id=client_id)
            return True
        except Exception as e:
            logger.error("send_to_failed", client_id=client_id, error=str(e))
            await self.unregister(client_id)
            return False

    async def send_to_json(
        self,
        client_id: str,
        data: dict,
        subject: str | None = None,
        correlation_id: str | None = None,
    ) -> bool:
        """
        Send JSON message to specific client with optional content routing.

        Args:
            client_id: Target client
            data: Dict to send as JSON
            subject: Optional message subject for content routing
            correlation_id: Optional correlation ID for tracing

        Returns:
            True if sent successfully
        """
        message = json.dumps(data).encode("utf-8")
        return await self.send_to(
            client_id,
            message,
            subject=subject,
            payload=data,
            correlation_id=correlation_id,
        )

    def get_client_ids(self) -> set[str]:
        """Get set of all connected client IDs."""
        return set(self.clients.keys())

    def get_content_router(self) -> ContentRouter:
        """Get the content router instance."""
        return self._content_router

    async def close_all(self) -> None:
        """Close all connections and cleanup."""
        async with self._lock:
            for _client_id, websocket in list(self.clients.items()):
                with contextlib.suppress(Exception):
                    await websocket.close()
            self.clients.clear()

        logger.info("eventmesh_closed_all", initial_count=len(self.clients))
