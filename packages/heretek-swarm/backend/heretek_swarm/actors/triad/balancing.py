"""
Triad Balancing - Balancing Algorithm Helpers for Triad Agents.

This module contains balancing-related utilities for the Triad agent system.

Author: Heretek Swarm Collective
Date: 2026-04-17
Version: 1.0.0
"""

from __future__ import annotations

from typing import Any


def calculate_deliberation_weight(
    agent_type: str,
    confidence: float,
    role_weights: dict[str, float] | None = None,
) -> float:
    """
    Calculate deliberation weight for an agent.

    Args:
        agent_type: Type of agent (steward, alpha, beta, charlie)
        confidence: Confidence level (0-1)
        role_weights: Optional role weights override

    Returns:
        Calculated weight for deliberation
    """
    if role_weights is None:
        role_weights = {
            "steward": 1.0,
            "alpha": 0.9,
            "beta": 0.85,
            "charlie": 0.8,
        }

    base_weight = role_weights.get(agent_type.lower(), 0.7)
    return base_weight * confidence


def aggregate_votes(
    votes: list[dict[str, Any]],
    weights: dict[str, float] | None = None,
) -> dict[str, Any]:
    """
    Aggregate votes from multiple agents with weights.

    Args:
        votes: List of vote dicts with agent_id, decision, confidence
        weights: Optional weight overrides

    Returns:
        Aggregated result with weighted decision
    """
    if not votes:
        return {"decision": None, "confidence": 0.0}

    total_weight = 0.0
    weighted_confidence = 0.0

    for vote in votes:
        agent_id = vote.get("agent_id", "unknown")
        confidence = vote.get("confidence", 0.5)
        weight = (weights or {}).get(agent_id, 1.0)

        total_weight += weight
        weighted_confidence += confidence * weight

    avg_confidence = weighted_confidence / total_weight if total_weight > 0 else 0.0

    # Use most common decision
    decisions = [v.get("decision") for v in votes]
    decision = max(set(decisions), key=decisions.count) if decisions else None

    return {
        "decision": decision,
        "confidence": avg_confidence,
        "vote_count": len(votes),
    }


__all__ = ["aggregate_votes", "calculate_deliberation_weight"]
