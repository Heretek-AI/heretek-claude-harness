"""
Prism Agent - Multi-Perspective Analysis & Bias Detection.

The Prism agent provides:
- Multi-perspective analysis of complex issues
- Cognitive bias detection in collective reasoning
- Analytical framework application (First Principles, Systems Thinking, etc.)
- Stakeholder mapping and viewpoint synthesis
- Perspective diversification for decision-making

Named for the ability to refract complex issues into multiple distinct perspectives,
revealing hidden facets and ensuring comprehensive analysis.
"""

from datetime import UTC, datetime
from typing import Any

import structlog
from heretek_swarm.actors.base import ActorMessage, AgentActor
from heretek_swarm.actors.mixins import (
    DeliberationMixin,
    LearningMixin,
    MemoryMixin,
    PatternMixin,
    ValidationMixin,
)
from heretek_swarm.actors.prism.transforms import (
    PrismTransforms,
    apply_framework_fallback,
    detect_biases_heuristic,
    generate_heuristic_perspective,
    generate_reframe_fallback,
    generate_stakeholder_map_fallback,
    get_framework_prompt,
)

# Import types and transforms from sibling modules
from heretek_swarm.actors.prism.types import (
    AnalyticalFramework,
    BiasDetection,
    BiasType,
    Perspective,
    PerspectiveType,
)

# Session 44: Collective Learning Integration
from heretek_swarm.consciousness.phi_training import (
    DecisionCoherenceTrainingScenario,
    PhiTrainingEnvironment,
    TrainingScenario,
)

logger = structlog.get_logger("PrismAgent")


class PrismAgent(
    ValidationMixin,
    DeliberationMixin,
    PatternMixin,
    MemoryMixin,
    LearningMixin,
    PrismTransforms,
    AgentActor,
):
    """
    Prism Agent - Multi-Perspective Analysis Specialist.

    The Prism is responsible for:
    - Generating multiple perspectives on complex issues
    - Detecting cognitive biases in collective reasoning
    - Applying different analytical frameworks to problems
    - Mapping stakeholders and their interests
    - Ensuring diverse viewpoints are considered

    Perspective Analysis Workflow:
    1. Receive issue or decision for analysis
    2. Identify relevant perspective types
    3. Generate viewpoints for each perspective
    4. Detect biases in current reasoning
    5. Apply analytical frameworks
    6. Synthesize insights for collective
    """

    def __init__(
        self,
        agent_id: str = "prism",
        name: str = "Prism",
        description: str = "Multi-perspective analysis and bias detection specialist",
        max_perspectives: int = 12,
        max_bias_history: int = 100,
        confidence_threshold: float = 0.6,
        pattern_extractor=None,
        deliberation_engine=None,
        access_analyzer=None,
        zero_trust_validator=None,
        **kwargs,
    ) -> None:
        """
        Initialize the Prism agent.

        Args:
            agent_id: Unique identifier
            name: Human-readable name
            description: Agent description
            max_perspectives: Maximum perspectives to generate per issue
            max_bias_history: Maximum bias detections to track
            confidence_threshold: Minimum confidence for perspective recommendations
            pattern_extractor: Optional pattern extractor
            deliberation_engine: Optional deliberation engine
            access_analyzer: Optional access analyzer
            zero_trust_validator: Optional zero trust validator
            **kwargs: Additional arguments
        """
        super().__init__(
            agent_id=agent_id,
            name=name,
            description=description,
            topics=[
                "perspectives",
                "analysis",
                "reframing",
                "biases",
                "viewpoints",
            ],
            capabilities=[
                "multi-perspective-analysis",
                "bias-detection",
                "framework-application",
                "stakeholder-mapping",
                "viewpoint-synthesis",
            ],
            pattern_extractor=pattern_extractor,
            deliberation_engine=deliberation_engine,
            access_analyzer=access_analyzer,
            zero_trust_validator=zero_trust_validator,
            **kwargs,
        )

        # Prism-specific state
        self.max_perspectives = max_perspectives
        self.max_bias_history = max_bias_history
        self.confidence_threshold = confidence_threshold

        # Perspective and bias tracking
        self.active_analyses: dict[str, dict[str, Any]] = {}
        self.perspective_cache: dict[str, list[Perspective]] = {}
        self.bias_history: list[BiasDetection] = []
        self.framework_results: dict[str, dict[str, Any]] = {}
        self.stakeholder_maps: dict[str, dict[str, Any]] = {}

        # Available perspectives and frameworks
        self.available_perspectives: list[PerspectiveType] = list(PerspectiveType)
        self.available_frameworks: list[AnalyticalFramework] = list(AnalyticalFramework)
        self.available_biases: list[BiasType] = list(BiasType)

        # Session 44: Integration state
        self._active_deliberations: dict[str, str] = {}
        self._pattern_emitted: set[str] = set()

        logger.info(f"[{self.agent_id}] Prism agent initialized")

    async def initialize(self) -> None:
        """Initialize the Prism agent."""
        # Register message handlers with Zero-Trust validation
        self.register_handler("generate_perspectives", self._handle_generate_perspectives)
        self.register_handler("detect_biases", self._handle_detect_biases)
        self.register_handler("apply_framework", self._handle_apply_framework)
        self.register_handler("map_stakeholders", self._handle_map_stakeholders)
        self.register_handler("get_analysis_summary", self._handle_get_analysis_summary)
        self.register_handler("reframe_issue", self._handle_reframe_issue)

        logger.info(f"[{self.agent_id}] Prism initialization complete")

    async def process_message(self, message: ActorMessage) -> None:
        """
        Process incoming messages with exception handling.

        Args:
            message: Actor message to process
        """
        handler = self._message_handlers.get(message.message_type)
        if handler:
            try:
                await handler(message)
            except Exception as e:
                logger.exception(
                    f"[{self.agent_id}] Error processing message {message.message_type}: {e}",

                )
                self.error_count += 1
                if message.content.get("reply_to"):
                    await self.send(
                        topic=message.content["reply_to"],
                        content={
                            "message_type": "error_response",
                            "error": str(e),
                            "original_message_type": message.message_type,
                        },
                        sender_id=self.agent_id,
                    )
        else:
            logger.warning(f"[{self.agent_id}] Unknown message type: {message.message_type}")

    def _validate_analysis_request(self, content: dict[str, Any]) -> tuple[bool, str]:
        """
        Validate analysis request content.

        Args:
            content: Message content to validate

        Returns:
            Tuple of (is_valid, error_message)
        """
        if "issue" not in content:
            return False, "Missing required field: issue"
        if not isinstance(content["issue"], str):
            return False, "Field 'issue' must be a string"
        if len(content["issue"]) > 10000:
            return False, "Issue exceeds maximum length (10000 chars)"
        return True, ""

    async def _handle_generate_perspectives(self, message: ActorMessage) -> None:
        """
        Generate multiple perspectives on an issue.

        Args:
            message: Actor message with issue details
        """
        try:
            # Validate content
            is_valid, _error = self._validate_analysis_request(message.content)
            if not is_valid:
                logger.error(f"[{self.agent_id}] Invalid perspective request: {_error}")
                return

            issue = message.content["issue"]
            analysis_id = message.content.get(
                "analysis_id", f"analysis_{datetime.now(UTC).timestamp()}"
            )
            requested_perspectives = message.content.get("perspective_types", None)

            logger.info(f"[{self.agent_id}] Generating perspectives for analysis: {analysis_id}")

            # Generate perspectives
            perspectives = await self._generate_perspectives(
                issue=issue,
                perspective_types=requested_perspectives,
            )

            # Store in cache
            self.perspective_cache[analysis_id] = perspectives

            # Store active analysis
            self.active_analyses[analysis_id] = {
                "issue": issue,
                "perspectives_count": len(perspectives),
                "timestamp": datetime.now(UTC).isoformat(),
                "status": "complete",
            }

            # Send response
            response = {
                "message_type": "perspectives_response",
                "analysis_id": analysis_id,
                "perspectives": [p.to_dict() for p in perspectives],
                "perspectives_count": len(perspectives),
            }

            if message.content.get("reply_to"):
                await self.send(
                    topic=message.content["reply_to"],
                    content=response,
                    sender_id=self.agent_id,
                )

            logger.info(
                f"[{self.agent_id}] Generated {len(perspectives)} perspectives for analysis: {analysis_id}"
            )

        except Exception as e:
            logger.exception(f"[{self.agent_id}] Error generating perspectives: {e}")

    async def _generate_perspectives(
        self,
        issue: str,
        perspective_types: list[str] | None = None,
    ) -> list[Perspective]:
        """
        Generate multiple perspectives on an issue.

        Args:
            issue: The issue to analyze
            perspective_types: Optional list of specific perspective types

        Returns:
            List of Perspective objects
        """
        perspectives = []

        # Determine which perspectives to generate
        if perspective_types:
            types_to_use = [
                PerspectiveType(t)
                for t in perspective_types
                if t in [pt.value for pt in PerspectiveType]
            ]
        else:
            types_to_use = self.available_perspectives[: self.max_perspectives]

        # Generate perspective for each type
        for ptype in types_to_use:
            try:
                perspective = await self._generate_single_perspective(issue, ptype)
                if perspective.confidence >= self.confidence_threshold:
                    perspectives.append(perspective)
            except Exception as e:
                logger.warning(
                    f"[{self.agent_id}] Failed to generate {ptype.value} perspective: {e}"
                )

        # Sort by confidence
        perspectives.sort(key=lambda p: p.confidence, reverse=True)

        return perspectives[: self.max_perspectives]

    async def _generate_single_perspective(
        self,
        issue: str,
        perspective_type: PerspectiveType,
    ) -> Perspective:
        """
        Generate a single perspective on an issue.

        Args:
            issue: The issue to analyze
            perspective_type: Type of perspective to generate

        Returns:
            Perspective object
        """
        # Build prompt for LLM
        prompt = f"""Analyze the following issue from a {perspective_type.value} perspective:

ISSUE: {issue}

Generate a comprehensive {perspective_type.value} perspective including:
1. The primary viewpoint from this perspective
2. Key insights this perspective reveals
3. Underlying assumptions this perspective makes
4. Blind spots or limitations of this perspective
5. A confidence score (0-1) in the analysis

Respond in JSON format:
{{
    "viewpoint": "...",
    "key_insights": ["...", "..."],
    "assumptions": ["...", "..."],
    "blind_spots": ["...", "..."],
    "confidence": 0.0-1.0
}}"""

        try:
            # Try LLM-based generation
            if self.pydantic_ai_agent:
                result = await self.run_with_llm(
                    prompt=prompt,
                    timeout=60,
                )

                # Parse result (assume JSON in response)
                import json

                try:
                    # Extract JSON from response
                    start_idx = result.find("{")
                    end_idx = result.rfind("}") + 1
                    if start_idx >= 0 and end_idx > start_idx:
                        json_str = result[start_idx:end_idx]
                        data = json.loads(json_str)

                        return Perspective(
                            perspective_type=perspective_type,
                            viewpoint=data.get("viewpoint", ""),
                            key_insights=data.get("key_insights", []),
                            assumptions=data.get("assumptions", []),
                            blind_spots=data.get("blind_spots", []),
                            confidence=float(data.get("confidence", 0.5)),
                        )
                except Exception as e:
                    logger.debug("prism_parse_failed", error=str(e))

            # Fallback: Generate heuristic perspective
            return self._heuristic_perspective(issue, perspective_type)

        except Exception as e:
            logger.warning(
                f"[{self.agent_id}] LLM perspective generation failed, using heuristic: {e}"
            )
            return self._heuristic_perspective(issue, perspective_type)

    async def _handle_detect_biases(self, message: ActorMessage) -> None:
        """
        Detect cognitive biases in reasoning or deliberation.

        Args:
            message: Actor message with reasoning/deliberation content
        """
        try:
            # Validate content
            content = message.content.get("reasoning", "") or message.content.get(
                "deliberation", ""
            )
            if not content:
                logger.error(f"[{self.agent_id}] No reasoning content provided for bias detection")
                return

            if len(content) > 50000:
                logger.error(f"[{self.agent_id}] Content exceeds maximum length")
                return

            logger.info(f"[{self.agent_id}] Detecting biases in reasoning")

            # Detect biases
            biases = await self._detect_biases_in_content(content)

            # Store in history
            self.bias_history.extend(biases)
            if len(self.bias_history) > self.max_bias_history:
                self.bias_history = self.bias_history[-self.max_bias_history :]

            # Send response
            response = {
                "message_type": "bias_detection_response",
                "biases_detected": len(biases),
                "biases": [b.to_dict() for b in biases],
                "recommendations": [b.recommendation for b in biases if b.recommendation],
            }

            if message.content.get("reply_to"):
                await self.send(
                    topic=message.content["reply_to"],
                    content=response,
                    sender_id=self.agent_id,
                )

            logger.info(f"[{self.agent_id}] Detected {len(biases)} potential biases")

        except Exception as e:
            logger.exception(f"[{self.agent_id}] Error detecting biases: {e}")

    async def _detect_biases_in_content(self, content: str) -> list[BiasDetection]:
        """
        Detect cognitive biases in content.

        Args:
            content: Text content to analyze

        Returns:
            List of detected biases
        """
        biases = []

        # Build prompt for LLM
        prompt = f"""Analyze the following reasoning for cognitive biases:

REASONING: {content[:5000]}  # Truncate for prompt

Identify any cognitive biases present, including:
- Confirmation bias (favoring information that confirms existing beliefs)
- Anchoring bias (relying too heavily on first piece of information)
- Availability heuristic (overweighting recent/vivid information)
- Survivorship bias (focusing on successes while ignoring failures)
- Sunk cost fallacy (continuing due to invested resources)
- Overconfidence bias (excessive confidence in judgments)
- Group think (conforming to group consensus)
- Recency bias (overweighting recent events)

For each bias detected, provide:
1. Bias type
2. Description of how it manifests
3. Evidence from the text
4. Severity (low/medium/high)
5. Recommendation to mitigate

Respond in JSON format:
[
    {{
        "bias_type": "...",
        "description": "...",
        "evidence": ["...", "..."],
        "severity": "...",
        "recommendation": "..."
    }}
]"""

        try:
            if self.pydantic_ai_agent:
                result = await self.run_with_llm(
                    prompt=prompt,
                    timeout=60,
                )

                import json

                try:
                    start_idx = result.find("[")
                    end_idx = result.rfind("]") + 1
                    if start_idx >= 0 and end_idx > start_idx:
                        json_str = result[start_idx:end_idx]
                        data = json.loads(json_str)

                        for item in data:
                            bias_type_str = item.get("bias_type", "")
                            bias_type = None
                            for bt in self.available_biases:
                                if (
                                    bt.value == bias_type_str
                                    or bt.name.lower() == bias_type_str.lower()
                                ):
                                    bias_type = bt
                                    break

                            if bias_type:
                                biases.append(
                                    BiasDetection(
                                        bias_type=bias_type,
                                        description=item.get("description", ""),
                                        evidence=item.get("evidence", []),
                                        severity=item.get("severity", "medium"),
                                        recommendation=item.get("recommendation"),
                                    )
                                )
                except Exception as e:
                    logger.debug("prism_parse_failed", error=str(e))

            # Fallback: Pattern-based bias detection
            biases.extend(self._heuristic_bias_detection(content))

        except Exception as e:
            logger.warning(f"[{self.agent_id}] LLM bias detection failed: {e}")
            biases.extend(self._heuristic_bias_detection(content))

        return biases

    async def _handle_apply_framework(self, message: ActorMessage) -> None:
        """
        Apply an analytical framework to an issue.

        Args:
            message: Actor message with issue and framework
        """
        try:
            # Validate content
            is_valid, _error = self._validate_analysis_request(message.content)
            if not is_valid:
                logger.error(f"[{self.agent_id}] Invalid framework request: {_error}")
                return

            issue = message.content["issue"]
            framework_str = message.content.get("framework", "first_principles")
            analysis_id = message.content.get(
                "analysis_id", f"framework_{datetime.now(UTC).timestamp()}"
            )

            # Map framework string to enum
            framework = None
            for f in self.available_frameworks:
                if f.value == framework_str or f.name.lower() == framework_str.lower():
                    framework = f
                    break

            if not framework:
                logger.error(f"[{self.agent_id}] Unknown framework: {framework_str}")
                return

            logger.info(f"[{self.agent_id}] Applying framework {framework.value} to issue")

            # Apply framework
            result = await self._apply_framework_to_issue(issue, framework)

            # Store results
            self.framework_results[analysis_id] = {
                "framework": framework.value,
                "issue": issue,
                "result": result,
                "timestamp": datetime.now(UTC).isoformat(),
            }

            # Send response
            response = {
                "message_type": "framework_response",
                "analysis_id": analysis_id,
                "framework": framework.value,
                "result": result,
            }

            if message.content.get("reply_to"):
                await self.send(
                    topic=message.content["reply_to"],
                    content=response,
                    sender_id=self.agent_id,
                )

            logger.info(f"[{self.agent_id}] Framework {framework.value} applied successfully")

        except Exception as e:
            logger.exception(f"[{self.agent_id}] Error applying framework: {e}")

    async def _apply_framework_to_issue(
        self,
        issue: str,
        framework: AnalyticalFramework,
    ) -> dict[str, Any]:
        """
        Apply an analytical framework to an issue.

        Args:
            issue: The issue to analyze
            framework: Framework to apply

        Returns:
            Framework analysis result
        """
        prompt = get_framework_prompt(framework, issue)

        try:
            if self.pydantic_ai_agent:
                result = await self.run_with_llm(
                    prompt=prompt,
                    timeout=60,
                )

                import json

                try:
                    start_idx = result.find("{")
                    end_idx = result.rfind("}") + 1
                    if start_idx >= 0 and end_idx > start_idx:
                        json_str = result[start_idx:end_idx]
                        return json.loads(json_str)
                except Exception as e:
                    logger.debug("prism_json_parse_failed", error=str(e))

            # Fallback
            return apply_framework_fallback(framework)

        except Exception as e:
            logger.warning(f"[{self.agent_id}] Framework application failed: {e}")
            return apply_framework_fallback(framework, str(e))

    async def _handle_map_stakeholders(self, message: ActorMessage) -> None:
        """
        Map stakeholders and their interests for an issue.

        Args:
            message: Actor message with issue details
        """
        try:
            is_valid, _error = self._validate_analysis_request(message.content)
            if not is_valid:
                logger.error(f"[{self.agent_id}] Invalid stakeholder mapping request: {_error}")
                return

            issue = message.content["issue"]
            map_id = message.content.get("map_id", f"stakeholders_{datetime.now(UTC).timestamp()}")

            logger.info(f"[{self.agent_id}] Mapping stakeholders for issue")

            # Generate stakeholder map
            stakeholder_map = await self._generate_stakeholder_map(issue)

            # Store map
            self.stakeholder_maps[map_id] = stakeholder_map

            # Send response
            response = {
                "message_type": "stakeholder_map_response",
                "map_id": map_id,
                "stakeholders": stakeholder_map,
            }

            if message.content.get("reply_to"):
                await self.send(
                    topic=message.content["reply_to"],
                    content=response,
                    sender_id=self.agent_id,
                )

            logger.info(f"[{self.agent_id}] Stakeholder mapping complete")

        except Exception as e:
            logger.exception(f"[{self.agent_id}] Error mapping stakeholders: {e}")

    async def _generate_stakeholder_map(self, issue: str) -> dict[str, Any]:
        """
        Generate a stakeholder map for an issue.

        Args:
            issue: The issue to analyze

        Returns:
            Stakeholder map dictionary
        """
        prompt = f"""Identify all stakeholders for this issue:

ISSUE: {issue}

For each stakeholder, identify:
1. Name/role
2. Interest in the issue
3. Level of influence (low/medium/high)
4. Impact on them (low/medium/high)
5. Their position (supportive/neutral/opposed)

Respond in JSON:
{{
    "stakeholders": [
        {{
            "name": "...",
            "interest": "...",
            "influence": "...",
            "impact": "...",
            "position": "..."
        }}
    ],
    "power_interest_matrix": "...",
    "engagement_strategy": "..."
}}"""

        try:
            if self.pydantic_ai_agent:
                result = await self.run_with_llm(
                    prompt=prompt,
                    timeout=60,
                )

                import json

                try:
                    start_idx = result.find("{")
                    end_idx = result.rfind("}") + 1
                    if start_idx >= 0 and end_idx > start_idx:
                        return json.loads(result[start_idx:end_idx])
                except Exception as e:
                    logger.debug("prism_json_parse_failed", error=str(e))

            # Fallback
            return generate_stakeholder_map_fallback()

        except Exception as e:
            logger.warning(f"[{self.agent_id}] Stakeholder mapping failed: {e}")
            return generate_stakeholder_map_fallback(str(e))

    async def _handle_get_analysis_summary(self, message: ActorMessage) -> None:
        """
        Get summary of all active analyses.

        Args:
            message: Actor message
        """
        try:
            analysis_id = message.content.get("analysis_id", None)

            if analysis_id and analysis_id in self.active_analyses:
                # Return specific analysis
                summary = self.active_analyses[analysis_id]
                perspectives = self.perspective_cache.get(analysis_id, [])
                summary["perspectives"] = [p.to_dict() for p in perspectives]
            else:
                # Return all analyses
                summary = {
                    "active_analyses_count": len(self.active_analyses),
                    "analyses": list(self.active_analyses.values()),
                    "bias_detections_count": len(self.bias_history),
                    "framework_applications_count": len(self.framework_results),
                }

            response = {
                "message_type": "analysis_summary_response",
                "summary": summary,
            }

            if message.content.get("reply_to"):
                await self.send(
                    topic=message.content["reply_to"],
                    content=response,
                    sender_id=self.agent_id,
                )

        except Exception as e:
            logger.exception(f"[{self.agent_id}] Error getting analysis summary: {e}")

    async def _handle_reframe_issue(self, message: ActorMessage) -> None:
        """
        Reframe an issue from multiple angles.

        Args:
            message: Actor message with issue to reframe
        """
        try:
            is_valid, _error = self._validate_analysis_request(message.content)
            if not is_valid:
                logger.error(f"[{self.agent_id}] Invalid reframe request: {_error}")
                return

            issue = message.content["issue"]

            logger.info(f"[{self.agent_id}] Reframing issue")

            # Generate reframes
            reframes = await self._generate_reframes(issue)

            response = {
                "message_type": "reframe_response",
                "original_issue": issue,
                "reframes": reframes,
            }

            if message.content.get("reply_to"):
                await self.send(
                    topic=message.content["reply_to"],
                    content=response,
                    sender_id=self.agent_id,
                )

            logger.info(f"[{self.agent_id}] Issue reframed into {len(reframes)} perspectives")

        except Exception as e:
            logger.exception(f"[{self.agent_id}] Error reframing issue: {e}")

    def get_learning_status(self) -> dict[str, Any]:
        """Get collective learning and memory optimization status with phi_training."""
        base_status = super().get_learning_status()
        base_status["phi_training"] = self.get_phi_training_status()
        return base_status

    # =========================================================================
    # Session 44: Collective Learning Integration
    # Phi Training Integration Methods
    # =========================================================================

    def _prism_agent_actor(self) -> AgentActor:
        """Create an AgentActor wrapper for Prism for Phi training."""

        class PrismAgentActor(AgentActor):
            def __init__(self, prism: "PrismAgent"):
                super().__init__(
                    agent_id=prism.agent_id,
                    agent_type="prism",
                )
                self.prism = prism

            async def act(self, observation: dict[str, Any]) -> dict[str, Any]:
                """Take action based on observation for Phi training."""
                # Use perspective analysis to determine action
                issue = observation.get("issue", "")
                if issue:
                    perspectives = self.prism.perspective_cache.get(issue, [])
                    if perspectives:
                        return {
                            "action": "analyze_perspectives",
                            "perspective_count": len(perspectives),
                            "avg_confidence": sum(p.confidence for p in perspectives)
                            / len(perspectives),
                        }
                return {"action": "monitor"}

            def get_state(self) -> dict[str, Any]:
                """Get current state for Phi calculation."""
                return {
                    "active_analyses": len(self.prism.active_analyses),
                    "perspective_cache_size": len(self.prism.perspective_cache),
                    "bias_history_size": len(self.prism.bias_history),
                    "framework_results_size": len(self.prism.framework_results),
                    "activation": len(self.prism.active_analyses)
                    / max(len(self.prism.available_perspectives), 1),
                }

        return PrismAgentActor(self)

    async def run_phi_training_episode(
        self,
        scenario: TrainingScenario | None = None,
        participating_agents: list[AgentActor] | None = None,
    ) -> dict[str, Any]:
        """
        Run a Phi training episode for Prism.

        Args:
            scenario: Optional training scenario (defaults to decision coherence)
            participating_agents: Optional list of agents to train with

        Returns:
            Training result dictionary
        """
        # Create training environment
        env = PhiTrainingEnvironment()

        # Get agent actors
        agent_actors = participating_agents or [self._prism_agent_actor()]

        # Use default scenario if not provided
        if scenario is None:
            scenario = DecisionCoherenceTrainingScenario(agent_count=len(agent_actors))

        # Run episode
        result = await env.run_episode(agent_actors, scenario)

        logger.info(
            "phi_training_episode_completed",
            agent_id=self.agent_id,
            phi_delta=result.episode.phi_delta,
            success=result.success,
        )

        return result.to_dict()

    def get_phi_training_status(self) -> dict[str, Any]:
        """Get Phi training status and metrics."""
        return {
            "phi_training_enabled": True,
            "agent_type": "prism",
            "training_capability": "decision_coherence",
            "phi_optimization_target": "perspective_integration",
        }

    async def _generate_reframes(self, issue: str) -> list[dict[str, Any]]:
        """
        Generate multiple reframes of an issue.

        Args:
            issue: The issue to reframe

        Returns:
            List of reframes
        """
        prompt = f"""Reframe this issue in multiple ways:

ORIGINAL ISSUE: {issue}

Generate 3-5 alternative framings that:
1. Change the scope (wider/narrower)
2. Change the timeframe (shorter/longer)
3. Change the perspective (different stakeholder)
4. Challenge assumptions
5. Focus on opportunities vs problems

Respond in JSON:
[
    {{
        "reframe": "...",
        "type": "...",
        "insights_revealed": ["...", "..."]
    }}
]"""

        try:
            if self.pydantic_ai_agent:
                result = await self.run_with_llm(
                    prompt=prompt,
                    timeout=60,
                )

                import json

                try:
                    start_idx = result.find("[")
                    end_idx = result.rfind("]") + 1
                    if start_idx >= 0 and end_idx > start_idx:
                        return json.loads(result[start_idx:end_idx])
                except Exception as e:
                    logger.debug("prism_json_parse_failed", error=str(e))

            # Fallback
            return generate_reframe_fallback()

        except Exception as e:
            logger.warning(f"[{self.agent_id}] Reframe generation failed: {e}")
            return []

    # Backward compatibility: alias private methods
    def _heuristic_perspective(
        self,
        issue: str,
        perspective_type: PerspectiveType,
    ) -> Perspective:
        """Alias for backward compatibility."""
        return generate_heuristic_perspective(issue, perspective_type)

    def _heuristic_bias_detection(self, content: str) -> list[BiasDetection]:
        """Alias for backward compatibility."""
        return detect_biases_heuristic(content)
