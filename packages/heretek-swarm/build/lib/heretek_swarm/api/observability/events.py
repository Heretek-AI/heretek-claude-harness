"""Message replay and time travel debugging endpoints for the observability API."""

import asyncio
from datetime import datetime
from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException

from heretek_swarm.gateway.auth import verify_auth

from . import (
    ReplayJobCreate,
    ReplayJobListResponse,
    ReplayJobResponse,
    TimeTravelRequestCreate,
    TimeTravelResponse,
    get_replay_manager,
)

logger = structlog.get_logger(__name__)
router = APIRouter(prefix="", tags=["observability"])


@router.post("/events/replay")
async def create_replay_job(
    job_data: ReplayJobCreate,
    replay_manager: Any | None = Depends(get_replay_manager),  # noqa: B008
    authenticated: str = Depends(verify_auth),
) -> ReplayJobResponse:
    """Create a new message replay job."""
    if not replay_manager:
        raise HTTPException(503, "Replay manager not available")

    try:
        start_time = None
        end_time = None

        if job_data.start_time:
            start_time = datetime.fromisoformat(job_data.start_time)
        if job_data.end_time:
            end_time = datetime.fromisoformat(job_data.end_time)

        job = await replay_manager.create_replay_job(
            stream_name=job_data.stream_name,
            start_sequence=job_data.start_sequence,
            end_sequence=job_data.end_sequence,
            start_time=start_time,
            end_time=end_time,
            subject_filter=job_data.subject_filter,
            destination_stream=job_data.destination_stream,
            replay_speed=job_data.replay_speed,
        )

        logger.info(
            "Replay job created",
            job_id=job.job_id,
            stream=job_data.stream_name,
        )

        return ReplayJobResponse(
            job_id=job.job_id,
            stream_name=job.stream_name,
            start_sequence=job.start_sequence,
            end_sequence=job.end_sequence,
            subject_filter=job.subject_filter,
            destination_stream=job.destination_stream,
            replay_speed=job.replay_speed,
            status=job.status.value,
            progress=job.progress,
            total=job.total,
            progress_percent=job.progress_percent,
            started_at=job.started_at.isoformat() if job.started_at else None,
            completed_at=job.completed_at.isoformat() if job.completed_at else None,
            error=job.error,
        )
    except Exception as e:
        logger.exception("Failed to create replay job: {e}")
        raise HTTPException(500, f"Failed to create replay job: {e!s}") from e


@router.post("/events/replay/{job_id}/execute")
async def execute_replay_job(
    job_id: str,
    replay_manager: Any | None = Depends(get_replay_manager),  # noqa: B008
    authenticated: str = Depends(verify_auth),
) -> dict[str, Any]:
    """Execute a replay job."""
    if not replay_manager:
        raise HTTPException(503, "Replay manager not available")

    job = replay_manager.get_job(job_id)
    if not job:
        raise HTTPException(404, f"Replay job '{job_id}' not found")

    try:
        asyncio.create_task(replay_manager.execute_replay(job))  # noqa: RUF006

        return {
            "status": "started",
            "job_id": job_id,
            "message": "Replay job started",
        }
    except Exception as e:
        logger.exception("Failed to execute replay job: {e}")
        raise HTTPException(500, f"Failed to execute replay job: {e!s}") from e


@router.post("/events/replay/{job_id}/pause")
async def pause_replay_job(
    job_id: str,
    replay_manager: Any | None = Depends(get_replay_manager),  # noqa: B008
    authenticated: str = Depends(verify_auth),
) -> dict[str, str]:
    """Pause a replay job."""
    if not replay_manager:
        raise HTTPException(503, "Replay manager not available")

    if not await replay_manager.pause_replay(job_id):
        raise HTTPException(400, f"Failed to pause job '{job_id}'")

    return {"status": "paused", "job_id": job_id}


@router.post("/events/replay/{job_id}/resume")
async def resume_replay_job(
    job_id: str,
    replay_manager: Any | None = Depends(get_replay_manager),  # noqa: B008
    authenticated: str = Depends(verify_auth),
) -> dict[str, str]:
    """Resume a paused replay job."""
    if not replay_manager:
        raise HTTPException(503, "Replay manager not available")

    if not await replay_manager.resume_replay(job_id):
        raise HTTPException(400, f"Failed to resume job '{job_id}'")

    return {"status": "resumed", "job_id": job_id}


@router.post("/events/replay/{job_id}/cancel")
async def cancel_replay_job(
    job_id: str,
    replay_manager: Any | None = Depends(get_replay_manager),  # noqa: B008
    authenticated: str = Depends(verify_auth),
) -> dict[str, str]:
    """Cancel a replay job."""
    if not replay_manager:
        raise HTTPException(503, "Replay manager not available")

    if not await replay_manager.cancel_replay(job_id):
        raise HTTPException(400, f"Failed to cancel job '{job_id}'")

    return {"status": "cancelled", "job_id": job_id}


@router.get("/events/replay")
async def list_replay_jobs(
    active_only: bool = False,
    replay_manager: Any | None = Depends(get_replay_manager),  # noqa: B008
    authenticated: str = Depends(verify_auth),
) -> ReplayJobListResponse:
    """List all replay jobs."""
    if not replay_manager:
        raise HTTPException(503, "Replay manager not available")

    try:
        jobs = replay_manager.get_all_jobs()

        if active_only:
            jobs = replay_manager.active_jobs

        active_count = len(replay_manager.active_jobs)

        return ReplayJobListResponse(
            jobs=[
                ReplayJobResponse(
                    job_id=job.job_id,
                    stream_name=job.stream_name,
                    start_sequence=job.start_sequence,
                    end_sequence=job.end_sequence,
                    subject_filter=job.subject_filter,
                    destination_stream=job.destination_stream,
                    replay_speed=job.replay_speed,
                    status=job.status.value,
                    progress=job.progress,
                    total=job.total,
                    progress_percent=job.progress_percent,
                    started_at=job.started_at.isoformat() if job.started_at else None,
                    completed_at=job.completed_at.isoformat() if job.completed_at else None,
                    error=job.error,
                )
                for job in jobs
            ],
            total=len(jobs),
            active=active_count,
        )
    except Exception as e:
        logger.exception("Failed to list replay jobs: {e}")
        raise HTTPException(500, f"Failed to list replay jobs: {e!s}") from e


@router.get("/events/replay/{job_id}")
async def get_replay_job(
    job_id: str,
    replay_manager: Any | None = Depends(get_replay_manager),  # noqa: B008
    authenticated: str = Depends(verify_auth),
) -> ReplayJobResponse:
    """Get details of a specific replay job."""
    if not replay_manager:
        raise HTTPException(503, "Replay manager not available")

    job = replay_manager.get_job(job_id)
    if not job:
        raise HTTPException(404, f"Replay job '{job_id}' not found")

    return ReplayJobResponse(
        job_id=job.job_id,
        stream_name=job.stream_name,
        start_sequence=job.start_sequence,
        end_sequence=job.end_sequence,
        subject_filter=job.subject_filter,
        destination_stream=job.destination_stream,
        replay_speed=job.replay_speed,
        status=job.status.value,
        progress=job.progress,
        total=job.total,
        progress_percent=job.progress_percent,
        started_at=job.started_at.isoformat() if job.started_at else None,
        completed_at=job.completed_at.isoformat() if job.completed_at else None,
        error=job.error,
    )


@router.post("/events/time-travel")
async def create_time_travel_request(
    request_data: TimeTravelRequestCreate,
    replay_manager: Any | None = Depends(get_replay_manager),  # noqa: B008
    authenticated: str = Depends(verify_auth),
) -> dict[str, Any]:
    """Create a time travel debugging request."""
    if not replay_manager:
        raise HTTPException(503, "Replay manager not available")

    try:
        target_time = datetime.fromisoformat(request_data.target_time)

        request = await replay_manager.create_time_travel_request(
            entity_id=request_data.entity_id,
            entity_type=request_data.entity_type,
            target_time=target_time,
            source_stream=request_data.source_stream,
            include_snapshots=request_data.include_snapshots,
        )

        return {
            "request_id": request.request_id,
            "entity_id": request.entity_id,
            "entity_type": request.entity_type,
            "target_time": request.target_time.isoformat(),
            "source_stream": request.source_stream,
            "status": "created",
        }
    except Exception as e:
        logger.exception("Failed to create time travel request: {e}")
        raise HTTPException(500, f"Failed to create time travel request: {e!s}") from e


@router.post("/events/time-travel/{request_id}/execute")
async def execute_time_travel(
    request_id: str,
    replay_manager: Any | None = Depends(get_replay_manager),  # noqa: B008
    authenticated: str = Depends(verify_auth),
) -> TimeTravelResponse:
    """Execute time travel state reconstruction."""
    if not replay_manager:
        raise HTTPException(503, "Replay manager not available")

    request = replay_manager._time_travel_requests.get(request_id)  # noqa: SLF001
    if not request:
        raise HTTPException(404, f"Time travel request '{request_id}' not found")

    try:

        def state_applier(state: dict[str, Any], event: Any) -> dict[str, Any]:
            """Apply event to state."""
            if hasattr(event, "payload"):
                state.update(event.payload)
            return state

        state = await replay_manager.execute_time_travel(request, state_applier)

        events_applied = len(state.get("_events_applied", [])) if isinstance(state, dict) else 0
        snapshot_used = state.get("_snapshot_used", False) if isinstance(state, dict) else False

        return TimeTravelResponse(
            request_id=request_id,
            entity_id=request.entity_id,
            entity_type=request.entity_type,
            target_time=request.target_time.isoformat(),
            state=state,
            events_applied=events_applied,
            snapshot_used=snapshot_used,
        )
    except Exception as e:
        logger.exception("Failed to execute time travel: {e}")
        raise HTTPException(500, f"Failed to execute time travel: {e!s}") from e


@router.get("/events/stats")
async def get_event_stats(
    replay_manager: Any | None = Depends(get_replay_manager),  # noqa: B008
    authenticated: str = Depends(verify_auth),
) -> dict[str, Any]:
    """Get event replay statistics."""
    if not replay_manager:
        raise HTTPException(503, "Replay manager not available")

    try:
        return await replay_manager.get_stats()
    except Exception as e:
        logger.exception("Failed to get event stats: {e}")
        raise HTTPException(500, f"Failed to get event stats: {e!s}") from e
