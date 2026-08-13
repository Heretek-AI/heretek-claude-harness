"""
``run`` command — start the Heretek Swarm autonomous runtime.
"""

from __future__ import annotations

import asyncio
import os
import signal
import sys
from typing import TYPE_CHECKING, Any

import click
import structlog

from heretek_swarm.cli.display import (
    _display_consensus_results,
    _display_deliberation_results,
    _display_routed_result,
    _print_startup_banner,
)
from heretek_swarm.cli.health import (
    _load_infrastructure_config_and_echo,
    _print_infrastructure_config,
)

if TYPE_CHECKING:
    from heretek_swarm.runtime.main_loop import AutonomousSwarm

logger = structlog.get_logger("cli.run")

# ---------------------------------------------------------------------------
# Module-level globals (signal handling needs module-level visibility)
# ---------------------------------------------------------------------------

_shutdown_event: asyncio.Event | None = None
_swarm_instance: AutonomousSwarm | None = None


# ---------------------------------------------------------------------------
# Signal handler
# ---------------------------------------------------------------------------


def _handle_signal(signum: int, frame: Any) -> None:
    """Handle SIGINT/SIGTERM for graceful shutdown."""
    sig_name = signal.Signals(signum).name
    logger.warning("shutdown_signal_received", signal=sig_name)

    if _shutdown_event:
        logger.info("initiating_graceful_shutdown", signal=sig_name)
        _shutdown_event.set()
    else:
        logger.info("immediate_exit", signal=sig_name)
        sys.exit(0)


# ---------------------------------------------------------------------------
# Async startup helper
# ---------------------------------------------------------------------------


async def _start_autonomous_swarm(
    no_infra: bool = False,
    prompt: str | None = None,
    target_agent: str | None = None,
    force_consensus: bool = False,
) -> None:
    """Start the AutonomousSwarm with signal handlers for graceful shutdown."""
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

    if no_infra:
        click.echo("  --no-infra: skipping external infrastructure connections")
        click.echo("  Components requiring Postgres, Redis, Qdrant, or NATS will be unavailable")
        config["persistent"]["connection_string"] = ""

    swarm = AutonomousSwarm(config, no_infra=no_infra)
    global _swarm_instance
    _swarm_instance = swarm

    await swarm.initialize()
    _print_startup_banner(swarm)

    if prompt:
        from heretek_swarm_core.consensus.complexity import ComplexityHeuristic

        click.echo("")
        if target_agent:
            click.echo(f"  Routing prompt to agent '{target_agent}': {prompt}")
            click.echo("  " + "-" * 50)
            try:
                result = await swarm.run_routed_task(
                    target_agent, "on_demand_analysis", {"prompt": prompt}
                )
            except Exception as e:
                click.echo(f"\n  ✗ Route failed: {e}")
                return
            _display_routed_result(result)
        else:
            heuristic = ComplexityHeuristic()
            complexity = heuristic.assess(prompt)

            logger.info(
                "auto_routing_decision",
                complexity_score=complexity.score,
                routing_decision=complexity.routing_mode,
                is_complex=complexity.is_complex,
                matched_keywords=complexity.matched_keywords,
                force_consensus=force_consensus,
            )

            if force_consensus or complexity.is_complex:
                mode_label = "forced consensus" if force_consensus else "auto-consensus"
                click.echo(f"  Routing: {mode_label} (complexity={complexity.score:.2f})")
                click.echo(f"  Consensus prompt: {prompt}")
                click.echo("  " + "-" * 50)
                try:
                    results = await swarm.run_consensus(prompt)
                except Exception as e:
                    click.echo(f"\n  ✗ Consensus failed: {e}")
                    return
                _display_consensus_results(results)
            else:
                click.echo(f"  Routing: triad deliberation (complexity={complexity.score:.2f})")
                click.echo(f"  Deliberating prompt: {prompt}")
                click.echo("  " + "-" * 50)
                try:
                    results = await swarm.run_deliberation(prompt)
                except Exception as e:
                    click.echo(f"\n  ✗ Deliberation failed: {e}")
                    return
                _display_deliberation_results(results)
        return

    await swarm.run()


# ---------------------------------------------------------------------------
# Click command
# ---------------------------------------------------------------------------


def _build_config(nats_url: str, no_infra: bool) -> dict[str, Any]:
    """Build the daemon-mode config dict shared by --detach path."""
    nats_servers = [s.strip() for s in nats_url.split(",")]

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

    if no_infra:
        config["persistent"]["connection_string"] = ""

    return config


@click.command(
    epilog=(
        "\b\n"
        "Examples:\n"
        "  heretek-swarm run\n"
        "  heretek-swarm run --detach\n"
        "  heretek-swarm run --no-infra\n"
        '  heretek-swarm run --no-infra --prompt "Analyze the strategic implications of X"\n'
        '  heretek-swarm run --prompt "analyze tradeoffs of Redis" --consensus\n'
        "  HERETEK_NATS_URL=nats://cluster1:4222,nats://cluster2:4222 heretek-swarm run"
    ),
)
@click.option("--detach", is_flag=True, help="Run in background (daemon mode)")
@click.option(
    "--nats-url",
    envvar="HERETEK_NATS_URL",
    help="NATS server URL(s), comma-separated for multiple servers",
)
@click.option(
    "--no-infra",
    is_flag=True,
    help=(
        "Skip external infrastructure connections (Postgres, Redis, Qdrant, NATS); "
        "use in-memory state only"
    ),
)
@click.option(
    "--prompt",
    type=str,
    default=None,
    help="Single prompt to deliberate through the triad, then exit",
)
@click.option(
    "--target-agent",
    type=str,
    default=None,
    help="Route prompt to a specific agent (default: triad deliberation)",
)
@click.option(
    "--consensus",
    "force_consensus",
    is_flag=True,
    default=False,
    help="Force MAKER consensus routing (bypasses complexity heuristic)",
)
def run(
    detach: bool,
    nats_url: str,
    no_infra: bool,
    prompt: str | None = None,
    target_agent: str | None = None,
    force_consensus: bool = False,
) -> None:
    """
    Start the Heretek Swarm autonomous runtime.

    Initializes and starts the AutonomousSwarm with 23 agents across 6 tiers.
    Supports graceful shutdown via SIGINT (Ctrl+C) and SIGTERM signals.

    Configuration is read from environment variables:
    - HERETEK_NATS_URL: NATS server URLs (default: nats://localhost:4222)
    - DATABASE_URL: PostgreSQL connection string
    - RAG_* environment variables for RAG configuration

    Use --no-infra to run without Docker/Postgres/Redis — the swarm uses
    in-memory state and logs graceful fallback warnings.
    """
    logger.info("run_command", detach=detach, nats_url=nats_url, no_infra=no_infra)

    click.echo("Heretek Swarm Autonomous Runtime")
    click.echo("=" * 40)

    if no_infra:
        click.echo("\n  --no-infra mode: external infrastructure connections will be skipped")
    else:
        infra_config = _load_infrastructure_config_and_echo()

    if detach:
        click.echo("\nStarting in detached mode...")
        from heretek_swarm.runtime.daemon import daemonize
        from heretek_swarm.runtime.main_loop import AutonomousSwarm
        from heretek_swarm.swarm_logging.config import setup_logging

        setup_logging(json_output=False, include_caller_info=False)

        config = _build_config(nats_url, no_infra)
        swarm = AutonomousSwarm(config, no_infra=no_infra)
        daemonize(swarm)
        return

    click.echo("\nInitializing autonomous swarm...")
    click.echo(f"  NATS: {nats_url}")

    if not no_infra:
        _print_infrastructure_config(infra_config)

    if prompt:
        try:
            asyncio.run(
                _start_autonomous_swarm(
                    no_infra=no_infra,
                    prompt=prompt,
                    target_agent=target_agent,
                    force_consensus=force_consensus,
                )
            )
        except Exception as e:
            logger.error("prompt_mode_failure", error=str(e))
            click.echo(f"\n✗ Failed to start: {e}")
            sys.exit(1)
        return

    # Long-running mode — install signal handlers
    shutdown_event = asyncio.Event()
    global _shutdown_event
    _shutdown_event = shutdown_event

    signal.signal(signal.SIGINT, _handle_signal)
    signal.signal(signal.SIGTERM, _handle_signal)

    try:
        asyncio.run(_start_autonomous_swarm(no_infra=no_infra))
    except KeyboardInterrupt:
        logger.info("shutdown_keyboard_interrupt")
        click.echo("\nShutdown complete.")
    except Exception as e:
        logger.error("startup_failure", error=str(e))
        click.echo(f"\n✗ Failed to start: {e}")
        sys.exit(1)
