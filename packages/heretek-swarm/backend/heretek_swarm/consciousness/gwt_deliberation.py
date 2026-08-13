"""
GWT Integration with Deliberation Engine.

Provides seamless integration between GWT broadcast and the SwarmDeliberationEngine:
- Broadcast deliberation outcomes via GWT
- Subscribe agents to relevant deliberation broadcasts
- Automatic salience calculation for deliberation content

This module provides both a wrapper class and mixin methods for agent integration.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import structlog

from heretek_swarm.consciousness.gwt import (
    GlobalWorkspaceBroadcast,
    GWTConfig,
    create_gwt_content,
)

if TYPE_CHECKING:
    from collections.abc import Callable

    from heretek_swarm_core.consensus.swarm_deliberation import (
        DeliberationResult,
        SwarmDeliberationEngine,
    )

logger = structlog.get_logger(__name__)


class GWTSalienceCalculator:
    """Calculate salience metrics for deliberation content."""

    @staticmethod
    def calculate_deliberation_salience(
        result: DeliberationResult,
        _domain: str | None = None,
    ) -> dict[str, float]:
        """
        Calculate salience metrics for a deliberation result.

        Args:
            result: The deliberation result
            domain: Optional domain for context

        Returns:
            Salience metrics dict
        """
        novelty = 0.3
        relevance = 0.5
        urgency = 0.3
        impact = result.consensus_score * 0.8
        confidence = result.consensus_score

        if result.participation_rate < 0.5:
            novelty += 0.2
            urgency += 0.2

        if result.minority_report:
            novelty += 0.1

        if result.rounds_completed >= 3:
            urgency -= 0.1

        return {
            "novelty": min(1.0, max(0.0, novelty)),
            "relevance": min(1.0, max(0.0, relevance)),
            "urgency": min(1.0, max(0.0, urgency)),
            "impact": min(1.0, max(0.0, impact)),
            "confidence": min(1.0, max(0.0, confidence)),
        }


class DeliberationGWTIntegrator:
    """
    Integrates GWT broadcast with SwarmDeliberationEngine.

    Wraps deliberation results and broadcasts them via GWT when
    deliberations complete, enabling consciousness-level awareness
    across all agents.
    """

    def __init__(
        self,
        gwt_broadcast: GlobalWorkspaceBroadcast | None = None,
        config: GWTConfig | None = None,
    ) -> None:
        self._gwt = gwt_broadcast or GlobalWorkspaceBroadcast(config=config)
        self._salience_calc = GWTSalienceCalculator()
        self._auto_broadcast_enabled = True
        self._deliberation_callbacks: list[Callable[[Any], Any]] = []

    @property
    def gwt_broadcast(self) -> GlobalWorkspaceBroadcast:
        """Get the GWT broadcast instance."""
        return self._gwt

    def enable_auto_broadcast(self) -> None:
        """Enable automatic broadcasting of deliberation outcomes."""
        self._auto_broadcast_enabled = True
        logger.info("deliberation_gwt_auto_broadcast_enabled")

    def disable_auto_broadcast(self) -> None:
        """Disable automatic broadcasting of deliberation outcomes."""
        self._auto_broadcast_enabled = False
        logger.info("deliberation_gwt_auto_broadcast_disabled")

    def add_deliberation_callback(
        self,
        callback: Callable[[Any], Any],
    ) -> None:
        """
        Add callback to be called when deliberations are broadcast.

        Args:
            callback: Async function to call with broadcast content
        """
        self._deliberation_callbacks.append(callback)

    def remove_deliberation_callback(
        self,
        callback: Callable[[Any], Any],
    ) -> None:
        """Remove a deliberation callback."""
        if callback in self._deliberation_callbacks:
            self._deliberation_callbacks.remove(callback)

    async def broadcast_deliberation_result(
        self,
        result: DeliberationResult,
        domain: str | None = None,
    ) -> bool:
        """
        Broadcast a deliberation result via GWT.

        Args:
            result: The deliberation result to broadcast
            domain: Optional domain context

        Returns:
            True if broadcast successful
        """
        salience_metrics = self._salience_calc.calculate_deliberation_salience(result, domain)

        gwt_content = create_gwt_content(
            source_agent="deliberation-engine",
            content_type="deliberation_outcome",
            payload=result.decision_provenance if hasattr(result, "decision_provenance") else {},
            novelty=salience_metrics["novelty"],
            relevance=salience_metrics["relevance"],
            urgency=salience_metrics["urgency"],
            impact=salience_metrics["impact"],
            confidence=salience_metrics["confidence"],
        )

        gwt_content.payload["deliberation_id"] = result.deliberation_id
        gwt_content.payload["proposal"] = result.proposal
        gwt_content.payload["final_position"] = result.final_position.value
        gwt_content.payload["consensus_score"] = result.consensus_score
        gwt_content.payload["participation_rate"] = result.participation_rate
        gwt_content.payload["rounds_completed"] = result.rounds_completed
        gwt_content.payload["minority_report"] = result.minority_report
        gwt_content.payload["arguments_summary"] = result.arguments_summary

        success = await self._gwt.broadcast_content(gwt_content)

        if success:
            for callback in self._deliberation_callbacks:
                try:
                    await callback(gwt_content)
                except Exception as e:
                    logger.error("deliberation_callback_error", error=str(e))

        return success

    async def wrap_engine_finalize(
        self,
        engine: SwarmDeliberationEngine,
        deliberation_id: str,
    ) -> Any:
        """
        Wrap engine finalize to add GWT broadcasting.

        This method finalizes the deliberation and broadcasts the result.

        Args:
            engine: The deliberation engine
            deliberation_id: ID of deliberation to finalize

        Returns:
            Deliberation result
        """
        result = engine.finalize_deliberation(deliberation_id)

        if result and self._auto_broadcast_enabled:
            await self.broadcast_deliberation_result(result)

        return result


async def integrate_gwt_with_agent(
    agent: Any,
    gwt_broadcast: GlobalWorkspaceBroadcast,
    subscribe_to_deliberations: bool = True,
    subscribe_to_broadcasts: bool = True,
    content_types: list[str] | None = None,
    min_salience: float = 0.3,
) -> dict[str, Any]:
    """
    Integrate GWT broadcast with an agent.

    Sets up the agent to:
    - Broadcast its decisions via GWT
    - Subscribe to deliberation broadcasts
    - Subscribe to other agent broadcasts

    Args:
        agent: The agent instance
        gwt_broadcast: GWT broadcast instance
        subscribe_to_deliberations: Whether to subscribe to deliberation outcomes
        subscribe_to_broadcasts: Whether to subscribe to general broadcasts
        content_types: Content types to subscribe to
        min_salience: Minimum salience level

    Returns:
        Dict with subscription IDs
    """
    subscriptions = {}

    agent._gwt_broadcast = gwt_broadcast  # noqa: SLF001

    if subscribe_to_deliberations:

        async def deliberation_handler(content: Any) -> None:
            if hasattr(agent, "receive_deliberation_broadcast"):
                await agent.receive_deliberation_broadcast(content)

        sub_id = await gwt_broadcast.subscribe_to_deliberations(deliberation_handler)
        if sub_id:
            subscriptions["deliberation"] = sub_id

    if subscribe_to_broadcasts:

        async def broadcast_handler(content: Any) -> None:
            if hasattr(agent, "receive_gwt_broadcast"):
                await agent.receive_gwt_broadcast(content)

        sub_id = await gwt_broadcast.subscribe_to_broadcasts(
            broadcast_handler,
            content_types=content_types,
            min_salience=min_salience,
        )
        if sub_id:
            subscriptions["broadcast"] = sub_id

    logger.info(
        "gwt_integrated_with_agent",
        agent=type(agent).__name__,
        subscriptions=len(subscriptions),
    )

    return subscriptions


class GWTDeliberationMixin:
    """
    Mixin to add GWT broadcast capabilities to deliberation-enabled agents.

    Agents using this mixin will automatically broadcast their
    deliberation outcomes via GWT.
    """

    _gwt_broadcast: GlobalWorkspaceBroadcast | None = None
    _gwt_deliberation_integrator: DeliberationGWTIntegrator | None = None

    async def _broadcast_via_gwt(
        self,
        content_type: str,
        payload: dict[str, Any],
        novelty: float = 0.5,
        relevance: float = 0.5,
        urgency: float = 0.5,
        impact: float = 0.5,
        confidence: float = 0.5,
    ) -> bool:
        """
        Broadcast content via GWT.

        Args:
            content_type: Type of content
            payload: Content payload
            novelty: Novelty score (0-1)
            relevance: Relevance score (0-1)
            urgency: Urgency score (0-1)
            impact: Impact score (0-1)
            confidence: Confidence score (0-1)

        Returns:
            True if broadcast successful
        """
        if not self._gwt_broadcast:
            logger.warning("gwt_not_configured", agent=type(self).__name__)
            return False

        gwt_content = create_gwt_content(
            source_agent=getattr(self, "agent_id", "unknown"),
            content_type=content_type,
            payload=payload,
            novelty=novelty,
            relevance=relevance,
            urgency=urgency,
            impact=impact,
            confidence=confidence,
        )

        return await self._gwt_broadcast.broadcast_content(gwt_content)

    async def _broadcast_deliberation_outcome(
        self,
        result: DeliberationResult,
    ) -> bool:
        """
        Broadcast a deliberation outcome via GWT.

        Args:
            result: The deliberation result

        Returns:
            True if broadcast successful
        """
        if not self._gwt_deliberation_integrator:
            logger.warning("gwt_integrator_not_configured", agent=type(self).__name__)
            return False

        return await self._gwt_deliberation_integrator.broadcast_deliberation_result(result)

    async def receive_gwt_broadcast(self, content: Any) -> None:
        """
        Handle received GWT broadcast.

        Override this method in subclasses to handle broadcasts.

        Args:
            content: The GWT content received
        """
        logger.debug(
            "gwt_broadcast_received",
            content_type=content.content_type,
            source=content.source_agent,
            salience=content.salience_metrics.overall_salience,
        )

    async def receive_deliberation_broadcast(self, content: Any) -> None:
        """
        Handle received deliberation broadcast.

        Override this method in subclasses to handle deliberation broadcasts.

        Args:
            content: The GWT content with deliberation data
        """
        logger.debug(
            "deliberation_broadcast_received",
            deliberation_id=content.payload.get("deliberation_id"),
            proposal=content.payload.get("proposal", "")[:50],
        )


__all__ = [
    "DeliberationGWTIntegrator",
    "GWTDeliberationMixin",
    "GWTSalienceCalculator",
    "integrate_gwt_with_agent",
]
