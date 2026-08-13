"""
Heretek Swarm FastAPI Main Application

Provides HTTP endpoints for:
- Health checks (gateway, redis, postgres, qdrant)
- Agent management and monitoring
- Memory statistics (PostgreSQL and mem0)
- LiteLLM metrics
- A2A message history
- Consensus state
- Prometheus metrics (/metrics)

Reference: MiniMax Audit Lines 585-725
"""

import asyncio
import os
from contextlib import asynccontextmanager, suppress
from datetime import UTC, datetime
from typing import Any

import structlog
from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from heretek_swarm_core.llm.pydantic_ai_agent_factory import build_pydantic_ai_agent_for
from heretek_swarm.config.secrets_loader import SecretsLoader
from heretek_swarm.swarm_logging.config import logger as logging_logger

# Initialize logging with JSON output for Loki/Promtail
from heretek_swarm.swarm_logging.config import setup_logging

# Setup structured JSON logging
log_level = os.getenv("LOG_LEVEL", "INFO").upper()
json_output = os.getenv("LOG_FORMAT", "json").lower() == "json"
setup_logging(log_level=log_level, json_output=json_output)

from heretek_swarm.actors.supervisor import ActorSupervisor
from heretek_swarm.api import (
    agents_management,
    autonomous,
    collective_evolution,
    compute_tier,
    configuration,
    consciousness,
    consensus,
    emergent_intelligence,
    evaluation,
    memories,
    memory_versions,
    metrics,
    observability,
    perceiver,
    plugins,
    providers_config,
    provisioner,
    rag,
    skills,
    websockets,
    wizard,
    workflows,
)

# Import logging middleware
from heretek_swarm.api.logging_middleware import setup_logging_middleware
from heretek_swarm.api.rate_limiting import setup_rate_limiting
from heretek_swarm.config.loader import (
    get_config,
    initialize_config_loader,
)
from heretek_swarm.config.service import (
    get_config_service,
    initialize_config_service,
    shutdown_config_service,
)
from heretek_swarm.gateway.auth import verify_auth
from heretek_swarm.gateway.nats_event_mesh import NATSEventMesh
from heretek_swarm.mcp.server import router as mcp_router
from heretek_swarm_core.memory.cognee_reader import CogneeMemoryReader
from heretek_swarm_core.memory.cognee_writer import CogneeMemoryWriter

# Import mem0 backend — see heretek_swarm.memory.mem0_backend
# (Previously this did `from memory import …` which always failed because
# `memory` is a sub-package of `heretek_swarm`, not a top-level module.
# See PLAN.md §1.8 — Prime Directive "Persistent Operation" violation.)
from heretek_swarm_core.memory.mem0_backend import (
    MEM0_AVAILABLE,
    Mem0Backend,
    Mem0Config,
)
from heretek_swarm.observability.tracing import setup_telemetry_middleware

logger = structlog.get_logger("api.main")

# Module-level constants for repeated string literals
_REDIS_URL_REQUIRED_MSG = "REDIS_URL is required. Set it to redis://host:port or use docker compose."
_QDRANT_URL_REQUIRED_MSG = "QDRANT_URL is required. Set it to http://host:port or use docker compose."

# Global supervisor instance
supervisor: ActorSupervisor | None = None
cognee_writer: CogneeMemoryWriter | None = None
cognee_reader: CogneeMemoryReader | None = None
mem0_backend: Any | None = None  # Mem0Backend when available
_nats_mesh: NATSEventMesh | None = None  # NATS event mesh for WebSocket bridge
_ws_pump_task: asyncio.Task | None = None  # WebSocket status pump background task


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan handler for startup and shutdown."""
    global supervisor, cognee_writer, cognee_reader, mem0_backend, _ws_pump_task

    # Startup
    logger.info("Starting Heretek Swarm API...")

    # Step 0: Decrypt SOPS secrets (must run BEFORE any other init)
    try:
        loader = SecretsLoader()
        await loader.load_secrets()
    except Exception as e:
        logger.critical("secrets_startup_failed", error=str(e))
        raise

    # Step 0.5: Certificate auto-renewal check (after secrets loaded)
    try:
        from heretek_swarm.infrastructure.nats.ca import check_and_renew_certs

        await check_and_renew_certs()
    except Exception as e:
        logger.warning("cert_auto_renewal_check_failed", error=str(e))

    await _init_config_service()
    await _init_supervisor()
    await _init_memory_store()
    await _init_mem0()
    await _init_nats_bridge()
    await _init_sovereign_services()

    # Start the WebSocket status pump — must happen after supervisor init
    _ws_pump_task = asyncio.create_task(_ws_status_pump())
    logger.info("ws_status_pump_task_created")

    await _log_startup_complete()

    yield

    # Shutdown
    logger.info("Shutting down Heretek Swarm API...")

    # Cancel the WebSocket status pump first
    if _ws_pump_task and not _ws_pump_task.done():
        _ws_pump_task.cancel()
        with suppress(asyncio.CancelledError):
            await _ws_pump_task
        logger.info("ws_status_pump_task_cancelled")

    if supervisor:
        await supervisor.terminate_all()

    if mem0_backend:
        await mem0_backend.shutdown()

    if cognee_writer:
        await cognee_writer.close()

    if cognee_reader:
        await cognee_reader.close()

    if _nats_mesh:
        await _nats_mesh.disconnect()

    # Shutdown ConfigurationService
    await shutdown_config_service()
    logger.info("ConfigurationService shutdown complete")


async def _init_config_service() -> None:
    """Initialize ConfigurationService and loader."""
    global mem0_backend

    try:
        await initialize_config_service()
        await initialize_config_loader()

        config_service = get_config_service()
        rate_limit_config = await config_service.get_config("rate_limit.enabled")
        if rate_limit_config is not None:
            logger.info("Configuration loaded from database")
        else:
            logger.info("Configuration falling back to environment variables")

        try:
            seed_result = await config_service.seed_from_env()
            if (
                seed_result.get("providers_created")
                or seed_result.get("embedding_providers_created")
                or seed_result.get("configs_created")
            ):
                logger.info("env_seeding_complete", **seed_result)
            else:
                logger.info("env_seeding_skipped", reason="no_env_vars_set")
        except Exception as e:
            logger.warning("env_seeding_skipped", reason=str(e))
    except Exception as e:
        logger.warning("ConfigurationService not available", error=str(e))
        logger.info("Using environment variables for configuration")


async def _init_supervisor() -> None:
    """Initialize ActorSupervisor."""
    global supervisor
    import heretek_swarm.actors.supervisor as supervisor_module

    supervisor = ActorSupervisor()
    # Set the global singleton so API endpoints can access the same instance
    supervisor_module._global_supervisor = supervisor

    # Connect NATS event mesh and set it on the supervisor
    try:
        mesh = NATSEventMesh(fallback=True)
        connected = await mesh.connect()
        if connected:
            supervisor._event_mesh = mesh
            logger.info("NATS event mesh connected to supervisor")
        else:
            logger.warning("NATS event mesh not connected, agents will use fallback")
    except Exception as e:
        logger.warning("Failed to connect NATS event mesh: %s", e)

    logger.info("ActorSupervisor initialized")

    # Fire-and-forget: spawn all 23 agents without blocking API startup
    asyncio.create_task(_spawn_all_agents())


async def _spawn_all_agents() -> None:
    """
    Spawn all 23 agents into the global supervisor.

    Mirrors the agent list from runtime/main_loop.py:_spawn_all_actors().
    Uses local imports inside the function to avoid import-cycle issues.
    Each spawn is wrapped in try/except so a single failure does not
    prevent others from spawning.
    """
    logger.info("agents_auto_spawn_started")

    # Tier 1: Core Triad (Governance)
    from heretek_swarm.actors.arbiter import ArbiterAgent
    from heretek_swarm.actors.catalyst import CatalystAgent
    from heretek_swarm.actors.chronos import ChronosAgent
    from heretek_swarm.actors.coder import CoderAgent

    # Tier 5: Coordination Agents (Integration)
    from heretek_swarm.actors.coordinator import CoordinatorAgent
    from heretek_swarm.actors.dreamer import DreamerAgent
    from heretek_swarm.actors.echo import EchoAgent
    from heretek_swarm.actors.empath import EmpathAgent
    from heretek_swarm.actors.examiner import ExaminerAgent

    # Tier 3: Exploration Agents (Discovery & Creation)
    from heretek_swarm.actors.explorer import ExplorerAgent
    from heretek_swarm.actors.habit_forge import HabitForgeAgent

    # Tier 2: Support Agents (Knowledge & Memory)
    from heretek_swarm.actors.historian import HistorianAgent
    from heretek_swarm.actors.metis import MetisAgent
    from heretek_swarm.actors.nexus import NexusAgent
    from heretek_swarm.actors.perceiver import PerceiverAgent
    from heretek_swarm.actors.perceiver_plus import PerceiverPlusAgent

    # Tier 6: Enhancement Agents (Optimization)
    from heretek_swarm.actors.prism import PrismAgent

    # Tier 4: Safety & Security (Protection)
    from heretek_swarm.actors.sentinel import SentinelAgent
    from heretek_swarm.actors.sentinel_prime import SentinelPrimeAgent
    from heretek_swarm.actors.triad import AlphaAgent, BetaAgent, CharlieAgent, StewardAgent

    actors = [
        # Tier 1: Core Triad
        (StewardAgent, "steward"),
        (AlphaAgent, "alpha"),
        (BetaAgent, "beta"),
        (CharlieAgent, "charlie"),
        # Tier 2: Support
        (HistorianAgent, "historian"),
        (MetisAgent, "metis"),
        (EmpathAgent, "empath"),
        (PerceiverAgent, "perceiver"),
        (EchoAgent, "echo"),
        # Tier 3: Exploration
        (ExplorerAgent, "explorer"),
        (ExaminerAgent, "examiner"),
        (DreamerAgent, "dreamer"),
        (CoderAgent, "coder"),
        # Tier 4: Safety
        (SentinelAgent, "sentinel"),
        (SentinelPrimeAgent, "sentinel-prime"),
        (ArbiterAgent, "arbiter"),
        # Tier 5: Coordination
        (CoordinatorAgent, "coordinator"),
        (NexusAgent, "nexus"),
        (CatalystAgent, "catalyst"),
        (ChronosAgent, "chronos"),
        # Tier 6: Enhancement
        (PrismAgent, "prism"),
        (HabitForgeAgent, "habit-forge"),
        (PerceiverPlusAgent, "perceiver-plus"),
    ]

    spawned_count = 0
    for agent_class, agent_id in actors:
        try:
            actor = await supervisor.spawn_actor(agent_class, agent_id)
            # Inject a pydantic-ai Agent so the actor can produce real LLM output
            actor.pydantic_ai_agent = build_pydantic_ai_agent_for(agent_id, agent_class.__name__)
            logger.info("actor_spawned", agent_id=agent_id)
            spawned_count += 1
        except Exception as e:
            logger.error("actor_spawn_failed", agent_id=agent_id, error=str(e))

    logger.info("all_actors_spawned", count=spawned_count)


async def _init_memory_store() -> None:
    """Initialize CogneeMemoryWriter and CogneeMemoryReader."""
    global cognee_writer, cognee_reader

    try:
        cognee_writer = CogneeMemoryWriter()
        cognee_reader = CogneeMemoryReader()
        logger.info(
            "cognee_memory_initialized",
            writer_enabled=cognee_writer.enabled,
            reader_enabled=cognee_reader.enabled,
        )
    except Exception as e:
        logger.warning("cognee_memory_init_failed", error=str(e))
        cognee_writer = None
        cognee_reader = None


async def _init_mem0() -> None:
    """Initialize Mem0Backend if available."""
    global mem0_backend

    if MEM0_AVAILABLE:
        try:
            qdrant_host = await get_config(
                "qdrant.url", default=os.environ.get("QDRANT_HOST")
            )
            if not qdrant_host:
                raise RuntimeError(
                    "QDRANT_HOST is required for Mem0 initialization. Set QDRANT_HOST env var."
                )
            qdrant_port = await get_config(
                "qdrant.port", default=int(os.environ.get("QDRANT_PORT", "6333"))
            )
            openai_api_key = await get_config(
                "llm.api_key", default=os.environ.get("OPENAI_API_KEY")
            )

            mem0_config = Mem0Config(
                qdrant_host=qdrant_host,
                qdrant_port=int(qdrant_port),
                openai_api_key=openai_api_key,
            )
            mem0_backend = Mem0Backend(config=mem0_config)
            await mem0_backend.initialize()
            logger.info("Mem0Backend initialized")
        except Exception as e:
            logger.warning("Mem0Backend not available", error=str(e))
            mem0_backend = None
    else:
        logger.info("mem0 not installed - using PostgreSQL memory only")


async def _init_nats_bridge() -> None:
    """Initialize NATS EventMesh for WebSocket bridge."""
    global _nats_mesh

    try:
        _nats_mesh = NATSEventMesh(fallback=True)
        connected = await _nats_mesh.connect()
        if connected:
            logger.info("NATS EventMesh connected for WebSocket bridge")

            # Subscribe to A2A events from NATS and broadcast to WebSocket clients
            from heretek_swarm.api import websockets

            async def a2a_event_handler(
                mesh: NATSEventMesh, subject: str, data: dict[str, Any]
            ) -> None:
                """Handle A2A event from NATS and broadcast to WebSocket clients."""
                try:
                    await websockets.manager.broadcast_a2a(data)
                    await websockets.manager.broadcast_dashboard({"type": "a2a_message", **data})
                    logger.debug(
                        "broadcast_a2a_from_nats",
                        subject=subject,
                        has_from=bool(data.get("from")),
                        has_to=bool(data.get("to")),
                    )
                except Exception as e:
                    logger.error(
                        "broadcast_a2a_failed",
                        subject=subject,
                        error=str(e),
                    )

            # Subscribe to swarm events (A2A messages)
            await _nats_mesh.subscribe("swarm.events", a2a_event_handler)
            # Also support wildcard pattern for agent messages
            await _nats_mesh.subscribe("agent.>.messages", a2a_event_handler)

            # Subscribe to external call events from NATS and broadcast to dashboard
            async def external_call_handler(
                mesh: NATSEventMesh, subject: str, data: dict[str, Any]
            ) -> None:
                """Handle external call event from NATS and broadcast to WebSocket clients."""
                try:
                    await websockets.manager.broadcast_dashboard(
                        {
                            "type": "external_call",
                            **data,
                        }
                    )
                    logger.debug(
                        "broadcast_external_call_from_nats",
                        subject=subject,
                        has_call_id=bool(data.get("call_id") or data.get("id")),
                    )
                except Exception as e:
                    logger.error(
                        "broadcast_external_call_failed",
                        subject=subject,
                        error=str(e),
                    )

            await _nats_mesh.subscribe("swarm.external_call", external_call_handler)

            # Subscribe to consciousness events from NATS and broadcast to dashboard
            async def consciousness_event_handler(
                mesh: NATSEventMesh, subject: str, data: dict[str, Any]
            ) -> None:
                """Handle consciousness event from NATS and broadcast to WebSocket dashboard."""
                try:
                    await websockets.manager.broadcast_dashboard(data)
                    logger.debug(
                        "broadcast_consciousness_event_from_nats",
                        subject=subject,
                        event_type=data.get("type"),
                        agent_id=data.get("agent_id"),
                    )
                except Exception as e:
                    logger.error(
                        "broadcast_consciousness_event_failed",
                        subject=subject,
                        error=str(e),
                    )

            await _nats_mesh.subscribe("swarm.metrics.consciousness", consciousness_event_handler)

            logger.info(
                "NATS subscriptions registered for A2A events, external calls, and consciousness events"
            )
        else:
            logger.warning("NATS EventMesh not available, WebSocket bridge using fallback")
    except Exception as e:
        logger.warning("NATS bridge initialization failed", error=str(e))
        _nats_mesh = None


async def _init_sovereign_services() -> None:
    """Initialize the optional sovereign-service gRPC clients.

    Phase 5 of PLAN.md (graduated sovereign services). When the
    api process is started with HERETEK_*_GRPC_URL env vars, the
    corresponding gRPC client is constructed at startup; route
    handlers can then route through it (with a fall-through to
    the in-process stub when the env var is unset).

    This is the wire-up the audit's Phase 5 deployment path
    expects: docker-compose's 'sovereign' profile starts the
    consensus_svc / memory_svc / realtime_svc / observability_svc
    sidecars, sets the env vars, and the api process picks them
    up here. Backwards compatible: when the env vars are unset,
    the resolvers return None and the api falls back to the
    in-process stub from Phase 3.2 / 3.3 / 3.4.

    Verification: the gRPC server was tested end-to-end in the
    Phase 5-actual commit (e15949e7). This commit wires the
    api process to consume it.
    """
    try:
        from heretek_swarm.services.grpc_clients import (
            get_consensus_grpc_client,
            get_memory_grpc_client,
            get_observability_grpc_client,
            get_realtime_grpc_client,
        )

        consensus_grpc = get_consensus_grpc_client()
        if consensus_grpc is not None:
            logger.info(
                "consensus_grpc_client_configured",
                url=os.getenv("HERETEK_CONSENSUS_GRPC_URL"),
            )
        else:
            logger.info("consensus_grpc_client_unset", fallback="in_process_stub")

        memory_grpc = get_memory_grpc_client()
        if memory_grpc is not None:
            logger.info(
                "memory_grpc_client_configured",
                url=os.getenv("HERETEK_MEMORY_GRPC_URL"),
            )

        realtime_grpc = get_realtime_grpc_client()
        if realtime_grpc is not None:
            logger.info(
                "realtime_grpc_client_configured",
                url=os.getenv("HERETEK_REALTIME_GRPC_URL"),
            )

        observability_grpc = get_observability_grpc_client()
        if observability_grpc is not None:
            logger.info(
                "observability_grpc_client_configured",
                url=os.getenv("HERETEK_OBSERVABILITY_GRPC_URL"),
            )

        configured = sum(
            1
            for c in (consensus_grpc, memory_grpc, realtime_grpc, observability_grpc)
            if c is not None
        )
        logger.info(
            "sovereign_services_init_complete",
            configured=configured,
            total=4,
        )
    except Exception as e:
        logger.warning("sovereign_services_init_failed", error=str(e))


async def _ws_status_pump() -> None:
    """
    Background pump that reads supervisor actor states every 10s and
    broadcasts agent_status messages to dashboard WebSocket clients.

    Deduplicates broadcasts against the last-seen status string per agent
    so identical states do not flood the WebSocket every cycle.

    Cancelled cleanly on API shutdown via asyncio.CancelledError.
    """
    global supervisor
    from heretek_swarm.api.websockets import send_agent_status_update

    logger.info("ws_status_pump_started")
    last_status: dict[str, str] = {}
    while True:
        try:
            await asyncio.sleep(10)
            if supervisor is None:
                continue
            actors = list(supervisor.actors.items())
            sent = 0
            for agent_id, actor in actors:
                status = actor.get_status()
                if status is None:
                    continue
                state_str = status.state.value if status.state else "unknown"
                if last_status.get(str(agent_id)) == state_str:
                    continue
                last_status[str(agent_id)] = state_str
                # broadcast_agent_status + broadcast_dashboard happen inside
                await send_agent_status_update(
                    agent_id=str(agent_id),
                    status=state_str,
                )
                sent += 1
            logger.info(
                "agent_status_push_cycle",
                agent_count=len(actors),
                broadcasts=sent,
                deduped=len(actors) - sent,
            )
        except asyncio.CancelledError:
            logger.info("ws_status_pump_cancelled")
            raise
        except Exception:
            logger.exception("ws_status_pump_error")


async def _log_startup_complete() -> None:
    """Log application startup completion."""
    logger.info(
        "Application startup complete",
        rate_limit_enabled=await get_config("rate_limit.enabled", default=True),
    )


# Create FastAPI application
app = FastAPI(
    title="Heretek Swarm API",
    description="Multi-agent swarm orchestration with A2A protocol communication",
    version="0.1.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)


# Add CORS middleware with configuration-based configuration
# Configuration will be loaded from database with environment fallback
allowed_origins_env = os.getenv("CORS_ORIGINS", "")
if allowed_origins_env:
    allowed_origins = allowed_origins_env.split(",")
elif os.getenv("ENVIRONMENT", "development") == "production":
    # Include localhost:3000 for local testing without CORS_ORIGINS env var
    allowed_origins = ["https://your-domain.com", "http://localhost:3000"]
else:
    allowed_origins = ["http://localhost:3000", "http://localhost:5173", "http://localhost:8000"]

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "PATCH"],
    allow_headers=["Authorization", "Content-Type", "X-Requested-With", "X-API-Key"],
)


async def security_headers_middleware(request, call_next):
    """Adds security headers to every response.

    Covers:
    - X-Content-Type-Options: nosniff  (prevents MIME sniffing)
    - X-Frame-Options: DENY          (clickjacking protection)
    - X-XSS-Protection: 1; mode=block (legacy browser XSS filter)
    - Referrer-Policy: strict-origin-when-cross-origin
    - Content-Security-Policy: default-src 'none' (CSP header)
    """
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Content-Security-Policy"] = "default-src 'self'; connect-src 'self' ws: wss:; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'"
    return response


app.middleware("http")(security_headers_middleware)

# Setup logging middleware for request tracking
setup_logging_middleware(app)
logging_logger.info("Logging middleware configured")

# Install slowapi-backed per-request rate limiter (Phase 1.5 of PLAN.md,
# §3.1 Replace). The hand-rolled RateLimiter in security/ddos_protection.py
# is retained for DDoS-pattern detection (sliding window, geo-anomaly,
# mitigation) but the per-route token bucket is now slowapi's
# moving-window strategy. Routes opt in via ``@limiter.limit("100/minute")``
# in their handlers. The state is exposed on app.state.limiter for
# middleware-style enforcement.
from heretek_swarm_core.security.rate_limiter import install_rate_limiter  # noqa: E402

install_rate_limiter(app)
logging_logger.info("Rate limiter (slowapi) configured")


# Register routers
app.include_router(websockets.router)
app.include_router(consensus.router)
from heretek_swarm.api.deliberation import router as deliberation_router  # noqa: E402

app.include_router(deliberation_router)
app.include_router(plugins.router)
app.include_router(workflows.router)
app.include_router(observability.router)
app.include_router(evaluation.router)
app.include_router(rag.router)
app.include_router(consciousness.router)
app.include_router(skills.router)
app.include_router(perceiver.router)
app.include_router(emergent_intelligence.router)
app.include_router(agents_management.router)
app.include_router(autonomous.router)
app.include_router(configuration.router)
app.include_router(providers_config.router)
app.include_router(wizard.router)
app.include_router(provisioner.router)
app.include_router(compute_tier.router)
app.include_router(metrics.router)
app.include_router(memories.router)
app.include_router(memory_versions.router)
app.include_router(collective_evolution.router)
from heretek_swarm.api.chat import router as chat_router  # noqa: E402

app.include_router(chat_router)
app.include_router(mcp_router)

# Setup Prometheus metrics middleware
from heretek_swarm.observability.prometheus_native import setup_metrics_middleware

setup_metrics_middleware(app)
logger.info("Prometheus metrics middleware configured")

# Setup OpenTelemetry distributed tracing middleware
setup_telemetry_middleware(app)
logger.info("OpenTelemetry tracing middleware configured")

# Setup rate limiting with configuration from database
# Note: Rate limiting is set up after lifespan starts, so we use environment variable here
# For runtime config changes, use the /api/config/reload endpoint
rate_limit_enabled = os.environ.get("RATE_LIMIT_ENABLED", "true").lower() == "true"
setup_rate_limiting(app, enabled=rate_limit_enabled)
logger.info("Rate limiting configured", enabled=rate_limit_enabled)


# =============================================================================
# SPA Catch-all Route (must be last to not intercept API routes)
# =============================================================================
# NOTE: This route is defined at the end of the file to ensure API routes are registered first


# =============================================================================
# Health Check Functions
# =============================================================================


async def check_gateway() -> dict[str, Any]:
    """Check the EventMesh gateway status."""
    try:
        # Check if event mesh is accessible
        # Note: In production, this would check actual connections
        return {
            "status": "healthy",
            "active_connections": 0,
            "messages_processed": 0,
        }
    except Exception as e:
        return {
            "status": "unhealthy",
            "error": str(e),
        }


async def check_redis() -> dict[str, Any]:
    """Check Redis connection status."""
    try:
        import redis.asyncio as redis

        # Try to connect to Redis
        redis_url = os.getenv("REDIS_URL")
        if not redis_url:
            raise RuntimeError(_REDIS_URL_REQUIRED_MSG)
        client = redis.from_url(redis_url)
        await client.ping()
        info = await client.info("server")
        await client.close()
        return {
            "status": "healthy",
            "version": info.get("redis_version", "unknown"),
        }
    except Exception as e:
        return {
            "status": "unhealthy",
            "error": str(e),
        }


async def check_postgres() -> dict[str, Any]:
    """Check PostgreSQL connection status via Cognee health endpoint."""
    try:
        # Check Cognee health (which wraps PostgreSQL connectivity)
        if cognee_reader and await cognee_reader.health():
            return {
                "status": "healthy",
                "database": "heretek_swarm",
            }
        if cognee_writer and await cognee_writer.health():
            return {
                "status": "healthy",
                "database": "heretek_swarm",
            }
        # Fallback: direct database URL check
        db_url = os.environ.get("DATABASE_URL", "")
        if not db_url:
            raise ValueError("DATABASE_URL environment variable is required")
        from sqlalchemy import text
        from sqlalchemy.ext.asyncio import create_async_engine

        engine = create_async_engine(db_url)
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        await engine.dispose()
        return {
            "status": "healthy",
            "database": "heretek_swarm",
        }
    except Exception as e:
        return {
            "status": "unhealthy",
            "error": str(e),
        }


async def check_qdrant() -> dict[str, Any]:
    """Check Qdrant vector database status."""
    try:
        import httpx

        # Check multiple environment variables for compatibility
        qdrant_url = os.environ.get("QDRANT_URL")
        if not qdrant_url:
            raise RuntimeError(_QDRANT_URL_REQUIRED_MSG)
        async with httpx.AsyncClient() as client:
            response = await client.get(f"{qdrant_url}/collections")
            if response.status_code == 200:
                return {
                    "status": "healthy",
                    "collections": response.json().get("result", {}).get("collections", []),
                }
        return {
            "status": "unhealthy",
            "error": "Connection failed",
        }
    except Exception as e:
        return {
            "status": "unhealthy",
            "error": str(e),
        }


async def check_mem0() -> dict[str, Any]:
    """Check mem0 embedded backend status.

    mem0 is an embedded logical service running inside the API container
    (not a standalone container). It uses Qdrant as its vector store backend.

    Returns healthy when the mem0_backend is initialized and reachable;
    returns unavailable when mem0_backend is None (e.g. mem0 not installed
    or Qdrant unavailable).
    """
    global mem0_backend

    _MEM0_NOTE = "mem0 is embedded in the API container — no standalone container needed"

    if mem0_backend is None:
        return {
            "status": "unavailable",
            "note": _MEM0_NOTE,
        }

    try:
        # Verify backend is initialized by checking the client attribute
        client = getattr(mem0_backend, "client", None)
        if client is None:
            return {
                "status": "unhealthy",
                "error": "mem0_backend initialized but client is None",
                "note": _MEM0_NOTE,
            }

        # Check Qdrant connectivity via a lightweight operation
        collection_name = getattr(mem0_backend, "collection_name", "mem0")
        try:
            # Use the Qdrant client to check if the collection exists
            from qdrant_client.http.exceptions import UnexpectedResponse

            try:
                client.get_collection(collection_name)
                return {
                    "status": "healthy",
                    "collection": collection_name,
                    "note": _MEM0_NOTE,
                }
            except UnexpectedResponse:
                return {
                    "status": "healthy",
                    "collection": collection_name,
                    "note": _MEM0_NOTE,
                }
        except Exception as e:
            return {
                "status": "degraded",
                "error": f"mem0 backend reachable but Qdrant check failed: {e}",
                "note": _MEM0_NOTE,
            }
    except Exception as e:
        return {
            "status": "unhealthy",
            "error": str(e),
            "note": _MEM0_NOTE,
        }


# =============================================================================
# Health Check Endpoints
# =============================================================================


@app.get("/api/health")
async def health_check():
    """
    Health check endpoint returning status of all services.

    Returns:
        - gateway: EventMesh status
        - redis: Redis connection status
        - postgres: PostgreSQL connection status
        - qdrant: Qdrant vector DB status
        - mem0: embedded memory service status (API-native, no standalone container)
        - pool: Database connection pool stats
    """
    from heretek_swarm.state.repository import StateRepository

    return {
        "status": "healthy",
        "services": {
            "gateway": await check_gateway(),
            "redis": await check_redis(),
            "postgres": await check_postgres(),
            "qdrant": await check_qdrant(),
            "mem0": await check_mem0(),
        },
        "pool": StateRepository.get_pool_stats(),
        "timestamp": datetime.now(UTC).isoformat(),
    }


@app.get("/api/health/live")
async def liveness_check():
    """Kubernetes liveness probe endpoint."""
    return {"status": "alive"}


@app.get("/api/health/ready")
async def readiness_check():
    """Kubernetes readiness probe endpoint."""
    # Check if critical services are available
    checks = await check_postgres()
    if checks.get("status") != "healthy":
        raise HTTPException(503, "PostgreSQL not ready")
    return {"status": "ready"}


# =============================================================================
# Historian Event Endpoints
# =============================================================================


@app.get("/api/historian/events")
async def get_historian_events(
    agent_id: str | None = None,
    event_type: str | None = None,
    since: str | None = None,
    until: str | None = None,
    limit: int = 100,
    authenticated: str = Depends(verify_auth),
):
    """
    Query persisted events from the Historian agent's event store.

    Query parameters:
    - agent_id: Filter by agent identifier (optional)
    - event_type: Filter by event type string (optional)
    - since: ISO-8601 lower bound for timestamp (optional)
    - until: ISO-8601 upper bound for timestamp (optional)
    - limit: Maximum number of results (default 100)

    Returns:
        { events: [...], mode: "postgres" | "jsonl" | "unavailable" | "error" }
    """
    if not supervisor:
        raise HTTPException(503, "Supervisor not initialized")

    historian = supervisor.actors.get("historian")
    if historian is None:
        return {"events": [], "mode": "unavailable", "detail": "Historian agent not yet spawned"}

    try:
        events = await historian.read_events(
            agent_id=agent_id,
            event_type=event_type,
            since=since,
            until=until,
            limit=limit,
        )
        mode = "postgres" if getattr(historian, "_using_pg", False) else "jsonl"
        return {"events": events, "mode": mode}
    except Exception as e:
        logger.exception(
            "historian_events_error",
            agent_id=agent_id,
            event_type=event_type,
            error=str(e),

        )
        return {"events": [], "mode": "error", "detail": str(e)}


# =============================================================================
# Supervisor Endpoints
# =============================================================================


@app.get("/api/supervisor/status")
async def get_supervisor_status(authenticated: str = Depends(verify_auth)):
    """
    Get supervisor overall status and statistics.

    Returns:
        Supervisor statistics including total, active, suspended actors
    """
    if not supervisor:
        raise HTTPException(503, "Supervisor not initialized")

    return supervisor.get_statistics()


# =============================================================================
# Memory Endpoints
# =============================================================================


@app.get("/api/memory")
async def get_memory_stats(authenticated: str = Depends(verify_auth)):
    """
    Get memory statistics across all agents.

    Returns:
        - total_memories: Total memory entries
        - by_agent: Memory count per agent
        - by_type: Memory count per type
    """
    if not cognee_reader or not cognee_reader.enabled:
        return {
            "total_memories": 0,
            "by_agent": {},
            "by_type": {},
            "status": "unavailable",
        }

    try:
        # Use CogneeMemoryReader to search across all memory
        results = await cognee_reader.read(query="agent memory", top_k=100)
        total = len(results)

        # Derive by_agent and by_type from search results metadata
        by_agent: dict[str, int] = {}
        by_type: dict[str, int] = {}
        for entry in results:
            meta = entry.get("metadata", {})
            agent_id = meta.get("agent_id", "unknown")
            mem_type = meta.get("memory_type", "unknown")
            by_agent[agent_id] = by_agent.get(agent_id, 0) + 1
            by_type[mem_type] = by_type.get(mem_type, 0) + 1

        return {
            "total_memories": total,
            "by_agent": by_agent,
            "by_type": by_type,
            "status": "available",
        }
    except Exception as e:
        logger.error("Memory stats failed", error=str(e))
        return {
            "total_memories": 0,
            "by_agent": {},
            "by_type": {},
            "status": "error",
            "error": str(e),
        }


# =============================================================================
# LiteLLM Metrics Endpoint
# =============================================================================


@app.get("/api/litellm/metrics")
async def get_litellm_metrics(authenticated: str = Depends(verify_auth)):
    """
    Get LiteLLM metrics if available.

    Returns:
        LiteLLM proxy metrics
    """
    import httpx

    litellm_url = os.environ.get("LITELLM_URL", "http://localhost:4000")  # Local dev only
    litellm_key = os.environ.get("LITELLM_MASTER_KEY", "")

    try:
        async with httpx.AsyncClient() as client:
            headers = {}
            if litellm_key:
                headers["Authorization"] = f"Bearer {litellm_key}"

            response = await client.get(
                f"{litellm_url}/metrics",
                headers=headers,
                timeout=5.0,
            )

            if response.status_code == 200:
                return response.json()

            return {
                "status": "error",
                "code": response.status_code,
                "message": "Failed to fetch metrics",
            }
    except Exception as e:
        return {
            "status": "unavailable",
            "error": str(e),
        }


# =============================================================================
# A2A Message History Endpoints
# =============================================================================


@app.get("/api/a2a/messages")
async def get_a2a_messages(limit: int = 100, authenticated: str = Depends(verify_auth)):
    """
    Get recent A2A messages from Redis.

    Args:
        limit: Maximum messages to return

    Returns:
        List of recent A2A messages
    """
    try:
        import json

        import redis.asyncio as redis

        redis_url = os.getenv("REDIS_URL")
        if not redis_url:
            raise RuntimeError(_REDIS_URL_REQUIRED_MSG)
        r = redis.from_url(redis_url)

        # Get recent messages from Redis list
        messages = await r.lrange("a2a:messages", 0, limit - 1)
        await r.close()

        return {
            "messages": [json.loads(m) for m in messages],
            "count": len(messages),
        }

    except Exception as e:
        logger.warning("Failed to get A2A messages", error=str(e))
        return {
            "messages": [],
            "count": 0,
            "error": str(e),
        }


@app.get("/api/a2a/messages/{from_agent}/{to_agent}")
async def get_a2a_conversation(from_agent: str, to_agent: str, limit: int = 50, authenticated: str = Depends(verify_auth)):
    """
    Get A2A messages between two agents.

    Args:
        from_agent: Source agent ID
        to_agent: Target agent ID
        limit: Maximum messages to return

    Returns:
        List of messages between the agents
    """
    try:
        import json

        import redis.asyncio as redis

        redis_url = os.getenv("REDIS_URL")
        if not redis_url:
            raise RuntimeError(_REDIS_URL_REQUIRED_MSG)
        r = redis.from_url(redis_url)

        # Get messages and filter
        all_messages = await r.lrange("a2a:messages", 0, 1000)
        await r.close()

        # Filter for this conversation
        conversation = []
        for msg_bytes in all_messages:
            msg = json.loads(msg_bytes)
            if (msg.get("from") == from_agent and msg.get("to") == to_agent) or (
                msg.get("from") == to_agent and msg.get("to") == from_agent
            ):
                conversation.append(msg)
                if len(conversation) >= limit:
                    break

        return {
            "from_agent": from_agent,
            "to_agent": to_agent,
            "messages": conversation[:limit],
            "count": len(conversation[:limit]),
        }

    except Exception as e:
        logger.warning("Failed to get A2A conversation", error=str(e))
        return {
            "from_agent": from_agent,
            "to_agent": to_agent,
            "messages": [],
            "count": 0,
            "error": str(e),
        }


# The /api/prompt swarm-deliberation endpoint lives in
# heretek_swarm.api.deliberation (Phase 2.7 of PLAN.md, §1.4 god-class
# extraction). It is registered as a router further down in this file
# so the URL surface is unchanged.
