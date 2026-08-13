# =============================================================================
"""Routing rules management endpoints."""

from typing import Annotated, Any

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from heretek_swarm.gateway.auth import verify_auth
from heretek_swarm.gateway.content_router import (
    ContentFilter,
    ContentRouter,
    FilterOperator,
    RoutingRule,
    get_content_router,
)

logger = structlog.get_logger()
router = APIRouter()


class RoutingRuleCreate(BaseModel):
    """Request model for creating a routing rule."""

    id: str = Field(..., description="Unique rule identifier")
    name: str = Field(..., description="Human-readable rule name")
    priority: int = Field(..., description="Rule priority (higher evaluated first)")
    subject_pattern: str = Field(..., description="Wildcard pattern for subject")
    content_filters: list[dict[str, Any]] = Field(
        default_factory=list, description="Content filters"
    )
    target_channel: str = Field(..., description="Target channel for routed messages")
    target_agents: list[str] = Field(default_factory=list, description="Target agent IDs")
    enabled: bool = Field(default=True, description="Whether rule is active")
    description: str | None = Field(None, description="Optional rule description")


class RoutingRuleResponse(BaseModel):
    """Response model for routing rule."""

    id: str
    name: str
    priority: int
    subject_pattern: str
    content_filters: list[dict[str, Any]]
    target_channel: str
    target_agents: list[str]
    enabled: bool
    description: str | None


class RoutingRulesListResponse(BaseModel):
    """Response model for listing routing rules."""

    rules: list[RoutingRuleResponse]
    total: int
    active: int


class RoutingStatsResponse(BaseModel):
    """Response model for routing statistics."""

    messages_evaluated: int
    messages_matched: int
    messages_no_match: int
    errors: int
    active_rules: int
    total_rules: int
    uptime_seconds: float


def get_router_instance() -> ContentRouter:
    """Dependency to get the content router."""
    return get_content_router()


@router.get("/routing/rules")
async def list_routing_rules(
    router: Annotated[ContentRouter, Depends(get_router_instance)],
    authenticated: Annotated[str, Depends(verify_auth)],
    enabled_only: bool = False,
) -> RoutingRulesListResponse:
    """
    List all routing rules.

    Args:
        enabled_only: If True, only return enabled rules

    Returns:
        List of routing rules
    """
    try:
        rules_data = router.list_rules(enabled_only=enabled_only)
        active_count = len([r for r in rules_data if r.get("enabled", False)])

        return RoutingRulesListResponse(
            rules=[RoutingRuleResponse(**r) for r in rules_data],
            total=len(rules_data),
            active=active_count,
        )
    except Exception as e:
        logger.exception("Failed to list routing rules: {e}")
        raise HTTPException(500, f"Failed to list routing rules: {e!s}") from e


@router.get("/routing/rules/{rule_id}")
async def get_routing_rule(
    rule_id: str,
    router: Annotated[ContentRouter, Depends(get_router_instance)],
    authenticated: Annotated[str, Depends(verify_auth)],
) -> RoutingRuleResponse:
    """
    Get a specific routing rule by ID.

    Args:
        rule_id: Rule identifier

    Returns:
        Routing rule details
    """
    rule = router.get_rule(rule_id)

    if not rule:
        raise HTTPException(404, f"Routing rule '{rule_id}' not found")

    return RoutingRuleResponse(
        id=rule.id,
        name=rule.name,
        priority=rule.priority,
        subject_pattern=rule.subject_pattern,
        content_filters=[
            {"field": f.field, "operator": f.operator.value, "value": f.value}
            for f in rule.content_filters
        ],
        target_channel=rule.target_channel,
        target_agents=rule.target_agents,
        enabled=rule.enabled,
        description=rule.description,
    )


@router.post("/routing/rules")
async def create_routing_rule(
    rule_data: RoutingRuleCreate,
    router: Annotated[ContentRouter, Depends(get_router_instance)],
    authenticated: Annotated[str, Depends(verify_auth)],
) -> RoutingRuleResponse:
    """
    Create a new routing rule.

    Args:
        rule_data: Rule configuration

    Returns:
        Created rule details
    """
    try:
        # Convert content filters
        content_filters = []
        for cf in rule_data.content_filters:
            content_filters.append(
                ContentFilter(
                    field=cf["field"],
                    operator=FilterOperator(cf["operator"]),
                    value=cf["value"],
                )
            )

        # Create rule
        rule = RoutingRule(
            id=rule_data.id,
            name=rule_data.name,
            priority=rule_data.priority,
            subject_pattern=rule_data.subject_pattern,
            content_filters=content_filters,
            target_channel=rule_data.target_channel,
            target_agents=rule_data.target_agents,
            enabled=rule_data.enabled,
            description=rule_data.description,
        )

        # Add to router
        if not router.add_rule(rule):
            raise HTTPException(409, f"Routing rule '{rule_data.id}' already exists")

        logger.info(
            "routing_rule_created",
            rule_id=rule.id,
            name=rule.name,
            priority=rule.priority,
        )

        return RoutingRuleResponse(
            id=rule.id,
            name=rule.name,
            priority=rule.priority,
            subject_pattern=rule.subject_pattern,
            content_filters=[
                {"field": f.field, "operator": f.operator.value, "value": f.value}
                for f in rule.content_filters
            ],
            target_channel=rule.target_channel,
            target_agents=rule.target_agents,
            enabled=rule.enabled,
            description=rule.description,
        )
    except ValueError as e:
        raise HTTPException(400, str(e)) from e
    except Exception as e:
        logger.exception("Failed to create routing rule: {e}")
        raise HTTPException(500, f"Failed to create routing rule: {e!s}") from e


@router.put("/routing/rules/{rule_id}")
async def update_routing_rule(
    rule_id: str,
    rule_data: RoutingRuleCreate,
    router: Annotated[ContentRouter, Depends(get_router_instance)],
    authenticated: Annotated[str, Depends(verify_auth)],
) -> RoutingRuleResponse:
    """
    Update an existing routing rule.

    Args:
        rule_id: Rule identifier
        rule_data: Updated rule configuration

    Returns:
        Updated rule details
    """
    # Remove existing rule
    router.remove_rule(rule_id)

    # Convert content filters
    content_filters = []
    for cf in rule_data.content_filters:
        content_filters.append(
            ContentFilter(
                field=cf["field"],
                operator=FilterOperator(cf["operator"]),
                value=cf["value"],
            )
        )

    # Create updated rule
    rule = RoutingRule(
        id=rule_data.id,
        name=rule_data.name,
        priority=rule_data.priority,
        subject_pattern=rule_data.subject_pattern,
        content_filters=content_filters,
        target_channel=rule_data.target_channel,
        target_agents=rule_data.target_agents,
        enabled=rule_data.enabled,
        description=rule_data.description,
    )

    # Add to router
    if not router.add_rule(rule):
        raise HTTPException(500, "Failed to add updated rule")

    logger.info("routing_rule_updated", rule_id=rule_id)

    return RoutingRuleResponse(
        id=rule.id,
        name=rule.name,
        priority=rule.priority,
        subject_pattern=rule.subject_pattern,
        content_filters=[
            {"field": f.field, "operator": f.operator.value, "value": f.value}
            for f in rule.content_filters
        ],
        target_channel=rule.target_channel,
        target_agents=rule.target_agents,
        enabled=rule.enabled,
        description=rule.description,
    )


@router.delete("/routing/rules/{rule_id}")
async def delete_routing_rule(
    rule_id: str,
    router: Annotated[ContentRouter, Depends(get_router_instance)],
    authenticated: Annotated[str, Depends(verify_auth)],
) -> dict[str, str]:
    """
    Delete a routing rule.

    Args:
        rule_id: Rule identifier

    Returns:
        Confirmation message
    """
    try:
        if router.remove_rule(rule_id):
            logger.info("routing_rule_deleted", rule_id=rule_id)
            return {"message": f"Rule {rule_id} deleted successfully"}
        raise HTTPException(404, f"Rule {rule_id} not found")
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Failed to delete routing rule: {e}")
        raise HTTPException(500, f"Failed to delete routing rule: {e!s}") from e
