"""
ActorSupervisor - Supervisor for managing multiple actors.

This module provides:
- Spawn and manage multiple actors
- Monitor actor health
- Restart failed actors
- Coordinate actors
"""

import asyncio
from typing import Any, Optional

import structlog

from heretek_swarm.actors.base import ActorState, ActorStatus, AgentActor
from heretek_swarm.actors.circuit_breaker import TierCircuitBreaker
from heretek_swarm.actors.factory import ActorConfig
from heretek_swarm.actors.mixins import (
    AuditMixin,
    HealthReportingMixin,
    PatternMixin,
    ValidationMixin,
)
from heretek_swarm.collective.learning import PatternExtractor

logger = structlog.get_logger("ActorSupervisor")


# Global supervisor instance
_global_supervisor: Optional["ActorSupervisor"] = None


def get_supervisor() -> "ActorSupervisor":
    """
    Get global supervisor instance.

    Returns:
        ActorSupervisor instance
    """
    global _global_supervisor

    if _global_supervisor is None:
        _global_supervisor = ActorSupervisor()

    return _global_supervisor


class ActorSupervisor(AuditMixin, ValidationMixin, HealthReportingMixin, PatternMixin, AgentActor):
    """
    Supervisor for managing multiple actors.

    The supervisor provides centralized management for a collection of actors,
    including lifecycle management, health monitoring, and coordination.

    Example:
        ```python
        supervisor = ActorSupervisor()

        # Spawn actors
        await supervisor.spawn_actor(MyActor, "actor-1", topics=["topic1"])
        await supervisor.spawn_actor(MyActor, "actor-2", topics=["topic2"])

        # Monitor health
        await supervisor.start_monitoring()

        # Get status
        status = await supervisor.get_actor_status("actor-1")

        # Terminate all
        await supervisor.terminate_all()
        ```
    """

    def __init__(
        self,
        name: str | None = None,
        health_check_interval: float = 5.0,
        auto_restart: bool = True,
        max_restarts: int = 3,
        db_pool: Any | None = None,
        pattern_extractor: PatternExtractor | None = None,
        event_mesh: Any | None = None,
    ) -> None:
        """
        Initialize the supervisor.

        Args:
            name: Supervisor name
            health_check_interval: Interval between health checks in seconds
            auto_restart: Automatically restart failed actors
            max_restarts: Maximum restart attempts per actor
            db_pool: Optional asyncpg database connection pool for state persistence
            event_mesh: Optional NATS event mesh for message routing via Tier 1
        """
        # P1-7: Configuration validation
        if health_check_interval <= 0:
            raise ValueError("health_check_interval must be positive")
        if max_restarts < 0:
            raise ValueError("max_restarts must be non-negative")

        self.name = name or "ActorSupervisor"
        self.health_check_interval = health_check_interval
        self.auto_restart = auto_restart
        self.max_restarts = max_restarts
        self.db_pool = db_pool
        self.pattern_extractor = pattern_extractor or PatternExtractor()
        self._pattern_emitted: set[str] = set()

        # Call super().__init__ to initialize mixins and AgentActor base
        super().__init__(
            agent_id=name or "ActorSupervisor",
            name=self.name,
        )

        # Override with the injected event_mesh (AgentActor defaults to a stub)
        self._event_mesh = event_mesh

        # Tier-based circuit breaker for cascading restart storm prevention (D003)
        self._circuit_breaker = TierCircuitBreaker()

        self.actors: dict[str, AgentActor] = {}
        self.actor_configs: dict[str, ActorConfig] = {}
        self.restart_counts: dict[str, int] = {}
        self._running = False
        self._monitor_task: asyncio.Task | None = None
        # P2-5 fix: Removed unused _factory - dead code removal

        logger.info(
            f"[{self.name}] Supervisor initialized",
            extra={
                "health_check_interval": health_check_interval,
                "auto_restart": auto_restart,
                "max_restarts": max_restarts,
            },
        )

    async def initialize(self) -> None:
        """
        Initialize the supervisor.

        This method is called to initialize the supervisor after construction.
        It can be overridden by subclasses for custom initialization logic.
        """
        logger.info(f"[{self.name}] Supervisor initialize called")
        # Initialization is handled in __init__, this method is for API compatibility

    async def spawn_actor(
        self,
        actor_class: type[AgentActor],
        actor_id: str,
        actor_type: str | None = None,
        **kwargs: Any,
    ) -> AgentActor:
        """
        Spawn a new actor.

        Args:
            actor_class: Actor class to instantiate
            actor_id: Unique identifier for the actor
            actor_type: Optional type identifier for factory registration
            **kwargs: Additional arguments for actor initialization

        Returns:
            Spawned actor instance

        Raises:
            ValueError: If actor_id already exists
        """
        if actor_id in self.actors:
            raise ValueError(f"Actor {actor_id} already exists")

        try:
            # Create actor instance - only pass agent_id, agents handle their own init
            actor = actor_class(agent_id=actor_id)

            # Inject actor registry reference for message delivery
            actor.update_state("_actor_registry", self.actors)

            # Inject database pool for state persistence
            if self.db_pool is not None:
                actor.update_state("_db_pool", self.db_pool)

            # Inject event mesh for Tier 1 message routing (NATS)
            if self._event_mesh is not None:
                # Set both the attribute (checked first by _send_via_event_mesh)
                # and internal_state (for get_state("_event_mesh") fallback)
                actor._event_mesh = self._event_mesh
                actor.update_state("_event_mesh", self._event_mesh)
                logger.info(
                    "agent_spawned_with_mesh",
                    agent_id=actor_id,
                    mesh_type=type(self._event_mesh).__name__,
                )
            else:
                # When supervisor has no mesh, the agent already has a
                # StubEventMesh from AgentActor.__init__ fallback.
                agent_mesh = actor._event_mesh or actor.get_state("_event_mesh")
                logger.info(
                    "agent_spawned_without_supervisor_mesh",
                    agent_id=actor_id,
                    has_stub_fallback=agent_mesh is not None,
                    stub_type=type(agent_mesh).__name__ if agent_mesh is not None else None,
                )

            # Spawn the actor
            await actor.spawn()

            # Register actor
            self.actors[actor_id] = actor
            self.restart_counts[actor_id] = 0

            # Store configuration for restart capability
            config = ActorConfig(
                actor_type=actor_type or actor_class.__name__,
                class_ref=actor_class,
                init_kwargs={"agent_id": actor_id, **kwargs},
                capabilities=actor.capabilities.copy(),
                actor_id=actor_id,
            )
            self.actor_configs[actor_id] = config

            logger.info(
                f"[{self.name}] Actor {actor_id} spawned",
                extra={"actor_class": actor_class.__name__, "actor_type": actor_type},
            )

            return actor
        except ValueError:
            # Re-raise ValueError (e.g., duplicate actor_id)
            raise
        except Exception as e:
            # P1-10f fix: Comprehensive exception handling for spawn failures
            logger.exception(
                f"[{self.name}] Failed to spawn actor {actor_id}: {e}",

            )
            # Clean up partial state if actor was partially registered
            self.actors.pop(actor_id, None)
            self.restart_counts.pop(actor_id, None)
            self.actor_configs.pop(actor_id, None)
            raise

    async def terminate_actor(self, actor_id: str) -> None:
        """
        Terminate an actor.

        Args:
            actor_id: Actor identifier
        """
        if actor_id not in self.actors:
            logger.warning(
                "[%s] Actor not found: actor_id_hash=%s", self.name, hash(actor_id) % 10000
            )
            return

        actor = self.actors[actor_id]
        try:
            # P1-10g fix: Add exception handling around terminate()
            await actor.terminate()
        except Exception as e:
            logger.exception(
                f"[{self.name}] Error terminating actor {actor_id}: {e}",

            )
            # Still attempt cleanup even if terminate failed
            actor.state = ActorState.ERROR

        # Cleanup registry entries
        del self.actors[actor_id]
        if actor_id in self.restart_counts:
            del self.restart_counts[actor_id]
        if actor_id in self.actor_configs:
            del self.actor_configs[actor_id]

        logger.info(f"[{self.name}] Actor {actor_id} terminated")

    async def terminate_all(self) -> None:
        """Terminate all actors."""
        logger.info(f"[{self.name}] Terminating all actors...")

        actor_ids = list(self.actors.keys())
        tasks = [self.terminate_actor(actor_id) for actor_id in actor_ids]

        await asyncio.gather(*tasks, return_exceptions=True)

        logger.info(f"[{self.name}] All actors terminated")

    async def get_actor_status(self, actor_id: str) -> ActorStatus | None:
        """
        Get status of an actor.

        Args:
            actor_id: Actor identifier

        Returns:
            Actor status or None if not found
        """
        if actor_id not in self.actors:
            return None

        return self.actors[actor_id].get_status()

    async def get_all_status(self) -> dict[str, ActorStatus]:
        """
        Get status of all actors.

        Returns:
            Dictionary of actor statuses
        """
        return {actor_id: actor.get_status() for actor_id, actor in self.actors.items()}

    async def start_monitoring(self) -> None:
        """Start monitoring actors."""
        if self._running:
            logger.warning(f"[{self.name}] Monitoring already running")
            return

        self._running = True
        self._monitor_task = asyncio.create_task(self._monitor_loop())

        logger.info(f"[{self.name}] Actor monitoring started")

    async def stop_monitoring(self) -> None:
        """Stop monitoring actors."""
        self._running = False

        if self._monitor_task:
            self._monitor_task.cancel()
            try:
                await self._monitor_task
            except asyncio.CancelledError:
                logger.debug("Monitor task cancelled during actor shutdown")
            finally:
                # P1-10h fix: Reset _monitor_task to None after cancellation
                self._monitor_task = None

        logger.info(f"[{self.name}] Actor monitoring stopped")

    async def _monitor_loop(self) -> None:
        """Monitor actor health."""
        logger.info(f"[{self.name}] Starting monitor loop")

        while self._running:
            try:
                for actor_id, actor in list(self.actors.items()):
                    status = actor.get_status()

                    # Check for terminated actors - CLEAN UP
                    if status.state == ActorState.TERMINATED:
                        logger.warning(
                            f"[{self.name}] Actor {actor_id} is terminated - cleaning up",
                        )
                        await self.terminate_actor(actor_id)
                        continue

                    # Check for error state
                    if status.state == ActorState.ERROR:
                        logger.error(
                            f"[{self.name}] Actor {actor_id} in error state",
                        )
                        if self.auto_restart:
                            await self._attempt_restart(actor_id)

                    # Check for high error count - TAKE ACTION
                    if status.error_count > 10:
                        logger.warning(
                            f"[{self.name}] Actor {actor_id} has high error count: {status.error_count}",
                        )
                        if self.auto_restart and status.state != ActorState.ERROR:
                            # Set error state and attempt restart
                            actor.state = ActorState.ERROR
                            await self._attempt_restart(actor_id)

                await asyncio.sleep(self.health_check_interval)

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.exception(f"[{self.name}] Monitor error: {e}")
                await asyncio.sleep(5.0)

    async def _attempt_restart(self, actor_id: str) -> None:
        """
        Attempt to restart a failed actor using stored configuration.

        Args:
            actor_id: Actor identifier
        """
        if actor_id not in self.actors:
            return

        restart_count = self.restart_counts.get(actor_id, 0)

        if restart_count >= self.max_restarts:
            logger.error(
                f"[{self.name}] Actor {actor_id} exceeded max restarts ({self.max_restarts})",
            )
            await self.terminate_actor(actor_id)
            return

        # --- D003: Tier-based circuit breaker gate ---
        tier = TierCircuitBreaker.classify_tier(actor_id)
        if self._circuit_breaker.is_open(tier):
            logger.warning(
                "circuit_broken_restart_blocked",
                extra={
                    "actor_id": actor_id,
                    "tier": tier,
                    "supervisor": self.name,
                },
            )
            return

        logger.info(
            f"[{self.name}] Attempting restart {restart_count + 1}/{self.max_restarts} for {actor_id}",
        )

        try:
            # Get stored configuration
            config = self.actor_configs.get(actor_id)
            if config is None:
                logger.error(
                    f"[{self.name}] No configuration found for actor {actor_id}",
                )
                return

            # Terminate current actor
            await self.actors[actor_id].terminate()

            # Remove from actors dict
            del self.actors[actor_id]

            # Re-spawn using stored configuration
            actor_class = config.class_ref
            init_kwargs = config.init_kwargs

            # Create new instance
            new_actor = actor_class(**init_kwargs)
            await new_actor.spawn()

            # Inject registry, db_pool, and event_mesh into restarted actor
            new_actor.update_state("_actor_registry", self.actors)
            if self.db_pool is not None:
                new_actor.update_state("_db_pool", self.db_pool)
            if self._event_mesh is not None:
                new_actor._event_mesh = self._event_mesh
                new_actor.update_state("_event_mesh", self._event_mesh)
                logger.info(
                    "agent_restarted_with_mesh",
                    agent_id=actor_id,
                    mesh_type=type(self._event_mesh).__name__,
                )

            # Register new actor
            self.actors[actor_id] = new_actor
            self.restart_counts[actor_id] = restart_count + 1

            logger.info(
                f"[{self.name}] Actor {actor_id} successfully restarted",
                extra={"restart_count": self.restart_counts[actor_id]},
            )

        except Exception as e:
            logger.exception(f"[{self.name}] Restart failed for {actor_id}: {e}")
            self.restart_counts[actor_id] = restart_count + 1

            # D003: Record failure for circuit breaker; log if circuit just opened
            just_opened = self._circuit_breaker.record_failure(tier)
            if just_opened:
                tier_windows = self._circuit_breaker._windows
                logger.error(
                    "circuit_open",
                    extra={
                        "tier": tier,
                        "failure_count": len(tier_windows.get(tier, [])),
                        "window_seconds": self._circuit_breaker.window_seconds,
                        "threshold": self._circuit_breaker.failure_threshold,
                        "supervisor": self.name,
                    },
                )

    async def respawn_actor(self, actor_id: str) -> bool:
        """
        Manually trigger actor respawn using stored configuration.

        This method provides explicit control for respawning actors,
        separate from the automatic restart mechanism.

        Args:
            actor_id: Actor identifier to respawn

        Returns:
            True if respawn successful, False otherwise
        """
        if actor_id not in self.actors:
            logger.warning(f"[{self.name}] Cannot respawn actor {actor_id}: not found")
            return False

        config = self.actor_configs.get(actor_id)
        if config is None:
            logger.error(f"[{self.name}] No configuration found for actor {actor_id}")
            return False

        logger.info(f"[{self.name}] Manual respawn triggered for {actor_id}")

        try:
            # Terminate current actor
            await self.actors[actor_id].terminate()

            # Remove from actors dict
            del self.actors[actor_id]

            # Re-spawn using stored configuration
            actor_class = config.class_ref
            init_kwargs = config.init_kwargs

            # Create new instance
            new_actor = actor_class(**init_kwargs)
            await new_actor.spawn()

            # Inject registry, db_pool, and event_mesh into respawned actor
            new_actor.update_state("_actor_registry", self.actors)
            if self.db_pool is not None:
                new_actor.update_state("_db_pool", self.db_pool)
            if self._event_mesh is not None:
                new_actor._event_mesh = self._event_mesh
                new_actor.update_state("_event_mesh", self._event_mesh)
                logger.info(
                    "agent_respawned_with_mesh",
                    agent_id=actor_id,
                    mesh_type=type(self._event_mesh).__name__,
                )

            # Register new actor
            self.actors[actor_id] = new_actor

            logger.info(f"[{self.name}] Actor {actor_id} successfully respawned")
            return True

        except Exception as e:
            logger.exception(f"[{self.name}] Respawn failed for {actor_id}: {e}")
            return False

    async def save_all_states(self) -> None:
        """Save states of all actors."""
        logger.info(f"[{self.name}] Saving all actor states...")

        tasks = [actor.save_state() for actor in self.actors.values()]
        await asyncio.gather(*tasks, return_exceptions=True)

        logger.info(f"[{self.name}] All states saved")

    async def load_all_states(self) -> None:
        """Load states for all actors."""
        logger.info(f"[{self.name}] Loading all actor states...")

        tasks = [actor.load_state() for actor in self.actors.values()]
        await asyncio.gather(*tasks, return_exceptions=True)

        logger.info(f"[{self.name}] All states loaded")

    def get_statistics(self) -> dict[str, Any]:
        """
        Get supervisor statistics.

        Returns:
            Statistics dictionary
        """
        statuses = [actor.get_status() for actor in self.actors.values()]

        return {
            "total_actors": len(self.actors),
            "total_configs": len(self.actor_configs),
            "active_actors": sum(1 for s in statuses if s.state == ActorState.ACTIVE),
            "suspended_actors": sum(1 for s in statuses if s.state == ActorState.SUSPENDED),
            "terminated_actors": sum(1 for s in statuses if s.state == ActorState.TERMINATED),
            "error_actors": sum(1 for s in statuses if s.state == ActorState.ERROR),
            "total_messages": sum(s.message_count for s in statuses),
            "total_errors": sum(s.error_count for s in statuses),
            "total_restarts": sum(self.restart_counts.values()),
            "monitoring_active": self._running,
        }

    async def broadcast_to_all(
        self,
        content: dict[str, Any],
        message_type: str = "broadcast",
    ) -> None:
        """
        Broadcast a message to all actors.

        Args:
            content: Message content
            message_type: Message type identifier
        """
        logger.info(
            f"[{self.name}] Broadcasting to {len(self.actors)} actors",
        )

        tasks = [actor.broadcast(content, message_type) for actor in self.actors.values()]
        await asyncio.gather(*tasks, return_exceptions=True)

    def find_actors_by_capability(self, capability: str) -> list[str]:
        """
        Find actors with a specific capability.

        Args:
            capability: Capability to search for

        Returns:
            List of actor IDs
        """
        return [
            actor_id for actor_id, actor in self.actors.items() if capability in actor.capabilities
        ]

    def find_actors_by_topic(self, topic: str) -> list[str]:
        """
        Find actors subscribed to a specific topic.

        Args:
            topic: Topic to search for

        Returns:
            List of actor IDs
        """
        return [actor_id for actor_id, actor in self.actors.items() if topic in actor.topics]
