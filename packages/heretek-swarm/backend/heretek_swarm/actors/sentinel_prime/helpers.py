"""
Sentinel-Prime helpers - Utility methods for threat management.

Extracted from sentinel_prime.py (SAFE-02).
Contains 16 helper methods as a mixin for cooperative MRO.
"""

import asyncio
import hashlib
from datetime import UTC, datetime
from typing import Any

import structlog

from heretek_swarm.actors.sentinel_prime.types import (
    ResponseAction,
    SecurityIncident,
    ThreatIndicator,
    ThreatLevel,
    ThreatType,
)

logger = structlog.get_logger(__name__)


class SentinelPrimeHelpers:
    """
    Helper methods mixin for SentinelPrimeAgent.

    Provides utility methods for incident management, threat analysis,
    and response coordination. Uses cooperative MRO with super().__init__().
    """

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)

    # =====================================================================
    # ID Generation
    # =====================================================================

    def _create_incident_id(self) -> str:
        """Generate unique incident ID."""
        timestamp = datetime.now(UTC).timestamp()
        random_suffix = hashlib.sha256(str(timestamp).encode()).hexdigest()[:8]
        return f"INC_{int(timestamp)}_{random_suffix}"

    # =====================================================================
    # Indicator Creation
    # =====================================================================

    def _create_indicator(self, data: dict[str, Any]) -> ThreatIndicator | None:
        """Create a threat indicator from data."""
        try:
            indicator_id = f"IND_{hashlib.sha256(data.get('value', '').encode()).hexdigest()[:12]}"
            now = datetime.now(UTC)

            return ThreatIndicator(
                indicator_id=indicator_id,
                indicator_type=data.get("indicator_type", "unknown"),
                value=data.get("value", ""),
                confidence=float(data.get("confidence", 0.5)),
                first_seen=now,
                last_seen=now,
                source=data.get("source", "unknown"),
                tags=data.get("tags", []),
            )
        except Exception:
            return None

    # =====================================================================
    # Alert Suppression (SAFE-02)
    # =====================================================================

    def _is_alert_suppressed(self, source: str) -> bool:
        """Check if alerts from source are suppressed."""
        import time

        if source not in self._suppressed_alerts:
            return False

        if time.time() > self._suppressed_alerts[source]:
            # Expired
            del self._suppressed_alerts[source]
            return False

        return True

    # =====================================================================
    # Incident Creation from Threat Detection (SAFE-02)
    # =====================================================================

    async def _create_incident_from_detection(
        self,
        threat_result: Any,
    ) -> SecurityIncident:
        """Create a SecurityIncident from ThreatDetectionResult."""
        from heretek_swarm_core.security.threat_detection import (
            ExternalThreatType,
        )
        from heretek_swarm_core.security.threat_detection import (
            ThreatLevel as ExtThreatLevel,
        )

        # Map threat type
        threat_type_map = {
            ExternalThreatType.PROMPT_INJECTION: ThreatType.PROMPT_INJECTION,
            ExternalThreatType.DOS_ATTACK: ThreatType.DOS_ATTACK,
            ExternalThreatType.DATA_EXFILTRATION: ThreatType.DATA_EXFILTRATION,
            ExternalThreatType.SQL_INJECTION: ThreatType.SQL_INJECTION,
            ExternalThreatType.API_ABUSE: ThreatType.API_ABUSE,
        }

        threat_type = threat_type_map.get(
            threat_result.threat_type,
            ThreatType.SUSPICIOUS_BEHAVIOR,
        )

        # Map threat level
        level_map = {
            ExtThreatLevel.CRITICAL: ThreatLevel.CRITICAL,
            ExtThreatLevel.HIGH: ThreatLevel.HIGH,
            ExtThreatLevel.MEDIUM: ThreatLevel.MEDIUM,
            ExtThreatLevel.LOW: ThreatLevel.LOW,
            ExtThreatLevel.BENIGN: ThreatLevel.INFORMATIONAL,
        }
        threat_level = level_map.get(threat_result.threat_level, ThreatLevel.MEDIUM)

        incident_id = self._create_incident_id()
        incident = SecurityIncident(
            incident_id=incident_id,
            threat_type=threat_type,
            threat_level=threat_level,
            status=self._get_incident_status("detected"),
            timestamp=threat_result.timestamp,
            source_actor=threat_result.source,
            target_actor=threat_result.target,
            description=f"External threat detected: {threat_result.threat_type.value}",
            evidence={
                "threat_id": threat_result.threat_id,
                "confidence": threat_result.confidence,
                "priority": threat_result.priority.value,
                "indicators": threat_result.indicators,
                "false_positive_likelihood": threat_result.false_positive_likelihood,
            },
        )

        # Update stats
        self._stats["total_incidents"] += 1
        self._stats["incidents_by_level"][threat_level.value] += 1
        self._stats["incidents_by_type"][threat_type.value] += 1

        # Store indicator
        if threat_result.indicators:
            for ind in threat_result.indicators[:5]:
                indicator = ThreatIndicator(
                    indicator_id=f"IND_{hashlib.sha256(str(ind).encode()).hexdigest()[:12]}",
                    indicator_type=ind.get("type", "unknown"),
                    value=str(ind),
                    confidence=ind.get("confidence", 0.5),
                    first_seen=datetime.now(UTC),
                    last_seen=datetime.now(UTC),
                    source=threat_result.source,
                )
                incident.indicators.append(indicator)

        return incident

    def _get_incident_status(self, value: str) -> Any:
        """Get IncidentStatus enum value."""
        from heretek_swarm.actors.sentinel_prime.types import IncidentStatus

        return IncidentStatus(value)

    # =====================================================================
    # Core Triad Escalation (SAFE-02)
    # =====================================================================

    async def _check_core_triad_escalation(
        self,
        source: str,
        _threat_result: Any,
    ) -> None:
        """Check if threat warrants escalation to Core Triad."""
        from heretek_swarm.actors.sentinel_prime.types import IncidentStatus

        # Check cooldown
        last_escalation = self._last_escalation_time.get(source)
        if last_escalation:
            cooldown_elapsed = (datetime.now(UTC) - last_escalation).total_seconds()
            if cooldown_elapsed < self._escalation_cooldown_seconds:
                return

        # Count recent threats from this source
        recent_threats = sum(
            1
            for inc in self._incidents.values()
            if inc.source_actor == source and inc.status == IncidentStatus.DETECTED
        )

        # Escalate if threshold reached
        threshold = self._external_threat_detector.config.escalation_threshold_count
        if recent_threats >= threshold:
            self._stats["core_triad_escalations"] += 1
            self._last_escalation_time[source] = datetime.now(UTC)

    # =====================================================================
    # Auto-Response Logic
    # =====================================================================

    async def _auto_respond(self, incident: SecurityIncident) -> list[ResponseAction]:
        """Execute automatic response to an incident."""
        actions = []

        # Determine response based on threat level
        if incident.threat_level == ThreatLevel.CRITICAL:
            # Critical: Immediate isolation and blocking
            actions.append(ResponseAction.ALERT)
            actions.append(ResponseAction.ISOLATE)
            actions.append(ResponseAction.BLOCK)
            actions.append(ResponseAction.QUARANTINE)

            if incident.source_actor:
                self._isolated_actors.add(incident.source_actor)
            if incident.target_resource:
                actions.append(ResponseAction.TERMINATE)

        elif incident.threat_level == ThreatLevel.HIGH:
            # High: Alert and rate limit
            actions.append(ResponseAction.ALERT)
            actions.append(ResponseAction.RATE_LIMIT)

            if incident.source_actor:
                self._rate_limits[incident.source_actor] = {
                    "max_requests": 10,
                    "window_seconds": 60,
                    "started_at": datetime.now(UTC),
                }

        elif incident.threat_level == ThreatLevel.MEDIUM:

            actions.append(ResponseAction.ALERT)
            actions.append(ResponseAction.LOG_ONLY)

        else:
            # Low/Informational: Log only
            actions.append(ResponseAction.LOG_ONLY)

        # Update statistics
        self._stats["auto_responses_triggered"] += len(actions)

        return actions

    # =====================================================================
    # Response Action Execution
    # =====================================================================

    async def _execute_response_action(
        self,
        incident: SecurityIncident,
        action: ResponseAction,
    ) -> bool:
        """Execute a specific response action."""
        try:
            if action == ResponseAction.ALERT:
                return True

            if action == ResponseAction.BLOCK:
                if incident.source_actor:
                    self._blocked_sources.add(incident.source_actor)
                return True

            if action == ResponseAction.ISOLATE:
                if incident.source_actor:
                    self._isolated_actors.add(incident.source_actor)
                return True

            if action == ResponseAction.QUARANTINE:
                if incident.target_resource:
                    # Mark resource as quarantined
                    incident.evidence["quarantined"] = True
                return True

            if action == ResponseAction.TERMINATE:
                # Terminate affected processes/connections
                incident.evidence["terminated"] = True
                return True

            if action == ResponseAction.RATE_LIMIT:
                if incident.source_actor:
                    self._rate_limits[incident.source_actor] = {
                        "max_requests": 10,
                        "window_seconds": 60,
                    }
                return True

            if action == ResponseAction.BLACKLIST:
                for indicator in incident.indicators:
                    self._blocked_sources.add(indicator.value)
                return True

            if action == ResponseAction.NOTIFY:
                return True

            return action == ResponseAction.LOG_ONLY

        except Exception:
            return False

    # =====================================================================
    # Severity Scoring
    # =====================================================================

    def _calculate_severity_score(self, incident: SecurityIncident) -> float:
        """Calculate numerical severity score for an incident."""
        base_scores = {
            ThreatLevel.CRITICAL: 10.0,
            ThreatLevel.HIGH: 7.5,
            ThreatLevel.MEDIUM: 5.0,
            ThreatLevel.LOW: 2.5,
            ThreatLevel.INFORMATIONAL: 1.0,
        }

        score = base_scores.get(incident.threat_level, 5.0)

        # Adjust based on indicators
        score += len(incident.indicators) * 0.5

        # Adjust based on target
        if incident.target_actor:
            score += 1.0

        return min(score, 10.0)

    def _correlation_score(self, incident: SecurityIncident, other: SecurityIncident) -> float:
        """Compute correlation score between two incidents."""
        score = 0.0
        if incident.source_actor and incident.source_actor == other.source_actor:
            score += 0.4
        if incident.target_actor and incident.target_actor == other.target_actor:
            score += 0.3
        if incident.threat_type == other.threat_type:
            score += 0.2
        shared = {i.value for i in incident.indicators} & {i.value for i in other.indicators}
        score += len(shared) * 0.1
        return score

    # =====================================================================
    # Correlation Analysis
    # =====================================================================

    def _find_correlated_incidents(
        self,
        incident: SecurityIncident,
        max_results: int = 10,
    ) -> list[SecurityIncident]:
        """Find incidents correlated with the given incident."""
        correlated = []

        for other in self._incidents.values():
            if other.incident_id == incident.incident_id:
                continue
            if self._correlation_score(incident, other) > 0.3:
                correlated.append(other)

        correlated.sort(key=self._calculate_severity_score, reverse=True)
        return correlated[:max_results]

    # =====================================================================
    # Attack Chain Reconstruction
    # =====================================================================

    def _reconstruct_attack_chain(self, incident: SecurityIncident) -> list[dict[str, Any]]:
        """Reconstruct the attack chain leading to this incident."""
        chain = []
        correlated = self._find_correlated_incidents(incident, max_results=20)

        # Sort by timestamp
        correlated.sort(key=lambda x: x.timestamp)

        for related in correlated:
            chain.append(
                {
                    "incident_id": related.incident_id,
                    "timestamp": related.timestamp.isoformat(),
                    "threat_type": related.threat_type.value,
                    "severity": self._calculate_severity_score(related),
                }
            )

        return chain

    # =====================================================================
    # IOC Matching
    # =====================================================================

    def _match_iocs(self, incident: SecurityIncident) -> list[dict[str, Any]]:
        """Match indicators of compromise against known threat intelligence."""
        matches = []

        for indicator in incident.indicators:
            if indicator.value in self._indicator_cache:
                cached = self._indicator_cache[indicator.value]
                matches.append(
                    {
                        "indicator": indicator.value,
                        "matched_threat": cached.indicator_id,
                        "confidence": cached.confidence,
                        "tags": cached.tags,
                    }
                )

        return matches

    # =====================================================================
    # MITRE ATT&CK Mapping
    # =====================================================================

    def _map_mitre_techniques(self, incident: SecurityIncident) -> list[str]:
        """Map incident to MITRE ATT&CK techniques."""
        technique_mapping = {
            ThreatType.SQL_INJECTION: ["T1190", "T1059"],
            ThreatType.XSS_ATTACK: ["T1189", "T1059"],
            ThreatType.UNAUTHORIZED_ACCESS: ["T1078", "T1133"],
            ThreatType.PRIVILEGE_ESCALATION: ["T1068", "T1134"],
            ThreatType.DATA_EXFILTRATION: ["T1041", "T1048"],
            ThreatType.MALWARE: ["T1204", "T1059"],
            ThreatType.PHISHING: ["T1566", "T1204"],
        }

        return technique_mapping.get(incident.threat_type, [])

    # =====================================================================
    # Recommendations Generation
    # =====================================================================

    def _generate_recommendations(self, incident: SecurityIncident) -> list[str]:
        """Generate remediation recommendations for an incident."""
        recommendations = []

        if incident.threat_level in [ThreatLevel.CRITICAL, ThreatLevel.HIGH]:
            recommendations.append("Immediately isolate affected systems")
            recommendations.append("Conduct forensic analysis")
            recommendations.append("Review access logs for compromise indicators")

        if incident.threat_type == ThreatType.SQL_INJECTION:
            recommendations.append("Review and parameterize all database queries")
            recommendations.append("Implement input validation")

        if incident.threat_type == ThreatType.XSS_ATTACK:
            recommendations.append("Implement Content Security Policy (CSP)")
            recommendations.append("Sanitize all user inputs")

        if incident.threat_type == ThreatType.UNAUTHORIZED_ACCESS:
            recommendations.append("Reset compromised credentials")
            recommendations.append("Review and restrict access permissions")

        return recommendations

    def _generate_strategic_recommendations(self) -> list[str]:
        """Generate strategic security recommendations based on overall threat landscape."""
        recommendations = []

        # Check incident trends
        critical_count = self._stats["incidents_by_level"].get("critical", 0)
        if critical_count > 5:
            recommendations.append(
                f"High critical incident count ({critical_count}) - consider security architecture review"
            )

        # Check for specific threat patterns
        sql_injection_count = self._stats["incidents_by_type"].get("sql_injection", 0)
        if sql_injection_count > 10:
            recommendations.append(
                f" Elevated SQL injection attempts ({sql_injection_count}) - implement WAF rules"
            )

        # Auto-response effectiveness
        if self._stats["auto_responses_triggered"] > 100:
            recommendations.append(
                "High auto-response rate - review detection thresholds for false positives"
            )

        # Check external threat detection stats
        if self._stats["external_threats_detected"] > 50:
            recommendations.append("High external threat count - review gateway protections")

        if not recommendations:
            recommendations.append("Security posture stable - continue monitoring")

        return recommendations

    # =====================================================================
    # Scheduled Operations
    # =====================================================================

    async def _schedule_unblock(self, source: str, duration: int) -> None:
        """Schedule automatic unblocking of a source."""
        await asyncio.sleep(duration)
        self._blocked_sources.discard(source)

    async def _schedule_unisolate(self, actor_id: str, duration: int) -> None:
        """Schedule automatic un-isolation of an actor."""
        await asyncio.sleep(duration)
        self._isolated_actors.discard(actor_id)
