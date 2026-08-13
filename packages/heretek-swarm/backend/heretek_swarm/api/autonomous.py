"""
Autonomous Runtime Integration Endpoints.

Provides endpoints for the autonomous runtime to register its agents
and for the frontend to query autonomous agent status.

The autonomous runtime periodically POSTs agent status to this endpoint,
and the frontend queries it via GET.
"""

import asyncio
import math
import uuid
from datetime import UTC, datetime
from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from heretek_swarm.gateway.auth import verify_auth

logger = structlog.get_logger("api.autonomous")

router = APIRouter(
    prefix="/api/autonomous",
    tags=["autonomous"],
    dependencies=[Depends(verify_auth)],
)

# In-memory cache of autonomous agent statuses
# Key: agent_id, Value: status dict with timestamp
_autonomous_agents: dict[str, dict[str, Any]] = {}
_last_update: datetime | None = None
_cache_lock = asyncio.Lock()

# In-memory buffer for analysis records (capped at 1000)
_analysis_records: list[dict[str, Any]] = []
_recents_lock = asyncio.Lock()
MAX_ANALYSIS_RECORDS = 1000

# In-memory buffer for Chronos task snapshots (capped at 500)
_tasks_buffer: list[dict[str, Any]] = []
_tasks_lock = asyncio.Lock()
MAX_TASKS = 500

# In-memory buffer for goal pipeline snapshots (capped at 200)
_goals_buffer: list[dict[str, Any]] = []
_goals_lock = asyncio.Lock()
MAX_GOALS = 200


def get_autonomous_agent_count_sync() -> int:
    """Synchronous access to agent count (for use in sync endpoints)."""
    return len(_autonomous_agents)


async def push_analysis_record(record: dict[str, Any]) -> None:
    """
    Push an analysis record into the in-memory buffer.

    Appends the record and trims to MAX_ANALYSIS_RECORDS if the buffer
    exceeds the cap. Records are stored in insertion order so they can
    be served to the frontend via GET /api/autonomous/analyses.

    Args:
        record: Structured analysis record dict with keys:
            id, collected_at, trigger_type, metis_analyses,
            empath_responses, chronos_actions, mediation_dispatched
    """
    global _analysis_records
    async with _recents_lock:
        _analysis_records.append(record)
        if len(_analysis_records) > MAX_ANALYSIS_RECORDS:
            _analysis_records[:] = _analysis_records[-MAX_ANALYSIS_RECORDS:]
    logger.debug("analysis_record_stored", id=record.get("id"))


async def push_task_snapshot(snapshot: dict[str, Any]) -> None:
    """
    Push a Chronos task snapshot into the in-memory buffer.

    Appends the snapshot and trims to MAX_TASKS if the buffer exceeds
    the cap. Snapshots are stored in insertion order so they can be
    served to the frontend via GET /api/autonomous/tasks.

    The internal runtime (Chronos) calls this to record what tasks are
    active at a given moment.

    Args:
        snapshot: Structured task snapshot dict with keys:
            task_id, title, status, priority, created_at,
            scheduled_at, assigned_to, description, tags
    """
    global _tasks_buffer
    async with _tasks_lock:
        _tasks_buffer.append(snapshot)
        if len(_tasks_buffer) > MAX_TASKS:
            _tasks_buffer[:] = _tasks_buffer[-MAX_TASKS:]
    logger.debug("task_snapshot_stored", task_id=snapshot.get("task_id"))


async def push_goal_snapshot(snapshot: dict[str, Any]) -> None:
    """
    Push a goal pipeline snapshot into the in-memory buffer.

    Appends the snapshot and trims to MAX_GOALS if the buffer exceeds
    the cap. Snapshots are stored in insertion order so they can be
    served to the frontend via GET /api/autonomous/goals.

    The goal engine calls this to record goal lifecycle state changes
    (proposed, voting, accepted, rejected, completed).

    Args:
        snapshot: Structured goal snapshot dict with keys:
            goal_id, title, description, status, priority,
            created_at, updated_at, votes_for, votes_against,
            outcome, proposed_by
    """
    global _goals_buffer
    async with _goals_lock:
        _goals_buffer.append(snapshot)
        if len(_goals_buffer) > MAX_GOALS:
            _goals_buffer[:] = _goals_buffer[-MAX_GOALS:]
    logger.debug("goal_snapshot_stored", goal_id=snapshot.get("goal_id"))


class AutonomousAgentStatus(BaseModel):
    """Agent status from the autonomous runtime."""

    agent_id: str
    agent_type: str
    state: str
    message_count: int = 0
    error_count: int = 0
    mailbox_size: int = 0
    last_activity: str | None = None
    uptime_seconds: float = 0.0


class AutonomousStatusUpdate(BaseModel):
    """Request model for autonomous runtime status updates."""

    runtime_id: str
    agents: list[AutonomousAgentStatus]
    total_agents: int
    uptime_seconds: float = 0.0


class AnalysisRecordResponse(BaseModel):
    """Response model for a single analysis record."""

    id: str
    collected_at: str
    trigger_type: str | None = None
    metis_analyses: list[dict] = []
    empath_responses: list[dict] = []
    chronos_actions: list[dict] = []
    mediation_dispatched: bool = False


class AnalysisListResponse(BaseModel):
    """Response model for paginated analysis list."""

    items: list[AnalysisRecordResponse]
    total: int
    page: int
    limit: int
    pages: int


class AutonomousAgentsResponse(BaseModel):
    """Response model for autonomous agents query."""

    agents: list[AutonomousAgentStatus]
    total: int
    last_update: str | None
    healthy: bool


class TaskSnapshotResponse(BaseModel):
    """Response model for a single Chronos task snapshot."""

    task_id: str
    title: str
    status: str
    priority: str | None = None
    created_at: str | None = None
    scheduled_at: str | None = None
    assigned_to: str | None = None
    description: str | None = None
    tags: list[str] = []


class TaskListResponse(BaseModel):
    """Response model for paginated task list."""

    items: list[TaskSnapshotResponse]
    total: int
    page: int
    limit: int
    pages: int


class GoalSnapshotResponse(BaseModel):
    """Response model for a single goal pipeline snapshot."""

    goal_id: str
    title: str
    description: str | None = None
    status: str
    priority: str | None = None
    created_at: str | None = None
    updated_at: str | None = None
    votes_for: int = 0
    votes_against: int = 0
    outcome: str | None = None
    proposed_by: str | None = None


class GoalListResponse(BaseModel):
    """Response model for paginated goal list."""

    items: list[GoalSnapshotResponse]
    total: int
    page: int
    limit: int
    pages: int


class EventResponse(BaseModel):
    """Response model for a single timeline event."""

    id: str
    event_type: str
    collected_at: str
    source: str
    summary: str | None = None
    payload: dict[str, Any] = {}


class EventListResponse(BaseModel):
    """Response model for paginated events timeline."""

    items: list[EventResponse]
    total: int
    page: int
    limit: int
    pages: int


class ProposeGoalRequest(BaseModel):
    """Request model for proposing a goal."""

    title: str
    description: str
    priority: str | None = None
    tags: list[str] = []


class ProposeGoalResponse(BaseModel):
    """Response model after proposing a goal."""

    goal_id: str
    status: str
    message: str


@router.post("/agents", status_code=200)
async def register_autonomous_agents(
    update: AutonomousStatusUpdate,
) -> dict[str, str]:
    """
    Receive agent status update from autonomous runtime.

    The autonomous runtime calls this endpoint periodically to register
    its running agents. This data is cached and served to the frontend.

    Args:
        update: Status update from autonomous runtime
    """
    global _autonomous_agents, _last_update

    async with _cache_lock:
        _autonomous_agents = {agent.agent_id: agent.model_dump() for agent in update.agents}
        _last_update = datetime.now(UTC)

    logger.debug(
        "autonomous_agents_registered",
        runtime_id=update.runtime_id,
        agent_count=update.total_agents,
    )

    return {"status": "ok", "agents": str(update.total_agents)}


@router.get("/agents")
async def get_autonomous_agents() -> AutonomousAgentsResponse:
    """
    Get current autonomous agent statuses.

    Returns the cached list of agents running in the autonomous runtime.
    This is queried by the frontend to display agent health.

    Returns:
        List of autonomous agents with their statuses
    """
    async with _cache_lock:
        agents = list(_autonomous_agents.values())
        total = len(agents)

    # Determine health: agents are healthy if we have data less than 2 minutes old
    healthy = True
    if _last_update:
        age = (datetime.now(UTC) - _last_update).total_seconds()
        healthy = age < 120

    return AutonomousAgentsResponse(
        agents=[AutonomousAgentStatus(**a) for a in agents],
        total=total,
        last_update=_last_update.isoformat() if _last_update else None,
        healthy=healthy,
    )


@router.get("/analyses")
async def get_analyses(
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
) -> AnalysisListResponse:
    """
    Get paginated analysis history.

    Returns analysis records sorted by recency (most recent first).
    This is the main frontend entry point for viewing analysis history.

    Args:
        page: Page number (1-indexed)
        limit: Records per page (max 100)
    """
    async with _recents_lock:
        snapshot = list(reversed(_analysis_records))

    total = len(snapshot)
    pages = math.ceil(total / limit) if total > 0 else 1
    start = (page - 1) * limit
    items = snapshot[start : start + limit]

    return AnalysisListResponse(
        items=[AnalysisRecordResponse(**r) for r in items],
        total=total,
        page=page,
        limit=limit,
        pages=pages,
    )


@router.get("/analyses/{analysis_id}")
async def get_analysis_by_id(analysis_id: str) -> AnalysisRecordResponse:
    """
    Get a single analysis record by its ID.

    Args:
        analysis_id: UUID of the analysis record

    Raises:
        HTTPException 404 if not found
    """
    async with _recents_lock:
        for record in _analysis_records:
            if record.get("id") == analysis_id:
                return AnalysisRecordResponse(**record)
    raise HTTPException(status_code=404, detail="Analysis not found")


@router.get("/tasks", response_model=TaskListResponse)
async def get_tasks(
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
) -> TaskListResponse:
    """
    Get active Chronos task snapshots.

    Returns task snapshots posted by the Chronos runtime, sorted by
    recency (most recent first). This is the frontend entry point for
    the Active Tasks sub-view.

    Args:
        page: Page number (1-indexed)
        limit: Records per page (max 100)
    """
    async with _tasks_lock:
        snapshot = list(reversed(_tasks_buffer))

    total = len(snapshot)
    pages = math.ceil(total / limit) if total > 0 else 1
    start = (page - 1) * limit
    items = snapshot[start : start + limit]

    return TaskListResponse(
        items=[TaskSnapshotResponse(**t) for t in items],
        total=total,
        page=page,
        limit=limit,
        pages=pages,
    )


@router.get("/goals", response_model=GoalListResponse)
async def get_goals(
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
) -> GoalListResponse:
    """
    Get goal pipeline state snapshots.

    Returns goal lifecycle updates posted by the goal engine, sorted by
    recency (most recent first). This is the frontend entry point for
    the Goal Pipeline sub-view.

    Args:
        page: Page number (1-indexed)
        limit: Records per page (max 100)
    """
    async with _goals_lock:
        snapshot = list(reversed(_goals_buffer))

    total = len(snapshot)
    pages = math.ceil(total / limit) if total > 0 else 1
    start = (page - 1) * limit
    items = snapshot[start : start + limit]

    return GoalListResponse(
        items=[GoalSnapshotResponse(**g) for g in items],
        total=total,
        page=page,
        limit=limit,
        pages=pages,
    )


@router.get("/events", response_model=EventListResponse)
async def get_events(
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
) -> EventListResponse:
    """
    Get combined chronological timeline of analysis events.

    Builds a timeline from analysis records in the in-memory buffer,
    extracting key events from each record and combining them into a
    single chronological feed sorted most-recent-first.

    Each analysis record contributes:
      - An analysis event (type: "analysis_completed")
      - Per Metis analysis sub-event (type: "metis_analysis")
      - Per Empath response sub-event (type: "empath_response")
      - Per Chronos action sub-event (type: "chronos_action")
      - A mediation event if mediation_dispatched (type: "mediation_dispatched")

    Args:
        page: Page number (1-indexed)
        limit: Events per page (max 100)
    """
    async with _recents_lock:
        records_snapshot = list(reversed(_analysis_records))

    # Build combined timeline from analysis records
    events: list[dict[str, Any]] = []
    for record in records_snapshot:
        collected_at = record.get("collected_at", "")
        record_id = record.get("id", "")

        # Main analysis completed event
        events.append(
            {
                "id": f"{record_id}-analysis",
                "event_type": "analysis_completed",
                "collected_at": collected_at,
                "source": "autonomous_loop",
                "summary": record.get("trigger_type", "unknown"),
                "payload": {},
            }
        )

        # Per-Metis analysis events
        for i, ma in enumerate(record.get("metis_analyses", [])):
            events.append(
                {
                    "id": f"{record_id}-metis-{i}",
                    "event_type": "metis_analysis",
                    "collected_at": collected_at,
                    "source": "metis",
                    "summary": ma.get("analysis", ""),
                    "payload": ma,
                }
            )

        # Per-Empath response events
        for i, er in enumerate(record.get("empath_responses", [])):
            events.append(
                {
                    "id": f"{record_id}-empath-{i}",
                    "event_type": "empath_response",
                    "collected_at": collected_at,
                    "source": "empath",
                    "summary": er.get("sentiment", ""),
                    "payload": er,
                }
            )

        # Per-Chronos action events
        for i, ca in enumerate(record.get("chronos_actions", [])):
            events.append(
                {
                    "id": f"{record_id}-chronos-{i}",
                    "event_type": "chronos_action",
                    "collected_at": collected_at,
                    "source": "chronos",
                    "summary": ca.get("action", ""),
                    "payload": ca,
                }
            )

        # Mediation event
        if record.get("mediation_dispatched", False):
            events.append(
                {
                    "id": f"{record_id}-mediation",
                    "event_type": "mediation_dispatched",
                    "collected_at": collected_at,
                    "source": "mediator",
                    "summary": "Mediation dispatched",
                    "payload": {},
                }
            )

    total = len(events)
    pages = math.ceil(total / limit) if total > 0 else 1
    start = (page - 1) * limit
    items = events[start : start + limit]

    return EventListResponse(
        items=[EventResponse(**e) for e in items],
        total=total,
        page=page,
        limit=limit,
        pages=pages,
    )


@router.post("/propose-goal", response_model=ProposeGoalResponse, status_code=201)
async def propose_goal(request: ProposeGoalRequest) -> ProposeGoalResponse:
    """
    Propose a new goal for the goal pipeline.

    Accepts a goal proposal and pushes it into the goals buffer as a
    "proposed" snapshot. This simulates what the goal engine would do
    when a new goal is proposed via the dashboard or external trigger.

    In production, this would dispatch to the goal engine for voting
    and lifecycle management.

    Args:
        request: Goal proposal details

    Returns:
        Proposed goal with assigned goal_id and "proposed" status
    """
    goal_id = str(uuid.uuid4())
    now = datetime.now(UTC).isoformat()

    snapshot: dict[str, Any] = {
        "goal_id": goal_id,
        "title": request.title,
        "description": request.description,
        "status": "proposed",
        "priority": request.priority or "medium",
        "created_at": now,
        "updated_at": now,
        "votes_for": 0,
        "votes_against": 0,
        "outcome": None,
        "proposed_by": "dashboard",
    }

    await push_goal_snapshot(snapshot)

    logger.debug(
        "goal_proposed",
        goal_id=goal_id,
        title=request.title,
    )

    return ProposeGoalResponse(
        goal_id=goal_id,
        status="proposed",
        message=f"Goal '{request.title}' proposed successfully",
    )


@router.get("/status")
async def get_autonomous_status() -> dict[str, Any]:
    """
    Get autonomous runtime status.

    Returns basic status about the autonomous runtime connection
    and analysis record count.
    """
    async with _cache_lock:
        agent_count = len(_autonomous_agents)
    async with _recents_lock:
        total_analyses = len(_analysis_records)

    return {
        "connected": _last_update is not None,
        "agent_count": agent_count,
        "last_update": _last_update.isoformat() if _last_update else None,
        "total_analyses": total_analyses,
    }
