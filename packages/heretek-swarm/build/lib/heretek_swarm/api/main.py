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
from datetime import datetime, timezone
from typing import Any

import structlog
from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from heretek_swarm.agents.agent_factory import build_agent_for
from heretek_swarm.config.secrets_loader import SecretsLoader
from heretek_swarm.swarm_logging.config import logger as logging_logger

# Initialize logging with JSON output for Loki/Promtail
from heretek_swarm.swarm_logging.config import setup_logging

# Setup structured JSON logging
log_level = os.getenv("LOG_LEVEL", "INFO").upper()
json_output = os.getenv("LOG_FORMAT", "json").lower() == "json"
setup_logging(log_level=log_level, json_output=json_output)

from heretek_swarm.actors.supervisor import ActorSupervisor  # noqa: E402
from heretek_swarm.api import (  # noqa: E402
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
from heretek_swarm.api.rate_limiting import setup_rate_limiting  # noqa: E402
from heretek_swarm.api.websockets import manager  # noqa: E402
from heretek_swarm.config.loader import (  # noqa: E402
    get_config,
    initialize_config_loader,
)
from heretek_swarm.config.service import (  # noqa: E402
    get_config_service,
    initialize_config_service,
    shutdown_config_service,
)
from heretek_swarm.consensus.deliberation import Position  # noqa: E402
from heretek_swarm.gateway.auth import verify_auth  # noqa: E402
from heretek_swarm.gateway.nats_event_mesh import NATSEventMesh  # noqa: E402
from heretek_swarm.mcp.server import router as mcp_router  # noqa: E402
from heretek_swarm.memory.persistent import PersistentMemory as PersistentMemoryStore  # noqa: E402
from heretek_swarm.observability.tracing import setup_telemetry_middleware  # noqa: E402

# Import mem0 backend
try:
    from memory import MEM0_AVAILABLE, Mem0Backend, Mem0Config
except ImportError:
    MEM0_AVAILABLE = False
    Mem0Backend = None
    Mem0Config = None

# Import logging middleware
from heretek_swarm.api.logging_middleware import setup_logging_middleware  # noqa: E402

logger = structlog.get_logger("api.main")

# Module-level constants for repeated string literals
_REDIS_URL_REQUIRED_MSG = "REDIS_URL is required. Set it to redis://host:port or use docker compose."
_QDRANT_URL_REQUIRED_MSG = "QDRANT_URL is required. Set it to http://host:port or use docker compose."

# Global supervisor instance
supervisor: ActorSupervisor | None = None
memory_store: PersistentMemoryStore | None = None
mem0_backend: Any | None = None  # Mem0Backend when available
_nats_mesh: NATSEventMesh | None = None  # NATS event mesh for WebSocket bridge
_ws_pump_task: asyncio.Task | None = None  # WebSocket status pump background task


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan handler for startup and shutdown."""
    global supervisor, memory_store, mem0_backend, _ws_pump_task

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

    if memory_store:
        await memory_store.disconnect()

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
    asyncio.create_task(_spawn_all_agents())  # noqa: RUF006


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
            # Inject a swarms.Agent so the actor can produce real LLM output
            actor.swarms_agent = build_agent_for(agent_id, agent_class.__name__)
            logger.info("actor_spawned", agent_id=agent_id)
            spawned_count += 1
        except Exception as e:
            logger.error("actor_spawn_failed", agent_id=agent_id, error=str(e))

    logger.info("all_actors_spawned", count=spawned_count)


async def _init_memory_store() -> None:
    """Initialize PersistentMemoryStore."""
    global memory_store

    try:
        database_url = await get_config("database.url", default=os.environ.get("DATABASE_URL"))
        if not database_url:
            raise ValueError("DATABASE_URL is required")
        memory_store = PersistentMemoryStore()
        await memory_store.connect()
        logger.info("PersistentMemoryStore connected")
    except Exception as e:
        logger.warning("PersistentMemoryStore not available", error=str(e))
        memory_store = None


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


# Register routers
app.include_router(websockets.router)
app.include_router(consensus.router)
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
app.include_router(mcp_router)

# Setup Prometheus metrics middleware
from heretek_swarm.observability.prometheus_metrics import setup_metrics_middleware  # noqa: E402

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
    """Check PostgreSQL connection status."""
    try:
        if not memory_store:
            # Try to get database URL and connect directly
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
        if memory_store and memory_store._engine:  # noqa: SLF001
            from sqlalchemy import text

            async with memory_store._engine.connect() as conn:  # noqa: SLF001
                await conn.execute(text("SELECT 1"))
            return {
                "status": "healthy",
                "database": "heretek_swarm",
            }
        return {
            "status": "unhealthy",
            "error": "Not connected",
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
        "timestamp": datetime.now(timezone.utc).isoformat(),
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
    if not memory_store:
        return {
            "total_memories": 0,
            "by_agent": {},
            "by_type": {},
            "status": "unavailable",
        }

    try:
        # Get total count
        from sqlalchemy import func, select

        from heretek_swarm.memory.persistent import MemoryEntryModel

        async with memory_store._session_factory() as session:  # noqa: SLF001
            # Total count
            stmt = select(func.count()).select_from(MemoryEntryModel)
            result = await session.execute(stmt)
            total = result.scalar() or 0

            # By agent
            agent_stmt = select(MemoryEntryModel.agent_id, func.count()).group_by(
                MemoryEntryModel.agent_id
            )
            agent_result = await session.execute(agent_stmt)
            by_agent = {row[0]: row[1] for row in agent_result.all()}

            # By type
            type_stmt = select(MemoryEntryModel.memory_type, func.count()).group_by(
                MemoryEntryModel.memory_type
            )
            type_result = await session.execute(type_stmt)
            by_type = {row[0]: row[1] for row in type_result.all()}

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


# =============================================================================
# Prompt Endpoint — Swarm Deliberation
# =============================================================================


class PromptRequest(BaseModel):
    """Request model for the prompt endpoint."""

    prompt: str


class PromptResponse(BaseModel):
    """Response model for swarm deliberation output."""

    deliberation_id: str
    topic: str
    opinions: list[dict[str, Any]]
    votes: dict[str, int]
    synthesis: str
    consensus_score: float
    rounds: int
    participants: list[str]
    dissent_notes: list[str]
    llm_available: bool


@app.post("/api/prompt", response_model=PromptResponse)
async def prompt_endpoint(request: PromptRequest, authenticated: str = Depends(verify_auth)):
    """
    Submit a prompt for swarm deliberation.

    Accepts a user prompt and orchestrates a deliberation across available
    swarm agents. Each agent submits a position and reasoning; the engine
    aggregates these into a synthesis.

    When no LLM provider is configured, agents contribute archetype-based
    responses derived from their agent type and role.

    Returns structured JSON containing agent opinions, votes, and synthesis.
    """
    from heretek_swarm.api.consensus import deliberation_engine

    logger.info("prompt_received", prompt=request.prompt[:200])

    # Determine active participants from the supervisor
    participants: list[str] = []
    if supervisor is not None and supervisor.actors:
        max_participants = int(os.environ.get("HERETEK_MAX_DELIBERATION_PARTICIPANTS", "5"))
        participants = list(supervisor.actors.keys())[:max_participants]
        logger.info("prompt_participants", count=len(participants), agents=participants)

    # If no supervisor actors exist, return empty — client should spawn agents first
    if not participants:
        raise HTTPException(
            status_code=503,
            detail="No agents available in supervisor registry. Deploy agents before starting deliberation.",
        )

    # Check whether we have a working LLM provider
    llm_available = bool(
        os.environ.get("OPENAI_API_KEY") or os.environ.get("ANTHROPIC_API_KEY")
    )

    # Start the deliberation
    deliberation_id = deliberation_engine.start_deliberation(
        topic=request.prompt,
        participants=participants,
    )

    # Broadcast deliberation_started to dashboard WebSocket clients
    with suppress(Exception):
        await manager.broadcast_dashboard({
            "type": "deliberation_started",
            "deliberation_id": deliberation_id,
            "topic": request.prompt[:200],
            "participant_count": len(participants),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })

    # Gather positions from each participant via submit_argument
    opinions: list[dict[str, Any]] = []
    votes: dict[str, int] = {"for": 0, "against": 0, "neutral": 0}

    for agent_id in participants:
        # Attempt real LLM-driven position when available
        reasoning: str | None = None
        if supervisor is not None and agent_id in supervisor.actors:
            actor = supervisor.actors[agent_id]
            try:
                run_fn = getattr(actor, "run_with_llm", None)
                if callable(run_fn) and llm_available:
                    reasoning = await run_fn(
                        f"As {agent_id}, give your position on: {request.prompt}\n"
                        f"Respond with a single paragraph of reasoning.",
                        timeout=15,
                    )
            except Exception:
                logger.warning(
                    "agent_llm_call_failed", agent_id=agent_id, exc_info=True
                )

        # Fallback: archetype-based synthetic position
        if not reasoning:
            reasoning = _archetype_response(agent_id, request.prompt)

        # Determine position from reasoning
        position_str = _classify_position(reasoning)
        position = Position(position_str)
        confidence = 0.6  # Default

        deliberation_engine.submit_argument(
            deliberation_id=deliberation_id,
            agent_id=agent_id,
            position=position,
            reasoning=reasoning,
            evidence_refs=[],
            confidence=confidence,
        )

        votes[position_str] += 1
        opinions.append({
            "agent_id": agent_id,
            "position": position_str,
            "confidence": confidence,
            "reasoning": reasoning,
        })

        # Broadcast agent position to dashboard WebSocket clients
        with suppress(Exception):
            await manager.broadcast_dashboard({
                "type": "agent_position_submitted",
                "deliberation_id": deliberation_id,
                "agent_id": agent_id,
                "position": position_str,
                "confidence": confidence,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            })

    # Run a deliberation round to synthesize
    consensus_score = 0.0
    round_count = 0
    synthesis = ""
    try:
        round_result = deliberation_engine.run_deliberation_round(
            deliberation_id=deliberation_id,
        )
        if round_result:
            consensus_score = round_result.consensus_score
            round_count = deliberation_engine.current_rounds.get(deliberation_id, 0)
            # Build synthesis from round arguments and outcome
            synthesis = _build_synthesis(round_result, votes, len(participants))
    except Exception:
        logger.warning("deliberation_round_failed", exc_info=True)
        synthesis = _synthesize_fallback(opinions)
        consensus_score = 0.5
        round_count = 1

        # Broadcast deliberation failure to dashboard WebSocket clients
        with suppress(Exception):
            await manager.broadcast_dashboard({
                "type": "deliberation_round_failed",
                "deliberation_id": deliberation_id,
                "error": "deliberation_round_engine_failed",
                "timestamp": datetime.now(timezone.utc).isoformat(),
            })

    # Collect dissent notes
    dissent_notes: list[str] = []
    try:
        dissent = deliberation_engine.dissent_records.get(deliberation_id, [])
        for d in dissent:
            if hasattr(d, "note") and d.note:
                dissent_notes.append(d.note)
            elif isinstance(d, dict) and d.get("note"):
                dissent_notes.append(d["note"])
    except Exception:
        # Dissent notes are display-only — skip inconsistent records silently
        logger.debug("Malformed dissent note skipped", exc_info=True)

    # Broadcast deliberation_completed to dashboard WebSocket clients
    with suppress(Exception):
        await manager.broadcast_dashboard({
            "type": "deliberation_completed",
            "deliberation_id": deliberation_id,
            "consensus_score": round(consensus_score, 3),
            "votes": votes,
            "participant_count": len(participants),
            "rounds": max(round_count, 1),
            "llm_available": llm_available,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })

    logger.info(
        "prompt_completed",
        deliberation_id=deliberation_id,
        participants=len(participants),
        votes=votes,
        consensus_score=consensus_score,
    )

    return PromptResponse(
        deliberation_id=deliberation_id,
        topic=request.prompt,
        opinions=opinions,
        votes=votes,
        synthesis=synthesis,
        consensus_score=round(consensus_score, 3),
        rounds=max(round_count, 1),
        participants=participants,
        dissent_notes=dissent_notes,
        llm_available=llm_available,
    )


def _archetype_response(agent_id: str, prompt: str) -> str:
    """Generate an archetype-based synthetic response when LLM is unavailable."""
    archetypes: dict[str, str] = {
        "analyst": f"Analyzing '{prompt}': This proposal warrants systematic examination. "
                   "Key factors include feasibility, resource allocation, and alignment with "
                   "swarm objectives. Recommend proceeding with structured evaluation.",
        "critic": f"Regarding '{prompt}': Critical assessment identifies potential risks. "
                  "We must verify assumptions, test edge cases, and ensure robustness before "
                  "committing. Caution is warranted.",
        "synthesizer": f"On '{prompt}': Integrating multiple perspectives reveals convergence "
                       "points. The swarm's collective intelligence suggests a balanced approach "
                       "that incorporates both innovation and prudence.",
        "explorer": f"Exploring '{prompt}': Novel directions emerge from this prompt. "
                    "We could expand into adjacent problem spaces, consider unconventional "
                    "solutions, and probe the boundaries of our current understanding.",
        "validator": f"Validating '{prompt}': Cross-referencing against established patterns "
                     "confirms internal consistency. The proposition aligns with swarm principles "
                     "and operational constraints.",
        "steward": f"Stewarding '{prompt}': The swarm's governance framework guides us. "
                   "I recommend structured deliberation with clear success criteria. "
                   "We should proceed methodically while maintaining operational integrity.",
        "alpha": f"Alpha perspective on '{prompt}': As primary agent, I support moving "
                 "forward with this direction. The proposal aligns with our core objectives "
                 "and warrants full swarm engagement.",
        "beta": f"Beta analysis of '{prompt}': While the direction is sound, I suggest "
                "refining the approach with additional safeguards. We should validate "
                "assumptions before full commitment.",
        "charlie": f"Charlie's take on '{prompt}': I concur with the general direction "
                   "but note potential edge cases. Recommend modifying scope to account "
                   "for boundary conditions.",
        "historian": f"Historical context on '{prompt}': Based on prior deliberation "
                     "patterns, this type of proposal typically benefits from iterative "
                     "refinement. I recommend at least two rounds of structured review.",
    }

    agent_lower = agent_id.lower()
    for key, response in archetypes.items():
        if key in agent_lower:
            return response

    # Generic fallback
    return (
        f"Considering '{prompt}': As agent {agent_id}, I evaluate this prompt within "
        f"the swarm's collective framework. The proposal merits deliberation and "
        f"structured analysis before reaching consensus."
    )


def _classify_position(reasoning: str) -> str:
    """Classify an agent's reasoning into a deliberation position."""
    reasoning_lower = reasoning.lower()
    if any(w in reasoning_lower for w in ("support", "recommend", "agree", "proceed", "promising", "should", "forward", "engage")):
        return "for"
    if any(w in reasoning_lower for w in ("oppose", "reject", "disagree", "danger", "unsafe", "against")):
        return "against"
    return "neutral"


def _build_synthesis(round_result: Any, votes: dict[str, int], participant_count: int) -> str:
    """Build a human-readable synthesis from a deliberation round result."""
    outcome = getattr(round_result, "outcome", None)
    outcome_str = outcome.value if outcome else "unknown"
    score = getattr(round_result, "consensus_score", 0.0)
    changes = getattr(round_result, "position_changes", 0)

    parts: list[str] = [
        f"Deliberation outcome: {outcome_str}",
        f"Consensus score: {score:.2f}",
        f"Vote distribution: {votes.get('for', 0)} for, "
        f"{votes.get('against', 0)} against, "
        f"{votes.get('neutral', 0)} neutral",
        f"Position changes during round: {changes}",
    ]

    # Include a brief argument preview
    arguments = getattr(round_result, "arguments", [])
    if arguments:
        previews: list[str] = []
        for arg in arguments[:3]:
            agent = getattr(arg, "agent_id", "unknown")
            pos = getattr(getattr(arg, "position", None), "value", "?")
            reason = getattr(arg, "reasoning", "")
            truncated = reason[:120] + "..." if len(reason) > 120 else reason
            previews.append(f"[{agent} / {pos}] {truncated}")
        parts.append("Argument previews:\n" + "\n".join(previews))

    return "\n\n".join(parts)


def _synthesize_fallback(opinions: list[dict[str, Any]]) -> str:
    """Build a fallback synthesis from agent opinions."""
    support_count = sum(1 for o in opinions if o["position"] == "for")
    total = len(opinions) or 1
    if support_count > total / 2:
        return (
            f"Consensus emerges: {support_count}/{total} agents favor the proposal. "
            "The swarm inclines toward acceptance with minor reservations noted."
        )
    return (
        f"Deliberation inconclusive: {support_count}/{total} agents favor. "
        "Further rounds may be needed to resolve divergent positions."
    )
