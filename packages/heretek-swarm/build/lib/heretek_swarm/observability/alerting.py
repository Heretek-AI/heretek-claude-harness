"""
Alerting System for Heretek Swarm

Provides structured alerting with PagerDuty and OpsGenie integration.

Alert Severity Levels:
- CRITICAL: Immediate attention required (system down)
- HIGH: Serious issue requiring attention
- MEDIUM: Moderate issue, should be addressed
- LOW: Minor issue, can be addressed later

Alert Sources:
- Agent health check failures
- Consensus failures
- API error rate thresholds
- Memory/database connection issues
- Phi score anomalies
- Free energy spikes

Author: Heretek Swarm Collective
Date: 2026-04-10
"""

import os
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

import structlog

logger = structlog.get_logger("alerting")


# Alert severity levels
class AlertSeverity(StrEnum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class AlertStatus(StrEnum):
    FIRING = "firing"
    RESOLVED = "resolved"
    ACKNOWLEDGED = "acknowledged"


@dataclass
class Alert:
    """Represents an alert in the system."""

    alert_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    severity: AlertSeverity = AlertSeverity.MEDIUM
    title: str = ""
    description: str = ""
    source: str = ""  # Component that triggered the alert
    status: AlertStatus = AlertStatus.FIRING
    timestamp: str = field(default_factory=lambda: datetime.now(UTC).isoformat())
    resolved_at: str | None = None
    acknowledged_at: str | None = None
    acknowledged_by: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    tags: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "alert_id": self.alert_id,
            "severity": self.severity.value,
            "title": self.title,
            "description": self.description,
            "source": self.source,
            "status": self.status.value,
            "timestamp": self.timestamp,
            "resolved_at": self.resolved_at,
            "acknowledged_at": self.acknowledged_at,
            "acknowledged_by": self.acknowledged_by,
            "metadata": self.metadata,
            "tags": self.tags,
        }


class AlertManager:
    """
    Central alert management with PagerDuty/OpsGenie integration.
    """

    def __init__(self):
        self._alerts: dict[str, Alert] = {}
        self._alert_history: list[Alert] = []
        self._pagerduty_enabled = bool(os.getenv("PAGERDUTY_API_KEY"))
        self._opsgenie_enabled = bool(os.getenv("OPSGENIE_API_KEY"))
        self._integration = os.getenv(
            "ALERT_INTEGRATION", "none"
        )  # pagerduty, opsgenie, both, none

    async def send_alert(self, alert: Alert) -> bool:
        """Send an alert through configured integration."""
        logger.info(
            "alert_triggered",
            alert_id=alert.alert_id,
            severity=alert.severity.value,
            title=alert.title,
            source=alert.source,
        )

        # Store alert
        self._alerts[alert.alert_id] = alert

        # Send to integrations
        success = True
        if self._integration in ("pagerduty", "both") and self._pagerduty_enabled:
            success = success and await self._send_pagerduty(alert)
        if self._integration in ("opsgenie", "both") and self._opsgenie_enabled:
            success = success and await self._send_opsgenie(alert)

        return success

    async def _send_pagerduty(self, alert: Alert) -> bool:
        """Send alert to PagerDuty Events API v2."""
        try:
            import aiohttp

            pd_urgency = (
                "high" if alert.severity in (AlertSeverity.CRITICAL, AlertSeverity.HIGH) else "low"
            )

            payload = {
                "routing_key": os.getenv("PAGERDUTY_API_KEY"),
                "event_action": "trigger",
                "payload": {
                    "summary": alert.title,
                    "source": f"heretek-swarm:{alert.source}",
                    "severity": pd_urgency,
                    "custom_details": {
                        "description": alert.description,
                        "alert_id": alert.alert_id,
                        "metadata": alert.metadata,
                    },
                },
            }

            async with (
                aiohttp.ClientSession() as session,
                session.post(
                    "https://events.pagerduty.com/v2/enqueue",
                    json=payload,
                    headers={"Content-Type": "application/json"},
                ) as resp,
            ):
                if resp.status == 202:
                    logger.info("pagerduty_alert_sent", alert_id=alert.alert_id)
                    return True
                logger.error("pagerduty_alert_failed", status=resp.status)
                return False
        except Exception as e:
            logger.error("pagerduty_alert_error", error=str(e))
            return False

    async def _send_opsgenie(self, alert: Alert) -> bool:
        """Send alert to OpsGenie Alerts API."""
        try:
            import aiohttp

            opsgenie_priority = (
                "P1"
                if alert.severity == AlertSeverity.CRITICAL
                else "P2"
                if alert.severity == AlertSeverity.HIGH
                else "P3"
                if alert.severity == AlertSeverity.MEDIUM
                else "P4"
            )

            payload = {
                "message": alert.title,
                "description": alert.description,
                "priority": opsgenie_priority,
                "tags": alert.tags,
                "extra_properties": {
                    "alert_id": alert.alert_id,
                    "source": alert.source,
                    **alert.metadata,
                },
            }

            headers = {
                "Content-Type": "application/json",
                "Authorization": f"GenieKey {os.getenv('OPSGENIE_API_KEY')}",
            }

            async with (
                aiohttp.ClientSession() as session,
                session.post(
                    "https://api.opsgenie.com/v2/alerts",
                    json=payload,
                    headers=headers,
                ) as resp,
            ):
                if resp.status == 202:
                    logger.info("opsgenie_alert_sent", alert_id=alert.alert_id)
                    return True
                logger.error("opsgenie_alert_failed", status=resp.status)
                return False
        except Exception as e:
            logger.error("opsgenie_alert_error", error=str(e))
            return False

    async def resolve_alert(self, alert_id: str, resolved_by: str = "system") -> bool:
        """Resolve an alert."""
        if alert_id not in self._alerts:
            return False

        alert = self._alerts[alert_id]
        alert.status = AlertStatus.RESOLVED
        alert.resolved_at = datetime.now(UTC).isoformat()

        # Move to history
        self._alert_history.append(alert)
        del self._alerts[alert_id]

        logger.info("alert_resolved", alert_id=alert_id, resolved_by=resolved_by)
        return True

    def get_active_alerts(self) -> list[Alert]:
        """Get all active (firing) alerts."""
        return list(self._alerts.values())

    def get_alert_history(self, limit: int = 100) -> list[Alert]:
        """Get alert history."""
        return self._alert_history[-limit:]

    async def check_and_alert(
        self,
        check_type: str,
        value: float,
        threshold: float,
        severity: AlertSeverity,
        title: str,
        description: str,
        source: str,
    ) -> Alert | None:
        """Check a value against threshold and alert if exceeded."""
        if (
            (check_type == "above" and value > threshold)
            or (check_type == "below" and value < threshold)
            or (check_type == "equals" and abs(value - threshold) < 0.001)
        ):
            pass  # Alert
        else:
            return None  # No alert needed

        alert = Alert(
            severity=severity,
            title=title,
            description=description,
            source=source,
            metadata={"value": value, "threshold": threshold, "check_type": check_type},
        )
        await self.send_alert(alert)
        return alert


# Global alert manager instance
_alert_manager: AlertManager | None = None


def get_alert_manager() -> AlertManager:
    """Get the global alert manager instance."""
    global _alert_manager
    if _alert_manager is None:
        _alert_manager = AlertManager()
    return _alert_manager
