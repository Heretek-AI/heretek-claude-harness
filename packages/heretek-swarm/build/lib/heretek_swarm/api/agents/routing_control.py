"""Routing control endpoints."""

from typing import Annotated, Any

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from heretek_swarm.gateway.auth import verify_auth
from heretek_swarm.gateway.content_router import ContentRouter, get_content_router

logger = structlog.get_logger()
router = APIRouter()


class RoutingStatsResponse(BaseModel):
    """Response model for routing statistics."""

    total_rules: int
    enabled_rules: int
    disabled_rules: int
    messages_routed: int
    routing_errors: int


async def delete_routing_rule(
    rule_id: str,
    router: Annotated[ContentRouter, Depends(get_content_router)],
    authenticated: Annotated[str, Depends(verify_auth)],
) -> dict[str, str]:
    """
    Delete a routing rule.

    Args:
        rule_id: Rule identifier

    Returns:
        Success status
    """
    if not router.remove_rule(rule_id):
        raise HTTPException(404, f"Routing rule '{rule_id}' not found")

    logger.info("routing_rule_deleted", rule_id=rule_id)

    return {"status": "success", "message": f"Deleted rule '{rule_id}'"}


@router.post("/routing/rules/{rule_id}/enable")
async def enable_routing_rule(
    rule_id: str,
    router: Annotated[ContentRouter, Depends(get_content_router)],
    authenticated: Annotated[str, Depends(verify_auth)],
) -> dict[str, str]:
    """Enable a routing rule."""
    if not router.enable_rule(rule_id):
        raise HTTPException(404, f"Routing rule '{rule_id}' not found")

    return {"status": "success", "message": f"Enabled rule '{rule_id}'"}


@router.post("/routing/rules/{rule_id}/disable")
async def disable_routing_rule(
    rule_id: str,
    router: Annotated[ContentRouter, Depends(get_content_router)],
    authenticated: Annotated[str, Depends(verify_auth)],
) -> dict[str, str]:
    """Disable a routing rule."""
    if not router.disable_rule(rule_id):
        raise HTTPException(404, f"Routing rule '{rule_id}' not found")

    return {"status": "success", "message": f"Disabled rule '{rule_id}'"}


@router.get("/routing/stats")
async def get_routing_stats(
    router: Annotated[ContentRouter, Depends(get_content_router)],
    authenticated: Annotated[str, Depends(verify_auth)],
) -> RoutingStatsResponse:
    """
    Get routing statistics.

    Returns statistics about message routing and rule evaluation.
    """
    try:
        stats = router.get_stats()
        return RoutingStatsResponse(**stats)
    except Exception as e:
        logger.exception("Failed to get routing stats: {e}")
        raise HTTPException(500, f"Failed to get routing stats: {e!s}") from e


@router.post("/routing/evaluate")
async def evaluate_routing(
    subject: str,
    payload: dict[str, Any],
    router: Annotated[ContentRouter, Depends(get_content_router)],
    authenticated: Annotated[str, Depends(verify_auth)],
    correlation_id: str | None = None,
) -> dict[str, Any]:
    """
    Evaluate routing for a message (test endpoint).

    Args:
        subject: Message subject
        payload: Message payload
        correlation_id: Optional correlation ID

    Returns:
        Routing decision details
    """
    try:
        decision = router.route(
            subject=subject,
            payload=payload,
            correlation_id=correlation_id,
        )

        return {
            "decision": decision.decision.value,
            "matched_rule": {
                "id": decision.matched_rule.id,
                "name": decision.matched_rule.name,
                "target_channel": decision.matched_rule.target_channel,
                "target_agents": decision.matched_rule.target_agents,
            }
            if decision.matched_rule
            else None,
            "correlation_id": decision.correlation_id,
            "evaluation_time_ms": decision.evaluation_time_ms,
            "filters_evaluated": decision.filters_evaluated,
            "filters_matched": decision.filters_matched,
        }
    except Exception as e:
        logger.exception("Failed to evaluate routing: {e}")
        raise HTTPException(500, f"Failed to evaluate routing: {e!s}") from e


# =============================================================================
# Behavior Profiling Endpoints
# =============================================================================
