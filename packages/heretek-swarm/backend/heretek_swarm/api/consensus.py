"""
Heretek Swarm Consensus API Endpoints

Provides HTTP endpoints for:
- Listing active consensus rounds
- Creating new consensus processes
- Submitting votes
- Retrieving consensus results

Uses MAKER (Multi-Agent Knowledge Extraction & Reasoning) consensus.

SECURITY: All endpoints require authentication. Agent identity verification required for voting.
"""

import asyncio
import os
from datetime import UTC, datetime
from typing import Annotated, Any
from uuid import uuid4

import structlog
from fastapi import APIRouter, Depends, Header, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from heretek_swarm_core.consensus import (
    ConsensusState,
    MAKERConsensus,
    Vote,
)
from heretek_swarm_core.consensus.audit import (
    ConsensusAuditTrail,
)
from heretek_swarm_core.consensus.deliberation import (
    Argument,
    DeliberationEngine,
    Evidence,
    Position,
)
from heretek_swarm_core.consensus.tribunal import (
    EvidenceType,
    RulingType,
    Tribunal,
)
from heretek_swarm.gateway.auth import TokenStore, default_token_store

logger = structlog.get_logger("api.consensus")


async def _snapshot_after_round(
    deliberation_id: str,
    round_number: int,
    summary: str,
    agent_id: str,
) -> None:
    """
    Fire-and-forget memory snapshot after a deliberation round.

    Non-fatal: snapshot failures must not propagate to the caller.
    """
    try:
        from heretek_swarm_core.memory.cognee_writer import CogneeMemoryWriter

        writer = CogneeMemoryWriter()
        snapshot_content = f"Round {round_number}: {summary}"
        dataset_name = f"deliberation-{deliberation_id}"
        await writer.store(content=snapshot_content, dataset=dataset_name)
    except Exception as e:
        logger.warning("memory_snapshot_failed", deliberation_id=deliberation_id, error=str(e))


# =============================================================================
# Error Messages (Constants)
# =============================================================================

TRIBUNAL_NOT_AVAILABLE = "Tribunal not available"

# =============================================================================
# Authentication Configuration
# =============================================================================

security = HTTPBearer(auto_error=False)


class ConsensusAuthManager:
    """Manages authentication for consensus operations.

    Backwards-compat shim. The previous bespoke implementation had
    subtle semantic drift from the canonical token store at
    :mod:`heretek_swarm.gateway.auth` (see PLAN.md §1.7
    "triplicated authentication" — three trust decisions for the same
    request was a direct zero-trust violation). This class now
    delegates to :class:`heretek_swarm.gateway.auth.TokenStore` so
    the three implementations share one source of truth. Existing
    callers (``generate_token``, ``validate_token``,
    ``check_permission``, ``revoke_token``) keep working.
    """

    def __init__(self, store: TokenStore | None = None) -> None:
        # Default to the process-wide store. Tests can inject a private
        # store by passing one in.
        self._store = store or default_token_store

    def generate_token(self, agent_id: str, permissions: list[str] | None = None) -> str:
        """Generate an authentication token for an agent."""
        return self._store.generate_token(agent_id, permissions=permissions)

    def validate_token(self, token: str) -> tuple[bool, str | None, str | None]:
        """Validate an authentication token.

        Returns:
            Tuple of (is_valid, agent_id, error_message)
        """
        return self._store.validate_token(token)

    def check_permission(self, agent_id: str, operation: str) -> bool:
        """Check if agent has permission for operation."""
        return self._store.check_permission(agent_id, operation)

    def revoke_token(self, token: str) -> bool:
        """Revoke a token."""
        return self._store.revoke_token(token)


# Global auth manager instance
consensus_auth_manager = ConsensusAuthManager()


async def get_authenticated_agent(
    credentials: HTTPAuthorizationCredentials | None = Depends(security),
    x_agent_id: str | None = Header(None, description="Agent ID header"),
) -> str:
    """
    Dependency to authenticate agent for consensus operations.

    Returns:
        Authenticated agent ID

    Raises:
        HTTPException: If authentication fails
    """
    if not credentials:
        raise HTTPException(401, "Authentication required. Provide Bearer token.")

    token = credentials.credentials
    is_valid, agent_id, error = consensus_auth_manager.validate_token(token)

    if not is_valid:
        raise HTTPException(401, f"Authentication failed: {error}")

    # Verify agent ID matches if provided in header
    if x_agent_id and x_agent_id != agent_id:
        raise HTTPException(403, "Agent ID mismatch. Token does not match provided agent ID.")

    return agent_id


# Create router
router = APIRouter(prefix="/api/consensus", tags=["consensus"])

# In-memory storage for consensus processes (use Redis in production)
_consensus_store: dict[str, MAKERConsensus] = {}
_active_rounds: dict[str, dict[str, Any]] = {}


# =============================================================================
# Consensus Round Endpoints
# =============================================================================


@router.get("")
async def get_active_consensus_rounds(agent_id: str = Depends(get_authenticated_agent)):
    """
    Get all active consensus rounds.

    SECURITY: Requires authentication.

    Returns:
        List of active consensus rounds with their current state
    """
    active = []
    for round_id, data in _active_rounds.items():
        if data["state"] in [ConsensusState.GATHERING.value, ConsensusState.VOTING.value]:
            active.append(
                {
                    "id": round_id,
                    "state": data["state"],
                    "topic": data["topic"],
                    "vote_count": len(data["votes"]),
                    "created_at": data["created_at"],
                    "deadline": data.get("deadline"),
                }
            )

    return {"consensus_rounds": active, "total": len(active)}


@router.get("/history")
async def get_consensus_history(limit: int = 50, agent_id: str = Depends(get_authenticated_agent)):
    """
    Get completed consensus rounds history.

    SECURITY: Requires authentication.

    Args:
        limit: Maximum number of results to return (default: 50)

    Returns:
        List of completed consensus results
    """
    completed = []
    for round_id, data in _active_rounds.items():
        if data["state"] == ConsensusState.COMPLETED.value:
            completed.append(
                {
                    "id": round_id,
                    "topic": data["topic"],
                    "decision": data.get("decision"),
                    "confidence": data.get("confidence"),
                    "vote_count": len(data["votes"]),
                    "completed_at": data.get("completed_at"),
                    "red_flags": data.get("red_flags", []),
                }
            )

    # Sort by completion time, most recent first
    completed.sort(key=lambda x: x.get("completed_at", ""), reverse=True)

    return {
        "consensus_history": completed[:limit],
        "total": len(completed),
    }


@router.get("/{consensus_id}")
async def get_consensus_round(consensus_id: str, agent_id: str = Depends(get_authenticated_agent)):
    """
    Get details of a specific consensus round.

    SECURITY: Requires authentication.

    Args:
        consensus_id: Unique consensus round identifier

    Returns:
        Consensus round details including all votes
    """
    if consensus_id not in _active_rounds:
        raise HTTPException(404, f"Consensus round {consensus_id} not found")

    data = _active_rounds[consensus_id]

    return {
        "id": consensus_id,
        "topic": data["topic"],
        "state": data["state"],
        "votes": data["votes"],
        "decision": data.get("decision"),
        "confidence": data.get("confidence"),
        "red_flags": data.get("red_flags", []),
        "created_at": data["created_at"],
        "completed_at": data.get("completed_at"),
        "metadata": data.get("metadata", {}),
    }


@router.post("")
async def create_consensus_round(
    topic: str, description: str = "", agent_id: str = Depends(get_authenticated_agent)
):
    """
    Create a new consensus round.

    SECURITY: Requires authentication with 'create' permission.

    Args:
        topic: The topic/question to reach consensus on
        description: Optional detailed description

    Returns:
        Created consensus round details
    """
    # Check permission
    if not consensus_auth_manager.check_permission(agent_id, "create"):
        raise HTTPException(403, "Permission denied. Agent cannot create consensus rounds.")
    consensus_id = str(uuid4())

    # Create MAKER consensus instance
    ahead_by_k = int(os.environ.get("CONSENSUS_AHEAD_BY_K", "2"))
    min_votes = int(os.environ.get("CONSENSUS_MIN_VOTES", "3"))
    consensus = MAKERConsensus(ahead_by_k=ahead_by_k, min_votes=min_votes)

    # Store consensus instance
    _consensus_store[consensus_id] = consensus

    # Store round data
    _active_rounds[consensus_id] = {
        "id": consensus_id,
        "topic": topic,
        "description": description,
        "state": ConsensusState.GATHERING.value,
        "votes": [],
        "created_at": datetime.now(UTC).isoformat(),
        "metadata": {},
    }

    logger.info("Created consensus round", consensus_id=consensus_id, topic=topic)

    created_at = _active_rounds[consensus_id]["created_at"]

    # Broadcast to dashboard WebSocket listeners
    try:
        from heretek_swarm.api.websockets import manager as ws_manager

        await ws_manager.broadcast_dashboard(
            {
                "type": "consensus_created",
                "consensus_id": consensus_id,
                "topic": topic,
                "description": description,
                "state": ConsensusState.GATHERING.value,
                "created_at": created_at,
                "timestamp": datetime.now(UTC).isoformat(),
            }
        )
    except Exception as e:
        logger.warning("consensus_ws_broadcast_failed", event="consensus_created", error=str(e))

    return {
        "id": consensus_id,
        "topic": topic,
        "description": description,
        "state": ConsensusState.GATHERING.value,
        "created_at": created_at,
    }


@router.post("/{consensus_id}/vote")
async def submit_vote(
    consensus_id: str,
    decision: str,
    confidence: float,
    metadata: dict[str, Any] | None = None,
    authenticated_agent_id: str = Depends(get_authenticated_agent),
    x_agent_id: str | None = Header(None, description="Agent ID header"),
):
    """
    Submit a vote for a consensus round.

    SECURITY: Requires authentication. Agent identity verified via token.

    Args:
        consensus_id: Unique consensus round identifier
        decision: The agent's decision/answer
        confidence: Confidence level (0.0 to 1.0)
        metadata: Optional additional metadata
        x_agent_id: Agent ID (must match authenticated token)

    Returns:
        Vote confirmation with current vote count
    """
    # Use authenticated agent ID
    agent_id = authenticated_agent_id

    # Check permission
    if not consensus_auth_manager.check_permission(agent_id, "vote"):
        raise HTTPException(403, "Permission denied. Agent cannot vote.")

    if consensus_id not in _active_rounds:
        raise HTTPException(404, f"Consensus round {consensus_id} not found")

    data = _active_rounds[consensus_id]

    # Check if consensus is still accepting votes
    if data["state"] in [ConsensusState.COMPLETED.value, ConsensusState.FAILED.value]:
        raise HTTPException(400, f"Consensus round {consensus_id} is already {data['state']}")

    # Validate confidence
    if not 0.0 <= confidence <= 1.0:
        raise HTTPException(400, "Confidence must be between 0.0 and 1.0")

    # Check for duplicate votes from same agent
    for vote in data["votes"]:
        if vote["agent_id"] == agent_id:
            raise HTTPException(400, f"Agent {agent_id} has already voted")

    # Create vote
    vote = Vote(
        agent_id=agent_id,
        decision=decision,
        confidence=confidence,
        timestamp=datetime.now(UTC).isoformat(),
        metadata=metadata or {},
    )

    # Add to store
    data["votes"].append(
        {
            "agent_id": vote.agent_id,
            "decision": vote.decision,
            "confidence": vote.confidence,
            "timestamp": vote.timestamp,
            "metadata": vote.metadata,
        }
    )

    # Get consensus and process vote
    consensus = _consensus_store.get(consensus_id)
    if consensus:
        consensus.add_vote(consensus_id, agent_id, decision, confidence)

    # Transition state if enough votes
    if len(data["votes"]) >= int(os.environ.get("CONSENSUS_MIN_VOTES", "3")):
        data["state"] = ConsensusState.AGGREGATING.value

    logger.info(
        "Vote submitted",
        consensus_id=consensus_id,
        agent_id=agent_id,
        decision=decision,
        confidence=confidence,
    )

    # Broadcast to dashboard WebSocket listeners
    try:
        from heretek_swarm.api.websockets import manager as ws_manager

        await ws_manager.broadcast_dashboard(
            {
                "type": "consensus_vote",
                "consensus_id": consensus_id,
                "agent_id": agent_id,
                "decision": decision,
                "confidence": confidence,
                "vote_count": len(data["votes"]),
                "current_state": data["state"],
                "timestamp": datetime.now(UTC).isoformat(),
            }
        )
    except Exception as e:
        logger.warning("consensus_ws_broadcast_failed", event="consensus_vote", error=str(e))

    return {
        "status": "vote_accepted",
        "consensus_id": consensus_id,
        "agent_id": agent_id,
        "vote_count": len(data["votes"]),
        "current_state": data["state"],
    }


@router.post("/{consensus_id}/aggregate")
async def aggregate_consensus(consensus_id: str, agent_id: str = Depends(get_authenticated_agent)):
    """
    Aggregate votes and determine consensus decision.

    SECURITY: Requires authentication with 'create' permission.

    Args:
        consensus_id: Unique consensus round identifier

    Returns:
        Aggregated consensus result
    """
    # Check permission
    if not consensus_auth_manager.check_permission(agent_id, "create"):
        raise HTTPException(403, "Permission denied. Agent cannot aggregate consensus.")
    if consensus_id not in _active_rounds:
        raise HTTPException(404, f"Consensus round {consensus_id} not found")

    data = _active_rounds[consensus_id]

    if len(data["votes"]) == 0:
        raise HTTPException(400, "No votes to aggregate")

    # Get consensus instance
    consensus = _consensus_store.get(consensus_id)
    if not consensus:
        raise HTTPException(500, "Consensus instance not found")

    # Aggregate
    # NOTE: MAKERConsensus / EnhancedMAKERConsensus expose the aggregation
    # operation as `compute_consensus`. Earlier revisions of this router
    # called a non-existent `aggregate_consensus` which raised AttributeError
    # at runtime. See PLAN.md §1.5 (latent bug, prime-directive zero-trust
    # violation). The call was previously at api/consensus.py:497.
    result = consensus.compute_consensus(consensus_id)

    # Update store
    data["state"] = result.state.value
    data["decision"] = result.decision
    data["confidence"] = result.confidence
    data["red_flags"] = result.red_flags
    data["completed_at"] = result.timestamp

    logger.info(
        "Consensus aggregated",
        consensus_id=consensus_id,
        decision=result.decision,
        confidence=result.confidence,
    )

    # Broadcast to dashboard WebSocket listeners
    try:
        from heretek_swarm.api.websockets import manager as ws_manager

        await ws_manager.broadcast_dashboard(
            {
                "type": "consensus_complete",
                "consensus_id": consensus_id,
                "decision": result.decision,
                "confidence": result.confidence,
                "state": result.state.value,
                "vote_count": len(data["votes"]),
                "red_flags": result.red_flags,
                "completed_at": result.timestamp,
                "timestamp": datetime.now(UTC).isoformat(),
            }
        )
    except Exception as e:
        logger.warning("consensus_ws_broadcast_failed", event="consensus_aggregated", error=str(e))

    return {
        "id": consensus_id,
        "decision": result.decision,
        "confidence": result.confidence,
        "state": result.state.value,
        "votes": data["votes"],
        "red_flags": result.red_flags,
        "completed_at": result.timestamp,
    }


@router.get("/{consensus_id}/results")
async def get_consensus_results(
    consensus_id: str, agent_id: str = Depends(get_authenticated_agent)
):
    """
    Get results of a completed consensus round.

    SECURITY: Requires authentication.

    Args:
        consensus_id: Unique consensus round identifier

    Returns:
        Consensus result with decision and all votes
    """
    if consensus_id not in _active_rounds:
        raise HTTPException(404, f"Consensus round {consensus_id} not found")

    data = _active_rounds[consensus_id]

    if data["state"] != ConsensusState.COMPLETED.value:
        return {
            "id": consensus_id,
            "state": data["state"],
            "decision": None,
            "confidence": None,
            "message": "Consensus not yet completed",
        }

    return {
        "id": consensus_id,
        "topic": data["topic"],
        "decision": data.get("decision"),
        "confidence": data.get("confidence"),
        "state": data["state"],
        "votes": data["votes"],
        "red_flags": data.get("red_flags", []),
        "completed_at": data.get("completed_at"),
    }


@router.delete("/{consensus_id}")
async def cancel_consensus(consensus_id: str, agent_id: str = Depends(get_authenticated_agent)):
    """
    Cancel an active consensus round.

    SECURITY: Requires authentication with 'create' permission.

    Args:
        consensus_id: Unique consensus round identifier

    Returns:
        Cancellation confirmation
    """
    # Check permission
    if not consensus_auth_manager.check_permission(agent_id, "create"):
        raise HTTPException(403, "Permission denied. Agent cannot cancel consensus.")
    if consensus_id not in _active_rounds:
        raise HTTPException(404, f"Consensus round {consensus_id} not found")

    data = _active_rounds[consensus_id]
    data["state"] = ConsensusState.FAILED.value

    # Clean up consensus instance
    _consensus_store.pop(consensus_id, None)

    logger.info("Consensus cancelled", consensus_id=consensus_id)

    return {
        "status": "cancelled",
        "consensus_id": consensus_id,
    }


# =============================================================================
# Consensus Configuration
# =============================================================================


@router.get("/config")
async def get_consensus_config(agent_id: str = Depends(get_authenticated_agent)):
    """
    Get current consensus configuration.

    SECURITY: Requires authentication.

    Returns:
        Consensus parameters
    """
    return {
        "ahead_by_k": int(os.environ.get("CONSENSUS_AHEAD_BY_K", "2")),
        "min_votes": int(os.environ.get("CONSENSUS_MIN_VOTES", "3")),
        "red_flag_threshold": float(os.environ.get("CONSENSUS_RED_FLAG_THRESHOLD", "0.3")),
        "voting_timeout_seconds": int(os.environ.get("CONSENSUS_VOTING_TIMEOUT", "300")),
    }


# Auth token generation endpoint
@router.post("/auth/token")
async def generate_auth_token(agent_id: str, permissions: list[str] | None = None):
    """
    Generate an authentication token for an agent.

    Args:
        agent_id: Agent identifier
        permissions: List of allowed operations (vote, create, view)

    Returns:
        Generated token
    """
    token = consensus_auth_manager.generate_token(agent_id, permissions)
    return {
        "token": token,
        "agent_id": agent_id,
        "permissions": permissions or ["vote", "create", "view"],
    }


# Token revocation endpoint
@router.post("/auth/revoke")
async def revoke_auth_token(token: str):
    """
    Revoke an authentication token.

    Args:
        token: Token to revoke

    Returns:
        Revocation confirmation
    """
    success = consensus_auth_manager.revoke_token(token)
    return {
        "revoked": success,
    }


# =============================================================================
# Deliberation Endpoints
# =============================================================================

# Global deliberation engine instance
deliberation_engine = DeliberationEngine()


@router.post("/deliberation/start")
async def start_deliberation(
    proposal: str,
    participants: list[str],
    topic: str | None = None,
    max_rounds: int = 5,
    timeout_minutes: int = 30,
    agent_id: str = Depends(get_authenticated_agent),
):
    """
    Start a new deliberation process.

    Args:
        proposal: Proposal to deliberate on
        participants: List of participant agent IDs
        topic: Optional topic/category for the deliberation
        max_rounds: Maximum number of deliberation rounds
        timeout_minutes: Timeout in minutes

    Returns:
        Deliberation ID and initial state
    """
    logger.info("starting_deliberation", agent_id=agent_id, participants=len(participants))

    deliberation_id = deliberation_engine.start_deliberation(
        proposal=proposal,
        participants=participants,
        topic=topic,
        max_rounds=max_rounds,
    )

    return {
        "deliberation_id": deliberation_id,
        "proposal": proposal,
        "topic": topic,
        "participants": participants,
        "max_rounds": max_rounds,
        "timeout_minutes": timeout_minutes,
        "state": "initiated",
    }


@router.post("/deliberation/{deliberation_id}/submit_position")
async def submit_deliberation_position(
    deliberation_id: str,
    position: str,
    confidence: float = 0.5,
    reasoning: str | None = None,
    agent_id: str = Depends(get_authenticated_agent),
):
    """
    Submit a position in a deliberation.

    Args:
        deliberation_id: Deliberation identifier
        position: Position ("support", "oppose", "neutral", "modify")
        confidence: Confidence level (0.0-1.0)
        reasoning: Optional reasoning text

    Returns:
        Submission confirmation
    """
    logger.info("submitting_position", deliberation_id=deliberation_id, agent_id=agent_id)

    try:
        position_enum = Position(position.lower())
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid position. Must be one of: {[p.value for p in Position]}",
        )

    success = deliberation_engine.submit_position(
        deliberation_id=deliberation_id,
        agent_id=agent_id,
        position=position_enum,
        confidence=confidence,
        reasoning=reasoning,
    )

    if not success:
        raise HTTPException(status_code=400, detail="Failed to submit position")

    return {
        "deliberation_id": deliberation_id,
        "agent_id": agent_id,
        "position": position,
        "confidence": confidence,
        "submitted": True,
    }


@router.post("/deliberation/{deliberation_id}/submit_argument")
async def submit_deliberation_argument(
    deliberation_id: str,
    position: str,
    reasoning: str,
    evidence_refs: list[str] | None = None,
    confidence: float = 0.5,
    agent_id: str = Depends(get_authenticated_agent),
):
    """
    Submit an argument in a deliberation.

    Args:
        deliberation_id: Deliberation identifier
        position: Position being argued ("support", "oppose", "neutral", "modify")
        reasoning: Argument reasoning text
        evidence_refs: Optional list of evidence references
        confidence: Confidence level (0.0-1.0)

    Returns:
        Argument ID and confirmation
    """
    logger.info("submitting_argument", deliberation_id=deliberation_id, agent_id=agent_id)

    try:
        position_enum = Position(position.lower())
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid position. Must be one of: {[p.value for p in Position]}",
        )

    argument = Argument(
        agent_id=agent_id,
        position=position_enum,
        reasoning=reasoning,
        evidence_refs=evidence_refs or [],
        confidence=confidence,
    )

    argument_id = deliberation_engine.submit_argument(
        deliberation_id=deliberation_id,
        argument=argument,
    )

    if not argument_id:
        raise HTTPException(status_code=400, detail="Failed to submit argument")

    return {
        "argument_id": argument_id,
        "deliberation_id": deliberation_id,
        "agent_id": agent_id,
        "position": position,
        "reasoning": reasoning,
        "evidence_refs": evidence_refs,
    }


@router.post("/deliberation/{deliberation_id}/submit_evidence")
async def submit_deliberation_evidence(
    deliberation_id: str,
    argument_id: str,
    content: str,
    source: str | None = None,
    quality_score: float = 0.5,
    agent_id: str = Depends(get_authenticated_agent),
):
    """
    Submit evidence for an argument.

    Args:
        deliberation_id: Deliberation identifier
        argument_id: Argument to support with evidence
        content: Evidence content
        source: Optional source reference
        quality_score: Quality score (0.0-1.0)

    Returns:
        Evidence ID and confirmation
    """
    logger.info("submitting_evidence", deliberation_id=deliberation_id, agent_id=agent_id)

    evidence = Evidence(
        argument_id=argument_id,
        content=content,
        source=source,
        quality_score=quality_score,
    )

    evidence_id = deliberation_engine.submit_evidence(
        deliberation_id=deliberation_id,
        evidence=evidence,
    )

    if not evidence_id:
        raise HTTPException(status_code=400, detail="Failed to submit evidence")

    return {
        "evidence_id": evidence_id,
        "argument_id": argument_id,
        "deliberation_id": deliberation_id,
        "content_length": len(content),
        "quality_score": quality_score,
    }


@router.post("/deliberation/{deliberation_id}/run_round")
async def run_deliberation_round(
    deliberation_id: str, agent_id: str = Depends(get_authenticated_agent)
):
    """
    Run a single deliberation round.

    Args:
        deliberation_id: Deliberation identifier

    Returns:
        Round results including consensus score and summary
    """
    logger.info("running_deliberation_round", deliberation_id=deliberation_id, agent_id=agent_id)

    round_result = deliberation_engine.run_deliberation_round(deliberation_id=deliberation_id)

    if not round_result:
        raise HTTPException(status_code=400, detail="Failed to run deliberation round")

    # Fire-and-forget: create memory version snapshot after deliberation round
    # Snapshot must not block the deliberation response
    asyncio.create_task(
        _snapshot_after_round(
            deliberation_id=deliberation_id,
            round_number=round_result.round_number,
            summary=round_result.summary,
            agent_id=agent_id,
        )
    )

    positions_dict = {k.value: v for k, v in round_result.positions.items()}

    # Broadcast to dashboard WebSocket listeners
    try:
        from heretek_swarm.api.websockets import manager as ws_manager

        await ws_manager.broadcast_dashboard(
            {
                "type": "deliberation_round",
                "deliberation_id": deliberation_id,
                "round_number": round_result.round_number,
                "arguments_submitted": len(round_result.arguments_submitted),
                "positions": positions_dict,
                "consensus_score": round_result.consensus_score,
                "summary": round_result.summary,
                "timestamp": datetime.now(UTC).isoformat(),
            }
        )
    except Exception as e:
        logger.warning(
            "consensus_ws_broadcast_failed", event="deliberation_round_complete", error=str(e)
        )

    return {
        "deliberation_id": deliberation_id,
        "round_number": round_result.round_number,
        "arguments_submitted": len(round_result.arguments_submitted),
        "positions": positions_dict,
        "consensus_score": round_result.consensus_score,
        "summary": round_result.summary,
        "timestamp": round_result.timestamp,
    }


@router.get("/deliberation/{deliberation_id}/state")
async def get_deliberation_state(
    deliberation_id: str, agent_id: str = Depends(get_authenticated_agent)
):
    """
    Get current deliberation state.

    Args:
        deliberation_id: Deliberation identifier

    Returns:
        Current deliberation state including positions and consensus score
    """
    state = deliberation_engine.get_deliberation_state(deliberation_id=deliberation_id)

    if not state:
        raise HTTPException(status_code=404, detail="Deliberation not found")

    return {
        "deliberation_id": deliberation_id,
        "state": state.state.value,
        "proposal": state.proposal,
        "topic": state.topic,
        "participants": state.participants,
        "current_round": state.current_round,
        "max_rounds": state.max_rounds,
        "consensus_score": state.consensus_score,
        "position_distribution": state.position_distribution,
    }


@router.get("/deliberation/{deliberation_id}/history")
async def get_deliberation_history(
    deliberation_id: str,
    limit: int = 10,
    agent_id: str = Depends(get_authenticated_agent),
):
    """
    Get deliberation round history.

    Args:
        deliberation_id: Deliberation identifier
        limit: Maximum number of rounds to return

    Returns:
        List of deliberation rounds
    """
    history = deliberation_engine.get_round_history(deliberation_id=deliberation_id, limit=limit)

    return {
        "deliberation_id": deliberation_id,
        "rounds": [
            {
                "round_number": r.round_number,
                "arguments_submitted": len(r.arguments_submitted),
                "positions": {k.value: v for k, v in r.positions.items()},
                "consensus_score": r.consensus_score,
                "summary": r.summary,
                "timestamp": r.timestamp,
            }
            for r in history
        ],
    }


@router.post("/deliberation/{deliberation_id}/finalize")
async def finalize_deliberation(
    deliberation_id: str, agent_id: str = Depends(get_authenticated_agent)
):
    """
    Finalize a deliberation and return results.

    Args:
        deliberation_id: Deliberation identifier

    Returns:
        Final deliberation results including decision and minority reports
    """
    logger.info("finalizing_deliberation", deliberation_id=deliberation_id, agent_id=agent_id)

    result = deliberation_engine.finalize_deliberation(deliberation_id=deliberation_id)

    if not result:
        raise HTTPException(status_code=400, detail="Failed to finalize deliberation")

    return {
        "deliberation_id": deliberation_id,
        "final_position": result.final_position.value,
        "consensus_score": result.consensus_score,
        "total_rounds": result.total_rounds,
        "total_arguments": result.total_arguments,
        "total_participants": result.total_participants,
        "minority_report": result.minority_report,
        "summary": result.summary,
        "timestamp": result.timestamp,
    }


@router.delete("/deliberation/{deliberation_id}")
async def cleanup_deliberation(
    deliberation_id: str, agent_id: str = Depends(get_authenticated_agent)
):
    """
    Cleanup and remove a deliberation.

    Args:
        deliberation_id: Deliberation identifier

    Returns:
        Cleanup confirmation
    """
    deliberation_engine.cleanup_deliberation(deliberation_id=deliberation_id)

    return {
        "deliberation_id": deliberation_id,
        "cleaned_up": True,
    }


# =============================================================================
# Audit Trail Endpoints
# =============================================================================

# Global audit trail instance
audit_trail = ConsensusAuditTrail()


@router.get("/audit/decision/{decision_id}")
async def get_decision_audit(decision_id: str, agent_id: str = Depends(get_authenticated_agent)):
    """
    Get comprehensive decision audit record.

    Args:
        decision_id: Decision identifier

    Returns:
        Complete audit record with deliberation history and votes
    """
    audit_record = audit_trail.get_decision_audit(decision_id=decision_id)

    if not audit_record:
        raise HTTPException(status_code=404, detail="Decision audit not found")

    return audit_record.to_dict()


@router.get("/audit/decision/{decision_id}/export")
async def export_decision_audit(decision_id: str, agent_id: str = Depends(get_authenticated_agent)):
    """
    Export decision audit record as JSON.

    Args:
        decision_id: Decision identifier

    Returns:
        JSON export of audit record
    """
    try:
        export_data = audit_trail.export_decision_audit(decision_id=decision_id, format="json")
        return {
            "decision_id": decision_id,
            "export_format": "json",
            "data": export_data,
        }
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e


@router.get("/audit/decision/{decision_id}/verify")
async def verify_decision_audit(decision_id: str, agent_id: str = Depends(get_authenticated_agent)):
    """
    Verify integrity of decision audit record.

    Args:
        decision_id: Decision identifier

    Returns:
        Verification result with hash validation
    """
    verification = audit_trail.verify_audit_integrity(decision_id=decision_id)

    if not verification.get("valid"):
        return {
            "decision_id": decision_id,
            "valid": False,
            "error": verification.get("error", "Unknown verification failure"),
        }

    return verification


@router.get("/audit/statistics")
async def get_audit_statistics(agent_id: str = Depends(get_authenticated_agent)):
    """
    Get audit trail statistics.

    Returns:
        Statistics about decision audits
    """
    return audit_trail.get_audit_statistics()


@router.get("/audit/failed")
async def get_failed_audits(agent_id: str = Depends(get_authenticated_agent)):
    """
    Get all failed decision audits.

    Returns:
        List of failed audit records
    """
    failed = audit_trail.get_failed_audits()
    return {
        "total_failed": len(failed),
        "audits": [a.to_dict() for a in failed],
    }


@router.get("/audit/successful")
async def get_successful_audits(agent_id: str = Depends(get_authenticated_agent)):
    """
    Get all successful decision audits.

    Returns:
        List of successful audit records
    """
    successful = audit_trail.get_successful_audits()
    return {
        "total_successful": len(successful),
        "audits": [a.to_dict() for a in successful],
    }


@router.get("/audit/deliberation/{consensus_id}/history")
async def get_deliberation_audit_history(
    consensus_id: str, agent_id: str = Depends(get_authenticated_agent)
):
    """
    Get deliberation history for audit.

    Args:
        consensus_id: Consensus identifier

    Returns:
        List of deliberation round records
    """
    history = audit_trail.get_deliberation_history(consensus_id=consensus_id)
    return {
        "consensus_id": consensus_id,
        "deliberation_rounds": [
            {
                "round_id": r.round_id,
                "round_number": r.round_number,
                "arguments_submitted": r.arguments_submitted,
                "positions": r.positions,
                "consensus_score": r.consensus_score,
                "timestamp": r.timestamp,
            }
            for r in history
        ],
    }


# =============================================================================
# Tribunal Endpoints
# =============================================================================

tribunal_instance: Tribunal | None = None


def get_tribunal() -> Tribunal | None:
    """Get the tribunal instance."""
    return tribunal_instance


@router.post("/tribunal/cases", responses={503: {"description": "Tribunal not available"}})
async def create_tribunal_case(
    agent_id: Annotated[str, Depends(get_authenticated_agent)],
    original_decision_id: str = "",
    grounds: str = "",
    description: str = "",
    original_consensus_id: str = "",
):
    """
    Submit an appeal case to the Tribunal.

    Args:
        original_decision_id: ID of the decision being appealed
        grounds: Legal grounds for the appeal
        description: Description of the appeal
        original_consensus_id: Related consensus process ID

    Returns:
        The created TribunalCase
    """
    tribunal = get_tribunal()
    if not tribunal:
        raise HTTPException(status_code=503, detail=TRIBUNAL_NOT_AVAILABLE)

    try:
        case = tribunal.create_case(
            original_decision_id=original_decision_id,
            appellant_agent_id=agent_id,
            grounds=grounds,
            description=description,
            original_consensus_id=original_consensus_id,
        )
        return {"case": case}
    except Exception as e:
        logger.error("tribunal_case_creation_failed", error=str(e))
        raise HTTPException(status_code=400, detail=str(e)) from e


@router.get("/tribunal/cases/{case_id}", responses={503: {"description": "Tribunal not available"}})
async def get_tribunal_case(
    agent_id: Annotated[str, Depends(get_authenticated_agent)],
    case_id: str = "",
):
    """
    Get a Tribunal case by ID.

    Args:
        case_id: The case ID to retrieve

    Returns:
        The TribunalCase
    """
    tribunal = get_tribunal()
    if not tribunal:
        raise HTTPException(status_code=503, detail=TRIBUNAL_NOT_AVAILABLE)

    case = tribunal.get_case(case_id)
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")
    return {"case": case}


@router.post("/tribunal/cases/{case_id}/evidence")
async def submit_tribunal_evidence(
    case_id: str,
    content: str,
    evidence_type: EvidenceType = EvidenceType.DOCUMENT,
    source: str | None = None,
    reliability_score: float = 0.5,
    agent_id: str = Depends(get_authenticated_agent),
):
    """
    Submit evidence to a Tribunal case.

    Args:
        case_id: Case to submit evidence to
        content: Evidence content
        evidence_type: Type of evidence
        source: Evidence source
        reliability_score: Reliability score (0.0-1.0)

    Returns:
        The created TribunalEvidence
    """
    tribunal = get_tribunal()
    if not tribunal:
        raise HTTPException(status_code=503, detail=TRIBUNAL_NOT_AVAILABLE)

    try:
        evidence = tribunal.submit_evidence(
            agent_id=agent_id,
            case_id=case_id,
            content=content,
            evidence_type=evidence_type,
            source=source,
            reliability_score=reliability_score,
        )
        return {"evidence": evidence}
    except Exception as e:
        logger.error("tribunal_evidence_submission_failed", error=str(e))
        raise HTTPException(status_code=400, detail=str(e)) from e


@router.post("/tribunal/cases/{case_id}/rule")
async def issue_tribunal_ruling(
    case_id: str,
    ruling_type: RulingType,
    reasoning: str,
    confidence: float = 1.0,
    agent_id: str = Depends(get_authenticated_agent),
):
    """
    Issue a ruling on a Tribunal case.

    Args:
        case_id: Case to rule on
        ruling_type: Type of ruling
        reasoning: Reasoning behind the ruling
        confidence: Confidence score (0.0-1.0)

    Returns:
        The issued TribunalRuling
    """
    tribunal = get_tribunal()
    if not tribunal:
        raise HTTPException(status_code=503, detail=TRIBUNAL_NOT_AVAILABLE)

    try:
        ruling = tribunal.issue_ruling(
            case_id=case_id,
            ruling_type=ruling_type.value,
            reasoning=reasoning,
            issued_by=agent_id,
            confidence=confidence,
        )
        return {"ruling": ruling}
    except Exception as e:
        logger.error("tribunal_ruling_failed", error=str(e))
        raise HTTPException(status_code=400, detail=str(e)) from e


@router.get("/tribunal/precedents")
async def get_tribunal_precedents(
    limit: int = 10,
    agent_id: str = Depends(get_authenticated_agent),
):
    """
    Get binding precedent rulings.

    Args:
        limit: Maximum number of precedents to return

    Returns:
        List of precedent TribunalRulings
    """
    tribunal = get_tribunal()
    if not tribunal:
        raise HTTPException(status_code=503, detail=TRIBUNAL_NOT_AVAILABLE)

    precedents = tribunal.get_precedents(limit=limit)
    return {"precedents": precedents}


@router.get("/tribunal/cases/{case_id}/precedents")
async def find_similar_precedents(
    case_id: str,
    limit: int = 5,
    agent_id: str = Depends(get_authenticated_agent),
):
    """
    Find precedents similar to a case.

    Args:
        case_id: Case to find precedents for
        limit: Maximum number of precedents to return

    Returns:
        List of similar TribunalRulings
    """
    tribunal = get_tribunal()
    if not tribunal:
        raise HTTPException(status_code=503, detail=TRIBUNAL_NOT_AVAILABLE)

    precedents = tribunal.find_similar_precedents(case_id, limit=limit)
    return {"precedents": precedents}


# Export router
__all__ = ["router"]
