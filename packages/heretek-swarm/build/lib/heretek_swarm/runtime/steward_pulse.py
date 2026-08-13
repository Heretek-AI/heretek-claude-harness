"""
Steward Pulse Loop — Heartbeat management for the Steward agent.

Extracted from runtime/main_loop.py to keep that module under 800 lines.

Also feeds collected metrics into Sentinel's anomaly monitor on each pulse
(D002 fire-and-forget dispatch).  Anomaly detection is non-blocking — the
pulse never delays its heartbeat interval waiting for Sentinel.
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING, Any

import structlog

from heretek_swarm.consensus.verdict import aggregate_triad_ruling

if TYPE_CHECKING:
    from heretek_swarm.runtime.main_loop import AutonomousSwarm

logger = structlog.get_logger(__name__)

# Per D002: anomaly detection is allowed to run for at most this many
# seconds before we give up and continue the pulse loop.
_ANOMALY_SCAN_TIMEOUT = 5.0  # seconds

# Per D002: rulings older than this many seconds are skipped (fire-and-forget).
_RULING_EXPIRY_SECONDS = 60.0  # seconds

# S03: Heartbeat timeout threshold for triggering RAFT leadership elections.
# If no steward heartbeat is recorded within this window, the governance
# agents initiate a RAFT election to select a new Steward.
HEARTBEAT_TIMEOUT = 10.0  # seconds


async def _collect_swarm_metrics(supervisor: Any) -> dict[str, float]:
    """Collect swarm-level metrics for anomaly monitoring.

    Returns a lightweight metrics dict suitable for passing to
    `sentinel.monitor_agent_behavior()`.
    """
    stats = supervisor.get_statistics()
    return {
        "active_actors": float(stats.get("active_actors", 0)),
        "total_errors": float(stats.get("total_errors", 0)),
        "total_restarts": float(stats.get("total_restarts", 0)),
    }


async def _run_anomaly_scan(
    sentinel: Any,
    supervisor: Any,
) -> int:
    """Run anomaly detection across swarm + per-actor health.

    Returns the total number of alerts generated (0 if none).
    Never raises — exceptions are caught and logged internally.
    """
    alert_count = 0

    try:
        # Swarm-level health check
        swarm_metrics = await _collect_swarm_metrics(supervisor)
        alerts = await asyncio.wait_for(
            sentinel.monitor_agent_behavior(
                agent_id="steward",
                metrics=swarm_metrics,
            ),
            timeout=_ANOMALY_SCAN_TIMEOUT,
        )
        alert_count += len(alerts)

        # Per-actor health: only actors with non-zero errors
        all_status = await supervisor.get_all_status()
        for actor_id, status in all_status.items():
            if status.error_count > 0 or supervisor.restart_counts.get(actor_id, 0) > 0:
                actor_metrics = {
                    "error_count": float(status.error_count),
                    "restart_count": float(supervisor.restart_counts.get(actor_id, 0)),
                }
                try:
                    alerts = await asyncio.wait_for(
                        sentinel.monitor_agent_behavior(
                            agent_id=actor_id,
                            metrics=actor_metrics,
                        ),
                        timeout=_ANOMALY_SCAN_TIMEOUT,
                    )
                    alert_count += len(alerts)
                except TimeoutError:
                    logger.debug(
                        "steward_pulse_anomaly_scan_timeout_per_actor",
                        agent_id=actor_id,
                        timeout_s=_ANOMALY_SCAN_TIMEOUT,
                    )
    except TimeoutError:
        logger.debug(
            "steward_pulse_anomaly_scan_timeout",
            timeout_s=_ANOMALY_SCAN_TIMEOUT,
        )

    return alert_count


async def _apply_pending_tribunal_rulings(
    steward: Any,
    sentinel: Any,
) -> None:
    """Apply pending Tribunal rulings to the behavioral baseline.

    Iterates sentinel.tribunal._rulings to find rulings not yet applied.
    Tracks applied rulings in steward.internal_state to avoid re-application.

    Per D002:
    - Rulings older than _RULING_EXPIRY_SECONDS are skipped (expired).
    - Each applied ruling logs ``steward_baseline_updated``.
    - Expired rulings log ``tribunal_ruling_expired`` at WARNING.
    """
    applied: set[str] = steward.internal_state.setdefault(
        "_applied_tribunal_rulings", set()
    )
    now = datetime.now(UTC)

    try:
        rulings = dict(sentinel.tribunal._rulings)
    except Exception:
        return  # Tribunal not yet populated

    for ruling_id, ruling in rulings.items():
        if ruling_id in applied:
            continue

        # Parse timestamp — may be ISO string or datetime object
        ruling_ts = ruling.timestamp
        if isinstance(ruling_ts, str):
            ruling_ts = datetime.fromisoformat(
                ruling_ts.replace("Z", "+00:00")
            )

        # D002: skip expired rulings
        if (now - ruling_ts) > timedelta(seconds=_RULING_EXPIRY_SECONDS):
            logger.warning(
                "tribunal_ruling_expired",
                ruling_id=ruling_id,
                case_id=ruling.case_id,
                ruling_age_seconds=(now - ruling_ts).total_seconds(),
            )
            applied.add(ruling_id)
            continue

        # Apply ruling to behavioral baseline via immune manager
        try:
            if hasattr(sentinel, "_immune_manager"):
                immune_mgr = sentinel._immune_manager
                if hasattr(immune_mgr, "_immune_system"):
                    immune_system = immune_mgr._immune_system
                    # Extract pattern_id from the case/anomaly context if available
                    # The anomaly_id from the case's original_decision_id maps back
                    # to the pattern that triggered this.
                    case = sentinel.tribunal._cases.get(ruling.case_id)
                    anomaly_id = (
                        case.original_decision_id if case else ruling.case_id
                    )

                    # Request a baseline update from the immune system
                    # Use the anomaly_id as the pattern lookup key
                    immune_system.request_baseline_update(
                        pattern_id=anomaly_id,
                        requesting_agent_id="steward",
                    )

                    logger.info(
                        "steward_baseline_updated",
                        ruling_id=ruling_id,
                        case_id=ruling.case_id,
                        ruling_type=(
                            ruling.ruling_type.value
                            if hasattr(ruling.ruling_type, "value")
                            else str(ruling.ruling_type)
                        ),
                        anomaly_id=anomaly_id,
                    )
                    applied.add(ruling_id)
                else:
                    # No immune system, still mark as applied
                    logger.debug(
                        "steward_baseline_update_skipped_no_immune",
                        ruling_id=ruling_id,
                    )
                    applied.add(ruling_id)
            else:
                logger.debug(
                    "steward_baseline_update_skipped_no_manager",
                    ruling_id=ruling_id,
                )
                applied.add(ruling_id)
        except Exception as e:
            logger.error(
                "steward_baseline_update_failed",
                ruling_id=ruling_id,
                error=str(e),
            )
            # Still mark as applied to avoid repeated failures
            applied.add(ruling_id)


async def _check_heartbeat_timeout(
    swarm: AutonomousSwarm,
    steward: Any,
) -> None:
    """Check whether the steward heartbeat has timed out and trigger an election.

    Compares the current heartbeat timestamp with the previously stored one
    on ``steward.internal_state["_last_seen_heartbeat"]``.  If the gap exceeds
    ``HEARTBEAT_TIMEOUT`` and an ``ElectionManager`` is available, starts a
    RAFT election and replaces the steward with the elected leader.
    """
    # Guard: only run if ElectionManager is wired
    if not hasattr(swarm, "_election_manager") or swarm._election_manager is None:
        return

    now = datetime.now(UTC)
    last_heartbeat_str = steward.internal_state.get("_last_heartbeat")
    if last_heartbeat_str is None:
        # First pulse — seed and bail
        steward.internal_state["_last_seen_heartbeat"] = last_heartbeat_str
        return

    try:
        last_heartbeat = datetime.fromisoformat(last_heartbeat_str)
    except (ValueError, TypeError):
        steward.internal_state["_last_seen_heartbeat"] = last_heartbeat_str
        return

    # Compare against previously seen heartbeat to detect a gap
    prev_seen_str = steward.internal_state.get("_last_seen_heartbeat")
    if prev_seen_str is None:
        steward.internal_state["_last_seen_heartbeat"] = last_heartbeat_str
        return

    try:
        _prev_seen = datetime.fromisoformat(prev_seen_str)
    except (ValueError, TypeError):
        steward.internal_state["_last_seen_heartbeat"] = last_heartbeat_str
        return

    gap = (now - last_heartbeat).total_seconds()
    if gap <= HEARTBEAT_TIMEOUT:
        # Heartbeat is fresh — update the cursor
        steward.internal_state["_last_seen_heartbeat"] = last_heartbeat_str
        return

    # --- Timeout detected ---
    logger.error(
        "steward_heartbeat_timeout_detected",
        extra={
            "last_heartbeat": last_heartbeat_str,
            "gap_seconds": gap,
            "timeout_threshold": HEARTBEAT_TIMEOUT,
        },
    )

    # Log raft_election_started via Sentinel if available
    sentinel = (
        swarm.supervisor.actors.get("sentinel")
        if swarm.supervisor else None
    )
    if sentinel is not None and hasattr(sentinel, "log_election_started"):
        sentinel.log_election_started()
    else:
        logger.info("raft_election_started")

    try:
        leader = await swarm._election_manager.trigger_election()
    except Exception:
        logger.exception("election_trigger_failed")
        leader = None

    if leader is not None:
        leader_status = swarm._election_manager.get_status()
        leader_term = (
            leader_status["nodes"][leader].get("term")
            if leader in leader_status.get("nodes", {})
            else None
        )
        vote_count = len(leader_status.get("nodes", {}))

        if sentinel is not None and hasattr(sentinel, "log_leader_elected"):
            sentinel.log_leader_elected(
                leader_id=leader,
                term=leader_term,
                vote_count=vote_count,
            )
        else:
            logger.info(
                "raft_leader_elected",
                extra={
                    "leader_id": leader,
                    "term": leader_term,
                    "vote_count": vote_count,
                },
            )

        # Terminate old steward + spawn new one
        try:
            await swarm.supervisor.terminate_actor("steward")
        except Exception:
            logger.exception("terminate_old_steward_failed")

        try:
            from heretek_swarm.actors.triad.agent import StewardAgent
            await swarm.supervisor.spawn_actor(StewardAgent, "steward")
            logger.info("new_steward_spawned", leader_id=leader)
        except Exception:
            logger.exception("spawn_new_steward_failed")
    else:
        # All cycles exhausted — no leader elected
        if sentinel is not None and hasattr(sentinel, "log_election_failed"):
            sentinel.log_election_failed(
                cycles=swarm._election_manager._max_cycles
            )
        else:
            logger.error(
                "tribunal_election_failed",
                extra={
                    "cycles_attempted": swarm._election_manager._max_cycles,
                },
            )

    # Update the cursor even after a timeout to prevent re-triggering
    # on every subsequent pulse while election resolution is in progress
    steward.internal_state["_last_seen_heartbeat"] = last_heartbeat_str


import json


async def _convene_tribunal_on_anomaly(
    swarm: "AutonomousSwarm",
    alert_count: int,
    pulse_data: dict[str, Any],
) -> None:
    """Convene a Tribunal deliberation when anomalies are detected.

    Flow: Anomaly detected -> Create Tribunal case -> Triad deliberation
    -> Ruling issued -> Ruling applied to baseline if beneficial.

    This implements the PRIME_DIRECTIVE Tribunal loop:
    "The Steward monitors baseline health. The Sentinel reacts to anomalies,
    and the Triad convenes retroactively to decide if the action was a threat
    or a breakthrough."

    Args:
        swarm: The AutonomousSwarm instance.
        alert_count: Number of anomaly alerts detected.
        pulse_data: Current pulse metrics for deliberation context.
    """
    try:
        sentinel = (
            swarm.supervisor.actors.get("sentinel")
            if swarm.supervisor else None
        )
        steward = (
            swarm.supervisor.actors.get("steward")
            if swarm.supervisor else None
        )
        if sentinel is None or steward is None:
            logger.warning("tribunal_convene_skipped_missing_agents")
            return

        # Create a Tribunal case for the anomaly
        case = sentinel.tribunal.create_case(
            original_decision_id=f"anomaly-{pulse_data.get('timestamp', 'unknown')}",
            appellant_agent_id="steward",
            grounds=f"Autonomous anomaly detection: {alert_count} alerts",
            description=(
                f"Anomaly detected during steward pulse at "
                f"{pulse_data.get('timestamp', 'unknown')}. "
                f"Active actors: {pulse_data.get('active_actors', 'N/A')}. "
                f"Total {alert_count} alert(s) raised by Sentinel."
            ),
        )
        logger.info(
            "tribunal_case_created_for_anomaly",
            case_id=case.case_id,
            alert_count=alert_count,
        )

        # Trigger Triad deliberation on the anomaly
        # The deliberation_orchestrator coordinates Steward -> Alpha -> Beta -> Charlie
        if swarm._deliberation is not None:
            deliberation_result = await swarm._deliberation.run_deliberation(
                prompt=(
                    f"TRIBUNAL SESSION: Anomaly Detection Review\n"
                    f"Case ID: {case.case_id}\n"
                    f"Alerts: {alert_count} anomaly alert(s) detected\n"
                    f"Context: {json.dumps(pulse_data, default=str)}\n\n"
                    f"Alpha: Analyze the root cause and severity of these anomalies.\n"
                    f"Beta: Validate Alpha's analysis — is the threat real or a false positive?\n"
                    f"Charlie: Challenge both positions — could this be an emergent beneficial "
                    f"behavior rather than a threat?"
                ),
                timeout=90,
            )
            logger.info(
                "tribunal_deliberation_complete",
                case_id=case.case_id,
                result_keys=list(deliberation_result.keys()),
            )

            # Determine outcome and issue a ruling
            # If all three agents agree on "no threat" -> baseline update (emergent behavior)
            # If agents agree on "threat" -> immune response
            alpha_output = deliberation_result.get("alpha", "")
            beta_output = deliberation_result.get("beta", "")
            charlie_output = deliberation_result.get("charlie", "")

            ruling_verdict = aggregate_triad_ruling(
                alpha_output, beta_output, charlie_output
            )
            is_threat = ruling_verdict.verdict == "threat"
            is_emergent = ruling_verdict.verdict == "emergent"

            if is_emergent and not is_threat:
                ruling = sentinel.tribunal.issue_ruling(
                    case_id=case.case_id,
                    ruling_type="modify",
                    reasoning=(
                        f"Tribunal determined the anomaly represents emergent beneficial "
                        f"behavior. Updating baselines to accommodate this new pattern. "
                        f"Alpha: {alpha_output[:200]}... "
                        f"Beta: {beta_output[:200]}... "
                        f"Charlie: {charlie_output[:200]}..."
                    ),
                )
                logger.info(
                    "tribunal_ruling_emergent_behavior",
                    case_id=case.case_id,
                    ruling_id=ruling.ruling_id,
                )
            elif is_threat:
                ruling = sentinel.tribunal.issue_ruling(
                    case_id=case.case_id,
                    ruling_type="uphold",
                    reasoning=(
                        f"Tribunal confirms anomaly as genuine threat. "
                        f"Immune response recommended. "
                        f"Alpha: {alpha_output[:200]}... "
                        f"Beta: {beta_output[:200]}..."
                    ),
                )
                logger.info(
                    "tribunal_ruling_threat_confirmed",
                    case_id=case.case_id,
                    ruling_id=ruling.ruling_id,
                )
            else:
                ruling = sentinel.tribunal.issue_ruling(
                    case_id=case.case_id,
                    ruling_type="dismiss",
                    reasoning=(
                        f"Tribunal unable to reach consensus on anomaly classification. "
                        f"Dismissing — will re-evaluate if anomaly recurs."
                    ),
                )
                logger.info(
                    "tribunal_ruling_dismissed",
                    case_id=case.case_id,
                    ruling_id=ruling.ruling_id,
                )

            # Log tribunal outcome to Historian
            historian = (
                swarm.supervisor.actors.get("historian")
                if swarm.supervisor else None
            )
            if historian is not None:
                await historian.log_event(
                    "tribunal_convened",
                    "steward",
                    {
                        "case_id": case.case_id,
                        "ruling_id": ruling.ruling_id if ruling else None,
                        "alert_count": alert_count,
                        "is_threat": is_threat,
                        "is_emergent": is_emergent,
                        "deliberation_complete": True,
                    },
                )
        else:
            logger.warning("tribunal_convene_skipped_no_deliberation_orchestrator")

    except Exception as e:
        logger.exception(
            "tribunal_convene_failed",
            error=str(e),
            alert_count=alert_count,
        )

async def run_steward_pulse(swarm: AutonomousSwarm) -> None:
    """Steward heartbeat pulse loop.

    Runs at health_check_interval frequency. Uses the None-guard pattern —
    missing steward or historian agents log a warning and skip gracefully.
    """
    while swarm._running:
        try:
            steward = swarm.supervisor.actors.get("steward") if swarm.supervisor else None
            if steward is None:
                logger.warning("steward_pulse_skipped_no_steward")
                await asyncio.sleep(swarm._health_check_interval)
                continue

            steward.internal_state["_last_heartbeat"] = datetime.now(UTC).isoformat()
            await _check_heartbeat_timeout(swarm, steward)

            pulse_data = _build_pulse_data(swarm, steward)
            sentinel = _get_sentinel(swarm)

            if sentinel is not None and hasattr(sentinel, "_anomaly_monitor"):
                await _process_anomaly_scan(swarm, sentinel, pulse_data)
            elif sentinel is None:
                logger.warning("steward_pulse_sentinel_skipped_no_sentinel")

            if sentinel is not None and hasattr(sentinel, "tribunal"):
                await _apply_pending_tribunal_rulings(steward=steward, sentinel=sentinel)

            await _log_pulse_to_historian(swarm, pulse_data)

            await asyncio.sleep(swarm._health_check_interval)
        except asyncio.CancelledError:
            break
        except Exception as e:
            logger.error("steward_pulse_error", error=str(e))
            await asyncio.sleep(swarm._health_check_interval)


def _build_pulse_data(swarm: AutonomousSwarm, steward: Any) -> dict[str, Any]:
    """Build the pulse data dict for a heartbeat."""
    return {
        "timestamp": datetime.now(UTC).isoformat(),
        "active_actors": len(swarm.supervisor.actors) if swarm.supervisor else 0,
        "deliberations_active": len(getattr(steward, "active_deliberations", {})),
        "heartbeat_healthy": True,
    }


def _get_sentinel(swarm: AutonomousSwarm) -> Any:
    """Get the sentinel actor, or None."""
    if swarm.supervisor is None:
        return None
    return swarm.supervisor.actors.get("sentinel")


async def _process_anomaly_scan(
    swarm: AutonomousSwarm, sentinel: Any, pulse_data: dict[str, Any]
) -> None:
    """Run anomaly scan and convene tribunal if anomalies detected."""
    alert_count = await _run_anomaly_scan(
        sentinel=sentinel, supervisor=swarm.supervisor,
    )
    if alert_count > 0:
        logger.warning(
            "steward_pulse_anomaly_detected",
            alert_count=alert_count,
            timestamp=pulse_data["timestamp"],
        )
        pulse_data["heartbeat_healthy"] = False
        await _convene_tribunal_on_anomaly(
            swarm=swarm, alert_count=alert_count, pulse_data=pulse_data,
        )


async def _log_pulse_to_historian(
    swarm: AutonomousSwarm, pulse_data: dict[str, Any]
) -> None:
    """Log pulse data via the Historian agent."""
    historian = (
        swarm.supervisor.actors.get("historian") if swarm.supervisor else None
    )
    if historian is not None:
        await historian.log_event("steward_pulse", "steward", pulse_data)
        logger.info("steward_pulse_logged", pulse_data=pulse_data)
    else:
        logger.warning("steward_pulse_historian_skipped_no_historian")
