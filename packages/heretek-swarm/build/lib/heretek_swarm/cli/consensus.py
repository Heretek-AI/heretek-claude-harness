"""
``consensus`` command — run MAKER consensus on a question.
"""

from __future__ import annotations

import asyncio
import os
import sys
from typing import Any

import click
import structlog

from heretek_swarm.cli.display import _display_consensus_results, _print_startup_banner

logger = structlog.get_logger("cli.consensus")


async def _run_consensus(
    question: str, timeout: float, max_rounds: int = 1
) -> dict[str, Any]:
    """Async helper for the consensus CLI command."""
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

    config: dict[str, Any] = {
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
    click.echo("  --no-infra: consensus runs without external infrastructure")

    swarm = AutonomousSwarm(config, no_infra=no_infra)

    await swarm.initialize()
    _print_startup_banner(swarm)

    click.echo("\nRunning consensus...")
    click.echo("  " + "-" * 50)

    return await swarm.run_consensus(question, timeout=timeout, max_rounds=max_rounds)


@click.command(
    epilog=(
        "\b\n"
        "Examples:\n"
        '  heretek-swarm consensus "should we add rate limiting?"\n'
        '  heretek-swarm consensus "should we refactor the auth module?" --timeout 180\n'
        '  heretek-swarm consensus "what database should we use?" --participants 5\n'
        '  heretek-swarm consensus "analyze the tradeoffs of caching" --rounds 3'
    ),
)
@click.argument("question")
@click.option(
    "--timeout",
    default=120,
    type=float,
    help="Consensus timeout in seconds (default: 120)",
)
@click.option(
    "--participants",
    default=None,
    type=int,
    help="Override number of participants (default: 5-7 from domain selection)",
)
@click.option(
    "--rounds",
    "max_rounds",
    default=1,
    type=int,
    help="Number of deliberation rounds with argument exchange (default: 1)",
)
def consensus(
    question: str, timeout: float, participants: int | None, max_rounds: int = 1
) -> None:
    """
    Run MAKER consensus on a question.

    Selects domain-relevant agents via topic matching, each agent votes with
    a decision and confidence through LLM, MAKER ahead-by-k voting terminates
    when a clear winner emerges, and the result is displayed with winning
    decision, confidence score, vote breakdown, and red flags.
    """
    logger.info(
        "consensus_command",
        question=question[:200],
        timeout=timeout,
        participants=participants,
        max_rounds=max_rounds,
    )

    click.echo("Heretek Swarm Consensus")
    click.echo("=" * 40)
    click.echo(f"\n  Question: {question}")
    click.echo(f"  Timeout:  {timeout}s")
    if participants is not None:
        click.echo(f"  Participants: {participants} (override)")
    if max_rounds > 1:
        click.echo(f"  Rounds:   {max_rounds} (with argument exchange)")

    click.echo("\nInitializing swarm...")

    try:
        results = asyncio.run(_run_consensus(question, timeout, max_rounds=max_rounds))
        _display_consensus_results(results)
    except Exception as e:
        logger.error("consensus_failure", error=str(e))
        click.echo(f"\n✗ Consensus failed: {e}")
        sys.exit(1)
