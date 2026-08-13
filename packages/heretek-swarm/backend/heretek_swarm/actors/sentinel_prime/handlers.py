"""
Sentinel-Prime Handlers - Message handlers for threat management.

Extracted from sentinel_prime.py (SAFE-02).
Contains 17 handlers organized as a mixin for cooperative MRO.
"""

import asyncio
import contextlib

import structlog

from heretek_swarm.actors.base import ActorMessage
from heretek_swarm.actors.validation import validate_message
from heretek_swarm_core.security.threat_detection import AlertPriority

logger = structlog.get_logger("SentinelPrimeAgent")

# Sentinel values for repeated error message literals
_ERR_MISSING_SOURCE = "Missing source"
_ERR_MISSING_INCIDENT_ID = "Missing incident_id"
_ERR_INCIDENT_NOT_FOUND = "Incident not found"


class SentinelPrimeHandlers:
    """
    Message handler mixin for SentinelPrimeAgent.

    Provides all 17 handlers for threat detection, incident management,
    and response coordination. Uses cooperative MRO with super().__init__().
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def _register_handlers(self) -> None:
        """Register message handlers."""
        self._message_handlers = {
            "report_threat": self._handle_report_threat,
            "analyze_threat": self._handle_analyze_threat,
            "get_incident_details": self._handle_get_incident_details,
            "get_active_incidents": self._handle_get_active_incidents,
            "respond_to_incident": self._handle_respond_to_incident,
            "add_threat_indicator": self._handle_add_threat_indicator,
            "check_indicator": self._handle_check_indicator,
            "get_threat_report": self._handle_get_threat_report,
            "block_source": self._handle_block_source,
            "isolate_actor": self._handle_isolate_actor,
            "get_statistics": self._handle_get_statistics,
            "update_config": self._handle_update_config,
            # SAFE-02: External threat detection handlers
            "detect_external_threat": self._handle_detect_external_threat,
            "get_threat_intelligence": self._handle_get_threat_intelligence,
            "configure_alert_priority": self._handle_configure_alert_priority,
            "suppress_alerts": self._handle_suppress_alerts,
            "escalate_to_core_triad": self._handle_escalate_to_core_triad,
        }

    # =====================================================================
    # SAFE-02: External Threat Detection Handlers
    # =====================================================================

    async def _handle_detect_external_threat(self, message: ActorMessage) -> None:
        """Detect external threats in content (SAFE-02)."""
        try:
            content = message.content
            input_content = content.get("content", "")
            source = content.get("source", "unknown")
            target = content.get("target")
            threat_type_str = content.get("threat_type")

            # Validate
            validate_message(
                "detect_external_threat",
                content,
            )

            # Convert threat type if specified
            from heretek_swarm_core.security.threat_detection import ExternalThreatType

            threat_type = None
            if threat_type_str:
                with contextlib.suppress(ValueError):
                    threat_type = ExternalThreatType(threat_type_str)

            # Check alert suppression
            if self._is_alert_suppressed(source):
                response_content = {
                    "source": source,
                    "threat_detected": False,
                    "reason": "alerts_suppressed",
                    "suppressed_until": self._suppressed_alerts.get(source),
                }
                self._stats["alert_fatigue_suppressions"] += 1
                await self._send_response(message, response_content)
                return

            # Detect external threat
            threat_result = await self._external_threat_detector.detect_threat(
                content=input_content,
                source=source,
                target=target,
                threat_type=threat_type,
            )

            if threat_result is None:
                response_content = {
                    "source": source,
                    "threat_detected": False,
                    "confidence": 0.0,
                }
                await self._send_response(message, response_content)
                return

            # Threat detected - update stats
            self._stats["external_threats_detected"] += 1

            # Execute containment if auto-response enabled
            containment_actions = []
            if self._auto_response_enabled:
                containment_actions = await self._external_threat_detector.execute_containment(
                    threat_result
                )
                self._stats["external_threats_contained"] += len(containment_actions)

            # Create incident for tracking
            incident = await self._create_incident_from_detection(threat_result)
            self._incidents[incident.incident_id] = incident

            # Check for Core Triad escalation
            if self._core_triad_escalation_enabled:
                await self._check_core_triad_escalation(source, threat_result)

            response_content = {
                "source": source,
                "threat_detected": True,
                "threat_id": threat_result.threat_id,
                "threat_type": threat_result.threat_type.value,
                "threat_level": threat_result.threat_level.value,
                "priority": threat_result.priority.value,
                "confidence": threat_result.confidence,
                "containment_actions": [a.value for a in containment_actions],
                "auto_responded": threat_result.auto_responded,
                "false_positive_likelihood": threat_result.false_positive_likelihood,
                "indicators": threat_result.indicators,
            }

            await self._send_response(message, response_content)

        except Exception as e:
            logger.exception("Error detecting external threat", error=str(e))
            await self._send_error(message, "External threat detection failed", str(e))

    async def _handle_get_threat_intelligence(self, message: ActorMessage) -> None:
        """Get aggregated threat intelligence (SAFE-02)."""
        try:
            content = message.content
            time_range = content.get("time_range", "24h")

            intelligence = await self._external_threat_detector.get_threat_intelligence(time_range)

            response_content = {
                "total_threats": intelligence.total_threats,
                "threats_by_type": intelligence.threats_by_type,
                "threats_by_source": intelligence.threats_by_source,
                "active_blocked_sources": intelligence.active_blocked_sources,
                "rate_limited_sources": intelligence.rate_limited_sources,
                "last_detection_time": (
                    intelligence.last_detection_time.isoformat()
                    if intelligence.last_detection_time
                    else None
                ),
                "top_indicators": intelligence.top_indicators,
                "recommendations": intelligence.recommendations,
            }

            await self._send_response(message, response_content)

        except Exception as e:
            logger.exception("Error getting threat intelligence", error=str(e))
            await self._send_error(message, "Threat intelligence retrieval failed", str(e))

    async def _handle_configure_alert_priority(self, message: ActorMessage) -> None:
        """Configure alert priority for a source (SAFE-02)."""
        try:
            content = message.content
            source = content.get("source")
            priority_str = content.get("priority", "critical")
            if not source:
                await self._send_error(message, _ERR_MISSING_SOURCE)
                return

            if not source:
                await self._send_error(message, _ERR_MISSING_SOURCE)
                return

            try:
                priority = AlertPriority(priority_str.lower())
            except ValueError:
                await self._send_error(message, f"Invalid priority: {priority_str}")
                return

            self._alert_priorities[source] = priority

            response_content = {
                "source": source,
                "priority": priority.value,
                "updated": True,
            }

            await self._send_response(message, response_content)

        except Exception as e:
            logger.exception("Error configuring alert priority", error=str(e))
            await self._send_error(message, "Priority configuration failed", str(e))

    async def _handle_suppress_alerts(self, message: ActorMessage) -> None:
        """Suppress alerts from a source (SAFE-02 alert fatigue prevention)."""
        try:
            content = message.content
            source = content.get("source")
            duration_seconds = content.get("duration_seconds", 300)

            if not source:
                await self._send_error(message, _ERR_MISSING_SOURCE)
                return

            import time

            self._suppressed_alerts[source] = time.time() + duration_seconds
            self._stats["alert_fatigue_suppressions"] += 1

            response_content = {
                "source": source,
                "suppressed": True,
                "duration_seconds": duration_seconds,
            }

            await self._send_response(message, response_content)

        except Exception as e:
            logger.exception("Error suppressing alerts", error=str(e))
            await self._send_error(message, "Alert suppression failed", str(e))

    async def _handle_escalate_to_core_triad(self, message: ActorMessage) -> None:
        """Manually escalate threat to Core Triad (SAFE-02)."""
        try:
            content = message.content
            threat_id = content.get("threat_id")
            reason = content.get("reason", "manual_escalation")

            if not threat_id:
                await self._send_error(message, "Missing threat_id")
                return

            # Find the incident
            incident = None
            for inc in self._incidents.values():
                if inc.incident_id == threat_id:
                    incident = inc
                    break

            if not incident:
                await self._send_error(message, "Threat not found", threat_id)
                return

            # Escalate
            incident.status = IncidentStatus.ESCALATED
            self._stats["core_triad_escalations"] += 1

            response_content = {
                "threat_id": threat_id,
                "escalated": True,
                "reason": reason,
            }

            await self._send_response(message, response_content)

        except Exception as e:
            logger.exception("Error escalating to Core Triad", error=str(e))
            await self._send_error(message, "Escalation failed", str(e))

    # =====================================================================
    # Original Sentinel-Prime Handlers
    # =====================================================================

    async def _handle_report_threat(self, message: ActorMessage) -> None:
        """Report a potential security threat."""
        try:
            content = message.content
            threat_type_str = content.get("threat_type")
            threat_level_str = content.get("threat_level", ThreatLevel.MEDIUM.value)
            source = content.get("source")
            target = content.get("target")
            description = content.get("description", "")
            evidence = content.get("evidence", {})
            indicators = content.get("indicators", [])

            # Validate
            validate_message(
                "report_threat",
                content,
            )

            # Convert enums
            with contextlib.suppress(ValueError):
                threat_type = ThreatType(threat_type_str)
            if threat_type_str:
                with contextlib.suppress(ValueError):
                    threat_type = ThreatType(threat_type_str)

            with contextlib.suppress(ValueError):
                threat_level = ThreatLevel(threat_level_str)

            # Create incident
            incident_id = self._create_incident_id()
            incident = SecurityIncident(
                incident_id=incident_id,
                threat_type=threat_type,
                threat_level=threat_level,
                status=IncidentStatus.DETECTED,
                timestamp=datetime.now(UTC),
                source_actor=source,
                target_actor=target,
                description=description,
                evidence=evidence,
            )

            # Add indicators
            for ind_data in indicators:
                indicator = self._create_indicator(ind_data)
                if indicator:
                    incident.indicators.append(indicator)
                    self._threat_indicators[indicator.indicator_id] = indicator

            # Store incident
            self._incidents[incident_id] = incident
            self._incident_history.append(incident_id)

            # Update statistics
            self._stats["total_incidents"] += 1
            self._stats["incidents_by_level"][threat_level.value] += 1
            self._stats["incidents_by_type"][threat_type.value] += 1

            # Auto-respond if enabled
            response_actions = []
            if self._auto_response_enabled:
                response_actions = await self._auto_respond(incident)
                incident.response_actions = response_actions

            # LRU cleanup
            if len(self._incident_history) > self._max_incidents:
                oldest = self._incident_history.pop(0)
                self._incidents.pop(oldest, None)

            response_content = {
                "incident_id": incident_id,
                "status": incident.status.value,
                "threat_level": threat_level.value,
                "auto_response_triggered": len(response_actions) > 0,
                "response_actions": [a.value for a in response_actions],
                "recommendations": self._generate_recommendations(incident),
            }

            await self._send_response(message, response_content)

        except Exception as e:
            logger.exception("Error reporting threat", error=str(e))
            await self._send_error(message, "Threat report failed", str(e))

    async def _handle_analyze_threat(self, message: ActorMessage) -> None:
        """Analyze a reported threat for correlation and severity."""
        try:
            content = message.content
            incident_id = content.get("incident_id")
            correlate = content.get("correlate", True)
            deep_analysis = content.get("deep_analysis", False)

            if not incident_id:
                await self._send_error(message, _ERR_MISSING_INCIDENT_ID)
                return

            incident = self._incidents.get(incident_id)
            if not incident:
                await self._send_error(message, _ERR_INCIDENT_NOT_FOUND, incident_id)
                return

            # Perform analysis
            analysis_result = {
                "incident_id": incident_id,
                "severity_score": self._calculate_severity_score(incident),
                "correlated_incidents": [],
                "attack_chain": [],
                "ioc_matches": [],
                "mitre_techniques": [],
            }

            # Correlation analysis
            if correlate:
                correlated = self._find_correlated_incidents(incident)
                analysis_result["correlated_incidents"] = [
                    {"incident_id": c.incident_id, "correlation_score": 0.8} for c in correlated[:5]
                ]

            # Deep analysis
            if deep_analysis:
                analysis_result["attack_chain"] = self._reconstruct_attack_chain(incident)
                analysis_result["ioc_matches"] = self._match_iocs(incident)
                analysis_result["mitre_techniques"] = self._map_mitre_techniques(incident)

            response_content = {
                "incident_id": incident_id,
                "analysis": analysis_result,
                "updated_threat_level": incident.threat_level.value,
            }

            await self._send_response(message, response_content)

        except Exception as e:
            logger.exception("Error analyzing threat", error=str(e))
            await self._send_error(message, "Threat analysis failed", str(e))

    async def _handle_get_incident_details(self, message: ActorMessage) -> None:
        """Get detailed information about a specific incident."""
        try:
            content = message.content
            incident_id = content.get("incident_id")

            if not incident_id:
                await self._send_error(message, _ERR_MISSING_INCIDENT_ID)
                return

            incident = self._incidents.get(incident_id)
            if not incident:
                await self._send_error(message, _ERR_INCIDENT_NOT_FOUND, incident_id)
                return

            response_content = {
                "incident_id": incident.incident_id,
                "threat_type": incident.threat_type.value,
                "threat_level": incident.threat_level.value,
                "status": incident.status.value,
                "timestamp": incident.timestamp.isoformat(),
                "source_actor": incident.source_actor,
                "target_actor": incident.target_actor,
                "target_resource": incident.target_resource,
                "description": incident.description,
                "indicators": [
                    {
                        "indicator_id": i.indicator_id,
                        "type": i.indicator_type,
                        "value": i.value,
                        "confidence": i.confidence,
                    }
                    for i in incident.indicators
                ],
                "response_actions": [a.value for a in incident.response_actions],
                "remediation_steps": incident.remediation_steps,
                "evidence": incident.evidence,
            }

            await self._send_response(message, response_content)

        except Exception as e:
            logger.exception("Error getting incident details", error=str(e))
            await self._send_error(message, "Failed to get incident details", str(e))

    async def _handle_get_active_incidents(self, message: ActorMessage) -> None:
        """Get all active (non-closed) incidents."""
        try:
            content = message.content
            threat_level_filter = content.get("threat_level_filter")
            limit = content.get("limit", 100)

            active_incidents = [
                inc
                for inc in self._incidents.values()
                if inc.status not in [IncidentStatus.CLOSED, IncidentStatus.REMEDIATED]
            ]

            # Filter by threat level
            if threat_level_filter:
                with contextlib.suppress(ValueError):
                    min_level = ThreatLevel(threat_level_filter)
                    level_order = {
                        ThreatLevel.INFORMATIONAL: 0,
                        ThreatLevel.LOW: 1,
                        ThreatLevel.MEDIUM: 2,
                        ThreatLevel.HIGH: 3,
                        ThreatLevel.CRITICAL: 4,
                    }
                    min_order = level_order.get(min_level, 0)
                    active_incidents = [
                        inc
                        for inc in active_incidents
                        if level_order.get(inc.threat_level, 0) >= min_order
                    ]

            # Sort by threat level (highest first)
            level_order = {
                ThreatLevel.CRITICAL: 4,
                ThreatLevel.HIGH: 3,
                ThreatLevel.MEDIUM: 2,
                ThreatLevel.LOW: 1,
                ThreatLevel.INFORMATIONAL: 0,
            }
            active_incidents.sort(
                key=lambda x: level_order.get(x.threat_level, 0),
                reverse=True,
            )

            # Apply limit
            active_incidents = active_incidents[:limit]

            response_content = {
                "active_incidents_count": len(active_incidents),
                "incidents": [
                    {
                        "incident_id": inc.incident_id,
                        "threat_type": inc.threat_type.value,
                        "threat_level": inc.threat_level.value,
                        "status": inc.status.value,
                        "timestamp": inc.timestamp.isoformat(),
                        "source_actor": inc.source_actor,
                        "target_actor": inc.target_actor,
                    }
                    for inc in active_incidents
                ],
            }

            await self._send_response(message, response_content)

        except Exception as e:
            logger.exception("Error getting active incidents", error=str(e))
            await self._send_error(message, "Failed to get active incidents", str(e))

    async def _handle_respond_to_incident(self, message: ActorMessage) -> None:
        """Execute response actions for an incident."""
        try:
            content = message.content
            incident_id = content.get("incident_id")
            actions = content.get("actions", [])
            manual = content.get("manual", False)

            if not incident_id:
                await self._send_error(message, _ERR_MISSING_INCIDENT_ID)
                return

            incident = self._incidents.get(incident_id)
            if not incident:
                await self._send_error(message, _ERR_INCIDENT_NOT_FOUND, incident_id)
                return

            executed_actions = []

            for action_str in actions:
                with contextlib.suppress(ValueError):
                    action = ResponseAction(action_str)
                    result = await self._execute_response_action(incident, action)
                    if result:
                        executed_actions.append(action)
                        incident.response_actions.append(action)

            # Update statistics
            if manual:
                self._stats["manual_responses_triggered"] += len(executed_actions)
            else:
                self._stats["auto_responses_triggered"] += len(executed_actions)

            response_content = {
                "incident_id": incident_id,
                "executed_actions": [a.value for a in executed_actions],
                "new_status": incident.status.value,
                "success": len(executed_actions) > 0,
            }

            await self._send_response(message, response_content)

        except Exception as e:
            logger.exception("Error responding to incident", error=str(e))
            await self._send_error(message, "Response execution failed", str(e))

    async def _handle_add_threat_indicator(self, message: ActorMessage) -> None:
        """Add a threat indicator to the intelligence database."""
        try:
            content = message.content
            indicator_data = {
                "indicator_type": content.get("indicator_type", "unknown"),
                "value": content.get("value", ""),
                "confidence": content.get("confidence", 0.5),
                "source": content.get("source", "manual"),
                "tags": content.get("tags", []),
            }

            indicator = self._create_indicator(indicator_data)
            if not indicator:
                await self._send_error(message, "Invalid indicator data")
                return

            self._threat_indicators[indicator.indicator_id] = indicator

            # Update cache
            self._indicator_cache[indicator.value] = indicator
            if len(self._indicator_cache) > self._max_indicator_cache:
                oldest_key = next(iter(self._indicator_cache))
                self._indicator_cache.pop(oldest_key)

            response_content = {
                "indicator_id": indicator.indicator_id,
                "type": indicator.indicator_type,
                "value": indicator.value,
                "confidence": indicator.confidence,
                "success": True,
            }

            await self._send_response(message, response_content)

        except Exception as e:
            logger.exception("Error adding threat indicator", error=str(e))
            await self._send_error(message, "Failed to add indicator", str(e))

    async def _handle_check_indicator(self, message: ActorMessage) -> None:
        """Check if a value matches any known threat indicator."""
        try:
            content = message.content
            value = content.get("value", "")
            indicator_type = content.get("indicator_type")

            # Check cache first
            cached = self._indicator_cache.get(value)
            if cached:
                response_content = {
                    "value": value,
                    "match_found": True,
                    "indicator": {
                        "indicator_id": cached.indicator_id,
                        "type": cached.indicator_type,
                        "confidence": cached.confidence,
                        "tags": cached.tags,
                    },
                    "source": "cache",
                }
                await self._send_response(message, response_content)
                return

            # Check all indicators
            for indicator in self._threat_indicators.values():
                if indicator.value == value:
                    if indicator_type and indicator.indicator_type != indicator_type:
                        continue

                    response_content = {
                        "value": value,
                        "match_found": True,
                        "indicator": {
                            "indicator_id": indicator.indicator_id,
                            "type": indicator.indicator_type,
                            "confidence": indicator.confidence,
                            "tags": indicator.tags,
                        },
                        "source": "database",
                    }
                    await self._send_response(message, response_content)
                    return

            response_content = {
                "value": value,
                "match_found": False,
                "source": "not_found",
            }
            await self._send_response(message, response_content)

        except Exception as e:
            logger.exception("Error checking indicator", error=str(e))
            await self._send_error(message, "Indicator check failed", str(e))

    async def _handle_get_threat_report(self, message: ActorMessage) -> None:
        """Generate comprehensive threat intelligence report."""
        try:
            content = message.content
            include_indicators = content.get("include_indicators", False)
            include_recommendations = content.get("include_recommendations", True)

            # Calculate statistics
            incidents_by_level = dict(self._stats["incidents_by_level"])
            incidents_by_type = dict(self._stats["incidents_by_type"])

            active_threats = sum(
                1
                for inc in self._incidents.values()
                if inc.status in [IncidentStatus.DETECTED, IncidentStatus.INVESTIGATING]
            )
            contained_threats = sum(
                1
                for inc in self._incidents.values()
                if inc.status in [IncidentStatus.CONTAINED, IncidentStatus.REMEDIATED]
            )

            # Get top indicators
            top_indicators = []
            if include_indicators:
                sorted_indicators = sorted(
                    self._threat_indicators.values(),
                    key=lambda x: x.confidence,
                    reverse=True,
                )[:20]
                top_indicators = [
                    {
                        "indicator_id": i.indicator_id,
                        "type": i.indicator_type,
                        "value": i.value,
                        "confidence": i.confidence,
                        "tags": i.tags,
                    }
                    for i in sorted_indicators
                ]

            # Generate recommendations
            recommendations = []
            if include_recommendations:
                recommendations = self._generate_strategic_recommendations()

            report = {
                "report_id": f"threat_report_{datetime.now(UTC).timestamp()}",
                "timestamp": datetime.now(UTC).isoformat(),
                "time_range": "24h",
                "total_incidents": self._stats["total_incidents"],
                "incidents_by_level": incidents_by_level,
                "incidents_by_type": incidents_by_type,
                "active_threats": active_threats,
                "contained_threats": contained_threats,
                "top_indicators": top_indicators,
                "recommendations": recommendations,
                "auto_response_stats": {
                    "auto_responses": self._stats["auto_responses_triggered"],
                    "manual_responses": self._stats["manual_responses_triggered"],
                },
            }

            await self._send_response(message, {"report": report})

        except Exception as e:
            logger.exception("Error generating threat report", error=str(e))
            await self._send_error(message, "Threat report generation failed", str(e))

    async def _handle_block_source(self, message: ActorMessage) -> None:
        """Block a source from communicating with the Collective."""
        try:
            content = message.content
            source = content.get("source")
            duration = content.get("duration")
            reason = content.get("reason", "manual_block")

            if not source:
                await self._send_error(message, _ERR_MISSING_SOURCE)
                return

            self._blocked_sources.add(source)

            # Schedule unblock if duration specified
            if duration:
                asyncio.create_task(self._schedule_unblock(source, duration))

            response_content = {
                "source": source,
                "blocked": True,
                "duration": duration,
                "reason": reason,
            }

            await self._send_response(message, response_content)

        except Exception as e:
            logger.exception("Error blocking source", error=str(e))
            await self._send_error(message, "Block operation failed", str(e))

    async def _handle_isolate_actor(self, message: ActorMessage) -> None:
        """Isolate an actor from the Collective."""
        try:
            content = message.content
            actor_id = content.get("actor_id")
            duration = content.get("duration")
            reason = content.get("reason", "security_isolation")

            if not actor_id:
                await self._send_error(message, "Missing actor_id")
                return

            self._isolated_actors.add(actor_id)

            # Schedule un-isolate if duration specified
            if duration:
                asyncio.create_task(self._schedule_unisolate(actor_id, duration))

            response_content = {
                "actor_id": actor_id,
                "isolated": True,
                "duration": duration,
                "reason": reason,
            }

            await self._send_response(message, response_content)

        except Exception as e:
            logger.exception("Error isolating actor", error=str(e))
            await self._send_error(message, "Isolation operation failed", str(e))

    async def _handle_get_statistics(self, message: ActorMessage) -> None:
        """Get current security statistics."""
        try:
            external_stats = self._external_threat_detector.get_statistics()

            response_content = {
                "statistics": {
                    "total_incidents": self._stats["total_incidents"],
                    "incidents_by_level": dict(self._stats["incidents_by_level"]),
                    "incidents_by_type": dict(self._stats["incidents_by_type"]),
                    "auto_responses": self._stats["auto_responses_triggered"],
                    "manual_responses": self._stats["manual_responses_triggered"],
                    "threats_contained": self._stats["threats_contained"],
                    "threats_mitigated": self._stats["threats_mitigated"],
                    # SAFE-02 stats
                    "external_threats_detected": self._stats["external_threats_detected"],
                    "external_threats_contained": self._stats["external_threats_contained"],
                    "core_triad_escalations": self._stats["core_triad_escalations"],
                    "alert_fatigue_suppressions": self._stats["alert_fatigue_suppressions"],
                },
                "active_state": {
                    "active_incidents": len(
                        [
                            i
                            for i in self._incidents.values()
                            if i.status not in [IncidentStatus.CLOSED, IncidentStatus.REMEDIATED]
                        ]
                    ),
                    "blocked_sources": len(self._blocked_sources),
                    "isolated_actors": len(self._isolated_actors),
                    "tracked_indicators": len(self._threat_indicators),
                },
                "external_threat_detection": external_stats,
            }

            await self._send_response(message, response_content)

        except Exception as e:
            logger.exception("Error getting statistics", error=str(e))
            await self._send_error(message, "Statistics retrieval failed", str(e))

    async def _handle_update_config(self, message: ActorMessage) -> None:
        """Update security configuration."""
        try:
            content = message.content

            if "auto_response_enabled" in content:
                self._auto_response_enabled = content["auto_response_enabled"]

            if "alert_threshold" in content:
                with contextlib.suppress(ValueError):
                    self._alert_threshold = ThreatLevel(content["alert_threshold"]).value

            if "max_incidents" in content:
                self._max_incidents = content["max_incidents"]

            response_content = {
                "updated": True,
                "current_config": {
                    "auto_response_enabled": self._auto_response_enabled,
                    "alert_threshold": self._alert_threshold,
                    "max_incidents": self._max_incidents,
                },
            }

            await self._send_response(message, response_content)

        except Exception as e:
            logger.exception("Error updating config", error=str(e))
            await self._send_error(message, "Config update failed", str(e))


# Import types needed by handlers (for type hints)
from datetime import UTC, datetime

from heretek_swarm.actors.sentinel_prime.types import (
    IncidentStatus,
    ResponseAction,
    SecurityIncident,
    ThreatLevel,
    ThreatType,
)
