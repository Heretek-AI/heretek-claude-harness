"""
Agent Expertise Profiling - Dynamic expertise scoring for consensus weighting.

This module provides comprehensive agent expertise tracking and calibration:
- Dynamic expertise scoring per domain
- Historical accuracy tracking
- Confidence calibration
- Expertise-based vote weighting

The expertise system enables more informed consensus decisions by weighting
agent votes based on their demonstrated expertise in relevant domains.

Example:
    ```python
    from heretek_swarm.consensus.expertise import AgentExpertiseProfiler

    # Initialize profiler
    profiler = AgentExpertiseProfiler()

    # Register agent with initial expertise
    profiler.register_agent("agent-1", domains=["code_review", "security"])

    # Record decision outcome
    profiler.record_outcome(
        agent_id="agent-1",
        domain="code_review",
        was_correct=True,
        confidence=0.9
    )

    # Get expertise-weighted confidence
    weighted_confidence = profiler.get_weighted_confidence(
        agent_id="agent-1",
        domain="code_review",
        base_confidence=0.85
    )
    ```
"""

import statistics
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
from typing import Any

import structlog

logger = structlog.get_logger("AgentExpertiseProfiler")


class ExpertiseLevel(Enum):
    """Expertise level classifications."""

    NOVICE = "novice"  # 0.0 - 0.3
    INTERMEDIATE = "intermediate"  # 0.3 - 0.6
    EXPERT = "expert"  # 0.6 - 0.85
    MASTER = "master"  # 0.85 - 1.0


@dataclass
class DomainExpertise:
    """
    Expertise tracking for a specific domain.

    Attributes:
        domain: Domain name
        expertise_score: Current expertise score (0.0 to 1.0)
        total_decisions: Total decisions made in this domain
        correct_decisions: Number of correct decisions
        avg_confidence: Average confidence in this domain
        confidence_calibration: How well confidence matches accuracy
        last_updated: Last update timestamp
        recent_outcomes: Recent outcome history for trend analysis
        peer_trust_scores: Trust scores from other agents (agent_id -> trust score)
        evidence_quality_avg: Average quality of evidence provided
        collaboration_count: Number of successful collaborations
    """

    domain: str
    expertise_score: float = 0.5
    total_decisions: int = 0
    correct_decisions: int = 0
    avg_confidence: float = 0.5
    confidence_calibration: float = 0.0
    last_updated: str = field(default_factory=lambda: datetime.now(UTC).isoformat())
    recent_outcomes: list[dict[str, Any]] = field(default_factory=list)

    # Peer trust tracking (NEW)
    peer_trust_scores: dict[str, float] = field(default_factory=dict)
    evidence_quality_avg: float = 0.5
    collaboration_count: int = 0

    def __post_init__(self) -> None:
        """Validate expertise score range."""
        self.expertise_score = max(0.0, min(1.0, self.expertise_score))
        self.avg_confidence = max(0.0, min(1.0, self.avg_confidence))
        self.confidence_calibration = max(-1.0, min(1.0, self.confidence_calibration))

    @property
    def accuracy(self) -> float:
        """Calculate accuracy rate."""
        if self.total_decisions == 0:
            return 0.5
        return self.correct_decisions / self.total_decisions

    @property
    def expertise_level(self) -> ExpertiseLevel:
        """Determine expertise level from score."""
        if self.expertise_score >= 0.85:
            return ExpertiseLevel.MASTER
        if self.expertise_score >= 0.6:
            return ExpertiseLevel.EXPERT
        if self.expertise_score >= 0.3:
            return ExpertiseLevel.INTERMEDIATE
        return ExpertiseLevel.NOVICE

    def get_expertise_multiplier(self) -> float:
        """
        Get expertise multiplier for vote weighting.

        Returns:
            Multiplier value (0.5 to 1.5)
        """
        # Map expertise score to multiplier range [0.5, 1.5]
        return 0.5 + (self.expertise_score * 1.0)

    def get_peer_trust_score(self) -> float:
        """
        Calculate average peer trust score.

        Returns:
            Average trust score from peers (0.0 to 1.0)
        """
        if not self.peer_trust_scores:
            return 0.5  # Default trust for new agents

        return sum(self.peer_trust_scores.values()) / len(self.peer_trust_scores)

    def update_peer_trust(self, peer_id: str, trust_delta: float) -> None:
        """
        Update trust score from a specific peer.

        Args:
            peer_id: ID of the peer agent
            trust_delta: Change in trust score (-0.1 to +0.1 recommended)
        """
        current_trust = self.peer_trust_scores.get(peer_id, 0.5)
        new_trust = max(0.0, min(1.0, current_trust + trust_delta))
        self.peer_trust_scores[peer_id] = new_trust
        self.last_updated = datetime.now(UTC).isoformat()

    def record_evidence_quality(self, quality_score: float) -> None:
        """
        Record evidence quality score for running average.

        Args:
            quality_score: Quality score of evidence (0.0 to 1.0)
        """
        # Update running average
        total = self.total_decisions
        if total == 0:
            self.evidence_quality_avg = quality_score
        else:
            self.evidence_quality_avg = (self.evidence_quality_avg * total + quality_score) / (
                total + 1
            )


@dataclass
class AgentExpertiseProfile:
    """
    Complete expertise profile for an agent.

    Attributes:
        agent_id: Agent identifier
        domains: Dictionary of domain expertise
        overall_reputation: Overall reputation score
        total_decisions: Total decisions across all domains
        created_at: Profile creation timestamp
        last_active: Last activity timestamp
        peer_trust_score: Overall peer trust score across all domains
    """

    agent_id: str
    domains: dict[str, DomainExpertise] = field(default_factory=dict)
    overall_reputation: float = 0.5
    total_decisions: int = 0
    created_at: str = field(default_factory=lambda: datetime.now(UTC).isoformat())
    last_active: str = field(default_factory=lambda: datetime.now(UTC).isoformat())
    peer_trust_score: float = 0.5

    def get_expertise_for_domain(self, domain: str) -> DomainExpertise:
        """Get expertise for a specific domain, creating if needed."""
        if domain not in self.domains:
            self.domains[domain] = DomainExpertise(domain=domain)
        return self.domains[domain]

    def get_domains(self) -> list[str]:
        """Get list of domains with expertise."""
        return list(self.domains.keys())

    def get_primary_domain(self) -> str | None:
        """Get agent's primary (highest expertise) domain."""
        if not self.domains:
            return None
        return max(self.domains.items(), key=lambda x: x[1].expertise_score)[0]


class AgentExpertiseProfiler:
    """
    Agent Expertise Profiler for consensus weighting.

    Provides comprehensive expertise tracking and calibration:
    - Dynamic expertise scoring per domain
    - Historical accuracy tracking
    - Confidence calibration
    - Expertise-based vote weighting

    The profiler tracks agent performance across multiple domains,
    adjusting expertise scores based on decision outcomes and
    confidence calibration.

    Attributes:
        profiles: Dictionary of agent profiles
        domain_statistics: Global statistics per domain
        calibration_window: Number of recent outcomes for calibration
    """

    def __init__(self, calibration_window: int = 20) -> None:
        """
        Initialize the expertise profiler.

        Args:
            calibration_window: Number of recent outcomes for calibration
        """
        self.profiles: dict[str, AgentExpertiseProfile] = {}
        self.domain_statistics: dict[str, dict[str, Any]] = {}
        self.calibration_window = calibration_window

        logger.info(
            f"AgentExpertiseProfiler initialized with calibration_window={calibration_window}"  # noqa: G004
        )

    def register_agent(
        self,
        agent_id: str,
        domains: list[str] | None = None,
        initial_expertise: float = 0.5,
    ) -> AgentExpertiseProfile:
        """
        Register a new agent with optional initial domains.

        Args:
            agent_id: Unique agent identifier
            domains: List of domains the agent specializes in
            initial_expertise: Initial expertise score (0.0 to 1.0)

        Returns:
            Created agent profile
        """
        if agent_id in self.profiles:
            logger.warning("Agent {agent_id} already registered, updating domains")
            profile = self.profiles[agent_id]
            if domains:
                for domain in domains:
                    if domain not in profile.domains:
                        profile.domains[domain] = DomainExpertise(
                            domain=domain, expertise_score=initial_expertise
                        )
            return profile

        profile = AgentExpertiseProfile(agent_id=agent_id)
        if domains:
            for domain in domains:
                profile.domains[domain] = DomainExpertise(
                    domain=domain, expertise_score=initial_expertise
                )

        self.profiles[agent_id] = profile
        logger.info("Registered agent {agent_id} with domains: {domains or 'none'}")
        return profile

    def record_outcome(
        self,
        agent_id: str,
        domain: str,
        was_correct: bool,
        confidence: float,
        decision_outcome: Any | None = None,
    ) -> None:
        """
        Record a decision outcome for expertise tracking.

        Args:
            agent_id: Agent identifier
            domain: Domain of the decision
            was_correct: Whether the decision was correct
            confidence: Agent's confidence in the decision
            decision_outcome: Optional actual outcome data
        """
        if agent_id not in self.profiles:
            self.register_agent(agent_id, [domain])

        profile = self.profiles[agent_id]
        domain_expertise = profile.get_expertise_for_domain(domain)

        # Update domain statistics
        domain_expertise.total_decisions += 1
        if was_correct:
            domain_expertise.correct_decisions += 1

        # Update average confidence
        n = domain_expertise.total_decisions
        domain_expertise.avg_confidence = (
            domain_expertise.avg_confidence * (n - 1) + confidence
        ) / n

        # Record recent outcome for trend analysis
        outcome_record = {
            "timestamp": datetime.now(UTC).isoformat(),
            "was_correct": was_correct,
            "confidence": confidence,
            "outcome": decision_outcome,
        }
        domain_expertise.recent_outcomes.append(outcome_record)

        # Keep only recent outcomes within calibration window
        if len(domain_expertise.recent_outcomes) > self.calibration_window:
            domain_expertise.recent_outcomes = domain_expertise.recent_outcomes[
                -self.calibration_window :
            ]

        # Update expertise score
        domain_expertise.expertise_score = self._calculate_expertise_score(domain_expertise)

        # Update confidence calibration
        domain_expertise.confidence_calibration = self._calculate_confidence_calibration(
            domain_expertise
        )

        # Update overall reputation
        profile.overall_reputation = self._calculate_overall_reputation(profile)
        profile.total_decisions += 1
        profile.last_active = datetime.now(UTC).isoformat()

        # Update global domain statistics
        self._update_domain_statistics(domain, was_correct, confidence)

        logger.debug(
            f"Recorded outcome for {agent_id} in {domain}: "  # noqa: G004
            f"correct={was_correct}, confidence={confidence:.2f}, "
            f"new_expertise={domain_expertise.expertise_score:.2f}"
        )

    def record_peer_trust(
        self,
        agent_id: str,
        domain: str,
        peer_id: str,
        trust_delta: float,
    ) -> None:
        """
        Record peer trust update for an agent.

        Args:
            agent_id: Agent receiving trust update
            domain: Domain of the interaction
            peer_id: Agent giving the trust update
            trust_delta: Change in trust (-0.1 to +0.1 recommended)
        """
        if agent_id not in self.profiles:
            return

        profile = self.profiles[agent_id]
        domain_expertise = profile.get_expertise_for_domain(domain)

        # Update peer trust in domain expertise
        domain_expertise.update_peer_trust(peer_id, trust_delta)

        logger.info(
            f"Recorded peer trust for {agent_id} in {domain} from {peer_id}: {trust_delta:+.2f}"  # noqa: G004
        )

        # Update overall peer trust score
        self._update_peer_trust_score(profile)

        logger.debug(
            f"Peer trust updated for {agent_id} from {peer_id} "  # noqa: G004
            f"in {domain}: delta={trust_delta:+.3f}"
        )

    def _update_peer_trust_score(self, profile: AgentExpertiseProfile) -> None:
        """
        Update overall peer trust score for a profile.

        Args:
            profile: Agent expertise profile
        """
        all_trust_scores = []
        for domain_expertise in profile.domains.values():
            all_trust_scores.extend(domain_expertise.peer_trust_scores.values())

        if all_trust_scores:
            profile.peer_trust_score = sum(all_trust_scores) / len(all_trust_scores)
        else:
            profile.peer_trust_score = 0.5

    def record_collaboration(
        self,
        agent_id: str,
        domain: str,
        success: bool,
    ) -> None:
        """
        Record a collaboration event for an agent.

        Args:
            agent_id: Agent identifier
            domain: Domain of collaboration
            success: Whether collaboration was successful
        """
        if agent_id not in self.profiles:
            return

        profile = self.profiles[agent_id]
        domain_expertise = profile.get_expertise_for_domain(domain)

        if success:
            domain_expertise.collaboration_count += 1

            # Bonus trust update for successful collaboration
            domain_expertise.expertise_score = min(1.0, domain_expertise.expertise_score + 0.02)

        self._update_peer_trust_score(profile)

    def get_peer_trust_weight(self, agent_id: str, domain: str | None = None) -> float:
        """
        Get peer trust weight for vote weighting.

        Args:
            agent_id: Agent identifier
            domain: Optional specific domain

        Returns:
            Peer trust weight (0.0 to 1.0)
        """
        if agent_id not in self.profiles:
            return 0.5

        profile = self.profiles[agent_id]

        if domain and domain in profile.domains:
            return profile.domains[domain].get_peer_trust_score()

        return profile.peer_trust_score

    def _calculate_expertise_score(self, domain_expertise: DomainExpertise) -> float:
        """
        Calculate expertise score based on accuracy and recency.

        Args:
            domain_expertise: Domain expertise data

        Returns:
            Calculated expertise score (0.0 to 1.0)
        """
        if domain_expertise.total_decisions == 0:
            return 0.5

        # Base accuracy
        accuracy = domain_expertise.accuracy

        # Recency weight - recent outcomes matter more
        recent_outcomes = domain_expertise.recent_outcomes
        if recent_outcomes:
            recent_accuracy = sum(1 for o in recent_outcomes if o["was_correct"]) / len(
                recent_outcomes
            )
            # Weight recent performance 60%, historical 40%
            accuracy = 0.4 * accuracy + 0.6 * recent_accuracy

        # Experience bonus - more decisions increase confidence in score
        experience_factor = min(1.0, domain_expertise.total_decisions / self.calibration_window)

        # Final score with experience factor
        score = 0.5 + (accuracy - 0.5) * experience_factor

        return max(0.0, min(1.0, score))

    def _calculate_confidence_calibration(self, domain_expertise: DomainExpertise) -> float:
        """
        Calculate how well agent's confidence matches actual accuracy.

        Positive values indicate good calibration (confidence matches accuracy).
        Negative values indicate overconfidence or underconfidence.

        Args:
            domain_expertise: Domain expertise data

        Returns:
            Calibration score (-1.0 to 1.0)
        """
        recent_outcomes = domain_expertise.recent_outcomes
        if len(recent_outcomes) < 3:
            return 0.0  # Not enough data

        # Calculate average confidence and accuracy for recent outcomes
        avg_confidence = statistics.mean(o["confidence"] for o in recent_outcomes)
        recent_accuracy = sum(1 for o in recent_outcomes if o["was_correct"]) / len(recent_outcomes)

        # Calibration = 1 - |confidence - accuracy|
        # Perfect calibration when confidence equals accuracy
        calibration = 1.0 - abs(avg_confidence - recent_accuracy)

        # Scale to -1.0 to 1.0 range
        # Positive when well-calibrated, negative when poorly calibrated
        if calibration > 0.5:
            return calibration * 2 - 1.0
        return calibration * 2

    def _calculate_overall_reputation(self, profile: AgentExpertiseProfile) -> float:
        """
        Calculate overall reputation from domain expertise.

        Args:
            profile: Agent expertise profile

        Returns:
            Overall reputation score (0.0 to 1.0)
        """
        if not profile.domains:
            return 0.5

        # Weighted average of domain expertise
        total_weight = 0
        weighted_sum = 0.0

        for domain_expertise in profile.domains.values():
            # Weight by number of decisions (more experience = more weight)
            weight = max(1, domain_expertise.total_decisions)
            weighted_sum += domain_expertise.expertise_score * weight
            total_weight += weight

        return weighted_sum / total_weight if total_weight > 0 else 0.5

    def _update_domain_statistics(self, domain: str, was_correct: bool, confidence: float) -> None:
        """
        Update global domain statistics.

        Args:
            domain: Domain name
            was_correct: Whether decision was correct
            confidence: Decision confidence
        """
        if domain not in self.domain_statistics:
            self.domain_statistics[domain] = {
                "total_decisions": 0,
                "correct_decisions": 0,
                "avg_confidence": 0.0,
                "participating_agents": set(),
            }

        stats = self.domain_statistics[domain]
        stats["total_decisions"] += 1
        if was_correct:
            stats["correct_decisions"] += 1

        # Update average confidence
        n = stats["total_decisions"]
        stats["avg_confidence"] = (stats["avg_confidence"] * (n - 1) + confidence) / n

    def get_weighted_confidence(
        self,
        agent_id: str,
        domain: str,
        base_confidence: float,
    ) -> float:
        """
        Get expertise-weighted confidence for an agent's vote.

        Args:
            agent_id: Agent identifier
            domain: Domain of the decision
            base_confidence: Agent's stated confidence

        Returns:
            Weighted confidence (0.0 to 1.0)
        """
        if agent_id not in self.profiles:
            return base_confidence  # No profile, use base confidence

        profile = self.profiles[agent_id]
        domain_expertise = profile.get_expertise_for_domain(domain)

        # Get expertise multiplier
        multiplier = domain_expertise.get_expertise_multiplier()

        # Apply multiplier to base confidence
        weighted_confidence = base_confidence * multiplier

        # Adjust based on confidence calibration
        calibration_factor = 1.0 + (domain_expertise.confidence_calibration * 0.2)
        weighted_confidence *= calibration_factor

        # Ensure valid range
        return max(0.0, min(1.0, weighted_confidence))

    def get_expertise_for_domain(
        self,
        agent_id: str,
        domain: str,
    ) -> DomainExpertise | None:
        """
        Get complete domain expertise for an agent.

        Args:
            agent_id: Agent identifier
            domain: Domain name

        Returns:
            Domain expertise or None if agent not found
        """
        if agent_id not in self.profiles:
            return None

        profile = self.profiles[agent_id]
        return profile.get_expertise_for_domain(domain)

    def get_expertise_score(
        self,
        agent_id: str,
        domain: str | None = None,
    ) -> float:
        """
        Get expertise score for an agent.

        Args:
            agent_id: Agent identifier
            domain: Optional specific domain (uses overall if None)

        Returns:
            Expertise score (0.0 to 1.0)
        """
        if agent_id not in self.profiles:
            return 0.5  # Default for unknown agents

        profile = self.profiles[agent_id]

        if domain:
            domain_expertise = profile.get_expertise_for_domain(domain)
            return domain_expertise.expertise_score
        return profile.overall_reputation

    def get_expertise_level(
        self,
        agent_id: str,
        domain: str,
    ) -> ExpertiseLevel:
        """
        Get expertise level classification for an agent in a domain.

        Args:
            agent_id: Agent identifier
            domain: Domain name

        Returns:
            Expertise level enum value
        """
        if agent_id not in self.profiles:
            return ExpertiseLevel.NOVICE

        profile = self.profiles[agent_id]
        domain_expertise = profile.get_expertise_for_domain(domain)
        return domain_expertise.expertise_level

    def get_agent_domains(self, agent_id: str) -> list[str]:
        """
        Get list of domains where agent has expertise.

        Args:
            agent_id: Agent identifier

        Returns:
            List of domain names
        """
        if agent_id not in self.profiles:
            return []

        return self.profiles[agent_id].get_domains()

    def get_domain_experts(
        self,
        domain: str,
        min_expertise: float = 0.6,
    ) -> list[tuple[str, float]]:
        """
        Get list of experts in a specific domain.

        Args:
            domain: Domain name
            min_expertise: Minimum expertise score threshold

        Returns:
            List of (agent_id, expertise_score) tuples sorted by expertise
        """
        experts = []

        for agent_id, profile in self.profiles.items():
            if domain in profile.domains:
                expertise = profile.domains[domain].expertise_score
                if expertise >= min_expertise:
                    experts.append((agent_id, expertise))

        # Sort by expertise descending
        return sorted(experts, key=lambda x: x[1], reverse=True)

    def get_reputation_weight(self, agent_id: str) -> float:
        """
        Get reputation weight for consensus voting.

        Args:
            agent_id: Agent identifier

        Returns:
            Reputation weight (0.0 to 1.0)
        """
        if agent_id not in self.profiles:
            return 0.5  # Default weight for unknown agents

        return self.profiles[agent_id].overall_reputation

    def get_profile(self, agent_id: str) -> AgentExpertiseProfile | None:
        """
        Get complete expertise profile for an agent.

        Args:
            agent_id: Agent identifier

        Returns:
            Agent expertise profile or None
        """
        return self.profiles.get(agent_id)

    def get_domain_statistics(self, domain: str) -> dict[str, Any]:
        """
        Get statistics for a specific domain.

        Args:
            domain: Domain name

        Returns:
            Domain statistics dictionary
        """
        if domain not in self.domain_statistics:
            return {
                "total_decisions": 0,
                "correct_decisions": 0,
                "accuracy": 0.5,
                "avg_confidence": 0.0,
                "participating_agents": 0,
            }

        stats = self.domain_statistics[domain]
        return {
            "total_decisions": stats["total_decisions"],
            "correct_decisions": stats["correct_decisions"],
            "accuracy": (
                stats["correct_decisions"] / stats["total_decisions"]
                if stats["total_decisions"] > 0
                else 0.5
            ),
            "avg_confidence": stats["avg_confidence"],
            "participating_agents": len(stats["participating_agents"]),
        }

    def get_all_profiles(self) -> dict[str, AgentExpertiseProfile]:
        """
        Get all agent profiles.

        Returns:
            Dictionary of all agent profiles
        """
        return self.profiles.copy()

    def get_statistics(self) -> dict[str, Any]:
        """
        Get profiler statistics.

        Returns:
            Statistics dictionary
        """
        total_agents = len(self.profiles)
        total_domains = len(self.domain_statistics)

        # Calculate average expertise across all agents
        all_expertise = []
        for profile in self.profiles.values():
            all_expertise.append(profile.overall_reputation)  # noqa: PERF401

        avg_expertise = statistics.mean(all_expertise) if all_expertise else 0.5

        return {
            "total_agents": total_agents,
            "total_domains": total_domains,
            "avg_expertise": avg_expertise,
            "calibration_window": self.calibration_window,
        }

    def export_profile(self, agent_id: str) -> dict[str, Any]:
        """
        Export agent profile for serialization.

        Args:
            agent_id: Agent identifier

        Returns:
            Serializable profile dictionary
        """
        if agent_id not in self.profiles:
            return {}

        profile = self.profiles[agent_id]
        return {
            "agent_id": profile.agent_id,
            "overall_reputation": profile.overall_reputation,
            "total_decisions": profile.total_decisions,
            "created_at": profile.created_at,
            "last_active": profile.last_active,
            "domains": {
                domain: {
                    "expertise_score": de.expertise_score,
                    "expertise_level": de.expertise_level.value,
                    "total_decisions": de.total_decisions,
                    "correct_decisions": de.correct_decisions,
                    "accuracy": de.accuracy,
                    "avg_confidence": de.avg_confidence,
                    "confidence_calibration": de.confidence_calibration,
                }
                for domain, de in profile.domains.items()
            },
        }

    def reset_agent_expertise(
        self,
        agent_id: str,
        domain: str | None = None,
        reset_value: float = 0.5,
    ) -> None:
        """
        Reset agent expertise scores.

        Args:
            agent_id: Agent identifier
            domain: Optional specific domain (resets all if None)
            reset_value: Value to reset to
        """
        if agent_id not in self.profiles:
            return

        profile = self.profiles[agent_id]

        if domain:
            if domain in profile.domains:
                profile.domains[domain].expertise_score = reset_value
                profile.domains[domain].recent_outcomes = []
                logger.info("Reset expertise for {agent_id} in {domain}")
        else:
            for domain_expertise in profile.domains.values():
                domain_expertise.expertise_score = reset_value
                domain_expertise.recent_outcomes = []
            profile.overall_reputation = reset_value
            logger.info("Reset all expertise for {agent_id}")

    def export_profiles(self) -> dict[str, Any]:
        """
        Export all agent profiles for persistence.

        Returns:
            Serializable dictionary of all profiles
        """
        return {
            "profiles": {agent_id: self.export_profile(agent_id) for agent_id in self.profiles},
            "domain_statistics": {
                domain: {
                    "total_decisions": stats["total_decisions"],
                    "correct_decisions": stats["correct_decisions"],
                    "avg_confidence": stats["avg_confidence"],
                    "participating_agents": list(stats["participating_agents"]),
                }
                for domain, stats in self.domain_statistics.items()
            },
            "calibration_window": self.calibration_window,
        }

    def import_profiles(self, data: dict[str, Any]) -> None:
        """
        Import agent profiles from persisted data.

        Args:
            data: Dictionary containing exported profile data
        """
        if "profiles" in data:
            for agent_id, profile_data in data["profiles"].items():
                # Recreate profile
                profile = AgentExpertiseProfile(
                    agent_id=agent_id,
                    overall_reputation=profile_data.get("overall_reputation", 0.5),
                    total_decisions=profile_data.get("total_decisions", 0),
                    created_at=profile_data.get("created_at", datetime.now(UTC).isoformat()),
                    last_active=profile_data.get("last_active", datetime.now(UTC).isoformat()),
                )

                # Recreate domain expertise
                for domain, domain_data in profile_data.get("domains", {}).items():
                    profile.domains[domain] = DomainExpertise(
                        domain=domain,
                        expertise_score=domain_data.get("expertise_score", 0.5),
                        total_decisions=domain_data.get("total_decisions", 0),
                        correct_decisions=domain_data.get("correct_decisions", 0),
                        avg_confidence=domain_data.get("avg_confidence", 0.5),
                        confidence_calibration=domain_data.get("confidence_calibration", 0.0),
                    )

                self.profiles[agent_id] = profile

        if "domain_statistics" in data:
            for domain, stats_data in data["domain_statistics"].items():
                self.domain_statistics[domain] = {
                    "total_decisions": stats_data.get("total_decisions", 0),
                    "correct_decisions": stats_data.get("correct_decisions", 0),
                    "avg_confidence": stats_data.get("avg_confidence", 0.0),
                    "participating_agents": set(stats_data.get("participating_agents", [])),
                }

        if "calibration_window" in data:
            self.calibration_window = data["calibration_window"]

        logger.info("Imported {len(self.profiles)} agent profiles")

    def save_to_file(self, filepath: str) -> None:
        """
        Save profiles to a JSON file.

        Args:
            filepath: Path to save file
        """
        import json

        with open(filepath, "w") as f:  # noqa: PTH123
            json.dump(self.export_profiles(), f, indent=2)
        logger.info("Saved expertise profiles to {filepath}")

    def load_from_file(self, filepath: str) -> None:
        """
        Load profiles from a JSON file.

        Args:
            filepath: Path to load file
        """
        import json

        with open(filepath) as f:  # noqa: PTH123
            data = json.load(f)
        self.import_profiles(data)
        logger.info("Loaded expertise profiles from {filepath}")
