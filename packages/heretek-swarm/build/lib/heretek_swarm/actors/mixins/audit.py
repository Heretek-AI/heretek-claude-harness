"""AuditMixin for Zero-Trust comprehensive audit trails (ZERO-03).

This mixin provides audit logging capabilities for all agent actions:
- Message send/receive events
- State change events
- Decision events
- Custom action logging

Usage:
    class MyAgent(AuditMixin, OtherMixin, AgentActor):
        ...

The mixin automatically logs:
- All incoming messages
- All outgoing messages
- State transitions
- Handler execution
"""

from typing import Any

import structlog

from heretek_swarm.infrastructure.audit import AuditEntry, get_audit_logger

logger = structlog.get_logger("AuditMixin")


class AuditMixin:
    """Mixin for Zero-Trust audit trail logging (ZERO-03)."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # Get audit logger (may not be initialized yet)
        try:
            self._audit_logger = get_audit_logger()
        except RuntimeError:
            self._audit_logger = None

        # Audit configuration
        self._audit_enabled: bool = self._get_config_value("audit_enabled", True)
        self._audit_actions: list[str] = self._get_config_value(
            "audit_actions",
            [
                "message_received",
                "message_sent",
                "state_change",
                "handler_executed",
                "decision_made",
            ],
        )

        # Audit statistics
        self._audit_stats = {
            "entries_logged": 0,
            "entries_failed": 0,
        }

        logger.info(
            "zero03_audit_mixin_initialized",
            agent_id=getattr(self, "agent_id", "unknown"),
            audit_enabled=self._audit_enabled,
        )

    def _get_config_value(self, key: str, default: Any) -> Any:
        """Get configuration value from agent config or default."""
        if hasattr(self, "_config") and self._config:
            return self._config.get(key, default)
        return default

    def _audit(
        self,
        action_type: str,
        input_data: Any | None = None,
        output_data: Any | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> AuditEntry | None:
        """
        ZERO-03: Log an action to the audit trail.

        Args:
            action_type: Type of action being logged
            input_data: Optional input data
            output_data: Optional output data
            metadata: Optional additional metadata

        Returns:
            AuditEntry if successful, None if audit disabled or failed
        """
        if not self._audit_enabled:
            return None

        if self._audit_logger is None:
            # Try to get audit logger again (may have been initialized)
            try:
                self._audit_logger = get_audit_logger()
            except RuntimeError:
                logger.warning(
                    "zero03_audit_logger_not_initialized",
                    agent_id=getattr(self, "agent_id", "unknown"),
                    action_type=action_type,
                )
                return None

        try:
            # Merge agent-specific metadata
            full_metadata = {
                "actor_type": getattr(self, "actor_type", "AgentActor"),
                "agent_name": getattr(self, "name", "unknown"),
                **(metadata or {}),
            }

            entry = self._audit_logger.log(
                actor_id=getattr(self, "agent_id", "unknown"),
                action_type=action_type,
                input_data=input_data,
                output_data=output_data,
                metadata=full_metadata,
            )

            self._audit_stats["entries_logged"] += 1
            return entry

        except Exception as e:
            logger.error(
                "zero03_audit_log_failed",
                agent_id=getattr(self, "agent_id", "unknown"),
                action_type=action_type,
                error=str(e),
            )
            self._audit_stats["entries_failed"] += 1
            return None

    def _audit_message_received(self, message_type: str, content: dict[str, Any]) -> None:
        """Log incoming message."""
        self._audit(
            action_type="message_received",
            input_data={"message_type": message_type, "content": content},
            metadata={"sender": getattr(self, "_last_sender", "unknown")},
        )

    def _audit_message_sent(
        self,
        topic: str,
        message_type: str,
        content: dict[str, Any],
    ) -> None:
        """Log outgoing message."""
        self._audit(
            action_type="message_sent",
            input_data={"topic": topic, "message_type": message_type, "content": content},
        )

    def _audit_state_change(
        self,
        old_state: str,
        new_state: str,
        reason: str | None = None,
    ) -> None:
        """Log state transition."""
        self._audit(
            action_type="state_change",
            input_data={"old_state": old_state, "reason": reason},
            output_data={"new_state": new_state},
            metadata={"transition": f"{old_state} -> {new_state}"},
        )

    def _audit_handler_executed(
        self,
        handler_name: str,
        message_type: str,
        result: Any | None = None,
    ) -> None:
        """Log handler execution."""
        self._audit(
            action_type="handler_executed",
            input_data={"handler": handler_name, "message_type": message_type},
            output_data={"result": result},
        )

    def _audit_decision_made(
        self,
        decision_type: str,
        decision_data: dict[str, Any],
        context: dict[str, Any] | None = None,
    ) -> None:
        """Log decision made by agent."""
        self._audit(
            action_type="decision_made",
            input_data={"decision_type": decision_type, "context": context or {}},
            output_data=decision_data,
            metadata={"decision_category": decision_type},
        )

    def _audit_validation_result(
        self,
        validation_type: str,
        is_valid: bool,
        details: dict[str, Any] | None = None,
    ) -> None:
        """Log validation result (ZERO-02 integration)."""
        self._audit(
            action_type="validation_performed",
            input_data={"validation_type": validation_type},
            output_data={"is_valid": is_valid, "details": details or {}},
        )

    def get_audit_stats(self) -> dict[str, Any]:
        """Get audit statistics for this agent."""
        return {
            **self._audit_stats,
            "audit_enabled": self._audit_enabled,
            "audit_actions": self._audit_actions,
            "agent_id": getattr(self, "agent_id", "unknown"),
        }

    def set_audit_enabled(self, enabled: bool) -> None:
        """Enable or disable audit logging for this agent."""
        self._audit_enabled = enabled
        logger.info(
            "audit_enabled_changed",
            agent_id=getattr(self, "agent_id", "unknown"),
            enabled=enabled,
        )


# Helper function to wrap message handling with audit logging
def audit_messages_wrapper(cls):
    """Decorator to add audit logging to message handling.

    Usage:
        @audit_messages_wrapper
        class MyAgent(AuditMixin, AgentActor):
            ...
    """
    original_process_message = cls.process_message if hasattr(cls, "process_message") else None

    async def audited_process_message(self, message):
        # Log message received
        if hasattr(self, "_audit_message_received"):
            self._audit_message_received(
                message_type=message.message_type,
                content=message.content,
            )

        # Call original handler
        result = None
        if original_process_message:
            result = await original_process_message(self, message)

        return result

    if original_process_message:
        cls.process_message = audited_process_message

    return cls
