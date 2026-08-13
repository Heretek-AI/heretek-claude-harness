"""
Handoff handlers — phased handler chain for agent-to-agent handoff processing.

Extracted from the original actors/handoff_handlers.py minus the duplicate
HandoffContext and HandoffResult definitions which now live in
heretek_swarm.actors.handoff.types.
"""

from datetime import UTC, datetime
from typing import Any

import structlog

from heretek_swarm.actors.handoff.types import HandoffResult

logger = structlog.get_logger(__name__)


class HandoffValidationHandler:
    """Handler for handoff validation phase"""

    def __init__(self, validator: Any):
        self._validator = validator

    async def validate(
        self, from_agent_id: str, to_agent_id: str, context: dict[str, Any]
    ) -> tuple[bool, str | None]:
        """Validate handoff request"""
        try:
            self._validator.validate(from_agent_id, to_agent_id, context)
            return True, None
        except ValueError as e:
            logger.error("handoff_validation_failed", error=str(e))
            return False, f"Validation failed: {e!s}"


class HandoffRateLimitHandler:
    """Handler for handoff rate limiting"""

    def __init__(self, handoff_timestamps: list[Any], max_per_minute: int = 10):
        self._handoff_timestamps = handoff_timestamps
        self.MAX_HANDOFFS_PER_MINUTE = max_per_minute

    async def check_rate_limit(self) -> tuple[bool, str | None]:
        """Check if rate limit is exceeded"""
        now = datetime.now(UTC)
        one_minute_ago = now.replace(microsecond=0)

        # Remove old timestamps
        self._handoff_timestamps[:] = [ts for ts in self._handoff_timestamps if ts > one_minute_ago]

        # Check limit
        if len(self._handoff_timestamps) >= self.MAX_HANDOFFS_PER_MINUTE:
            error = f"Rate limit exceeded: max {self.MAX_HANDOFFS_PER_MINUTE} handoffs per minute"
            logger.error("handoff_rate_limit_exceeded", error=error)
            return False, error

        # Record this handoff
        self._handoff_timestamps.append(now)
        return True, None


class HandoffTransferHandler:
    """Handler for context transfer between agents"""

    def __init__(self, supervisor_getter: Any, actor_message_class: Any):
        self._get_supervisor = supervisor_getter
        self._ActorMessage = actor_message_class

    async def transfer_context(
        self,
        handoff_id: str,
        from_agent_id: str,
        to_agent_id: str,
        context: dict[str, Any],
        reason: str,
        timestamp: str,
    ) -> tuple[bool, str | None]:
        """Transfer context to destination agent"""
        supervisor = self._get_supervisor()

        if supervisor and to_agent_id in supervisor.actors:
            destination_actor = supervisor.actors[to_agent_id]

            await destination_actor.put_message(
                self._ActorMessage(
                    sender=from_agent_id,
                    message_type="handoff_request",
                    content={
                        "handoff_id": handoff_id,
                        "from_agent": from_agent_id,
                        "context": context,
                        "reason": reason,
                        "timestamp": timestamp,
                    },
                    timestamp=timestamp,
                    correlation_id=handoff_id,
                )
            )

            logger.info("handoff_context_transferred", handoff_id=handoff_id, to_agent=to_agent_id)
            return True, None

        logger.warning("handoff_destination_not_found", handoff_id=handoff_id, to_agent=to_agent_id)
        return False, f"Destination agent {to_agent_id} not found"


class HandoffLoggingHandler:
    """Handler for historian logging"""

    def __init__(self, historian: Any | None = None):
        self._historian = historian

    async def log_handoff(
        self,
        handoff_id: str,
        from_agent_id: str,
        to_agent_id: str,
        reason: str,
        timestamp: str,
        context: dict[str, Any],
    ) -> None:
        """Log handoff to historian"""
        if self._historian and hasattr(self._historian, "log_event"):
            await self._historian.log_event(
                event_type="agent_handoff",
                data={
                    "handoff_id": handoff_id,
                    "from_agent": from_agent_id,
                    "to_agent": to_agent_id,
                    "reason": reason,
                    "timestamp": timestamp,
                    "context_keys": list(context.keys()),
                },
            )


class HandoffProcessor:
    """Main processor that chains all handoff handlers"""

    def __init__(
        self,
        validator: Any,
        handoff_timestamps: list[Any],
        supervisor_getter: Any,
        actor_message_class: Any,
        historian: Any | None = None,
        max_active_handoffs: int = 100,
    ):
        self._validation_handler = HandoffValidationHandler(validator)
        self._rate_limit_handler = HandoffRateLimitHandler(handoff_timestamps)
        self._transfer_handler = HandoffTransferHandler(supervisor_getter, actor_message_class)
        self._logging_handler = HandoffLoggingHandler(historian)
        self.MAX_ACTIVE_HANDOFFS = max_active_handoffs

    async def process(
        self,
        from_agent_id: str,
        to_agent_id: str,
        context: dict[str, Any],
        reason: str,
        active_handoffs_count: int,
    ) -> HandoffResult:
        """Process handoff through all phases"""
        import uuid

        # Phase 1: Validation
        is_valid, error = await self._validation_handler.validate(
            from_agent_id, to_agent_id, context
        )
        if not is_valid:
            return HandoffResult(success=False, handoff_id="", error=error)

        # Phase 2: Rate limiting
        is_allowed, error = await self._rate_limit_handler.check_rate_limit()
        if not is_allowed:
            return HandoffResult(success=False, handoff_id="", error=error)

        # Phase 3: Active handoffs limit
        if active_handoffs_count >= self.MAX_ACTIVE_HANDOFFS:
            error = f"Maximum active handoffs exceeded ({self.MAX_ACTIVE_HANDOFFS})"
            logger.error("handoff_limit_exceeded", active_count=active_handoffs_count)
            return HandoffResult(success=False, handoff_id="", error=error)

        # Generate handoff ID and timestamp
        handoff_id = str(uuid.uuid4())
        timestamp = datetime.now(UTC).isoformat()

        logger.info(
            "handoff_initiated",
            handoff_id=handoff_id,
            from_agent=from_agent_id,
            to_agent=to_agent_id,
            reason=reason,
        )

        # Phase 4: Context transfer
        transfer_success, transfer_error = await self._transfer_handler.transfer_context(
            handoff_id, from_agent_id, to_agent_id, context, reason, timestamp
        )

        # Phase 5: Logging (regardless of transfer success)
        await self._logging_handler.log_handoff(
            handoff_id, from_agent_id, to_agent_id, reason, timestamp, context
        )

        if transfer_success:
            logger.info("handoff_completed", handoff_id=handoff_id, status="success")
            return HandoffResult(success=True, handoff_id=handoff_id, error=None)

        return HandoffResult(success=False, handoff_id=handoff_id, error=transfer_error)
