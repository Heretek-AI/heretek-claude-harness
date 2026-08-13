"""
Autonomous Runtime Manager

Manages 24/7 autonomous operation of Heretek Swarm including:
- Agent lifecycle management
- Health monitoring and auto-recovery
- Auto-scaling based on load
- State persistence and recovery
- Alerting and notifications
"""

import asyncio
import os
import signal
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import structlog

from heretek_swarm.actors.supervisor import ActorSupervisor
from heretek_swarm.collective.agency_tracking import AgencyMetricsTracker

from .agent_runtime import AgentRuntime
from .autonomous_runtime_config import (
    AutonomousRuntimeConfig,
)
from .scaling import (
    AgentPoolManager,
    ScalingAction,
    ScalingConfig,
    ScalingResult,
)
from .self_maintenance import (
    SelfMaintenanceConfig,
    SelfMaintenanceScheduler,
)

logger = structlog.get_logger("AutonomousRuntime")


@dataclass
class RuntimeState:
    """Current state of the autonomous runtime."""

    start_time: datetime
    uptime_seconds: float = 0.0
    total_agent_restarts: int = 0
    total_failures: int = 0
    last_health_check: datetime | None = None
    last_scale_event: datetime | None = None
    current_agents: int = 0


class AutonomousRuntime:
    """
    Autonomous runtime manager for 24/7 operation.

    Features:
    - Continuous health monitoring
    - Automatic failure recovery
    - Dynamic agent scaling
    - State persistence
    - Alert notifications
    """

    def __init__(self, config: AutonomousRuntimeConfig):
        """
        Initialize autonomous runtime.

        Args:
            config: Runtime configuration
        """
        # P2-1 fix: Use timezone-aware datetime
        self.config = config
        self.supervisor: ActorSupervisor | None = None
        self.agent_runtime: AgentRuntime | None = None
        self.state = RuntimeState(start_time=datetime.now(UTC))
        self._running = False
        self._shutdown_event = asyncio.Event()

        # Alert cooldown tracking
        self._last_alert_time: dict[str, datetime] = {}

        # Scaling cooldown tracking
        self._last_scale_up_time: datetime | None = None
        self._last_scale_down_time: datetime | None = None

        # P1-8 fix: Track restart attempts separately instead of using __dict__
        self._restart_attempts: dict[str, int] = {}

        # Self-maintenance scheduler
        self._maintenance_scheduler: SelfMaintenanceScheduler | None = None
        self._maintenance_config = SelfMaintenanceConfig()

        # NATS publisher for event emission
        self._nats_publisher = None

        # Tracing context
        self._trace_id: str | None = None

        # Agent pool manager for scaling
        self.pool_manager: AgentPoolManager | None = None
        self._scaling_config = ScalingConfig(
            min_replicas=config.min_agents,
            max_replicas=config.max_agents,
            scale_up_cooldown_seconds=config.scale_up_cooldown_minutes * 60,
            scale_down_cooldown_seconds=config.scale_down_cooldown_minutes * 60,
        )

        # Consciousness plugin singleton — created once in initialize(), reused in metrics loop
        self._consciousness_plugin = None
        # Agency metrics tracker — integrated into consciousness event emission
        self._agency_tracker = None

    async def initialize(self) -> None:
        """Initialize runtime components."""
        logger.info("Initializing autonomous runtime...")

        # Initialize supervisor
        self.supervisor = ActorSupervisor()
        # Note: ActorSupervisor.initialize() is a no-op, agents are initialized via AgentRuntime

        # Initialize agent runtime
        self.agent_runtime = AgentRuntime(
            supervisor=self.supervisor,
            character_configs=self.config.agent_configs,
        )
        await self.agent_runtime.initialize()

        # Load persisted state if enabled
        if self.config.state_persistence_enabled:
            await self._load_state()

        # Initialize self-maintenance scheduler
        self._maintenance_scheduler = SelfMaintenanceScheduler(
            self._maintenance_config,
            runtime_ref=self,
        )

        # Initialize agent pool manager for scaling
        self.pool_manager = AgentPoolManager(self._scaling_config)

        # Initialize consciousness plugin singleton (T03)
        await self._init_consciousness_plugin()

        # Initialize agency metrics tracker (T03)
        self._init_agency_tracker()

        logger.info("Autonomous runtime initialized")

    async def start(self) -> None:
        """Start autonomous runtime."""
        # P2-1 fix: Use timezone-aware datetime
        logger.info("Starting autonomous runtime...")
        self._running = True
        self.state.start_time = datetime.now(UTC)

        # Start initial agents
        await self._start_initial_agents()

        # Start background tasks
        tasks = [
            self._monitoring_loop(),
            self._scaling_loop(),
            self._state_persistence_loop(),
            self._metrics_collection_loop(),
            self._report_agents_loop(),
            self._maintenance_scheduler.start() if self._maintenance_scheduler else None,
        ]
        tasks = [t for t in tasks if t is not None]

        if self.config.consciousness_plugin_enabled:
            tasks.append(self._consciousness_metrics_loop())

        # Run all tasks concurrently
        await asyncio.gather(*[asyncio.create_task(t) for t in tasks])

    async def stop(self) -> None:
        """Stop autonomous runtime gracefully."""
        logger.info("Stopping autonomous runtime...")
        self._running = False
        self._shutdown_event.set()

        # Stop all agents
        if self.supervisor:
            await self.supervisor.terminate_all()

        # Save final state
        if self.config.state_persistence_enabled:
            await self._save_state()

        # Stop self-maintenance scheduler
        if self._maintenance_scheduler:
            await self._maintenance_scheduler.stop()

        logger.info("Autonomous runtime stopped")

    async def _start_initial_agents(self) -> None:
        """Start initial set of agents."""
        logger.info("Starting initial agents...")

        # Load agent configurations
        for agent_name, config_path in self.config.agent_configs.items():
            try:
                if config_path.exists():
                    await self.agent_runtime.spawn_agent(
                        agent_name,
                        str(config_path),
                    )
                    logger.info("Started agent: {agent_name}")
            except Exception:
                logger.error("Failed to start agent {agent_name}: {e}")
                self.state.total_failures += 1

        self.state.current_agents = len(self.supervisor.actors) if self.supervisor else 0

    async def _monitoring_loop(self) -> None:
        """Main monitoring loop."""
        while self._running and not self._shutdown_event.is_set():
            try:
                # Health checks
                if self.config.monitoring_enabled:
                    await self._health_checks()

                # Wait for next interval
                await asyncio.sleep(self.config.health_check_interval)

            except asyncio.CancelledError:
                break
            except Exception:
                logger.error("Monitoring loop error: {e}")
                await asyncio.sleep(5)  # Brief pause before retry

    async def _health_checks(self) -> None:
        """Perform health checks on all components."""
        # P2-1 fix: Use timezone-aware datetime
        self.state.last_health_check = datetime.now(UTC)

        # Check agent health
        if self.supervisor:
            failed_agents = []
            for agent_id, actor in self.supervisor.actors.items():
                status = actor.get_status()
                # Fix: Use ActorState enum values for comparison (uppercase)
                from heretek_swarm.actors.base import ActorState

                if status and status.state in [
                    ActorState.SUSPENDED,
                    ActorState.TERMINATED,
                    ActorState.ERROR,
                ]:
                    failed_agents.append(agent_id)

            # Auto-restart failed agents if enabled
            if failed_agents and self.config.auto_restart_enabled:
                await self._restart_agents(failed_agents)

        # Check memory usage
        await self._check_memory_usage()

        # Check API health
        await self._check_api_health()

    async def _restart_agents(self, agent_ids: list[str]) -> None:
        """Restart failed agents."""
        for agent_id in agent_ids:
            try:
                # Check restart attempts (P1-8 fix: use dedicated dict instead of __dict__)
                attempts = self._restart_attempts.get(agent_id, 0)

                if attempts >= self.config.max_restart_attempts:
                    logger.error("Max restart attempts reached for {agent_id}")
                    # Publish failure event to NATS
                    await self._publish_recovery_event(
                        agent_id,
                        "max_restart_attempts",
                        alert_type="agent.failure",
                    )
                    await self._send_alert(
                        "agent_failure",
                        {"agent_id": agent_id, "reason": "max_restart_attempts"},
                    )
                    continue

                # Terminate existing actor
                if agent_id in self.supervisor.actors:
                    await self.supervisor.terminate_actor(agent_id)

                # Restart agent
                config_path = self.config.agent_configs.get(agent_id)
                if config_path and config_path.exists():
                    await self.agent_runtime.spawn_agent(agent_id, str(config_path))
                    self.state.total_agent_restarts += 1
                    # Track restart attempt
                    self._restart_attempts[agent_id] = attempts + 1
                    logger.info("Restarted agent: {agent_id} (attempt {attempts + 1})")

                    # Publish recovery event to NATS
                    await self._publish_recovery_event(agent_id, "health_check_failure")

                # Wait before next attempt
                await asyncio.sleep(self.config.restart_delay_seconds)

            except Exception:
                logger.error("Failed to restart agent {agent_id}: {e}")
                self.state.total_failures += 1

    async def _check_memory_usage(self) -> None:
        """Check memory usage and trigger alerts."""
        try:
            import psutil

            memory = psutil.virtual_memory()
            usage_percent = memory.percent

            if usage_percent > self.config.memory_usage_threshold * 100:
                await self._send_alert(
                    "high_memory",
                    {"usage_percent": usage_percent},
                )

        except ImportError:
            logger.warning("psutil not available for memory monitoring")
        except Exception:
            logger.error("Memory check error: {e}")

    async def _check_api_health(self) -> None:
        """Check API health and latency."""
        try:
            import httpx

            start_time = time.time()
            async with httpx.AsyncClient() as client:
                await client.get(
                    f"http://{self.config.api_host}:{self.config.api_port}/api/health/live",  # Local health check  # noqa: E501
                    timeout=5.0,
                )
            latency_ms = (time.time() - start_time) * 1000

            if latency_ms > self.config.high_latency_threshold_ms:
                await self._send_alert(
                    "high_latency",
                    {"latency_ms": latency_ms},
                )

        except Exception:
            logger.error("API health check failed: {e}")
            self.state.total_failures += 1

    async def _scaling_loop(self) -> None:
        """Auto-scaling loop."""
        while self._running and not self._shutdown_event.is_set():
            try:
                if self.config.auto_scaling_enabled:
                    await self._check_scaling_conditions()

                await asyncio.sleep(60)  # Check every minute

            except asyncio.CancelledError:
                break
            except Exception:
                logger.error("Scaling loop error: {e}")
                await asyncio.sleep(5)

    async def _check_scaling_conditions(self) -> None:
        """Check if scaling is needed using AgentPoolManager."""
        if not self.supervisor or not self.pool_manager:
            return

        # Get current system metrics
        load = await self._calculate_system_load()
        current_agents = len(self.supervisor.actors)

        # Build metrics for pool manager
        metrics = {
            "cpu_usage": load * 100,
            "memory_usage": load * 100,
            "agent_pool_utilization": (current_agents / self.config.max_agents) * 100
            if self.config.max_agents > 0
            else 0,
        }

        # Evaluate scaling using pool manager
        result = await self.pool_manager.evaluate_scaling(metrics)

        if result:
            # Translate ScalingResult into actual agent operations
            await self._execute_scaling_result(result)

    async def _calculate_system_load(self) -> float:
        """Calculate current system load (CPU + memory)."""
        try:
            import psutil

            cpu = psutil.cpu_percent(interval=1)
            memory = psutil.virtual_memory().percent

            # Average CPU and memory
            return (cpu + memory) / 200

        except ImportError:
            return 0.5  # Default moderate load
        except Exception:
            logger.error("Load calculation error: {e}")
            return 0.5

    async def _scale_up(self) -> None:
        """Scale up by adding more agents."""
        # P2-1 fix: Use timezone-aware datetime
        # Check cooldown
        if self._last_scale_up_time:
            time_since = datetime.now(UTC) - self._last_scale_up_time
            if time_since.total_seconds() < self.config.scale_up_cooldown_minutes * 60:
                return

        current_agents = len(self.supervisor.actors) if self.supervisor else 0
        if current_agents >= self.config.max_agents:
            return

        # Add new agent
        available_agents = [
            name
            for name in self.config.agent_configs
            if name not in (self.supervisor.actors if self.supervisor else {})
        ]

        if available_agents:
            agent_name = available_agents[0]
            config_path = self.config.agent_configs[agent_name]

            try:
                # P2-1 fix: Use timezone-aware datetime
                await self.agent_runtime.spawn_agent(agent_name, str(config_path))
                self.state.last_scale_event = datetime.now(UTC)
                self._last_scale_up_time = datetime.now(UTC)
                logger.info("Scaled up: Started agent {agent_name}")
            except Exception:
                logger.error("Failed to scale up: {e}")

    async def _scale_down(self) -> None:
        """Scale down by removing idle agents."""
        # Check cooldown and minimum uptime
        if self._last_scale_down_time:
            time_since = datetime.now(UTC) - self._last_scale_down_time
            if time_since.total_seconds() < self.config.scale_down_cooldown_minutes * 60:
                return

        current_agents = len(self.supervisor.actors) if self.supervisor else 0
        if current_agents <= self.config.min_agents:
            return

        # Find idle agent to remove
        idle_agent = await self._find_idle_agent()
        if idle_agent:
            try:
                # P2-1 fix: Use timezone-aware datetime
                await self.supervisor.terminate_actor(idle_agent)
                self.state.last_scale_event = datetime.now(UTC)
                self._last_scale_down_time = datetime.now(UTC)
                logger.info("Scaled down: Terminated agent {idle_agent}")
            except Exception:
                logger.error("Failed to scale down: {e}")

    async def _execute_scaling_result(self, result: ScalingResult) -> None:
        """
        Execute scaling result from AgentPoolManager.

        Translates ScalingResult into actual agent_runtime.spawn_agent
        or supervisor.terminate_actor calls.
        """
        if result.action == ScalingAction.SCALE_UP:
            await self._execute_scale_up(result)
        elif result.action == ScalingAction.SCALE_DOWN:
            await self._execute_scale_down(result)
        # NO_OP: Do nothing

    async def _execute_scale_up(self, result: ScalingResult) -> None:
        """Execute scale up from pool manager result."""
        # Check cooldown (pool manager already checked, but we add runtime-level protection)
        if self._last_scale_up_time:
            time_since = datetime.now(UTC) - self._last_scale_up_time
            if time_since.total_seconds() < self.config.scale_up_cooldown_minutes * 60:
                logger.debug(
                    "scale_up_cooldown_active", time_since_seconds=time_since.total_seconds()
                )
                return

        current_agents = len(self.supervisor.actors) if self.supervisor else 0
        agents_to_add = result.agents_added

        for i in range(agents_to_add):
            if current_agents >= self.config.max_agents:
                break

            # Find available agent config
            available_agents = [
                name
                for name in self.config.agent_configs
                if name not in (self.supervisor.actors if self.supervisor else {})
            ]

            if not available_agents:
                logger.warning("no_available_agent_configs_for_scale_up")
                break

            agent_name = available_agents[0]
            config_path = self.config.agent_configs[agent_name]

            try:
                # Register instance in pool manager
                instance_id = f"{agent_name}-{current_agents + i + 1}"
                self.pool_manager.register_instance(instance_id)

                # Spawn agent
                await self.agent_runtime.spawn_agent(agent_name, str(config_path))
                self.state.last_scale_event = datetime.now(UTC)
                self._last_scale_up_time = datetime.now(UTC)

                logger.info(
                    "pool_manager_scale_up_executed",
                    agent_name=agent_name,
                    instance_id=instance_id,
                )
            except Exception:
                logger.error("Failed to spawn agent during scale up: {e}")

    async def _execute_scale_down(self, result: ScalingResult) -> None:
        """Execute scale down from pool manager result."""
        # Check cooldown (pool manager already checked, but we add runtime-level protection)
        if self._last_scale_down_time:
            time_since = datetime.now(UTC) - self._last_scale_down_time
            if time_since.total_seconds() < self.config.scale_down_cooldown_minutes * 60:
                logger.debug(
                    "scale_down_cooldown_active", time_since_seconds=time_since.total_seconds()
                )
                return

        current_agents = len(self.supervisor.actors) if self.supervisor else 0
        agents_to_remove = result.agents_removed

        # Find idle agents to remove
        for _ in range(agents_to_remove):
            if current_agents <= self.config.min_agents:
                break

            idle_agent = await self._find_idle_agent()
            if not idle_agent:
                # If no idle agent found, find any non-critical agent
                idle_agent = self._find_any_removable_agent()

            if idle_agent:
                try:
                    # Terminate agent
                    await self.supervisor.terminate_actor(idle_agent)
                    self.state.last_scale_event = datetime.now(UTC)
                    self._last_scale_down_time = datetime.now(UTC)

                    logger.info(
                        "pool_manager_scale_down_executed",
                        agent_id=idle_agent,
                    )
                except Exception:
                    logger.error("Failed to terminate agent during scale down: {e}")

    def _find_any_removable_agent(self) -> str | None:
        """Find any agent that can be removed (fallback when no idle agents)."""
        if not self.supervisor:
            return None

        # Find an agent that isn't critical (any agent other than coordinator)
        for agent_id in self.supervisor.actors:
            if agent_id != "coordinator":
                return agent_id

        return None

    def _parse_last_activity(self, status: Any) -> datetime | None:
        """Parse last_activity timestamp from status object."""
        if not status or not status.last_activity:
            return None
        try:
            last_activity_str = status.last_activity
            if isinstance(last_activity_str, str):
                return datetime.fromisoformat(last_activity_str.replace("Z", "+00:00"))
            return last_activity_str
        except (ValueError, TypeError):
            return None

    def _is_agent_idle(self, status: Any) -> bool:
        """Check if agent has been idle long enough to be removed."""
        last_activity_dt = self._parse_last_activity(status)
        if last_activity_dt is None:
            return False
        idle_time = datetime.now(UTC) - last_activity_dt
        return idle_time.total_seconds() > self.config.min_uptime_before_scale_down * 60

    async def _find_idle_agent(self) -> str | None:
        """Find an idle agent to scale down."""
        if not self.supervisor:
            return None

        for agent_id, actor in self.supervisor.actors.items():
            status = actor.get_status()
            if status and self._is_agent_idle(status):
                return agent_id
        return None

    async def _state_persistence_loop(self) -> None:
        """State persistence loop."""
        while self._running and not self._shutdown_event.is_set():
            try:
                if self.config.state_persistence_enabled:
                    await self._save_state()

                await asyncio.sleep(self.config.state_backup_interval)

            except asyncio.CancelledError:
                break
            except Exception:
                logger.error("State persistence error: {e}")
                await asyncio.sleep(5)

    async def _save_state(self) -> None:
        """Save current state to disk."""
        # P2-1 fix: Use timezone-aware datetime
        state_file = Path(self.config.log_directory) / "runtime_state.json"

        state_data = {
            "timestamp": datetime.now(UTC).isoformat(),
            "uptime_seconds": self.state.uptime_seconds,
            "total_agent_restarts": self.state.total_agent_restarts,
            "total_failures": self.state.total_failures,
            "current_agents": self.state.current_agents,
        }

        try:
            state_file.parent.mkdir(parents=True, exist_ok=True)
            with open(state_file, "w") as f:  # noqa: ASYNC230,PTH123
                import json

                json.dump(state_data, f, indent=2)
        except Exception:
            logger.error("Failed to save state: {e}")

    async def _load_state(self) -> None:
        """Load saved state from disk."""
        state_file = Path(self.config.log_directory) / "runtime_state.json"

        if not state_file.exists():
            return

        try:
            with open(state_file) as f:  # noqa: ASYNC230,PTH123
                import json

                state_data = json.load(f)

            self.state.total_agent_restarts = state_data.get("total_agent_restarts", 0)
            self.state.total_failures = state_data.get("total_failures", 0)

            logger.info("Loaded state from {state_file}")
        except Exception:
            logger.error("Failed to load state: {e}")

    async def _metrics_collection_loop(self) -> None:
        """Metrics collection loop."""
        while self._running and not self._shutdown_event.is_set():
            try:
                await self._collect_metrics()

                await asyncio.sleep(self.config.metrics_collection_interval)

            except asyncio.CancelledError:
                break
            except Exception:
                logger.error("Metrics collection error: {e}")
                await asyncio.sleep(5)

    async def _collect_metrics(self) -> None:
        """Collect and store metrics."""
        if not self.supervisor:
            return

        # Collect agent metrics
        agent_metrics = []
        for agent_id, actor in self.supervisor.actors.items():
            status = actor.get_status()
            if status:
                agent_metrics.append(
                    {
                        "agent_id": agent_id,
                        "message_count": status.message_count,
                        "error_count": status.error_count,
                        "uptime_seconds": status.uptime_seconds,
                    }
                )

        # Store metrics
        # P2-1 fix: Use timezone-aware datetime
        self.state.uptime_seconds = (datetime.now(UTC) - self.state.start_time).total_seconds()

        logger.info("Collected metrics for {len(agent_metrics)} agents")

    async def _report_agents_loop(self) -> None:
        """Report agent statuses to the API server periodically."""
        import os as _os

        api_host = self.config.api_host or _os.getenv("HERETEK_API_HOST", "heretek-api")
        api_port = self.config.api_port or 8000
        report_interval = 30  # seconds

        while self._running and not self._shutdown_event.is_set():
            try:
                await self._report_agents_to_api(api_host, api_port)
            except Exception:
                logger.warning("Failed to report agents to API: {e}")

            await asyncio.sleep(report_interval)

    async def _report_agents_to_api(self, api_host: str, api_port: int) -> None:
        """Send current agent statuses to the API server."""
        import httpx

        if not self.supervisor:
            return

        agents = []
        for agent_id, actor in self.supervisor.actors.items():
            try:
                status = actor.get_status()
                agents.append(
                    {
                        "agent_id": agent_id,
                        "agent_type": getattr(actor, "actor_type", "unknown"),
                        "state": status.state.value if status else "unknown",
                        "message_count": status.message_count if status else 0,
                        "error_count": status.error_count if status else 0,
                        "mailbox_size": status.mailbox_size if status else 0,
                        "last_activity": status.last_activity if status else None,
                        "uptime_seconds": status.uptime_seconds if status else 0.0,
                    }
                )
            except Exception:
                logger.debug("Failed to get status for agent {agent_id}: {e}")

        payload = {
            "runtime_id": "autonomous",
            "agents": agents,
            "total_agents": len(agents),
            "uptime_seconds": (datetime.now(UTC) - self.state.start_time).total_seconds(),
        }

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                await client.post(
                    f"http://{api_host}:{api_port}/api/autonomous/agents",
                    json=payload,
                )
        except httpx.ConnectError:
            logger.debug("API not available at {api_host}:{api_port}, skipping report")
        except Exception:
            logger.warning("Failed to report agents to API: {e}")

    async def _consciousness_metrics_loop(self) -> None:
        """Consciousness metrics collection loop."""
        while self._running and not self._shutdown_event.is_set():
            try:
                await self._collect_consciousness_metrics()

                await asyncio.sleep(self.config.consciousness_metrics_interval)

            except asyncio.CancelledError:
                break
            except Exception:
                logger.error("Consciousness metrics error: {e}")
                await asyncio.sleep(5)

    async def _init_consciousness_plugin(self) -> None:
        """Initialize the consciousness plugin singleton."""
        try:
            from heretek_swarm.plugins.consciousness_enhanced import EnhancedConsciousnessPlugin

            self._consciousness_plugin = EnhancedConsciousnessPlugin()
            await self._consciousness_plugin.initialize()
            logger.info("consciousness_plugin_initialized")
        except ImportError:
            logger.warning("ConsciousnessEnhancedPlugin not available: {e}")
            self._consciousness_plugin = None
        except Exception:
            logger.error("Failed to initialize consciousness plugin: {e}")
            self._consciousness_plugin = None

    def _init_agency_tracker(self) -> None:
        """Initialize the agency metrics tracker."""
        try:
            self._agency_tracker = AgencyMetricsTracker()
            logger.info("agency_metrics_tracker_initialized")
        except Exception:
            logger.error("Failed to initialize agency tracker: {e}")
            self._agency_tracker = None

    async def _collect_consciousness_metrics(self) -> None:
        """Collect and emit consciousness metrics with agency tracking."""
        if not self._consciousness_plugin:
            logger.debug("consciousness_plugin_unavailable_skip")
            return

        try:
            # Get statistics and log
            stats = self._consciousness_plugin.get_statistics()
            logger.info(
                "Consciousness stats: "  # noqa: G004
                f"agents={stats.get('total_agents', 0)}, "
                f"avg_phi={stats.get('iit_average_phi', 0):.4f}, "
                f"conscious={stats.get('conscious_agents', 0)}"
            )

            # Check for consciousness drop
            if stats.get("conscious_agents", 0) > 0:
                consciousness_ratio = stats["conscious_agents"] / stats["total_agents"]
                if consciousness_ratio < self.config.consciousness_drop_threshold:
                    await self._send_alert(
                        "consciousness_drop",
                        {"ratio": consciousness_ratio},
                    )

            # Emit consciousness events to NATS if publisher is available
            if self._nats_publisher:
                await self._consciousness_plugin.emit_consciousness_events(self._nats_publisher)

            # Integrate agency metrics (T03): snapshot and record per-agent metrics
            if self._agency_tracker:
                snapshot = self._agency_tracker.get_current_snapshot()
                # For each agent tracked by consciousness plugin, sync to agency tracker
                for agent_id in stats.get("total_agents", 0):
                    # Get metrics from consciousness plugin for this agent
                    agent_data = self._consciousness_plugin.get_agent_metrics(agent_id)
                    if agent_data:
                        from heretek_swarm.consciousness.agency_metrics import (
                            AgentAgencyMetrics,
                        )

                        # Map consciousness metrics to agency metrics
                        agency_metrics = AgentAgencyMetrics(
                            agent_id=agent_id,
                            autonomy_score=agent_data.get("gwt_score", 0.5),
                            agency_score=agent_data.get("composite_score", 0.5),
                            self_determination_index=agent_data.get("fep_free_energy", 0.5),
                            autonomous_action_ratio=agent_data.get("gwt_score", 0.5),
                            resource_autonomy=agent_data.get("composite_score", 0.5),
                            prime_directive_compliance=agent_data.get("composite_score", 0.5),
                        )
                        self._agency_tracker.record_agent_metrics(agency_metrics)

                logger.debug(
                    "agency_tracker_synced",
                    agents=stats.get("total_agents", 0),
                    snapshot_timestamp=snapshot.timestamp,
                )

        except Exception:
            logger.error("Consciousness metrics collection error: {e}")

    async def _publish_recovery_event(
        self,
        agent_id: str,
        reason: str,
        alert_type: str | None = None,
    ) -> None:
        """Publish recovery event to NATS swarm.events topic.

        Args:
            agent_id: The agent that was restarted
            reason: The reason for the restart
            alert_type: Optional alert type for failure events (e.g., "agent.failure")
        """
        # Generate or use existing correlation_id for tracing
        import uuid

        from heretek_swarm.infrastructure.nats.publisher import (
            EventPriority,
            SwarmEvent,
        )

        correlation_id = str(uuid.uuid4())

        # Determine event type based on context
        event_type = alert_type if alert_type else "agent.recovery"

        event = SwarmEvent(
            event_type=event_type,
            source_agent=agent_id,
            payload={
                "agent_id": agent_id,
                "reason": reason,
                "timestamp": datetime.now(UTC).isoformat(),
            },
            priority=EventPriority.HIGH,
            correlation_id=correlation_id,
            trace_id=self._trace_id,
        )

        # Publish event
        if self._nats_publisher:
            await self._nats_publisher.publish_event(event)

    async def _send_alert(self, alert_type: str, data: dict[str, Any]) -> None:
        """Send alert notification."""
        # P2-1 fix: Use timezone-aware datetime
        # Check cooldown
        last_time = self._last_alert_time.get(alert_type)
        if last_time:
            time_since = datetime.now(UTC) - last_time
            if time_since.total_seconds() < 300:  # 5 minute cooldown
                return

        # P2-1 fix: Use timezone-aware datetime
        self._last_alert_time[alert_type] = datetime.now(UTC)

        logger.warning("Alert: {alert_type}", data=data)

        # Send to configured channels
        if self.config.alert_config.slack_channel:
            await self._send_slack_alert(alert_type, data)

        if self.config.alert_config.discord_channel:
            await self._send_discord_alert(alert_type, data)

        if self.config.alert_config.email_enabled:
            await self._send_email_alert(alert_type, data)

    async def _send_slack_alert(self, alert_type: str, data: dict[str, Any]) -> None:
        """Send alert to Slack."""
        # P1-9 fix: Specific ImportError handling
        try:
            from heretek_swarm.integrations.slack_bot import SlackBot
        except ImportError:
            logger.warning("SlackBot not available: {e}")
            return

        try:
            bot = SlackBot(
                token=os.getenv("SLACK_BOT_TOKEN"),
                signing_secret=os.getenv("SLACK_SIGNING_SECRET"),
                agent_id="runtime_monitor",
                supervisor=self.supervisor,
            )

            message = f"🚨 Alert: {alert_type}\n"
            message += f"```json\n{data}\n```"

            await bot.send_notification(
                channel=self.config.alert_config.slack_channel,
                message=message,
            )

        except Exception:
            logger.error("Failed to send Slack alert: {e}")

    async def _send_discord_alert(self, alert_type: str, data: dict[str, Any]) -> None:
        """Send alert to Discord."""
        # P1-9 fix: Specific ImportError handling
        try:
            from heretek_swarm.integrations.discord_bot import DiscordBot
        except ImportError:
            logger.warning("DiscordBot not available: {e}")
            return

        try:
            DiscordBot(
                token=os.getenv("DISCORD_BOT_TOKEN"),
                agent_id="runtime_monitor",
                prefix="!",
                supervisor=self.supervisor,
            )

            message = f"🚨 Alert: {alert_type}\n"
            message += f"```json\n{data}\n```"

            # Note: Discord bot would need channel reference
            logger.info("Discord alert prepared: {alert_type}")

        except Exception:
            logger.error("Failed to send Discord alert: {e}")

    async def _send_email_alert(self, alert_type: str, data: dict[str, Any]) -> None:
        """Send alert via email."""
        try:
            import smtplib
            from email.mime.multipart import MIMEMultipart
            from email.mime.text import MIMEText

            msg = MIMEMultipart()
            msg["From"] = os.getenv("SMTP_FROM", "noreply@heretek.swarm")
            msg["To"] = ", ".join(self.config.alert_config.email_recipients)
            msg["Subject"] = f"Heretek Swarm Alert: {alert_type}"

            # P2-1 fix: Use timezone-aware datetime
            body = f"Alert Type: {alert_type}\n\n"
            body += f"Data:\n{data}\n\n"
            body += f"Timestamp: {datetime.now(UTC).isoformat()}"

            msg.attach(MIMEText(body, "plain"))

            with smtplib.SMTP(
                os.getenv("SMTP_HOST", "localhost"),
                int(os.getenv("SMTP_PORT", "25")),
            ) as server:
                if os.getenv("SMTP_USERNAME"):
                    server.login(
                        os.getenv("SMTP_USERNAME"),
                        os.getenv("SMTP_PASSWORD"),
                    )
                server.send_message(msg)

            logger.info("Email alert sent: {alert_type}")

        except Exception:
            logger.error("Failed to send email alert: {e}")

    def get_status(self) -> dict[str, Any]:
        """Get current runtime status."""
        return {
            "running": self._running,
            "uptime_seconds": self.state.uptime_seconds,
            "total_agent_restarts": self.state.total_agent_restarts,
            "total_failures": self.state.total_failures,
            "current_agents": self.state.current_agents,
            "last_health_check": self.state.last_health_check.isoformat()
            if self.state.last_health_check
            else None,
            "last_scale_event": self.state.last_scale_event.isoformat()
            if self.state.last_scale_event
            else None,
        }


async def start_autonomous_runtime(config: AutonomousRuntimeConfig) -> AutonomousRuntime:
    """
    Start autonomous runtime with signal handling.

    Args:
        config: Runtime configuration

    Returns:
        AutonomousRuntime instance
    """
    runtime = AutonomousRuntime(config)
    await runtime.initialize()

    # Setup signal handlers
    def signal_handler(signum, frame):
        logger.info("Received signal {signum}, shutting down...")
        asyncio.create_task(runtime.stop())  # noqa: RUF006

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    # Start runtime
    await runtime.start()

    return runtime
