"""
NATS Agent Discovery Protocol.

Provides agent presence detection and registry via NATS pub/sub.
Uses heartbeat mechanism to track agent liveness.
"""

import asyncio
import contextlib
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from enum import Enum

import structlog

from heretek_swarm.infrastructure.nats.client import get_nats_client

logger = structlog.get_logger(__name__)

logger = __import__("logging").getLogger(__name__)


class AgentStatus(Enum):
    """Agent availability status."""

    ONLINE = "online"
    AWAY = "away"
    BUSY = "busy"
    OFFLINE = "offline"


@dataclass
class AgentInfo:
    """Information about a discovered agent."""

    agent_id: str
    agent_type: str
    name: str
    status: AgentStatus = AgentStatus.ONLINE
    capabilities: list[str] = field(default_factory=list)
    metadata: dict = field(default_factory=dict)
    last_heartbeat: datetime = field(default_factory=lambda: datetime.now(UTC))
    registered_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def to_dict(self) -> dict:
        return {
            "agent_id": self.agent_id,
            "agent_type": self.agent_type,
            "name": self.name,
            "status": self.status.value,
            "capabilities": self.capabilities,
            "metadata": self.metadata,
            "last_heartbeat": self.last_heartbeat.isoformat(),
            "registered_at": self.registered_at.isoformat(),
        }

    @classmethod
    def from_dict(cls, data: dict) -> "AgentInfo":
        return cls(
            agent_id=data["agent_id"],
            agent_type=data["agent_type"],
            name=data["name"],
            status=AgentStatus(data.get("status", "online")),
            capabilities=data.get("capabilities", []),
            metadata=data.get("metadata", {}),
            last_heartbeat=datetime.fromisoformat(data["last_heartbeat"]),
            registered_at=datetime.fromisoformat(data["registered_at"]),
        )


@dataclass
class HeartbeatMessage:
    """Heartbeat message for agent liveness."""

    agent_id: str
    timestamp: datetime = field(default_factory=lambda: datetime.now(UTC))
    status: AgentStatus = AgentStatus.ONLINE

    def to_dict(self) -> dict:
        return {
            "agent_id": self.agent_id,
            "timestamp": self.timestamp.isoformat(),
            "status": self.status.value,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "HeartbeatMessage":
        return cls(
            agent_id=data["agent_id"],
            timestamp=datetime.fromisoformat(data["timestamp"]),
            status=AgentStatus(data.get("status", "online")),
        )


@dataclass
class PresenceAnnouncement:
    """Agent presence announcement."""

    agent_id: str
    agent_type: str
    name: str
    capabilities: list[str]
    metadata: dict
    action: str  # "join" or "leave"
    timestamp: datetime = field(default_factory=lambda: datetime.now(UTC))

    def to_dict(self) -> dict:
        return {
            "agent_id": self.agent_id,
            "agent_type": self.agent_type,
            "name": self.name,
            "capabilities": self.capabilities,
            "metadata": self.metadata,
            "action": self.action,
            "timestamp": self.timestamp.isoformat(),
        }

    @classmethod
    def from_dict(cls, data: dict) -> "PresenceAnnouncement":
        return cls(
            agent_id=data["agent_id"],
            agent_type=data["agent_type"],
            name=data["name"],
            capabilities=data.get("capabilities", []),
            metadata=data.get("metadata", {}),
            action=data["action"],
            timestamp=datetime.fromisoformat(data["timestamp"]),
        )


class AgentRegistry:
    """
    Agent registry that tracks online agents via NATS pub/sub.

    Uses heartbeat mechanism to detect agent liveness and
    presence announcements for join/leave events.
    """

    HEARTBEAT_INTERVAL = 5.0  # seconds
    HEARTBEAT_TIMEOUT = 15.0  # seconds
    ANNOUNCEMENT_TOPIC = "agents.presence"
    HEARTBEAT_TOPIC = "agents.heartbeat"
    REGISTRY_TOPIC = "agents.registry"

    def __init__(self, nats_client=None):
        self._nats = nats_client
        self._agents: dict[str, AgentInfo] = {}
        self._heartbeat_tasks: dict[str, asyncio.Task] = {}
        self._subscriptions: list = []
        self._lock = asyncio.Lock()
        self._running = False

    async def initialize(self) -> None:
        """Initialize the discovery protocol."""
        if self._nats is None:
            self._nats = get_nats_client()

        await self._nats.ensure_connected()
        self._running = True

        # Subscribe to presence announcements
        sub = await self._nats.subscribe(self.ANNOUNCEMENT_TOPIC, self._handle_presence)
        self._subscriptions.append(sub)

        # Subscribe to heartbeat messages
        heartbeat_sub = await self._nats.subscribe(self.HEARTBEAT_TOPIC, self._handle_heartbeat)
        self._subscriptions.append(heartbeat_sub)

        logger.info("Agent discovery protocol initialized")

    async def _handle_presence(self, msg: dict) -> None:
        """Handle presence announcement (join/leave)."""
        try:
            announcement = PresenceAnnouncement.from_dict(msg)

            async with self._lock:
                if announcement.action == "join":
                    agent_info = AgentInfo(
                        agent_id=announcement.agent_id,
                        agent_type=announcement.agent_type,
                        name=announcement.name,
                        capabilities=announcement.capabilities,
                        metadata=announcement.metadata,
                    )
                    self._agents[announcement.agent_id] = agent_info
                    logger.info("Agent joined: {announcement.name} ({announcement.agent_id})")

                elif announcement.action == "leave":
                    if announcement.agent_id in self._agents:
                        del self._agents[announcement.agent_id]
                        logger.info("Agent left: {announcement.agent_id}")

        except Exception:
            logger.error("Error handling presence: {e}")

    async def _handle_heartbeat(self, msg: dict) -> None:
        """Handle heartbeat message from an agent."""
        try:
            heartbeat = HeartbeatMessage.from_dict(msg)

            async with self._lock:
                if heartbeat.agent_id in self._agents:
                    agent = self._agents[heartbeat.agent_id]
                    agent.last_heartbeat = heartbeat.timestamp
                    agent.status = heartbeat.status

        except Exception:
            logger.error("Error handling heartbeat: {e}")

    async def register_agent(
        self,
        agent_id: str,
        agent_type: str,
        name: str,
        capabilities: list[str] | None = None,
        metadata: dict | None = None,
    ) -> None:
        """
        Register an agent and announce its presence.

        Args:
            agent_id: Unique identifier for the agent
            agent_type: Type/category of the agent
            name: Human-readable name
            capabilities: List of agent capabilities
            metadata: Additional metadata
        """
        agent_info = AgentInfo(
            agent_id=agent_id,
            agent_type=agent_type,
            name=name,
            capabilities=capabilities or [],
            metadata=metadata or {},
        )

        async with self._lock:
            self._agents[agent_id] = agent_info

        # Announce presence
        announcement = PresenceAnnouncement(
            agent_id=agent_id,
            agent_type=agent_type,
            name=name,
            capabilities=capabilities or [],
            metadata=metadata or {},
            action="join",
        )

        await self._nats.publish(self.ANNOUNCEMENT_TOPIC, announcement.to_dict())

        # Start heartbeat for this agent
        await self._start_heartbeat(agent_id)

        logger.info("Agent registered: {name} ({agent_id})")

    async def unregister_agent(self, agent_id: str) -> None:
        """
        Unregister an agent and announce its departure.

        Args:
            agent_id: The agent to unregister
        """
        # Stop heartbeat task
        if agent_id in self._heartbeat_tasks:
            self._heartbeat_tasks[agent_id].cancel()
            del self._heartbeat_tasks[agent_id]

        # Get agent info before removal
        async with self._lock:
            agent = self._agents.get(agent_id)
            if agent:
                del self._agents[agent_id]

        # Announce departure
        if agent:
            announcement = PresenceAnnouncement(
                agent_id=agent_id,
                agent_type=agent.agent_type,
                name=agent.name,
                capabilities=agent.capabilities,
                metadata=agent.metadata,
                action="leave",
            )
            await self._nats.publish(self.ANNOUNCEMENT_TOPIC, announcement.to_dict())

        logger.info("Agent unregistered: {agent_id}")

    async def _start_heartbeat(self, agent_id: str) -> None:
        """Start heartbeat task for an agent."""

        async def heartbeat_loop():
            while self._running and agent_id in self._agents:
                try:
                    heartbeat = HeartbeatMessage(
                        agent_id=agent_id,
                        timestamp=datetime.now(UTC),
                    )
                    await self._nats.publish(self.HEARTBEAT_TOPIC, heartbeat.to_dict())
                    await asyncio.sleep(self.HEARTBEAT_INTERVAL)
                except asyncio.CancelledError:
                    break
                except Exception:
                    logger.error("Heartbeat error for {agent_id}: {e}")

        task = asyncio.create_task(heartbeat_loop())
        self._heartbeat_tasks[agent_id] = task

    async def send_heartbeat(
        self,
        agent_id: str,
        status: AgentStatus = AgentStatus.ONLINE,
    ) -> None:
        """
        Send a heartbeat for this agent.

        Args:
            agent_id: The agent's ID
            status: Current agent status
        """
        heartbeat = HeartbeatMessage(
            agent_id=agent_id,
            timestamp=datetime.now(UTC),
            status=status,
        )
        await self._nats.publish(self.HEARTBEAT_TOPIC, heartbeat.to_dict())

    def get_agent(self, agent_id: str) -> AgentInfo | None:
        """Get information about a specific agent."""
        return self._agents.get(agent_id)

    def get_agents_by_type(self, agent_type: str) -> list[AgentInfo]:
        """Get all agents of a specific type."""
        return [agent for agent in self._agents.values() if agent.agent_type == agent_type]

    def get_agents_by_status(self, status: AgentStatus) -> list[AgentInfo]:
        """Get all agents with a specific status."""
        return [agent for agent in self._agents.values() if agent.status == status]

    def list_agents(self) -> list[AgentInfo]:
        """List all registered agents."""
        return list(self._agents.values())

    async def cleanup_stale_agents(self) -> list[str]:
        """
        Remove agents that haven't sent heartbeat recently.

        Returns:
            List of removed agent IDs
        """
        removed = []
        cutoff = datetime.now(UTC) - timedelta(seconds=self.HEARTBEAT_TIMEOUT)

        async with self._lock:
            stale = [
                agent_id
                for agent_id, agent in self._agents.items()
                if agent.last_heartbeat < cutoff
            ]

            for agent_id in stale:
                del self._agents[agent_id]
                removed.append(agent_id)

                # Stop heartbeat task
                if agent_id in self._heartbeat_tasks:
                    self._heartbeat_tasks[agent_id].cancel()
                    del self._heartbeat_tasks[agent_id]

        for agent_id in removed:
            logger.warning("Removed stale agent: {agent_id}")

        return removed

    async def close(self) -> None:
        """Close the discovery protocol and cleanup."""
        self._running = False

        # Cancel all heartbeat tasks
        for task in self._heartbeat_tasks.values():
            task.cancel()
        self._heartbeat_tasks.clear()

        # Unsubscribe from topics
        for sub in self._subscriptions:
            with contextlib.suppress(Exception):
                await sub.unsubscribe()
        self._subscriptions.clear()

        # Clear agents
        self._agents.clear()

        logger.info("Agent discovery protocol closed")


# Global registry instance
_registry: AgentRegistry | None = None


async def get_discovery_registry() -> AgentRegistry:
    """Get the global discovery registry instance."""
    global _registry
    if _registry is None:
        _registry = AgentRegistry()
        await _registry.initialize()
    return _registry


async def shutdown_discovery_registry() -> None:
    """Shutdown the global discovery registry."""
    global _registry
    if _registry is not None:
        await _registry.close()
        _registry = None
