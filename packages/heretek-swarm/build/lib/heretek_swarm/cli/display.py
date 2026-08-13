"""
Display helpers for the ``run`` command.

These format and print AutonomousSwarm output to the terminal:
startup banner, deliberation results, routed-task results, and consensus results.
"""

from __future__ import annotations

from typing import Any

import click
import structlog

logger = structlog.get_logger(__name__)


def _print_startup_banner(swarm: Any) -> None:
    """Print a formatted startup status table showing component health."""
    status = swarm.get_startup_status()
    click.echo("")
    click.echo("  " + "-" * 50)
    click.echo(f"  {'Component':<20} {'Status':<12}")
    click.echo("  " + "-" * 50)
    for name, s in status.items():
        click.echo(f"  {name:<20}: {s}")
    click.echo("  " + "-" * 50)
    any_fail = any(s.startswith("✗") for s in status.values())
    if any_fail:
        click.echo("  ⚠ Some components unavailable — swarm running with degraded capabilities")
    click.echo("")


def _display_deliberation_results(results: dict[str, dict]) -> None:
    """Print formatted deliberation results per agent."""
    for agent_id in ["alpha", "beta", "charlie"]:
        agent_result = results.get(agent_id, {})
        click.echo("")
        click.echo(f"  {agent_id.upper()} response:")
        if "error" in agent_result:
            click.echo(f"    [Error: {agent_result['error']}]")
            continue
        analyses = agent_result.get("analyses", agent_result.get("challenges", []))
        if not analyses:
            click.echo("    [No analysis produced]")
            continue
        for entry in analyses:
            decision = entry.get("analysis", entry.get("decision", ""))
            if isinstance(decision, dict):
                decision = decision.get("decision", str(decision))
            click.echo(f"    {decision}")
    click.echo("")
    click.echo("  Deliberation complete.")


def _display_routed_result(result: dict) -> None:
    """Print a compact summary of a routed task result."""
    status = result.get("status", "unknown")
    target = result.get("target_agent", "?")
    task_type = result.get("task_type", "?")
    message_id = result.get("message_id", "?")

    if status == "dispatched":
        status_icon = "✓"
    elif status == "failed":
        status_icon = "✗"
    else:
        status_icon = "?"

    click.echo("")
    click.echo(f"  {status_icon} Routed to agent: {target}")
    click.echo(f"    Task type:       {task_type}")
    click.echo(f"    Status:          {status}")
    click.echo(f"    Message ID:      {message_id}")

    error = result.get("error")
    if error:
        click.echo(f"    Error:           {error}")

    click.echo("")
    click.echo("  Route complete.")


def _display_consensus_results(results: dict[str, Any]) -> None:
    """Print formatted consensus results."""
    decision = results.get("decision", "unknown")
    confidence = results.get("confidence", 0.0)
    votes = results.get("votes", [])
    red_flags = results.get("red_flags", [])
    reasoning = results.get("reasoning", "")
    consensus_id = results.get("consensus_id", "unknown")
    round_history = results.get("round_history", [])
    total_rounds = results.get("total_rounds", 1)

    click.echo("")
    click.echo(f"  Consensus ID: {consensus_id}")
    click.echo("  " + "-" * 50)

    if total_rounds > 1 or round_history:
        click.echo(f"  Rounds: {total_rounds}")
        click.echo("")

    agent_ids = [v.get("agent_id", "?") for v in votes]
    click.echo(f"  Agents ({len(agent_ids)}): {', '.join(agent_ids)}")
    click.echo("")

    click.echo("  Votes:")
    for v in votes:
        agent_id = v.get("agent_id", "?")
        v_decision = v.get("decision", "?")
        v_confidence = v.get("confidence", 0.0)
        reasoning_text = v.get("metadata", {}).get("reasoning", "")
        line = f"    {agent_id:<20} → {v_decision:<20} (conf: {v_confidence:.2f})"
        click.echo(line)
        if reasoning_text:
            click.echo(f"      Reasoning: {reasoning_text}")

    click.echo("")
    click.echo("  " + "-" * 50)

    click.echo(f"  ✓ Decision:  {decision}")
    click.echo(f"  ✓ Confidence: {confidence:.2f}")

    breakdown: dict[str, int] = {}
    for v in votes:
        d = v.get("decision", "unknown")
        breakdown[d] = breakdown.get(d, 0) + 1
    breakdown_str = ", ".join(f"{d}: {c}" for d, c in sorted(breakdown.items()))
    click.echo(f"  Vote breakdown: {breakdown_str}")

    if red_flags:
        click.echo("")
        click.echo("  ⚠ Red Flags:")
        for flag in red_flags:
            click.echo(f"    - {flag}")

    if reasoning:
        click.echo("")
        click.echo("  Reasoning:")
        for line in reasoning.split("; "):
            click.echo(f"    {line}")

    if round_history:
        click.echo("")
        click.echo("  Round History:")
        click.echo("  " + "-" * 50)
        for rh in round_history:
            r_num = rh.get("round_number", "?")
            r_score = rh.get("consensus_score", 0.0)
            r_decision = rh.get("decision", "none")
            r_votes = rh.get("vote_count", 0)
            click.echo(
                f"    Round {r_num}: decision={r_decision}, score={r_score:.2f}, votes={r_votes}"
            )

    click.echo("")
