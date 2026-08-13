"""
Knowledge Transformation Module - Cross-Agent Learning

Implements knowledge transformation for agent-specific contexts.
This module transforms raw patterns into formats suitable for different
agent types, validates transformed knowledge, and prepares knowledge
for distribution across the swarm.

Features:
- Transform raw patterns into agent-specific contexts
- Format knowledge for different agent types
- Validate transformed knowledge before distribution
- Knowledge adaptation based on agent capabilities
- Context-aware knowledge packaging

Zero-Trust Principles:
- All transformations validated
- Source attribution preserved
- Type-specific validation rules
- Audit logging for all transformations
"""

import asyncio
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from typing import TYPE_CHECKING, Any

import structlog

from .learning import ExtractedPattern, PatternType

if TYPE_CHECKING:
    from collections.abc import Callable

logger = structlog.get_logger(__name__)


class AgentType(StrEnum):
    """Types of agents in the swarm."""

    LEADERSHIP = "leadership"  # steward, alpha, arbiter
    ANALYSIS = "analysis"  # alpha, beta, charlie, examiner
    SUPPORT = "support"  # historian, metis, empath, nexus
    EXPLORATION = "exploration"  # explorer, perceiver
    DEVELOPMENT = "development"  # coder, dreamer, catalyst
    SAFETY = "safety"  # sentinel, sentinel-prime
    COORDINATION = "coordination"  # coordinator, chronos


class TransformationType(StrEnum):
    """Types of knowledge transformations."""

    ABSTRACT = "abstract"  # High-level summary
    DETAILED = "detailed"  # Full pattern details
    ACTIONABLE = "actionable"  # Action-oriented format
    CONTEXTUAL = "contextual"  # Context-enriched format
    CONDENSED = "condensed"  # Compressed for efficiency
    EXPANDED = "expanded"  # Elaborated with examples


@dataclass
class TransformedKnowledge:
    """Represents transformed knowledge for a specific agent type."""

    transformation_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    source_pattern_id: str = ""
    target_agent_type: AgentType = AgentType.SUPPORT
    transformation_type: TransformationType = TransformationType.ABSTRACT
    knowledge_content: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)
    validation_status: str = "pending"
    validation_errors: list[str] = field(default_factory=list)
    created_at: str = field(default_factory=lambda: datetime.now(UTC).isoformat())
    expires_at: str | None = None
    priority: float = 0.5
    applicability_score: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "transformation_id": self.transformation_id,
            "source_pattern_id": self.source_pattern_id,
            "target_agent_type": self.target_agent_type.value,
            "transformation_type": self.transformation_type.value,
            "knowledge_content": self.knowledge_content,
            "metadata": self.metadata,
            "validation_status": self.validation_status,
            "validation_errors": self.validation_errors,
            "created_at": self.created_at,
            "expires_at": self.expires_at,
            "priority": self.priority,
            "applicability_score": self.applicability_score,
        }


@dataclass
class TransformationResult:
    """Result of a knowledge transformation operation."""

    success: bool
    transformed_knowledge: TransformedKnowledge | None = None
    error_message: str | None = None
    transformation_time_ms: float = 0.0
    validation_passed: bool = False
    warnings: list[str] = field(default_factory=list)


@dataclass
class AgentCapabilityProfile:
    """Profile of an agent's capabilities for knowledge adaptation."""

    agent_type: AgentType
    capabilities: list[str] = field(default_factory=list)
    knowledge_preferences: dict[str, Any] = field(default_factory=dict)
    max_knowledge_size: int = 10000  # Maximum content size
    preferred_formats: list[str] = field(default_factory=list)
    excluded_topics: list[str] = field(default_factory=list)


class KnowledgeTransformer:
    """
    Transforms raw patterns into agent-specific knowledge formats.

    This class handles the transformation of extracted patterns into
    formats suitable for different agent types, with validation and
    adaptation based on agent capabilities.

    Attributes:
        agent_profiles: Dictionary of agent capability profiles
        transformation_rules: Rules for each transformation type
        validation_rules: Validation rules for transformed knowledge
    """

    def __init__(self):
        """Initialize knowledge transformer."""
        self._agent_profiles: dict[str, AgentCapabilityProfile] = {}
        self._transformation_rules: dict[TransformationType, Callable] = {}
        self._validation_rules: dict[AgentType, list[Callable]] = {}
        self._transformed_cache: dict[str, TransformedKnowledge] = {}

        self._register_default_rules()

        logger.info("knowledge_transformer_initialized")

    def _register_default_rules(self) -> None:
        """Register default transformation and validation rules."""
        # Transformation rules
        self._transformation_rules = {
            TransformationType.ABSTRACT: self._transform_abstract,
            TransformationType.DETAILED: self._transform_detailed,
            TransformationType.ACTIONABLE: self._transform_actionable,
            TransformationType.CONTEXTUAL: self._transform_contextual,
            TransformationType.CONDENSED: self._transform_condensed,
            TransformationType.EXPANDED: self._transform_expanded,
        }

        # Validation rules by agent type
        self._validation_rules = {
            AgentType.LEADERSHIP: [
                self._validate_leadership_knowledge,
            ],
            AgentType.ANALYSIS: [
                self._validate_analysis_knowledge,
            ],
            AgentType.SUPPORT: [
                self._validate_support_knowledge,
            ],
            AgentType.EXPLORATION: [
                self._validate_exploration_knowledge,
            ],
            AgentType.DEVELOPMENT: [
                self._validate_development_knowledge,
            ],
            AgentType.SAFETY: [
                self._validate_safety_knowledge,
            ],
            AgentType.COORDINATION: [
                self._validate_coordination_knowledge,
            ],
        }

    def register_agent_profile(
        self,
        agent_id: str,
        profile: AgentCapabilityProfile,
    ) -> None:
        """
        Register a capability profile for an agent.

        Args:
            agent_id: Unique agent identifier
            profile: AgentCapabilityProfile instance
        """
        self._agent_profiles[agent_id] = profile
        logger.debug(
            "agent_profile_registered",
            agent_id=agent_id,
            agent_type=profile.agent_type.value,
        )

    def get_agent_profile(self, agent_id: str) -> AgentCapabilityProfile | None:
        """
        Get capability profile for an agent.

        Args:
            agent_id: Agent identifier

        Returns:
            AgentCapabilityProfile or None if not found
        """
        return self._agent_profiles.get(agent_id)

    async def transform_knowledge(
        self,
        pattern: ExtractedPattern,
        target_agent_type: AgentType,
        transformation_type: TransformationType = TransformationType.ABSTRACT,
        agent_id: str | None = None,
    ) -> TransformationResult:
        """
        Transform a pattern into agent-specific knowledge.

        Args:
            pattern: Source pattern to transform
            target_agent_type: Target agent type for transformation
            transformation_type: Type of transformation to apply
            agent_id: Optional specific agent ID for customization

        Returns:
            TransformationResult with transformed knowledge
        """
        start_time = datetime.now(UTC)
        warnings = []

        try:
            # Get transformation rule
            transform_func = self._transformation_rules.get(transformation_type)
            if not transform_func:
                return TransformationResult(
                    success=False,
                    error_message=f"Unknown transformation type: {transformation_type}",
                )

            # Apply transformation
            knowledge_content = transform_func(pattern, target_agent_type)

            # Calculate applicability score
            applicability = self._calculate_applicability(
                pattern,
                target_agent_type,
                agent_id,
            )

            # Get agent-specific customization
            if agent_id and agent_id in self._agent_profiles:
                profile = self._agent_profiles[agent_id]
                knowledge_content = self._customize_for_agent(
                    knowledge_content,
                    profile,
                    warnings,
                )

            # Create transformed knowledge
            transformed = TransformedKnowledge(
                source_pattern_id=pattern.metadata.pattern_id,
                target_agent_type=target_agent_type,
                transformation_type=transformation_type,
                knowledge_content=knowledge_content,
                metadata={
                    "original_pattern_type": pattern.metadata.pattern_type.value,
                    "original_confidence": pattern.metadata.confidence,
                    "agents_involved": pattern.metadata.agents_involved,
                    "topics": pattern.metadata.topics,
                },
                priority=self._calculate_priority(pattern, target_agent_type),
                applicability_score=applicability,
            )

            # Validate transformed knowledge
            validation_passed, errors = await self._validate_transformation(
                transformed,
                target_agent_type,
            )
            transformed.validation_status = "valid" if validation_passed else "invalid"
            transformed.validation_errors = errors

            # Calculate transformation time
            transformation_time = (datetime.now(UTC) - start_time).total_seconds() * 1000

            # Cache result
            self._transformed_cache[transformed.transformation_id] = transformed

            return TransformationResult(
                success=True,
                transformed_knowledge=transformed,
                transformation_time_ms=transformation_time,
                validation_passed=validation_passed,
                warnings=warnings,
            )

        except Exception as e:
            transformation_time = (datetime.now(UTC) - start_time).total_seconds() * 1000

            logger.error(
                "transformation_error",
                error=str(e),
                pattern_id=pattern.metadata.pattern_id,
                target_agent_type=target_agent_type.value,
            )

            return TransformationResult(
                success=False,
                error_message=str(e),
                transformation_time_ms=transformation_time,
            )

    async def transform_for_multiple_agents(
        self,
        pattern: ExtractedPattern,
        agent_types: list[AgentType],
        transformation_type: TransformationType = TransformationType.ABSTRACT,
    ) -> list[TransformationResult]:
        """
        Transform a pattern for multiple agent types.

        Args:
            pattern: Source pattern
            agent_types: List of target agent types
            transformation_type: Type of transformation

        Returns:
            List of TransformationResult for each agent type
        """
        tasks = [
            self.transform_knowledge(
                pattern=pattern,
                target_agent_type=agent_type,
                transformation_type=transformation_type,
            )
            for agent_type in agent_types
        ]

        results = await asyncio.gather(*tasks, return_exceptions=True)

        transformed_results = []
        for _i, result in enumerate(results):
            if isinstance(result, Exception):
                transformed_results.append(
                    TransformationResult(
                        success=False,
                        error_message=str(result),
                    )
                )
            else:
                transformed_results.append(result)

        return transformed_results

    def _transform_abstract(
        self,
        pattern: ExtractedPattern,
        target_agent_type: AgentType,
    ) -> dict[str, Any]:
        """Transform pattern into abstract/high-level summary."""
        return {
            "summary": f"Pattern: {pattern.metadata.pattern_type.value} interaction",
            "key_insight": self._extract_key_insight(pattern),
            "relevance": f"Applicable to {target_agent_type.value} agents",
            "confidence": pattern.metadata.confidence,
            "pattern_id": pattern.metadata.pattern_id,
        }

    def _transform_detailed(
        self,
        pattern: ExtractedPattern,
        target_agent_type: AgentType,
    ) -> dict[str, Any]:
        """Transform pattern into detailed format with full information."""
        return {
            "pattern_metadata": pattern.to_dict(),
            "full_context": pattern.context,
            "outcomes": pattern.outcomes,
            "preconditions": pattern.preconditions,
            "postconditions": pattern.postconditions,
            "applicability_conditions": pattern.applicability_conditions,
            "agent_type_relevance": self._get_agent_relevance(
                pattern,
                target_agent_type,
            ),
        }

    def _transform_actionable(
        self,
        pattern: ExtractedPattern,
        target_agent_type: AgentType,
    ) -> dict[str, Any]:
        """Transform pattern into action-oriented format."""
        actions = []

        # Extract actionable items from pattern
        if pattern.metadata.pattern_type == PatternType.SUCCESS:
            actions.append("Replicate this successful interaction pattern")
            actions.extend(pattern.applicability_conditions)
        elif pattern.metadata.pattern_type == PatternType.FAILURE:
            actions.append("Avoid conditions that led to this failure")
            actions.extend([f"Check: {pre}" for pre in pattern.preconditions])
        elif pattern.metadata.pattern_type == PatternType.HANDOFF:
            actions.append("Consider this handoff path for similar tasks")
        elif pattern.metadata.pattern_type == PatternType.OPTIMIZATION:
            actions.append("Apply this optimization when conditions match")

        return {
            "recommended_actions": actions,
            "priority": self._calculate_priority(pattern, target_agent_type),
            "expected_outcome": self._predict_outcome(pattern, target_agent_type),
            "pattern_id": pattern.metadata.pattern_id,
        }

    def _transform_contextual(
        self,
        pattern: ExtractedPattern,
        target_agent_type: AgentType,
    ) -> dict[str, Any]:
        """Transform pattern with enriched context."""
        return {
            "pattern_summary": pattern.to_dict(),
            "historical_context": {
                "first_observed": pattern.metadata.first_observed,
                "last_observed": pattern.metadata.last_observed,
                "occurrence_count": pattern.metadata.support_count,
            },
            "social_context": {
                "agents_involved": pattern.metadata.agents_involved,
                "agent_types": self._infer_agent_types(pattern.metadata.agents_involved),
            },
            "task_context": {
                "topics": pattern.metadata.topics,
                "tags": pattern.metadata.tags,
            },
            "relevance_to_agent": self._get_agent_relevance(pattern, target_agent_type),
        }

    def _transform_condensed(
        self,
        pattern: ExtractedPattern,
        target_agent_type: AgentType,  # noqa: ARG002
    ) -> dict[str, Any]:
        """Transform pattern into condensed/compressed format."""
        return {
            "id": pattern.metadata.pattern_id,
            "type": pattern.metadata.pattern_type.value,
            "conf": round(pattern.metadata.confidence, 2),
            "count": pattern.metadata.support_count,
            "agents": len(pattern.metadata.agents_involved),
            "topics": len(pattern.metadata.topics),
        }

    def _transform_expanded(
        self,
        pattern: ExtractedPattern,
        target_agent_type: AgentType,
    ) -> dict[str, Any]:
        """Transform pattern with expanded examples and elaborations."""
        return {
            "pattern_details": pattern.to_dict(),
            "elaboration": {
                "what": f"This {pattern.metadata.pattern_type.value} pattern represents...",
                "why": "This pattern is important because...",
                "how": "To apply this pattern...",
                "when": "Use this pattern when...",
            },
            "examples": self._generate_examples(pattern, target_agent_type),
            "counter_examples": self._generate_counter_examples(pattern),
            "related_patterns": [],  # Would be populated from pattern library
        }

    def _customize_for_agent(
        self,
        knowledge: dict[str, Any],
        profile: AgentCapabilityProfile,
        warnings: list[str],
    ) -> dict[str, Any]:
        """
        Customize knowledge for a specific agent's profile.

        Args:
            knowledge: Transformed knowledge content
            profile: Agent's capability profile
            warnings: List to append warnings to

        Returns:
            Customized knowledge content
        """
        customized = knowledge.copy()

        # Filter excluded topics
        if profile.excluded_topics:
            for topic in profile.excluded_topics:
                if topic in str(customized):
                    warnings.append(f"Content contains excluded topic: {topic}")  # noqa: PERF401

        # Check size limits
        content_size = len(str(customized))
        if content_size > profile.max_knowledge_size:
            warnings.append(
                f"Knowledge size ({content_size}) exceeds limit ({profile.max_knowledge_size})"
            )
            # Truncate large content
            customized = self._truncate_content(customized, profile.max_knowledge_size)

        # Apply format preferences
        if profile.preferred_formats:
            customized["_format_preferences"] = profile.preferred_formats

        return customized

    def _truncate_content(self, content: dict[str, Any], max_size: int) -> dict[str, Any]:
        """Truncate content to fit size limits."""
        content_str = str(content)
        if len(content_str) <= max_size:
            return content

        # Simple truncation - keep main keys
        truncated = {}
        current_size = 0

        for key, value in content.items():
            item_str = str(value)
            if current_size + len(item_str) <= max_size:
                truncated[key] = value
                current_size += len(item_str)
            else:
                truncated[key] = item_str[: max_size - current_size] + "... [truncated]"
                break

        return truncated

    def _calculate_applicability(
        self,
        pattern: ExtractedPattern,
        target_agent_type: AgentType,
        agent_id: str | None,  # noqa: ARG002
    ) -> float:
        """
        Calculate how applicable a pattern is to an agent type.

        Args:
            pattern: Source pattern
            target_agent_type: Target agent type
            agent_id: Optional specific agent ID

        Returns:
            Applicability score between 0.0 and 1.0
        """
        score = 0.5  # Base score

        # Boost if pattern involves same agent type
        pattern_agents = pattern.metadata.agents_involved
        if self._agent_type_in_list(target_agent_type, pattern_agents):
            score += 0.2

        # Boost if topics match agent type interests
        topic_match = self._topics_match_agent_type(
            pattern.metadata.topics,
            target_agent_type,
        )
        if topic_match:
            score += 0.15

        # Boost based on pattern confidence
        score += pattern.metadata.confidence * 0.15

        return min(1.0, score)

    def _calculate_priority(
        self,
        pattern: ExtractedPattern,
        target_agent_type: AgentType,
    ) -> float:
        """Calculate priority for knowledge distribution."""
        # Higher priority for:
        # - High confidence patterns
        # - Recent patterns
        # - Patterns involving same agent type

        priority = pattern.metadata.confidence * 0.5

        # Recency bonus
        try:
            last_observed = datetime.fromisoformat(pattern.metadata.last_observed)
            age_hours = (datetime.now(UTC) - last_observed).total_seconds() / 3600
            recency_bonus = max(0, 0.3 - (age_hours / 100))  # Decay over 30 hours
            priority += recency_bonus
        except (ValueError, TypeError):
            logger.debug("Knowledge transform parsing fallback", exc_info=True)

        # Agent type relevance
        if self._agent_type_in_list(target_agent_type, pattern.metadata.agents_involved):
            priority += 0.2

        return min(1.0, priority)

    def _agent_type_in_list(
        self,
        agent_type: AgentType,
        agent_ids: list[str],
    ) -> bool:
        """Check if agent type is represented in agent ID list."""
        type_keywords = {
            AgentType.LEADERSHIP: ["steward", "alpha", "arbiter"],
            AgentType.ANALYSIS: ["alpha", "beta", "charlie", "examiner"],
            AgentType.SUPPORT: ["historian", "metis", "empath", "nexus"],
            AgentType.EXPLORATION: ["explorer", "perceiver"],
            AgentType.DEVELOPMENT: ["coder", "dreamer", "catalyst"],
            AgentType.SAFETY: ["sentinel", "prime"],
            AgentType.COORDINATION: ["coordinator", "chronos"],
        }

        keywords = type_keywords.get(agent_type, [])
        return any(
            any(keyword in agent_id.lower() for keyword in keywords) for agent_id in agent_ids
        )

    def _topics_match_agent_type(
        self,
        topics: list[str],
        agent_type: AgentType,
    ) -> bool:
        """Check if topics match agent type interests."""
        topic_interests = {
            AgentType.LEADERSHIP: ["coordination", "strategy", "decision"],
            AgentType.ANALYSIS: ["analysis", "evaluation", "pattern"],
            AgentType.SUPPORT: ["memory", "knowledge", "assistance"],
            AgentType.EXPLORATION: ["discovery", "search", "investigation"],
            AgentType.DEVELOPMENT: ["code", "implementation", "optimization"],
            AgentType.SAFETY: ["security", "validation", "risk"],
            AgentType.COORDINATION: ["handoff", "communication", "synchronization"],
        }

        interests = topic_interests.get(agent_type, [])
        return any(
            any(interest in (topic or "").lower() for topic in topics) for interest in interests
        )

    def _get_agent_relevance(
        self,
        pattern: ExtractedPattern,
        agent_type: AgentType,
    ) -> dict[str, Any]:
        """Get relevance information for an agent type."""
        return {
            "agent_type": agent_type.value,
            "direct_relevance": self._agent_type_in_list(
                agent_type,
                pattern.metadata.agents_involved,
            ),
            "topic_relevance": self._topics_match_agent_type(
                pattern.metadata.topics,
                agent_type,
            ),
            "pattern_type_match": pattern.metadata.pattern_type
            in [
                PatternType.SUCCESS,
                PatternType.OPTIMIZATION,
            ],
        }

    def _infer_agent_types(self, agent_ids: list[str]) -> list[str]:
        """Infer agent types from agent IDs."""
        types = []
        type_keywords = {
            AgentType.LEADERSHIP.value: ["steward", "alpha", "arbiter"],
            AgentType.ANALYSIS.value: ["alpha", "beta", "charlie", "examiner"],
            AgentType.SUPPORT.value: ["historian", "metis", "empath", "nexus"],
            AgentType.EXPLORATION.value: ["explorer", "perceiver"],
            AgentType.DEVELOPMENT.value: ["coder", "dreamer", "catalyst"],
            AgentType.SAFETY.value: ["sentinel", "prime"],
            AgentType.COORDINATION.value: ["coordinator", "chronos"],
        }

        for agent_id in agent_ids:
            for agent_type, keywords in type_keywords.items():
                if any(keyword in agent_id.lower() for keyword in keywords):  # noqa: SIM102
                    if agent_type not in types:
                        types.append(agent_type)

        return types

    def _extract_key_insight(self, pattern: ExtractedPattern) -> str:
        """Extract key insight from a pattern."""
        insights = {
            PatternType.SUCCESS: "This interaction pattern leads to successful outcomes",
            PatternType.FAILURE: "This pattern identifies conditions that lead to failures",
            PatternType.OPTIMIZATION: "This pattern shows how to optimize agent interactions",
            PatternType.HANDOFF: "This pattern demonstrates effective task handoffs",
            PatternType.COLLABORATION: "This pattern shows successful multi-agent collaboration",
            PatternType.DECISION: "This pattern captures effective decision-making processes",
            PatternType.COMMUNICATION: "This pattern reveals efficient communication flows",
            PatternType.ERROR_RECOVERY: "This pattern shows how to recover from errors",
            PatternType.EMERGENT: "This pattern captures emergent multi-agent behavior",
            PatternType.RESOURCE_USAGE: "This pattern shows efficient resource usage",
        }

        base_insight = insights.get(
            pattern.metadata.pattern_type,
            "This pattern provides useful interaction insights",
        )

        # Add specificity from pattern data
        if pattern.pattern_data:
            key = next(iter(pattern.pattern_data), None)
            if key:
                base_insight += f" (focus: {key})"

        return base_insight

    def _predict_outcome(
        self,
        pattern: ExtractedPattern,
        agent_type: AgentType,  # noqa: ARG002
    ) -> str:
        """Predict outcome if pattern is applied."""
        if pattern.metadata.pattern_type == PatternType.SUCCESS:
            return "High probability of successful outcome if pattern is followed"
        if pattern.metadata.pattern_type == PatternType.FAILURE:
            return "Avoiding this pattern reduces failure risk"
        if pattern.metadata.pattern_type == PatternType.OPTIMIZATION:
            return "Expected improvement in efficiency or performance"
        if pattern.metadata.pattern_type == PatternType.HANDOFF:
            return "Smoother task transitions and reduced handoff latency"
        return "Improved agent coordination and decision quality"

    def _generate_examples(
        self,
        pattern: ExtractedPattern,
        agent_type: AgentType,
    ) -> list[dict[str, Any]]:
        """Generate examples for pattern application."""
        examples = []

        # Create example based on pattern type
        example_base = {
            "scenario": f"Example for {agent_type.value} agent",
            "pattern_application": "Apply the pattern by...",
            "expected_result": "Expected outcome...",
        }

        if pattern.metadata.pattern_type == PatternType.SUCCESS:
            example_base["scenario"] = "When facing a similar task..."
            example_base["pattern_application"] = "Follow the successful interaction sequence"
            example_base["expected_result"] = "Similar successful outcome"

        examples.append(example_base)

        return examples

    def _generate_counter_examples(
        self,
        pattern: ExtractedPattern,
    ) -> list[dict[str, Any]]:
        """Generate counter-examples showing what to avoid."""
        counter_examples = []

        if pattern.metadata.pattern_type == PatternType.FAILURE:
            counter_examples.append(
                {
                    "what_to_avoid": "Conditions that triggered this failure pattern",
                    "alternative": "Use alternative approach...",
                }
            )

        return counter_examples

    async def _validate_transformation(
        self,
        transformed: TransformedKnowledge,
        agent_type: AgentType,
    ) -> tuple[bool, list[str]]:
        """
        Validate transformed knowledge for an agent type.

        Args:
            transformed: TransformedKnowledge to validate
            agent_type: Target agent type

        Returns:
            Tuple of (validation_passed, error_list)
        """
        errors = []

        # Get validation rules for agent type
        validators = self._validation_rules.get(agent_type, [])

        # Run all validators
        for validator in validators:
            try:
                result = await validator(transformed)
                if not result.valid:
                    errors.extend(result.errors)
            except Exception as e:
                errors.append(f"Validation error: {e!s}")

        # Common validation checks
        if not transformed.knowledge_content:
            errors.append("Empty knowledge content")

        if transformed.validation_status == "invalid":
            errors.append("Knowledge marked as invalid")

        return len(errors) == 0, errors

    # Validation methods for each agent type
    async def _validate_leadership_knowledge(
        self,
        transformed: TransformedKnowledge,
    ) -> "ValidationResult":
        """Validate knowledge for leadership agents."""
        errors = []

        # Leadership needs strategic relevance
        if "strategy" not in str(transformed.knowledge_content).lower():  # noqa: SIM102
            if transformed.target_agent_type == AgentType.LEADERSHIP:
                errors.append("Leadership knowledge should have strategic relevance")

        return ValidationResult(valid=len(errors) == 0, errors=errors)

    async def _validate_analysis_knowledge(
        self,
        transformed: TransformedKnowledge,
    ) -> "ValidationResult":
        """Validate knowledge for analysis agents."""
        errors = []

        # Analysis needs data/analytical content
        content_str = str(transformed.knowledge_content)
        if not any(term in content_str.lower() for term in ["data", "analysis", "pattern"]):
            errors.append("Analysis knowledge should contain analytical content")

        return ValidationResult(valid=len(errors) == 0, errors=errors)

    async def _validate_support_knowledge(
        self,
        transformed: TransformedKnowledge,
    ) -> "ValidationResult":
        """Validate knowledge for support agents."""
        errors = []

        # Support knowledge should be actionable
        if transformed.transformation_type == TransformationType.ACTIONABLE:  # noqa: SIM102
            if not transformed.knowledge_content.get("recommended_actions"):
                errors.append("Support knowledge should have actionable recommendations")

        return ValidationResult(valid=len(errors) == 0, errors=errors)

    async def _validate_exploration_knowledge(
        self,
        transformed: TransformedKnowledge,
    ) -> "ValidationResult":
        """Validate knowledge for exploration agents."""
        errors = []

        # Exploration needs discovery-oriented content
        if "discovery" not in str(transformed.knowledge_content).lower():  # noqa: SIM102
            if transformed.transformation_type == TransformationType.EXPANDED:
                errors.append("Exploration knowledge should encourage discovery")

        return ValidationResult(valid=len(errors) == 0, errors=errors)

    async def _validate_development_knowledge(
        self,
        transformed: TransformedKnowledge,
    ) -> "ValidationResult":
        """Validate knowledge for development agents."""
        errors = []

        # Development needs implementation details
        if transformed.transformation_type in [
            TransformationType.DETAILED,
            TransformationType.ACTIONABLE,
        ]:
            content_str = str(transformed.knowledge_content)
            if not any(term in content_str for term in ["implement", "code", "build"]):
                errors.append("Development knowledge should have implementation focus")

        return ValidationResult(valid=len(errors) == 0, errors=errors)

    async def _validate_safety_knowledge(
        self,
        transformed: TransformedKnowledge,
    ) -> "ValidationResult":
        """Validate knowledge for safety agents."""
        errors = []

        # Safety knowledge must include risk/validation info
        if transformed.target_agent_type == AgentType.SAFETY:
            content_str = str(transformed.knowledge_content)
            if not any(
                term in content_str.lower() for term in ["risk", "validate", "security", "check"]
            ):
                errors.append("Safety knowledge should address risk or validation")

        return ValidationResult(valid=len(errors) == 0, errors=errors)

    async def _validate_coordination_knowledge(
        self,
        transformed: TransformedKnowledge,
    ) -> "ValidationResult":
        """Validate knowledge for coordination agents."""
        errors = []

        # Coordination needs interaction patterns
        if "interaction" not in str(transformed.knowledge_content).lower():  # noqa: SIM102
            if "handoff" not in str(transformed.knowledge_content).lower():  # noqa: SIM102
                if "communication" not in str(transformed.knowledge_content).lower():
                    errors.append("Coordination knowledge should involve interaction patterns")

        return ValidationResult(valid=len(errors) == 0, errors=errors)

    def get_transformed_knowledge(
        self,
        transformation_id: str,
    ) -> TransformedKnowledge | None:
        """
        Get transformed knowledge by ID.

        Args:
            transformation_id: Transformation identifier

        Returns:
            TransformedKnowledge or None if not found
        """
        return self._transformed_cache.get(transformation_id)

    def clear_cache(self) -> None:
        """Clear the transformed knowledge cache."""
        self._transformed_cache.clear()
        logger.info("transformed_knowledge_cache_cleared")


@dataclass
class ValidationResult:
    """Result of a validation operation."""

    valid: bool
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


class KnowledgeTransformationService:
    """
    Service for orchestrating knowledge transformations.

    This service provides a high-level interface for transforming
    patterns and distributing knowledge across the swarm.
    """

    def __init__(self):
        """Initialize knowledge transformation service."""
        self.transformer = KnowledgeTransformer()
        self._transformation_history: list[TransformationResult] = []

        logger.info("knowledge_transformation_service_initialized")

    async def transform_and_distribute(
        self,
        pattern: ExtractedPattern,
        target_agent_types: list[AgentType] | None = None,
    ) -> dict[str, Any]:
        """
        Transform a pattern and prepare for distribution.

        Args:
            pattern: Pattern to transform
            target_agent_types: Agent types to transform for (default: all)

        Returns:
            Distribution summary
        """
        if target_agent_types is None:
            target_agent_types = list(AgentType)

        results = await self.transformer.transform_for_multiple_agents(
            pattern=pattern,
            agent_types=target_agent_types,
            transformation_type=TransformationType.ABSTRACT,
        )

        # Store history
        self._transformation_history.extend(results)

        # Generate summary
        successful = sum(1 for r in results if r.success)
        failed = len(results) - successful

        return {
            "pattern_id": pattern.metadata.pattern_id,
            "transformations_attempted": len(results),
            "transformations_successful": successful,
            "transformations_failed": failed,
            "results": [r.to_dict() if hasattr(r, "to_dict") else str(r) for r in results],
        }

    def get_transformation_status(self) -> dict[str, Any]:
        """
        Get current transformation service status.

        Returns:
            Status dictionary
        """
        return {
            "total_transformations": len(self._transformation_history),
            "successful": sum(1 for r in self._transformation_history if r.success),
            "failed": sum(1 for r in self._transformation_history if not r.success),
            "cache_size": len(self.transformer._transformed_cache),  # noqa: SLF001
            "registered_agents": len(self.transformer._agent_profiles),  # noqa: SLF001
        }
