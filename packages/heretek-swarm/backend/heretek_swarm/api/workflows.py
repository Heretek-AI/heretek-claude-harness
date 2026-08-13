"""
Workflows API - Workflow management endpoints

Provides REST API for:
- Creating workflows from Canvas UI
- Listing workflows
- Executing workflows
- Getting workflow status
- Deleting workflows
- Validating workflows
- Workflow execution events (SSE)
"""

import asyncio
import json
import uuid
from collections.abc import AsyncGenerator
from datetime import UTC, datetime
from typing import Annotated, Any

import structlog
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse

from heretek_swarm.gateway.auth import verify_auth
from heretek_swarm.workflow.engine import get_workflow_engine
from heretek_swarm.workflow.execution_events import get_execution_event_bus
from heretek_swarm.workflow.models import WorkflowStatus
from heretek_swarm.workflow.validator import WorkflowValidator

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/api/workflows", tags=["workflows"])


def _serialize_node_results(node_results: dict[str, Any]) -> dict[str, Any]:
    """
    Serialize node_results dict for JSON response.

    NodeResult dataclass contains Exception objects which Pydantic cannot serialize.
    Converts to JSON-safe dict with error as string.
    """
    result = {}
    for key, val in node_results.items():
        if hasattr(val, "__dict__"):
            # dataclass-like object — convert to dict
            d = vars(val).copy() if hasattr(val, "__dict__") else {}
            if "error" in d and isinstance(d["error"], Exception):
                d["error"] = str(d["error"])
            if "output" in d and not isinstance(
                d["output"], (str, int, float, bool, list, dict, type(None))
            ):
                d["output"] = str(d["output"])
            result[key] = d
        else:
            result[key] = val
    return result


@router.post("", status_code=201)
async def create_workflow(
    workflow_definition: dict[str, Any], authenticated: Annotated[str, Depends(verify_auth)]
) -> dict[str, Any]:
    """
    Create a new workflow from Canvas UI definition.

    Args:
        workflow_definition: Workflow definition from Canvas UI
        authenticated: Authentication token

    Returns:
        Created workflow with ID
    """
    engine = await get_workflow_engine()

    # Create workflow from definition (load_workflow persists to disk)
    workflow = await engine.load_workflow(workflow_definition)

    logger.info("workflow_created", workflow_id=workflow.id, name=workflow.name)

    return {
        "id": workflow.id,
        "name": workflow.name,
        "created_at": workflow.created_at,
        "state": WorkflowStatus.PENDING.value,
    }


@router.get("", status_code=200)
async def list_workflows(authenticated: Annotated[str, Depends(verify_auth)]) -> dict[str, Any]:
    """
    List all workflows.

    Args:
        authenticated: Authentication token

    Returns:
        List of workflows
    """
    engine = await get_workflow_engine()

    return {
        "workflows": [
            {
                "id": workflow_id,
                "name": workflow.name,
                "created_at": workflow.created_at,
                "state": WorkflowStatus.PENDING.value,
            }
            for workflow_id, workflow in engine.workflows.items()
        ]
    }


@router.get("/{workflow_id}", status_code=200)
async def get_workflow(
    workflow_id: str, authenticated: Annotated[str, Depends(verify_auth)]
) -> dict[str, Any]:
    """
    Get a specific workflow by ID.

    Args:
        workflow_id: Workflow ID
        authenticated: Authentication token

    Returns:
        Workflow definition
    """
    engine = await get_workflow_engine()

    workflow = engine.get_workflow(workflow_id)
    if workflow is None:
        raise HTTPException(status_code=404, detail=_WORKFLOW_NOT_FOUND)

    return {
        "id": workflow.id,
        "name": workflow.name,
        "nodes": [
            {
                "id": n.id,
                "type": n.type,
                "data": n.data,
                "inputs": n.inputs,
                "outputs": n.outputs,
                "position": n.position,
            }
            for n in workflow.nodes
        ],
        "edges": [
            {
                "id": e.id,
                "source": e.source,
                "target": e.target,
                "condition": e.condition,
            }
            for e in workflow.edges
        ],
        "metadata": workflow.metadata,
        "created_at": workflow.created_at,
        "state": WorkflowStatus.PENDING.value,
    }


@router.post("/{workflow_id}/execute", status_code=201)
async def execute_workflow(
    workflow_id: str,
    input_data: dict[str, Any],
    authenticated: Annotated[str, Depends(verify_auth)],
    strategy: str = "dag",
) -> dict[str, Any]:
    """
    Execute a workflow.

    Args:
        workflow_id: Workflow ID
        input_data: Input data for workflow
        authenticated: Authentication token
        strategy: Execution strategy - "dag" (default), "cycle", "majority_vote"
                  - dag: Topological sort (dependency order)
                  - cycle: Feedback loop with convergence monitoring
                  - majority_vote: Parallel execution with vote aggregation

    Returns:
        Execution result
    """
    engine = await get_workflow_engine()

    if engine.get_workflow(workflow_id) is None:
        raise HTTPException(status_code=404, detail=_WORKFLOW_NOT_FOUND)

    result = await engine.execute_workflow(
        workflow_id=workflow_id,
        input_data=input_data,
        strategy=strategy,
    )

    logger.info(
        "workflow_executed",
        workflow_id=workflow_id,
        strategy=strategy,
        status=result.status,
    )

    return {
        "execution_id": result.execution_id,
        "workflow_id": workflow_id,
        "status": result.status.value if hasattr(result.status, "value") else str(result.status),
        "node_results": _serialize_node_results(result.node_results),
        "variables": result.variables,
        "start_time": result.start_time.isoformat(),
        "end_time": result.end_time.isoformat() if result.end_time else None,
        "error": str(result.error) if result.error else None,
    }


@router.put("/{workflow_id}", status_code=200)
async def update_workflow(
    workflow_id: str,
    workflow_definition: dict[str, Any],
    authenticated: Annotated[str, Depends(verify_auth)],
) -> dict[str, Any]:
    """Update an existing workflow definition.

    Canvas uses this for save-as-you-type persistence.

    Args:
        workflow_id: Workflow ID to update.
        workflow_definition: New workflow definition.
        authenticated: Authentication token.

    Returns:
        Updated workflow metadata.
    """
    engine = await get_workflow_engine()

    try:
        workflow = await engine.update_workflow(workflow_id, workflow_definition)
    except ValueError:
        raise HTTPException(status_code=404, detail=_WORKFLOW_NOT_FOUND)

    logger.info("workflow_updated", workflow_id=workflow.id, name=workflow.name)

    return {
        "id": workflow.id,
        "name": workflow.name,
        "created_at": workflow.created_at,
        "state": WorkflowStatus.PENDING.value,
    }


@router.delete("/{workflow_id}")
async def delete_workflow(workflow_id: str, authenticated: Annotated[str, Depends(verify_auth)]):
    """
    Delete a workflow.

    Args:
        workflow_id: Workflow ID
        authenticated: Authentication token

    Returns:
        204 No Content on success
    """
    engine = await get_workflow_engine()

    if not engine.delete_workflow(workflow_id):
        raise HTTPException(status_code=404, detail=_WORKFLOW_NOT_FOUND)


@router.get("/{workflow_id}/status", status_code=200)
async def get_workflow_status(
    workflow_id: str, authenticated: Annotated[str, Depends(verify_auth)]
) -> dict[str, Any]:
    """
    Get status of a workflow execution.

    Args:
        workflow_id: Workflow ID
        authenticated: Authentication token

    Returns:
        Current execution status
    """
    engine = await get_workflow_engine()

    execution_id = f"exec_{workflow_id}_{uuid.uuid4().hex[:8]}"

    context = engine.active_executions.get(execution_id)

    if not context:
        return {
            "workflow_id": workflow_id,
            "status": WorkflowStatus.PENDING.value,
            "execution_id": None,
        }

    return {
        "workflow_id": workflow_id,
        "status": context.state.value,
        "execution_id": context.execution_id,
        "node_results": context.node_results,
        "variables": context.variables,
        "start_time": context.start_time.isoformat(),
        "end_time": context.end_time.isoformat() if context.end_time else None,
        "error": str(context.error) if context.error else None,
    }


@router.post("/{workflow_id}/cancel", status_code=200)
async def cancel_workflow(
    workflow_id: str, authenticated: Annotated[str, Depends(verify_auth)]
) -> dict[str, Any]:
    """
    Cancel a running workflow execution.

    Args:
        workflow_id: Workflow ID
        authenticated: Authentication token

    Returns:
        Cancellation confirmation
    """
    engine = await get_workflow_engine()

    execution_id = f"exec_{workflow_id}_{uuid.uuid4().hex[:8]}"

    success = await engine.cancel_workflow(execution_id)

    if success:
        return {"message": f"Workflow execution {execution_id} cancelled"}
    return {"message": f"Failed to cancel workflow execution {execution_id}"}


@router.post("/{workflow_id}/validate", status_code=200)
async def validate_workflow_endpoint(
    workflow_id: str, authenticated: Annotated[str, Depends(verify_auth)]
) -> dict[str, Any]:
    """
    Validate a workflow graph before execution.

    Checks for:
    - Disconnected nodes (no input/output connections)
    - Circular dependencies (beyond allowed loops)
    - Missing required connections
    - Invalid agent types
    - Resource conflicts

    Args:
        workflow_id: Workflow ID to validate
        authenticated: Authentication token

    Returns:
        Validation result with errors, warnings, and info messages
    """
    engine = await get_workflow_engine()

    workflow = engine.get_workflow(workflow_id)
    if workflow is None:
        raise HTTPException(status_code=404, detail=_WORKFLOW_NOT_FOUND)

    # Convert workflow to validation format
    workflow_definition = {
        "id": workflow.id,
        "name": workflow.name,
        "nodes": [
            {
                "id": node.id,
                "type": node.type,
                "data": node.data,
                "position": node.position,
            }
            for node in workflow.nodes
        ],
        "edges": [
            {
                "id": edge.id,
                "source": edge.source,
                "target": edge.target,
                "condition": edge.condition,
            }
            for edge in workflow.edges
        ],
    }

    # Validate
    validator = WorkflowValidator()
    result = validator.validate(workflow_definition)

    logger.info(
        "workflow_validated",
        workflow_id=workflow_id,
        valid=result.valid,
        error_count=len(result.errors),
        warning_count=len(result.warnings),
    )

    return result.to_dict()


@router.post("/validate", status_code=200)
async def validate_workflow_draft(
    workflow_definition: dict[str, Any], authenticated: Annotated[str, Depends(verify_auth)]
) -> dict[str, Any]:
    """
    Validate a workflow definition (draft mode).

    Useful for validating workflows before saving them.

    Args:
        workflow_definition: Workflow definition to validate
        authenticated: Authentication token

    Returns:
        Validation result with errors, warnings, and info messages
    """
    validator = WorkflowValidator()
    result = validator.validate(workflow_definition)

    logger.info(
        "workflow_draft_validated",
        valid=result.valid,
        error_count=len(result.errors),
        warning_count=len(result.warnings),
    )

    return result.to_dict()


# =============================================================================
# SSE Endpoint for Workflow Events
# =============================================================================


def _resolve_execution_ids(
    engine: Any,
    workflow_id: str | None,
    execution_id: str | None,
) -> list[str]:
    """Resolve execution IDs to watch from engine state."""
    if execution_id:
        return [execution_id]
    ids: list[str] = []
    for exec_id, ctx in engine.active_executions.items():
        if workflow_id is None or ctx.workflow_id == workflow_id:
            ids.append(exec_id)
    if not ids and workflow_id:
        ids = [
            exec_id
            for exec_id, events in get_execution_event_bus()._history.items()
            if events and events[-1].get("workflow_id") == workflow_id
        ]
    return ids


async def _stream_workflow_events(
    *,
    workflow_id: str | None = None,
    execution_id: str | None = None,
) -> AsyncGenerator[str, None]:
    """Yield SSE payloads from the workflow execution event bus."""
    engine = await get_workflow_engine()
    bus = get_execution_event_bus()
    watch_ids = _resolve_execution_ids(engine, workflow_id, execution_id)
    seen: set[tuple[str, str]] = set()
    event_count = 0

    connected = {
        "status": "connected",
        "execution_id": execution_id or (watch_ids[0] if watch_ids else None),
        "workflow_id": workflow_id,
        "message": "SSE connection established",
        "timestamp": datetime.now(UTC).isoformat(),
    }
    yield f"data: {json.dumps(connected)}\n\n"

    try:
        while True:
            emitted = False
            for exec_id in watch_ids:
                for event in bus.get_history(exec_id):
                    key = (exec_id, event.get("timestamp", ""))
                    if key in seen:
                        continue
                    seen.add(key)
                    event_count += 1
                    emitted = True
                    yield f"data: {json.dumps(event)}\n\n"
                    if event.get("status") in ("completed", "failed", "cancelled"):
                        return

            if not emitted:
                await asyncio.sleep(0.5)
                watch_ids = _resolve_execution_ids(engine, workflow_id, execution_id)
                if not watch_ids and event_count > 0:
                    return
    except asyncio.CancelledError:
        cancelled = {
            "status": "cancelled",
            "execution_id": execution_id,
            "message": "SSE connection closed by client",
            "timestamp": datetime.now(UTC).isoformat(),
        }
        yield f"data: {json.dumps(cancelled)}\n\n"


@router.get("/events", response_class=StreamingResponse)
async def workflow_events_stream(
    authenticated: Annotated[str, Depends(verify_auth)],
    workflow_id: str | None = Query(None, description="Filter events by workflow ID"),
    execution_id: str | None = Query(None, description="Watch a specific execution ID"),
) -> StreamingResponse:
    """
    SSE endpoint for streaming workflow execution events.

    Events are sent as Server-Sent Events with JSON payloads:
    - status: "started" | "running" | "completed" | "failed"
    - currentNode: Node ID currently executing (or null)
    - progress: 0-100 percentage
    - message: Human-readable status message
    - timestamp: ISO format timestamp
    - workflow_id: Workflow ID (if filtered)
    - execution_id: Execution ID for this run

    Args:
        workflow_id: Optional workflow ID to filter events
        authenticated: Authentication token

    Returns:
        StreamingResponse with text/event-stream content type
    """
    return StreamingResponse(
        _stream_workflow_events(workflow_id=workflow_id, execution_id=execution_id),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.get("/{workflow_id}/events", response_class=StreamingResponse)
async def workflow_specific_events_stream(
    workflow_id: str,
    authenticated: Annotated[str, Depends(verify_auth)],
    execution_id: str | None = Query(None, description="Optional execution ID to watch"),
) -> StreamingResponse:
    """
    SSE endpoint for streaming events from a specific workflow execution.

    Args:
        workflow_id: Workflow ID to stream events for
        authenticated: Authentication token

    Returns:
        StreamingResponse with text/event-stream content type
    """
    engine = await get_workflow_engine()
    if workflow_id not in engine.workflows:
        raise HTTPException(status_code=404, detail=_WORKFLOW_NOT_FOUND)

    return StreamingResponse(
        _stream_workflow_events(workflow_id=workflow_id, execution_id=execution_id),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
# Error detail constants (extracted to avoid duplicate literals)
_WORKFLOW_NOT_FOUND = "Workflow not found"
