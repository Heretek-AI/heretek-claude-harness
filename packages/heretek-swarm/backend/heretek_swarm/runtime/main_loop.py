"""
Autonomous Main Loop - 24/7 Operation Entry Point for Heretek Swarm

This is the primary entry point for autonomous operation.
Wires together all components into a cohesive autonomous system:
- 23 agents across 6 tiers
- Communication channels via NATS/A2A
- MCP tools registry
- Memory and RAG systems
- MAKER consensus engine
- Health monitoring and auto-recovery

Based on architecture from:
- AUTONOMOUS_WORKFLOW_DESIGN-QWEN.md
- AUTONOMOUS_WORKFLOW_DESIGN-GLM5.md
- AUTONOMOUS_WORKFLOW_DESIGN-MINIMAX.md
"""

import asyncio
import contextlib
import json
import os
import time
import uuid
from datetime import UTC, datetime
from typing import Any

import structlog

from heretek_swarm.actors.stubs import StubEventMesh
from heretek_swarm.actors.supervisor import ActorSupervisor
from heretek_swarm.api.autonomous import push_analysis_record
from heretek_swarm.api.consciousness import get_consciousness_plugin
from heretek_swarm.channels.registry import ChannelRegistry, GroupRegistry
from heretek_swarm_core.consensus.consensus_coordinator import ConsensusCoordinator
from heretek_swarm_core.consensus.domain_selector import DomainSelector
from heretek_swarm_core.consensus.election_manager import ElectionManager
from heretek_swarm_core.consensus.maker import MAKERConsensus
from heretek_swarm.gateway.nats_event_mesh import NATSEventMeshWithJetStream
from heretek_swarm.goals.pipeline import run_goal_cycle
from heretek_swarm.goals.store import FileGoalStore
from heretek_swarm_core.llm.model_garage import ModelGarage
from heretek_swarm_core.memory.cognee_reader import CogneeMemoryReader
from heretek_swarm_core.memory.cognee_writer import CogneeMemoryWriter
from heretek_swarm.rag.cognee_rag import CogneeRAGRetriever, get_rag_retriever
from heretek_swarm.routing.model_router import set_global_model_garage
from heretek_swarm.runtime.actor_orchestrator import ActorOrchestrator
from heretek_swarm.runtime.deliberation_orchestrator import DeliberationOrchestrator
from heretek_swarm.runtime.registry_enhanced import get_enhanced_registry
from heretek_swarm.runtime.steward_pulse import run_steward_pulse
from heretek_swarm.tools.mcp_tools import CoreMCPTools

logger = structlog.get_logger(__name__)


class AutonomousSwarm:
    """
    Main entry point for autonomous 24/7 swarm operation.

    Coordinates all components into a unified autonomous loop:
    - Initializes all 23 agents
    - Sets up communication channels
    - Starts health monitoring
    - Runs continuous task processing

    Attributes:
        config: Configuration dictionary
        supervisor: Actor supervisor for health monitoring
        event_mesh: NATS event mesh for communication
        _cognee_reader: Cognee read client for graph-augmented retrieval
        _cognee_writer: Cognee write client for knowledge ingestion
        rag: RAG pipeline for knowledge retrieval
        consensus: MAKER consensus engine
        channel_registry: Communication channel registry
        mcp_tools: MCP tools registry
    """

    def __init__(self, config: dict[str, Any] | None = None, no_infra: bool = False):
        self._no_infra = no_infra
        if no_infra:
            self.config = config or {}
        else:
            self.config = config or self._default_config()

        # Core components (initialized in initialize())
        self.supervisor: ActorSupervisor | None = None
        self.event_mesh: NATSEventMeshWithJetStream | None = None
        self._cognee_reader: CogneeMemoryReader | None = None
        self._cognee_writer: CogneeMemoryWriter | None = None
        self.rag: CogneeRAGRetriever | None = None
        self.consensus: MAKERConsensus | None = None
        self.channel_registry: ChannelRegistry | None = None
        self.group_registry: GroupRegistry | None = None
        self.mcp_tools: CoreMCPTools | None = None
        self.model_garage: ModelGarage | None = None

        # State
        self._running = False
        self._tasks: list[asyncio.Task] = []
        self._health_check_interval = self.config.get("health_check_interval", 30)
        self._loop_interval = self.config.get("loop_interval", 1)
        self._consciousness_interval = self.config.get("consciousness_interval", 5)
        self._memory_maintenance_interval = self.config.get("memory_maintenance_interval", 300)
        self._scaling_interval = self.config.get("scaling_interval", 60)

        # S04: Periodic analysis cycle counter — triggers Metis/Empath every 30 cycles
        self._analysis_cycle_count = 0

        # S02: Cooldown timer for event-driven analysis dispatch
        self._cooldown_until: float | None = None  # epoch seconds
        self._pending_event_conditions: list[dict[str, Any]] = []

        # S01: NATS response queue for periodic analysis results
        self._response_queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue()
        self._latest_analysis: dict[str, Any] = {}

        # S05: In-memory analysis record buffer (capped) for API consumption
        self._analysis_records: list[dict[str, Any]] = []
        self._last_chronos_operations: list[dict[str, Any]] = []
        self._mediation_dispatched: bool = False
        self._max_analysis_records: int = 1000

        # S03: RAFT election manager (initialized in initialize() unless --no-infra)
        self._election_manager = None  # ElectionManager | None

        # M011: Goal pipeline store (initialized on first use in --no-infra path)
        self._goal_store: FileGoalStore | None = None

        # Orchestrators — created in __init__, wired during initialize()
        # DeliberationOrchestrator handles triad, MAKER consensus, and routed tasks
        self._deliberation = DeliberationOrchestrator(
            supervisor=self.supervisor,
            consensus=self.consensus,
            config=self.config,
        )
        # ActorOrchestrator handles agent spawning and channel subscriptions
        self._actor_orch = ActorOrchestrator(
            supervisor=self.supervisor,
            mcp_tools=self.mcp_tools,
            channel_registry=self.channel_registry,
            event_mesh=self.event_mesh,
        )

    def _default_config(self) -> dict[str, Any]:
        """Default configuration for autonomous swarm."""
        database_url = os.getenv("DATABASE_URL")
        if not database_url:
            raise RuntimeError(
                "DATABASE_URL is required. Set it to postgresql://user:pass@host:port/db "
                "or use docker compose."
            )

        nats_url = os.getenv("HERETEK_NATS_URL")
        if not nats_url:
            raise RuntimeError(
                "HERETEK_NATS_URL is required. Set it to nats://host:port "
                "or use docker compose."
            )
        nats_servers = [s.strip() for s in nats_url.split(",")]

        return {
            "nats_servers": nats_servers,
            "health_check_interval": 30,
            "loop_interval": 1,
            "consciousness_interval": 5,
            "memory_maintenance_interval": 300,
            "scaling_interval": 60,
            "ephemeral": {"ttl_seconds": 3600},
            "persistent": {
                "connection_string": database_url,
            },
            "rag": {
                "embedding_provider": "openai",
                "collection_name": "heretek_documents",
            },
            "consensus": {
                "ahead_by_k": 2,
                "min_votes": 3,
                "red_flag_threshold": 0.3,
            },
        }

    async def initialize(self) -> None:
        """Initialize all swarm components.

        Each component is wrapped in an independent try/except so a failure
        in one step (e.g. NATS unavailable) does not crash the entire swarm.
        """
        logger.info("initializing_autonomous_swarm", no_infra=self._no_infra)

        # Auto-enable OTel tracing when OTLP endpoint is configured
        if os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT"):
            try:
                from heretek_swarm.infrastructure.otel.tracing import (
                    TracingConfig,
                    init_tracing,
                )

                config = TracingConfig(exporter="otlp")
                init_tracing(config)
                logger.info("otel_tracing_auto_enabled")
            except Exception as exc:
                logger.warning("otel_tracing_auto_enable_failed", error=str(exc))

        if self._no_infra:
            await self._initialize_no_infra()
            return

        await self._initialize_channel_registry()
        await self._initialize_memory()
        await self._initialize_rag()
        await self._initialize_consensus()
        await self._initialize_event_mesh()
        await self._initialize_jetstream()
        await self._initialize_mcp_tools()
        await self._initialize_supervisor()
        await self._initialize_model_garage()
        await self._initialize_election_manager()
        self._rewire_orchestrator_refs()
        self._thread_event_mesh_to_supervisor()
        await self._spawn_all_actors()
        await self._create_per_agent_streams()
        await self._setup_channel_subscriptions()

        logger.info("autonomous_swarm_fully_initialized")

    async def _initialize_no_infra(self) -> None:
        """Initialize in-memory components when --no-infra is set."""
        logger.warning("infra_skipped_no_infra_flag")
        self.channel_registry = ChannelRegistry()
        self.group_registry = GroupRegistry(self.channel_registry)
        self.rag = get_rag_retriever()
        consensus_config = self.config.get("consensus", {})
        self.consensus = MAKERConsensus(
            ahead_by_k=consensus_config.get("ahead_by_k", 2),
            min_votes=consensus_config.get("min_votes", 3),
            confidence_threshold=consensus_config.get("red_flag_threshold", 0.3),
        )
        self.mcp_tools = CoreMCPTools(
            cognee_reader=None,
            cognee_writer=None,
            rag_retriever=self.rag,
            consensus_engine=self.consensus,
            event_mesh=None,
        )
        from heretek_swarm.mcp.bridge import sync_mcp_registries
        bridged = sync_mcp_registries(self.mcp_tools)
        logger.info("mcp_bridge_applied", tool_count=bridged)
        self.model_garage = ModelGarage()
        await self.model_garage.initialize()
        set_global_model_garage(self.model_garage)
        logger.info("model_garage_initialized")
        self._election_manager = None
        logger.info("election_manager_skipped_no_infra")
        self.supervisor = ActorSupervisor(
            health_check_interval=self._health_check_interval, auto_restart=True, max_restarts=5
        )
        self.event_mesh = StubEventMesh()
        await self.event_mesh.connect()
        self.supervisor._event_mesh = self.event_mesh
        self._actor_orch._supervisor = self.supervisor
        self._actor_orch._mcp_tools = self.mcp_tools
        self._actor_orch._channel_registry = self.channel_registry
        self._actor_orch._event_mesh = self.event_mesh
        self._deliberation._supervisor = self.supervisor
        self._deliberation._consensus = self.consensus
        await self._actor_orch.spawn_all_actors()
        logger.info("autonomous_swarm_fully_initialized", event_mesh_type="StubEventMesh")

    async def _initialize_channel_registry(self) -> None:
        """Wire the channel + group registries.

        Thin delegate to
        :func:`heretek_swarm.runtime.initializers.channel_registry.initialize_channel_registry`
        (Phase 2.6 of PLAN.md).
        """
        await _init_channel_registry(self)

    async def _initialize_memory(self) -> None:
        """Wire the cognee memory reader + writer.

        Thin delegate to
        :func:`heretek_swarm.runtime.initializers.memory.initialize_memory`
        (Phase 2.6 of PLAN.md).
        """
        await _init_memory(self)

    async def _initialize_rag(self) -> None:
        """Wire the cognee RAG retriever.

        Thin delegate to
        :func:`heretek_swarm.runtime.initializers.rag.initialize_rag`
        (Phase 2.6 of PLAN.md).
        """
        await _init_rag(self)

    async def _initialize_consensus(self) -> None:
        """Wire the MAKERConsensus engine.

        Thin delegate to
        :func:`heretek_swarm.runtime.initializers.consensus.initialize_consensus`
        (Phase 2.6 of PLAN.md).
        """
        await _init_consensus_engine(self)

    async def _initialize_event_mesh(self) -> None:
        """Thin delegate to :func:`heretek_swarm.runtime.initializers.event_mesh.initialize_event_mesh`."""
        from heretek_swarm.runtime.initializers.event_mesh import initialize_event_mesh
        await initialize_event_mesh(self)

    async def _initialize_jetstream(self) -> None:
        """Thin delegate to :func:`heretek_swarm.runtime.initializers.jetstream.initialize_jetstream`."""
        from heretek_swarm.runtime.initializers.jetstream import initialize_jetstream
        await initialize_jetstream(self)

    async def _initialize_mcp_tools(self) -> None:
        """Thin delegate to :func:`heretek_swarm.runtime.initializers.mcp_tools.initialize_mcp_tools`."""
        from heretek_swarm.runtime.initializers.mcp_tools import initialize_mcp_tools
        await initialize_mcp_tools(self)

    async def _initialize_supervisor(self) -> None:
        """Thin delegate to :func:`heretek_swarm.runtime.initializers.supervisor.initialize_supervisor`."""
        from heretek_swarm.runtime.initializers.supervisor import initialize_supervisor
        await initialize_supervisor(self)

    async def _initialize_model_garage(self) -> None:
        """Thin delegate to :func:`heretek_swarm.runtime.initializers.model_garage.initialize_model_garage`."""
        from heretek_swarm.runtime.initializers.model_garage import initialize_model_garage
        await initialize_model_garage(self)

    async def _initialize_election_manager(self) -> None:
        """Thin delegate to :func:`heretek_swarm.runtime.initializers.election_manager.initialize_election_manager`."""
        from heretek_swarm.runtime.initializers.election_manager import (
            initialize_election_manager,
        )
        await initialize_election_manager(self)

    def _rewire_orchestrator_refs(self) -> None:
        """Post-hoc wiring of orchestrator dependencies.

        Thin delegate to
        :func:`heretek_swarm.runtime.wiring.wire_orchestrators`
        (Phase 2.2 of PLAN.md). The audit's exit criterion is to
        move from post-hoc attribute assignment to constructor
        injection; when each orchestrator accepts its supervisor
        / mcp_tools / event_mesh through ``__init__``, this
        method becomes a no-op.
        """
        _wire_orchestrators_ext(self)

    def _thread_event_mesh_to_supervisor(self) -> None:
        """Thread the event mesh into the supervisor.

        Thin delegate to
        :func:`heretek_swarm.runtime.wiring.thread_event_mesh_to_supervisor`
        (Phase 2.2 of PLAN.md).
        """
        _thread_event_mesh_to_supervisor_ext(self)

    async def _spawn_all_actors(self) -> None:
        try:
            await self._actor_orch.spawn_all_actors()
            logger.info("all_actors_spawned")
            from heretek_swarm.actors.supervisor import get_supervisor
            get_supervisor().actors.update(self.supervisor.actors)
            logger.info("actor_registry_bridged", total_actors=len(self.supervisor.actors))
        except Exception as exc:
            logger.warning("actor_spawn_init_failed", error=str(exc))

    async def _create_per_agent_streams(self) -> None:
        try:
            if self.event_mesh is not None and self.event_mesh.jetstream_enabled:
                agent_ids = list(self.supervisor.actors.keys()) if self.supervisor else []
                stream_result = await self.event_mesh.ensure_agent_streams(agent_ids)
                logger.info(
                    "per_agent_jetstream_streams_created",
                    created=stream_result.get("created", 0),
                    skipped=stream_result.get("skipped", 0),
                )
            else:
                logger.warning(
                    "per_agent_streams_skipped",
                    message="No event mesh or JetStream not enabled",
                )
        except Exception as exc:
            logger.warning("per_agent_streams_init_failed", error=str(exc))

    async def _setup_channel_subscriptions(self) -> None:
        try:
            await self._actor_orch.setup_channel_subscriptions()
            logger.info("channel_subscriptions_configured")
        except Exception as exc:
            logger.warning("channel_subscriptions_init_failed", error=str(exc))

    async def run_deliberation(
        self,
        prompt: str,
        timeout: int = 120,
    ) -> dict[str, Any]:
        """Run a triad deliberation — delegates to DeliberationOrchestrator."""
        return await self._deliberation.run_deliberation(prompt, timeout)

    async def run_consensus(
        self,
        question: str,
        timeout: float = 120,
        max_rounds: int = 3,
    ) -> dict[str, Any]:
        """Run MAKER consensus — delegates to DeliberationOrchestrator."""
        return await self._deliberation.run_consensus(question, timeout, max_rounds)

    async def run_routed_task(
        self,
        agent_name: str,
        task_type: str,
        task_data: dict[str, Any],
        timeout: int = 30,
    ) -> dict[str, Any]:
        """Route a task to a specific agent — delegates to DeliberationOrchestrator."""
        return await self._deliberation.run_routed_task(agent_name, task_type, task_data, timeout)

    def get_startup_status(self) -> dict[str, str]:
        """Return startup status of each component for diagnostics."""
        status: dict[str, str] = {}
        self._add_component_status(status, "Channels", self.channel_registry)
        self._add_component_status(status, "Cognee Reader", self._cognee_reader)
        self._add_component_status(status, "Cognee Writer", self._cognee_writer)
        self._add_component_status(status, "RAG", self.rag)
        self._add_component_status(status, "Consensus", self.consensus)
        self._add_component_status(status, "Event Mesh", self.event_mesh, "Connected")
        self._add_component_status(status, "MCP Tools", self.mcp_tools)
        self._add_agent_status(status)
        return status

    @staticmethod
    def _add_component_status(
        status: dict[str, str], name: str, component: object, label: str = "Initialized"
    ) -> None:
        status[name] = f"✓ {label}" if component is not None else "✗ Unavailable"

    def _add_agent_status(self, status: dict[str, str]) -> None:
        if self.supervisor is not None:
            agent_count = len(self.supervisor.actors) if hasattr(self.supervisor, "actors") else 0
            status["Agents"] = f"✓ {agent_count} spawned"
        else:
            status["Agents"] = "✗ Unavailable"

    async def run(self) -> None:
        """Main autonomous loop - runs 24/7."""
        logger.info("starting_autonomous_loop")
        self._running = True

        # Gate consciousness loop behind CONSCIOUSNESS_ENABLED (default: false)
        consciousness_enabled = os.getenv("CONSCIOUSNESS_ENABLED", "false").lower() == "true"

        # Start background tasks
        self._tasks = [
            asyncio.create_task(self._health_monitor_loop()),
            asyncio.create_task(self._task_processing_loop()),
            asyncio.create_task(self._memory_maintenance_loop()),
            asyncio.create_task(self._scaling_loop()),
            asyncio.create_task(self._report_agents_loop()),
            asyncio.create_task(self._steward_pulse_loop()),
            asyncio.create_task(self._collect_responses()),
            asyncio.create_task(self._monitor_error_rate()),
            asyncio.create_task(self._monitor_agent_state()),
            asyncio.create_task(self._monitor_mailbox_depth()),
        ]

        if consciousness_enabled:
            self._tasks.append(asyncio.create_task(self._consciousness_loop()))
            logger.info("consciousness_loop_enabled")
        else:
            logger.info("consciousness_loop_disabled", hint="Set CONSCIOUSNESS_ENABLED=true to enable")

        logger.info("autonomous_loop_started", background_tasks=len(self._tasks))

        # Main loop
        try:
            while self._running:
                try:
                    await self._process_cycle()
                    await asyncio.sleep(self._loop_interval)
                except asyncio.CancelledError:
                    break
                except Exception as e:
                    logger.error("autonomous_loop_error", error=str(e))
                    await asyncio.sleep(5)  # Backoff on error
        finally:
            await self.shutdown()

    async def _process_cycle(self) -> None:
        """Process one cycle of the autonomous loop."""
        # 1. Check for scheduled tasks (Chronos)
        await self._process_scheduled_tasks()

        # 2. Check for external events (Nexus/Echo)
        await self._process_external_events()

        # 3. Process pending workflows
        await self._process_workflows()

        # 4. Run health checks
        await self._run_health_checks()

        # 5. Event-driven analysis dispatch and periodic heartbeat
        # First: drain any coalesced pending events (if cooldown has expired)
        if self._pending_event_conditions and not self._is_in_cooldown():
            pending = list(self._pending_event_conditions)
            self._pending_event_conditions = []
            await self._request_analysis(pending)

        # Second: fallback periodic heartbeat (every 30 cycles)
        self._analysis_cycle_count += 1
        if self._analysis_cycle_count >= 30:
            self._analysis_cycle_count = 0
            await self._trigger_periodic_analysis()

            # Drain any responses that arrived since the last cycle
            drained: list[dict[str, Any]] = []
            while not self._response_queue.empty():
                item = self._response_queue.get_nowait()
                drained.append(item)
            if drained:
                self._latest_analysis = {
                    "responses": drained,
                    "collected_at": datetime.now(UTC).isoformat(),
                }
                logger.info("responses_drained", count=len(drained))

            # T02: integrate Metis analysis recommendations into Chronos
            await self._integrate_analysis_into_chronos()

            # T03: check Empath stress data and trigger mediation if threshold exceeded
            await self._check_empath_stress_and_mediate()

            # S05: store analysis record in buffer, Cognee, and API store
            await self._store_analysis_to_cognee()

        # 6. Log cycle completion to Historian
        historian = self.supervisor.actors.get("historian") if self.supervisor else None
        if historian is not None:
            await historian.log_event("cycle_complete", "main_loop", {})

    async def _process_scheduled_tasks(self) -> None:
        """Process tasks scheduled by Chronos.

        Gets due ticks from the Chronos actor, routes each tick to its
        target agent via ``put_message()``, and logs the cycle event to
        the Historian actor.

        Gracefully handles missing Chronos, Historian, or target agents
        in the supervisor registry — logs a warning and skips each.
        """
        # 1. Get the Chronos actor
        chronos = self.supervisor.actors.get("chronos") if self.supervisor else None
        if chronos is None:
            logger.warning("scheduled_tasks_skipped_no_chronos")
            return

        # 2. Get due ticks
        ticks = await chronos.generate_ticks()

        # 3. Route each tick to its target agent
        for tick in ticks:
            target = self.supervisor.actors.get(tick.agent_id) if self.supervisor else None
            if target is None:
                logger.warning(
                    "scheduled_task_skipped_no_target",
                    tick_id=tick.tick_id,
                    agent_id=tick.agent_id,
                )
                continue

            from heretek_swarm.actors.base import ActorMessage

            msg = ActorMessage(
                sender="chronos",
                message_type=tick.action,
                content=tick.to_dict(),
                timestamp=datetime.now(UTC).isoformat(),
                recipient=tick.agent_id,
            )
            await target.put_message(msg)

        # 4. Log event to Historian
        historian = self.supervisor.actors.get("historian") if self.supervisor else None
        if historian is not None:
            await historian.log_event(
                "cycle_scheduled_tasks",
                "main_loop",
                {"tick_count": len(ticks)},
            )
        else:
            logger.warning("scheduled_tasks_historian_skipped_no_historian")

    async def _trigger_periodic_analysis(self) -> None:
        """Trigger periodic Metis analysis and Empath sentiment analysis.

        Called every 30 cycles from _process_cycle(). Builds a cycle-count
        context string and delegates dispatch to
        ``_dispatch_analysis_with_conditions()`` so periodic and event-driven
        analysis share the same dispatch path.

        Also runs the autonomous goal pipeline (``_run_goal_pipeline``) which
        is specific to the periodic trigger and not fired for event-driven
        analysis.
        """
        # Build a shared context string from recent cycle activity
        context = (
            f"Cycle analysis at tick {self._analysis_cycle_count}. "
            "Provide a concise strategic overview of current swarm state."
        )

        # Delegate dispatch to the shared method
        conditions: list[dict[str, Any]] = [
            {
                "type": "periodic_heartbeat",
                "cycle_count": self._analysis_cycle_count,
            }
        ]
        metis, _, historian = await self._dispatch_analysis_with_conditions(
            conditions=conditions, context=context
        )

        # --- M011: Autonomous goal pipeline ---
        await self._run_goal_pipeline(metis, historian)

    async def _dispatch_analysis_with_conditions(
        self,
        conditions: list[dict[str, Any]],
        context: str,
    ) -> tuple[Any, Any, Any]:
        """Shared dispatch logic for both periodic and event-driven analysis.

        Constructs and sends analysis messages to Metis and Empath via
        ``put_message()``, then logs the dispatch to Historian.

        Uses the None-guard pattern: missing agents are logged with a
        warning and skipped gracefully.

        Args:
            conditions: List of condition dicts describing why analysis
                was triggered (e.g. ``[{"type": "periodic_heartbeat", ...}]``
                or ``[{"type": "error_spike", ...}]``).
            context: Human-readable context string passed to both agents.

        Returns:
            Tuple of (metis_actor, empath_actor, historian_actor) so
            callers can perform additional agent-specific work.
        """
        from heretek_swarm.actors.base import ActorMessage

        timestamp = datetime.now(UTC).isoformat()

        metis = self.supervisor.actors.get("metis") if self.supervisor else None
        empath = self.supervisor.actors.get("empath") if self.supervisor else None
        historian = self.supervisor.actors.get("historian") if self.supervisor else None

        # --- Metis analysis ---
        if metis is not None:
            msg = ActorMessage(
                sender="main_loop",
                message_type="on_demand_analysis",
                content={
                    "context": context,
                    "conditions": conditions,
                    "perspective": "neutral",
                    "reply_to": "swarm.analysis.metis.response",
                },
                timestamp=timestamp,
            )
            await metis.put_message(msg)
            logger.info("analysis_dispatched_to_metis", condition_count=len(conditions))
        else:
            logger.warning("analysis_skipped_no_metis")

        # --- Empath sentiment ---
        if empath is not None:
            msg = ActorMessage(
                sender="main_loop",
                message_type="on_demand_sentiment",
                content={
                    "text": context,
                    "conditions": conditions,
                    "source_agent": "main_loop",
                    "reply_to": "swarm.analysis.empath.response",
                },
                timestamp=timestamp,
            )
            await empath.put_message(msg)
            logger.info("analysis_dispatched_to_empath", condition_count=len(conditions))
        else:
            logger.warning("analysis_skipped_no_empath")

        # --- Log to Historian ---
        conditions_summary = [
            {k: v for k, v in c.items() if k != "context"} for c in conditions
        ]
        if historian is not None:
            await historian.log_event(
                event_type="analysis_dispatched",
                source="main_loop",
                data={
                    "dispatch_path": "_dispatch_analysis_with_conditions",
                    "condition_count": len(conditions),
                    "conditions": conditions_summary,
                    "metis_dispatched": metis is not None,
                    "empath_dispatched": empath is not None,
                },
            )
        else:
            logger.warning("analysis_historian_skipped_no_historian")

        logger.info(
            "analysis_dispatch_complete",
            conditions=len(conditions),
            metis=metis is not None,
            empath=empath is not None,
            historian=historian is not None,
        )

        return metis, empath, historian

    def _is_in_cooldown(self) -> bool:
        """Check whether the analysis cooldown timer is still active.

        Returns True if ``_cooldown_until`` is set and the current time
        has not yet passed it. Returns False when cooldown has expired
        or has never been set.
        """
        if self._cooldown_until is None:
            return False
        return time.time() < self._cooldown_until

    def _build_event_context(self, conditions: list[dict[str, Any]]) -> str:
        """Build a concise context string from event conditions.

        Iterates over each condition in the list and creates a sentence
        fragment for each type (error_spike, agent_state_change,
        mailbox_depth) including key details like agent IDs, counts,
        and thresholds.

        Args:
            conditions: List of condition dicts with ``type`` and optional
                detail keys (``agent_id``, ``count``, ``threshold``, etc.).

        Returns:
            Concise human-readable context string.
        """
        parts: list[str] = []
        for c in conditions:
            ctype = c.get("type", "unknown")
            if ctype == "error_spike":
                agent_id = c.get("agent_id", "unknown")
                error_count = c.get("count", 0)
                threshold = c.get("threshold", 0)
                parts.append(
                    f"error spike on {agent_id}: {error_count} errors "
                    f"(threshold {threshold})"
                )
            elif ctype == "agent_state_change":
                agent_id = c.get("agent_id", "unknown")
                old_state = c.get("old_state", "unknown")
                new_state = c.get("new_state", "unknown")
                parts.append(
                    f"state change on {agent_id}: {old_state} -> {new_state}"
                )
            elif ctype == "mailbox_depth":
                agent_id = c.get("agent_id", "unknown")
                depth = c.get("count", 0)
                threshold = c.get("threshold", 0)
                parts.append(
                    f"mailbox depth on {agent_id}: {depth} messages "
                    f"(threshold {threshold})"
                )
            elif ctype == "periodic_heartbeat":
                cycle = c.get("cycle_count", 0)
                parts.append(f"periodic heartbeat at cycle {cycle}")
            else:
                parts.append(f"event: {ctype}")

        return "Event-driven analysis triggered by: " + "; ".join(parts)

    async def _request_analysis(self, conditions: list[dict[str, Any]]) -> None:
        """Request event-driven analysis with cooldown protection.

        If the cooldown timer is active, the conditions are coalesced
        into ``_pending_event_conditions`` and the method returns
        without dispatching. Once cooldown expires, pending + new
        conditions are merged, dispatched via
        ``_dispatch_analysis_with_conditions()``, and the cooldown
        timer is reset.

        Cooldown duration is configured via the
        ``HERETEK_ANALYSIS_COOLDOWN_SECONDS`` environment variable
        (default 300 seconds, clamped to minimum 60 seconds).

        Args:
            conditions: List of condition dicts that triggered this
                analysis request.
        """
        # 1. Check cooldown — coalesce if still active
        if self._is_in_cooldown():
            self._pending_event_conditions.extend(conditions)
            logger.info(
                "analysis_cooldown_coalesced",
                cooldown_until=self._cooldown_until,
                pending_count=len(self._pending_event_conditions),
            )
            return

        # 2. Read cooldown duration from env (default 300s, min 60s)
        raw = os.getenv("HERETEK_ANALYSIS_COOLDOWN_SECONDS", "300")
        try:
            cooldown_seconds = max(int(raw), 60)
        except (ValueError, TypeError):
            cooldown_seconds = 300

        # 3. Set cooldown timer
        self._cooldown_until = time.time() + cooldown_seconds

        # 4. Merge pending + new conditions, reset pending
        all_conditions = list(self._pending_event_conditions) + list(conditions)
        self._pending_event_conditions = []

        # 5. Build context string
        context = self._build_event_context(all_conditions)

        # 6. Dispatch to Metis and Empath
        await self._dispatch_analysis_with_conditions(
            conditions=all_conditions, context=context
        )

        logger.info(
            "event_driven_analysis_dispatched",
            condition_count=len(all_conditions),
            cooldown_seconds=cooldown_seconds,
            cooldown_until=self._cooldown_until,
        )

    async def _monitor_error_rate(self) -> None:
        """Monitor for error spikes across all actors.

        Reads ``HERETEK_ANALYSIS_ERROR_THRESHOLD`` env var (default "1").
        Each cycle iterates ``self.supervisor.actors``, calls
        ``actor.get_status()``, and collects agents whose state is
        ``"error"``.  If the count meets or exceeds the threshold,
        dispatches an ``error_spike`` condition via
        ``_request_analysis()``.

        Runs as an independent background task; cooldown and coalescing
        are handled by ``_request_analysis()``.
        """
        while self._running:
            try:
                # Read threshold from env each cycle so it can be tuned at runtime
                raw = os.getenv("HERETEK_ANALYSIS_ERROR_THRESHOLD", "1")
                try:
                    threshold = int(raw)
                except (ValueError, TypeError):
                    threshold = 1

                if self.supervisor is None:
                    await asyncio.sleep(self._health_check_interval)
                    continue

                error_agents: list[str] = []
                for agent_id, actor in self.supervisor.actors.items():
                    try:
                        status = actor.get_status()
                        if status and status.state.value == "error":
                            error_agents.append(agent_id)
                    except Exception:
                        # Individual actor failure should not crash the monitor
                        continue

                if len(error_agents) >= threshold:
                    await self._request_analysis([
                        {
                            "type": "error_spike",
                            "agents": error_agents,
                            "count": len(error_agents),
                            "threshold": threshold,
                        }
                    ])
                    logger.info(
                        "error_spike_detected",
                        error_agents=error_agents,
                        count=len(error_agents),
                        threshold=threshold,
                    )

                await asyncio.sleep(self._health_check_interval)
            except asyncio.CancelledError:
                break
            except Exception as exc:
                logger.error("error_rate_monitor_failed", error=str(exc))
                await asyncio.sleep(self._health_check_interval)

    async def _monitor_agent_state(self) -> None:
        """Monitor agent state transitions to detect changes worth analysis.

        Maintains an internal ``last_states`` dict tracking each actor's
        last-known ``state.value``.  On each cycle, compares current
        states against last known and, for any transitions, dispatches
        an ``agent_state_change`` condition via ``_request_analysis()``.

        Runs as an independent background task; cooldown and coalescing
        are handled by ``_request_analysis()``.
        """
        last_states: dict[str, str] = {}

        while self._running:
            try:
                if self.supervisor is None:
                    await asyncio.sleep(self._health_check_interval)
                    continue

                changes: list[dict[str, str]] = []
                for agent_id, actor in self.supervisor.actors.items():
                    try:
                        status = actor.get_status()
                        if status is None:
                            continue
                        current_state = status.state.value
                        prev_state = last_states.get(agent_id)
                        if prev_state is not None and current_state != prev_state:
                            changes.append({
                                "agent": agent_id,
                                "from": prev_state,
                                "to": current_state,
                            })
                        last_states[agent_id] = current_state
                    except Exception:
                        continue

                if changes:
                    await self._request_analysis([
                        {
                            "type": "agent_state_change",
                            "changes": changes,
                        }
                    ])
                    logger.info(
                        "agent_state_change_detected",
                        changes=changes,
                    )

                await asyncio.sleep(self._health_check_interval)
            except asyncio.CancelledError:
                break
            except Exception as exc:
                logger.error("agent_state_monitor_failed", error=str(exc))
                await asyncio.sleep(self._health_check_interval)

    async def _monitor_mailbox_depth(self) -> None:
        """Monitor actor mailbox depths for backlog conditions.

        Reads ``HERETEK_ANALYSIS_MAILBOX_THRESHOLD`` env var (default "10").
        Each cycle inspects each actor's ``mailbox`` attribute and checks
        ``qsize()``.  If any actor's depth meets or exceeds the threshold,
        dispatches a ``mailbox_depth`` condition via ``_request_analysis()``.

        Uses ``self._loop_interval * 10`` as the sleep period (faster
        check cycle than error/state monitors).

        Runs as an independent background task; cooldown and coalescing
        are handled by ``_request_analysis()``.
        """
        while self._running:
            try:
                # Read threshold from env each cycle for runtime tuneability
                raw = os.getenv("HERETEK_ANALYSIS_MAILBOX_THRESHOLD", "10")
                try:
                    threshold = int(raw)
                except (ValueError, TypeError):
                    threshold = 10

                if self.supervisor is None:
                    await asyncio.sleep(self._loop_interval * 10)
                    continue

                deep_agents: list[dict[str, int]] = []
                for agent_id, actor in self.supervisor.actors.items():
                    try:
                        mailbox = getattr(actor, "mailbox", None)
                        if mailbox is None:
                            continue
                        depth = mailbox.qsize()
                        if depth >= threshold:
                                deep_agents.append({agent_id: depth})
                    except Exception:
                        continue

                if deep_agents:
                    await self._request_analysis([
                        {
                            "type": "mailbox_depth",
                            "agents": deep_agents,
                            "threshold": threshold,
                        }
                    ])
                    logger.info(
                        "mailbox_depth_detected",
                        deep_agents=deep_agents,
                        threshold=threshold,
                    )

                await asyncio.sleep(self._loop_interval * 10)
            except asyncio.CancelledError:
                break
            except Exception as exc:
                logger.error("mailbox_depth_monitor_failed", error=str(exc))
                await asyncio.sleep(self._loop_interval * 10)

    async def _collect_responses(self) -> None:
        """Subscribe to analysis response topics and collect responses.

        Subscribes to ``swarm.analysis.metis.response`` and
        ``swarm.analysis.empath.response``, routing each received
        message through ``_response_queue`` for later drainage in
        ``_process_cycle``.

        Runs as a long-lived background task that is cancelled when the
        swarm shuts down.
        """
        response_topics = [
            "swarm.analysis.metis.response",
            "swarm.analysis.empath.response",
        ]

        async def _on_response(
            mesh_or_none: Any,
            subject: str,
            data: dict[str, Any],
        ) -> None:
            """Callback placed into the event mesh subscription."""
            await self._response_queue.put(
                {
                    "subject": subject,
                    "data": data,
                    "timestamp": datetime.now(UTC).isoformat(),
                }
            )
            logger.info(
                "response_collected",
                topic=subject,
                message_type=data.get("message_type", ""),
            )

        for topic in response_topics:
            await self.event_mesh.subscribe(topic, _on_response)
            logger.info("subscribed_to_response_topic", topic=topic)

        # Keep the coroutine alive as a background task
        await asyncio.Event().wait()

    async def _run_goal_pipeline(self, metis: Any, historian: Any) -> None:
        """Run the goal pipeline: propose, vote, accept/reject goals.

        Uses a lazily-initialised FileGoalStore and builds a
        ConsensusCoordinator from the swarm's MAKER consensus engine
        and the full actor registry.

        Failures are logged at error level and swallowed so the main
        autonomous loop is never crashed by a goal pipeline fault.
        """
        # Lazily initialise the goal store on first use
        if self._goal_store is None:
            self._goal_store = FileGoalStore()

        if self.consensus is None or self.supervisor is None:
            logger.warning(
                "goal_pipeline_skipped",
                reason="consensus_or_supervisor_unavailable",
            )
            return

        try:
            domain_selector = DomainSelector()
            coordinator = ConsensusCoordinator(
                maker=self.consensus,
                domain_selector=domain_selector,
                actors=self.supervisor.actors,
            )

            await run_goal_cycle(
                store=self._goal_store,
                metis=metis,
                coordinator=coordinator,
                actors=self.supervisor.actors,
                historian=historian,
            )
            logger.info("goal_pipeline_cycle_completed")
        except Exception as exc:
            logger.error(
                "goal_pipeline_cycle_failed",
                goal_pipeline_error=str(exc),
            )

    async def _integrate_analysis_into_chronos(self) -> None:
        """Translate Metis analysis recommendations into Chronos bulk operations.

        Called after the cycle-30 response drain to convert Metis
        recommendations from _latest_analysis into schedule operations
        (create, cancel, update_priority) and dispatch them to the
        Chronos agent via put_message().

        Uses None-guard and try/except so no fault crashes the main loop.
        """
        try:
            # Guard: no analysis available
            if not self._latest_analysis or not self._latest_analysis.get("responses"):
                logger.debug("no_analysis_to_integrate")
                return

            responses = self._latest_analysis["responses"]

            # Extract Metis responses only
            metis_responses = [
                r
                for r in responses
                if r.get("subject") == "swarm.analysis.metis.response"
            ]

            if not metis_responses:
                logger.debug("no_metis_responses_to_integrate")
                return

            # Collect all recommendations, deduplicating by normalized text
            seen: set[str] = set()
            operations: list[dict[str, Any]] = []

            for response in metis_responses:
                data = response.get("data", {})
                recommendations: list[str] = data.get("recommendations", [])
                if not isinstance(recommendations, list):
                    continue

                for recommendation in recommendations:
                    if not isinstance(recommendation, str):
                        continue

                    normalized = recommendation.lower().strip()
                    if normalized in seen:
                        continue
                    seen.add(normalized)

                    op = self._classify_recommendation(recommendation)
                    if op is not None:
                        operations.append(op)

            if not operations:
                logger.debug("no_operations_to_integrate")
                return

            logger.info(
                "integration_building_operations",
                total_operations=len(operations),
            )

            # Save to S05 buffer for _store_analysis_to_cognee
            self._last_chronos_operations = list(operations)

            # Send to Chronos
            chronos = self.supervisor.actors.get("chronos") if self.supervisor else None
            if chronos is None:
                logger.warning("integration_skipped_no_chronos")
                return

            from heretek_swarm.actors.base import ActorMessage

            msg = ActorMessage(
                sender="main_loop",
                message_type="bulk_schedule_adjust",
                content={
                    "operations": operations,
                },
                timestamp=datetime.now(UTC).isoformat(),
            )
            await chronos.put_message(msg)

            logger.info(
                "integration_dispatch_complete",
                total_operations=len(operations),
            )

        except Exception as e:
            logger.error(
                "integration_failed",
                error=str(e),
            )

    @staticmethod
    def _classify_recommendation(recommendation: str) -> dict[str, Any] | None:
        """Classify a recommendation string into a Chronos bulk operation dict.

        Uses keyword heuristic matching:
        - cancel/stop/pause/remove -> cancel operation
        - priorit/urgent/critical/elevate -> update_priority operation
        - All other strings -> create operation

        Args:
            recommendation: The recommendation text from Metis analysis.

        Returns:
            An operation dict suitable for bulk_schedule_adjust, or None
            if the recommendation could not be classified.
        """
        import uuid
        from datetime import UTC, datetime

        lower = recommendation.lower()

        # Cancel operations
        if any(kw in lower for kw in ("cancel", "stop", "pause", "remove")):
            return {
                "op": "cancel",
                "operation_id": f"cancel_{uuid.uuid4().hex[:8]}",
                "task_id": f"rec_{uuid.uuid4().hex[:8]}",
            }

        # Update priority operations
        if any(kw in lower for kw in ("priorit", "urgent", "critical", "elevate")):
            is_critical = any(kw in lower for kw in ("urgent", "critical"))
            return {
                "op": "update_priority",
                "operation_id": f"prio_{uuid.uuid4().hex[:8]}",
                "task_id": f"rec_{uuid.uuid4().hex[:8]}",
                "new_priority": 4 if is_critical else 3,
            }

        # All other recommendations -> create operation
        scheduled_at = (datetime.now(UTC).timestamp() + 3600)
        return {
            "op": "create",
            "operation_id": f"create_{uuid.uuid4().hex[:8]}",
            "name": recommendation[:80],
            "action": "analysis_recommendation",
            "scheduled_at": datetime.fromtimestamp(scheduled_at, tz=UTC).isoformat(),
            "priority": 2,
            "target_agents": ["metis"],
            "recurrence": "once",
        }

    async def _check_empath_stress_and_mediate(self) -> None:
        """Check Empath stress data and trigger mediation if threshold exceeded.

        Called after _integrate_analysis_into_chronos() during the cycle-30 drain.
        Reads collective_stress from Empath on_demand_sentiment responses and
        dispatches a trigger_mediation message to the Coordinator when stress
        exceeds the configured threshold.

        Threshold is configurable via HERETEK_MEDIATION_STRESS_THRESHOLD env var
        (default 0.7, clamped to min 0.1, max 1.0).

        Uses the same None-guard pattern as _integrate_analysis_into_chronos() so
        no fault crashes the main loop.
        """
        try:
            # Guard: no analysis available
            if not self._latest_analysis or not self._latest_analysis.get("responses"):
                logger.debug("stress_check_skipped_no_analysis")
                return

            responses = self._latest_analysis["responses"]

            # Extract Empath responses only
            empath_responses = [
                r
                for r in responses
                if r.get("subject") == "swarm.analysis.empath.response"
            ]

            if not empath_responses:
                logger.debug("mediation_skipped", reason="no_empathic_responses")
                return

            # Read threshold from env (default 0.7, clamped 0.1-1.0)
            raw = os.getenv("HERETEK_MEDIATION_STRESS_THRESHOLD", "0.7")
            try:
                threshold = max(0.1, min(1.0, float(raw)))
            except (ValueError, TypeError):
                threshold = 0.7

            # Check each Empath response for high stress
            high_stress_agents: list[str] = []
            stress_levels: dict[str, float] = {}

            for response in empath_responses:
                data = response.get("data", {})
                stress = data.get("collective_stress", 0.0)
                source_agent = data.get("source_agent", "unknown")

                if stress > threshold:
                    high_stress_agents.append(source_agent)
                    stress_levels[source_agent] = stress

            # If no high-stress agents found, log and return
            if not high_stress_agents:
                logger.debug(
                    "mediation_skipped",
                    reason="low_stress",
                    threshold=threshold,
                )
                return

            logger.info(
                "mediation_triggered",
                stress_level=stress_levels,
                agents=high_stress_agents,
                threshold=threshold,
            )

            # Dispatch trigger_mediation to Coordinator
            coordinator = (
                self.supervisor.actors.get("coordinator")
                if self.supervisor
                else None
            )
            if coordinator is None:
                logger.error(
                    "mediation_dispatch_failed",
                    reason="coordinator_unavailable",
                )
                return

            from heretek_swarm.actors.base import ActorMessage

            msg = ActorMessage(
                sender="main_loop",
                message_type="trigger_mediation",
                content={
                    "agents": high_stress_agents,
                    "stress_levels": stress_levels,
                    "context": (
                        f"High collective stress detected: {stress_levels} "
                        f"exceeds threshold {threshold}"
                    ),
                },
                timestamp=datetime.now(UTC).isoformat(),
            )
            await coordinator.put_message(msg)

            self._mediation_dispatched = True

            logger.info(
                "mediation_dispatched",
                stress_level=stress_levels,
                agent_count=len(high_stress_agents),
            )

        except Exception as e:
            logger.error(
                "mediation_dispatch_failed",
                error=str(e),
            )

    async def _store_analysis_to_cognee(self) -> None:
        """Store structured analysis record in-memory and persist to Cognee.

        Called after the cycle-30 response drain, integration, and mediation
        check are all done. Builds a structured record from the latest
        analysis data (Metis analyses, Empath responses, Chronos actions,
        mediation state), appends it to the in-memory buffer (capped at
        ``_max_analysis_records``), and best-effort persists to Cognee via
        ``_cognee_writer`` and pushes to the API store via
        ``push_analysis_record``.
        """
        try:
            # Guard: no analysis available
            if not self._latest_analysis or not self._latest_analysis.get("responses"):
                logger.debug("store_analysis_skipped")
                return

            responses = self._latest_analysis["responses"]

            # Extract Metis analyses
            metis_analyses: list[dict[str, Any]] = []
            for r in responses:
                if r.get("subject") == "swarm.analysis.metis.response":
                    data = r.get("data", {})
                    metis_analyses.append({
                        "analysis": data.get("analysis", ""),
                        "recommendations": data.get("recommendations", []),
                        "confidence": data.get("confidence", 0.0),
                    })

            # Extract Empath responses
            empath_responses: list[dict[str, Any]] = []
            for r in responses:
                if r.get("subject") == "swarm.analysis.empath.response":
                    data = r.get("data", {})
                    empath_responses.append({
                        "collective_stress": data.get("collective_stress", 0.0),
                        "source_agent": data.get("source_agent", "unknown"),
                        "conflict_detected": data.get("conflict_detected", False),
                        "sentiment": data.get("sentiment", "neutral"),
                    })

            # Determine trigger type (informational; default to periodic)
            trigger_type = "periodic"

            # Build record
            record = {
                "id": str(uuid.uuid4()),
                "collected_at": self._latest_analysis.get(
                    "collected_at", datetime.now(UTC).isoformat()
                ),
                "trigger_type": trigger_type,
                "metis_analyses": metis_analyses,
                "empath_responses": empath_responses,
                "chronos_actions": list(self._last_chronos_operations),
                "mediation_dispatched": self._mediation_dispatched,
            }

            # Clear transient tracking state
            self._last_chronos_operations = []
            self._mediation_dispatched = False

            # Append to in-memory buffer (capped)
            self._analysis_records.append(record)
            if len(self._analysis_records) > self._max_analysis_records:
                self._analysis_records[:] = self._analysis_records[-self._max_analysis_records:]

            logger.info(
                "analysis_record_stored",
                id=record["id"],
                metis_count=len(metis_analyses),
                empath_count=len(empath_responses),
                action_count=len(record["chronos_actions"]),
                mediation_dispatched=record["mediation_dispatched"],
            )

            # Best-effort Cognee persist
            if self._cognee_writer is not None:
                try:
                    await self._cognee_writer.store(
                        content=json.dumps(record),
                        dataset="analysis_history",
                        cognify_after=False,
                    )
                except Exception:
                    logger.warning(
                        "analysis_cognee_persist_failed",
                        id=record["id"],
                    )

            # Push to API store
            try:
                await push_analysis_record(record)
            except Exception as e:
                logger.warning(
                    "analysis_push_to_api_failed",
                    error=str(e),
                )

        except Exception as e:
            logger.error(
                "analysis_store_failed",
                error=str(e),
            )

    async def _process_external_events(self) -> None:
        """Process external events from Discord, Slack, Telegram, webhooks."""
        # Check event mesh for external messages
        # Route through Steward for triage

    async def _process_workflows(self) -> None:
        """Process pending workflows."""
        # Check for workflows needing execution
        # Execute HeavySwarm workflows as needed

    async def _run_health_checks(self) -> None:
        """Run health checks on all actors."""
        for agent_id, actor in self.supervisor.actors.items():
            status = actor.get_status()
            if status.state.value == "error":
                logger.warning("actor_error", agent_id=agent_id)
                await self.supervisor.restart_actor(agent_id)

    async def _health_monitor_loop(self) -> None:
        """Continuous health monitoring loop."""
        while self._running:
            try:
                # Publish health metrics
                health_data = {
                    "timestamp": datetime.now(UTC).isoformat(),
                    "active_actors": len(self.supervisor.actors),
                    "mailbox_sizes": {
                        agent_id: getattr(actor, "mailbox", asyncio.Queue()).qsize()
                        for agent_id, actor in self.supervisor.actors.items()
                    },
                    "system_status": "healthy",
                }

                await self.event_mesh.publish(
                    "swarm.system.health",
                    health_data,
                )

                logger.debug("health_metrics_published", active_actors=health_data["active_actors"])

                await asyncio.sleep(self._health_check_interval)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error("health_monitor_error", error=str(e))

    async def _consciousness_loop(self) -> None:
        """Consciousness metrics update loop — wires live agent telemetry to NATS."""
        while self._running:
            try:
                plugin = get_consciousness_plugin()
                registry = get_enhanced_registry()
                phi_stats = plugin.get_statistics()
                attention_distribution, active_count, total_count = self._build_attention_distribution(registry)
                workspace_coherence = active_count / total_count if total_count > 0 else 0.0
                consciousness_data = {
                    "timestamp": datetime.now(UTC).isoformat(),
                    "workspace_coherence": workspace_coherence,
                    "attention_distribution": attention_distribution,
                    "phi_metric": phi_stats.get("average_phi", 0.0),
                    "total_agents": total_count,
                    "active_agents": active_count,
                    "average_free_energy": phi_stats.get("average_free_energy", 0.0),
                    "conscious_agents": phi_stats.get("conscious_agents", 0),
                }
                await self.event_mesh.publish("swarm.system.consciousness", consciousness_data)
                await asyncio.sleep(self._consciousness_interval)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error("consciousness_loop_error", error=str(e))
                await asyncio.sleep(self._consciousness_interval)

    @staticmethod
    def _build_attention_distribution(registry: Any) -> tuple[dict[str, dict[str, str]], int, int]:
        all_instances = registry.get_all_instances()
        attention_distribution: dict[str, dict[str, str]] = {}
        active_count = 0
        for agent_id, instance in all_instances.items():
            state = getattr(instance, "state", None)
            attention_distribution[agent_id] = {
                "state": str(state.value) if hasattr(state, "value") else str(state),
                "type": getattr(instance, "agent_type", "unknown"),
            }
            if state and hasattr(state, "value"):
                active_count += 1
        return attention_distribution, active_count, len(all_instances)

    async def _task_processing_loop(self) -> None:
        """Task processing loop - polls for new tasks."""
        while self._running:
            try:
                # Poll for new tasks from:
                # - External integrations (Discord, Slack, Telegram)
                # - Webhooks
                # - Scheduled tasks (Chronos)
                # - Internal agent requests

                # Route tasks through Steward for triage
                await asyncio.sleep(self._loop_interval)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error("task_processing_error", error=str(e))

    async def _memory_maintenance_loop(self) -> None:
        """Memory tier optimization and cleanup loop."""
        while self._running:
            try:
                # Run memory maintenance
                if self._cognee_reader:
                    await self._cognee_reader.health()
                if self._cognee_writer:
                    await self._cognee_writer.health()

                logger.debug("memory_maintenance_completed")

                await asyncio.sleep(self._memory_maintenance_interval)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error("memory_maintenance_error", error=str(e))

    async def _scaling_loop(self) -> None:
        """Auto-scaling check loop."""
        while self._running:
            try:
                # Check queue depths
                # Check resource utilization
                # Scale up/down based on load

                await asyncio.sleep(self._scaling_interval)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error("scaling_check_error", error=str(e))

    async def _report_agents_loop(self) -> None:
        """Report agent statuses to the API server periodically."""
        import os

        api_host = os.getenv("HERETEK_API_HOST", "heretek-api")
        api_port = int(os.getenv("HERETEK_API_PORT", "8000"))
        report_interval = 30  # seconds

        while self._running:
            await self._report_agents_batch(api_host, api_port)
            await asyncio.sleep(report_interval)

    async def _report_agents_batch(self, api_host: str, api_port: int) -> None:
        """Collect and report agent statuses to the API server.

        Extracts the agent collection and reporting logic to reduce
        cognitive complexity of the parent loop.
        """
        import httpx

        try:
            agents = self._collect_agent_statuses()
            await self._post_agent_report(api_host, api_port, agents)
        except httpx.ConnectError:
            logger.debug("api_not_available")
        except Exception as e:
            logger.warning("agent_report_failed", error=str(e))

    def _collect_agent_statuses(self) -> list[dict[str, Any]]:
        """Collect status information from all active agents."""
        agents = []
        for agent_id, actor in self.supervisor.actors.items():
            status_dict = self._extract_agent_status(agent_id, actor)
            if status_dict:
                agents.append(status_dict)
        return agents

    def _extract_agent_status(self, agent_id: str, actor: Any) -> dict[str, Any] | None:
        """Extract status dictionary for a single agent.

        Returns None if status cannot be extracted (agent not ready).
        """
        try:
            status = actor.get_status()
            return {
                "agent_id": agent_id,
                "agent_type": getattr(actor, "actor_type", "unknown"),
                "state": status.state.value if status else "unknown",
                "message_count": status.message_count if status else 0,
                "error_count": status.error_count if status else 0,
                "mailbox_size": status.mailbox_size if status else 0,
                "last_activity": status.last_activity if status else None,
                "uptime_seconds": status.uptime_seconds if status else 0.0,
            }
        except Exception:
            return None

    async def _post_agent_report(
        self, api_host: str, api_port: int, agents: list[dict[str, Any]]
    ) -> None:
        """Post agent status report to the API server."""
        import httpx

        payload = {
            "runtime_id": "autonomous",
            "agents": agents,
            "total_agents": len(agents),
            "uptime_seconds": 0.0,
        }

        async with httpx.AsyncClient(timeout=10.0) as client:
            await client.post(
                f"http://{api_host}:{api_port}/autonomous/agents",
                json=payload,
            )
        logger.debug("reported_agents_to_api", count=len(agents))

    async def _steward_pulse_loop(self) -> None:
        """Steward heartbeat pulse loop — delegates to steward_pulse module."""
        await run_steward_pulse(self)

    async def shutdown(self) -> None:
        """Graceful shutdown of the autonomous swarm."""
        logger.info("shutting_down_autonomous_swarm")

        self._running = False

        # Cancel background tasks
        for task in self._tasks:
            task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await task

        # Terminate all actors
        if self.supervisor:
            await self.supervisor.terminate_all()
            logger.info("all_actors_terminated")

        # Disconnect event mesh
        if self.event_mesh:
            await self.event_mesh.disconnect()
            logger.info("event_mesh_disconnected")

        # Shutdown RAG
        if self.rag:
            await self.rag.shutdown()
            logger.info("rag_shutdown_complete")

        # Close Cognee clients
        if self._cognee_reader:
            await self._cognee_reader.close()
            logger.info("cognee_reader_closed")
        if self._cognee_writer:
            await self._cognee_writer.close()
            logger.info("cognee_writer_closed")

        # Close ModelGarage
        if self.model_garage:
            await self.model_garage.close()
            logger.info("model_garage_closed")

        logger.info("autonomous_swarm_shutdown_complete")


# ============================================================================
# Re-exports for backward compatibility
# ============================================================================


def _get_main():
    """Lazy import for backward-compatible ``main`` access."""
    from heretek_swarm.runtime.entrypoint import main as _entrypoint_main

    return _entrypoint_main


# Keep main available via __init__.py for backward compatibility.
# Direct execution moved to runtime/entrypoint.py.
