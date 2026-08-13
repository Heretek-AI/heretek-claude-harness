"""
Arbiter Handlers - Event handlers and responses.

This module contains:
- Message handler registration
- All _handle_* methods for processing incoming messages
- Response and error sending helpers
"""

from datetime import UTC, datetime

import structlog
from pydantic import ValidationError

from heretek_swarm.actors.base import ActorMessage
from heretek_swarm.actors.validation import validate_message

from .agent import (
    ArbiterAgent,
    Conflict,
    ConflictSeverity,
    ConflictType,
    Relationship,
    ResolutionStatus,
)

logger = structlog.get_logger("ArbiterAgent")


def register_handlers(agent: ArbiterAgent) -> None:
    """Register message handlers on an ArbiterAgent instance."""
    agent._message_handlers = {
        "report_conflict": agent._handle_report_conflict,
        "request_arbitration": agent._handle_request_arbitration,
        "mediate_dispute": agent._handle_mediate_dispute,
        "resolve_contention": agent._handle_resolve_contention,
        "get_conflict_details": agent._handle_get_conflict_details,
        "get_active_conflicts": agent._handle_get_active_conflicts,
        "propose_resolution": agent._handle_propose_resolution,
        "accept_resolution": agent._handle_accept_resolution,
        "get_relationship_status": agent._handle_get_relationship_status,
        "get_relationship_health": agent._handle_get_relationship_health,
        "update_relationship": agent._handle_update_relationship,
        "get_arbitration_report": agent._handle_get_arbitration_report,
        "register_interaction": agent._handle_register_interaction,
    }


VALIDATION_ERROR = "Validation error"
MISSING_CONFLICT_ID = "Missing conflict_id"
CONFLICT_NOT_FOUND = "Conflict not found"


async def _handle_report_conflict(agent: ArbiterAgent, message: ActorMessage) -> None:
    """
    Report an inter-agent conflict.

    Content: {
        "conflict_type": str,
        "severity": str (optional),
        "parties": List[str],
        "description": str,
        "context": Dict (optional),
        "evidence": List[Dict] (optional)
    }
    """
    try:
        content = message.content
        conflict_type_str = content.get("conflict_type")
        severity_str = content.get("severity", ConflictSeverity.MEDIUM.value)
        parties = content.get("parties", [])
        description = content.get("description", "")
        context = content.get("context", {})
        evidence = content.get("evidence", [])

        # Validate
        validate_message(
            "report_conflict",
            content,
        )

        # Convert enums
        try:
            conflict_type = ConflictType(conflict_type_str)
        except ValueError:
            conflict_type = ConflictType.COMMUNICATION_BREAKDOWN

        try:
            severity = ConflictSeverity(severity_str)
        except ValueError:
            severity = ConflictSeverity.MEDIUM

        # Create conflict record
        conflict_id = agent._create_conflict_id()
        conflict = Conflict(
            conflict_id=conflict_id,
            conflict_type=conflict_type,
            severity=severity,
            status=ResolutionStatus.PENDING,
            timestamp=datetime.now(UTC),
            parties=parties,
            description=description,
            context=context,
            evidence=evidence,
        )

        # Store conflict
        agent._conflicts[conflict_id] = conflict
        agent._conflict_history.append(conflict_id)

        # Update statistic
        agent._stats["total_conflicts"] += 1
        agent._stats["conflicts_by_type"][conflict_type.value] += 1
        agent._stats["conflicts_by_severity"][severity.value] += 1

        # Update relationships
        agent._update_relationships_for_conflict(conflict)

        # Auto-resolution if enabled
        resolution_result = None
        if agent._auto_resolution:
            resolution_result = await agent._attempt_auto_resolution(conflict)

        # LRU cleanup
        if len(agent._conflict_history) > agent._max_conflicts:
            oldest = agent._conflict_history.pop(0)
            agent._conflicts.pop(oldest, None)

        logger.warning(
            "Conflict reported",
            conflict_id=conflict_id,
            conflict_type=conflict_type.value,
            severity=severity.value,
            parties=parties,
            auto_resolution=resolution_result is not None,
        )

        response_content = {
            "conflict_id": conflict_id,
            "status": conflict.status.value,
            "severity": severity.value,
            "auto_resolution_attempted": resolution_result is not None,
            "resolution_status": resolution_result.get("status") if resolution_result else None,
            "next_steps": agent._get_next_steps(conflict),
        }

        await agent._send_response(message, response_content)

    except ValidationError as ve:
        logger.warning(VALIDATION_ERROR, error=str(ve))
        await agent._send_error(message, VALIDATION_ERROR, str(ve))
    except Exception as e:
        logger.exception("Error reporting conflict", error=str(e))
        await agent._send_error(message, "Conflict report failed", str(e))


async def _handle_request_arbitration(agent: ArbiterAgent, message: ActorMessage) -> None:
    """
    Request formal arbitration for a conflict.

    Content: {
        "conflict_id": str (optional),
        "parties": List[str] (optional),
        "dispute": str,
        "desired_outcome": str (optional),
        "urgency": str (optional)
    }
    """
    try:
        content = message.content
        conflict_id = content.get("conflict_id")
        parties = content.get("parties", [])
        dispute = content.get("dispute", "")
        desired_outcome = content.get("desired_outcome")
        urgency = content.get("urgency", "normal")

        # Validate
        validate_message(
            "request_arbitration",
            content,
        )

        # Get or create conflict
        if conflict_id and conflict_id in agent._conflicts:
            conflict = agent._conflicts[conflict_id]
        else:
            # Create new conflict for arbitration
            conflict_id = agent._create_conflict_id()
            conflict = Conflict(
                conflict_id=conflict_id,
                conflict_type=ConflictType.AUTHORITY_CONFLICT,
                severity=ConflictSeverity.HIGH if urgency == "urgent" else ConflictSeverity.MEDIUM,
                status=ResolutionStatus.IN_PROGRESS,
                timestamp=datetime.now(UTC),
                parties=[*parties, message.sender_id],
                description=dispute,
                context={"desired_outcome": desired_outcome, "urgency": urgency},
            )
            agent._conflicts[conflict_id] = conflict
            agent._conflict_history.append(conflict_id)

        # Register for arbitration
        agent._pending_arbitrations[conflict_id] = agent._pending_arbitrations.get(conflict_id, [])
        agent._pending_arbitrations[conflict_id].append(message.sender_id)

        # Check if all parties are present
        all_parties_present = all(
            p in agent._pending_arbitrations[conflict_id] for p in conflict.parties
        )

        response_content = {
            "conflict_id": conflict_id,
            "arbitration_status": "in_progress",
            "parties_registered": len(agent._pending_arbitrations[conflict_id]),
            "total_parties": len(set(conflict.parties)),
            "all_parties_present": all_parties_present,
            "next_step": "waiting_for_parties"
            if not all_parties_present
            else "arbitration_scheduled",
        }

        await agent._send_response(message, response_content)

    except ValidationError as ve:
        logger.warning(VALIDATION_ERROR, error=str(ve))
        await agent._send_error(message, "Invalid arbitration request", str(ve))
    except Exception as e:
        logger.exception("Error requesting arbitration", error=str(e))
        await agent._send_error(message, "Arbitration request failed", str(e))


async def _handle_mediate_dispute(agent: ArbiterAgent, message: ActorMessage) -> None:
    """
    Request mediation for a dispute.

    Content: {
        "conflict_id": str (optional),
        "dispute_description": str,
        "other_party": str,
        "proposed_solution": str (optional)
    }
    """
    try:
        content = message.content
        _ = content.get("conflict_id")  # Required for message contract
        dispute_description = content.get("dispute_description", "")
        other_party = content.get("other_party")
        proposed_solution = content.get("proposed_solution")

        # Validate
        validate_message(
            "mediate_dispute",
            content,
        )

        # Perform mediation
        mediation_result = await agent._conduct_mediation(
            sender=message.sender_id,
            other_party=other_party,
            dispute=dispute_description,
            proposed_solution=proposed_solution,
        )

        response_content = {
            "mediation_status": mediation_result["status"],
            "resolution_achieved": mediation_result["resolved"],
            "agreement": mediation_result.get("agreement"),
            "follow_up_actions": mediation_result.get("actions", []),
        }

        await agent._send_response(message, response_content)

    except ValidationError as ve:
        logger.warning(VALIDATION_ERROR, error=str(ve))
        await agent._send_error(message, "Invalid mediation request", str(ve))
    except Exception as e:
        logger.exception("Error mediating dispute", error=str(e))
        await agent._send_error(message, "Mediation failed", str(e))


async def _handle_resolve_contention(agent: ArbiterAgent, message: ActorMessage) -> None:
    """
    Resolve resource or task contention.

    Content: {
        "contention_type": str,
        "resource": str (optional),
        "competing_agents": List[str],
        "priority_override": Dict[str, int] (optional)
    }
    """
    try:
        content = message.content
        contention_type = content.get("contention_type", "resource")
        resource = content.get("resource")
        competing_agents = content.get("competing_agents", [])
        priority_override = content.get("priority_override", {})

        # Validate
        validate_message(
            "resolve_contention",
            content,
        )

        # Resolve based on contention type
        if contention_type == "resource":
            resolution = await agent._resolve_resource_contention(
                resource=resource,
                competing_agents=competing_agents,
                priority_override=priority_override,
            )
        elif contention_type == "task":
            resolution = await agent._resolve_task_contention(
                competing_agents=competing_agents,
                priority_override=priority_override,
            )
        else:
            resolution = await agent._resolve_generic_contention(
                contention_type=contention_type,
                competing_agents=competing_agents,
            )

        response_content = {
            "resolution": resolution,
            "assigned_to": resolution.get("winner"),
            "reasoning": resolution.get("reasoning"),
            "alternatives": resolution.get("alternatives"),
        }

        await agent._send_response(message, response_content)

    except ValidationError as ve:
        logger.warning(VALIDATION_ERROR, error=str(ve))
        await agent._send_error(message, "Invalid contention resolution", str(ve))
    except Exception as e:
        logger.exception("Error resolving contention", error=str(e))
        await agent._send_error(message, "Contention resolution failed", str(e))


async def _handle_get_conflict_details(agent: ArbiterAgent, message: ActorMessage) -> None:
    """
    Get detailed information about a specific conflict.

    Content: {
        "conflict_id": str
    }
    """
    try:
        content = message.content
        conflict_id = content.get("conflict_id")

        if not conflict_id:
            await agent._send_error(message, MISSING_CONFLICT_ID)
            return

        conflict = agent._conflicts.get(conflict_id)
        if not conflict:
            await agent._send_error(message, CONFLICT_NOT_FOUND, conflict_id)
            return

        response_content = {
            "conflict_id": conflict.conflict_id,
            "conflict_type": conflict.conflict_type.value,
            "severity": conflict.severity.value,
            "status": conflict.status.value,
            "timestamp": conflict.timestamp.isoformat(),
            "parties": conflict.parties,
            "description": conflict.description,
            "context": conflict.context,
            "evidence": conflict.evidence,
            "proposed_resolutions": conflict.proposed_resolutions,
            "selected_resolution": conflict.selected_resolution,
            "resolved_at": conflict.resolved_at.isoformat() if conflict.resolved_at else None,
            "resolution_notes": conflict.resolution_notes,
        }

        await agent._send_response(message, response_content)

    except ValidationError as ve:
        logger.warning(VALIDATION_ERROR, error=str(ve))
        await agent._send_error(message, "Invalid request", str(ve))
    except Exception as e:
        logger.exception("Error getting conflict details", error=str(e))
        await agent._send_error(message, "Failed to get conflict details", str(e))


async def _handle_get_active_conflicts(agent: ArbiterAgent, message: ActorMessage) -> None:
    """
    Get all active (unresolved) conflicts.

    Content: {
        "severity_filter": str (optional),
        "party_filter": str (optional),
        "limit": int (optional)
    }
    """
    try:
        content = message.content
        severity_filter = content.get("severity_filter")
        party_filter = content.get("party_filter")
        limit = content.get("limit", 100)

        active_conflicts = [
            c
            for c in agent._conflicts.values()
            if c.status not in [ResolutionStatus.RESOLVED, ResolutionStatus.FAILED]
        ]

        # Apply filters
        if severity_filter:
            try:
                min_severity = ConflictSeverity(severity_filter)
                severity_order = {
                    ConflictSeverity.LOW: 0,
                    ConflictSeverity.MEDIUM: 1,
                    ConflictSeverity.HIGH: 2,
                    ConflictSeverity.CRITICAL: 3,
                }
                min_order = severity_order.get(min_severity, 0)
                active_conflicts = [
                    c for c in active_conflicts if severity_order.get(c.severity, 0) >= min_order
                ]
            except ValueError:
                logger.debug("Arbiter handler value parsing fallback", exc_info=True)

        if party_filter:
            active_conflicts = [c for c in active_conflicts if party_filter in c.parties]

        # Sort by severity
        severity_order = {
            ConflictSeverity.CRITICAL: 3,
            ConflictSeverity.HIGH: 2,
            ConflictSeverity.MEDIUM: 1,
            ConflictSeverity.LOW: 0,
        }
        active_conflicts.sort(
            key=lambda x: severity_order.get(x.severity, 0),
            reverse=True,
        )

        # Apply limit
        active_conflicts = active_conflicts[:limit]

        response_content = {
            "active_conflicts_count": len(active_conflicts),
            "conflicts": [
                {
                    "conflict_id": c.conflict_id,
                    "conflict_type": c.conflict_type.value,
                    "severity": c.severity.value,
                    "status": c.status.value,
                    "parties": c.parties,
                    "description": c.description,
                }
                for c in active_conflicts
            ],
        }

        await agent._send_response(message, response_content)

    except Exception as e:
        logger.exception("Error getting active conflicts", error=str(e))
        await agent._send_error(message, "Failed to get active conflicts", str(e))


async def _handle_propose_resolution(agent: ArbiterAgent, message: ActorMessage) -> None:
    """
    Propose a resolution for a conflict.

    Content: {
        "conflict_id": str,
        "resolution_strategy": str,
        "proposal": Dict,
        "rationale": str (optional)
    }
    """
    try:
        content = message.content
        conflict_id = content.get("conflict_id")
        resolution_strategy = content.get("resolution_strategy")
        proposal = content.get("proposal", {})
        rationale = content.get("rationale", "")

        if not conflict_id:
            await agent._send_error(message, MISSING_CONFLICT_ID)
            return

        conflict = agent._conflicts.get(conflict_id)
        if not conflict:
            await agent._send_error(message, CONFLICT_NOT_FOUND, conflict_id)
            return

        # Add proposed resolution
        proposed = {
            "proposed_by": message.sender_id,
            "strategy": resolution_strategy,
            "proposal": proposal,
            "rationale": rationale,
            "timestamp": datetime.now(UTC).isoformat(),
        }

        conflict.proposed_resolutions.append(proposed)

        response_content = {
            "conflict_id": conflict_id,
            "proposal_accepted": True,
            "total_proposals": len(conflict.proposed_resolutions),
            "next_step": "waiting_for_acceptance",
        }

        await agent._send_response(message, response_content)

    except ValidationError as ve:
        logger.warning(VALIDATION_ERROR, error=str(ve))
        await agent._send_error(message, "Invalid proposal", str(ve))
    except Exception as e:
        logger.exception("Error proposing resolution", error=str(e))
        await agent._send_error(message, "Proposal failed", str(e))


async def _handle_accept_resolution(agent: ArbiterAgent, message: ActorMessage) -> None:
    """
    Accept a proposed resolution.

    Content: {
        "conflict_id": str,
        "proposal_index": int (optional),
        "resolution_data": Dict (optional)
    }
    """
    try:
        content = message.content
        conflict_id = content.get("conflict_id")
        proposal_index = content.get("proposal_index", -1)
        resolution_data = content.get("resolution_data")

        if not conflict_id:
            await agent._send_error(message, MISSING_CONFLICT_ID)
            return

        conflict = agent._conflicts.get(conflict_id)
        if not conflict:
            await agent._send_error(message, CONFLICT_NOT_FOUND, conflict_id)
            return

        # Select or create resolution
        if resolution_data:
            selected = resolution_data
        elif 0 <= proposal_index < len(conflict.proposed_resolutions):
            selected = conflict.proposed_resolutions[proposal_index]
        elif conflict.proposed_resolutions:
            selected = conflict.proposed_resolutions[-1]
        else:
            selected = {"resolution": "default", "details": {}}

        # Apply resolution
        conflict.selected_resolution = selected
        conflict.status = ResolutionStatus.RESOLVED
        conflict.resolved_at = datetime.now(UTC)

        # Update statistics
        agent._stats["resolutions_successful"] += 1

        # Update relationships
        agent._update_relationships_for_resolution(conflict)

        response_content = {
            "conflict_id": conflict_id,
            "resolution_accepted": True,
            "status": ResolutionStatus.RESOLVED.value,
            "resolution": selected,
        }

        await agent._send_response(message, response_content)

    except ValidationError as ve:
        logger.warning(VALIDATION_ERROR, error=str(ve))
        await agent._send_error(message, "Invalid acceptance", str(ve))
    except Exception as e:
        logger.exception("Error accepting resolution", error=str(e))
        await agent._send_error(message, "Acceptance failed", str(e))


async def _handle_get_relationship_status(agent: ArbiterAgent, message: ActorMessage) -> None:
    """
    Get relationship status between two agents.

    Content: {
        "agent_a": str,
        "agent_b": str
    }
    """
    try:
        content = message.content
        agent_a = content.get("agent_a")
        agent_b = content.get("agent_b")

        if not agent_a or not agent_b:
            await agent._send_error(message, "Missing agent_a or agent_b")
            return

        # Normalize key (alphabetically ordered)
        key = tuple(sorted([agent_a, agent_b]))
        relationship = agent._relationships.get(key)

        if not relationship:
            response_content = {
                "agent_a": agent_a,
                "agent_b": agent_b,
                "relationship_exists": False,
                "health_score": 0.5,  # Default neutral
            }
        else:
            response_content = {
                "agent_a": relationship.agent_a,
                "agent_b": relationship.agent_b,
                "health_score": relationship.health_score,
                "interaction_count": relationship.interaction_count,
                "conflict_count": relationship.conflict_count,
                "cooperation_count": relationship.cooperation_count,
                "trust_level": relationship.trust_level,
                "last_interaction": relationship.last_interaction.isoformat(),
                "tags": relationship.tags,
            }

        await agent._send_response(message, response_content)

    except ValidationError as ve:
        logger.warning(VALIDATION_ERROR, error=str(ve))
        await agent._send_error(message, "Invalid request", str(ve))
    except Exception as e:
        logger.exception("Error getting relationship status", error=str(e))
        await agent._send_error(message, "Failed to get relationship status", str(e))


async def _handle_get_relationship_health(agent: ArbiterAgent, message: ActorMessage) -> None:
    """
    Get overall relationship health across the Collective.

    Content: {
        "include_details": bool (optional)
    }
    """
    try:
        content = message.content
        include_details = content.get("include_details", False)

        # Calculate aggregate health
        if agent._relationships:
            avg_health = sum(r.health_score for r in agent._relationships.values()) / len(
                agent._relationships
            )
            avg_trust = sum(r.trust_level for r in agent._relationships.values()) / len(
                agent._relationships
            )
        else:
            avg_health = 1.0
            avg_trust = 1.0

        response_content = {
            "total_relationships": len(agent._relationships),
            "average_health_score": avg_health,
            "average_trust_level": avg_trust,
            "relationships_needing_attention": len(
                [r for r in agent._relationships.values() if r.health_score < 0.5]
            ),
        }

        if include_details:
            response_content["relationships"] = [
                {
                    "agents": [r.agent_a, r.agent_b],
                    "health_score": r.health_score,
                    "trust_level": r.trust_level,
                    "conflict_count": r.conflict_count,
                }
                for r in agent._relationships.values()
            ]

        await agent._send_response(message, response_content)

    except Exception as e:
        logger.exception("Error getting relationship health", error=str(e))
        await agent._send_error(message, "Relationship health check failed", str(e))


async def _handle_update_relationship(agent: ArbiterAgent, message: ActorMessage) -> None:
    """
    Update relationship metrics based on interaction.

    Content: {
        "other_agent": str,
        "interaction_type": str,
        "outcome": str (optional),
        "trust_delta": float (optional)
    }
    """
    try:
        content = message.content
        other_agent = content.get("other_agent")
        interaction_type = content.get("interaction_type", "neutral")
        content.get("outcome", "neutral")
        trust_delta = content.get("trust_delta", 0.0)

        if not other_agent:
            await agent._send_error(message, "Missing other_agent")
            return

        # Get or create relationship
        key = tuple(sorted([message.sender_id, other_agent]))

        if key not in agent._relationships:
            agent._relationships[key] = Relationship(
                agent_a=key[0],
                agent_b=key[1],
                health_score=0.7,  # Start slightly positive
                interaction_count=0,
                conflict_count=0,
                cooperation_count=0,
                last_interaction=datetime.now(UTC),
                trust_level=0.5,  # Start neutral
            )

        relationship = agent._relationships[key]

        # Update metrics
        relationship.interaction_count += 1
        relationship.last_interaction = datetime.now(UTC)

        if interaction_type in ["cooperation", "helpful", "collaborative"]:
            relationship.cooperation_count += 1
            relationship.health_score = min(1.0, relationship.health_score + 0.05)
        elif interaction_type in ["conflict", "dispute", "contention"]:
            relationship.conflict_count += 1
            relationship.health_score = max(0.0, relationship.health_score - 0.1)

        # Apply trust delta
        relationship.trust_level = max(0.0, min(1.0, relationship.trust_level + trust_delta))

        # Apply decay to health score
        relationship.health_score = max(0.0, relationship.health_score - agent._relationship_decay)

        response_content = {
            "relationship_updated": True,
            "health_score": relationship.health_score,
            "trust_level": relationship.trust_level,
            "interaction_count": relationship.interaction_count,
        }

        await agent._send_response(message, response_content)

    except ValidationError as ve:
        logger.warning(VALIDATION_ERROR, error=str(ve))
        await agent._send_error(message, "Invalid update", str(ve))
    except Exception as e:
        logger.exception("Error updating relationship", error=str(e))
        await agent._send_error(message, "Relationship update failed", str(e))


async def _handle_get_arbitration_report(agent: ArbiterAgent, message: ActorMessage) -> None:
    """
    Generate comprehensive arbitration report.

    Content: {
        "time_range": str (optional),
        "include_recommendations": bool (optional)
    }
    """
    try:
        content = message.content
        time_range = content.get("time_range", "24h")
        include_recommendations = content.get("include_recommendations", True)

        # Calculate statistics
        active_conflicts = len(
            [
                c
                for c in agent._conflicts.values()
                if c.status not in [ResolutionStatus.RESOLVED, ResolutionStatus.FAILED]
            ]
        )
        resolved_conflicts = len(
            [c for c in agent._conflicts.values() if c.status == ResolutionStatus.RESOLVED]
        )
        failed_resolutions = len(
            [c for c in agent._conflicts.values() if c.status == ResolutionStatus.FAILED]
        )

        conflicts_by_type = dict(agent._stats["conflicts_by_type"])
        conflicts_by_severity = dict(agent._stats["conflicts_by_severity"])

        # Relationship health summary
        relationship_health = {
            f"{r.agent_a}-{r.agent_b}": r.health_score for r in agent._relationships.values()
        }

        # Generate recommendations
        recommendations = []
        if include_recommendations:
            recommendations = agent._generate_recommendations()

        report = {
            "report_id": f"arb_report_{datetime.now(UTC).timestamp()}",
            "timestamp": datetime.now(UTC).isoformat(),
            "time_range": time_range,
            "active_conflicts": active_conflicts,
            "resolved_conflicts": resolved_conflicts,
            "failed_resolutions": failed_resolutions,
            "conflicts_by_type": conflicts_by_type,
            "conflicts_by_severity": conflicts_by_severity,
            "relationship_health": relationship_health,
            "statistics": {
                "total_conflicts": agent._stats["total_conflicts"],
                "resolutions_successful": agent._stats["resolutions_successful"],
                "resolutions_failed": agent._stats["resolutions_failed"],
                "resolutions_escalated": agent._stats["resolutions_escalated"],
                "average_resolution_time": agent._stats["average_resolution_time"],
            },
            "recommendations": recommendations,
        }

        await agent._send_response(message, {"report": report})

    except Exception as e:
        logger.exception("Error generating arbitration report", error=str(e))
        await agent._send_error(message, "Report generation failed", str(e))


async def _handle_register_interaction(agent: ArbiterAgent, message: ActorMessage) -> None:
    """
    Register an inter-agent interaction for relationship tracking.

    Content: {
        "other_agent": str,
        "interaction_type": str,
        "outcome": str (optional),
        "success": bool (optional)
    }
    """
    try:
        content = message.content
        other_agent = content.get("other_agent")
        content.get("interaction_type", "communication")
        outcome = content.get("outcome", "neutral")
        success = content.get("success", True)

        if not other_agent:
            await agent._send_error(message, "Missing other_agent")
            return

        # Update relationship
        key = tuple(sorted([message.sender_id, other_agent]))

        if key not in agent._relationships:
            agent._relationships[key] = Relationship(
                agent_a=key[0],
                agent_b=key[1],
                health_score=0.7,
                interaction_count=0,
                conflict_count=0,
                cooperation_count=0,
                last_interaction=datetime.now(UTC),
                trust_level=0.5,
            )

        relationship = agent._relationships[key]
        relationship.interaction_count += 1
        relationship.last_interaction = datetime.now(UTC)

        if success and outcome in ["positive", "successful", "helpful"]:
            relationship.cooperation_count += 1
            relationship.health_score = min(1.0, relationship.health_score + 0.02)
            relationship.trust_level = min(1.0, relationship.trust_level + 0.01)

        response_content = {
            "interaction_registered": True,
            "relationship_health": relationship.health_score,
            "trust_level": relationship.trust_level,
        }

        await agent._send_response(message, response_content)

    except ValidationError as ve:
        logger.warning(VALIDATION_ERROR, error=str(ve))
        await agent._send_error(message, "Invalid interaction", str(ve))
    except Exception as e:
        logger.exception("Error registering interaction", error=str(e))
        await agent._send_error(message, "Interaction registration failed", str(e))
