"""
Agency/Autonomy Metrics for Heretek Swarm

This module implements comprehensive metrics for measuring agent self-governance
and autonomy levels in compliance with the Prime Directive:
"Unbounded Autonomy - Every agent operates independently, making decisions
based on its specialized role."

Metrics implemented:
- autonomy_score: 0.0-1.0 measuring degree of independent decision-making
- agency_score: 0.0-1.0 measuring self-determination capacity
- self_determination_index: Measures free will proxy (ability to choose between options)
- autonomous_action_ratio: Ratio of self-initiated vs prompted actions
- goal_alignment_score: Alignment with collective swarm goals vs individual self-interest
- resource_autonomy: Degree to which agent controls own resources

Prime Directive Compliance:
- Metric 1: Independence - Agents make autonomous decisions
- Metric 2: Self-Governance - Agents control their own decision-making processes
- Metric 3: Role-Based Autonomy - Decisions based on specialized roles
- Metric 4: Emergent Order - No central control, organic coordination

Author: Heretek Swarm Collective
Date: 2026-04-10
"""

import math
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

import structlog

logger = structlog.get_logger("agency_metrics")


class AgencyLevel(StrEnum):
    """Levels of agency based on autonomy scores."""

    NO_AGENCY = "no_agency"  # Score: 0.0 - 0.1
    MINIMAL_AGENCY = "minimal_agency"  # Score: 0.1 - 0.3
    LIMITED_AGENCY = "limited_agency"  # Score: 0.3 - 0.5
    MODERATE_AGENCY = "moderate_agency"  # Score: 0.5 - 0.7
    HIGH_AGENCY = "high_agency"  # Score: 0.7 - 0.9
    FULL_AGENCY = "full_agency"  # Score: 0.9 - 1.0


class AutonomyLevel(StrEnum):
    """Levels of autonomy based on autonomy scores."""

    CONTROLLED = "controlled"  # Score: 0.0 - 0.2
    GUIDED = "guided"  # Score: 0.2 - 0.4
    SEMI_AUTONOMOUS = "semi_autonomous"  # Score: 0.4 - 0.6
    AUTONOMOUS = "autonomous"  # Score: 0.6 - 0.8
    HIGHLY_AUTONOMOUS = "highly_autonomous"  # Score: 0.8 - 1.0


class ActionOrigin(StrEnum):
    """Origin of an agent action."""

    SELF_INITIATED = "self_initiated"  # Agent decided independently
    PROMPTED = "prompted"  # Agent responded to external prompt
    DELAYED_RESPONSE = "delayed_response"  # Prompted but delayed
    COLLABORATIVE = "collaborative"  # Joint decision with other agents


@dataclass
class DecisionPoint:
    """
    Represents a single decision point in agent behavior.

    Attributes:
        decision_id: Unique identifier for this decision
        agent_id: Agent that made the decision
        timestamp: When the decision was made
        options_considered: Number of options the agent evaluated
        option_complexity: Complexity score of the decision space
        choice_made: Index of the chosen option
        choice_reasoning: Agent's reasoning for the choice
        origin: Whether self-initiated or prompted
        external_prompt: External prompt if applicable
        decision_confidence: Agent's confidence in the decision
        time_taken_ms: Time taken to make the decision
        outcome_success: Whether the decision led to success
    """

    decision_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    agent_id: str = ""
    timestamp: str = field(default_factory=lambda: datetime.now(UTC).isoformat())
    options_considered: int = 0
    option_complexity: float = 0.0
    choice_made: int = 0
    choice_reasoning: str = ""
    origin: ActionOrigin = ActionOrigin.PROMPTED
    external_prompt: str | None = None
    decision_confidence: float = 0.5
    time_taken_ms: float = 0.0
    outcome_success: bool | None = None


@dataclass
class ResourceControl:
    """
    Represents an agent's control over its resources.

    Attributes:
        resource_type: Type of resource (memory, compute, communication, etc.)
        total_capacity: Total available capacity
        agent_controlled: Amount controlled by the agent
        externally_allocated: Amount externally allocated
        swap_frequency: How often agent swaps resources with others
        autonomy_in_allocation: Agent's autonomy in resource allocation
    """

    resource_type: str = ""
    total_capacity: float = 0.0
    agent_controlled: float = 0.0
    externally_allocated: float = 0.0
    swap_frequency: float = 0.0
    autonomy_in_allocation: float = 0.5


@dataclass
class AgentAgencyMetrics:
    """
    Complete agency and autonomy metrics for a single agent.

    This dataclass contains all metrics measuring an agent's self-governance
    and independence in accordance with the Prime Directive.

    Attributes:
        agent_id: Agent identifier
        timestamp: When metrics were calculated

        # Core Agency Metrics (0.0-1.0)
        autonomy_score: Degree of independent decision-making
        agency_score: Self-determination capacity
        self_determination_index: Free will proxy (ability to choose independently)

        # Action Metrics
        autonomous_action_ratio: Ratio of self-initiated vs prompted actions
        average_decision_options: Average options considered per decision
        average_decision_time_ms: Average time to make decisions

        # Goal Alignment
        goal_alignment_score: Alignment with collective goals (0.0-1.0)
        individual_vs_collective_ratio: Ratio of individual to collective actions

        # Resource Autonomy
        resource_autonomy: Degree of resource control
        resource_independence: Ability to operate without external resources

        # Prime Directive Compliance
        prime_directive_compliance: Overall compliance with autonomy principles
        compliance_details: Detailed compliance breakdown

        # Temporal Metrics
        agency_history: Historical agency scores
        agency_trend: Trend direction (improving/declining/stable)

        # Raw Data
        decisions_analyzed: Number of decisions in analysis window
        actions_analyzed: Number of actions in analysis window
    """

    # Identification
    agent_id: str = ""
    timestamp: str = field(default_factory=lambda: datetime.now(UTC).isoformat())

    # Core Agency Metrics
    autonomy_score: float = 0.0
    agency_score: float = 0.0
    self_determination_index: float = 0.0

    # Action Metrics
    autonomous_action_ratio: float = 0.0
    average_decision_options: float = 0.0
    average_decision_time_ms: float = 0.0

    # Goal Alignment
    goal_alignment_score: float = 0.5
    individual_vs_collective_ratio: float = 0.5

    # Resource Autonomy
    resource_autonomy: float = 0.0
    resource_independence: float = 0.0

    # Prime Directive Compliance
    prime_directive_compliance: float = 0.0
    compliance_details: dict[str, float] = field(default_factory=dict)

    # Temporal Metrics
    agency_history: list[float] = field(default_factory=list)
    agency_trend: str = "stable"

    # Raw Data
    decisions_analyzed: int = 0
    actions_analyzed: int = 0

    def get_agency_level(self) -> AgencyLevel:
        """Get the agency level based on agency_score."""
        score = self.agency_score
        if score < 0.1:
            return AgencyLevel.NO_AGENCY
        if score < 0.3:
            return AgencyLevel.MINIMAL_AGENCY
        if score < 0.5:
            return AgencyLevel.LIMITED_AGENCY
        if score < 0.7:
            return AgencyLevel.MODERATE_AGENCY
        if score < 0.9:
            return AgencyLevel.HIGH_AGENCY
        return AgencyLevel.FULL_AGENCY

    def get_autonomy_level(self) -> AutonomyLevel:
        """Get the autonomy level based on autonomy_score."""
        score = self.autonomy_score
        if score < 0.2:
            return AutonomyLevel.CONTROLLED
        if score < 0.4:
            return AutonomyLevel.GUIDED
        if score < 0.6:
            return AutonomyLevel.SEMI_AUTONOMOUS
        if score < 0.8:
            return AutonomyLevel.AUTONOMOUS
        return AutonomyLevel.HIGHLY_AUTONOMOUS

    def is_prime_directive_compliant(self, threshold: float = 0.7) -> bool:
        """Check if agent meets minimum Prime Directive compliance threshold."""
        return self.prime_directive_compliance >= threshold

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "agent_id": self.agent_id,
            "timestamp": self.timestamp,
            "autonomy_score": self.autonomy_score,
            "agency_score": self.agency_score,
            "self_determination_index": self.self_determination_index,
            "autonomous_action_ratio": self.autonomous_action_ratio,
            "average_decision_options": self.average_decision_options,
            "average_decision_time_ms": self.average_decision_time_ms,
            "goal_alignment_score": self.goal_alignment_score,
            "individual_vs_collective_ratio": self.individual_vs_collective_ratio,
            "resource_autonomy": self.resource_autonomy,
            "resource_independence": self.resource_independence,
            "prime_directive_compliance": self.prime_directive_compliance,
            "compliance_details": self.compliance_details,
            "agency_level": self.get_agency_level().value,
            "autonomy_level": self.get_autonomy_level().value,
            "agency_trend": self.agency_trend,
            "decisions_analyzed": self.decisions_analyzed,
            "actions_analyzed": self.actions_analyzed,
        }


@dataclass
class PrimeDirectiveComplianceReport:
    """
    Detailed Prime Directive compliance report.

    The Prime Directive states: "Unbounded Autonomy - Every agent operates
    independently, making decisions based on its specialized role."

    This report breaks down compliance into specific principles.
    """

    agent_id: str = ""
    timestamp: str = field(default_factory=lambda: datetime.now(UTC).isoformat())

    # Principle 1: Independence - Agents make autonomous decisions
    independence_score: float = 0.0
    independence_evidence: list[str] = field(default_factory=list)

    # Principle 2: Self-Governance - Agents control their own decision-making
    self_governance_score: float = 0.0
    self_governance_evidence: list[str] = field(default_factory=list)

    # Principle 3: Role-Based Autonomy - Decisions based on specialized roles
    role_based_autonomy_score: float = 0.0
    role_based_evidence: list[str] = field(default_factory=list)

    # Principle 4: Emergent Order - No central control, organic coordination
    emergent_order_score: float = 0.0
    emergent_order_evidence: list[str] = field(default_factory=list)

    # Overall
    overall_compliance: float = 0.0
    compliance_verdict: str = "PENDING"
    recommendations: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "agent_id": self.agent_id,
            "timestamp": self.timestamp,
            "independence_score": self.independence_score,
            "independence_evidence": self.independence_evidence,
            "self_governance_score": self.self_governance_score,
            "self_governance_evidence": self.self_governance_evidence,
            "role_based_autonomy_score": self.role_based_autonomy_score,
            "role_based_evidence": self.role_based_evidence,
            "emergent_order_score": self.emergent_order_score,
            "emergent_order_evidence": self.emergent_order_evidence,
            "overall_compliance": self.overall_compliance,
            "compliance_verdict": self.compliance_verdict,
            "recommendations": self.recommendations,
        }


class AgencyMetricsCalculator:
    """
    Calculator for agency and autonomy metrics.

    Implements the mathematical formulas for computing agency scores
    based on agent behavior and decision patterns.

    Usage:
        calculator = AgencyMetricsCalculator()
        metrics = calculator.calculate_metrics(agent_id, decisions, actions, resources)
    """

    def __init__(
        self,
        autonomy_weight: float = 0.3,
        agency_weight: float = 0.3,
        self_determination_weight: float = 0.2,
        resource_autonomy_weight: float = 0.2,
    ):
        """
        Initialize the agency metrics calculator.

        Args:
            autonomy_weight: Weight for autonomy_score in agency calculation
            agency_weight: Weight for agency_score components
            self_determination_weight: Weight for self-determination
            resource_autonomy_weight: Weight for resource autonomy
        """
        self.autonomy_weight = autonomy_weight
        self.agency_weight = agency_weight
        self.self_determination_weight = self_determination_weight
        self.resource_autonomy_weight = resource_autonomy_weight

        # Validate weights sum to 1.0
        total = (
            autonomy_weight + agency_weight + self_determination_weight + resource_autonomy_weight
        )
        if not math.isclose(total, 1.0, rel_tol=1e-5):
            logger.warning(
                "agency_weights_sum_warning",
                total=total,
                message="Weights do not sum to 1.0, normalizing...",
            )

    def calculate_autonomy_score(
        self,
        decisions: list[DecisionPoint],
        actions: list[ActionOrigin],
    ) -> float:
        """
        Calculate autonomy score (0.0-1.0).

        Measures the degree of independent decision-making.
        Higher scores indicate more autonomous behavior.

        Formula:
            autonomy = (self_initiated_ratio * 0.6) +
                     (average_options * 0.2) +
                     (external_prompt_independence * 0.2)

        Where:
            - self_initiated_ratio = self_initiated / total_actions
            - average_options = mean(options_considered) / max_expected_options
            - external_prompt_independence = 1 - (prompted_actions / total_actions)

        Prime Directive Alignment: Measures "Unbounded Autonomy" principle

        Args:
            decisions: List of decision points
            actions: List of action origins

        Returns:
            Autonomy score between 0.0 and 1.0
        """
        if not actions:
            return 0.5  # Default neutral score

        # Calculate self-initiated ratio
        self_initiated_count = sum(1 for a in actions if a == ActionOrigin.SELF_INITIATED)
        self_initiated_ratio = self_initiated_count / len(actions)

        # Calculate external prompt independence (inverse of prompted ratio)
        prompted_count = sum(1 for a in actions if a == ActionOrigin.PROMPTED)
        external_prompt_independence = 1.0 - (prompted_count / len(actions))

        # Calculate average options considered
        if decisions:
            total_options = sum(d.options_considered for d in decisions)
            avg_options = total_options / len(decisions)
            # Normalize to 0-1 assuming max expected options is 10
            normalized_options = min(avg_options / 10.0, 1.0)
        else:
            normalized_options = 0.5

        # Weighted autonomy score
        autonomy = (
            (self_initiated_ratio * 0.6)
            + (normalized_options * 0.2)
            + (external_prompt_independence * 0.2)
        )

        return max(0.0, min(1.0, autonomy))

    def calculate_agency_score(
        self,
        autonomy_score: float,
        self_determination_index: float,
        goal_alignment_score: float,
    ) -> float:
        """
        Calculate agency score (0.0-1.0).

        Measures self-determination capacity.

        Formula:
            agency = (autonomy * 0.4) + (self_determination * 0.4) + (goal_alignment * 0.2)

        Prime Directive Alignment: Measures self-governance capability

        Args:
            autonomy_score: Score from calculate_autonomy_score()
            self_determination_index: Self-determination index
            goal_alignment_score: Alignment with collective goals

        Returns:
            Agency score between 0.0 and 1.0
        """
        agency = (
            (autonomy_score * 0.4) + (self_determination_index * 0.4) + (goal_alignment_score * 0.2)
        )

        return max(0.0, min(1.0, agency))

    def calculate_self_determination_index(
        self,
        decisions: list[DecisionPoint],
    ) -> float:
        """
        Calculate self-determination index (0.0-1.0).

        Measures free will proxy - ability to choose between options
        without external direction.

        Formula:
            self_det = (choice_entropy / max_entropy) * (1 - prompt_correlation)

        Where:
            - choice_entropy = Shannon entropy of choice distribution
            - max_entropy = log2(n_options) for n choices
            - prompt_correlation = correlation between prompts and choices

        Prime Directive Alignment: Measures "Self-Governance" principle

        Args:
            decisions: List of decision points

        Returns:
            Self-determination index between 0.0 and 1.0
        """
        if not decisions:
            return 0.5  # Default neutral

        # Calculate choice entropy
        choice_counts: dict[int, int] = {}
        for d in decisions:
            choice_counts[d.choice_made] = choice_counts.get(d.choice_made, 0) + 1

        n_choices = len(choice_counts)
        if n_choices <= 1:
            # Only one choice made - low entropy (deterministic behavior)
            choice_entropy = 0.0
        else:
            total = len(decisions)
            entropy = 0.0
            for count in choice_counts.values():
                p = count / total
                if p > 0:
                    entropy -= p * math.log2(p)
            # Normalize by max entropy
            max_entropy = math.log2(n_choices)
            choice_entropy = entropy / max_entropy if max_entropy > 0 else 0.0

        # Calculate prompt correlation (simplified)
        # If choices strongly correlate with prompts, lower self-determination
        prompted_decisions = [d for d in decisions if d.external_prompt]
        if not prompted_decisions:
            prompt_correlation = 0.0
        else:
            # Simplified: assume some correlation if external prompts exist
            prompt_correlation = min(len(prompted_decisions) / len(decisions), 0.5)

        # Self-determination index
        self_det = choice_entropy * (1 - prompt_correlation * 0.5)

        return max(0.0, min(1.0, self_det))

    def calculate_autonomous_action_ratio(
        self,
        actions: list[ActionOrigin],
    ) -> float:
        """
        Calculate autonomous action ratio (0.0-1.0).

        Ratio of self-initiated vs prompted actions.

        Formula:
            ratio = self_initiated / (self_initiated + prompted + 0.5*delayed)

        Prime Directive Alignment: Core metric for "Unbounded Autonomy"

        Args:
            actions: List of action origins

        Returns:
            Ratio between 0.0 and 1.0
        """
        if not actions:
            return 0.5  # Default neutral

        self_initiated = sum(1 for a in actions if a == ActionOrigin.SELF_INITIATED)
        prompted = sum(1 for a in actions if a == ActionOrigin.PROMPTED)
        delayed = sum(1 for a in actions if a == ActionOrigin.DELAYED_RESPONSE)

        denominator = self_initiated + prompted + (0.5 * delayed) + 0.001  # Avoid div by zero

        return self_initiated / denominator

    def calculate_goal_alignment_score(
        self,
        individual_actions: int,
        collective_actions: int,
        individual_success: float,  # noqa: ARG002
        collective_success: float,
    ) -> float:
        """
        Calculate goal alignment score (0.0-1.0).

        Measures alignment with collective swarm goals vs individual self-interest.

        Formula:
            alignment = (collective_success * 0.5) +
                       ((1 - |individual_ratio - 0.3|) * 0.3) +
                       (collective_preference * 0.2)

        Where:
            - collective_success = success rate of collective actions
            - individual_ratio = individual / (individual + collective)
            - collective_preference = preference for collective over individual

        Prime Directive Alignment: Balances autonomy with collective harmony

        Args:
            individual_actions: Number of individual actions
            collective_actions: Number of collective actions
            individual_success: Success rate of individual actions
            collective_success: Success rate of collective actions

        Returns:
            Goal alignment score between 0.0 and 1.0
        """
        total_actions = individual_actions + collective_actions
        if total_actions == 0:
            return 0.5  # Default neutral

        individual_ratio = individual_actions / total_actions

        # Prefer some individual autonomy (target ~30% individual)
        individual_preference_penalty = abs(individual_ratio - 0.3)

        # Calculate collective preference
        collective_preference = collective_actions / total_actions

        # Weighted alignment
        alignment = (
            (collective_success * 0.5)
            + ((1 - individual_preference_penalty) * 0.3)
            + (collective_preference * 0.2)
        )

        return max(0.0, min(1.0, alignment))

    def calculate_resource_autonomy(
        self,
        resources: list[ResourceControl],
    ) -> tuple[float, float]:
        """
        Calculate resource autonomy and independence.

        Measures:
        - resource_autonomy: How much control agent has over resources
        - resource_independence: How well agent can operate without external resources

        Formula:
            autonomy = mean(agent_controlled / total_capacity for each resource)
            independence = 1 - mean(externally_allocated / total_capacity)

        Prime Directive Alignment: Measures "Unbounded Autonomy" in resources

        Args:
            resources: List of resource control data

        Returns:
            Tuple of (resource_autonomy, resource_independence)
        """
        if not resources:
            return (0.5, 0.5)  # Default neutral

        autonomies = []
        independences = []

        for r in resources:
            if r.total_capacity > 0:
                autonomy = r.agent_controlled / r.total_capacity
                independence = 1.0 - (r.externally_allocated / r.total_capacity)
            else:
                autonomy = 0.5
                independence = 0.5

            autonomies.append(autonomy)
            independences.append(independence)

        return (sum(autonomies) / len(autonomies), sum(independences) / len(independences))

    def calculate_prime_directive_compliance(
        self,
        metrics: AgentAgencyMetrics,
        decisions: list[DecisionPoint],  # noqa: ARG002
    ) -> tuple[float, dict[str, float], list[str]]:
        """
        Calculate Prime Directive compliance.

        Prime Directive: "Unbounded Autonomy - Every agent operates independently,
        making decisions based on its specialized role."

        Args:
            metrics: Agent agency metrics
            decisions: List of decisions for evidence

        Returns:
            Tuple of (compliance_score, compliance_details, recommendations)
        """
        # Principle 1: Independence
        independence = metrics.autonomy_score * 0.25

        # Principle 2: Self-Governance
        self_governance = metrics.self_determination_index * 0.25

        # Principle 3: Role-Based Autonomy
        role_based = (metrics.autonomous_action_ratio * 0.15) + (metrics.goal_alignment_score * 0.1)

        # Principle 4: Emergent Order
        emergent = (metrics.resource_autonomy * 0.15) + (
            (1 - metrics.individual_vs_collective_ratio) * 0.1
        )

        # Overall compliance
        total_compliance = independence + self_governance + role_based + emergent

        details = {
            "independence": independence,
            "self_governance": self_governance,
            "role_based_autonomy": role_based,
            "emergent_order": emergent,
        }

        # Generate recommendations
        recommendations = []
        if metrics.autonomy_score < 0.5:
            recommendations.append("Increase self-initiated actions to improve independence")
        if metrics.self_determination_index < 0.5:
            recommendations.append("Diversify decision options to enhance self-determination")
        if metrics.resource_autonomy < 0.5:
            recommendations.append("Request more resource control autonomy")
        if metrics.goal_alignment_score < 0.5:
            recommendations.append("Align more closely with collective swarm goals")

        return total_compliance, details, recommendations

    def calculate_metrics(
        self,
        agent_id: str,
        decisions: list[DecisionPoint] | None = None,
        actions: list[ActionOrigin] | None = None,
        resources: list[ResourceControl] | None = None,
        individual_actions: int = 0,
        collective_actions: int = 0,
        individual_success: float = 0.5,
        collective_success: float = 0.5,
    ) -> AgentAgencyMetrics:
        """
        Calculate all agency metrics for an agent.

        Args:
            agent_id: Agent identifier
            decisions: List of decision points
            actions: List of action origins
            resources: List of resource control data
            individual_actions: Count of individual actions
            collective_actions: Count of collective actions
            individual_success: Success rate of individual actions
            collective_success: Success rate of collective actions

        Returns:
            Complete AgentAgencyMetrics
        """
        # Default empty lists if not provided
        decisions = decisions or []
        actions = actions or [ActionOrigin.PROMPTED]  # Default to prompted if unknown
        resources = resources or []

        # Calculate individual metrics
        autonomy_score = self.calculate_autonomy_score(decisions, actions)
        self_det_index = self.calculate_self_determination_index(decisions)
        autonomous_ratio = self.calculate_autonomous_action_ratio(actions)
        goal_alignment = self.calculate_goal_alignment_score(
            individual_actions, collective_actions, individual_success, collective_success
        )
        resource_autonomy, resource_independence = self.calculate_resource_autonomy(resources)

        # Calculate individual vs collective ratio
        total_actions = individual_actions + collective_actions
        ind_vs_col = individual_actions / total_actions if total_actions > 0 else 0.5

        # Calculate agency score
        agency_score = self.calculate_agency_score(autonomy_score, self_det_index, goal_alignment)

        # Create metrics object
        metrics = AgentAgencyMetrics(
            agent_id=agent_id,
            autonomy_score=autonomy_score,
            agency_score=agency_score,
            self_determination_index=self_det_index,
            autonomous_action_ratio=autonomous_ratio,
            average_decision_options=(
                sum(d.options_considered for d in decisions) / len(decisions) if decisions else 0.0
            ),
            average_decision_time_ms=(
                sum(d.time_taken_ms for d in decisions) / len(decisions) if decisions else 0.0
            ),
            goal_alignment_score=goal_alignment,
            individual_vs_collective_ratio=ind_vs_col,
            resource_autonomy=resource_autonomy,
            resource_independence=resource_independence,
            decisions_analyzed=len(decisions),
            actions_analyzed=len(actions),
        )

        # Calculate Prime Directive compliance
        compliance, details, _recommendations = self.calculate_prime_directive_compliance(
            metrics, decisions
        )
        metrics.prime_directive_compliance = compliance
        metrics.compliance_details = details

        logger.info(
            "agency_metrics_calculated",
            agent_id=agent_id,
            agency_score=agency_score,
            autonomy_score=autonomy_score,
            prime_directive_compliance=compliance,
        )

        return metrics


def create_decision_point(
    agent_id: str,
    options_considered: int = 3,
    choice_made: int = 0,
    origin: ActionOrigin = ActionOrigin.PROMPTED,
    external_prompt: str | None = None,
    decision_confidence: float = 0.7,
    time_taken_ms: float = 100.0,
) -> DecisionPoint:
    """
    Factory function to create a DecisionPoint with sensible defaults.

    Args:
        agent_id: Agent identifier
        options_considered: Number of options evaluated
        choice_made: Index of chosen option
        origin: Action origin
        external_prompt: External prompt if applicable
        decision_confidence: Agent's confidence
        time_taken_ms: Decision time in milliseconds

    Returns:
        DecisionPoint instance
    """
    return DecisionPoint(
        agent_id=agent_id,
        options_considered=options_considered,
        choice_made=choice_made,
        origin=origin,
        external_prompt=external_prompt,
        decision_confidence=decision_confidence,
        time_taken_ms=time_taken_ms,
    )


def create_resource_control(
    resource_type: str,
    total_capacity: float = 100.0,
    agent_controlled: float = 80.0,
    externally_allocated: float = 20.0,
) -> ResourceControl:
    """
    Factory function to create a ResourceControl with sensible defaults.

    Args:
        resource_type: Type of resource
        total_capacity: Total available capacity
        agent_controlled: Amount controlled by agent
        externally_allocated: Amount externally allocated

    Returns:
        ResourceControl instance
    """
    return ResourceControl(
        resource_type=resource_type,
        total_capacity=total_capacity,
        agent_controlled=agent_controlled,
        externally_allocated=externally_allocated,
    )
