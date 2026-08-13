"""
Sentinel-Prime Agent - Security Commander & Threat Response.

This module contains the SentinelPrimeAgent class which inherits from:
- SentinelPrimeHelpers (16 utility methods)
- SentinelPrimeHandlers (17 message handlers)
- HealthReportingMixin
- ValidationMixin
- DeliberationMixin
- PatternMixin
- MemoryMixin
- LearningMixin
- AgentActor

SAFE-02: External threat detection integration included.
"""

import re
from collections import defaultdict
from typing import TYPE_CHECKING, Any

import structlog

from heretek_swarm.actors.base import ActorMessage, AgentActor
from heretek_swarm.actors.mixins import (
    DeliberationMixin,
    HealthReportingMixin,
    LearningMixin,
    MemoryMixin,
    PatternMixin,
    ValidationMixin,
)
from heretek_swarm.security.threat_detection import (
    AlertPriority,
    ThreatDetectionConfig,
    create_default_detector,
)

from .handlers import SentinelPrimeHandlers
from .helpers import SentinelPrimeHelpers
from .types import (
    SecurityIncident,
    ThreatIndicator,
    ThreatLevel,
    ThreatType,
)

if TYPE_CHECKING:
    from datetime import datetime

logger = structlog.get_logger("SentinelPrimeAgent")


class SentinelPrimeAgent(
    SentinelPrimeHelpers,
    SentinelPrimeHandlers,
    HealthReportingMixin,
    ValidationMixin,
    DeliberationMixin,
    PatternMixin,
    MemoryMixin,
    LearningMixin,
    AgentActor,
):
    """
    Sentinel-Prime Agent - Security Commander for the Heretek Swarm Collective.

    Sentinel-Prime provides active threat detection, incident response, and
    security intelligence for the Collective.

    SAFE-02 External Threat Detection:
    - Detects external threats: prompt injection, DoS, exfiltration
    - Containment actions operational
    - False positive rate < 1%
    - Alert fatigue prevention via priority filtering
    - Automatic escalation to Core Triad
    """

    def __init__(
        self,
        agent_id: str | None = None,
        name: str = "Sentinel-Prime",
        description: str = "Security Commander - Threat Response",
        config: dict[str, Any] | None = None,
        db_pool: Any | None = None,
        redis_client: Any | None = None,
    ):
        super().__init__(
            agent_id=agent_id,
            name=name,
            description=description,
            config=config,
            db_pool=db_pool,
            redis_client=redis_client,
        )

        # Security configuration
        self._auto_response_enabled = config.get("auto_response_enabled", True) if config else True
        self._alert_threshold = (
            config.get("alert_threshold", ThreatLevel.MEDIUM.value)
            if config
            else ThreatLevel.MEDIUM.value
        )
        self._max_incidents = config.get("max_incidents", 5000) if config else 5000
        self._correlation_window = (
            config.get("correlation_window", 300) if config else 300
        )  # seconds

        # =====================================================================
        # SAFE-02: External Threat Detection
        # =====================================================================
        threat_config = ThreatDetectionConfig(
            min_detection_confidence=config.get("min_detection_confidence", 0.7) if config else 0.7,
            max_false_positive_rate=config.get("max_false_positive_rate", 0.01) if config else 0.01,
            default_alert_priority=AlertPriority.CRITICAL,
            auto_response_priorities={AlertPriority.CRITICAL},
            prompt_injection_enabled=config.get("prompt_injection_enabled", True)
            if config
            else True,
            exfiltration_detection_enabled=config.get("exfiltration_detection_enabled", True)
            if config
            else True,
            dos_detection_enabled=config.get("dos_detection_enabled", True) if config else True,
            core_triad_escalation_enabled=config.get("core_triad_escalation_enabled", True)
            if config
            else True,
            escalation_threshold_count=config.get("escalation_threshold_count", 5) if config else 5,
        )
        self._external_threat_detector = create_default_detector(threat_config)

        # Core Triad escalation configuration
        self._core_triad_escalation_enabled = (
            config.get("core_triad_escalation_enabled", True) if config else True
        )
        self._escalation_cooldown_seconds = (
            config.get("escalation_cooldown_seconds", 300) if config else 300
        )
        self._last_escalation_time: dict[str, datetime] = {}

        # Alert priority filtering state
        self._alert_priorities: dict[str, AlertPriority] = {}
        self._suppressed_alerts: dict[str, float] = {}  # source -> suppression_end_time

        # Security state
        self._incidents: dict[str, SecurityIncident] = {}
        self._incident_history: list[str] = []  # LRU keys
        self._threat_indicators: dict[str, ThreatIndicator] = {}
        self._indicator_cache: dict[str, ThreatIndicator] = {}  # LRU cache
        self._max_indicator_cache = 10000

        # Rate limiting state
        self._rate_limits: dict[str, dict[str, Any]] = {}
        self._blocked_sources: set[str] = set()
        self._isolated_actors: set[str] = set()

        # Statistics
        self._stats = {
            "total_incidents": 0,
            "incidents_by_level": defaultdict(int),
            "incidents_by_type": defaultdict(int),
            "auto_responses_triggered": 0,
            "manual_responses_triggered": 0,
            "threats_contained": 0,
            "threats_mitigated": 0,
            # SAFE-02 external threat stats
            "external_threats_detected": 0,
            "external_threats_contained": 0,
            "core_triad_escalations": 0,
            "alert_fatigue_suppressions": 0,
        }

        # Threat patterns
        self._attack_patterns = [
            (r"(?i)union\s+select", ThreatType.SQL_INJECTION),
            (r"(?i)or\s+1\s*=\s*1", ThreatType.SQL_INJECTION),
            (r"(?i)drop\s+table", ThreatType.SQL_INJECTION),
            (r"(?i)<script[^>]*>", ThreatType.XSS_ATTACK),
            (r"(?i)javascript:", ThreatType.XSS_ATTACK),
            (r"(?i)on\w+\s*=", ThreatType.XSS_ATTACK),
            (r"(?i)passwd|password|secret|api_key|token", ThreatType.DATA_EXFILTRATION),
            (r"(?i)/etc/passwd|/etc/shadow", ThreatType.UNAUTHORIZED_ACCESS),
            (r"(?i)\.\./", ThreatType.UNAUTHORIZED_ACCESS),
            (r"(?i)cmd\.exe|powershell|/bin/sh|/bin/bash", ThreatType.PRIVILEGE_ESCALATION),
        ]

        self._compiled_patterns = [
            (re.compile(pattern), threat_type) for pattern, threat_type in self._attack_patterns
        ]

        # Register handlers
        self._register_handlers()

        logger.info(
            "Sentinel-Prime Agent initialized",
            agent_id=self.agent_id,
            auto_response=self._auto_response_enabled,
            alert_threshold=self._alert_threshold,
            external_threat_detection_enabled=True,
            core_triad_escalation=self._core_triad_escalation_enabled,
        )

    async def process_message(self, message: ActorMessage) -> None:
        """Process incoming message with security validation."""
        try:
            handler = self._message_handlers.get(message.message_type)
            if handler:
                await handler(message)
            else:
                logger.warning(
                    "Unknown message type",
                    message_type=message.message_type,
                    sender=message.sender_id,
                )
        except Exception as e:
            logger.exception(
                "Error processing message",
                message_type=message.message_type,
                error=str(e),

            )
