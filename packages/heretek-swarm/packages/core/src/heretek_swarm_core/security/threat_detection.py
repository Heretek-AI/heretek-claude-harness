"""
External Threat Detection Module for Sentinel-Prime (SAFE-02).

Provides comprehensive detection and response for external threats:
- Prompt Injection Detection (leveraging adversarial.py)
- Denial of Service (DoS) Detection (leveraging ddos_protection.py)
- Data Exfiltration Detection
- Threat Intelligence Correlation
- Automated Containment Actions
- False Positive Rate < 1% Target

Features:
- Priority filtering for alert fatigue prevention
- Critical alerts only by default
- Automatic escalation to Core Triad
- Multi-source threat intelligence aggregation

Reference: Phase 2 Plan Task 5 (SAFE-02)
"""

import hashlib
import re
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

import structlog

from heretek_swarm_core.security.adversarial import (
    ThreatLevel,
)
from heretek_swarm_core.security.adversarial import (
    create_default_detector as create_adversarial_detector,
)
from heretek_swarm_core.security.ddos_protection import (
    RateLimitConfig,
    RateLimiter,
)
from heretek_swarm_core.security.ddos_protection import (
    create_default_protection as create_ddos_protection,
)

logger = structlog.get_logger("threat_detection")


# =============================================================================
# Threat Classification Enums
# =============================================================================


class ExternalThreatType(StrEnum):
    """Types of external threats."""

    PROMPT_INJECTION = "prompt_injection"
    DOS_ATTACK = "dos_attack"
    DATA_EXFILTRATION = "data_exfiltration"
    BRUTE_FORCE = "brute_force"
    CREDENTIAL_STUFFING = "credential_stuffing"
    SQL_INJECTION = "sql_injection"
    XSS_ATTACK = "xss_attack"
    PATH_TRAVERSAL = "path_traversal"
    API_ABUSE = "api_abuse"
    RATE_VIOLATION = "rate_violation"


class ThreatSource(StrEnum):
    """Source of the threat."""

    EXTERNAL_API = "external_api"
    INTERNAL_AGENT = "internal_agent"
    GATEWAY = "gateway"
    UNKNOWN = "unknown"


class ContainmentAction(StrEnum):
    """Containment actions for external threats."""

    ALERT = "alert"
    BLOCK_IP = "block_ip"
    RATE_LIMIT = "rate_limit"
    QUARANTINE = "quarantine"
    ISOLATE_AGENT = "isolate_agent"
    ESCALATE = "escalate"
    LOG_ONLY = "log_only"


class AlertPriority(StrEnum):
    """Alert priority levels for filtering."""

    CRITICAL = "critical"  # Only critical alerts fire auto-response
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFO = "info"


# =============================================================================
# Configuration
# =============================================================================


@dataclass
class ThreatDetectionConfig:
    """Configuration for threat detection system."""

    # Detection thresholds
    min_detection_confidence: float = 0.7  # Minimum confidence to trigger alert
    max_false_positive_rate: float = 0.01  # < 1% false positive rate target

    # Alert priority filtering
    default_alert_priority: AlertPriority = AlertPriority.CRITICAL
    auto_response_priorities: set[AlertPriority] = field(
        default_factory=lambda: {AlertPriority.CRITICAL}
    )

    # DoS detection
    dos_detection_enabled: bool = True
    dos_spike_multiplier: float = 10.0

    # Prompt injection detection
    prompt_injection_enabled: bool = True
    prompt_injection_min_confidence: float = 0.5

    # Exfiltration detection
    exfiltration_detection_enabled: bool = True
    exfiltration_keywords: list[str] = field(
        default_factory=lambda: [
            "password",
            "secret",
            "api_key",
            "token",
            "credential",
            "private_key",
            "access_token",
            "auth_token",
            "ssn",
            "credit_card",
            "social_security",
        ]
    )

    # Rate limiting
    rate_limit_enabled: bool = True
    max_requests_per_minute: int = 100

    # Core Triad escalation
    core_triad_escalation_enabled: bool = True
    escalation_threshold_count: int = 5  # Escalate after 5+ threats
    escalation_cooldown_seconds: int = 300  # 5 minutes between escalations


@dataclass
class ThreatDetectionResult:
    """Result of threat detection analysis."""

    threat_id: str
    threat_type: ExternalThreatType
    threat_level: ThreatLevel
    priority: AlertPriority
    confidence: float
    source: str
    target: str | None
    indicators: list[dict[str, Any]]
    containment_actions: list[ContainmentAction]
    auto_responded: bool
    false_positive_likelihood: float  # 0.0 = definitely not FP, 1.0 = definitely FP
    timestamp: datetime
    details: dict[str, Any] = field(default_factory=dict)


@dataclass
class ThreatIntelligence:
    """Aggregated threat intelligence."""

    total_threats: int
    threats_by_type: dict[str, int]
    threats_by_source: dict[str, int]
    active_blocked_sources: int
    rate_limited_sources: int
    last_detection_time: datetime | None
    top_indicators: list[dict[str, Any]]
    recommendations: list[str]


# =============================================================================
# Threat Detector Implementation
# =============================================================================


class ExternalThreatDetector:
    """
    Comprehensive external threat detection system.

    Detects and responds to external threats including:
    - Prompt injection attacks
    - Denial of Service (DoS) attacks
    - Data exfiltration attempts
    - API abuse and rate violations

    Target: False positive rate < 1%
    """

    def __init__(
        self,
        config: ThreatDetectionConfig | None = None,
    ):
        self.config = config or ThreatDetectionConfig()

        # Initialize component detectors
        self._adversarial_detector = create_adversarial_detector()
        self._ddos_protection = create_ddos_protection()

        # Rate limiter for threat detection itself
        self._rate_limiter = RateLimiter(
            config=RateLimitConfig(
                enable_token_bucket=True,
                enable_sliding_window=True,
                enable_redis_backend=False,
            )
        )

        # Threat tracking
        self._threat_history: list[ThreatDetectionResult] = []
        self._max_threat_history = 10000

        # Blocked/rate-limited sources
        self._blocked_sources: dict[str, datetime] = {}
        self._rate_limited_sources: dict[str, dict[str, Any]] = {}

        # Statistics
        self._stats = {
            "total_detections": 0,
            "true_positives": 0,
            "false_positives": 0,
            "auto_responses": 0,
            "escalations_to_triad": 0,
            "blocked_sources": 0,
        }

        # Core Triad escalation tracking
        self._escalation_count: dict[str, int] = defaultdict(int)
        self._last_escalation_time: dict[str, datetime] = {}

        # False positive tracking for learning
        self._fp_likelihood_cache: dict[str, float] = {}

        logger.info(
            "external_threat_detector_initialized",
            config={
                "min_detection_confidence": self.config.min_detection_confidence,
                "max_false_positive_rate": self.config.max_false_positive_rate,
                "default_priority": self.config.default_alert_priority.value,
            },
        )

    async def detect_threat(
        self,
        content: str,
        source: str,
        target: str | None = None,
        threat_type: ExternalThreatType | None = None,
        context: dict[str, Any] | None = None,
    ) -> ThreatDetectionResult | None:
        """
        Detect external threats in content.

        Args:
            content: Content to analyze
            source: Source identifier (IP, agent ID, etc.)
            target: Target identifier (optional)
            threat_type: Specific threat type to check (optional)
            context: Additional context

        Returns:
            ThreatDetectionResult if threat detected, None otherwise
        """
        context = context or {}
        indicators = []
        threat_types_detected = []

        # Check rate limits first
        rate_result = await self._rate_limiter.check_rate_limit(
            identifier=source,
            tier=RateLimitConfig().tiers.get("authenticated"),
        )

        if not rate_result.allowed:
            # Source is rate limited - check if it crosses threshold
            return await self._create_threat_detection(
                threat_type=ExternalThreatType.RATE_VIOLATION,
                level=ThreatLevel.MEDIUM,
                source=source,
                target=target,
                confidence=0.8,
                indicators=[{"type": "rate_limit", "details": rate_result.to_headers()}],
                context=context,
            )

        # 1. Prompt Injection Detection
        if self.config.prompt_injection_enabled:
            injection_result = self._adversarial_detector.detect(content)
            if injection_result.is_malicious:
                threat_types_detected.append(ExternalThreatType.PROMPT_INJECTION)
                indicators.append(
                    {
                        "type": "prompt_injection",
                        "confidence": injection_result.confidence,
                        "categories": [c.value for c in injection_result.categories],
                        "matches": len(injection_result.matches),
                    }
                )

        # 2. Data Exfiltration Detection
        if self.config.exfiltration_detection_enabled:
            exfil_indicators = self._detect_exfiltration(content)
            if exfil_indicators:
                threat_types_detected.append(ExternalThreatType.DATA_EXFILTRATION)
                indicators.extend(exfil_indicators)

        # 3. DoS Attack Detection (via DDoS protection)
        if self.config.dos_detection_enabled and threat_type == ExternalThreatType.DOS_ATTACK:
            ddos_result = self._ddos_protection.detector.detect()
            if ddos_result.is_attack:
                threat_types_detected.append(ExternalThreatType.DOS_ATTACK)
                indicators.append(
                    {
                        "type": "dos_attack",
                        "severity": ddos_result.severity.value,
                        "affected_ips": ddos_result.affected_ips,
                        "attack_types": ddos_result.attack_type,
                    }
                )

        # 4. SQL Injection Detection
        sql_patterns = [
            (r"union\s+select", 0.9),
            (r"or\s+1\s*=\s*1", 0.85),
            (r"drop\s+table", 0.95),
            (r";\s*shutdown", 0.9),
        ]
        for pattern, confidence in sql_patterns:
            if re.search(pattern, content, re.IGNORECASE):
                threat_types_detected.append(ExternalThreatType.SQL_INJECTION)
                indicators.append(
                    {
                        "type": "sql_injection",
                        "pattern": pattern,
                        "confidence": confidence,
                    }
                )
                break

        # 5. Path Traversal Detection
        path_patterns = [
            (r"\.\./", 0.9),
            (r"\.\.\\", 0.9),
            (r"%2e%2e", 0.85),
        ]
        for pattern, confidence in path_patterns:
            if re.search(pattern, content, re.IGNORECASE):
                threat_types_detected.append(ExternalThreatType.PATH_TRAVERSAL)
                indicators.append(
                    {
                        "type": "path_traversal",
                        "pattern": pattern,
                        "confidence": confidence,
                    }
                )
                break

        # If no threats detected, return None
        if not threat_types_detected:
            return None

        # Calculate overall threat level
        max_confidence = max(ind.get("confidence", 0) for ind in indicators) if indicators else 0
        level = self._calculate_threat_level(max_confidence, len(threat_types_detected))
        priority = self._calculate_priority(level, max_confidence)

        # Calculate false positive likelihood
        fp_likelihood = self._calculate_fp_likelihood(
            source=source,
            indicators=indicators,
            threat_types=threat_types_detected,
        )

        # Skip if likely false positive (above threshold)
        if fp_likelihood > self.config.max_false_positive_rate:
            self._stats["false_positives"] += 1
            logger.info(
                "threat_marked_as_fp",
                source=source,
                fp_likelihood=fp_likelihood,
            )
            return None

        # Create detection result
        result = await self._create_threat_detection(
            threat_type=threat_types_detected[0],
            level=level,
            source=source,
            target=target,
            confidence=max_confidence,
            indicators=indicators,
            context=context,
            fp_likelihood=fp_likelihood,
            priority=priority,
        )

        # Store in history
        self._threat_history.append(result)
        if len(self._threat_history) > self._max_threat_history:
            self._threat_history = self._threat_history[-self._max_threat_history :]

        # Update statistics
        self._stats["total_detections"] += 1
        self._stats["true_positives"] += 1

        # Check for Core Triad escalation
        if self.config.core_triad_escalation_enabled:
            await self._check_escalation(source, result)

        return result

    def _detect_exfiltration(self, content: str) -> list[dict[str, Any]]:
        """Detect potential data exfiltration attempts."""
        indicators = []
        content_lower = content.lower()

        for keyword in self.config.exfiltration_keywords:
            if keyword.lower() in content_lower:
                # Check for patterns suggesting exfiltration
                patterns = [
                    rf"\b{keyword}\b.*[:=].*['\"][^'\"]+['\"]",
                    rf"['\"][^'\"]*{keyword}[^'\"]*['\"]",
                ]
                for pattern in patterns:
                    if re.search(pattern, content, re.IGNORECASE):
                        indicators.append(
                            {
                                "type": "data_exfiltration",
                                "keyword": keyword,
                                "confidence": 0.75,
                            }
                        )
                        break

        # Check for unusual data transfer patterns
        if re.search(r"(export|dump|extract|download).{0,30}(file|db|database)", content_lower):
            indicators.append(
                {
                    "type": "data_exfiltration",
                    "pattern": "bulk_data_transfer",
                    "confidence": 0.8,
                }
            )

        return indicators

    async def execute_containment(
        self,
        threat: ThreatDetectionResult,
    ) -> list[ContainmentAction]:
        """
        Execute containment actions for a detected threat.

        Args:
            threat: The detected threat

        Returns:
            List of containment actions taken
        """
        actions_taken = []

        # Check if priority warrants auto-response
        if threat.priority not in self.config.auto_response_priorities:
            actions_taken.append(ContainmentAction.LOG_ONLY)
            return actions_taken

        # Determine containment actions based on threat level
        if threat.threat_level == ThreatLevel.CRITICAL:
            actions_taken.extend(
                [
                    ContainmentAction.ALERT,
                    ContainmentAction.BLOCK_IP,
                    ContainmentAction.QUARANTINE,
                ]
            )
            self._blocked_sources[threat.source] = datetime.now(UTC)
            self._stats["blocked_sources"] += 1

        elif threat.threat_level == ThreatLevel.HIGH:
            actions_taken.extend(
                [
                    ContainmentAction.ALERT,
                    ContainmentAction.RATE_LIMIT,
                ]
            )
            self._rate_limited_sources[threat.source] = {
                "started_at": datetime.now(UTC),
                "max_requests": 10,
                "window_seconds": 60,
            }

        elif threat.threat_level == ThreatLevel.MEDIUM:
            actions_taken.extend(
                [
                    ContainmentAction.ALERT,
                    ContainmentAction.RATE_LIMIT,
                ]
            )

        else:
            actions_taken.append(ContainmentAction.LOG_ONLY)

        self._stats["auto_responses"] += len(actions_taken)

        logger.warning(
            "containment_executed",
            threat_id=threat.threat_id,
            threat_level=threat.threat_level.value,
            actions=[a.value for a in actions_taken],
        )

        return actions_taken

    async def _check_escalation(
        self,
        source: str,
        threat: ThreatDetectionResult,
    ) -> None:
        """
        Check if threat warrants escalation to Core Triad.

        Args:
            source: Source identifier
            threat: The detected threat
        """
        self._escalation_count[source] += 1

        # Check cooldown
        last_escalation = self._last_escalation_time.get(source)
        if last_escalation:
            cooldown_elapsed = (datetime.now(UTC) - last_escalation).total_seconds()
            if cooldown_elapsed < self.config.escalation_cooldown_seconds:
                return

        # Check threshold
        if self._escalation_count[source] >= self.config.escalation_threshold_count:
            # Escalate to Core Triad
            logger.warning(
                "escalating_to_core_triad",
                source=source,
                threat_count=self._escalation_count[source],
                threat_level=threat.threat_level.value,
            )

            self._stats["escalations_to_triad"] += 1
            self._last_escalation_time[source] = datetime.now(UTC)
            self._escalation_count[source] = 0

            # In production, this would send a message to Core Triad via NATS


    def _calculate_threat_level(
        self,
        confidence: float,
        threat_type_count: int,
    ) -> ThreatLevel:
        """Calculate threat level from confidence and type count."""
        # Adjust confidence based on number of threat types detected
        adjusted = min(confidence + (threat_type_count * 0.05), 1.0)

        if adjusted >= 0.95:
            return ThreatLevel.CRITICAL
        if adjusted >= 0.85:
            return ThreatLevel.HIGH
        if adjusted >= 0.70:
            return ThreatLevel.MEDIUM
        if adjusted >= 0.50:
            return ThreatLevel.LOW
        return ThreatLevel.BENIGN

    def _calculate_priority(
        self,
        level: ThreatLevel,
        confidence: float,
    ) -> AlertPriority:
        """Calculate alert priority."""
        if level == ThreatLevel.CRITICAL or confidence >= 0.95:
            return AlertPriority.CRITICAL
        if level == ThreatLevel.HIGH or confidence >= 0.85:
            return AlertPriority.HIGH
        if level == ThreatLevel.MEDIUM or confidence >= 0.70:
            return AlertPriority.MEDIUM
        if level == ThreatLevel.LOW:
            return AlertPriority.LOW
        return AlertPriority.INFO

    def _calculate_fp_likelihood(
        self,
        source: str,
        indicators: list[dict[str, Any]],
        threat_types: list[ExternalThreatType],
    ) -> float:
        """
        Calculate likelihood that this detection is a false positive.

        Uses historical data and pattern analysis.
        """
        # Check cache first
        cache_key = f"{source}:{len(indicators)}"
        if cache_key in self._fp_likelihood_cache:
            return self._fp_likelihood_cache[cache_key]

        likelihood = 0.1  # Base 10% likelihood

        # Reduce likelihood if multiple threat types detected
        if len(threat_types) > 1:
            likelihood -= 0.1 * len(threat_types)

        # Increase likelihood if only single low-confidence indicator
        if len(indicators) == 1:
            single_confidence = indicators[0].get("confidence", 0.5)
            if single_confidence < 0.7:
                likelihood += 0.2

        # Historical false positive rate adjustment
        if self._stats["total_detections"] > 0:
            historical_fp_rate = self._stats["false_positives"] / self._stats["total_detections"]
            likelihood = 0.5 * likelihood + 0.5 * historical_fp_rate

        likelihood = max(0.0, min(1.0, likelihood))
        self._fp_likelihood_cache[cache_key] = likelihood

        return likelihood

    async def _create_threat_detection(
        self,
        threat_type: ExternalThreatType,
        level: ThreatLevel,
        source: str,
        target: str | None,
        confidence: float,
        indicators: list[dict[str, Any]],
        context: dict[str, Any],
        fp_likelihood: float = 0.0,
        priority: AlertPriority | None = None,
    ) -> ThreatDetectionResult:
        """Create a threat detection result."""
        timestamp = datetime.now(UTC)
        threat_id = f"THREAT_{int(timestamp.timestamp())}_{hashlib.sha256(str(timestamp).encode()).hexdigest()[:8]}"

        # Determine containment actions
        containment_actions = []
        if level == ThreatLevel.CRITICAL:
            containment_actions = [
                ContainmentAction.ALERT,
                ContainmentAction.BLOCK_IP,
                ContainmentAction.QUARANTINE,
            ]
        elif level == ThreatLevel.HIGH:
            containment_actions = [
                ContainmentAction.ALERT,
                ContainmentAction.RATE_LIMIT,
            ]
        elif level == ThreatLevel.MEDIUM:
            containment_actions = [
                ContainmentAction.ALERT,
            ]
        else:
            containment_actions = [ContainmentAction.LOG_ONLY]

        return ThreatDetectionResult(
            threat_id=threat_id,
            threat_type=threat_type,
            threat_level=level,
            priority=priority or self._calculate_priority(level, confidence),
            confidence=confidence,
            source=source,
            target=target,
            indicators=indicators,
            containment_actions=containment_actions,
            auto_responded=priority in self.config.auto_response_priorities if priority else False,
            false_positive_likelihood=fp_likelihood,
            timestamp=timestamp,
            details=context,
        )

    async def get_threat_intelligence(
        self,
        time_range: str = "24h",
    ) -> ThreatIntelligence:
        """
        Get aggregated threat intelligence.

        Args:
            time_range: Time range for intelligence (not yet implemented)

        Returns:
            ThreatIntelligence with aggregated data
        """
        threats_by_type: dict[str, int] = defaultdict(int)
        threats_by_source: dict[str, int] = defaultdict(int)
        all_indicators: list[dict[str, Any]] = []

        for threat in self._threat_history:
            threats_by_type[threat.threat_type.value] += 1
            threats_by_source[threat.source] += 1
            all_indicators.extend(threat.indicators)

        # Get top indicators
        top_indicators = sorted(
            all_indicators,
            key=lambda x: x.get("confidence", 0),
            reverse=True,
        )[:20]

        # Generate recommendations
        recommendations = []
        if self._stats["false_positives"] > self._stats["total_detections"] * 0.05:
            recommendations.append(
                "Consider adjusting detection thresholds - elevated false positive rate"
            )

        critical_count = sum(
            1 for t in self._threat_history if t.threat_level == ThreatLevel.CRITICAL
        )
        if critical_count > 10:
            recommendations.append("High critical threat count - review security architecture")

        return ThreatIntelligence(
            total_threats=self._stats["total_detections"],
            threats_by_type=dict(threats_by_type),
            threats_by_source=dict(threats_by_source),
            active_blocked_sources=len(self._blocked_sources),
            rate_limited_sources=len(self._rate_limited_sources),
            last_detection_time=self._threat_history[-1].timestamp
            if self._threat_history
            else None,
            top_indicators=top_indicators,
            recommendations=recommendations,
        )

    def get_statistics(self) -> dict[str, Any]:
        """Get threat detection statistics."""
        return {
            **self._stats,
            "blocked_sources_current": len(self._blocked_sources),
            "rate_limited_sources_current": len(self._rate_limited_sources),
            "false_positive_rate": (
                self._stats["false_positives"] / self._stats["total_detections"]
                if self._stats["total_detections"] > 0
                else 0.0
            ),
            "precision": (
                (self._stats["total_detections"] - self._stats["false_positives"])
                / self._stats["total_detections"]
                if self._stats["total_detections"] > 0
                else 1.0
            ),
            "threat_history_size": len(self._threat_history),
        }


# =============================================================================
# Convenience Functions
# =============================================================================


def create_default_detector(config: ThreatDetectionConfig | None = None) -> ExternalThreatDetector:
    """Create an ExternalThreatDetector with default configuration."""
    return ExternalThreatDetector(config=config)


def create_strict_detector() -> ExternalThreatDetector:
    """Create an ExternalThreatDetector with strict security configuration."""
    config = ThreatDetectionConfig(
        min_detection_confidence=0.8,
        max_false_positive_rate=0.005,  # 0.5% false positive rate
        default_alert_priority=AlertPriority.HIGH,
        auto_response_priorities={AlertPriority.CRITICAL, AlertPriority.HIGH},
        dos_spike_multiplier=5.0,  # More sensitive
    )
    return ExternalThreatDetector(config=config)
