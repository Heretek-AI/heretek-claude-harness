"""
``serve`` command — start the Heretek Swarm API server.
"""

from __future__ import annotations

import sys

import click
import structlog

from heretek_swarm.cli.health import (
    _load_infrastructure_config_and_echo,
    _print_infrastructure_config,
)

logger = structlog.get_logger("cli.serve")


@click.command(
    epilog=(
        "\b\n"
        "Examples:\n"
        "  heretek-swarm serve\n"
        "  heretek-swarm serve --host 127.0.0.1 --port 9000\n"
        "  heretek-swarm serve --workers 4"
    ),
)
@click.option("--host", default="0.0.0.0", help="Host to bind to (default: 0.0.0.0)")
@click.option("--port", default=8000, type=int, help="Port to bind to (default: 8000)")
@click.option("--workers", default=1, type=int, help="Number of worker processes (default: 1)")
def serve(host: str, port: int, workers: int) -> None:
    """
    Start the Heretek Swarm API server.

    Starts uvicorn with the FastAPI application on the specified host and port.
    Uses structured logging via uvicorn's built-in configuration.
    """
    logger.info("serve_command", host=host, port=port, workers=workers)

    click.echo("Heretek Swarm API Server")
    click.echo("=" * 40)

    infra_config = _load_infrastructure_config_and_echo()

    try:
        import uvicorn
    except ImportError:
        click.echo("\n✗ uvicorn not installed. Install with: pip install uvicorn")
        sys.exit(1)

    click.echo(f"\nStarting API server on {host}:{port}...")
    click.echo("  Press Ctrl+C to stop")

    _print_infrastructure_config(infra_config)

    app_module = "heretek_swarm.api.main:app"

    log_config = uvicorn.config.LOGGING_CONFIG
    log_config["formatters"]["default"]["fmt"] = (
        "%(asctime)s | %(levelname)s | %(name)s | %(message)s"
    )
    log_config["formatters"]["access"]["fmt"] = (
        '%(asctime)s | %(client_addr)s | "%(request_line)s" %(status_code)s'
    )

    uvicorn.run(app_module, host=host, port=port, workers=workers, log_config=log_config)
