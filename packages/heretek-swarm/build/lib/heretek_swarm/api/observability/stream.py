"""Real-time metrics stream endpoints for the observability API."""

import asyncio
import uuid
from datetime import UTC, datetime
from typing import Any

import structlog
from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Query,
    Request,
    WebSocket,
    WebSocketDisconnect,
)
from fastapi.responses import PlainTextResponse

from heretek_swarm.gateway.auth import verify_auth
from heretek_swarm.security.zero_trust import LayerResult, ZeroTrustResult

from . import (
    check_rate_limit,
    get_metrics_stream,
    get_zero_trust,
)

logger = structlog.get_logger(__name__)
router = APIRouter(prefix="", tags=["observability"])


@router.get("/metrics/stream")
async def stream_metrics(
    request: Request,
    interval: int = Query(default=5, ge=1, le=60, description="Stream interval in seconds"),
    authenticated: str = Depends(verify_auth),
) -> dict[str, Any]:
    """Get real-time metrics snapshot (non-streaming HTTP version).

    For WebSocket streaming, use /ws/metrics endpoint.
    """
    client_id = request.client.host if request.client else "unknown"
    if not check_rate_limit(client_id):
        raise HTTPException(status_code=429, detail="Rate limit exceeded")

    validator = get_zero_trust()
    request_id = str(uuid.uuid4())
    audit_result = ZeroTrustResult(
        passed=True,
        layer1=LayerResult(layer="input_validation", passed=True),
        layer2=LayerResult(layer="context_validation", passed=True),
        layer3=LayerResult(layer="output_validation", passed=True),
        layer4=LayerResult(layer="audit_logging", passed=True),
        request_id=request_id,
    )
    validator.audit_logger.log(
        event_type="api_call",
        result=audit_result,
        additional_context={
            "endpoint": "/api/v1/observability/metrics/stream",
            "client_id": client_id,
            "method": "GET",
        },
    )

    stream = get_metrics_stream()
    snapshot = stream.get_metrics_snapshot()

    return {
        **snapshot.to_dict(),
        "stream_interval_seconds": interval,
    }


@router.websocket("/ws/metrics")
async def websocket_metrics(websocket: WebSocket, interval: int = 5):
    """WebSocket endpoint for real-time metrics streaming."""
    await websocket.accept()

    validator = get_zero_trust()
    validator.audit_log(
        event_type="websocket_connected",
        event_data={
            "endpoint": "/api/v1/observability/ws/metrics",
            "interval": interval,
        },
    )

    stream = get_metrics_stream()

    try:
        while True:
            try:
                swarm = stream._collector.collect_swarm_metrics()  # noqa: SLF001
                consciousness = stream._collector.collect_consciousness_metrics()  # noqa: SLF001
                agents = stream._collector.get_all_agent_metrics()  # noqa: SLF001
                health = stream._collector.calculate_health_score()  # noqa: SLF001

                await websocket.send_json(
                    {
                        "swarm_metrics": swarm.to_dict(),
                        "consciousness_metrics": consciousness.to_dict(),
                        "agent_metrics": {k: v.to_dict() for k, v in agents.items()},
                        "health_score": health,
                        "timestamp": datetime.now(UTC).isoformat(),
                    }
                )

                try:
                    async with asyncio.timeout(interval):
                        message = await websocket.receive_text()
                        if message == "stop":
                            break
                except TimeoutError:
                    logger.debug("Stream timeout during wait, continuing")

            except WebSocketDisconnect:
                logger.info("websocket_disconnected")
                break
            except Exception as e:
                logger.error("websocket_error", error=str(e))
                await websocket.close()
                break

    finally:
        request_id = str(uuid.uuid4())
        audit_result = ZeroTrustResult(
            passed=True,
            layer1=LayerResult(layer="input_validation", passed=True),
            layer2=LayerResult(layer="context_validation", passed=True),
            layer3=LayerResult(layer="output_validation", passed=True),
            layer4=LayerResult(layer="audit_logging", passed=True),
            request_id=request_id,
        )
        validator.audit_logger.log(
            event_type="websocket_disconnected",
            result=audit_result,
            additional_context={"endpoint": "/api/v1/observability/ws/metrics"},
        )


@router.get("/metrics/prometheus")
async def get_prometheus_metrics(
    request: Request, authenticated: str = Depends(verify_auth)
) -> PlainTextResponse:
    """Get metrics in Prometheus text format."""
    client_id = request.client.host if request.client else "unknown"
    if not check_rate_limit(client_id):
        raise HTTPException(status_code=429, detail="Rate limit exceeded")

    stream = get_metrics_stream()
    prometheus_data = stream.export_prometheus_format()

    return PlainTextResponse(
        content=prometheus_data,
        media_type="text/plain; version=0.0.4",
    )


@router.get("/metrics/legacy")
async def get_legacy_metrics(authenticated: str = Depends(verify_auth)) -> dict[str, Any]:
    """Get legacy observability metrics (backward compatibility)."""
    from . import _traces, connection_manager

    total_events = 0
    events_by_type: dict[str, int] = {}
    events_by_agent: dict[str, int] = {}

    for agent_traces in _traces.values():
        for trace in agent_traces:
            total_events += 1
            events_by_type[trace.event_type] = events_by_type.get(trace.event_type, 0) + 1
            events_by_agent[trace.agent_id] = events_by_agent.get(trace.agent_id, 0) + 1

    avg_duration = 0
    if total_events > 0:
        total_duration = sum(
            trace.duration or 0 for traces in _traces.values() for trace in traces
        )
        avg_duration = total_duration / total_events

    return {
        "total_events": total_events,
        "events_by_type": events_by_type,
        "events_by_agent": events_by_agent,
        "average_duration_ms": round(avg_duration, 2),
        "active_connections": len(connection_manager.active_connections),
        "timestamp": datetime.now(UTC).isoformat(),
    }
