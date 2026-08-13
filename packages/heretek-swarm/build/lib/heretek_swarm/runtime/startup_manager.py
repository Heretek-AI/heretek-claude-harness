"""
Runtime Startup Manager

Subscribes to wizard.completed events and starts the autonomous runtime
with tier-specific agent configurations.
"""

import asyncio
import signal
from pathlib import Path
from typing import Any

import structlog

from heretek_swarm.infrastructure.nats.publisher import (
    SwarmEvent,
)
from heretek_swarm.infrastructure.nats.subscriber import (
    NATSSubscriber,
    get_subscriber,
)
from heretek_swarm.runtime.autonomous_runtime import AutonomousRuntime
from heretek_swarm.runtime.autonomous_runtime_config import AutonomousRuntimeConfig

logger = structlog.get_logger("startup_manager")


class StartupManager:
    """
    Manages autonomous runtime startup triggered by wizard completion.

    Subscribes to swarm.wizard.completed events and starts the runtime
    with tier-specific configuration.
    """

    def __init__(self):
        self._subscriber: NATSSubscriber | None = None
        self._runtime: AutonomousRuntime | None = None
        self._running = False
        self._subscription_id: str | None = None

    async def initialize(self) -> None:
        """Initialize the startup manager."""
        self._subscriber = get_subscriber()
        await self._subscriber.initialize()
        logger.info("startup_manager_initialized")

    async def start(self) -> None:
        """Start listening for wizard.completed events."""
        if self._running:
            logger.warning("startup_manager_already_running")
            return

        self._running = True

        # Subscribe to wizard.completed events
        async def on_wizard_completed(event: SwarmEvent) -> None:
            """Handle wizard completion event."""
            await self._handle_wizard_completed(event)

        try:
            self._subscription_id = await self._subscriber.subscribe(
                subject="swarm.wizard.completed",
                callback=on_wizard_completed,
                queue="startup_manager",
            )
            logger.info(
                "startup_manager_subscription_created",
                subscription_id=self._subscription_id,
            )
        except Exception as e:
            logger.error("startup_manager_subscription_failed", error=str(e))
            raise

        # Setup signal handlers for graceful shutdown
        loop = asyncio.get_event_loop()
        for sig in (signal.SIGINT, signal.SIGTERM):
            try:
                loop.add_signal_handler(
                    sig, lambda s=sig: asyncio.create_task(self._handle_signal(s))
                )
            except NotImplementedError:
                # Windows doesn't support add_signal_handler
                logger.debug("Signal handler setup not supported on this platform (Windows)")

        logger.info("startup_manager_started")

    async def _handle_signal(self, signum: int) -> None:
        """Handle shutdown signals."""
        logger.info("startup_manager_shutdown_signal", signal=signum)
        await self.stop()

    async def _handle_wizard_completed(self, event: SwarmEvent) -> None:
        """
        Handle wizard completion event.

        Extracts tier configuration from the event and starts the autonomous runtime.
        """
        logger.info(
            "wizard_completed_event_received",
            event_type=event.event_type,
            correlation_id=event.correlation_id,
        )

        try:
            # Extract tier configuration from event payload
            payload = event.payload
            tier_id = payload.get("tier_id", "default")
            agent_count = payload.get("agent_count", 3)
            agents = payload.get("agents", [])
            memory_enabled = payload.get("memory_enabled", True)
            consciousness_enabled = payload.get("consciousness_enabled", True)

            logger.info(
                "starting_runtime_from_wizard",
                tier_id=tier_id,
                agent_count=agent_count,
                agents=agents,
                memory_enabled=memory_enabled,
                consciousness_enabled=consciousness_enabled,
            )

            # Build agent configs from event payload
            agent_configs = self._build_agent_configs(agents, tier_id)

            # Create runtime configuration
            config = AutonomousRuntimeConfig(
                agent_configs=agent_configs,
                monitoring_enabled=True,
                auto_restart_enabled=True,
                consciousness_plugin_enabled=consciousness_enabled,
                rag_enabled=memory_enabled,
                min_agents=min(agent_count, 3),
                max_agents=agent_count,
                state_persistence_enabled=True,
            )

            # Initialize and start the runtime
            self._runtime = AutonomousRuntime(config)
            await self._runtime.initialize()

            logger.info("autonomous_runtime_initialized", tier_id=tier_id)
            await self._runtime.start()

        except Exception as e:
            logger.error(
                "runtime_startup_failed",
                error=str(e),
                error_type=type(e).__name__,
            )
            # Don't re-raise - allow manager to continue running
            # for future wizard.completed events

    def _build_agent_configs(
        self,
        agents: list[str],
        tier_id: str,  # noqa: ARG002
    ) -> dict[str, Path]:
        """
        Build agent configuration paths from tier agents list.

        Args:
            agents: List of agent names from wizard configuration
            tier_id: Tier identifier

        Returns:
            Dictionary mapping agent names to character config paths
        """
        base_dir = Path(__file__).parent / "characters"
        agent_configs: dict[str, Path] = {}

        for agent_name in agents:
            # Use character config if exists, otherwise use tier-based default
            config_path = base_dir / f"{agent_name}.json"
            if not config_path.exists():
                config_path = base_dir / "default.json"

            agent_configs[agent_name] = config_path

        # Ensure at least one agent
        if not agent_configs:
            default_path = base_dir / "coordinator.json"
            if not default_path.exists():
                default_path = base_dir / "default.json"
            agent_configs["coordinator"] = default_path

        return agent_configs

    async def stop(self) -> None:
        """Stop the startup manager and runtime."""
        logger.info("stopping_startup_manager")

        self._running = False

        # Stop the runtime if running
        if self._runtime:
            try:
                await self._runtime.stop()
                logger.info("runtime_stopped")
            except Exception as e:
                logger.error("runtime_stop_error", error=str(e))

        # Unsubscribe from NATS
        if self._subscription_id and self._subscriber:
            try:
                await self._subscriber.unsubscribe(self._subscription_id)
            except Exception as e:
                logger.warning("unsubscribe_error", error=str(e))

        # Close subscriber
        if self._subscriber:
            try:
                await self._subscriber.close()
            except Exception as e:
                logger.warning("subscriber_close_error", error=str(e))

        logger.info("startup_manager_stopped")

    def get_status(self) -> dict[str, Any]:
        """Get current status of the startup manager."""
        return {
            "running": self._running,
            "subscription_id": self._subscription_id,
            "runtime_active": self._runtime is not None,
            "runtime_status": self._runtime.get_status() if self._runtime else None,
        }


# Global startup manager instance
_manager: StartupManager | None = None


def get_startup_manager() -> StartupManager:
    """Get the global startup manager instance."""
    global _manager
    if _manager is None:
        _manager = StartupManager()
    return _manager


async def run_startup_manager() -> None:
    """
    Run the startup manager as a standalone service.

    This is the main entry point for starting the runtime via wizard completion.
    """
    manager = get_startup_manager()
    await manager.initialize()
    await manager.start()

    try:
        # Keep running until stopped
        while manager._running:  # noqa: SLF001,ASYNC110
            await asyncio.sleep(1)
    except asyncio.CancelledError:
        logger.debug("Startup manager run loop cancelled")
    finally:
        await manager.stop()


__all__ = [
    "StartupManager",
    "get_startup_manager",
    "run_startup_manager",
]
