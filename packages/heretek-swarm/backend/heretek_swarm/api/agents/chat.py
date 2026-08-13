"""
Chat API endpoint for agent messaging via triad deliberation.

This module provides a REST API endpoint for sending chat messages to agents,
which routes messages through the triad deliberation mechanism (alpha/beta/charlie)
and returns a synthesized response with per-agent contributions.
"""

import asyncio
import uuid
from contextlib import suppress
from typing import Annotated, Any

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from heretek_swarm.actors.supervisor import get_supervisor
from heretek_swarm.gateway.auth import verify_auth

logger = structlog.get_logger()

router = APIRouter()

# Constants for deliberation timeout
COLLECTION_TIMEOUT_SECONDS = 15  # Time to wait for triad vote responses
TOTAL_TIMEOUT_SECONDS = 30  # Total endpoint timeout


class ChatRequest(BaseModel):
    """Request body for chat endpoint."""

    message: str


class Contribution(BaseModel):
    """Contribution from a single agent."""

    agent_id: str
    role: str
    content: str
    timestamp: str


class ChatResponse(BaseModel):
    """Response from chat endpoint."""

    response: str
    contributions: list[Contribution]
    deliberation_id: str
    timeout: bool = False


def _get_supervisor() -> Any:
    """Dependency to get the actor supervisor."""
    return get_supervisor()


async def _collect_vote_responses(
    deliberation_id: str,
    expected_agents: list[str],
    timeout_seconds: int = COLLECTION_TIMEOUT_SECONDS,
) -> tuple[list[Contribution], bool]:
    """Collect vote responses from triad agents."""
    contributions: list[Contribution] = []
    received_agents: set[str] = set()
    timed_out = False
    try:
        response_queue: asyncio.Queue[Contribution] = asyncio.Queue()
        collect_task_handle = asyncio.create_task(
            _poll_for_responses(response_queue, expected_agents, timeout_seconds)
        )
        contributions, timed_out = await _drain_response_queue(
            response_queue, expected_agents, timeout_seconds
        )
        if not collect_task_handle.done():
            collect_task_handle.cancel()
            with suppress(asyncio.CancelledError):
                await collect_task_handle
    except Exception as e:
        logger.warning("Error collecting vote responses: %s", e)
    return contributions, timed_out


async def _poll_for_responses(
    queue: asyncio.Queue[Contribution], expected_agents: list[str], timeout_seconds: int
) -> list[Contribution]:
    collected: list[Contribution] = []
    deadline = asyncio.get_event_loop().time() + timeout_seconds
    while len(collected) < len(expected_agents):
        if asyncio.get_event_loop().time() >= deadline:
            break
        await asyncio.sleep(0.1)
    return collected


async def _drain_response_queue(
    queue: asyncio.Queue[Contribution], expected_agents: list[str], timeout_seconds: int
) -> tuple[list[Contribution], bool]:
    contributions: list[Contribution] = []
    received_agents: set[str] = set()
    deadline = asyncio.get_event_loop().time() + timeout_seconds
    while len(contributions) < len(expected_agents):
        remaining = deadline - asyncio.get_event_loop().time()
        if remaining <= 0:
            return contributions, True
        try:
            contribution = await asyncio.wait_for(queue.get(), timeout=min(remaining, 0.5))
            if contribution.agent_id not in received_agents:
                contributions.append(contribution)
                received_agents.add(contribution.agent_id)
        except TimeoutError:
            continue
    return contributions, False


def _get_agent_role(agent_id: str) -> str:
    """Get the role name for an agent."""
    roles = {
        "alpha": "Primary Analyst",
        "beta": "Secondary Analyst",
        "charlie": "Challenger",
        "steward": "Coordinator",
    }
    return roles.get(agent_id.lower(), agent_id)


def _synthesize_response(
    contributions: list[Contribution],
    original_message: str,
) -> str:
    """
    Synthesize a response from contributions.

    Args:
        contributions: List of agent contributions
        original_message: Original user message

    Returns:
        Synthesized response string
    """
    if not contributions:
        return (
            "I received your message but the triad deliberation did not produce "
            f"a response. Your message was: {original_message}"
        )

    # Join all contributions into a synthesized response
    response_parts = []
    for contrib in contributions:
        role_label = _get_agent_role(contrib.agent_id)
        response_parts.append(f"[{role_label}] {contrib.content}")

    synthesized = "\n\n".join(response_parts)

    # Add synthesis note if multiple contributions
    if len(contributions) > 1:
        synthesized = f"Based on deliberation with {len(contributions)} agents:\n\n{synthesized}"

    return synthesized


@router.post(
    "/{agent_id}/chat",
    response_model=ChatResponse,
    tags=["chat"],
)
async def send_chat_message(
    agent_id: str,
    request: ChatRequest,
    authenticated: Annotated[str, Depends(verify_auth)],
    supervisor: Annotated[Any, Depends(_get_supervisor)],
) -> ChatResponse:
    """
    Send a chat message to an agent.

    This endpoint routes messages through the triad deliberation mechanism
    (alpha/beta/charlie agents) and returns a synthesized response with
    per-agent contributions.

    The deliberation process:
    1. Creates a deliberation session
    2. Sends deliberation_request to triad members
    3. Collects vote_response messages within 15s
    4. Synthesizes a unified response
    5. Returns response with contributions (or timeout indication)

    Args:
        agent_id: Target agent ID (e.g., 'steward')
        request: Chat request containing the message
        authenticated: Authentication dependency
        supervisor: Actor supervisor dependency

    Returns:
        ChatResponse with synthesized response and per-agent contributions

    Raises:
        HTTPException: 404 if agent not found, 500 on deliberation error
    """
    deliberation_id = f"chat_{uuid.uuid4().hex[:12]}"

    logger.info(
        "Chat deliberation started",
        extra={
            "deliberation_id": deliberation_id,
            "agent_id": agent_id,
            "message_length": len(request.message),
        },
    )

    # Check if agent exists
    if agent_id not in supervisor.actors:
        logger.warning(
            "Chat request for unknown agent",
            extra={"agent_id": agent_id},
        )
        raise HTTPException(404, f"Agent '{agent_id}' not found")

    # Define triad agents to contact
    triad_agents = ["alpha", "beta", "charlie"]

    # Send deliberation requests to triad agents
    for triad_id in triad_agents:
        if triad_id in supervisor.actors:
            try:
                await supervisor.actors[triad_id].send_to_actor(
                    target_actor_id=triad_id,
                    message_type="deliberation_request",
                    content={
                        "deliberation_id": deliberation_id,
                        "topic": request.message,
                        "steward_id": agent_id,
                    },
                )
                logger.info(
                    "Deliberation request sent",
                    extra={
                        "deliberation_id": deliberation_id,
                        "triad_agent": triad_id,
                    },
                )
            except Exception as e:
                logger.warning(
                    "Failed to send to triad agent",
                    extra={
                        "triad_agent": triad_id,
                        "error": str(e),
                    },
                )

    # Collect responses from triad
    contributions: list[Contribution] = []
    timed_out = False

    try:
        # Wait for vote responses with timeout
        contributions, timed_out = await asyncio.wait_for(
            _collect_vote_responses(deliberation_id, triad_agents),
            timeout=TOTAL_TIMEOUT_SECONDS,
        )

        if timed_out:
            logger.warning(
                "Deliberation timed out with partial contributions",
                extra={
                    "deliberation_id": deliberation_id,
                    "contributions_received": len(contributions),
                    "expected": len(triad_agents),
                },
            )

    except TimeoutError:
        # Total timeout reached
        timed_out = True
        logger.warning(
            "Total deliberation timeout reached",
            extra={
                "deliberation_id": deliberation_id,
                "contributions_received": len(contributions),
            },
        )

    # Synthesize the response
    response_text = _synthesize_response(contributions, request.message)

    # Log structured info about deliberation
    logger.info(
        "Chat deliberation completed",
        extra={
            "deliberation_id": deliberation_id,
            "triad_members_reached": len(contributions),
            "synthesis_time_ms": 0,  # Could track actual synthesis time
            "timeout": timed_out,
        },
    )

    return ChatResponse(
        response=response_text,
        contributions=contributions,
        deliberation_id=deliberation_id,
        timeout=timed_out,
    )
