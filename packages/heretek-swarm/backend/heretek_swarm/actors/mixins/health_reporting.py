"""HealthReportingMixin for agent health and error reporting."""

import asyncio
import time
from typing import Any

import structlog

logger = structlog.get_logger(__name__)

class HealthReportingMixin:
    """Mixin for health reporting and error handling.

    Extracted from 21+ actor files to remove ~880 lines of duplication.
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._error_count = 0
        self._last_health_check = 0.0
        self._health_status = "healthy"
        self._spawn_time = time.monotonic()

    def get_health_status(self) -> dict[str, Any]:
        """Get current health status."""
        return {
            "status": self._health_status,
            "error_count": self._error_count,
            "last_health_check": self._last_health_check,
            "agent_id": getattr(self, "agent_id", "unknown"),
            "uptime": time.monotonic() - self._spawn_time,
        }

    def record_error(self, error: Exception, context: dict[str, Any] | None = None) -> None:
        """Record an error for health tracking."""
        self._error_count += 1
        if self._error_count >= 10:
            self._health_status = "critical"
        elif self._error_count >= 5:
            self._health_status = "degraded"
        elif self._error_count >= 1:
            self._health_status = "warning"

        error_data = {
            "error_type": type(error).__name__,
            "error_message": str(error),
            "agent_id": getattr(self, "agent_id", "unknown"),
            "context": context or {},
        }
        self.logger.error(
            f"Agent error: {error_data['error_type']} - {error_data['error_message']}",
            extra=error_data,
        )

    def reset_error_count(self) -> None:
        """Reset error count after recovery."""
        self._error_count = 0
        self._health_status = "healthy"

    async def health_check(self) -> dict[str, Any]:
        """Perform health check."""
        self._last_health_check = asyncio.get_event_loop().time()
        health_data = self.get_health_status()
        subsystem_health = {}

        if hasattr(self, "_memory_system"):
            subsystem_health["memory"] = await self._check_memory_health()
        if hasattr(self, "_consensus_client"):
            subsystem_health["consensus"] = await self._check_consensus_health()
        if hasattr(self, "_pattern_client"):
            subsystem_health["patterns"] = await self._check_pattern_health()

        health_data["subsystems"] = subsystem_health

        await self._emit_pattern(pattern_type="health_report", data=health_data)
        return health_data

    async def _check_memory_health(self) -> bool:
        """Check memory subsystem health."""
        try:
            if hasattr(self, "_memory_system"):
                await self._memory_system.ping()
                return True
        except Exception:
            return False
        return True

    async def _check_consensus_health(self) -> bool:
        """Check consensus subsystem health."""
        try:
            if hasattr(self, "_consensus_client"):
                return self._consensus_client.is_connected()
        except Exception:
            return False
        return True

    async def _check_pattern_health(self) -> bool:
        """Check pattern subsystem health."""
        try:
            if hasattr(self, "_pattern_client"):
                return self._pattern_client.is_connected()
        except Exception:
            return False
        return True

    def get_error_history(self, _limit: int = 10) -> list[dict[str, Any]]:
        """Get recent error history."""
        return [
            {
                "agent_id": getattr(self, "agent_id", "unknown"),
                "total_errors": self._error_count,
                "status": self._health_status,
            }
        ]
