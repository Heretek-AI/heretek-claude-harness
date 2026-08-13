"""
Observability API subpackage.

Phase 2A.3 cutover: the package used to mount 8 sub-routers backed
by the deleted ``observability.metrics`` module
(:class:`SwarmMetricsCollector` / :class:`RealTimeMetricsStream`).
Six of the eight routers (alerts, consciousness, stream, swarm,
traces) are deleted in commit 9 because they were 1:1 wrappers
around the collector. The package now mounts only the two
production-surviving routers (``events`` for replay, ``external_calls``
for the call log) plus the shared glue (DB session factory,
WebSocket connection manager, rate limiter, zero-trust validator,
and Pydantic models for the replay endpoints).

The ``get_replay_manager()`` helper that used to live here is
relocated to ``heretek_swarm.gateway.message_replay``.
"""

from __future__ import annotations

import os
from datetime import UTC, datetime, timedelta
from typing import Any

import structlog
from fastapi import APIRouter, HTTPException, WebSocket
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from heretek_swarm.gateway.auth import verify_auth
from heretek_swarm_core.security.zero_trust import ZeroTrustValidator

logger = structlog.get_logger(__name__)

# =============================================================================
# Rate limiting state (used by external_calls.py)
# =============================================================================

_rate_limit_state: dict[str, list[datetime]] = {}
RATE_LIMIT_REQUESTS = 100  # requests per minute
RATE_LIMIT_WINDOW = 60  # seconds

# External call log database session factory (used by external_calls.py)
_external_call_log_session_factory: async_sessionmaker[AsyncSession] | None = None
_external_call_log_engine: Any = None

# Zero trust validator singleton (used by external_calls.py)
_zero_trust: ZeroTrustValidator | None = None


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
        from heretek_swarm.observability.prometheus_native import DB_QUERY_DURATION

        attach_db_timing(
            _external_call_log_engine,
            histogram=DB_QUERY_DURATION,
            histogram_labels={"db_name": "external_call_log"},
        )
        logger.info("ExternalCallLog database session factory initialized")
    return _external_call_log_session_factory


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
# ConnectionManager (used by external_calls.py for websocket broadcast)
# =============================================================================


class ConnectionManager:
    """Manage WebSocket connections for real-time observability event broadcast."""

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

    async def broadcast_observability(self, data: dict[str, Any]):
        """Broadcast observability update to all connections.

        Broadcasts to all active WebSocket connections regardless of agent.
        Used for external call logs and other observability events.
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
# Pydantic Models (shared across submodules, used by events.py)
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

# Import submodule routers and include them. The imports happen at the
# bottom so submodules can access shared globals from this package via
# absolute imports.

from .events import router as _events_router
from .external_calls import router as _external_calls_router

router.include_router(_external_calls_router)
router.include_router(_events_router)
