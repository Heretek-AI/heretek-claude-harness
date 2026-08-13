"""
Example Plugins for Heretek Swarm

This module contains example plugins demonstrating the plugin system.
"""

import asyncio
from datetime import UTC
from typing import Any

import structlog

from .manager import Plugin, PluginMetadata, PluginState

logger = structlog.get_logger(__name__)


class LoggingPlugin(Plugin):
    """
    Example plugin that logs all messages.

    Demonstrates basic message handling.
    """

    def __init__(self):
        self.metadata = PluginMetadata(
            name="logging",
            version="0.1.0",
            description="Logs all messages passing through the system",
            author="Heretek Swarm",
            dependencies=[],
        )
        self.message_count = 0

    async def on_load(self, runtime) -> None:
        """Called when plugin is loaded."""
        await super().on_load(runtime)

    async def on_message(self, _message: dict[str, Any]) -> dict[str, Any] | None:
        """
        Handle incoming messages.

        Args:
            message: Message dictionary

        Returns:
            None (no response)
        """
        self.message_count += 1

        # Don't modify the message, just log it
        return None


class MemoryEnhancementPlugin(Plugin):
    """
    Example plugin that enhances memory operations.

    Demonstrates agent lifecycle hooks.
    """

    def __init__(self):
        self.metadata = PluginMetadata(
            name="memory_enhancement",
            version="0.1.0",
            description="Enhances memory with importance scoring",
            author="Heretek Swarm",
            dependencies=["memory"],
        )
        self.active_agents: dict[str, Any] = {}

    async def on_load(self, runtime) -> None:
        """Called when plugin is loaded."""
        await super().on_load(runtime)

    async def on_agent_spawn(self, agent_id: str) -> None:
        """
        Called when an agent is spawned.

        Args:
            agent_id: Agent identifier
        """
        self.active_agents[agent_id] = {"spawned_at": self._get_timestamp(), "message_count": 0}

    async def on_agent_terminate(self, agent_id: str) -> None:
        """
        Called when an agent is terminated.

        Args:
            agent_id: Agent identifier
        """
        if agent_id in self.active_agents:
            self.active_agents[agent_id]
            del self.active_agents[agent_id]

    async def on_message(self, message: dict[str, Any]) -> dict[str, Any] | None:
        """
        Handle incoming messages.

        Args:
            message: Message dictionary

        Returns:
            Enhanced message with importance score
        """
        # Track message count for active agents
        agent_id = message.get("agent_id")
        if agent_id and agent_id in self.active_agents:
            self.active_agents[agent_id]["message_count"] += 1

        # Add importance score based on message content
        content = str(message.get("content", ""))
        importance = self._calculate_importance(content)

        # Return enhanced message
        return {
            "original_message": message,
            "importance_score": importance,
            "enhanced_at": self._get_timestamp(),
        }

    def _calculate_importance(self, content: str) -> float:
        """
        Calculate importance score based on content.

        Args:
            content: Message content

        Returns:
            Importance score (0.0 to 1.0)
        """
        if not content:
            return 0.1

        # Simple heuristics
        importance = 0.1

        # Longer content is more important
        if len(content) > 100:
            importance += 0.2

        # Contains keywords
        keywords = ["important", "urgent", "critical", "error", "warning"]
        if any(keyword in content.lower() for keyword in keywords):
            importance += 0.3

        # Cap at 1.0
        return min(importance, 1.0)

    def _get_timestamp(self) -> str:
        """Get current timestamp in ISO format."""
        from datetime import datetime

        return datetime.now(UTC).isoformat()


class HealthMonitorPlugin(Plugin):
    """
    Example plugin that monitors system health.

    Demonstrates periodic tasks.
    """

    def __init__(self):
        self.metadata = PluginMetadata(
            name="health_monitor",
            version="0.1.0",
            description="Monitors system health and performance",
            author="Heretek Swarm",
            dependencies=[],
        )
        self.health_status = "healthy"
        self.check_count = 0

    async def on_load(self, runtime) -> None:
        """Called when plugin is loaded."""
        await super().on_load(runtime)

        # Start periodic health checks
        self._start_health_checks()

    def _start_health_checks(self) -> None:
        """Start periodic health checks."""
        asyncio.create_task(self._health_check_loop())  # noqa: RUF006

    async def _health_check_loop(self) -> None:
        """Periodic health check loop."""
        while self.state == PluginState.ACTIVE:
            await asyncio.sleep(60)  # Check every minute
            await self._check_health()

    async def _check_health(self) -> None:
        """Perform health check."""
        self.check_count += 1

        # Check memory
        try:
            from memory.persistent import PersistentMemoryStore

            memory_store = PersistentMemoryStore()
            await memory_store.connect()

            # Simple health check
            self.health_status = "healthy"

        except Exception as e:
            self.health_status = f"unhealthy: {e!s}"

    async def on_message(self, message: dict[str, Any]) -> dict[str, Any] | None:
        """
        Handle incoming messages.

        Args:
            message: Message dictionary

        Returns:
            Health status if requested
        """
        # Respond to health status requests
        if message.get("type") == "health_check":
            return {
                "health_status": self.health_status,
                "check_count": self.check_count,
                "checked_at": self._get_timestamp(),
            }

        return None


# Plugin registry for easy import
AVAILABLE_PLUGINS = {
    "logging": LoggingPlugin,
    "memory_enhancement": MemoryEnhancementPlugin,
    "health_monitor": HealthMonitorPlugin,
}


def get_plugin(plugin_name: str) -> type | None:
    """
    Get a plugin class by name.

    Args:
        plugin_name: Name of plugin

    Returns:
        Plugin class or None
    """
    return AVAILABLE_PLUGINS.get(plugin_name)


def list_available_plugins() -> list[str]:
    """
    List all available example plugins.

    Returns:
        List of plugin names
    """
    return list(AVAILABLE_PLUGINS.keys())
