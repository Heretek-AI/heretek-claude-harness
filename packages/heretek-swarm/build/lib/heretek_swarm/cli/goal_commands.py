"""
Goal commands — `heretek-swarm goal propose` and `heretek-swarm goal list`.

Propose strategic goals via Metis, list persisted goals from the file store.
"""

from __future__ import annotations

import asyncio
import os
import uuid
from datetime import UTC, datetime

import click
import structlog

logger = structlog.get_logger("goal_cli")


from typing import TYPE_CHECKING  # noqa: E402

if TYPE_CHECKING:
    from heretek_swarm.goals.models import Goal


def _goal_table_header() -> str:
    """Return the formatted column header for the goal list table."""
    return f"{'GOAL ID':<38} {'TITLE':<40} {'STATUS':<12} {'VOTES':<6} {'CREATED':<20}"


def _format_goal_row(goal: Goal) -> str:
    """Format a single Goal as a table row."""
    vote_count = len(goal.votes) if goal.votes else 0
    created = goal.created_at[:19].replace("T", " ") if goal.created_at else "-"
    title = goal.title
    if len(title) > 38:
        title = title[:37] + "\u2026"
    return f"{goal.id:<38} {title:<40} {goal.status:<12} {vote_count:<6} {created:<20}"


async def _run_goal_propose() -> None:
    """Async helper: spin up swarm, propose a goal via Metis, persist, and display."""
    from heretek_swarm.goals.models import Goal
    from heretek_swarm.goals.store import FileGoalStore
    from heretek_swarm.runtime.main_loop import AutonomousSwarm
    from heretek_swarm.swarm_logging.config import setup_logging

    setup_logging(json_output=False, include_caller_info=False)

    nats_servers_str = os.getenv("HERETEK_NATS_URL")
    if not nats_servers_str:
        raise RuntimeError(
            "HERETEK_NATS_URL is required. Set it to nats://host:port "
            "or use docker compose."
        )
    nats_servers = [s.strip() for s in nats_servers_str.split(",")]

    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        raise RuntimeError(
            "DATABASE_URL is required. Set it to postgresql://user:pass@host:port/db "
            "or use docker compose."
        )

    config = {
        "nats_servers": nats_servers,
        "health_check_interval": 30,
        "loop_interval": 1,
        "consciousness_interval": 5,
        "memory_maintenance_interval": 300,
        "scaling_interval": 60,
        "ephemeral": {"ttl_seconds": 3600},
        "persistent": {
            "connection_string": database_url,
        },
        "rag": {
            "embedding_provider": os.getenv("RAG_EMBEDDING_PROVIDER", "openai"),
            "embedding_model": os.getenv("RAG_EMBEDDING_MODEL", "text-embedding-3-small"),
            "llm_provider": os.getenv("RAG_LLM_PROVIDER", "openai"),
            "llm_model": os.getenv("RAG_LLM_MODEL", "gpt-4o-mini"),
            "collection_name": os.getenv("RAG_COLLECTION", "heretek_documents"),
        },
        "consensus": {
            "ahead_by_k": 2,
            "min_votes": 3,
            "red_flag_threshold": 0.3,
        },
    }

    no_infra = True
    click.echo("  --no-infra: goal propose runs without external infrastructure")
    click.echo("")

    swarm = AutonomousSwarm(config, no_infra=no_infra)
    await swarm.initialize()

    click.echo("  Locating Metis strategic planning agent...")

    # Find the metis actor from the supervisor
    if swarm.supervisor is None:
        click.echo(click.style("\n  \u2717 Supervisor not initialized", fg="red"))
        return

    metis_actors = swarm.supervisor.find_actors_by_capability("strategic_planning")
    if not metis_actors:
        # Fallback: try finding by topic
        metis_actors = swarm.supervisor.find_actors_by_topic("strategy")

    if not metis_actors:
        click.echo(
            click.style(
                "\n  \u2717 Metis agent not found in the swarm. "
                "Ensure the swarm is properly initialized.",
                fg="red",
            )
        )
        return

    metis_id = metis_actors[0]
    metis_actor = swarm.supervisor.actors.get(metis_id)
    if metis_actor is None:
        click.echo(click.style("\n  \u2717 Could not access Metis agent", fg="red"))
        return

    click.echo(f"  \u2713 Found Metis agent: {metis_id}")
    click.echo("")

    # Generate goal proposal
    click.echo("  Generating strategic goal proposal via Metis + LLM...")
    click.echo("  " + "-" * 60)

    try:
        result = metis_actor.generate_goal_proposal()
    except Exception as exc:
        logger.error("goal_proposal_generation_failed", error=str(exc))
        click.echo(click.style(f"\n  \u2717 Goal proposal failed: {exc}", fg="red"))
        return

    goal_id = result.get("id", str(uuid.uuid4()))
    title = result.get("title", "Untitled Goal")
    description = result.get("description", "")
    success_criteria = result.get("success_criteria", [])
    estimated_node_types = result.get("estimated_node_types", [])

    # Display the proposal
    click.echo("")
    click.echo(click.style(f"  Goal ID:     {goal_id}", fg="cyan"))
    click.echo(click.style(f"  Title:       {title}", bold=True))
    click.echo(f"  Description: {description}")
    click.echo("  Success Criteria:")
    for i, sc in enumerate(success_criteria, 1):
        click.echo(f"    {i}. {sc}")
    if estimated_node_types:
        click.echo(f"  Est. Nodes:  {', '.join(estimated_node_types)}")
    click.echo("")

    # Persist the goal
    now = datetime.now(UTC).isoformat()
    goal = Goal(
        id=goal_id,
        title=title,
        description=description,
        status="proposed",
        success_criteria=success_criteria,
        estimated_node_types=estimated_node_types,
        created_at=now,
        updated_at=now,
        votes=[],
    )

    store = FileGoalStore()
    store.save(goal)

    click.echo(click.style("  \u2713 Goal persisted to goals.json", fg="green"))
    click.echo("")


@click.group("goal")
def goal() -> None:
    """Manage strategic goals — propose, list, and track autonomous goals."""


@goal.command(
    "propose",
    epilog=("\b\nExamples:\n  heretek-swarm goal propose\n"),
)
def goal_propose() -> None:
    """
    Propose a strategic goal via Metis (LLM).

    Spins up the autonomous swarm in --no-infra mode, locates the Metis
    strategic planning agent, generates a goal proposal via LLM, persists
    it to the goal store, and displays the full proposal text.
    """
    logger.info("goal_propose_command")

    click.echo("Heretek Swarm — Goal Proposal")
    click.echo("=" * 40)
    click.echo("")

    try:
        asyncio.run(_run_goal_propose())
    except Exception as exc:
        logger.error("goal_propose_failure", error=str(exc))
        click.echo(click.style(f"\n\u2717 Goal propose failed: {exc}", fg="red"))


@goal.command(
    "list",
    epilog=(
        "\b\n"
        "Examples:\n"
        "  heretek-swarm goal list\n"
        "  heretek-swarm goal list --status accepted\n"
        "  heretek-swarm goal list --status proposed\n"
    ),
)
@click.option(
    "--status",
    "status_filter",
    default=None,
    type=click.Choice(["proposed", "voting", "accepted", "rejected"]),
    help="Filter goals by status",
)
def goal_list(status_filter: str | None) -> None:
    """
    List all persisted goals.

    Displays a formatted table showing goal ID, title, status, vote count,
    and creation time.  Optional --status flag filters by goal status.
    """
    from heretek_swarm.goals.store import FileGoalStore

    logger.info("goal_list_command", status_filter=status_filter)

    click.echo("Heretek Swarm — Goal List")
    click.echo("")

    store = FileGoalStore()
    goals = store.load_all()

    if status_filter:
        goals = [g for g in goals if g.status == status_filter]

    if not goals:
        if status_filter:
            click.echo(f"  No goals found with status '{status_filter}'.")
        else:
            click.echo("  No goals persisted yet.")
        click.echo("  Run 'heretek-swarm goal propose' to create one.")
        return

    click.echo(f"  {len(goals)} goal(s) found")
    click.echo("")
    click.echo("  " + _goal_table_header())
    click.echo("  " + "-" * len(_goal_table_header()))

    for goal in goals:
        click.echo("  " + _format_goal_row(goal))

    click.echo("")
