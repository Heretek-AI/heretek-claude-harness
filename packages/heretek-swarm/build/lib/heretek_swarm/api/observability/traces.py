"""Trace event endpoints for the observability API."""

from datetime import datetime
from typing import Any

import structlog
from fastapi import APIRouter, Depends, Query, WebSocket, WebSocketDisconnect

from heretek_swarm.gateway.auth import verify_auth

from . import (
    TraceEvent,
    _traces,
    connection_manager,
    get_zero_trust,
    validate_input,
)

logger = structlog.get_logger(__name__)
router = APIRouter(prefix="", tags=["observability"])


@router.get("/traces")
async def get_traces(
    agent_id: str | None = None,
    event_type: str | None = None,
    start_time: str | None = None,
    end_time: str | None = None,
    limit: int = Query(default=100, ge=1, le=1000),
    authenticated: str = Depends(verify_auth),
) -> dict[str, Any]:
    """Get trace events with optional filtering."""
    filtered_traces = []

    for traces in _traces.values():
        for trace in traces:
            if agent_id and trace.agent_id != agent_id:
                continue

            if event_type and trace.event_type != event_type:
                continue

            if start_time:
                trace_time = datetime.fromisoformat(trace.timestamp)
                start_dt = datetime.fromisoformat(start_time)
                if trace_time < start_dt:
                    continue

            if end_time:
                trace_time = datetime.fromisoformat(trace.timestamp)
                end_dt = datetime.fromisoformat(end_time)
                if trace_time > end_dt:
                    continue

            filtered_traces.append(trace)

            if len(filtered_traces) >= limit:
                break

    return {
        "events": [trace.to_dict() for trace in filtered_traces],
        "total": len(filtered_traces),
        "filtered": len(_traces.get(agent_id, [])) - len(filtered_traces),
    }


@router.get("/traces/{trace_id}")
async def get_trace(trace_id: str, authenticated: str = Depends(verify_auth)) -> dict[str, Any]:
    """Get a specific trace by ID."""
    for agent_traces in _traces.values():
        for trace in agent_traces:
            if trace.id == trace_id:
                return trace.to_dict()

    return {"error": "Trace not found"}


@router.post("/traces")
async def create_trace(
    event_type: str,
    agent_id: str,
    data: dict[str, Any],
    duration: float | None = None,
    authenticated: str = Depends(verify_auth),
) -> dict[str, Any]:
    """Create a new trace event."""
    validator = get_zero_trust()
    validate_input(
        validator, {"event_type": event_type, "agent_id": agent_id, "data": data}, "trace"
    )

    trace = TraceEvent(
        event_type=event_type,
        agent_id=agent_id,
        data=data,
        duration=duration,
    )

    if agent_id not in _traces:
        _traces[agent_id] = []

    _traces[agent_id].append(trace)

    await connection_manager.broadcast_trace(trace, agent_id)

    logger.info(
        "trace_created",
        trace_id=trace.id,
        event_type=event_type,
        agent_id=agent_id,
    )

    return trace.to_dict()


@router.websocket("/ws/traces/{agent_id}")
async def websocket_traces(websocket: WebSocket, agent_id: str):
    """WebSocket endpoint for real-time trace streaming."""
    await connection_manager.connect(websocket, agent_id)

    try:
        if agent_id in _traces:
            recent_traces = _traces[agent_id][-100:]
            for trace in recent_traces:
                await websocket.send_json(trace.to_dict())

        while True:
            try:
                _message = await websocket.receive_json()

            except WebSocketDisconnect:
                logger.info("websocket_disconnected", agent_id=agent_id)
                break
            except Exception as e:
                logger.error("websocket_error", agent_id=agent_id, error=str(e))
                await websocket.close()

    finally:
        await connection_manager.disconnect(websocket, agent_id)


@router.delete("/traces/{agent_id}")
async def clear_traces(agent_id: str, authenticated: str = Depends(verify_auth)) -> dict[str, Any]:
    """Clear all traces for an agent."""
    if agent_id in _traces:
        count = len(_traces[agent_id])
        del _traces[agent_id]
        logger.info("traces_cleared", agent_id=agent_id, count=count)
    else:
        count = 0

    return {
        "agent_id": agent_id,
        "cleared": count,
        "message": f"Cleared {count} traces for agent {agent_id}",
    }
