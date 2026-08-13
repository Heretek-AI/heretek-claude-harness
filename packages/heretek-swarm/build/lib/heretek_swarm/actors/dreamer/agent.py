"""
Dreamer Agent - Creative Solution Generation & Divergent Thinking.

The Dreamer provides:
- Novel solution generation through divergent thinking
- Creative problem-solving and ideation
- Alternative perspective exploration
- Innovation and breakthrough ideas
- Scenario imagination and visualization
- Pattern breaking and lateral thinking

Dreamer is the "creative engine" of the Collective, generating novel
solutions that other agents might not consider through conventional analysis.

Extracted components:
- types.py: Type definitions (CreativityTechnique, IdeaCategory, NoveltyLevel, etc.)
- generators.py: DreamerGeneratorsMixin for generation helpers

Author: Heretek Swarm Collective
Date: 2026-04-17
Version: 1.0.0
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

import structlog

from heretek_swarm.actors.base import ActorMessage, AgentActor
from heretek_swarm.actors.dreamer.generators import DreamerGeneratorsMixin
from heretek_swarm.actors.dreamer.types import (
    CreativeIdea,
    CreativeSession,
    CreativityTechnique,
    IdeaCategory,
    NoveltyLevel,
)
from heretek_swarm.actors.mixins import (
    DeliberationMixin,
    LearningMixin,
    MemoryMixin,
    PatternMixin,
    ValidationMixin,
)
from heretek_swarm.actors.validation import validate_message

# DISC-03: Novel Connections Module
from heretek_swarm.creativity.novel_connections import (
    ConnectionTechnique,
    HarmfulContentFilter,
    LateralThinkingMetricsTracker,
    NovelConnection,
    NovelConnectionEngine,
)

# Session 44: Zero-Trust Validation
from heretek_swarm.security.zero_trust import ZeroTrustValidator

logger = structlog.get_logger("DreamerAgent")


class DreamerAgent(
    ValidationMixin,
    DeliberationMixin,
    PatternMixin,
    MemoryMixin,
    LearningMixin,
    DreamerGeneratorsMixin,
    AgentActor,
):
    """
    Creative Solution Generation & Divergent Thinking Agent.

    Dreamer generates novel solutions through creative thinking techniques,
    providing the Collective with innovative approaches to complex problems.
    """

    def __init__(
        self,
        agent_id: str = "dreamer",
        name: str = "Dreamer",
        description: str = "Creative Solution Generation Specialist",
        swarms_agent=None,  # noqa: ARG002
        pattern_extractor=None,
        deliberation_engine=None,
        access_analyzer=None,
        zero_trust_validator=None,
        **kwargs,
    ):
        super().__init__(
            agent_id=agent_id,
            name=name,
            description=description,
            **kwargs,
        )

        self._config: dict[str, Any] = {}

        # Idea storage
        self._ideas: dict[str, CreativeIdea] = {}
        self._idea_counter = 0
        self.max_ideas = self._config.get("max_ideas", 500)

        # Creative sessions
        self._sessions: dict[str, CreativeSession] = {}
        self._active_sessions: set[str] = set()
        self.max_sessions = self._config.get("max_sessions", 50)

        # Creativity configuration
        self._default_technique = self._config.get(
            "default_technique", CreativityTechnique.BRAINSTORMING
        )
        self._creativity_temperature = self._config.get("creativity_temperature", 0.8)  # LLM temp
        self._divergence_factor = self._config.get("divergence_factor", 5)  # Ideas per session

        # Inspiration cache
        self._inspiration_cache: list[dict[str, Any]] = []
        self.max_inspiration = self._config.get("max_inspiration", 100)

        # Session 44: Collective Learning Integration
        self.pattern_extractor = pattern_extractor

        # Session 44: Consensus Integration
        self.deliberation_engine = deliberation_engine

        # Session 44: Memory Optimization Integration
        self.access_analyzer = access_analyzer

        # Session 44: Zero-Trust Validation
        self.zero_trust_validator = zero_trust_validator or ZeroTrustValidator()

        # Session 44: Integration state (required by mixins)
        self._active_deliberations: dict[str, str] = {}
        self._pattern_emitted: set[str] = set()

        # DISC-03: Novel connection components
        self._connection_engine = NovelConnectionEngine(
            llm_provider=None,
            creativity_temperature=self._creativity_temperature,
            max_connections_per_session=self._config.get("max_connections", 20),
        )

        self._content_filter = HarmfulContentFilter(
            beta_agent_id=self._config.get("beta_agent_id", "beta"),
        )

        self._metrics_tracker = LateralThinkingMetricsTracker()

        # DISC-03: Novel connection state
        self._novel_connections: dict[str, NovelConnection] = {}
        self._connection_counter = 0

        logger.info(
            "DreamerAgent initialized",
            agent_id=self.agent_id,
            default_technique=self._default_technique.value,
            creativity_temperature=self._creativity_temperature,
        )

    def get_handlers(self) -> dict[str, callable]:
        """Return message handlers for Dreamer agent."""
        return {
            "generate_ideas": self._handle_generate_ideas,
            "start_creative_session": self._handle_start_creative_session,
            "explore_alternatives": self._handle_explore_alternatives,
            "apply_creativity_technique": self._handle_apply_creativity_technique,
            "get_innovation_report": self._handle_get_innovation_report,
            "get_idea_details": self._handle_get_idea_details,
            "combine_ideas": self._handle_combine_ideas,
            "generate_novel_connections": self._handle_generate_novel_connections,
            "get_lateral_thinking_metrics": self._handle_get_lateral_thinking_metrics,
            "track_deliberation_contribution": self._handle_track_deliberation_contribution,
        }

    # ========================================================================
    # Message Handlers
    # ========================================================================

    async def _handle_generate_ideas(self, message: ActorMessage) -> dict[str, Any] | None:
        """Handle idea generation request."""
        try:
            content = validate_message("DreamerGenerateIdeas", message.content)
            problem = content.get("problem", "")
            constraints = content.get("constraints", [])
            technique = CreativityTechnique(content.get("technique", self._default_technique.value))
            num_ideas = content.get("num_ideas", self._divergence_factor)

            logger.info(
                "Generating ideas",
                problem=problem[:100],
                technique=technique.value,
                num_ideas=num_ideas,
            )

            ideas = await self._generate_creative_ideas(
                problem=problem, constraints=constraints, technique=technique, num_ideas=num_ideas
            )

            stored_ids = []
            for idea in ideas:
                self._idea_counter += 1
                idea.id = f"idea_{self._idea_counter}"
                self._ideas[idea.id] = idea
                stored_ids.append(idea.id)

            if len(self._ideas) > self.max_ideas:
                excess = len(self._ideas) - self.max_ideas
                for _ in range(excess):
                    oldest_id = next(iter(self._ideas))
                    del self._ideas[oldest_id]

            top_idea = None
            if ideas:
                top_idea = {
                    "id": stored_ids[0],
                    "title": ideas[0].title,
                    "novelty": ideas[0].novelty.value,
                }

            return {
                "status": "success",
                "ideas_generated": len(ideas),
                "idea_ids": stored_ids,
                "technique_used": technique.value,
                "top_idea": top_idea,
            }

        except Exception as e:
            logger.error("Failed to generate ideas", error=str(e))
            return {"status": "error", "error": str(e)}

    async def _handle_start_creative_session(self, message: ActorMessage) -> dict[str, Any] | None:
        """Handle creative session start request."""
        try:
            content = validate_message("DreamerStartCreativeSession", message.content)
            problem_statement = content.get("problem_statement", "")
            technique = CreativityTechnique(content.get("technique", self._default_technique.value))
            constraints = content.get("constraints", [])
            inspiration_sources = content.get("inspiration_sources", [])

            session_id = f"session_{uuid.uuid4().hex[:8]}"
            session = CreativeSession(
                id=session_id,
                problem_statement=problem_statement,
                technique=technique,
                ideas_generated=[],
                started_at=datetime.now(UTC),
                constraints=constraints,
                inspiration_sources=inspiration_sources,
            )

            self._sessions[session_id] = session
            self._active_sessions.add(session_id)

            if len(self._sessions) > self.max_sessions:
                oldest_id = next(iter(self._sessions))
                del self._sessions[oldest_id]
                self._active_sessions.discard(oldest_id)

            logger.info(
                "Creative session started", session_id=session_id, technique=technique.value
            )

            return {
                "status": "success",
                "session_id": session_id,
                "technique": technique.value,
                "problem_statement": problem_statement[:100],
                "estimated_duration_minutes": 15,
            }

        except Exception as e:
            logger.error("Failed to start creative session", error=str(e))
            return {"status": "error", "error": str(e)}

    async def _handle_explore_alternatives(self, message: ActorMessage) -> dict[str, Any] | None:
        """Handle alternative exploration request."""
        try:
            content = validate_message("DreamerExploreAlternatives", message.content)
            current_solution = content.get("current_solution", "")
            domain = content.get("domain", "general")
            divergence_level = content.get("divergence_level", "medium")

            logger.info(
                "Exploring alternatives",
                current_solution=current_solution[:100],
                domain=domain,
                divergence_level=divergence_level,
            )

            alternatives = await self._generate_alternatives(
                current_solution=current_solution, domain=domain, divergence_level=divergence_level
            )

            return {
                "status": "success",
                "current_solution": current_solution[:200],
                "alternatives": alternatives,
                "count": len(alternatives),
            }

        except Exception as e:
            logger.error("Failed to explore alternatives", error=str(e))
            return {"status": "error", "error": str(e)}

    async def _handle_apply_creativity_technique(
        self, message: ActorMessage
    ) -> dict[str, Any] | None:
        """Handle technique application request."""
        try:
            content = validate_message("DreamerApplyTechnique", message.content)
            problem = content.get("problem", "")
            technique = CreativityTechnique(content.get("technique", self._default_technique.value))
            context = content.get("context", {})

            logger.info(
                "Applying creativity technique", technique=technique.value, problem=problem[:100]
            )

            result = await self._apply_technique(
                problem=problem, technique=technique, context=context
            )

            return {
                "status": "success",
                "technique": technique.value,
                "result": result,
                "insights_count": len(result.get("insights", [])),
            }

        except Exception as e:
            logger.error("Failed to apply creativity technique", error=str(e))
            return {"status": "error", "error": str(e)}

    async def _handle_get_innovation_report(self, message: ActorMessage) -> dict[str, Any] | None:
        """Handle innovation report generation request."""
        try:
            content = validate_message("DreamerInnovationReport", message.content)
            problem_area = content.get("problem_area", "all")
            include_sessions = content.get("include_sessions", True)
            content.get("time_range_days", 7)

            logger.info("Generating innovation report", problem_area=problem_area)

            cutoff = datetime.now(UTC)
            ideas = [idea for idea in self._ideas.values() if idea.generated_at >= cutoff]

            sessions = list(self._sessions.values()) if include_sessions else []

            innovation_score = self._calculate_innovation_score(ideas, sessions)

            report_content = await self._generate_innovation_report(
                ideas=ideas,
                sessions=sessions,
                problem_area=problem_area,
                innovation_score=innovation_score,
            )

            return {
                "status": "success",
                "report": {
                    "generated_at": datetime.now(UTC).isoformat(),
                    "problem_area": problem_area,
                    "innovation_score": innovation_score,
                    "ideas_count": len(ideas),
                    "sessions_count": len(sessions),
                    "top_recommendations": report_content.get("recommendations", []),
                    "implementation_roadmap": report_content.get("roadmap", []),
                    "risks": report_content.get("risks", []),
                    "opportunities": report_content.get("opportunities", []),
                },
            }

        except Exception as e:
            logger.error("Failed to generate innovation report", error=str(e))
            return {"status": "error", "error": str(e)}

    async def _handle_get_idea_details(self, message: ActorMessage) -> dict[str, Any] | None:
        """Handle idea details retrieval request."""
        try:
            content = validate_message("DreamerGetIdeaDetails", message.content)
            idea_id = content.get("idea_id")

            if not idea_id:
                return {"status": "error", "error": "idea_id required"}

            idea = self._ideas.get(idea_id)
            if not idea:
                return {"status": "error", "error": f"Idea {idea_id} not found"}

            return {
                "status": "success",
                "idea": {
                    "id": idea.id,
                    "title": idea.title,
                    "description": idea.description,
                    "category": idea.category.value,
                    "novelty": idea.novelty.value,
                    "feasibility_score": idea.feasibility_score,
                    "impact_score": idea.impact_score,
                    "originality_score": idea.originality_score,
                    "generated_at": idea.generated_at.isoformat(),
                    "variations": idea.variations,
                },
            }

        except Exception as e:
            logger.error("Failed to get idea details", error=str(e))
            return {"status": "error", "error": str(e)}

    async def _handle_combine_ideas(self, message: ActorMessage) -> dict[str, Any] | None:
        """Handle idea combination request."""
        try:
            content = validate_message("DreamerCombineIdeas", message.content)
            idea_ids = content.get("idea_ids", [])
            combination_method = content.get("combination_method", "synthesis")

            ideas = [self._ideas.get(iid) for iid in idea_ids]
            ideas = [i for i in ideas if i is not None]

            if len(ideas) < 2:
                return {"status": "error", "error": "Need at least 2 valid ideas to combine"}

            logger.info("Combining ideas", idea_count=len(ideas), method=combination_method)

            combined = await self._combine_ideas_llm(ideas=ideas, method=combination_method)

            self._idea_counter += 1
            new_idea = CreativeIdea(
                id=f"idea_{self._idea_counter}",
                title=combined.get("title", "Combined Solution"),
                description=combined.get("description", ""),
                category=IdeaCategory(combined.get("category", "product")),
                novelty=NoveltyLevel.BREAKTHROUGH,
                technique_used=CreativityTechnique.ANALOGICAL_THINKING,
                feasibility_score=combined.get("feasibility", 0.5),
                impact_score=combined.get("impact", 0.8),
                originality_score=combined.get("originality", 0.9),
                generated_at=datetime.now(UTC),
                related_to=", ".join(idea_ids),
                variations=combined.get("variations", []),
            )
            self._ideas[new_idea.id] = new_idea

            return {
                "status": "success",
                "combined_idea_id": new_idea.id,
                "title": new_idea.title,
                "novelty": new_idea.novelty.value,
                "source_ideas": idea_ids,
            }

        except Exception as e:
            logger.error("Failed to combine ideas", error=str(e))
            return {"status": "error", "error": str(e)}

    async def _handle_generate_novel_connections(
        self, message: ActorMessage
    ) -> dict[str, Any] | None:
        """Handle novel connections generation request."""
        try:
            content = validate_message("DreamerNovelConnections", message.content)
            concepts = content.get("concepts", [])
            technique_str = content.get("technique", ConnectionTechnique.RANDOM_ASSOCIATION.value)
            technique = ConnectionTechnique(technique_str)
            target_count = content.get("target_count", 5)

            if len(concepts) < 2:
                return {"status": "error", "error": "At least 2 concepts required"}

            logger.info(
                "Generating novel connections",
                concepts=concepts[:3],
                technique=technique.value,
                target_count=target_count,
            )

            connections = await self._connection_engine.generate_connections(
                concepts=concepts,
                technique=technique,
                target_count=target_count,
            )

            validated_connections = []
            rejected_count = 0

            for conn in connections:
                is_safe, reason = await self._content_filter.validate_connection(conn)
                if is_safe:
                    conn.validated = True
                    validated_connections.append(conn)
                    self._connection_counter += 1
                    conn.connection_id = f"conn-{self._connection_counter}"
                    self._novel_connections[conn.connection_id] = conn
                else:
                    conn.validated = False
                    conn.validation_notes = reason
                    rejected_count += 1

            session_id = message.correlation_id or f"session-{uuid.uuid4().hex[:8]}"
            metrics = self._calculate_session_metrics(
                connections, validated_connections, rejected_count
            )
            await self._metrics_tracker.track_session(session_id, metrics)

            if self._metrics_tracker.detect_overreliance():
                logger.warning("Over-reliance on Dreamer detected - alerting Steward")
                await self._notify_steward_overreliance()

            return {
                "status": "success",
                "connections_generated": len(connections),
                "validated_count": len(validated_connections),
                "rejected_count": rejected_count,
                "connections": [c.to_dict() for c in validated_connections],
            }

        except Exception as e:
            logger.error("Failed to generate novel connections", error=str(e))
            return {"status": "error", "error": str(e)}

    async def _handle_get_lateral_thinking_metrics(
        self, message: ActorMessage
    ) -> dict[str, Any] | None:
        """Handle lateral thinking metrics request."""
        try:
            content = validate_message("DreamerGetLateralMetrics", message.content)
            session_id = content.get("session_id")

            if session_id:
                metrics = self._metrics_tracker._session_metrics.get(session_id)  # noqa: SLF001
                if metrics:
                    return {
                        "status": "success",
                        "metrics": {
                            "session_id": metrics.session_id,
                            "divergence_score": metrics.divergence_score,
                            "association_distance_avg": metrics.association_distance_avg,
                            "insight_rate": metrics.insight_rate,
                            "breakthrough_count": metrics.breakthrough_count,
                            "validated_count": metrics.validated_count,
                            "total_connections": metrics.total_connections,
                            "creativity_score": metrics.calculate_creativity_score(),
                        },
                    }
                return {"status": "error", "error": f"Session {session_id} not found"}

            all_metrics = [
                {
                    "session_id": m.session_id,
                    "creativity_score": m.calculate_creativity_score(),
                    "total_connections": m.total_connections,
                }
                for m in self._metrics_tracker._session_metrics.values()  # noqa: SLF001
            ]

            return {
                "status": "success",
                "metrics": all_metrics,
                "count": len(all_metrics),
                "position_change_ratio": self._metrics_tracker.calculate_position_change_ratio(),
                "dreamer_usage_rate": self._metrics_tracker.calculate_dreamer_usage_rate(),
            }

        except Exception as e:
            logger.error("Failed to get lateral thinking metrics", error=str(e))
            return {"status": "error", "error": str(e)}

    async def _handle_track_deliberation_contribution(
        self, message: ActorMessage
    ) -> dict[str, Any] | None:
        """Handle deliberation contribution tracking request."""
        try:
            content = validate_message("DreamerDeliberationContribution", message.content)
            deliberation_id = content.get("deliberation_id")
            idea_ids = content.get("idea_ids", [])
            outcome = content.get("outcome")

            self._metrics_tracker.record_dreamer_contribution(True)

            if outcome in ["rejected", "modified"]:
                self._metrics_tracker.record_position_change(True)
            else:
                self._metrics_tracker.record_position_change(False)

            logger.info(
                "Deliberation contribution tracked",
                deliberation_id=deliberation_id,
                idea_count=len(idea_ids),
                outcome=outcome,
            )

            return {
                "status": "success",
                "contribution_recorded": True,
            }

        except Exception as e:
            logger.error("Failed to track deliberation contribution", error=str(e))
            return {"status": "error", "error": str(e)}

    # ========================================================================
    # Internal Helper Methods
    # ========================================================================

    # ========================================================================
    # Internal Helper Methods
    # ========================================================================
