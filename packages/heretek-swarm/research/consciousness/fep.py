"""
FEP - Free Energy Principle Active Inference Implementation.

This module implements the Free Energy Principle (FEP) for active inference
in agent swarms. FEP provides a unified framework for understanding
perception, action, and learning in biological and artificial agents.

Key Concepts:
- Variational Free Energy: Upper bound on surprise
- Bayesian Surprise: Information gain from belief updates
- Expected Free Energy: Future free energy for policies
- Active Inference: Action selection minimizing expected free energy
- Generative Model: Agent's internal model of the world

References:
- Friston, K. (2010). The free-energy principle: a unified brain theory.
- Friston, K., et al. (2017). Active inference: a process theory.

Author: Heretek Swarm Collective
Date: 2026-04-15
Version: 1.0.0
"""

import math
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
from typing import Any

import structlog

logger = structlog.get_logger("FEPSelfModel")


class FreeEnergyLevel(Enum):
    """Free energy/surprise level classification."""

    VERY_LOW = "very_low"
    LOW = "low"
    MODERATE = "moderate"
    HIGH = "high"
    VERY_HIGH = "very_high"


class SurpriseLevel(Enum):
    """Surprise level classification."""

    MINIMAL = "minimal"
    LOW = "low"
    MODERATE = "moderate"
    HIGH = "high"
    EXTREME = "extreme"


@dataclass
class SurpriseMetrics:
    """
    Surprise minimization tracking metrics.

    Attributes:
        entity_id: Entity identifier
        current_surprise: Current surprise level (0-1)
        surprise_level: Classification of surprise level
        belief_updates: Number of belief updates
        total_surprise_reduced: Total surprise reduction achieved
        surprise_trend: Recent surprise trend
        timestamp: Measurement timestamp
    """

    entity_id: str
    current_surprise: float = 0.0
    surprise_level: SurpriseLevel = SurpriseLevel.MODERATE
    belief_updates: int = 0
    total_surprise_reduced: float = 0.0
    surprise_trend: list[float] = field(default_factory=list)
    timestamp: str = field(default_factory=lambda: datetime.now(UTC).isoformat())

    def to_dict(self) -> dict[str, Any]:
        return {
            "entity_id": self.entity_id,
            "current_surprise": self.current_surprise,
            "surprise_level": self.surprise_level.value,
            "belief_updates": self.belief_updates,
            "total_surprise_reduced": self.total_surprise_reduced,
            "surprise_trend": self.surprise_trend,
            "timestamp": self.timestamp,
        }


@dataclass
class ExpectedFreeEnergyMetrics:
    """
    Expected free energy calculation metrics.

    Attributes:
        entity_id: Entity identifier
        expected_free_energy: Calculated expected free energy
        free_energy_level: Classification of free energy level
        risk_component: Risk (divergence from preferences)
        ambiguity_component: Ambiguity (uncertainty about outcomes)
        policy_id: Policy that achieved minimum free energy
        timestamp: Measurement timestamp
    """

    entity_id: str
    expected_free_energy: float = 0.0
    free_energy_level: FreeEnergyLevel = FreeEnergyLevel.MODERATE
    risk_component: float = 0.0
    ambiguity_component: float = 0.0
    policy_id: str | None = None
    timestamp: str = field(default_factory=lambda: datetime.now(UTC).isoformat())

    def to_dict(self) -> dict[str, Any]:
        return {
            "entity_id": self.entity_id,
            "expected_free_energy": self.expected_free_energy,
            "free_energy_level": self.free_energy_level.value,
            "risk_component": self.risk_component,
            "ambiguity_component": self.ambiguity_component,
            "policy_id": self.policy_id,
            "timestamp": self.timestamp,
        }


@dataclass
class ActiveInferenceMetrics:
    """
    Active inference integration metrics.

    Attributes:
        entity_id: Entity identifier
        decisions_made: Number of decisions via active inference
        successful_inferences: Successful inference count
        belief_precision: Current belief precision (0-1)
        preference_alignment: Alignment with preferences (0-1)
        active_inference_score: Overall active inference score (0-1)
        timestamp: Measurement timestamp
    """

    entity_id: str
    decisions_made: int = 0
    successful_inferences: int = 0
    belief_precision: float = 0.5
    preference_alignment: float = 0.5
    active_inference_score: float = 0.0
    timestamp: str = field(default_factory=lambda: datetime.now(UTC).isoformat())

    def to_dict(self) -> dict[str, Any]:
        return {
            "entity_id": self.entity_id,
            "decisions_made": self.decisions_made,
            "successful_inferences": self.successful_inferences,
            "belief_precision": self.belief_precision,
            "preference_alignment": self.preference_alignment,
            "active_inference_score": self.active_inference_score,
            "timestamp": self.timestamp,
        }


@dataclass
class FEPMetrics:
    """
    Complete FEP metrics for an entity.

    Attributes:
        entity_id: Entity identifier
        surprise: Surprise minimization metrics
        expected_free_energy: Expected free energy metrics
        active_inference: Active inference metrics
        overall_fep_score: Combined FEP score (0-1)
        timestamp: Last update timestamp
    """

    entity_id: str
    surprise: SurpriseMetrics | None = None
    expected_free_energy: ExpectedFreeEnergyMetrics | None = None
    active_inference: ActiveInferenceMetrics | None = None
    overall_fep_score: float = 0.0
    timestamp: str = field(default_factory=lambda: datetime.now(UTC).isoformat())

    def to_dict(self) -> dict[str, Any]:
        return {
            "entity_id": self.entity_id,
            "surprise": self.surprise.to_dict() if self.surprise else None,
            "expected_free_energy": self.expected_free_energy.to_dict()
            if self.expected_free_energy
            else None,
            "active_inference": self.active_inference.to_dict() if self.active_inference else None,
            "overall_fep_score": self.overall_fep_score,
            "timestamp": self.timestamp,
        }


def calculate_surprise(
    observations: dict[str, Any],
    predictions: dict[str, Any],
) -> tuple[float, SurpriseLevel]:
    """
    Calculate surprise from observations and predictions.

    Args:
        observations: Observed data
        predictions: Predicted probability distribution

    Returns:
        Tuple of (surprise_value, surprise_level)
    """
    if not observations or not predictions:
        return 0.0, SurpriseLevel.MODERATE

    surprise = 0.0

    for key, obs_value in observations.items():
        if key in predictions:
            pred_dist = predictions[key]
            if isinstance(pred_dist, dict):
                prob = pred_dist.get(str(obs_value), pred_dist.get(obs_value, 0.0))
                if prob > 0:
                    surprise -= math.log(prob + 1e-10)
                else:
                    surprise += 10.0
            elif isinstance(pred_dist, (int, float)):
                prob = pred_dist
                if prob > 0:
                    surprise -= math.log(prob + 1e-10)
                else:
                    surprise += 10.0

    normalized_surprise = math.tanh(surprise / 5.0)
    normalized_surprise = min(1.0, max(0.0, normalized_surprise))

    surprise_level = SurpriseLevel.MODERATE
    if normalized_surprise >= 0.9:
        surprise_level = SurpriseLevel.EXTREME
    elif normalized_surprise >= 0.7:
        surprise_level = SurpriseLevel.HIGH
    elif normalized_surprise >= 0.5:
        surprise_level = SurpriseLevel.MODERATE
    elif normalized_surprise >= 0.3:
        surprise_level = SurpriseLevel.LOW
    else:
        surprise_level = SurpriseLevel.MINIMAL

    return normalized_surprise, surprise_level


def calculate_expected_free_energy(
    policy_outcomes: dict[str, float],
    preferences: dict[str, float],
) -> tuple[float, float, float]:
    """
    Calculate expected free energy for a policy.

    Args:
        policy_outcomes: Predicted outcomes from policy
        preferences: Preferred outcome values

    Returns:
        Tuple of (expected_free_energy, risk_component, ambiguity_component)
    """
    risk = 0.0
    for key, outcome_value in policy_outcomes.items():
        if key in preferences:
            risk += abs(outcome_value - preferences[key])

    outcome_dist = {k: v for k, v in policy_outcomes.items() if isinstance(v, (int, float))}
    entropy = 0.0
    if outcome_dist:
        total = sum(outcome_dist.values())
        if total > 0:
            normalized = {k: v / total for k, v in outcome_dist.items()}
            for prob in normalized.values():
                if prob > 0:
                    entropy -= prob * math.log2(prob + 1e-10)

    ambiguity = entropy / 10.0

    expected_fe = risk + ambiguity

    return expected_fe, risk, ambiguity


def calculate_free_energy(
    observations: dict[str, Any],
    generative_model: dict[str, Any],
) -> float:
    """
    Calculate variational free energy.

    Args:
        observations: Observed data
        generative_model: Generative model with likelihood and prior

    Returns:
        Variational free energy value (lower is better)
    """
    if not generative_model:
        return 0.5

    likelihood = generative_model.get("likelihood", {})
    prior = generative_model.get("prior", {})

    expected_energy = 0.0
    for key, obs_value in observations.items():
        if key in likelihood:
            like_dist = likelihood[key]
            if isinstance(like_dist, dict):
                prob = like_dist.get(str(obs_value), like_dist.get(obs_value, 0.5))
                if prob > 0:
                    expected_energy -= math.log(prob + 1e-10)
            elif isinstance(like_dist, (int, float)):
                if like_dist > 0:
                    expected_energy -= math.log(like_dist + 1e-10)

    entropy = 0.0
    for prob in prior.values():
        if isinstance(prob, (int, float)) and prob > 0:
            entropy -= prob * math.log2(prob + 1e-10)

    kl_div = 0.0
    for q_prob in prior.values():
        if isinstance(q_prob, (int, float)) and q_prob > 0:
            p_prob = 0.5
            kl_div += q_prob * math.log(q_prob / (p_prob + 1e-10))

    free_energy = expected_energy - entropy + kl_div
    return min(1.0, max(0.0, 1.0 / (1.0 + math.exp(-free_energy + 2.5))))


def create_fep_metrics(
    entity_id: str,
    agent_state: dict[str, Any],
) -> FEPMetrics:
    """
    Create comprehensive FEP metrics for an entity.

    Args:
        entity_id: Entity identifier
        agent_state: Agent state containing FEP data

    Returns:
        FEPMetrics for the entity
    """
    observations = agent_state.get("observations", {})
    predictions = agent_state.get("predictions", {})
    preferences = agent_state.get("preferences", {})

    current_surprise, surprise_level = calculate_surprise(observations, predictions)

    previous_surprise = agent_state.get("previous_surprise", current_surprise)
    surprise_reduced = max(0.0, previous_surprise - current_surprise)

    surprise_trend = agent_state.get("surprise_trend", [])
    surprise_trend.append(current_surprise)
    if len(surprise_trend) > 10:
        surprise_trend = surprise_trend[-10:]

    surprise_metrics = SurpriseMetrics(
        entity_id=entity_id,
        current_surprise=current_surprise,
        surprise_level=surprise_level,
        belief_updates=agent_state.get("belief_updates", 0),
        total_surprise_reduced=agent_state.get("total_surprise_reduced", 0.0) + surprise_reduced,
        surprise_trend=surprise_trend,
    )

    policy_outcomes = agent_state.get("policy_outcomes", {})
    expected_fe, risk, ambiguity = calculate_expected_free_energy(policy_outcomes, preferences)

    free_energy_level = FreeEnergyLevel.MODERATE
    if expected_fe >= 0.9:
        free_energy_level = FreeEnergyLevel.VERY_HIGH
    elif expected_fe >= 0.7:
        free_energy_level = FreeEnergyLevel.HIGH
    elif expected_fe >= 0.5:
        free_energy_level = FreeEnergyLevel.MODERATE
    elif expected_fe >= 0.3:
        free_energy_level = FreeEnergyLevel.LOW
    else:
        free_energy_level = FreeEnergyLevel.VERY_LOW

    expected_fe_metrics = ExpectedFreeEnergyMetrics(
        entity_id=entity_id,
        expected_free_energy=expected_fe,
        free_energy_level=free_energy_level,
        risk_component=risk,
        ambiguity_component=ambiguity,
        policy_id=agent_state.get("selected_policy_id"),
    )

    decisions = agent_state.get("decisions_made", 0)
    successful = agent_state.get("successful_inferences", 0)
    belief_precision = agent_state.get("belief_precision", 0.5)
    preference_alignment = agent_state.get("preference_alignment", 0.5)

    active_inference_score = (
        (successful / max(1, decisions) * 0.3 if decisions > 0 else 0.0)
        + belief_precision * 0.3
        + preference_alignment * 0.2
        + (1.0 - current_surprise) * 0.2
    )

    active_inference_metrics = ActiveInferenceMetrics(
        entity_id=entity_id,
        decisions_made=decisions,
        successful_inferences=successful,
        belief_precision=belief_precision,
        preference_alignment=preference_alignment,
        active_inference_score=min(1.0, active_inference_score),
    )

    overall_score = (
        (1.0 - current_surprise) * 0.3 + (1.0 - expected_fe) * 0.3 + active_inference_score * 0.4
    )

    return FEPMetrics(
        entity_id=entity_id,
        surprise=surprise_metrics,
        expected_free_energy=expected_fe_metrics,
        active_inference=active_inference_metrics,
        overall_fep_score=min(1.0, overall_score),
    )


_entity_fep_metrics: dict[str, FEPMetrics] = {}


def update_fep_metrics(entity_id: str, metrics: FEPMetrics) -> None:
    """Update FEP metrics for an entity."""
    _entity_fep_metrics[entity_id] = metrics


def get_fep_metrics(entity_id: str) -> FEPMetrics | None:
    """Get FEP metrics for an entity."""
    return _entity_fep_metrics.get(entity_id)


def get_all_fep_metrics() -> dict[str, FEPMetrics]:
    """Get all tracked FEP metrics."""
    return _entity_fep_metrics.copy()


class FEPTracker:
    """
    Tracker for FEP metrics with history and analysis.

    Provides methods for tracking surprise minimization,
    expected free energy, and active inference over time.
    """

    def __init__(self, history_limit: int = 100):
        self._history: dict[str, list[FEPMetrics]] = {}
        self._history_limit = history_limit

    def track(self, entity_id: str, agent_state: dict[str, Any]) -> FEPMetrics:
        """
        Track FEP metrics for an entity.

        Args:
            entity_id: Entity identifier
            agent_state: Current agent state

        Returns:
            FEPMetrics for the entity
        """
        metrics = create_fep_metrics(entity_id, agent_state)

        if entity_id not in self._history:
            self._history[entity_id] = []
        self._history[entity_id].append(metrics)

        if len(self._history[entity_id]) > self._history_limit:
            self._history[entity_id] = self._history[entity_id][-self._history_limit :]

        update_fep_metrics(entity_id, metrics)

        return metrics

    def get_history(self, entity_id: str) -> list[FEPMetrics]:
        """Get FEP metrics history for an entity."""
        return self._history.get(entity_id, [])

    def get_surprise_trend(self, entity_id: str) -> list[float]:
        """Get surprise values over time."""
        history = self._history.get(entity_id, [])
        return [m.surprise.current_surprise if m.surprise else 0.0 for m in history]

    def get_free_energy_trend(self, entity_id: str) -> list[float]:
        """Get expected free energy values over time."""
        history = self._history.get(entity_id, [])
        return [
            m.expected_free_energy.expected_free_energy if m.expected_free_energy else 0.0
            for m in history
        ]

    def get_active_inference_trend(self, entity_id: str) -> list[float]:
        """Get active inference scores over time."""
        history = self._history.get(entity_id, [])
        return [
            m.active_inference.active_inference_score if m.active_inference else 0.0
            for m in history
        ]

    def get_statistics(self, entity_id: str) -> dict[str, Any]:
        """Get statistics for an entity's FEP history."""
        history = self._history.get(entity_id, [])
        if not history:
            return {}

        surprise_values = [m.surprise.current_surprise if m.surprise else 0.0 for m in history]
        fe_values = [
            m.expected_free_energy.expected_free_energy if m.expected_free_energy else 0.0
            for m in history
        ]
        ai_scores = [
            m.active_inference.active_inference_score if m.active_inference else 0.0
            for m in history
        ]
        overall_scores = [m.overall_fep_score for m in history]

        return {
            "surprise": {
                "mean": sum(surprise_values) / len(surprise_values),
                "min": min(surprise_values),
                "max": max(surprise_values),
                "current": surprise_values[-1],
            },
            "free_energy": {
                "mean": sum(fe_values) / len(fe_values),
                "min": min(fe_values),
                "max": max(fe_values),
                "current": fe_values[-1],
            },
            "active_inference": {
                "mean": sum(ai_scores) / len(ai_scores),
                "min": min(ai_scores),
                "max": max(ai_scores),
                "current": ai_scores[-1],
            },
            "overall": {
                "mean": sum(overall_scores) / len(overall_scores),
                "min": min(overall_scores),
                "max": max(overall_scores),
                "current": overall_scores[-1],
            },
            "samples": len(history),
        }
