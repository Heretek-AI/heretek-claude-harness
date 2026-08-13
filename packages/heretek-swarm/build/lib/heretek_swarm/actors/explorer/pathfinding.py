"""
Explorer Pathfinding - Monitoring and Navigation Logic

Contains intelligence gathering, source monitoring, and opportunity/anomaly
detection methods extracted from explorer.py.

Author: Heretek Swarm Collective
Date: 2026-04-17
Version: 1.0.0
"""

from __future__ import annotations

import asyncio
import uuid
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

import structlog

from heretek_swarm.actors.explorer.types import (
    Anomaly,
    AnomalyType,
    IntelligenceReport,
    Opportunity,
    OpportunityType,
    ResearchProgress,
    ResearchState,
    ThreatLevel,
)

if TYPE_CHECKING:
    from heretek_swarm.actors.base import ActorMessage
    from heretek_swarm.knowledge.research import ResearchFinding, ResearchQuery, ResearchResult

logger = structlog.get_logger("ExplorerPathfinding")


class ExplorerPathfindingMixins:
    """
    Mixin class providing Explorer monitoring and navigation capabilities.

    This mixin handles:
    - Source monitoring loops
    - Opportunity and anomaly tracking
    - Intelligence report generation
    - Research workflow execution
    """

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        """Initialize pathfinding mixin - call super().__init__ first."""
        # Source monitoring configuration
        self.monitoring_interval_seconds: int = 300
        self.max_opportunities: int = 50
        self.max_anomalies: int = 100
        self.confidence_threshold: float = 0.6

        # Explorer state
        self._opportunities: dict[str, Opportunity] = {}
        self._anomalies: dict[str, Anomaly] = {}
        self._monitored_sources: set[str] = set()
        self._monitoring_active: bool = False
        self._monitor_task: asyncio.Task[None] | None = None
        self._intelligence_history: list[IntelligenceReport] = []
        self._max_intelligence_history: int = 20

        # Source-specific state
        self._source_configs: dict[str, dict[str, Any]] = {}
        self._last_source_check: dict[str, datetime] = {}
        self._source_error_counts: dict[str, int] = {}
        self._max_source_errors: int = 3

        # DISC-01: Integration state
        self._active_deliberations: dict[str, str] = {}
        self._pattern_emitted: set[str] = set()

        # DISC-01: Research infrastructure
        self._research_module: Any = None
        self._active_research: dict[str, ResearchProgress] = {}
        self._research_history: list[ResearchResult] = []
        self._max_research_history: int = 50
        self._research_state = ResearchState.IDLE

        # DISC-01: Pattern detection configuration
        self._pattern_confidence_threshold = 0.7

        # DISC-01: Beta validation integration
        self._beta_agent_id: str = "beta"

        super().__init__(*args, **kwargs)

    async def _monitoring_loop(self) -> None:
        """
        Continuous monitoring loop.

        Runs at configured intervals to check all monitored sources
        for opportunities and anomalies.
        """
        while self._monitoring_active:
            try:
                await self._check_all_sources()
                await self._analyze_findings()
                await asyncio.sleep(self.monitoring_interval_seconds)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error("Monitoring loop error", error=str(e))
                await asyncio.sleep(self.monitoring_interval_seconds)

    async def _check_all_sources(self) -> None:
        """Check all configured monitoring sources."""
        for source_id, config in self._source_configs.items():
            try:
                await self._check_source(source_id, config)
                self._last_source_check[source_id] = datetime.now(UTC)
                self._source_error_counts[source_id] = 0
            except Exception as e:
                self._source_error_counts[source_id] = (
                    self._source_error_counts.get(source_id, 0) + 1
                )
                logger.error(
                    "Source check failed",
                    source_id=source_id,
                    error=str(e),
                    error_count=self._source_error_counts[source_id],
                )

    async def _check_source(self, source_id: str, config: dict[str, Any]) -> None:
        """
        Check a single monitoring source.

        Args:
            source_id: Source identifier
            config: Source configuration (type, url, headers, etc.)
        """
        source_type = config.get("type", "generic")
        logger.debug("Checking source", source_id=source_id, type=source_type)

        # Placeholder for actual source checking logic
        # This would integrate with HTTP clients, RSS parsers, API clients, etc.
        # For now, we'll log the check and rely on explicit intelligence requests

    async def _analyze_findings(self) -> None:
        """Analyze collected findings for patterns and correlations."""
        # Placeholder for pattern analysis
        # Would look for correlations between opportunities and anomalies

    def _add_opportunity(self, opportunity: Opportunity) -> None:
        """
        Add opportunity with LRU eviction.

        Args:
            opportunity: Opportunity record to add
        """
        if len(self._opportunities) >= self.max_opportunities:
            # Evict oldest/lowest priority opportunity
            oldest_id = min(
                self._opportunities.keys(),
                key=lambda x: (
                    self._opportunities[x].impact_score,
                    self._opportunities[x].discovered_at,
                ),
            )
            del self._opportunities[oldest_id]
            logger.debug("Evicted oldest opportunity", evicted_id=oldest_id)

        self._opportunities[opportunity.id] = opportunity
        logger.info(
            "Opportunity added",
            opportunity_id=opportunity.id,
            type=opportunity.type.value,
            confidence=opportunity.confidence,
            impact=opportunity.impact_score,
        )

    def _add_anomaly(self, anomaly: Anomaly) -> None:
        """
        Add anomaly with LRU eviction.

        Args:
            anomaly: Anomaly record to add
        """
        if len(self._anomalies) >= self.max_anomalies:
            # Evict oldest/lowest severity anomaly
            severity_order = {
                ThreatLevel.LOW: 0,
                ThreatLevel.MEDIUM: 1,
                ThreatLevel.HIGH: 2,
                ThreatLevel.CRITICAL: 3,
            }
            oldest_id = min(
                self._anomalies.keys(),
                key=lambda x: (
                    severity_order.get(self._anomalies[x].severity, 0),
                    self._anomalies[x].detected_at,
                ),
            )
            del self._anomalies[oldest_id]
            logger.debug("Evicted oldest anomaly", evicted_id=oldest_id)

        self._anomalies[anomaly.id] = anomaly
        logger.info(
            "Anomaly added",
            anomaly_id=anomaly.id,
            type=anomaly.type.value,
            severity=anomaly.severity.value,
        )

    def _add_opportunity_legacy(self, opportunity: Opportunity) -> None:
        """Alias for _add_opportunity for backward compatibility."""
        return self._add_opportunity(opportunity)

    def _add_anomaly_legacy(self, anomaly: Anomaly) -> None:
        """Alias for _add_anomaly for backward compatibility."""
        return self._add_anomaly(anomaly)

    # -------------------------------------------------------------------------
    # Message Handlers
    # -------------------------------------------------------------------------

    async def _handle_start_monitoring(self, message: ActorMessage) -> None:
        """
        Start monitoring a source.

        Content schema:
        {
            "source_id": str,
            "source_type": str,
            "config": dict,
        }
        """
        try:
            from heretek_swarm.actors.validation import validate_message

            validated = validate_message("start_monitoring", message.content)
            content = validated.content

            source_id = content.get("source_id")
            source_type = content.get("source_type", "generic")
            config = content.get("config", {})

            if not source_id:
                logger.warning("Start monitoring missing source_id")
                return

            config["type"] = source_type
            self._source_configs[source_id] = config
            self._monitored_sources.add(source_id)
            self._last_source_check[source_id] = datetime.now(UTC)

            logger.info(
                "Started monitoring source",
                source_id=source_id,
                source_type=source_type,
            )

            await self._send_status_update(
                status="monitoring_started",
                source_id=source_id,
                source_type=source_type,
            )

        except Exception as e:
            logger.error("Failed to start monitoring", error=str(e))
            await self._send_error_response(message.sender_id, f"Failed to start monitoring: {e}")

    async def _handle_stop_monitoring(self, message: ActorMessage) -> None:
        """
        Stop monitoring a source.

        Content schema:
        {
            "source_id": str,
        }
        """
        try:
            from heretek_swarm.actors.validation import validate_message

            validated = validate_message("stop_monitoring", message.content)
            content = validated.content

            source_id = content.get("source_id")

            if not source_id:
                logger.warning("Stop monitoring missing source_id")
                return

            if source_id in self._source_configs:
                del self._source_configs[source_id]
                self._monitored_sources.discard(source_id)
                logger.info("Stopped monitoring source", source_id=source_id)

            await self._send_status_update(
                status="monitoring_stopped",
                source_id=source_id,
            )

        except Exception as e:
            logger.error("Failed to stop monitoring", error=str(e))
            await self._send_error_response(message.sender_id, f"Failed to stop monitoring: {e}")

    async def _handle_get_opportunities(self, message: ActorMessage) -> None:
        """
        Get discovered opportunities.

        Content schema:
        {
            "limit": int (optional, default 10),
            "min_confidence": float (optional),
            "type": str (optional, filter by type),
            "status": str (optional, filter by status),
        }
        """
        try:
            from heretek_swarm.actors.validation import validate_message

            validated = validate_message("get_opportunities", message.content)
            content = validated.content

            limit = content.get("limit", 10)
            min_confidence = content.get("min_confidence", self.confidence_threshold)
            opp_type = content.get("type")
            status = content.get("status")

            # Filter opportunities
            filtered = [
                opp
                for opp in self._opportunities.values()
                if opp.confidence >= min_confidence
                and (not opp_type or opp.type.value == opp_type)
                and (not status or opp.status == status)
            ]

            # Sort by impact score and confidence
            filtered.sort(key=lambda x: (x.impact_score, x.confidence), reverse=True)
            filtered = filtered[:limit]

            # Convert to serializable format
            result = [
                {
                    "id": opp.id,
                    "type": opp.type.value,
                    "title": opp.title,
                    "description": opp.description,
                    "source": opp.source,
                    "confidence": opp.confidence,
                    "impact_score": opp.impact_score,
                    "effort_estimate": opp.effort_estimate,
                    "discovered_at": opp.discovered_at.isoformat(),
                    "status": opp.status,
                }
                for opp in filtered
            ]

            await self._send_response(
                message.sender_id,
                {
                    "opportunities": result,
                    "total_available": len(self._opportunities),
                    "total_filtered": len(filtered),
                },
            )

        except Exception as e:
            logger.error("Failed to get opportunities", error=str(e))
            await self._send_error_response(message.sender_id, f"Failed to get opportunities: {e}")

    async def _handle_get_anomalies(self, message: ActorMessage) -> None:
        """
        Get detected anomalies.

        Content schema:
        {
            "limit": int (optional, default 10),
            "min_severity": str (optional),
            "type": str (optional, filter by type),
            "status": str (optional, filter by status),
        }
        """
        try:
            from heretek_swarm.actors.validation import validate_message

            validated = validate_message("get_anomalies", message.content)
            content = validated.content

            limit = content.get("limit", 10)
            min_severity = content.get("min_severity", ThreatLevel.LOW.value)
            anomaly_type = content.get("type")
            status = content.get("status")

            severity_order = {
                ThreatLevel.LOW.value: 0,
                ThreatLevel.MEDIUM.value: 1,
                ThreatLevel.HIGH.value: 2,
                ThreatLevel.CRITICAL.value: 3,
            }
            min_severity_value = severity_order.get(min_severity, 0)

            # Filter anomalies
            filtered = [
                anom
                for anom in self._anomalies.values()
                if severity_order.get(anom.severity.value, 0) >= min_severity_value
                and (not anomaly_type or anom.type.value == anomaly_type)
                and (not status or anom.status == status)
            ]

            # Sort by severity and recency
            filtered.sort(
                key=lambda x: (severity_order.get(x.severity.value, 0), x.detected_at),
                reverse=True,
            )
            filtered = filtered[:limit]

            # Convert to serializable format
            result = [
                {
                    "id": anom.id,
                    "type": anom.type.value,
                    "description": anom.description,
                    "source": anom.source,
                    "severity": anom.severity.value,
                    "detected_at": anom.detected_at.isoformat(),
                    "affected_components": anom.affected_components,
                    "status": anom.status,
                }
                for anom in filtered
            ]

            await self._send_response(
                message.sender_id,
                {
                    "anomalies": result,
                    "total_available": len(self._anomalies),
                    "total_filtered": len(filtered),
                },
            )

        except Exception as e:
            logger.error("Failed to get anomalies", error=str(e))
            await self._send_error_response(message.sender_id, f"Failed to get anomalies: {e}")

    async def _handle_generate_report(self, message: ActorMessage) -> None:
        """
        Generate intelligence report.

        Content schema:
        {
            "time_range_hours": int (optional, default 24),
            "include_opportunities": bool (optional, default True),
            "include_anomalies": bool (optional, default True),
        }
        """
        try:
            from heretek_swarm.actors.validation import validate_message

            validated = validate_message("generate_report", message.content)
            content = validated.content

            time_range_hours = content.get("time_range_hours", 24)
            include_opportunities = content.get("include_opportunities", True)
            include_anomalies = content.get("include_anomalies", True)

            cutoff = datetime.now(UTC)

            # Filter by time range
            opportunities = [
                opp
                for opp in self._opportunities.values()
                if include_opportunities and opp.discovered_at >= cutoff
            ]
            anomalies = [
                anom
                for anom in self._anomalies.values()
                if include_anomalies and anom.detected_at >= cutoff
            ]

            # Generate summary using LLM if available
            summary = await self._generate_summary(opportunities, anomalies, time_range_hours)
            recommendations = await self._generate_recommendations(opportunities, anomalies)

            report = IntelligenceReport(
                id=f"intel-{datetime.now(UTC).strftime('%Y%m%d-%H%M%S')}",
                generated_at=datetime.now(UTC),
                opportunities=opportunities,
                anomalies=anomalies,
                summary=summary,
                recommendations=recommendations,
                sources_monitored=list(self._monitored_sources),
                time_range_hours=time_range_hours,
            )

            # Store in history
            self._intelligence_history.append(report)
            if len(self._intelligence_history) > self._max_intelligence_history:
                self._intelligence_history = self._intelligence_history[
                    -self._max_intelligence_history :
                ]

            # Convert to serializable format
            report_data = {
                "id": report.id,
                "generated_at": report.generated_at.isoformat(),
                "summary": report.summary,
                "recommendations": report.recommendations,
                "opportunities_count": len(report.opportunities),
                "anomalies_count": len(report.anomalies),
                "sources_monitored": report.sources_monitored,
                "time_range_hours": report.time_range_hours,
            }

            await self._send_response(message.sender_id, report_data)

        except Exception as e:
            logger.error("Failed to generate report", error=str(e))
            await self._send_error_response(message.sender_id, f"Failed to generate report: {e}")

    async def _handle_report_opportunity(self, message: ActorMessage) -> None:
        """
        Report a new opportunity from external source.

        Content schema:
        {
            "type": str,
            "title": str,
            "description": str,
            "source": str,
            "confidence": float,
            "impact_score": float,
            "effort_estimate": str,
            "metadata": dict (optional),
        }
        """
        try:
            from heretek_swarm.actors.validation import validate_message

            validated = validate_message("report_opportunity", message.content)
            content = validated.content

            opportunity = Opportunity(
                id=f"opp-{uuid.uuid4().hex[:8]}",
                type=OpportunityType(content.get("type", "capability_addition")),
                title=content.get("title", "Untitled Opportunity"),
                description=content.get("description", ""),
                source=content.get("source", "external"),
                confidence=float(content.get("confidence", 0.5)),
                impact_score=float(content.get("impact_score", 0.5)),
                effort_estimate=content.get("effort_estimate", "medium"),
                discovered_at=datetime.now(UTC),
                metadata=content.get("metadata", {}),
            )

            self._add_opportunity(opportunity)

            await self._send_status_update(
                status="opportunity_recorded",
                opportunity_id=opportunity.id,
                title=opportunity.title,
            )

        except Exception as e:
            logger.error("Failed to report opportunity", error=str(e))
            await self._send_error_response(message.sender_id, f"Failed to report opportunity: {e}")

    async def _handle_report_anomaly(self, message: ActorMessage) -> None:
        """
        Report a detected anomaly.

        Content schema:
        {
            "type": str,
            "description": str,
            "source": str,
            "severity": str,
            "affected_components": list,
            "evidence": dict,
            "metadata": dict (optional),
        }
        """
        try:
            from heretek_swarm.actors.validation import validate_message

            validated = validate_message("report_anomaly", message.content)
            content = validated.content

            anomaly = Anomaly(
                id=f"anom-{uuid.uuid4().hex[:8]}",
                type=AnomalyType(content.get("type", "behavioral")),
                description=content.get("description", ""),
                source=content.get("source", "internal"),
                severity=ThreatLevel(content.get("severity", ThreatLevel.LOW.value)),
                detected_at=datetime.now(UTC),
                affected_components=content.get("affected_components", []),
                evidence=content.get("evidence", {}),
                metadata=content.get("metadata", {}),
            )

            self._add_anomaly(anomaly)

            # Escalate high/critical anomalies immediately
            if anomaly.severity in [ThreatLevel.HIGH, ThreatLevel.CRITICAL]:
                logger.warning(
                    "High severity anomaly detected - escalating",
                    anomaly_id=anomaly.id,
                    severity=anomaly.severity.value,
                    description=anomaly.description,
                )

            await self._send_status_update(
                status="anomaly_recorded",
                anomaly_id=anomaly.id,
                severity=anomaly.severity.value,
            )

        except Exception as e:
            logger.error("Failed to report anomaly", error=str(e))
            await self._send_error_response(message.sender_id, f"Failed to report anomaly: {e}")

    async def _handle_get_monitoring_status(self, message: ActorMessage) -> None:
        """
        Get monitoring status overview.

        Content schema: {}
        """
        try:
            sources_status = []
            for source_id in self._monitored_sources:
                last_check = self._last_source_check.get(source_id)
                error_count = self._source_error_counts.get(source_id, 0)

                sources_status.append(
                    {
                        "source_id": source_id,
                        "type": self._source_configs.get(source_id, {}).get("type", "unknown"),
                        "last_check": last_check.isoformat() if last_check else None,
                        "error_count": error_count,
                        "status": "healthy" if error_count < self._max_source_errors else "error",
                    }
                )

            status_data = {
                "monitoring_active": self._monitoring_active,
                "sources_count": len(self._monitored_sources),
                "opportunities_tracked": len(self._opportunities),
                "anomalies_tracked": len(self._anomalies),
                "reports_generated": len(self._intelligence_history),
                "sources": sources_status,
            }

            await self._send_response(message.sender_id, status_data)

        except Exception as e:
            logger.error("Failed to get monitoring status", error=str(e))
            await self._send_error_response(message.sender_id, f"Failed to get status: {e}")

    # -------------------------------------------------------------------------
    # Helper Methods
    # -------------------------------------------------------------------------

    async def _generate_summary(
        self,
        opportunities: list[Opportunity],
        anomalies: list[Anomaly],
        time_range_hours: int,
    ) -> str:
        """Generate intelligence summary using LLM."""
        try:
            prompt = self._build_summary_prompt(opportunities, anomalies, time_range_hours)
            summary = await self.run_with_llm(prompt, timeout=60)
            opp_count = len(opportunities)
            anom_count = len(anomalies)
            default_summary = (
                f"Intelligence report for the past {time_range_hours} hours: "
                f"{opp_count} opportunities and {anom_count} anomalies identified."
            )
            return summary or default_summary
        except Exception as e:
            logger.error("Failed to generate LLM summary", error=str(e))
            return (
                f"Intelligence report: {opp_count} opportunities, "
                f"{anom_count} anomalies (summary generation failed)"
            )

    async def _generate_recommendations(
        self,
        opportunities: list[Opportunity],
        anomalies: list[Anomaly],
    ) -> list[str]:
        """Generate recommendations based on findings."""
        recommendations = []

        # High-impact opportunities
        high_impact = [o for o in opportunities if o.impact_score > 0.7]
        if high_impact:
            recommendations.append(
                f"Prioritize investigation of {len(high_impact)} high-impact opportunities"
            )

        # High-severity anomalies
        critical = [a for a in anomalies if a.severity in [ThreatLevel.HIGH, ThreatLevel.CRITICAL]]
        if critical:
            recommendations.append(
                f"Immediately address {len(critical)} critical/high-severity anomalies"
            )

        # Pattern-based recommendations
        if len(opportunities) > 10:
            recommendations.append("Consider expanding monitoring scope - high opportunity rate")

        if len(anomalies) > 20:
            recommendations.append("Review system health - elevated anomaly count detected")

        return recommendations or ["Continue standard monitoring operations"]

    def _build_summary_prompt(
        self,
        opportunities: list[Opportunity],
        anomalies: list[Anomaly],
        time_range_hours: int,
    ) -> str:
        """Build LLM prompt for summary generation."""
        opp_lines = []
        for opp in opportunities[:10]:
            opp_lines.append(  # noqa: PERF401
                f"- [{opp.type.value}] {opp.title} "
                f"(confidence: {opp.confidence:.2f}, impact: {opp.impact_score:.2f})"
            )
        opp_summary = "\n".join(opp_lines)
        anom_lines = []
        for anom in anomalies[:10]:
            anom_lines.append(  # noqa: PERF401
                f"- [{anom.severity.value}] {anom.description[:50]}... (source: {anom.source})"
            )
        anom_summary = "\n".join(anom_lines)

        return f"""Generate a concise intelligence summary for the past {time_range_hours} hours.

OPPORTUNITIES IDENTIFIED ({len(opportunities)} total, showing top 10):
{opp_summary or "None"}

ANOMALIES DETECTED ({len(anomalies)} total, showing top 10):
{anom_summary or "None"}

Provide a 2-3 sentence executive summary highlighting
the most significant findings and recommended focus areas."""

    async def _send_status_update(self, status: str, **kwargs: Any) -> None:
        """Send status update to relevant agents."""
        await self._send_response("broadcast", {"status": status, **kwargs})

    async def _send_error_response(self, recipient: str, error: str) -> None:
        """Send error response."""
        await self._send_response(recipient, {"error": error})

    async def _send_response(self, recipient: str, data: dict[str, Any]) -> None:
        """Send response message."""
        if recipient == "broadcast":
            # Broadcast to subscribed agents
            pass
        else:
            await self.put_message(
                recipient=recipient,
                message_type="intelligence_response",
                content=data,
            )

    # -------------------------------------------------------------------------
    # DISC-01: Research Workflow Methods
    # -------------------------------------------------------------------------

    async def _handle_research_topic(self, message: ActorMessage) -> None:
        """
        Execute deep research on a topic.

        Content schema:
        {
            "topic": str,
            "depth": str (surface/standard/deep/exhaustive),
            "focus_areas": list[str] (optional),
            "max_sources": int (optional),
            "time_limit_seconds": float (optional),
        }
        """
        try:
            from heretek_swarm.actors.validation import validate_message
            from heretek_swarm.knowledge.research import ResearchDepth, ResearchQuery

            validated = validate_message("ExplorerResearchTopic", message.content)
            content = validated.content

            topic = content.get("topic", "")
            if not topic:
                await self._send_error_response(message.sender_id, "Topic is required for research")
                return

            depth_str = content.get("depth", "standard")
            depth = ResearchDepth(depth_str)

            query = ResearchQuery(
                query_id=f"research-{uuid.uuid4().hex[:8]}",
                topic=topic,
                depth=depth,
                max_sources=content.get("max_sources", 10),
                time_range_hours=content.get("time_range_hours"),
                filters=content.get("filters", {}),
                validate_contradictions=True,
                detect_correlations=True,
            )

            progress = ResearchProgress(
                query_id=query.query_id,
                topic=topic,
                state=ResearchState.RESEARCHING,
            )
            self._active_research[query.query_id] = progress

            await self._report_progress_to_steward(progress, status="started")

            self._research_state = ResearchState.RESEARCHING

            result = await self._execute_research(query, progress)

            self._research_history.append(result)
            if len(self._research_history) > self._max_research_history:
                self._research_history = self._research_history[-self._max_research_history :]

            self._research_state = ResearchState.IDLE
            del self._active_research[query.query_id]

            patterns = await self._detect_and_emit_patterns(result.findings)

            if result.contradictions_detected:
                await self._resolve_contradictions(result.contradictions_detected)

            response_data = {
                "status": "success",
                "query_id": query.query_id,
                "topic": topic,
                "depth": depth.value,
                "findings_count": len(result.findings),
                "contradictions_count": len(result.contradictions_detected),
                "patterns_detected": len(patterns),
                "summary": result.summary,
                "confidence_score": result.confidence_score,
                "research_duration_ms": result.research_duration_ms,
            }

            await self._send_response(message.sender_id, response_data)

            await self._report_progress_to_steward(progress, status="completed")

            logger.info(
                "Research completed",
                query_id=query.query_id,
                topic=topic,
                findings=len(result.findings),
                contradictions=len(result.contradictions_detected),
            )

        except Exception as e:
            logger.error("Failed to execute research", error=str(e))
            self._research_state = ResearchState.IDLE
            await self._send_error_response(message.sender_id, f"Research failed: {e}")

    async def _handle_get_research_status(self, message: ActorMessage) -> None:
        """
        Get status of active research operations.

        Content schema: {}
        """
        try:
            active_list = []
            for progress in self._active_research.values():
                active_list.append(  # noqa: PERF401
                    {
                        "query_id": progress.query_id,
                        "topic": progress.topic,
                        "state": progress.state.value,
                        "sources_consulted": progress.sources_consulted,
                        "findings_count": progress.findings_count,
                        "percent_complete": progress.percent_complete,
                        "elapsed_seconds": progress.elapsed_seconds,
                    }
                )

            await self._send_response(
                message.sender_id,
                {
                    "active_research": active_list,
                    "research_state": self._research_state.value,
                },
            )

        except Exception as e:
            logger.error("Failed to get research status", error=str(e))
            await self._send_error_response(message.sender_id, f"Failed to get status: {e}")

    async def _handle_get_research_results(self, message: ActorMessage) -> None:
        """
        Get results from a completed research operation.

        Content schema:
        {
            "query_id": str (optional, gets most recent if not specified),
            "limit": int (optional, default 10),
        }
        """
        try:
            from heretek_swarm.actors.validation import validate_message

            validated = validate_message("ExplorerGetResearchResults", message.content)
            content = validated.content

            query_id = content.get("query_id")
            limit = content.get("limit", 10)

            if query_id:
                result = self._research_module.get_research_history(limit=1)
                if result:
                    await self._send_response(
                        message.sender_id,
                        {
                            "result": result[0].to_dict() if result else None,
                        },
                    )
                else:
                    await self._send_error_response(
                        message.sender_id, f"Research {query_id} not found"
                    )
            else:
                results = self._research_history[-limit:]
                await self._send_response(
                    message.sender_id,
                    {
                        "results": [r.to_dict() for r in results],
                        "count": len(results),
                    },
                )

        except Exception as e:
            logger.error("Failed to get research results", error=str(e))
            await self._send_error_response(message.sender_id, f"Failed to get results: {e}")

    async def _execute_research(
        self,
        query: ResearchQuery,
        progress: ResearchProgress,
    ) -> ResearchResult:
        """Execute the research workflow."""
        import time

        start_time = time.time()
        self._research_state = ResearchState.RESEARCHING

        progress.state = ResearchState.RESEARCHING
        result = await self._research_module.investigate(query)

        progress.state = ResearchState.ANALYZING
        self._research_state = ResearchState.ANALYZING

        progress.sources_consulted = len(result.sources_consulted)
        progress.findings_count = len(result.findings)
        progress.elapsed_seconds = time.time() - start_time
        progress.percent_complete = 50.0

        await self._report_progress_to_steward(progress, status="update")

        if result.contradictions_detected:
            progress.state = ResearchState.CONTRADICTION
            self._research_state = ResearchState.CONTRADICTION
            progress.contradictions_found = len(result.contradictions_detected)

        progress.state = ResearchState.DELIVERING
        self._research_state = ResearchState.DELIVERING
        progress.percent_complete = 90.0

        result.research_duration_ms = progress.elapsed_seconds * 1000

        return result

    async def _detect_and_emit_patterns(
        self,
        findings: list[ResearchFinding],
    ) -> list:
        """Detect patterns in findings and emit to collective learning."""
        from heretek_swarm.actors.explorer.types import Pattern as PatternType

        patterns: list[PatternType] = []

        if not self.pattern_extractor:
            return patterns

        by_type: dict[str, list[ResearchFinding]] = {}
        for finding in findings:
            ftype = finding.finding_type.value
            if ftype not in by_type:
                by_type[ftype] = []
            by_type[ftype].append(finding)

        for ptype, type_findings in by_type.items():
            if len(type_findings) >= 3:
                avg_confidence = sum(f.confidence for f in type_findings) / len(type_findings)
                if avg_confidence >= self._pattern_confidence_threshold:
                    pattern = PatternType(
                        pattern_id=f"pattern-{uuid.uuid4().hex[:8]}",
                        pattern_type=ptype,
                        confidence=avg_confidence,
                        supporting_findings=[f.finding_id for f in type_findings],
                        description=f"Trend detected: {len(type_findings)} {ptype} findings",
                    )
                    patterns.append(pattern)

                    await self._emit_pattern(
                        item_id=pattern.pattern_id,
                        item_type="research_pattern",
                        outcome="detected",
                        content={
                            "pattern_type": pattern.pattern_type,
                            "confidence": pattern.confidence,
                            "findings_count": len(type_findings),
                            "description": pattern.description,
                        },
                    )

        return patterns

    async def _resolve_contradictions(
        self,
        contradictions: list[ResearchFinding],
    ) -> None:
        """Resolve contradictory findings via Beta validation."""
        self._research_state = ResearchState.VALIDATING

        for finding in contradictions:
            validation = await self._request_beta_validation(finding)

            if not validation.get("is_valid", True):
                logger.info(
                    "Beta rejected contradictory finding",
                    finding_id=finding.finding_id,
                    reason=validation.get("reason"),
                )

        await self._request_deliberation(contradictions)

    async def _request_beta_validation(self, finding: ResearchFinding) -> dict[str, Any]:
        """Request Beta agent to validate a finding."""
        try:
            validation_request = {
                "validation_type": "research_finding",
                "finding_id": finding.finding_id,
                "content": finding.content,
                "confidence": finding.confidence,
                "source": finding.source.name if finding.source else "unknown",
            }

            await self.put_message(
                recipient=self._beta_agent_id,
                message_type="validate_research_finding",
                content=validation_request,
            )

            logger.info(
                "Beta validation requested",
                finding_id=finding.finding_id,
                beta_agent=self._beta_agent_id,
            )

            return {"is_valid": True}

        except Exception as e:
            logger.error("Beta validation request failed", error=str(e))
            return {"is_valid": True, "reason": str(e)}

    async def _request_deliberation(self, findings: list[ResearchFinding]) -> None:
        """Request deliberation on findings via Steward."""
        try:
            if not self.deliberation_engine:
                return

            deliberation_id = f"delib-research-{uuid.uuid4().hex[:8]}"
            findings_count = len(findings)
            proposal = (
                f"Research findings require consensus: "
                f"{findings_count} contradictory findings detected"
            )

            self.deliberation_engine.start_deliberation(
                deliberation_id=deliberation_id,
                proposal=proposal[:200],
                participants=["explorer", "beta", "steward"],
                domain="research",
            )

            self._active_deliberations[deliberation_id] = deliberation_id

            logger.info(
                "Deliberation requested",
                deliberation_id=deliberation_id,
                findings_count=len(findings),
            )

        except Exception as e:
            logger.error("Deliberation request failed", error=str(e))

    async def _report_progress_to_steward(
        self,
        progress: ResearchProgress,
        status: str,
    ) -> None:
        """Report research progress to Steward."""
        try:
            await self.put_message(
                recipient="steward",
                message_type="research_progress",
                content={
                    "query_id": progress.query_id,
                    "topic": progress.topic,
                    "status": status,
                    "state": progress.state.value,
                    "sources_consulted": progress.sources_consulted,
                    "findings_count": progress.findings_count,
                    "percent_complete": progress.percent_complete,
                    "elapsed_seconds": progress.elapsed_seconds,
                },
            )
        except Exception as e:
            logger.warning("Failed to report progress to steward", error=str(e))
