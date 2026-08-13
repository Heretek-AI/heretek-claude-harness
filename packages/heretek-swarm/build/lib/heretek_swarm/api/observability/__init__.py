"""
Observability API subpackage - LLM Tracing and Agent Monitoring

Provides endpoints for:
- LLM call traces
- Tool call traces
- Agent message traces
- Real-time streaming via WebSocket
- Swarm health metrics
- Consciousness metrics (IIT Phi, FEP)
- External call logs
- Message replay & time travel debugging
"""

import asyncio
import os
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

import structlog
from fastapi import APIRouter, HTTPException, WebSocket
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from heretek_swarm.gateway.auth import verify_auth
from heretek_swarm.observability.metrics import (
    RealTimeMetricsStream,
    SwarmMetricsCollector,
)
from heretek_swarm.security.zero_trust import LayerResult, ZeroTrustResult, ZeroTrustValidator

logger = structlog.get_logger(__name__)

# =============================================================================
# Module-Level Globals
# =============================================================================

# In-memory trace storage (in production, use database)
_traces: dict[str, list[Any]] = {}

# Metrics collector and stream instances
_metrics_collector: SwarmMetricsCollector | None = None
_metrics_stream: RealTimeMetricsStream | None = None
_zero_trust: ZeroTrustValidator | None = None

# Rate limiting state
_rate_limit_state: dict[str, list[datetime]] = {}
RATE_LIMIT_REQUESTS = 100  # requests per minute
RATE_LIMIT_WINDOW = 60  # seconds

# External call log database session factory
_external_call_log_session_factory: async_sessionmaker[AsyncSession] | None = None
_external_call_log_engine: Any = None


# =============================================================================
# Helper Functions
# =============================================================================


def _get_external_call_log_session_factory() -> async_sessionmaker[AsyncSession]:
    """Get or create the external call log database session factory."""
    global _external_call_log_session_factory, _external_call_log_engine
    if _external_call_log_session_factory is None:
        database_url = os.environ.get("DATABASE_URL")
        if not database_url:
            raise HTTPException(
                status_code=503,
                detail="External call log database not available: DATABASE_URL not set",
            )
        _external_call_log_engine = create_async_engine(
            database_url,
            echo=False,
            pool_pre_ping=True,
        )
        _external_call_log_session_factory = async_sessionmaker(
            _external_call_log_engine,
            class_=AsyncSession,
            expire_on_commit=False,
        )
        # Lazy-attach DB timing listener — zero cost until this factory is first used
        from heretek_swarm.observability.db_timing import attach_db_timing
        from heretek_swarm.observability.prometheus_metrics import (
            heretek_swarm_db_query_duration_seconds,
        )

        attach_db_timing(
            _external_call_log_engine,
            histogram=heretek_swarm_db_query_duration_seconds,
            histogram_labels={"db_name": "external_call_log"},
        )
        logger.info("ExternalCallLog database session factory initialized")
    return _external_call_log_session_factory


def get_metrics_collector() -> SwarmMetricsCollector:
    """Get or create the metrics collector singleton."""
    global _metrics_collector
    if _metrics_collector is None:
        _metrics_collector = SwarmMetricsCollector()
    return _metrics_collector


def get_metrics_stream() -> RealTimeMetricsStream:
    """Get or create the metrics stream singleton."""
    global _metrics_stream
    if _metrics_stream is None:
        _metrics_stream = RealTimeMetricsStream(get_metrics_collector())
    return _metrics_stream


def get_zero_trust() -> ZeroTrustValidator:
    """Get or create zero trust validator."""
    global _zero_trust
    if _zero_trust is None:
        _zero_trust = ZeroTrustValidator()
    return _zero_trust


def check_rate_limit(client_id: str) -> bool:
    """Check if client has exceeded rate limit."""
    now = datetime.now(UTC)
    window_start = now - timedelta(seconds=RATE_LIMIT_WINDOW)

    if client_id not in _rate_limit_state:
        _rate_limit_state[client_id] = []

    # Clean old entries
    _rate_limit_state[client_id] = [
        ts for ts in _rate_limit_state[client_id] if ts > window_start
    ]

    # Check limit
    if len(_rate_limit_state[client_id]) >= RATE_LIMIT_REQUESTS:
        return False

    # Record this request
    _rate_limit_state[client_id].append(now)
    return True


def validate_input(validator: ZeroTrustValidator, data: Any, context: str) -> None:
    """Validate input using zero-trust validation.

    Note: This is a simplified validation for API inputs.
    The ZeroTrustValidator.validate_request method is async and designed
    for full request/response validation. For simple input validation,
    we just ensure the data is present and non-empty.
    """
    if data is None or (isinstance(data, str) and not data.strip()):
        logger.warning("Input validation failed: {context}")
        raise HTTPException(status_code=400, detail="Invalid input: empty or None")


# =============================================================================
# Helper Classes
# =============================================================================


class TraceEvent:
    """A trace event for observability."""

    def __init__(
        self,
        event_type: str,
        agent_id: str,
        data: dict[str, Any],
        timestamp: datetime | None = None,
        duration: float | None = None,
    ):
        self.id = f"{event_type}-{agent_id}-{datetime.now(UTC).timestamp()}"
        self.event_type = event_type  # 'llm_call', 'tool_call', 'agent_message'
        self.agent_id = agent_id
        self.data = data
        self.timestamp = timestamp or datetime.now(UTC)
        self.duration = duration

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "id": self.id,
            "type": self.event_type,
            "agent_id": self.agent_id,
            "timestamp": self.timestamp.isoformat(),
            "duration": self.duration,
            "data": self.data,
        }


class ConnectionManager:
    """Manage WebSocket connections for real-time trace streaming."""

    def __init__(self):
        self.active_connections: dict[str, WebSocket] = {}

    async def connect(self, websocket: WebSocket, agent_id: str):
        """Handle new WebSocket connection."""
        self.active_connections[agent_id] = websocket
        logger.info("websocket_connected", agent_id=agent_id)

    async def disconnect(self, _websocket: WebSocket, agent_id: str):
        """Handle WebSocket disconnection."""
        if agent_id in self.active_connections:
            del self.active_connections[agent_id]
            logger.info("websocket_disconnected", agent_id=agent_id)

    async def broadcast_trace(self, trace: TraceEvent, agent_id: str):
        """Broadcast trace to all connections for an agent."""
        if agent_id in self.active_connections:
            websocket = self.active_connections[agent_id]
            try:
                await websocket.send_json(trace.to_dict())
            except Exception as e:
                logger.error("websocket_send_failed", agent_id=agent_id, error=str(e))

    async def broadcast_observability(self, data: dict[str, Any]):
        """Broadcast observability update to all connections.

        Broadcasts to all active WebSocket connections regardless of agent.
        Used for external call logs, metrics, and other observability events.
        """
        disconnected: set[WebSocket] = set()
        for agent_id, websocket in self.active_connections.items():
            try:
                await websocket.send_json(data)
            except Exception as e:
                logger.debug(
                    "websocket_broadcast_disconnect", agent_id=agent_id, error=str(e)
                )
                disconnected.add(websocket)
        # Clean up disconnected
        for ws in disconnected:
            for aid, w in list(self.active_connections.items()):
                if w == ws:
                    del self.active_connections[aid]


connection_manager = ConnectionManager()


# =============================================================================
# Replay Manager (shared state for events.py)
# =============================================================================

_replay_manager: Any | None = None


def get_replay_manager() -> Any | None:
    """Get or create the replay manager."""
    global _replay_manager
    if _replay_manager is None:
        try:
            from heretek_swarm.gateway.jetstream_manager import get_jetstream_manager
            from heretek_swarm.gateway.message_replay import get_replay_manager as get_rm
            from heretek_swarm.state.event_store import get_event_store

            js_manager = get_jetstream_manager()
            event_store = get_event_store()
            _replay_manager = get_rm()

            # Setup with dependencies
            _replay_manager._js_manager = js_manager  # noqa: SLF001
            _replay_manager._event_store = event_store  # noqa: SLF001

        except ImportError:
            return None
    return _replay_manager


# =============================================================================
# Pydantic Models (shared across submodules)
# =============================================================================


class ReplayJobCreate(BaseModel):
    """Request model for creating a replay job."""

    stream_name: str = Field(..., description="Source stream name")
    start_sequence: int | None = Field(None, description="Start sequence number")
    end_sequence: int | None = Field(None, description="End sequence number")
    start_time: str | None = Field(None, description="Start timestamp (ISO format)")
    end_time: str | None = Field(None, description="End timestamp (ISO format)")
    subject_filter: str | None = Field(None, description="Subject pattern filter")
    destination_stream: str | None = Field(None, description="Destination stream")
    replay_speed: float = Field(
        default=1.0, ge=0.1, le=100.0, description="Replay speed multiplier"
    )


class ReplayJobResponse(BaseModel):
    """Response model for replay job."""

    job_id: str
    stream_name: str
    start_sequence: int | None
    end_sequence: int | None
    subject_filter: str | None
    destination_stream: str | None
    replay_speed: float
    status: str
    progress: int
    total: int
    progress_percent: float
    started_at: str | None
    completed_at: str | None
    error: str | None


class ReplayJobListResponse(BaseModel):
    """Response model for listing replay jobs."""

    jobs: list[ReplayJobResponse]
    total: int
    active: int


class TimeTravelRequestCreate(BaseModel):
    """Request model for time travel debugging."""

    entity_id: str = Field(..., description="Entity to reconstruct")
    entity_type: str = Field(..., description="Entity type (agent, workflow)")
    target_time: str = Field(..., description="Target timestamp (ISO format)")
    source_stream: str = Field(..., description="Source stream name")
    include_snapshots: bool = Field(
        default=True, description="Use snapshots if available"
    )


class TimeTravelResponse(BaseModel):
    """Response model for time travel result."""

    request_id: str
    entity_id: str
    entity_type: str
    target_time: str
    state: dict[str, Any]
    events_applied: int
    snapshot_used: bool


# =============================================================================
# Main Router
# =============================================================================

router = APIRouter(prefix="/api/observability", tags=["observability"])

# Import submodule routers and include them.
# These imports happen at the bottom so submodules can access shared globals
# from this package via absolute imports.

from .alerts import router as _alerts_router  # noqa: E402
from .consciousness import router as _consciousness_router  # noqa: E402
from .events import router as _events_router  # noqa: E402
from .external_calls import router as _external_calls_router  # noqa: E402
from .stream import router as _stream_router  # noqa: E402
from .swarm import router as _swarm_router  # noqa: E402
from .traces import router as _traces_router  # noqa: E402

router.include_router(_swarm_router)
router.include_router(_consciousness_router)
router.include_router(_stream_router)
router.include_router(_alerts_router)
router.include_router(_traces_router)
router.include_router(_external_calls_router)
router.include_router(_events_router)
