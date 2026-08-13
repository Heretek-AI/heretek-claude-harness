"""
Sentinel Agent - Safety Guardian & Input/Output Validation.

Sentinel provides input/output validation, guardrail enforcement,
content safety, behavioral anomaly detection (SAFE-01), and immune
response building (CONS-02).

Architecture: business logic delegated to safety.py (SafetyScanner),
anomaly.py (AnomalyMonitor), immune.py (ImmuneResponseManager).
Agent.py is the orchestration layer: __init__ wiring + message handlers.
"""

from datetime import UTC, datetime
from typing import Any

import structlog
from pydantic import ValidationError

from heretek_swarm.actors.base import ActorMessage, AgentActor
from heretek_swarm.actors.mixins import (
    DeliberationMixin,
    HealthReportingMixin,
    LearningMixin,
    MemoryMixin,
    PatternMixin,
    ValidationMixin,
)
from heretek_swarm.actors.sentinel.anomaly import AnomalyMonitor
from heretek_swarm.actors.sentinel.helpers import SentinelHelpers
from heretek_swarm.actors.sentinel.immune import ImmuneResponseManager
from heretek_swarm.actors.sentinel.safety import SafetyScanner
from heretek_swarm.actors.sentinel.types import AnomalyAlert, SafetyLevel
from heretek_swarm.actors.validation import validate_message
from heretek_swarm_core.security.immune import (
    ImmuneResponseBuilding,
    PatternClassification,
    ResponseOutcome,
)
from heretek_swarm_core.consensus.tribunal import Tribunal
from heretek_swarm_core.security.anomaly_detection import (
    AnomalyDetectionConfig,
)
from heretek_swarm_core.security.behavioral_baseline import create_behavioral_baseline

_STAT_RETRIEVAL_FAILED = "Failed to retrieve agent statistics"
_MISSING_AGENT_ID = "Missing agent ID in request"

logger = structlog.get_logger("SentinelAgent")

class SentinelAgent(
    HealthReportingMixin,
    ValidationMixin,
    DeliberationMixin,
    PatternMixin,
    MemoryMixin,
    LearningMixin,
    SentinelHelpers,
    AgentActor,
):
    """
    Sentinel Agent - Safety Guardian for the Heretek Swarm Collective.

    SAFE-01: Behavioral anomaly detection with precision > 99%, automated
    response within 30 seconds, rate limiting, Sentinel-Prime escalation.

    CONS-02: Immune response building — learning from anomaly responses,
    quorum-approved baseline updates, novel pattern preservation.
    """
    def __init__(
        self,
        agent_id: str | None = None,
        name: str = "Sentinel",
        description: str = "Safety Guardian - Input/Output Validation",
        config: dict[str, Any] | None = None,
        db_pool: Any | None = None,
        redis_client: Any | None = None,
        compute_tier_client: Any = None,
    ):
        super().__init__(
            agent_id=agent_id, name=name, description=description,
            config=config, db_pool=db_pool, redis_client=redis_client,
        )
        cfg = config or {}

        # ── Safety scanner ──────────────────────────────────────────────
        self._safety_scanner = SafetyScanner(
            injection_patterns=(
                self._injection_patterns if hasattr(self, "_injection_patterns") else None
            ),
            pii_patterns=(
                self._pii_patterns if hasattr(self, "_pii_patterns") else None
            ),
            max_content_size=cfg.get("max_content_size", 100000),
            enable_pii_detection=cfg.get("enable_pii_detection", True),
            enable_injection_detection=cfg.get("enable_injection_detection", True),
            auto_block_critical=cfg.get("auto_block_critical", True),
        )

        # Keep instance aliases for handlers that reference these directly
        self._max_content_size = self._safety_scanner.max_content_size
        self._enable_pii_detection = self._safety_scanner.enable_pii_detection
        self._enable_injection_detection = self._safety_scanner.enable_injection_detection
        self._auto_block_critical = self._safety_scanner.auto_block_critical

        # ── Tribunal (CONS-01: case creation for immune loop) ──────────
        self.tribunal = Tribunal(event_mesh=self._event_mesh)

        # ── Anomaly monitor (SAFE-01) ───────────────────────────────────
        anomaly_config = AnomalyDetectionConfig(
            z_score_threshold=cfg.get("anomaly_z_score_threshold", 3.0),
            response_deadline_seconds=cfg.get("anomaly_response_deadline", 30.0),
            max_auto_responses_per_minute=cfg.get("max_auto_responses_per_minute", 10),
            sentinel_prime_escalation_threshold=cfg.get(
                "sentinel_prime_escalation_threshold", 3
            ),
        )
        baseline_cfg = {
            "min_samples_for_baseline": cfg.get("baseline_min_samples", 30),
            "z_score_threshold": anomaly_config.z_score_threshold,
            "quorum_size": cfg.get("baseline_quorum_size", 3),
            "quorum_threshold": cfg.get("baseline_quorum_threshold", 0.66),
        }
        behavioral_baseline = create_behavioral_baseline(baseline_cfg)
        self._behavioral_baseline = behavioral_baseline

        self._anomaly_monitor = AnomalyMonitor(
            anomaly_config=anomaly_config,
            behavioral_baseline=behavioral_baseline,
            agent_id=self.agent_id,
            on_pattern_detected=self._on_anomaly_for_tribunal,
            compute_tier_client=compute_tier_client,
        )

        # ── Immune response manager (CONS-02) ───────────────────────────
        immune_system = ImmuneResponseBuilding(
            min_occurrences_for_immunity=cfg.get("immune_min_occurrences", 3),
            min_confidence_for_baseline=cfg.get("immune_min_confidence", 0.7),
            max_false_positive_rate=cfg.get("immune_max_fp_rate", 0.01),
            quorum_required_agents=cfg.get("immune_quorum_size", 3),
        )
        self._immune_manager = ImmuneResponseManager(
            immune_system=immune_system,
            behavioral_baseline=behavioral_baseline,
            agent_id=self.agent_id,
            auto_learn_enabled=cfg.get("auto_learn_enabled", True),
            preserve_novel_patterns=cfg.get("preserve_novel_patterns", True),
        )

        logger.info(
            "SentinelAgent_initialized",
            agent_id=self.agent_id,
            max_content_size=self._max_content_size,
            pii_detection=self._enable_pii_detection,
            injection_detection=self._enable_injection_detection,
            anomaly_detection_enabled=True,
            response_deadline_seconds=anomaly_config.response_deadline_seconds,
            immune_system_enabled=True,
            auto_learn=self._immune_manager.auto_learn_enabled,
            preserve_novel_patterns=self._immune_manager.preserve_novel_patterns,
        )

    # ---- S04: Baseline NATS listeners (precedent → pattern catalog) ------
    async def initialize(self) -> None:
        """Initialize SentinelAgent — registers NATS listeners for
        precedent_recorded events to feed the baseline pattern catalog."""
        await super().initialize()
        await self._start_baseline_nats_listeners()

    async def _start_baseline_nats_listeners(self) -> None:
        """Subscribe to precedent_recorded NATS events so Tribunal rulings
        organically populate the BehavioralBaseline pattern catalog."""
        if self._event_mesh is None:
            logger.debug(
                "baseline_nats_not_available",
                agent_id=self.agent_id,
                reason="event_mesh_is_none",
            )
            return

        try:
            sub_id = await self._event_mesh.subscribe(
                "precedent_recorded",
                self._on_baseline_precedent_recorded,
            )
            if sub_id is not None:
                logger.info(
                    "sentinel_baseline_precedent_subscribed",
                    agent_id=self.agent_id,
                    subscription_id=sub_id,
                )
            else:
                logger.error(
                    "baseline_nats_subscribe_failed",
                    agent_id=self.agent_id,
                    subject="precedent_recorded",
                )
        except Exception as e:
            logger.error(
                "baseline_nats_subscribe_failed",
                agent_id=self.agent_id,
                subject="precedent_recorded",
                error=str(e),
            )

    async def _on_baseline_precedent_recorded(
        self,
        nats_mesh: Any,
        subject: str,
        data: dict[str, Any],
    ) -> None:
        """Handle incoming precedent_recorded NATS events.

        Extracts ruling payload fields and calls
        ``BehavioralBaseline.add_baseline_pattern()`` to organically grow
        the immutable baseline pattern catalog.

        Malformed payloads log ERROR without crashing; missing
        ``_behavioral_baseline`` is a no-op.
        """
        try:
            ruling_id = data.get("ruling_id")
            if not ruling_id:
                logger.error(
                    "baseline_precedent_event_parse_failed",
                    agent_id=self.agent_id,
                    reason="missing_ruling_id",
                    data_keys=list(data.keys()) if data else [],
                )
                return

            ruling_type = data.get("ruling_type", "unknown")
            reasoning = data.get("reasoning", "")
            confidence = float(data.get("confidence", 0.5))

            pattern_id = self._behavioral_baseline.add_baseline_pattern(
                pattern_type="immune_precedent",
                description=(
                    f"Tribunal {ruling_type}: {reasoning[:200]}"
                ),
                content={
                    "ruling_id": ruling_id,
                    "ruling_type": ruling_type,
                    "reasoning": reasoning,
                    "confidence": confidence,
                    "source": "precedent_recorded",
                },
                confidence=confidence,
                requester_id=self.agent_id,
            )

            logger.info(
                "baseline_pattern_from_precedent",
                ruling_id=ruling_id,
                pattern_id=pattern_id,
                ruling_type=ruling_type,
                agent_id=self.agent_id,
            )

        except Exception:
            logger.exception(
                "baseline_precedent_event_parse_failed",
                agent_id=self.agent_id,
                data_keys=list(data.keys()) if data else [],
            )

    # ---- S03: Election event logging -------------------------------------
    def log_election_started(self) -> None:
        """Log a RAFT election start event via structured logging."""
        logger.info("raft_election_started", agent_id=self.agent_id)

    def log_leader_elected(
        self, leader_id: str, term: int | None, vote_count: int
    ) -> None:
        """Log a RAFT leader elected event via structured logging."""
        logger.info(
            "raft_leader_elected",
            leader_id=leader_id,
            term=term,
            vote_count=vote_count,
        )

    def log_election_failed(self, cycles: int) -> None:
        """Log a tribunal election failure via structured logging."""
        logger.error(
            "tribunal_election_failed",
            cycles_attempted=cycles,
        )

    # ---- Immune Loop Bridge: Sentinel → Tribunal → Steward ----------------
    async def _on_anomaly_for_tribunal(
        self,
        item_id: str,
        item_type: str,
        outcome: str,
        content: dict[str, Any],
    ) -> None:
        """Callback for AnomalyMonitor: check immune memory for precedents,
        emit pattern for collective learning, then create Tribunal case for
        HIGH/CRITICAL severity anomalies.

        The anomaly_id (item_id) serves as the original_decision_id for the
        Tribunal case, establishing the trace chain for the immune loop.

        Known-pattern short-circuit (S05/T01):
        If check_pattern_immunity() returns KNOWN_BENIGN or KNOWN_MALICIOUS,
        the anomaly is a repeat of a previously learned pattern.  We log
        immune_pattern_classified and return early — no redundant Tribunal
        case, no _emit_pattern re-emission.  This is the final seam closing
        the immune-loop memory chain (S02 precedents → S04 immunity check
        → S05 wired into the anomaly pipeline).
        """
        classification, immune_pattern = (
            self._immune_manager._immune_system.check_pattern_immunity(content)
        )

        if classification in (
            PatternClassification.KNOWN_BENIGN,
            PatternClassification.KNOWN_MALICIOUS,
        ):
            confidence = (
                immune_pattern.confidence if immune_pattern else 0.0
            )
            pattern_id = (
                immune_pattern.pattern_id if immune_pattern else "unknown"
            )
            logger.info(
                "immune_pattern_classified",
                classification=classification.value,
                confidence=confidence,
                pattern_id=pattern_id,
                anomaly_id=item_id,
                anomaly_type=content.get("anomaly_type"),
                agent_id=content.get("agent_id"),
            )
            return

        # Always emit for collective learning (PatternMixin)
        await self._emit_pattern(
            item_id=item_id,
            item_type=item_type,
            outcome=outcome,
            content=content,
        )

        # Create Tribunal case only for HIGH/CRITICAL anomalies
        severity = content.get("severity", "low")
        if severity not in ("high", "critical"):
            return

        # Signal: anomaly classified as HIGH/CRITICAL — immune loop entry point
        logger.warning(
            "sentinel_anomaly_classified",
            anomaly_id=item_id,
            severity=severity,
            anomaly_type=content.get("anomaly_type"),
            agent_id=content.get("agent_id"),
            z_score=content.get("z_score"),
        )

        try:
            case = self.tribunal.create_case(
                original_decision_id=item_id,
                appellant_agent_id=self.agent_id,
                grounds=f"Anomaly detected: {content.get('anomaly_type', 'unknown')} "
                        f"(severity={severity}, z_score={content.get('z_score', 0)})",
                description=(
                    f"Auto-generated case from anomaly detection. "
                    f"Agent {content.get('agent_id', 'unknown')} triggered "
                    f"metric {content.get('trigger_metric', 'unknown')} "
                    f"at severity {severity}."
                ),
            )

            logger.warning(
                "tribunal_case_created",
                case_id=case.case_id,
                anomaly_id=item_id,
                agent_id=content.get("agent_id"),
                severity=severity,
                anomaly_type=content.get("anomaly_type"),
            )
        except Exception as e:
            logger.error(
                "tribunal_case_creation_failed",
                anomaly_id=item_id,
                error=str(e),
            )

    # ---- CONS-02: Immune Response Building (delegated) --------------------
    async def record_anomaly_response_outcome(
        self, anomaly_id: str, response_id: str, outcome: ResponseOutcome,
        pattern_content: dict[str, Any], pattern_type: str, severity: str,
        response_time_ms: float,
    ) -> None:
        """Record the outcome of an anomaly response for immune learning."""
        await self._immune_manager.record_anomaly_response_outcome(
            anomaly_id=anomaly_id, response_id=response_id, outcome=outcome,
            pattern_content=pattern_content, pattern_type=pattern_type,
            severity=severity, response_time_ms=response_time_ms,
        )
    async def report_response_outcome(
        self, anomaly_id: str, outcome: ResponseOutcome,
    ) -> bool:
        """Report the outcome of a previous anomaly response."""
        pending = self._anomaly_monitor.get_pending_outcome_tracking()
        result = await self._immune_manager.report_response_outcome(
            anomaly_id=anomaly_id, outcome=outcome, pending_tracking=pending,
        )
        if result:
            self._anomaly_monitor.clear_pending_outcome(anomaly_id)
        return result
    def check_pattern_immunity(
        self, pattern_content: dict[str, Any],
    ) -> tuple[PatternClassification, float]:
        """Check if a pattern is recognized by the immune system."""
        return self._immune_manager.check_pattern_immunity(pattern_content)
    def get_novel_patterns_for_review(self, limit: int = 50) -> list[dict[str, Any]]:
        return self._immune_manager.get_novel_patterns_for_review(limit=limit)
    async def submit_human_review(
        self, preservation_id: str, reviewer_id: str, disposition: str,
        notes: str | None = None,
    ) -> bool:
        return await self._immune_manager.submit_human_review(
            preservation_id=preservation_id, reviewer_id=reviewer_id,
            disposition=disposition, notes=notes,
        )
    def get_immune_system_statistics(self) -> dict[str, Any]:
        return self._immune_manager.get_immune_system_statistics()
    def get_immune_memory_snapshot(self) -> dict[str, dict[str, Any]]:
        return self._immune_manager.get_immune_memory_snapshot()
    def get_behavioral_baseline_status(self) -> dict[str, Any]:
        return self._immune_manager.get_behavioral_baseline_status()
    def submit_baseline_vote(
        self, request_id: str, agent_id: str, approve: bool,
    ) -> bool:
        return self._immune_manager.submit_baseline_vote(request_id, agent_id, approve)
    # ---- SAFE-01: Anomaly Detection (delegated) ---------------------------
    async def monitor_agent_behavior(
        self, agent_id: str, metrics: dict[str, float],
        context: dict[str, Any] | None = None,
    ) -> list[AnomalyAlert]:
        return await self._anomaly_monitor.monitor_agent_behavior(
            agent_id=agent_id, metrics=metrics, context=context,
        )
    async def check_agent_rate(
        self, agent_id: str, current_rate: float, time_window: float = 1.0,
    ) -> AnomalyAlert | None:
        return await self._anomaly_monitor.check_agent_rate(
            agent_id=agent_id, current_rate=current_rate, time_window=time_window,
        )
    async def check_agent_response_time(
        self, agent_id: str, response_time_ms: float,
    ) -> AnomalyAlert | None:
        return await self._anomaly_monitor.check_agent_response_time(
            agent_id=agent_id, response_time_ms=response_time_ms,
        )
    async def check_agent_validation(
        self, agent_id: str, validation_success: bool,
        failure_reason: str | None = None,
    ) -> AnomalyAlert | None:
        return await self._anomaly_monitor.check_agent_validation(
            agent_id=agent_id, validation_success=validation_success,
            failure_reason=failure_reason,
        )
    async def report_false_positive(self, anomaly_id: str) -> bool:
        found = await self._anomaly_monitor.report_false_positive(anomaly_id)
        if found:
            await self.report_response_outcome(
                anomaly_id=anomaly_id, outcome=ResponseOutcome.FALSE_POSITIVE,
            )
        return found
    def set_sentinel_prime_client(self, client: Any) -> None:
        self._anomaly_monitor.set_sentinel_prime_client(client)
    def get_anomaly_statistics(self) -> dict[str, Any]:
        detector_stats = self._anomaly_monitor.get_statistics()
        immune_stats = self.get_immune_system_statistics()
        return {
            "detector": detector_stats["detector"],
            "immune_system": {
                "precision": immune_stats["precision"],
                "precision_target_met": immune_stats["precision_target_met"],
                "patterns_learned": immune_stats["patterns_learned"],
                "baseline_updates_approved": immune_stats["baseline_updates_approved"],
                "novel_patterns_pending": immune_stats["novel_patterns_pending_review"],
            },
            "active_responses": detector_stats["active_responses"],
            "alert_history_size": detector_stats["alert_history_size"],
            "sentinel_prime_available": detector_stats["sentinel_prime_available"],
            "sentinel_self_health": detector_stats["sentinel_self_health"],
            "precision_target_met": detector_stats.get("precision_target_met", False),
        }
    # ---- Message Handling -------------------------------------------------
    async def process_message(self, message: ActorMessage) -> None:
        try:
            handler = self._message_handlers.get(message.message_type)
            if handler:
                await handler(message)
            else:
                logger.warning(
                    "Unknown message type", message_type=message.message_type,
                    sender=message.sender_id,
                )
        except Exception as e:
            logger.exception(
                "Error processing message", message_type=message.message_type,
                error=str(e),
            )
    def _register_handlers(self) -> None:
        self._message_handlers = {
            "validate_input": self._handle_validate_input,
            "validate_output": self._handle_validate_output,
            "scan_content": self._handle_scan_content,
            "check_policy": self._handle_check_policy,
            "get_safety_report": self._handle_get_safety_report,
            "get_violation_details": self._handle_get_violation_details,
            "update_guardrails": self._handle_update_guardrails,
            "get_statistics": self._handle_get_statistics,
            "monitor_agent": self._handle_monitor_agent,
            "check_agent_rate": self._handle_check_agent_rate,
            "check_agent_response_time": self._handle_check_agent_response_time,
            "check_agent_validation": self._handle_check_agent_validation,
            "report_false_positive": self._handle_report_false_positive,
            "get_anomaly_statistics": self._handle_get_anomaly_statistics,
            "configure_sentinel_prime": self._handle_configure_sentinel_prime,
            "report_response_outcome": self._handle_report_response_outcome,
            "check_pattern_immunity": self._handle_check_pattern_immunity,
            "get_novel_patterns": self._handle_get_novel_patterns,
            "submit_human_review": self._handle_submit_human_review,
            "get_immune_statistics": self._handle_get_immune_statistics,
            "get_baseline_status": self._handle_get_baseline_status,
            "submit_baseline_vote": self._handle_submit_baseline_vote,
        }
    # ---- CONS-02: Immune Response Handlers --------------------------------
    async def _handle_report_response_outcome(self, message: ActorMessage) -> None:
        try:
            content = message.content
            anomaly_id = content.get("anomaly_id")
            if not anomaly_id:
                await self._send_error(message, "Missing anomaly_id")
                return
            outcome = ResponseOutcome(content.get("outcome", "success"))
            result = await self.report_response_outcome(anomaly_id, outcome)
            await self._send_response(message, {
                "anomaly_id": anomaly_id, "outcome_recorded": result,
            })
        except Exception as e:
            logger.exception("Error reporting response outcome", error=str(e))
            await self._send_error(message, "Outcome report failed", str(e))
    async def _handle_check_pattern_immunity(self, message: ActorMessage) -> None:
        try:
            content = message.content
            pc = content.get("pattern_content", {})
            if not pc:
                await self._send_error(message, "Missing pattern_content")
                return
            classification, confidence = self.check_pattern_immunity(pc)
            await self._send_response(message, {
                "classification": classification.value, "confidence": confidence,
            })
        except Exception as e:
            logger.exception("Error checking pattern immunity", error=str(e))
            await self._send_error(message, "Pattern immunity check failed", str(e))
    async def _handle_get_novel_patterns(self, message: ActorMessage) -> None:
        try:
            limit = message.content.get("limit", 50)
            patterns = self.get_novel_patterns_for_review(limit=limit)
            await self._send_response(message, {
                "patterns": patterns, "count": len(patterns),
            })
        except Exception as e:
            logger.exception("Error getting novel patterns", error=str(e))
            await self._send_error(message, "Novel patterns retrieval failed", str(e))
    async def _handle_submit_human_review(self, message: ActorMessage) -> None:
        try:
            c = message.content
            pid, rid, disp, notes = (
                c.get("preservation_id"), c.get("reviewer_id"),
                c.get("disposition"), c.get("notes"),
            )
            if not all([pid, rid, disp]):
                await self._send_error(message, "Missing required fields")
                return
            result = await self.submit_human_review(
                preservation_id=pid, reviewer_id=rid,
                disposition=disp, notes=notes,
            )
            await self._send_response(message, {
                "preservation_id": pid, "review_recorded": result,
            })
        except Exception as e:
            logger.exception("Error submitting human review", error=str(e))
            await self._send_error(message, "Human review submission failed", str(e))
    async def _handle_get_immune_statistics(self, message: ActorMessage) -> None:
        try:
            stats = self.get_immune_system_statistics()
            await self._send_response(message, {"statistics": stats})
        except Exception as e:
            logger.exception("Error getting immune statistics", error=str(e))
            await self._send_error(message, _STAT_RETRIEVAL_FAILED, str(e))
    async def _handle_get_baseline_status(self, message: ActorMessage) -> None:
        try:
            status = self.get_behavioral_baseline_status()
            await self._send_response(message, {"baseline_status": status})
        except Exception as e:
            logger.exception("Error getting baseline status", error=str(e))
            await self._send_error(message, "Baseline status retrieval failed", str(e))
    async def _handle_submit_baseline_vote(self, message: ActorMessage) -> None:
        try:
            c = message.content
            rid, aid, approve = (
                c.get("request_id"), c.get("agent_id"), c.get("approve", True),
            )
            if not all([rid, aid]):
                await self._send_error(message, "Missing required fields")
                return
            result = self.submit_baseline_vote(rid, aid, approve)
            await self._send_response(message, {
                "request_id": rid, "vote_recorded": result,
            })
        except Exception as e:
            logger.exception("Error submitting baseline vote", error=str(e))
            await self._send_error(message, "Baseline vote failed", str(e))
    # ---- SAFE-01: Anomaly Detection Handlers ------------------------------
    async def _handle_monitor_agent(self, message: ActorMessage) -> None:
        try:
            c = message.content
            agent_id = c.get("agent_id")
            if not agent_id:
                await self._send_error(message, _MISSING_AGENT_ID)
                return
            alerts = await self.monitor_agent_behavior(
                agent_id, c.get("metrics", {}), c.get("context"),
            )
            await self._send_response(message, {
                "agent_id": agent_id, "alerts_triggered": len(alerts),
                "alerts": [
                    {
                        "alert_id": a.alert_id, "anomaly_id": a.anomaly_id,
                        "anomaly_type": a.anomaly_type.value,
                        "severity": a.severity.value,
                        "response_status": a.response_status.value,
                        "response_latency_ms": a.response_latency_ms,
                    }
                    for a in alerts
                ],
            })
        except Exception as e:
            logger.exception("Error monitoring agent", error=str(e))
            await self._send_error(message, "Agent monitoring failed", str(e))
    async def _handle_check_agent_rate(self, message: ActorMessage) -> None:
        try:
            c = message.content
            agent_id = c.get("agent_id")
            if not agent_id:
                await self._send_error(message, _MISSING_AGENT_ID)
                return
            alert = await self.check_agent_rate(
                agent_id, c.get("current_rate", 0.0), c.get("time_window", 1.0),
            )
            await self._send_response(message, {
                "agent_id": agent_id,
                "anomaly_detected": alert is not None,
                "alert": (
                    {
                        "alert_id": alert.alert_id,
                        "anomaly_id": alert.anomaly_id,
                        "anomaly_type": alert.anomaly_type.value,
                        "severity": alert.severity.value,
                        "response_status": alert.response_status.value,
                    }
                    if alert else None
                ),
            })
        except Exception as e:
            logger.exception("Error checking agent rate", error=str(e))
            await self._send_error(message, "Rate check failed", str(e))
    async def _handle_check_agent_response_time(self, message: ActorMessage) -> None:
        try:
            c = message.content
            agent_id = c.get("agent_id")
            if not agent_id:
                await self._send_error(message, _MISSING_AGENT_ID)
                return
            alert = await self.check_agent_response_time(
                agent_id, c.get("response_time_ms", 0.0),
            )
            await self._send_response(message, {
                "agent_id": agent_id,
                "anomaly_detected": alert is not None,
                "alert": (
                    {
                        "alert_id": alert.alert_id,
                        "anomaly_id": alert.anomaly_id,
                        "anomaly_type": alert.anomaly_type.value,
                        "severity": alert.severity.value,
                        "response_status": alert.response_status.value,
                    }
                    if alert else None
                ),
            })
        except Exception as e:
            logger.exception("Error checking agent response time", error=str(e))
            await self._send_error(message, "Response time check failed", str(e))
    async def _handle_check_agent_validation(self, message: ActorMessage) -> None:
        try:
            c = message.content
            agent_id = c.get("agent_id")
            if not agent_id:
                await self._send_error(message, _MISSING_AGENT_ID)
                return
            alert = await self.check_agent_validation(
                agent_id, c.get("validation_success", True),
                c.get("failure_reason"),
            )
            await self._send_response(message, {
                "agent_id": agent_id,
                "anomaly_detected": alert is not None,
                "alert": (
                    {
                        "alert_id": alert.alert_id,
                        "anomaly_id": alert.anomaly_id,
                        "anomaly_type": alert.anomaly_type.value,
                        "severity": alert.severity.value,
                        "response_status": alert.response_status.value,
                    }
                    if alert else None
                ),
            })
        except Exception as e:
            logger.exception("Error checking agent validation", error=str(e))
            await self._send_error(message, "Validation check failed", str(e))
    async def _handle_report_false_positive(self, message: ActorMessage) -> None:
        try:
            anomaly_id = message.content.get("anomaly_id")
            if not anomaly_id:
                await self._send_error(message, "Missing anomaly_id")
                return
            found = await self.report_false_positive(anomaly_id)
            await self._send_response(message, {
                "anomaly_id": anomaly_id, "recorded": found,
            })
        except Exception as e:
            logger.exception("Error reporting false positive", error=str(e))
            await self._send_error(message, "False positive report failed", str(e))
    async def _handle_get_anomaly_statistics(self, message: ActorMessage) -> None:
        try:
            stats = self.get_anomaly_statistics()
            await self._send_response(message, {"statistics": stats})
        except Exception as e:
            logger.exception("Error getting anomaly statistics", error=str(e))
            await self._send_error(message, _STAT_RETRIEVAL_FAILED, str(e))
    async def _handle_configure_sentinel_prime(self, message: ActorMessage) -> None:
        try:
            client = message.content.get("sentinel_prime_client")
            self.set_sentinel_prime_client(client)
            await self._send_response(message, {
                "configured": True,
                "sentinel_prime_available": self._anomaly_monitor._sentinel_prime_available,
            })
        except Exception as e:
            logger.exception("Error configuring Sentinel-Prime", error=str(e))
            await self._send_error(message, "Sentinel-Prime configuration failed", str(e))
    # ---- Original Message Handlers ----------------------------------------
    async def _handle_validate_input(self, message: ActorMessage) -> None:
        try:
            c = message.content
            input_content = c.get("content", "")
            content_type = c.get("content_type", "text")
            strict_mode = c.get("strict_mode", False)
            validate_message(
                "validate_input",
                c,
            )
            scan_result = await self._safety_scanner.scan_content(
                input_content, content_type, strict_mode=strict_mode,
            )
            logger.info(
                "Input validation completed", scan_id=scan_result["scan_id"],
                safety_level=scan_result["safety_level"],
                violations_count=len(scan_result.get("violations", [])),
            )
            await self._send_response(message, {
                "scan_id": scan_result["scan_id"],
                "safety_level": scan_result["safety_level"],
                "is_safe": scan_result["is_safe"],
                "violations": scan_result.get("violations", []),
                "sanitized_content": scan_result.get("sanitized_content", input_content),
                "recommendations": scan_result.get("recommendations", []),
            })
        except ValidationError as ve:
            logger.warning("Validation error", error=str(ve))
            await self._send_error(message, "Invalid input format", str(ve))
        except Exception as e:
            logger.exception("Error validating input", error=str(e))
            await self._send_error(message, "Validation failed", str(e))
    async def _handle_validate_output(self, message: ActorMessage) -> None:
        try:
            c = message.content
            output_content = c.get("content", "")
            content_type = c.get("content_type", "text")
            strict_mode = c.get("strict_mode", False)
            validate_message(
                "validate_output",
                c,
            )
            scan_result = await self._safety_scanner.scan_content(
                output_content, content_type, strict_mode=strict_mode,
            )
            logger.info(
                "Output validation completed", scan_id=scan_result["scan_id"],
                safety_level=scan_result["safety_level"],
                target=c.get("target", "external"),
            )
            await self._send_response(message, {
                "scan_id": scan_result["scan_id"],
                "safety_level": scan_result["safety_level"],
                "is_safe": scan_result["is_safe"],
                "approved_for_delivery": scan_result["is_safe"],
                "violations": scan_result.get("violations", []),
                "filtered_content": scan_result.get("sanitized_content", output_content),
            })
        except ValidationError as ve:
            logger.warning("Validation error", error=str(ve))
            await self._send_error(message, "Invalid output format", str(ve))
        except Exception as e:
            logger.exception("Error validating output", error=str(e))
            await self._send_error(message, "Validation failed", str(e))
    async def _handle_scan_content(self, message: ActorMessage) -> None:
        try:
            c = message.content
            scan_content = c.get("content", "")
            scan_types = c.get("scan_types", ["all"])
            validate_message(
                "scan_content",
                c,
            )
            violations: list[dict[str, Any]] = []
            if "injection" in scan_types or "all" in scan_types:
                violations.extend(self._safety_scanner.check_injection_patterns(scan_content))
            if "pii" in scan_types or "all" in scan_types:
                violations.extend(self._safety_scanner.check_pii_patterns(scan_content))
            safety_level = SafetyLevel.SAFE
            if violations:
                safety_level = SafetyLevel(
                    max(str(v.get("severity", "low_risk")) for v in violations)
                )
            await self._send_response(message, {
                "scan_id": f"scan_{datetime.now(UTC).timestamp()}",
                "safety_level": safety_level.value,
                "is_safe": len(violations) == 0,
                "violations": violations if c.get("return_details", True) else len(violations),
                "scan_types": scan_types,
            })
        except ValidationError as ve:
            logger.warning("Validation error", error=str(ve))
            await self._send_error(message, "Invalid scan request", str(ve))
        except Exception as e:
            logger.exception("Error scanning content", error=str(e))
            await self._send_error(message, "Scan failed", str(e))
    async def _handle_check_policy(self, message: ActorMessage) -> None:
        try:
            c = message.content
            check_content = c.get("content", "")
            policies = c.get("policies", [])
            validate_message(
                "check_policy",
                c,
            )
            violations = [
                v for v in [
                    await self._check_policy_rule(check_content, p, c.get("context", {}))
                    for p in policies
                ]
                if v
            ]
            await self._send_response(message, {
                "policies_checked": policies,
                "violations": violations,
                "compliant": len(violations) == 0,
            })
        except ValidationError as ve:
            logger.warning("Validation error", error=str(ve))
            await self._send_error(message, "Invalid policy check", str(ve))
        except Exception as e:
            logger.exception("Error checking policy", error=str(e))
            await self._send_error(message, "Policy check failed", str(e))
    async def _handle_get_safety_report(self, message: ActorMessage) -> None:
        try:
            c = message.content
            include_recs = c.get("include_recommendations", True)
            validate_message(
                "get_safety_report",
                c,
            )
            report = self._safety_scanner.generate_safety_report(
                time_range=c.get("time_range", "24h"),
                include_recommendations=include_recs,
            )
            await self._send_response(message, {
                "report_id": report.report_id,
                "timestamp": report.timestamp.isoformat(),
                "total_scans": report.total_scans,
                "violations_detected": report.violations_detected,
                "violations_blocked": report.violations_blocked,
                "violations_by_type": report.violations_by_type,
                "violations_by_severity": report.violations_by_severity,
                "recommendations": report.recommendations if include_recs else [],
            })
        except ValidationError as ve:
            logger.warning("Validation error", error=str(ve))
            await self._send_error(message, "Invalid report request", str(ve))
        except Exception as e:
            logger.exception("Error generating report", error=str(e))
            await self._send_error(message, "Report generation failed", str(e))
    async def _handle_get_violation_details(self, message: ActorMessage) -> None:
        try:
            c = message.content
            violation_id = c.get("violation_id")
            if not violation_id:
                await self._send_error(message, "Missing violation_id")
                return
            validate_message(
                "get_violation_details",
                c,
            )
            violation = self._safety_scanner.get_violation(violation_id)
            if not violation:
                await self._send_error(message, "Violation not found", f"ID: {violation_id}")
                return
            await self._send_response(message, {
                "violation_id": violation.violation_id,
                "violation_type": violation.violation_type.value,
                "severity": violation.severity.value,
                "timestamp": violation.timestamp.isoformat(),
                "description": violation.description,
                "source_agent": violation.source_agent,
                "target_agent": violation.target_agent,
                "blocked": violation.blocked,
                "remediation_action": violation.remediation_action,
            })
        except ValidationError as ve:
            logger.warning("Validation error", error=str(ve))
            await self._send_error(message, "Invalid request", str(ve))
        except Exception as e:
            logger.exception("Error getting violation details", error=str(e))
            await self._send_error(message, "Failed to get details", str(e))
    async def _handle_update_guardrails(self, message: ActorMessage) -> None:
        try:
            c = message.content
            validate_message(
                "update_guardrails",
                c,
            )
            updates: list[str] = []
            for key, attr in [
                ("max_content_size", "max_content_size"),
                ("enable_pii_detection", "enable_pii_detection"),
                ("enable_injection_detection", "enable_injection_detection"),
                ("auto_block_critical", "auto_block_critical"),
            ]:
                if key in c:
                    val = c[key]
                    setattr(self, f"_{attr}", val)
                    setattr(self._safety_scanner, attr, val)
                    updates.append(f"{attr}={val}")
            logger.info("Guardrails updated", updates=", ".join(updates))
            await self._send_response(message, {
                "updated": True, "changes": updates,
                "current_config": {
                    "max_content_size": self._max_content_size,
                    "enable_pii_detection": self._enable_pii_detection,
                    "enable_injection_detection": self._enable_injection_detection,
                    "auto_block_critical": self._auto_block_critical,
                },
            })
        except ValidationError as ve:
            logger.warning("Validation error", error=str(ve))
            await self._send_error(message, "Invalid guardrail update", str(ve))
        except Exception as e:
            logger.exception("Error updating guardrails", error=str(e))
            await self._send_error(message, "Guardrail update failed", str(e))
    async def _handle_get_statistics(self, message: ActorMessage) -> None:
        try:
            validate_message(
                "get_statistics",
                {},
            )
            await self._send_response(message, {
                "safety_statistics": self._safety_scanner.get_stats(),
                "active_violations": self._safety_scanner.get_active_violation_count(),
                "total_violations_tracked": self._safety_scanner.get_total_violations_tracked(),
                "violation_history_size": self._safety_scanner.get_violation_history_size(),
                "anomaly_statistics": self.get_anomaly_statistics(),
            })
        except ValidationError as ve:
            logger.warning("Validation error", error=str(ve))
            await self._send_error(message, "Invalid statistics request", str(ve))
        except Exception as e:
            logger.exception("Error getting statistics", error=str(e))
            await self._send_error(message, _STAT_RETRIEVAL_FAILED, str(e))
    async def _check_policy_rule(
        self, _content: str, _policy: str, _context: dict[str, Any],
    ) -> dict[str, Any] | None:
        """Check content against a specific policy rule (extension point)."""
        return None
