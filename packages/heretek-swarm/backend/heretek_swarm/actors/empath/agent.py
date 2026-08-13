"""
Empath Agent - Emotional Intelligence & Sentiment Analysis.

The Empath agent provides:
- Sentiment analysis on inputs and communications
- Agent mood tracking and emotional state monitoring
- Conflict de-escalation and emotional mediation
- Emotional context for decision-making
- Stress detection and burnout prevention

Named for the ability to understand and share the feelings of others.
"""

import asyncio
from datetime import UTC, datetime
from typing import Any

import structlog
from pydantic import ValidationError
from heretek_swarm.actors.base import ActorMessage, AgentActor
from heretek_swarm.actors.mixins import (
    DeliberationMixin,
    HealthReportingMixin,
    LearningMixin,
    MemoryMixin,
    PatternMixin,
    ValidationMixin,
)

# Session 44: Zero-Trust Validation
from heretek_swarm_core.security.zero_trust import ZeroTrustValidator
from heretek_swarm_core.validation import validate_message

logger = structlog.get_logger("EmpathAgent")


class EmpathAgent(
    HealthReportingMixin,
    ValidationMixin,
    DeliberationMixin,
    PatternMixin,
    MemoryMixin,
    LearningMixin,
    AgentActor,
):
    """
    Empath Agent - Emotional Intelligence Specialist.

    The Empath is responsible for:
    - Analyzing sentiment in all inter-agent communications
    - Tracking emotional states of agents (mood, stress, confidence)
    - Detecting conflicts and initiating de-escalation protocols
    - Providing emotional context to Triad deliberations
    - Monitoring collective emotional health of the swarm

    Emotional Intelligence Workflow:
    1. Receive message or communication
    2. Analyze sentiment (positive/negative/neutral + intensity)
    3. Update agent emotional state
    4. Detect conflicts or stress patterns
    5. Trigger interventions if needed
    6. Log emotional metrics for observability
    """

    def __init__(
        self,
        agent_id: str = "empath",
        name: str = "Empath",
        description: str = "Emotional intelligence and sentiment analysis specialist",
        sentiment_threshold: float = 0.7,
        stress_threshold: float = 0.8,
        max_mood_history: int = 100,
        _pattern_extractor: Any | None = None,
        _deliberation_engine: Any | None = None,
        _access_analyzer: Any | None = None,
        zero_trust_validator: ZeroTrustValidator | None = None,
        **kwargs,
    ) -> None:
        """
        Initialize the Empath agent.

        Args:
            agent_id: Unique identifier
            name: Human-readable name
            description: Agent description
            sentiment_threshold: Threshold for flagging strong sentiments (0-1)
            stress_threshold: Threshold for stress alerts (0-1)
            max_mood_history: Maximum mood history entries per agent
            **kwargs: Additional arguments
        """
        super().__init__(
            agent_id=agent_id,
            name=name,
            description=description,
            topics=[
                "sentiment",
                "emotions",
                "conflict-resolution",
                "agent-health",
            ],
            capabilities=[
                "sentiment-analysis",
                "emotion-detection",
                "conflict-mediation",
                "stress-monitoring",
                "emotional-context",
            ],
            **kwargs,
        )

        # Empath-specific state
        self.sentiment_threshold = sentiment_threshold
        self.stress_threshold = stress_threshold
        self.max_mood_history = max_mood_history

        # Agent emotional states
        self.agent_moods: dict[str, list[dict[str, Any]]] = {}
        self.agent_stress_levels: dict[str, float] = {}
        self.agent_confidence: dict[str, float] = {}
        self.conflict_log: list[dict[str, Any]] = []
        self.sentiment_history: list[dict[str, Any]] = []
        # Aliases for test compatibility
        self._agent_emotions: dict[str, Any] = {}
        self._sentiment_log: list[dict[str, Any]] = self.sentiment_history

        # Aggregate emotional metrics
        self.collective_mood: dict[str, float] = {
            "positive": 0.5,
            "negative": 0.1,
            "neutral": 0.4,
        }
        self.collective_stress: float = 0.0

        # Aliases for test compatibility
        self._conflict_history: list[dict[str, Any]] = self.conflict_log
        self._collective_mood: dict[str, float] = self.collective_mood

        # Session 44: Collective Learning Integration (provided by LearningMixin)
        # Session 44: Consensus Integration (provided by DeliberationMixin)
        # Session 44: Memory Optimization Integration (provided by MemoryMixin)

        # Session 44: Zero-Trust Validation
        self.zero_trust_validator = zero_trust_validator or ZeroTrustValidator()

        # Session 44: Integration state
        self._active_deliberations: dict[str, str] = {}
        self._pattern_emitted: set[str] = set()

        # Session 44: Collective Learning Integration - initialize pattern extractor
        from heretek_swarm.collective.learning import PatternExtractor

        self.pattern_extractor = _pattern_extractor or PatternExtractor(min_support=3, min_confidence=0.6)

        # Session 44: Consensus Integration - initialize deliberation engine
        from heretek_swarm_core.consensus.swarm_deliberation import SwarmDeliberationEngine

        self.deliberation_engine = _deliberation_engine or SwarmDeliberationEngine(
            max_rounds=5, consensus_threshold=0.75, min_participants=2
        )

        # Session 44: Memory Optimization Integration - initialize access analyzer
        from heretek_swarm_core.memory.access_patterns import AccessPatternAnalyzer

        self.access_analyzer = _access_analyzer or AccessPatternAnalyzer()

        logger.info(f"[{self.agent_id}] Empath agent initialized")

    async def initialize(self) -> None:
        """Initialize the Empath agent."""
        # Register message handlers with Zero-Trust validation
        self.register_handler("analyze_sentiment", self._handle_analyze_sentiment)
        self.register_handler("track_emotion", self._handle_track_emotion)
        self.register_handler("detect_conflict", self._handle_detect_conflict)
        self.register_handler("get_emotional_state", self._handle_get_emotional_state)
        self.register_handler("mediate_conflict", self._handle_mediate_conflict)
        self.register_handler("get_collective_mood", self._handle_get_collective_mood)
        self.register_handler("on_demand_sentiment", self._handle_on_demand_sentiment)

        logger.info(f"[{self.agent_id}] Empath initialization complete")

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
                # Send error response if reply_to is specified
                if message.content.get("reply_to"):
                    await self.send(
                        topic=message.content["reply_to"],
                        content={
                            "message_type": "error_response",
                            "error": str(e),
                            "original_message_type": message.message_type,
                        },
                        correlation_id=message.correlation_id,
                    )
        else:
            logger.warning(f"[{self.agent_id}] No handler for message type: {message.message_type}")

    def _validate_message_content(self, message_type: str, content: dict[str, Any]) -> Any:
        """
        Validate message content using Pydantic models.

        Args:
            message_type: Type of message
            content: Message content to validate

        Returns:
            Validated content or None if no validator exists
        """
        try:
            return validate_message(message_type, content)
        except ValidationError as e:
            logger.warning(
                f"[{self.agent_id}] Message validation failed for {message_type}: {e}",
                extra={"validation_errors": e.errors()},
            )
            raise ValueError(f"Invalid message format: {e.errors()}") from e
        except KeyError:
            # Unknown message type - skip validation
            logger.debug(f"[{self.agent_id}] No validator for message type: {message_type}")
            return None

    async def _handle_analyze_sentiment(self, message: ActorMessage) -> None:
        """
        Analyze sentiment of text content.

        Args:
            message: ActorMessage with content containing:
                - text: Text to analyze
                - source_agent: ID of the source agent
                - context: Optional context (message type, topic, etc.)

        Response:
            - sentiment: positive/negative/neutral
            - confidence: 0-1 confidence score
            - intensity: 0-1 emotional intensity
            - emotions: List of detected emotions
        """
        try:
            # Zero-Trust input validation
            validated = self._validate_message_content("analyze_sentiment", message.content)
            content = (
                validated.content
                if hasattr(validated, "content")
                else (validated.to_dict().get("content") if hasattr(validated, "to_dict") else message.content)
            )

            text = content.get("text", "")
            source_agent = content.get("source_agent", "unknown")
            context = content.get("context", {})

            if not text:
                logger.warning(f"[{self.agent_id}] Empty text for sentiment analysis")
                await self._send_error_response(message, "Empty text provided")
                return

            # Perform sentiment analysis
            sentiment_result = await self._analyze_sentiment_llm(text, source_agent, context)

            # Update agent mood history
            self._update_agent_mood(source_agent, sentiment_result)

            # Check for stress indicators
            self._check_stress_indicators(source_agent, sentiment_result)

            # Log sentiment for observability
            self._log_sentiment(source_agent, sentiment_result)

            # Send response
            await self.send(
                topic=message.content.get("reply_to", f"actor:{source_agent}"),
                content={
                    "message_type": "sentiment_result",
                    "text": text[:100],  # Truncate for logging
                    **sentiment_result,
                },
                correlation_id=message.correlation_id,
            )

            logger.debug(
                f"[{self.agent_id}] Sentiment analyzed for {source_agent}",
                extra={"sentiment": sentiment_result["sentiment"]},
            )

        except Exception as e:
            logger.exception(f"[{self.agent_id}] Sentiment analysis failed: {e}")
            await self._send_error_response(message, f"Sentiment analysis failed: {e}")

    async def _analyze_sentiment_llm(
        self, text: str, source_agent: str | None = None, context: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        context = context or {}
        """
        Analyze sentiment using LLM if available, otherwise use heuristic analysis.

        Args:
            text: Text to analyze
            source_agent: Source agent ID
            context: Additional context

        Returns:
            Sentiment analysis result dict
        """
        try:
            if self.pydantic_ai_agent:
                # Use LLM for sophisticated sentiment analysis
                prompt = self._build_sentiment_prompt(text, context)
                response = await asyncio.wait_for(
                    self.pydantic_ai_agent.run(prompt),
                    timeout=60,  # P1-2: LLM timeout
                )
                return self._parse_sentiment_response(response)
            # Fallback to heuristic analysis
            return self._analyze_sentiment_heuristic(text)

        except TimeoutError:
            logger.warning(f"[{self.agent_id}] LLM sentiment analysis timed out")
            return self._analyze_sentiment_heuristic(text)
        except Exception as e:
            logger.error(f"[{self.agent_id}] LLM sentiment analysis error: {e}")
            return self._analyze_sentiment_heuristic(text)

    def _build_sentiment_prompt(self, text: str, context: dict[str, Any]) -> str:
        """Build prompt for LLM sentiment analysis."""
        context_str = f"Context: {context}\n" if context else ""
        return f"""
Analyze the sentiment of the following text. Consider the emotional tone,
intensity, and any underlying emotions.

{context_str}
Text: {text}

Provide your analysis in this exact JSON format:
{{
    "sentiment": "positive|negative|neutral",
    "confidence": 0.0-1.0,
    "intensity": 0.0-1.0,
    "emotions": ["emotion1", "emotion2"],
    "stress_indicators": true|false,
    "conflict_potential": true|false
}}
"""

    def _parse_sentiment_response(self, response: str) -> dict[str, Any]:
        """Parse LLM response into sentiment result."""
        import json
        import re

        try:
            # Extract JSON from response
            json_match = re.search(r"\{.*\}", response, re.DOTALL)
            if json_match:
                return json.loads(json_match.group())
        except Exception as e:
            logger.warning(f"[{self.agent_id}] Failed to parse LLM sentiment response: {e}")

        # Fallback to heuristic analysis
        return self._analyze_sentiment_heuristic(response)

    def _analyze_sentiment_heuristic(self, text: str) -> dict[str, Any]:
        """
        Analyze sentiment using heuristic rules.

        This is a fallback when LLM is unavailable.
        """
        text_lower = text.lower()

        # Simple positive/negative word lists
        positive_words = {
            "good",
            "great",
            "excellent",
            "positive",
            "success",
            "happy",
            "confident",
            "sure",
            "certain",
            "agree",
            "support",
            "help",
            "thanks",
            "thank",
            "appreciate",
            "wonderful",
            "amazing",
        }
        negative_words = {
            "bad",
            "terrible",
            "awful",
            "negative",
            "fail",
            "error",
            "wrong",
            "disagree",
            "reject",
            "problem",
            "issue",
            "stress",
            "angry",
            "frustrat",
            "worried",
            "concern",
            "unfortunately",
        }
        stress_words = {
            "urgent",
            "asap",
            "immediately",
            "stress",
            "panic",
            "crisis",
            "emergency",
            "deadline",
            "overwhelm",
            "burnout",
            "pressure",
        }
        conflict_words = {
            "disagree",
            "conflict",
            "argue",
            "fight",
            "oppose",
            "against",
            "wrong",
            "reject",
            "deny",
            "accuse",
            "blame",
        }

        # Count matches
        positive_count = sum(1 for word in positive_words if word in text_lower)
        negative_count = sum(1 for word in negative_words if word in text_lower)
        stress_count = sum(1 for word in stress_words if word in text_lower)
        conflict_count = sum(1 for word in conflict_words if word in text_lower)

        # Calculate sentiment
        total = positive_count + negative_count + 1  # +1 to avoid division by zero
        positive_score = positive_count / total
        negative_score = negative_count / total

        if positive_score > negative_score + 0.2:
            sentiment = "positive"
        elif negative_score > positive_score + 0.2:
            sentiment = "negative"
        else:
            sentiment = "neutral"

        # Detect emotions
        emotions = []
        if "angry" in text_lower or "frustrat" in text_lower:
            emotions.append("anger")
        if "worried" in text_lower or "concern" in text_lower:
            emotions.append("anxiety")
        if "happy" in text_lower or "great" in text_lower:
            emotions.append("joy")
        if "sad" in text_lower or "disappoint" in text_lower:
            emotions.append("sadness")
        if "sure" in text_lower or "confident" in text_lower:
            emotions.append("confidence")

        return {
            "sentiment": sentiment,
            "confidence": min(0.9, 0.5 + (max(positive_count, negative_count) * 0.1)),
            "intensity": min(1.0, (positive_count + negative_count) * 0.15),
            "emotions": emotions if emotions else ["neutral"],
            "stress_indicators": stress_count > 0,
            "conflict_potential": conflict_count > 0,
        }

    def _update_agent_mood(self, agent_id: str, sentiment_result: dict[str, Any]) -> None:
        """Update agent's mood history with new sentiment data."""
        if agent_id not in self.agent_moods:
            self.agent_moods[agent_id] = []

        # Get emotions from sentiment_result
        emotions_list = sentiment_result.get("emotions", [])
        if "emotion" in sentiment_result and not emotions_list:
            emotions_list = [sentiment_result["emotion"]]

        mood_entry = {
            "timestamp": datetime.now(UTC).isoformat(),
            "sentiment": sentiment_result.get("sentiment", "neutral"),
            "intensity": sentiment_result.get("intensity", sentiment_result.get("arousal", 0.5)),
            "emotions": emotions_list if emotions_list else ["neutral"],
        }

        self.agent_moods[agent_id].append(mood_entry)

        # Enforce max history size (P1-3 pattern)
        if len(self.agent_moods[agent_id]) > self.max_mood_history:
            self.agent_moods[agent_id] = self.agent_moods[agent_id][-self.max_mood_history :]

        # Preserve existing fields in _agent_emotions while updating with new data
        existing = self._agent_emotions.get(agent_id, {})
        self._agent_emotions[agent_id] = {**existing, **mood_entry, **sentiment_result}

    def _check_stress_indicators(self, agent_id: str, sentiment_result: dict[str, Any] | None = None) -> float:
        """Check for stress indicators and update stress levels. Returns current stress level."""
        if sentiment_result is not None:
            # Update stress level based on sentiment
            if sentiment_result.get("stress_indicators", False):
                self.agent_stress_levels[agent_id] = min(1.0, self.agent_stress_levels.get(agent_id, 0.0) + 0.1)
            else:
                # Gradually decrease stress over time
                self.agent_stress_levels[agent_id] = max(0.0, self.agent_stress_levels.get(agent_id, 0.0) - 0.05)
        else:
            # Compute stress from stored emotional state if no sentiment_result provided
            emotions = self._agent_emotions.get(agent_id, {})
            arousal = emotions.get("arousal", 0.0)
            valence = emotions.get("valence", 0.5)
            # Low valence + high arousal = high stress
            computed = max(0.0, arousal - valence + 0.5) if (arousal or valence != 0.5) else 0.0
            if computed > 0:
                self.agent_stress_levels[agent_id] = min(1.0, computed)

        stress_level = self.agent_stress_levels.get(agent_id, 0.0)

        # Check for high stress alert
        if stress_level > self.stress_threshold:
            logger.warning(
                f"[{self.agent_id}] High stress detected for agent {agent_id}",
                extra={"stress_level": stress_level},
            )

        return stress_level

    def _log_sentiment(self, agent_id: str, sentiment_result: dict[str, Any]) -> None:
        """Log sentiment for observability and analysis."""
        self.sentiment_history.append(
            {
                "timestamp": datetime.now(UTC).isoformat(),
                "agent_id": agent_id,
                **sentiment_result,
            }
        )

        # Limit history size
        if len(self.sentiment_history) > 1000:
            self.sentiment_history = self.sentiment_history[-1000:]

    async def _handle_track_emotion(self, message: ActorMessage) -> None:
        """
        Track emotional state for an agent.

        Args:
            message: ActorMessage with content containing:
                - agent_id: Agent to track
                - emotion: Emotion to record
                - intensity: Optional intensity (0-1)
        """
        try:
            content = message.content
            agent_id = content.get("agent_id")
            emotion = content.get("emotion")
            intensity = content.get("intensity", 0.5)

            if not agent_id or not emotion:
                await self._send_error_response(message, "Missing required fields: agent_id, emotion")
                return

            self._update_agent_mood(
                agent_id,
                {
                    "sentiment": "neutral",
                    "intensity": intensity,
                    "emotion": emotion,  # Include singular emotion for compatibility
                    "emotions": [emotion],
                    "valence": 0.5,  # Default valence
                    "arousal": intensity,  # Use intensity as arousal
                    "stress_indicators": False,
                    "conflict_potential": False,
                },
            )

            logger.debug(f"[{self.agent_id}] Emotion tracked for {agent_id}: {emotion}")

        except Exception as e:
            logger.exception(f"[{self.agent_id}] Emotion tracking failed: {e}")
            await self._send_error_response(message, f"Emotion tracking failed: {e}")

    async def _handle_detect_conflict(self, message: ActorMessage) -> None:
        """
        Detect potential conflicts between agents.

        Args:
            message: ActorMessage with content containing:
                - agents: List of agent IDs involved
                - context: Description of the situation
        """
        try:
            content = message.content
            agents = content.get("agents", [])
            context = content.get("context", "")

            if len(agents) < 2:
                await self._send_error_response(message, "Conflict detection requires at least 2 agents")
                return

            # Analyze recent interactions between agents
            conflict_detected = self._analyze_conflict_potential(agents)

            if conflict_detected:
                # Log conflict
                self.conflict_log.append(
                    {
                        "timestamp": datetime.now(UTC).isoformat(),
                        "agents": agents,
                        "context": context,
                        "status": "detected",
                    }
                )

                # Alert steward for mediation
                await self.send(
                    topic="actor:steward",
                    content={
                        "message_type": "conflict_alert",
                        "agents": agents,
                        "context": context,
                    },
                )

            # Send response
            await self.send(
                topic=message.content.get("reply_to", f"actor:{agents[0]}"),
                content={
                    "message_type": "conflict_result",
                    "conflict_detected": conflict_detected,
                    "agents": agents,
                },
                correlation_id=message.correlation_id,
            )

        except Exception as e:
            logger.exception(f"[{self.agent_id}] Conflict detection failed: {e}")
            await self._send_error_response(message, f"Conflict detection failed: {e}")

    def _analyze_conflict_potential(self, agents: list[str]) -> bool:
        """Analyze potential for conflict between agents."""
        if self._has_sentiment_divergence(agents):
            return True
        return self._has_high_stress(agents)

    def _has_sentiment_divergence(self, agents: list[str]) -> bool:
        """Check for significant sentiment divergence between agents."""
        recent_sentiments = {}
        for agent_id in agents:
            moods = self.agent_moods.get(agent_id, [])[-10:]
            if moods:
                avg_sentiment = sum(
                    1 if m["sentiment"] == "positive" else -1 if m["sentiment"] == "negative" else 0 for m in moods
                ) / len(moods)
                recent_sentiments[agent_id] = avg_sentiment
        if len(recent_sentiments) >= 2:
            values = list(recent_sentiments.values())
            if max(values) - min(values) > 1.5:
                return True
        return False

    def _has_high_stress(self, agents: list[str]) -> bool:
        """Check if any agent exceeds the stress threshold."""
        return any(self.agent_stress_levels.get(aid, 0.0) > self.stress_threshold for aid in agents)

    async def _handle_get_emotional_state(self, message: ActorMessage) -> None:
        """
        Get current emotional state for an agent or all agents.

        Args:
            message: ActorMessage with optional agent_id
        """
        try:
            agent_id = message.content.get("agent_id")

            if agent_id:
                # Get specific agent state
                moods = self.agent_moods.get(agent_id, [])
                recent_mood = moods[-1] if moods else None
                stress = self.agent_stress_levels.get(agent_id, 0.0)
                confidence = self.agent_confidence.get(agent_id, 0.5)

                result = {
                    "agent_id": agent_id,
                    "current_mood": recent_mood,
                    "stress_level": stress,
                    "confidence": confidence,
                    "mood_history_size": len(moods),
                }
            else:
                # Get aggregate state
                result = {
                    "collective_mood": self.collective_mood.copy(),
                    "collective_stress": self.collective_stress,
                    "agent_count": len(self.agent_moods),
                    "high_stress_agents": [
                        aid for aid, stress in self.agent_stress_levels.items() if stress > self.stress_threshold
                    ],
                }

            await self.send(
                topic=message.content.get("reply_to", "actor:*"),
                content={
                    "message_type": "emotional_state_result",
                    **result,
                },
                correlation_id=message.correlation_id,
            )

        except Exception as e:
            logger.exception(f"[{self.agent_id}] Emotional state query failed: {e}")
            await self._send_error_response(message, f"Emotional state query failed: {e}")

    async def _handle_mediate_conflict(self, message: ActorMessage) -> None:
        """
        Mediate conflict between agents.

        Args:
            message: ActorMessage with content containing:
                - conflict_id: ID of conflict to mediate
                - agents: List of agent IDs
                - proposed_resolution: Optional proposed solution
        """
        try:
            content = message.content
            agents = content.get("agents", [])
            proposed_resolution = content.get("proposed_resolution")

            if len(agents) < 2:
                await self._send_error_response(message, "Mediation requires at least 2 agents")
                return

            # Generate mediation suggestions using LLM if available
            mediation_result = await self._generate_mediation(agents, proposed_resolution)

            # Send mediation suggestions to all involved agents
            for agent_id in agents:
                await self.send(
                    topic=f"actor:{agent_id}",
                    content={
                        "message_type": "mediation_suggestion",
                        "agents": agents,
                        **mediation_result,
                    },
                )

            # Log mediation attempt
            self.conflict_log.append(
                {
                    "timestamp": datetime.now(UTC).isoformat(),
                    "agents": agents,
                    "status": "mediated",
                    "result": mediation_result,
                }
            )

            await self.send(
                topic=message.content.get("reply_to"),
                content={
                    "message_type": "mediation_result",
                    "agents": agents,
                    **mediation_result,
                },
                correlation_id=message.correlation_id,
            )

        except Exception as e:
            logger.exception(f"[{self.agent_id}] Conflict mediation failed: {e}")
            await self._send_error_response(message, f"Mediation failed: {e}")

    async def _generate_mediation(self, agents: list[str], proposed_resolution: str | None) -> dict[str, Any]:
        """Generate mediation suggestions."""
        try:
            if self.pydantic_ai_agent:
                prompt = f"""
Generate a fair mediation suggestion for a conflict between these agents: {agents}.

{"Proposed resolution: " + proposed_resolution if proposed_resolution else ""}

Provide a balanced resolution that considers all perspectives.
Return as JSON: {{"resolution": "...", "reasoning": "..."}}
"""
                response = await asyncio.wait_for(
                    self.pydantic_ai_agent.run(prompt),
                    timeout=60,
                )
                import json
                import re

                json_match = re.search(r"\{.*\}", response, re.DOTALL)
                if json_match:
                    return json.loads(json_match.group())
        except Exception as e:
            logger.warning(f"[{self.agent_id}] LLM mediation failed: {e}")

        # Fallback mediation
        return {
            "resolution": "Consider taking a break and revisiting this discussion later.",
            "reasoning": "High stress or conflicting sentiments detected. Cooling-off period recommended.",
        }

    async def _handle_get_collective_mood(self, message: ActorMessage) -> None:
        """
        Get the collective mood of the swarm.

        Args:
            message: ActorMessage
        """
        try:
            # Calculate collective metrics
            self._update_collective_mood()

            await self.send(
                topic=message.content.get("reply_to"),
                content={
                    "message_type": "collective_mood_result",
                    "collective_mood": self.collective_mood,
                    "collective_stress": self.collective_stress,
                    "total_agents": len(self.agent_moods),
                    "timestamp": datetime.now(UTC).isoformat(),
                },
                correlation_id=message.correlation_id,
            )

        except Exception as e:
            logger.exception(f"[{self.agent_id}] Collective mood query failed: {e}")
            await self._send_error_response(message, f"Collective mood query failed: {e}")

    def _update_collective_mood(self) -> None:
        """Update aggregate collective mood metrics."""
        if not self.agent_moods:
            return

        # Average sentiment across all agents
        all_moods = []
        for moods in self.agent_moods.values():
            all_moods.extend(moods[-5:])  # Last 5 entries per agent

        if all_moods:
            positive = sum(1 for m in all_moods if m["sentiment"] == "positive")
            negative = sum(1 for m in all_moods if m["sentiment"] == "negative")
            neutral = sum(1 for m in all_moods if m["sentiment"] == "neutral")
            total = len(all_moods)

            self.collective_mood = {
                "positive": positive / total,
                "negative": negative / total,
                "neutral": neutral / total,
            }

        # Average stress
        if self.agent_stress_levels:
            self.collective_stress = sum(self.agent_stress_levels.values()) / len(self.agent_stress_levels)

    # =========================================================================
    # Session 44: Collective Learning, Deliberation, and Memory Integration
    # Provided by DeliberationMixin, PatternMixin, MemoryMixin, LearningMixin
    # =========================================================================

    async def _perform_sentiment(
        self,
        text: str,
        source_agent: str | None = None,
    ) -> dict[str, Any]:
        """
        Perform a lightweight on-demand sentiment analysis.

        Uses run_with_llm() for consistent timeout/error handling with
        the rest of the codebase.  Falls back to a degraded result on
        LLM failure.

        Args:
            text: The text to analyze
            source_agent: Optional source agent identifier

        Returns:
            Dict with keys:
            - sentiment (str): "positive", "negative", or "neutral"
            - tone (str): Descriptive tone label (e.g. "confident",
                          "concerned", "assertive")
            - confidence (float): Confidence score 0-1
        """
        prompt = f"""
On-Demand Sentiment Analysis Request:

Text: {text}
{f"Source: {source_agent}" if source_agent else ""}

Analyze the sentiment and tone of the above text. Provide:
1. Overall sentiment (positive, negative, or neutral)
2. Dominant tone (e.g. confident, concerned, urgent, assertive,
   supportive, doubtful)
3. Confidence in your assessment (0-1)

Format your response as a clear analysis with these three elements.
"""
        try:
            response = await self.run_with_llm(
                prompt=prompt,
                system_prompt=(
                    "You are Empath, an emotional intelligence and sentiment "
                    "analysis specialist. Provide concise, accurate sentiment "
                    "analysis."
                ),
                timeout=60,
            )

            # Extract sentiment and tone from the response (simplified).
            # In production, this would use structured output parsing.
            response_lower = (response or "").lower()

            # Determine overall sentiment from response text
            if any(w in response_lower for w in ["positive", "optimistic", "supportive"]):
                sentiment = "positive"
            elif any(w in response_lower for w in ["negative", "pessimistic", "hostile"]):
                sentiment = "negative"
            else:
                sentiment = "neutral"

            # Simple tone extraction
            tone = "neutral"
            tone_keywords = {
                "confident": "confident",
                "concern": "concerned",
                "urgent": "urgent",
                "assertive": "assertive",
                "supportive": "supportive",
                "doubt": "doubtful",
                "hopeful": "hopeful",
                "critical": "critical",
            }
            for keyword, label in tone_keywords.items():
                if keyword in response_lower:
                    tone = label
                    break

            return {
                "sentiment": sentiment,
                "tone": tone,
                "confidence": 0.8,
            }

        except TimeoutError:
            logger.warning(
                f"[{self.agent_id}] On-demand sentiment analysis timed out",
                extra={"text_preview": text[:60]},
            )
            return {
                "sentiment": "neutral",
                "tone": "unknown",
                "confidence": 0.0,
            }

        except Exception as e:
            logger.exception(
                f"[{self.agent_id}] On-demand sentiment analysis failed: {e}",
            )
            return {
                "sentiment": "neutral",
                "tone": "unknown",
                "confidence": 0.0,
            }

    async def _handle_on_demand_sentiment(self, message: ActorMessage) -> None:
        """
        Handle on-demand sentiment analysis requests.

        Expected message.content keys:
        - text (str): Text to analyze for sentiment
        - source_agent (str, optional): ID of the source agent

        Responds with:
        - message_type: "on_demand_sentiment_response"
        - sentiment (str): "positive", "negative", or "neutral"
        - tone (str): Descriptive tone label
        - confidence (float): Confidence score 0-1
        - collective_stress (float): Average stress level across all tracked
          agents, computed by _update_collective_mood()
        - source_agent (str): The source agent that triggered the analysis
        """
        text = message.content.get("text", "")
        source_agent = message.content.get("source_agent", "unknown")

        if not text:
            logger.warning(f"[{self.agent_id}] on_demand_sentiment called with empty text")
            if message.content.get("reply_to"):
                await self.send(
                    topic=message.content["reply_to"],
                    content={
                        "message_type": "error_response",
                        "error": "Empty text provided",
                        "original_message_type": "on_demand_sentiment",
                    },
                    correlation_id=message.correlation_id,
                )
            return

        logger.info(
            f"[{self.agent_id}] Performing on-demand sentiment analysis",
            extra={
                "text_preview": text[:80],
                "source_agent": source_agent,
            },
        )

        result = await self._perform_sentiment(
            text=text,
            source_agent=source_agent,
        )

        # Integrate text analysis into stress tracking
        self._check_stress_indicators(source_agent, result)

        # Refresh collective stress metrics
        self._update_collective_mood()

        if message.content.get("reply_to"):
            await self.send(
                topic=message.content["reply_to"],
                content={
                    "message_type": "on_demand_sentiment_response",
                    "sentiment": result["sentiment"],
                    "tone": result["tone"],
                    "confidence": result["confidence"],
                    "collective_stress": self.collective_stress,
                    "source_agent": source_agent,
                },
                correlation_id=message.correlation_id,
            )

        logger.info(
            f"[{self.agent_id}] On-demand sentiment analysis complete",
            extra={
                "sentiment": result["sentiment"],
                "confidence": result["confidence"],
                "collective_stress": self.collective_stress,
                "source_agent": source_agent,
            },
        )

    async def _send_error_response(self, message: ActorMessage, error: str) -> None:
        """Send error response."""
        if message.content.get("reply_to"):
            await self.send(
                topic=message.content["reply_to"],
                content={
                    "message_type": "error_response",
                    "error": error,
                    "original_message_type": message.message_type,
                },
                correlation_id=message.correlation_id,
            )
