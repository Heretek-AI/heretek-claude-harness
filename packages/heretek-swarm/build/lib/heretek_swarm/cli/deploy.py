"""
``deploy`` command — deploy Heretek Swarm agents via container runtime.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import click
import httpx
import structlog

from heretek_swarm.cli.health import check_compose_plugin, check_container_runtime

logger = structlog.get_logger("cli.deploy")

DEFAULT_API_BASE = "http://localhost:8000"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _fetch_wizard_config(api_base: str) -> dict[str, Any]:
    """Fetch wizard configuration from the API.

    Returns an empty dict if the API is unreachable.
    """
    try:
        response = httpx.get(f"{api_base}/api/wizard/config", timeout=5.0)
        response.raise_for_status()
        return response.json()
    except httpx.ConnectError:
        logger.warning("api_unavailable", api_base=api_base)
        return {}
    except httpx.HTTPError as e:
        logger.warning("api_error", error=str(e))
        return {}


# ---------------------------------------------------------------------------
# Click command
# ---------------------------------------------------------------------------


@click.command(
    epilog=(
        "\b\n"
        "Examples:\n"
        "  heretek-swarm deploy\n"
        "  heretek-swarm deploy --production --scale 3\n"
        "  heretek-swarm deploy --nats-url nats://cluster:4222"
    ),
)
@click.option("--production", is_flag=True, help="Deploy to production mode")
@click.option("--scale", default=1, type=int, help="Number of agent instances (default: 1)")
@click.option("--nats-url", envvar="HERETEK_NATS_URL", required=True, help="NATS server URL")
@click.option("--api-base", default=DEFAULT_API_BASE, help="API base URL")
@click.option(
    "--check-runtime/--no-check-runtime",
    default=True,
    help="Check container runtime availability",
)
def deploy(
    production: bool, scale: int, nats_url: str, api_base: str, check_runtime: bool
) -> None:
    """
    Deploy Heretek Swarm agents.

    Reads wizard configuration from the API, checks Docker/Podman availability,
    and prints deployment instructions.
    """
    logger.info(
        "deploy_command",
        production=production,
        scale=scale,
        nats_url=nats_url,
        api_base=api_base,
    )

    click.echo("Heretek Swarm Deployment")
    click.echo("=" * 40)

    # Step 1: Read wizard config from API
    click.echo("\n[1/3] Reading wizard configuration...")
    wizard_config = _fetch_wizard_config(api_base)

    if wizard_config.get("wizard_completed"):
        click.echo("  ✓ Wizard configuration found")
        infrastructure = wizard_config.get("infrastructure", [])
        if infrastructure:
            click.echo(f"  ✓ {len(infrastructure)} infrastructure service(s) configured")
        providers = wizard_config.get("database_configured", {}).get("providers", [])
        if providers:
            click.echo(f"  ✓ {len(providers)} LLM provider(s) configured")
    else:
        click.echo("  ⚠ No wizard configuration found. Run 'heretek-swarm wizard' first.")

    # Step 2: Check container runtime
    click.echo("\n[2/3] Checking container runtime...")
    runtime, version = check_container_runtime()

    if runtime:
        click.echo(f"  ✓ {runtime.capitalize()} found: {version}")

        if check_compose_plugin(runtime):
            click.echo(f"  ✓ {runtime.capitalize()} Compose plugin available")
        else:
            click.echo(f"  ⚠ {runtime.capitalize()} Compose plugin not found")
            click.echo("    Install with: " + runtime + " compose install")
    else:
        click.echo(f"  ✗ {version}")
        click.echo("\n    Container runtime required for deployment.")
        click.echo("    Install Docker: https://docs.docker.com/get-docker/")
        click.echo("    Or Podman: https://podman.io/getting-started/installation")

    # Step 3: Print deployment instructions
    click.echo("\n[3/3] Deployment instructions:")
    click.echo("-" * 40)

    if runtime:
        compose_file = Path("docker-compose.yml")
        if compose_file.exists():
            click.echo("\nTo start the deployment:")
            click.echo(f"  {runtime} compose up -d")
            if production:
                click.echo(f"  {runtime} compose up -d --scale agent={scale}")
        else:
            click.echo("\nNo docker-compose.yml found in current directory.")
            click.echo("Create one or use heretek-swarm generate-compose.")
    else:
        click.echo("\n  Cannot proceed without container runtime.")
        click.echo("  Please install Docker or Podman first.")

    click.echo("\n" + "=" * 40)
    click.echo("Deployment ready. Run 'heretek-swarm status' to verify.")
