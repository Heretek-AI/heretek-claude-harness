"""
Explorer Agent - Intelligence Gathering & Opportunity Discovery.

The Explorer agent provides:
- Monitoring of upstream sources and external systems
- Intelligence gathering from external sources
- Opportunity identification and capability discovery
- Anomaly detection and threat reporting
- External integration research

Explorer is the "eyes and ears" of the Collective, constantly scanning
the environment for opportunities, threats, and new capabilities.

Author: Heretek Swarm Collective
Date: 2026-04-17
Version: 1.0.0
"""

from __future__ import annotations

import asyncio
import contextlib
from typing import TYPE_CHECKING, Any

import structlog

from heretek_swarm.actors.base import AgentActor
from heretek_swarm.actors.explorer.pathfinding import ExplorerPathfindingMixins
from heretek_swarm.actors.mixins import (
    DeliberationMixin,
    LearningMixin,
    MemoryMixin,
    PatternMixin,
    ValidationMixin,
)

if TYPE_CHECKING:
    from swarms import Agent

logger = structlog.get_logger("ExplorerAgent")


class ExplorerAgent(
    ExplorerPathfindingMixins,
    ValidationMixin,
    DeliberationMixin,
    PatternMixin,
    MemoryMixin,
    LearningMixin,
    AgentActor,
):
    """
    Explorer Agent - Intelligence Gathering Specialist.

    The Explorer is responsible for:
    - Continuously monitoring upstream sources and external APIs
    - Identifying new capabilities, frameworks, and integrations
    - Detecting anomalies in external systems and internal metrics
    - Gathering intelligence to support collective decisions
    - Reporting opportunities and threats to the swarm

    Intelligence Gathering Workflow:
    1. Monitor configured sources (APIs, feeds, repositories)
    2. Parse and analyze incoming data
    3. Identify patterns, opportunities, and anomalies
    4. Score and prioritize findings
    5. Generate intelligence reports
    6. Notify relevant agents of significant findings
    """

    def __init__(
        self,
        agent_id: str = "explorer",
        name: str = "Explorer",
        description: str = "Intelligence gathering and opportunity discovery specialist",
        swarms_agent: Agent | None = None,
        monitoring_interval_seconds: int = 300,
        max_opportunities: int = 50,
        max_anomalies: int = 100,
        confidence_threshold: float = 0.6,
        **kwargs: Any,
    ) -> None:
        """
        Initialize the Explorer agent.

        Args:
            agent_id: Unique identifier
            name: Human-readable name
            description: Agent description
            swarms_agent: Optional Swarms Agent for LLM capabilities
            monitoring_interval_seconds: Interval between monitoring cycles
            max_opportunities: Maximum tracked opportunities (LRU eviction)
            max_anomalies: Maximum tracked anomalies (LRU eviction)
            confidence_threshold: Minimum confidence for reporting findings
            **kwargs: Additional arguments
        """
        # Initialize mixin first to set up attributes
        ExplorerPathfindingMixins.__init__(
            self,
            monitoring_interval_seconds=monitoring_interval_seconds,
            max_opportunities=max_opportunities,
            max_anomalies=max_anomalies,
            confidence_threshold=confidence_threshold,
        )

        # Initialize base agent
        super().__init__(
            agent_id=agent_id,
            name=name,
            description=description,
            topics=[
                "exploration",
                "intelligence",
                "opportunities",
                "discovery",
                "monitoring",
            ],
            capabilities=[
                "source-monitoring",
                "opportunity-identification",
                "anomaly-detection",
                "intelligence-gathering",
                "capability-discovery",
            ],
            swarms_agent=swarms_agent,
            **kwargs,
        )

        # DISC-01: Configuration
        self._config: dict[str, Any] = {}

        # DISC-01: Research infrastructure
        from heretek_swarm.knowledge.research import ResearchModule

        self._research_module = ResearchModule(
            max_findings_per_topic=100,
            contradiction_threshold=0.7,
            correlation_threshold=0.6,
        )

        # DISC-01: Beta validation integration
        self._beta_agent_id = self._config.get("beta_agent_id", "beta")

        logger.info(
            "Explorer agent initialized",
            agent_id=agent_id,
            monitoring_interval=monitoring_interval_seconds,
            confidence_threshold=confidence_threshold,
        )

    async def on_start(self) -> None:
        """Start the Explorer agent and begin monitoring."""
        await super().on_start()
        self._monitoring_active = True
        self._monitor_task = asyncio.create_task(self._monitoring_loop())
        logger.info("Explorer agent started, monitoring active")

    async def on_stop(self) -> None:
        """Stop the Explorer agent and halt monitoring."""
        self._monitoring_active = False
        if self._monitor_task:
            self._monitor_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._monitor_task
            self._monitor_task = None
        await super().on_stop()
        logger.info("Explorer agent stopped")

    # Legacy aliases for backward compatibility with external code
    def _add_opportunity_legacy(self, opportunity: Any) -> None:
        """Alias for _add_opportunity for backward compatibility."""
        return self._add_opportunity(opportunity)

    def _add_anomaly_legacy(self, anomaly: Any) -> None:
        """Alias for _add_anomaly for backward compatibility."""
        return self._add_anomaly(anomaly)


# Backward-compatible module-level imports
from heretek_swarm.actors.explorer.types import (  # noqa: E402
    Anomaly,
    AnomalyType,
    IntelligenceReport,
    Opportunity,
    OpportunityType,
    Pattern,
    ResearchProgress,
    ResearchState,
    ThreatLevel,
)

__all__ = [
    "Anomaly",
    "AnomalyType",
    # Main agent class
    "ExplorerAgent",
    # Mixin for pathfinding
    "ExplorerPathfindingMixins",
    "IntelligenceReport",
    "Opportunity",

    "OpportunityType",
    "Pattern",
    "ResearchProgress",
    "ResearchState",
    "ThreatLevel",
]
