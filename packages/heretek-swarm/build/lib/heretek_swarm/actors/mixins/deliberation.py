"""DeliberationMixin for consensus-based decision making."""

import asyncio
from typing import Any

import structlog

logger = structlog.get_logger(__name__)

class DeliberationMixin:
    """Mixin for consensus deliberation methods.

    Extracted from 21 actor files to remove ~735 lines of duplication.
    """

    _deliberation_active: bool = False
    _deliberation_id: str | None = None
    _deliberation_position: dict[str, Any] | None = None

    @property
    def is_deliberating(self) -> bool:
        """Check if currently in deliberation."""
        return self._deliberation_active

    async def _initiate_deliberation(
        self,
        topic: str,
        options: list[str],  # noqa: ARG002
    ) -> str:
        """Initiate a new deliberation.

        Args:
            topic: The topic to deliberate
            options: List of options to choose from

        Returns:
            deliberation_id: Unique ID for this deliberation
        """
        self._deliberation_active = True
        self._deliberation_id = f"delib_{hash(topic) % 1000000}"
        self._deliberation_position = None
        return self._deliberation_id

    async def _submit_deliberation_position(
        self,
        deliberation_id: str,
        position: dict[str, Any],
        rationale: str = "",  # noqa: ARG002
        timeout: float = 30.0,  # noqa: ASYNC109
    ) -> dict[str, Any] | None:
        """Submit position to consensus deliberation.

        Args:
            deliberation_id: The deliberation ID to submit to
            position: The position/proposal to submit
            rationale: The rationale for this position
            timeout: Timeout in seconds for deliberation

        Returns:
            Consensus result if reached, None if timeout
        """
        # Validate we're in the right deliberation
        if self._deliberation_id != deliberation_id:
            return False

        try:
            await self._publish_position(position, deliberation_id)
            result = await asyncio.wait_for(
                self._wait_for_consensus(deliberation_id), timeout=timeout
            )
            self._deliberation_position = position
            return result
        except TimeoutError:
            self.logger.warning(
                f"Consensus timeout for round {deliberation_id}",  # noqa: G004
                extra={"deliberation_id": deliberation_id},
            )
            return None
        except Exception as e:
            self.logger.error(
                f"Error submitting deliberation position: {e}",  # noqa: G004
                extra={"deliberation_id": deliberation_id},
            )
            return None

    async def _finalize_deliberation(
        self, deliberation_id: str, binding: bool = True  # noqa: ARG002
    ) -> dict[str, Any]:
        """Finalize deliberation and apply consensus.

        Args:
            deliberation_id: The deliberation ID to finalize
            binding: Whether consensus is binding on this agent

        Returns:
            Finalized decision with metadata
        """
        finalized = {
            "decision": None,
            "confidence": 0.0,
            "participation_rate": 0.0,
            "binding": binding,
            "timestamp": asyncio.get_event_loop().time(),
            "success": True,
        }

        if binding:
            await self._apply_consensus_decision(finalized)

        await self._emit_pattern(pattern_type="consensus_decision", data=finalized)

        self._deliberation_active = False
        self._deliberation_id = None
        return finalized

    def _get_deliberation_status(self) -> dict[str, Any]:
        """Get current deliberation status."""
        return {
            "active": self._deliberation_active,
            "deliberation_id": self._deliberation_id,
            "position": self._deliberation_position,
        }

    async def _publish_position(self, position: dict[str, Any], deliberation_id: str) -> None:
        """Publish position to consensus channel."""
        if hasattr(self, "_consensus_publisher"):
            await self._consensus_publisher.publish(
                channel=f"consensus:{deliberation_id}", message=position
            )

    async def _wait_for_consensus(self, deliberation_id: str) -> dict[str, Any]:
        """Wait for consensus result."""
        if hasattr(self, "_consensus_subscriber"):
            return await self._consensus_subscriber.subscribe(
                channel=f"consensus:{deliberation_id}"
            )
        return {"decision": None, "confidence": 0.0}

    async def _apply_consensus_decision(self, decision: dict[str, Any]) -> None:
        """Apply consensus decision to agent state."""
        if hasattr(self, "state"):
            self.state["last_consensus_decision"] = decision
