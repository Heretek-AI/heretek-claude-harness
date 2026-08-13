"""
Perceiver+ Agent - Advanced Analytics Specialist.

The PerceiverPlusAgent provides:
- Advanced multi-modal analytics and pattern recognition
- Deep feature extraction and correlation analysis
- Predictive modeling and trend forecasting
- Statistical analysis and significance testing
- Enhanced signal processing and noise reduction

Author: Heretek Swarm Collective
Date: 2026-04-17
Version: 1.0.0
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

import structlog

from heretek_swarm.actors.base import ActorMessage, AgentActor
from heretek_swarm.actors.mixins import (
    DeliberationMixin,
    LearningMixin,
    MemoryMixin,
    PatternMixin,
    ValidationMixin,
)
from heretek_swarm.actors.perceiver_plus.analytics import PerceiverAnalyticsMixinImpl
from heretek_swarm.actors.perceiver_plus.types import (
    AnalyticsResult,
    AnalyticsType,
    CorrelationMatrix,
    TrendAnalysis,
)

# Session 44: Collective Learning Integration
from heretek_swarm.collective.learning import PatternType

# Session 44: Consensus Integration
from heretek_swarm.knowledge.unified_access import KnowledgeQueryResult, UnifiedKnowledgeAccess

if TYPE_CHECKING:
    from swarms import Agent

    from heretek_swarm.consensus.swarm_deliberation import Position

logger = structlog.get_logger("PerceiverPlusAgent")


class PerceiverPlusAgent(
    ValidationMixin,
    DeliberationMixin,
    PatternMixin,
    MemoryMixin,
    LearningMixin,
    PerceiverAnalyticsMixinImpl,
    AgentActor,
):
    """
    Perceiver+ Agent - Advanced Analytics Specialist.

    The Perceiver+ is responsible for:
    - Advanced multi-modal analytics and pattern recognition
    - Deep feature extraction and correlation analysis
    - Predictive modeling and trend forecasting
    - Statistical analysis and significance testing
    - Enhanced signal processing and noise reduction

    Enhanced Analytics Workflow:
    1. Receive data for analysis
    2. Detect data modalities and quality
    3. Apply appropriate analytical methods
    4. Extract deep features and patterns
    5. Generate predictions and forecasts
    6. Provide actionable recommendations
    """

    def __init__(
        self,
        agent_id: str = "perceiver-plus",
        name: str = "Perceiver+",
        description: str = "Advanced analytics and enhanced perception specialist",
        swarms_agent: Agent | None = None,
        max_analyses: int = 100,
        confidence_threshold: float = 0.7,
        significance_level: float = 0.05,
        pattern_extractor=None,
        deliberation_engine=None,
        access_analyzer=None,
        zero_trust_validator=None,
        **kwargs,
    ) -> None:
        """
        Initialize the Perceiver+ agent.

        Args:
            agent_id: Unique identifier
            name: Human-readable name
            description: Agent description
            swarms_agent: Optional Swarms Agent for LLM capabilities
            max_analyses: Maximum analyses to store
            confidence_threshold: Minimum confidence for reporting
            significance_level: Statistical significance threshold
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
                "analytics",
                "statistics",
                "prediction",
                "patterns",
                "insights",
            ],
            capabilities=[
                "advanced-analytics",
                "predictive-modeling",
                "statistical-analysis",
                "correlation-detection",
                "trend-forecasting",
                "signal-processing",
            ],
            swarms_agent=swarms_agent,
            pattern_extractor=pattern_extractor,
            deliberation_engine=deliberation_engine,
            access_analyzer=access_analyzer,
            zero_trust_validator=zero_trust_validator,
            **kwargs,
        )

        # Perceiver+ specific state
        self.max_analyses = max_analyses
        self.confidence_threshold = confidence_threshold
        self.significance_level = significance_level

        # Analytics storage
        self.analysis_results: dict[str, AnalyticsResult] = {}
        self.trend_analyses: dict[str, TrendAnalysis] = {}
        self.correlation_matrices: dict[str, CorrelationMatrix] = {}
        self.feature_cache: dict[str, dict[str, Any]] = {}

        # Statistical computation state
        self.data_buffers: dict[str, list[float]] = {}
        self.categorical_buffers: dict[str, list[str]] = {}

        # Session 44: Integration state
        self._active_deliberations: dict[str, str] = {}
        self._pattern_emitted: set[str] = set()

        logger.info(f"[{self.agent_id}] Perceiver+ agent initialized")

    async def initialize(self) -> None:
        """Initialize the Perceiver+ agent."""
        # Initialize unified knowledge access layer
        memory_system = getattr(self, "memory_system", None)
        rag_pipeline = getattr(self, "rag_pipeline", None)
        if memory_system or rag_pipeline:
            self.knowledge_access = UnifiedKnowledgeAccess(
                memory_system=memory_system,
                rag_pipeline=rag_pipeline,
            )
            logger.info(f"[{self.agent_id}] Unified knowledge access initialized")

        # Register message handlers with Zero-Trust validation
        self.register_handler("analyze_data", self._handle_analyze_data)
        self.register_handler("detect_trends", self._handle_detect_trends)
        self.register_handler("compute_correlations", self._handle_compute_correlations)
        self.register_handler("run_statistical_test", self._handle_run_statistical_test)
        self.register_handler("extract_features", self._handle_extract_features)
        self.register_handler("forecast_values", self._handle_forecast_values)
        self.register_handler("get_analytics_summary", self._handle_get_analytics_summary)
        self.register_handler("signal_processing", self._handle_signal_processing)
        self.register_handler(
            "knowledge_enhanced_analysis", self._handle_knowledge_enhanced_analysis
        )

        logger.info(f"[{self.agent_id}] Perceiver+ initialization complete")

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

    async def _handle_analyze_data(self, message: ActorMessage) -> None:
        """
        Perform comprehensive data analysis.

        Args:
            message: Actor message with data for analysis
        """
        try:
            # Validate content
            is_valid, _error = self._validate_data_input(message.content)
            if not is_valid:
                logger.error(f"[{self.agent_id}] Invalid data analysis request: {_error}")
                return

            data = message.content["data"]
            analysis_id = message.content.get(
                "analysis_id", f"analysis_{datetime.now(UTC).timestamp()}"
            )
            analytics_types = message.content.get("analytics_types", ["descriptive"])

            logger.info(f"[{self.agent_id}] Performing comprehensive analysis: {analysis_id}")

            # Perform analyses in parallel — each analysis is independent
            async def _run_one(atype: str) -> Any:
                try:
                    atype_enum = AnalyticsType(atype)
                    result = await self._perform_analysis(data, atype_enum, analysis_id)
                    return result if result.confidence >= self.confidence_threshold else None
                except ValueError:
                    logger.warning(f"[{self.agent_id}] Unknown analytics type: {atype}")
                    return None

            gathered = await asyncio.gather(
                *(_run_one(a) for a in analytics_types),
                return_exceptions=False,
            )
            results = [r for r in gathered if r is not None]

            # Store results
            for result in results:
                if len(self.analysis_results) >= self.max_analyses:
                    oldest_id = next(iter(self.analysis_results.keys()))
                    del self.analysis_results[oldest_id]
                self.analysis_results[result.analysis_id] = result

            # Send response
            response = {
                "message_type": "data_analysis_response",
                "analysis_id": analysis_id,
                "results": [r.to_dict() for r in results],
                "results_count": len(results),
            }

            if message.content.get("reply_to"):
                await self.send(
                    topic=message.content["reply_to"],
                    content=response,
                    sender_id=self.agent_id,
                )

            logger.info(f"[{self.agent_id}] Completed {len(results)} analyses")

        except Exception as e:
            logger.exception(f"[{self.agent_id}] Error analyzing data: {e}")

    async def _handle_detect_trends(self, message: ActorMessage) -> None:
        """
        Detect trends in time series data.

        Args:
            message: Actor message with time series data
        """
        try:
            is_valid, _error = self._validate_data_input(message.content)
            if not is_valid:
                logger.error(f"[{self.agent_id}] Invalid trend detection request: {_error}")
                return

            data = message.content["data"]

            logger.info(f"[{self.agent_id}] Detecting trends")

            result = await self._trend_analysis(data, f"trend_{datetime.now(UTC).timestamp()}")

            # Get trend details
            trend_id = f"trend_{result.analysis_id}"
            trend = self.trend_analyses.get(trend_id)

            response = {
                "message_type": "trend_detection_response",
                "result": result.to_dict(),
                "trend_details": trend.to_dict() if trend else None,
            }

            if message.content.get("reply_to"):
                await self.send(
                    topic=message.content["reply_to"],
                    content=response,
                    sender_id=self.agent_id,
                )

        except Exception as e:
            logger.exception(f"[{self.agent_id}] Error detecting trends: {e}")

    async def _handle_compute_correlations(self, message: ActorMessage) -> None:
        """
        Compute correlations between variables.

        Args:
            message: Actor message with variable data
        """
        try:
            is_valid, _error = self._validate_data_input(message.content)
            if not is_valid:
                logger.error(f"[{self.agent_id}] Invalid correlation request: {_error}")
                return

            data = message.content["data"]

            logger.info(f"[{self.agent_id}] Computing correlations")

            result = await self._correlational_analysis(
                data, f"corr_{datetime.now(UTC).timestamp()}"
            )

            response = {
                "message_type": "correlation_response",
                "result": result.to_dict(),
            }

            if message.content.get("reply_to"):
                await self.send(
                    topic=message.content["reply_to"],
                    content=response,
                    sender_id=self.agent_id,
                )

        except Exception as e:
            logger.exception(f"[{self.agent_id}] Error computing correlations: {e}")

    async def _handle_run_statistical_test(self, message: ActorMessage) -> None:
        """
        Run a statistical test.

        Args:
            message: Actor message with test parameters
        """
        try:
            test_type = message.content.get("test_type", "t_test")
            data = message.content.get("data", [])

            logger.info(f"[{self.agent_id}] Running statistical test: {test_type}")

            # For now, run basic statistical analysis
            result = await self._statistical_analysis(data, f"stat_{datetime.now(UTC).timestamp()}")

            response = {
                "message_type": "statistical_test_response",
                "test_type": test_type,
                "result": result.to_dict(),
            }

            if message.content.get("reply_to"):
                await self.send(
                    topic=message.content["reply_to"],
                    content=response,
                    sender_id=self.agent_id,
                )

        except Exception as e:
            logger.exception(f"[{self.agent_id}] Error running statistical test: {e}")

    async def _handle_extract_features(self, message: ActorMessage) -> None:
        """
        Extract features from data.

        Args:
            message: Actor message with data
        """
        try:
            is_valid, _error = self._validate_data_input(message.content)
            if not is_valid:
                logger.error(f"[{self.agent_id}] Invalid feature extraction request: {_error}")
                return

            data = message.content["data"]
            feature_id = message.content.get(
                "feature_id", f"features_{datetime.now(UTC).timestamp()}"
            )

            logger.info(f"[{self.agent_id}] Extracting features")

            # Extract features
            features = await self._extract_features_from_data(data)

            # Cache features
            self.feature_cache[feature_id] = features

            response = {
                "message_type": "feature_extraction_response",
                "feature_id": feature_id,
                "features": features,
            }

            if message.content.get("reply_to"):
                await self.send(
                    topic=message.content["reply_to"],
                    content=response,
                    sender_id=self.agent_id,
                )

        except Exception as e:
            logger.exception(f"[{self.agent_id}] Error extracting features: {e}")

    async def _handle_forecast_values(self, message: ActorMessage) -> None:
        """
        Forecast future values.

        Args:
            message: Actor message with historical data
        """
        try:
            data = message.content.get("data", [])
            periods = message.content.get("periods", 5)

            logger.info(f"[{self.agent_id}] Forecasting {periods} periods")

            # Simple forecasting
            forecast = await self._forecast_values(data, periods)

            response = {
                "message_type": "forecast_response",
                "historical_count": len(data),
                "forecast_periods": periods,
                "forecast": forecast,
            }

            if message.content.get("reply_to"):
                await self.send(
                    topic=message.content["reply_to"],
                    content=response,
                    sender_id=self.agent_id,
                )

        except Exception as e:
            logger.exception(f"[{self.agent_id}] Error forecasting: {e}")

    async def _handle_get_analytics_summary(self, message: ActorMessage) -> None:
        """
        Get summary of all analytics.

        Args:
            message: Actor message
        """
        try:
            summary = {
                "analyses_count": len(self.analysis_results),
                "trend_analyses_count": len(self.trend_analyses),
                "correlation_matrices_count": len(self.correlation_matrices),
                "feature_cache_count": len(self.feature_cache),
                "recent_analyses": [r.to_dict() for r in list(self.analysis_results.values())[-5:]],
            }

            response = {
                "message_type": "analytics_summary_response",
                "summary": summary,
            }

            if message.content.get("reply_to"):
                await self.send(
                    topic=message.content["reply_to"],
                    content=response,
                    sender_id=self.agent_id,
                )

        except Exception as e:
            logger.exception(f"[{self.agent_id}] Error getting analytics summary: {e}")

    async def _handle_signal_processing(self, message: ActorMessage) -> None:
        """
        Process signals with noise reduction.

        Args:
            message: Actor message with signal data
        """
        try:
            data = message.content.get("data", [])
            method = message.content.get("method", "moving_average")
            window = message.content.get("window", 3)

            logger.info(f"[{self.agent_id}] Processing signal with {method}")

            # Process signal
            processed = self._process_signal(data, method, window)

            response = {
                "message_type": "signal_processing_response",
                "method": method,
                "window": window,
                "original_length": len(data),
                "processed_length": len(processed),
                "processed_signal": processed,
            }

            if message.content.get("reply_to"):
                await self.send(
                    topic=message.content["reply_to"],
                    content=response,
                    sender_id=self.agent_id,
                )

        except Exception as e:
            logger.exception(f"[{self.agent_id}] Error processing signal: {e}")

    async def _handle_knowledge_enhanced_analysis(self, message: ActorMessage) -> None:
        """
        Perform knowledge-enhanced analytics using the unified knowledge access layer.

        This handler combines data analysis with contextual knowledge from memory and RAG.

        Args:
            message: Actor message with data and query for context
        """
        try:
            data = message.content.get("data", [])
            query = message.content.get("query")
            sources = message.content.get("sources", ["memory", "rag"])
            limit = message.content.get("limit", 10)

            if not query:
                logger.error(f"[{self.agent_id}] Knowledge enhanced analysis requires query")
                return

            logger.info(f"[{self.agent_id}] Performing knowledge-enhanced analysis: {query[:50]}")

            # First, query knowledge base for context
            if self.knowledge_access:
                knowledge_result = await self.knowledge_access.query(
                    query=query,
                    sources=sources,
                    limit=limit,
                    rerank=True,
                    diversity_lambda=0.5,
                )

                # Perform analysis on data
                analysis_id = f"knowledge_analysis_{datetime.now(UTC).timestamp()}"

                # Combine data analysis with knowledge context
                result = {
                    "analysis_id": analysis_id,
                    "query": query,
                    "knowledge_context": {
                        "entries": [e.to_dict() for e in knowledge_result.entries],
                        "total_results": knowledge_result.total_results,
                        "query_time_ms": knowledge_result.query_time_ms,
                    },
                    "data_analysis": {
                        "data_points": len(data),
                        "mean": sum(data) / len(data) if data else 0,
                        "min": min(data) if data else 0,
                        "max": max(data) if data else 0,
                    },
                }

                response = {
                    "message_type": "knowledge_enhanced_analysis_response",
                    "result": result,
                }

                if message.content.get("reply_to"):
                    await self.send(
                        topic=message.content["reply_to"],
                        content=response,
                        sender_id=self.agent_id,
                    )
            else:
                logger.warning(f"[{self.agent_id}] Knowledge access not initialized")

        except Exception as e:
            logger.exception(
                f"[{self.agent_id}] Error in knowledge enhanced analysis: {e}"
            )

    async def knowledge_enhanced_query(
        self,
        query: str,
        sources: list[str] | None = None,
        limit: int = 10,
        rerank: bool = True,
    ) -> KnowledgeQueryResult:
        """
        Execute a knowledge-enhanced query for analytics context.

        Args:
            query: Search query string
            sources: List of sources (memory, rag)
            limit: Maximum results
            rerank: Apply MMR reranking

        Returns:
            KnowledgeQueryResult with merged and reranked entries
        """
        if not self.knowledge_access:
            logger.warning(f"[{self.agent_id}] Knowledge access not initialized")
            return KnowledgeQueryResult(entries=[], total_results=0)

        return await self.knowledge_access.query(
            query=query,
            sources=sources or ["memory", "rag"],
            limit=limit,
            rerank=rerank,
        )

    # =========================================================================
    # Session 44: Collective Learning Integration Methods
    # =========================================================================

    async def _emit_pattern(
        self, item_id: str, item_type: str, outcome: str, content: dict[str, Any]
    ) -> None:
        """Emit pattern for collective learning."""
        if not self.pattern_extractor:
            return

        if item_id in self._pattern_emitted:
            return

        try:
            await self.pattern_extractor.analyze_message(
                message_id=f"{item_type}_{item_id}",
                sender=self.agent_id,
                recipient="broadcast",
                message_type=f"{item_type}_completion",
                content=content,
                timestamp=datetime.now(UTC).isoformat(),
            )

            self._pattern_emitted.add(item_id)
            logger.info("{item_type}_pattern_emitted", item_id=item_id, outcome=outcome)
        except Exception as e:
            logger.warning("failed_to_emit_pattern", item_id=item_id, error=str(e))

    async def _consume_patterns(
        self, pattern_types: list[PatternType] | None = None
    ) -> list[dict[str, Any]]:
        """Consume patterns from collective learning."""
        if not self.pattern_extractor:
            return []

        try:
            patterns = await self.pattern_extractor.extract_patterns(
                time_window_hours=24,
                pattern_types=pattern_types or [PatternType.SUCCESS, PatternType.DECISION],
            )
            return [p.to_dict() for p in patterns if p.metadata.confidence >= 0.7]
        except Exception as e:
            logger.warning("failed_to_consume_patterns", error=str(e))
            return []

    # =========================================================================
    # Session 44: Consensus Deliberation Integration Methods
    # =========================================================================

    async def _initiate_deliberation(
        self,
        item_id: str,
        proposal: str,
        participating_agents: list[str],
        domain: str = "general",
    ) -> str | None:
        """Initiate swarm deliberation."""
        if not self.deliberation_engine:
            return None

        try:
            deliberation_id = f"delib_{item_id}"
            self.deliberation_engine.start_deliberation(
                deliberation_id=deliberation_id,
                proposal=proposal[:200],
                participants=participating_agents,
                domain=domain,
            )
            self._active_deliberations[item_id] = deliberation_id

            logger.info("deliberation_initiated", deliberation_id=deliberation_id, item_id=item_id)
            return deliberation_id
        except Exception as e:
            logger.error("failed_to_initiate_deliberation", item_id=item_id, error=str(e))
            return None

    async def _submit_deliberation_position(
        self,
        item_id: str,
        agent_id: str,
        position: Position,
        confidence: float,
        argument: str,
    ) -> bool:
        """Submit agent position in deliberation."""
        if not self.deliberation_engine:
            return False

        deliberation_id = self._active_deliberations.get(item_id)
        if not deliberation_id:
            return False

        try:
            success = self.deliberation_engine.submit_position(
                deliberation_id=deliberation_id,
                agent_id=agent_id,
                position=position,
                confidence=confidence,
                argument=argument,
            )

            if success and self.access_analyzer:
                self.access_analyzer.record_access(
                    memory_id=f"delib_{deliberation_id}_{agent_id}",
                    access_type="write",
                    agent_id=agent_id,
                )

            return success
        except Exception as e:
            logger.error("failed_to_submit_deliberation_position", error=str(e))
            return False

    async def _finalize_deliberation(self, item_id: str) -> Any | None:
        """Finalize deliberation and apply result."""
        if not self.deliberation_engine:
            return None

        deliberation_id = self._active_deliberations.get(item_id)
        if not deliberation_id:
            return None

        try:
            result = self.deliberation_engine.finalize_deliberation(deliberation_id)

            if result:
                self.deliberation_engine.cleanup_deliberation(deliberation_id)
                del self._active_deliberations[item_id]
                logger.info("deliberation_finalized", deliberation_id=deliberation_id)

            return result
        except Exception as e:
            logger.error("failed_to_finalize_deliberation", error=str(e))
            return None


__all__ = ["PerceiverPlusAgent"]
