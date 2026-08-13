"""
A2A Protocol Server - Agent-to-Agent Communication

WebSocket RPC server on port 18789 for inter-agent communication.
Implements handshake, discovery, messaging, and consensus protocols.

Reference: OpenClaw A2A Protocol + MiniMax Audit

SECURITY: Token-based authentication required for all connections.
"""

import asyncio
import json
import os
import secrets
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from enum import StrEnum
from typing import Any

import structlog
from fastapi import WebSocket, WebSocketDisconnect

from .event_mesh import EventMesh

logger = structlog.get_logger(__name__)

# =============================================================================
# Authentication Configuration
# =============================================================================


class AuthTokenManager:
    """Manages authentication tokens for A2A connections."""

    def __init__(self, secret_key: str | None = None):
        self.secret_key = secret_key or os.environ.get("A2A_SECRET_KEY", secrets.token_hex(32))
        self._valid_tokens: dict[str, dict[str, Any]] = {}
        self._token_expiry = timedelta(hours=24)

    def generate_token(self, agent_id: str, metadata: dict | None = None) -> str:
        """Generate an authentication token for an agent."""
        token = secrets.token_urlsafe(32)
        self._valid_tokens[token] = {
            "agent_id": agent_id,
            "created_at": datetime.now(UTC),
            "expires_at": datetime.now(UTC) + self._token_expiry,
            "metadata": metadata or {},
        }
        return token

    def validate_token(self, token: str) -> tuple[bool, str | None, str | None]:
        """
        Validate an authentication token.

        Returns:
            Tuple of (is_valid, agent_id, error_message)
        """
        if token not in self._valid_tokens:
            return False, None, "Invalid token"

        token_data = self._valid_tokens[token]
        if datetime.now(UTC) > token_data["expires_at"]:
            del self._valid_tokens[token]
            return False, None, "Token expired"

        return True, token_data["agent_id"], None

    def revoke_token(self, token: str) -> bool:
        """Revoke a token."""
        if token in self._valid_tokens:
            del self._valid_tokens[token]
            return True
        return False

    def cleanup_expired(self) -> int:
        """Remove expired tokens. Returns count of removed tokens."""
        now = datetime.now(UTC)
        expired = [t for t, data in self._valid_tokens.items() if now > data["expires_at"]]
        for token in expired:
            del self._valid_tokens[token]
        return len(expired)


# Global token manager instance
token_manager = AuthTokenManager()


class MessageType(StrEnum):
    """A2A message types."""

    HANDSHAKE = "handshake"
    DISCOVERY = "discovery"
    MESSAGE = "message"
    STATUS = "status"
    PROPOSAL = "proposal"
    VOTE = "vote"
    DECISION = "decision"
    ERROR = "error"


@dataclass
class AgentInfo:
    """Connected agent information."""

    id: str
    websocket: WebSocket
    connected_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    last_activity: datetime = field(default_factory=lambda: datetime.now(UTC))
    status: str = "idle"
    metadata: dict[str, Any] = field(default_factory=dict)


class A2AServer:
    """
    Agent-to-Agent communication server.

    Runs on port 18789, manages agent connections and message routing.
    """

    def __init__(self, event_mesh: EventMesh):
        self.event_mesh = event_mesh
        self.agents: dict[str, AgentInfo] = {}
        self._lock = asyncio.Lock()
        self._message_log: list[dict] = []
        self._max_log_size = 1000

    async def handle_connection(
        self, websocket: WebSocket, agent_id: str, auth_token: str | None = None
    ) -> None:
        """
        Handle new agent connection with authentication.

        SECURITY: Requires valid authentication token before allowing connection.

        Args:
            websocket: WebSocket connection
            agent_id: Agent identifier
            auth_token: Authentication token (required)
        """
        # SECURITY: Validate authentication token
        if not auth_token:
            try:
                await websocket.accept()
                await websocket.send_json(
                    {
                        "type": MessageType.ERROR.value,
                        "error": "Authentication required. Provide valid auth_token.",
                    }
                )
                await websocket.close()
            except Exception as e:
                logger.debug("a2a_close_failed", error=str(e))
            logger.warning("a2a_connection_rejected_no_auth", agent_id=agent_id)
            return

        # Validate token
        is_valid, valid_agent_id, error = token_manager.validate_token(auth_token)
        if not is_valid:
            try:
                await websocket.accept()
                await websocket.send_json(
                    {"type": MessageType.ERROR.value, "error": f"Authentication failed: {error}"}
                )
                await websocket.close()
            except Exception as e:
                logger.debug("a2a_close_failed", error=str(e))
            logger.warning("a2a_connection_rejected_invalid_token", agent_id=agent_id, error=error)
            return

        # SECURITY: Verify agent_id matches token
        if valid_agent_id != agent_id:
            try:
                await websocket.accept()
                await websocket.send_json(
                    {
                        "type": MessageType.ERROR.value,
                        "error": f"Agent ID mismatch. Token belongs to {valid_agent_id}",
                    }
                )
                await websocket.close()
            except Exception as e:
                logger.debug("a2a_close_failed", error=str(e))
            logger.warning(
                "a2a_connection_rejected_agent_mismatch",
                requested_agent=agent_id,
                token_agent=valid_agent_id,
            )
            return

        # Accept connection
        await websocket.accept()
        logger.info("a2a_connection_accepted", agent_id=agent_id, authenticated=True)

        # Register agent
        agent_info = AgentInfo(id=agent_id, websocket=websocket)
        async with self._lock:
            self.agents[agent_id] = agent_info

        await self.event_mesh.register(agent_id, websocket)

        # Send handshake response
        await websocket.send_json(
            {
                "type": MessageType.HANDSHAKE.value,
                "status": "ok",
                "agent_id": agent_id,
                "timestamp": datetime.now(UTC).isoformat(),
                "server": "heretek-swarm-a2a",
                "authenticated": True,
            }
        )

        # Log connection
        self._log_message(
            {
                "type": "connection",
                "agent_id": agent_id,
                "action": "connected",
                "authenticated": True,
                "timestamp": datetime.now(UTC).isoformat(),
            }
        )

        try:
            # Message loop
            while True:
                try:
                    data = await websocket.receive_json()
                    await self._handle_message(agent_id, data)
                except json.JSONDecodeError as e:
                    logger.error("a2a_invalid_json", agent_id=agent_id, error=str(e))
                    await websocket.send_json(
                        {"type": MessageType.ERROR.value, "error": f"Invalid JSON: {e!s}"}
                    )
        except WebSocketDisconnect:
            logger.info("a2a_agent_disconnected", agent_id=agent_id)
        finally:
            await self._cleanup_agent(agent_id)

    async def _handle_message(self, agent_id: str, data: dict) -> None:
        """
        Handle incoming message from agent.

        Args:
            agent_id: Sending agent
            data: Message data
        """
        msg_type = data.get("type", "message")
        logger.debug("a2a_message_received", agent_id=agent_id, type=msg_type)

        # Update last activity
        async with self._lock:
            if agent_id in self.agents:
                self.agents[agent_id].last_activity = datetime.now(UTC)

        # Route by message type
        if msg_type == MessageType.HANDSHAKE.value:
            await self._handle_handshake(agent_id, data)
        elif msg_type == MessageType.DISCOVERY.value:
            await self._handle_discovery(agent_id, data)
        elif msg_type == MessageType.MESSAGE.value:
            await self._handle_message_broadcast(agent_id, data)
        elif msg_type == MessageType.PROPOSAL.value:
            await self._handle_proposal(agent_id, data)
        elif msg_type == MessageType.VOTE.value:
            await self._handle_vote(agent_id, data)
        else:
            logger.warning("a2a_unknown_message_type", type=msg_type)

    async def _handle_handshake(self, agent_id: str, _data: dict) -> None:
        """Handle handshake message."""
        logger.info("a2a_handshake", agent_id=agent_id)
        # Already handled in connection setup

    async def _handle_discovery(self, agent_id: str, _data: dict) -> None:
        """
        Handle discovery request - return list of all agents.

        Args:
            agent_id: Requesting agent
            data: Request data
        """
        async with self._lock:
            agents_list = [
                {
                    "id": aid,
                    "status": info.status,
                    "connected_at": info.connected_at.isoformat()
                    if isinstance(info.connected_at, datetime)
                    else info.connected_at,
                    "last_activity": info.last_activity.isoformat()
                    if isinstance(info.last_activity, datetime)
                    else info.last_activity,
                }
                for aid, info in self.agents.items()
            ]

        response = {
            "type": MessageType.DISCOVERY.value,
            "agents": agents_list,
            "count": len(agents_list),
            "timestamp": datetime.now(UTC).isoformat(),
        }

        await self.event_mesh.send_to_json(agent_id, response)

    async def _handle_message_broadcast(self, sender_id: str, data: dict) -> None:
        """
        Handle message broadcast to all agents.

        Args:
            sender_id: Sending agent
            data: Message with content
        """
        message = {
            "type": MessageType.MESSAGE.value,
            "from": sender_id,
            "content": data.get("content"),
            "metadata": data.get("metadata", {}),
            "timestamp": datetime.now(UTC).isoformat(),
        }

        # Broadcast to all except sender
        await self.event_mesh.broadcast_json(message)

        # Fire-and-forget: publish to NATS for dashboard/WebSocket bridge
        await self.event_mesh.publish_to_nats(
            event_type="a2a.message",
            source_agent=sender_id,
            payload=message,
            topic="swarm.events",
        )

        # Log message
        self._log_message(message)

    async def _handle_proposal(self, agent_id: str, data: dict) -> None:
        """
        Handle consensus proposal.

        Args:
            agent_id: Proposing agent
            data: Proposal data
        """
        proposal = {
            "type": MessageType.PROPOSAL.value,
            "id": data.get("id", f"proposal_{datetime.now(UTC).timestamp()}"),
            "from": agent_id,
            "action": data.get("action"),
            "details": data.get("details", {}),
            "timestamp": datetime.now(UTC).isoformat(),
        }

        logger.info("a2a_proposal_created", proposal_id=proposal["id"], agent_id=agent_id)

        # Broadcast to all agents
        await self.event_mesh.broadcast_json(proposal)

        # Log
        self._log_message(proposal)

    async def _handle_vote(self, agent_id: str, data: dict) -> None:
        """
        Handle consensus vote.

        Args:
            agent_id: Voting agent
            data: Vote data
        """
        vote = {
            "type": MessageType.VOTE.value,
            "proposal_id": data.get("proposal_id"),
            "from": agent_id,
            "vote": data.get("vote"),  # "yes", "no", "abstain"
            "reason": data.get("reason", ""),
            "timestamp": datetime.now(UTC).isoformat(),
        }

        logger.info("a2a_vote_cast", proposal_id=vote["proposal_id"], vote=vote["vote"])

        # Broadcast vote
        await self.event_mesh.broadcast_json(vote)

        # Log
        self._log_message(vote)

    async def _cleanup_agent(self, agent_id: str) -> None:
        """
        Cleanup agent connection.

        Args:
            agent_id: Agent to cleanup
        """
        async with self._lock:
            if agent_id in self.agents:
                del self.agents[agent_id]

        await self.event_mesh.unregister(agent_id)

        # Log disconnection
        self._log_message(
            {
                "type": "connection",
                "agent_id": agent_id,
                "action": "disconnected",
                "timestamp": datetime.now(UTC).isoformat(),
            }
        )

    def _log_message(self, message: dict) -> None:
        """
        Log message to internal log with size limit.

        Args:
            message: Message to log
        """
        self._message_log.append(message)

        # Trim if over limit
        if len(self._message_log) > self._max_log_size:
            self._message_log = self._message_log[-self._max_log_size :]

    def get_message_log(self, limit: int = 100) -> list[dict]:
        """Get recent message log."""
        return self._message_log[-limit:]

    def get_statistics(self) -> dict:
        """Get server statistics."""
        return {
            "connected_agents": len(self.agents),
            "agent_ids": list(self.agents.keys()),
            "message_log_size": len(self._message_log),
            "uptime": "active",
            "active_tokens": len(token_manager._valid_tokens),  # noqa: SLF001
        }

    @staticmethod
    def generate_auth_token(agent_id: str, metadata: dict | None = None) -> str:
        """Generate an authentication token for an agent."""
        return token_manager.generate_token(agent_id, metadata)

    @staticmethod
    def revoke_auth_token(token: str) -> bool:
        """Revoke an authentication token."""
        return token_manager.revoke_token(token)
