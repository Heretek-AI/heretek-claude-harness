"""
Heretek Swarm CLI package.

Defines the ``cli`` Click group and ``GroupedGroup``, then imports and
registers subcommands from per-command modules.

Usage::

    from heretek_swarm.cli import cli
    cli()

``python -m heretek_swarm.cli`` also works via ``__main__.py``.
"""

from __future__ import annotations

import difflib
import sys
import webbrowser
from importlib.metadata import PackageNotFoundError
from importlib.metadata import version as _get_version
from pathlib import Path
from typing import Any, ClassVar

import click

try:
    __version__ = _get_version("heretek-swarm")
except PackageNotFoundError:
    __version__ = "0.0.0-dev"

# =============================================================================
# GroupedGroup — organises commands into labelled sections in help output
# =============================================================================

class GroupedGroup(click.Group):
    """Custom Click group that organizes commands into labeled sections."""

    COMMAND_GROUPS: ClassVar[dict[str, list[str]]] = {
        "Core Operations": ["run", "serve", "deploy", "wizard", "consensus"],
        "Configuration": ["config", "init"],
        "Monitoring": ["status", "stop"],
    }

    def format_commands(self, _ctx: click.Context, formatter: click.HelpFormatter) -> None:
        commands = {
            name: self.commands[name]
            for name in sorted(self.commands)
            if not self.commands[name].hidden
        }
        if not commands:
            return

        placed: set[str] = set()
        for group_label, cmd_names in self.COMMAND_GROUPS.items():
            rows: list[tuple[str, str]] = []
            for cmd_name in cmd_names:
                if cmd_name in commands:
                    cmd = commands[cmd_name]
                    rows.append((cmd_name, cmd.get_short_help_str(limit=50)))
                    placed.add(cmd_name)
            if rows:
                with formatter.section(group_label):
                    formatter.write_dl(rows)

        remaining = {name: cmd for name, cmd in commands.items() if name not in placed}
        if remaining:
            rows = [
                (name, cmd.get_short_help_str(limit=50))
                for name, cmd in sorted(remaining.items())
            ]
            with formatter.section("Other"):
                formatter.write_dl(rows)

    def get_command(self, ctx: click.Context, cmd_name: str) -> click.Command | None:
        cmd = super().get_command(ctx, cmd_name)
        if cmd is not None:
            return cmd

        matches = difflib.get_close_matches(cmd_name, self.list_commands(ctx), n=1, cutoff=0.6)
        if matches:
            raise click.UsageError(
                f"No such command '{cmd_name}'. Did you mean '{matches[0]}'?",
                ctx=ctx,
            )
        raise click.UsageError(f"No such command '{cmd_name}'.", ctx=ctx)

# =============================================================================
# CLI group
# =============================================================================

@click.group(
    cls=GroupedGroup,
    invoke_without_command=True,
    help=(
        "Heretek Swarm — autonomous multi-agent system with 23 specialized agents.\n"
        "Run locally or deploy via Docker."
    ),
    epilog=(
        "\b\n"
        "Examples:\n"
        "  pip install heretek-swarm\n"
        "  heretek-swarm run\n"
        '  heretek-swarm run --no-infra --prompt "Analyze threat model"\n'
        "  heretek-swarm serve --host 127.0.0.1 --port 9000\n"
        "  heretek-swarm config wizard"
    ),
)
@click.version_option(version=__version__, prog_name="heretek-swarm")
@click.pass_context
def cli(ctx: click.Context) -> None:
    """Heretek Swarm - Autonomous multi-agent system with 23 specialized agents."""
    if ctx.invoked_subcommand is None:
        click.echo(ctx.get_help())

# =============================================================================
# Register subcommands from per-command modules
# =============================================================================

# --- Core Operations ---
from heretek_swarm.cli.consensus import consensus
from heretek_swarm.cli.deploy import deploy
from heretek_swarm.cli.run import run
from heretek_swarm.cli.serve import serve

cli.add_command(run)
cli.add_command(serve)
cli.add_command(deploy)
cli.add_command(consensus)

# --- Configuration ---
from heretek_swarm.cli.config import config

cli.add_command(config)

# --- Monitoring ---
from heretek_swarm.cli.status import status

cli.add_command(status)

# =============================================================================
# Leaf commands defined inline (small enough not to warrant separate modules)
# =============================================================================

@cli.command()
def wizard() -> None:
    """Open the Heretek Swarm wizard in your browser."""
    url = "http://localhost:3000"
    try:
        webbrowser.open(url)
        click.echo(f"Opening {url} in browser...")
    except Exception:
        click.echo(f"No browser available. Navigate to: {url}")

@cli.command()
def init() -> None:
    """
    Initialize Heretek Swarm configuration.

    Creates ~/.heretek-swarm/.env from .env.example if it doesn't already exist.
    """
    import shutil

    config_dir = Path.home() / ".heretek-swarm"
    config_file = config_dir / ".env"

    config_dir.mkdir(parents=True, exist_ok=True)
    if config_file.exists():
        click.echo(f"Already initialized: {config_file}")
        sys.exit(0)

    example_paths = [Path(".env.example"), Path(__file__).parent.parent.parent / ".env.example"]
    example_path: Path | None = None
    for p in example_paths:
        if p.exists():
            example_path = p
            break

    if example_path is None:
        click.echo("Error: .env.example not found")
        click.echo("  Searched in current directory and package directory")
        sys.exit(1)

    shutil.copy2(example_path, config_file)
    click.echo(f"Initialized: {config_file}")

@cli.command()
def stop() -> None:
    """
    Stop a running Heretek Swarm background daemon.

    Sends SIGTERM to the daemon process and cleans up the socket file.
    """
    from heretek_swarm.runtime.daemon import (
        DEFAULT_PID_FILE,
        DEFAULT_SOCKET_PATH,
        cleanup_daemon,
        read_pid_file,
        send_stop,
    )

    pid = read_pid_file(DEFAULT_PID_FILE)
    if pid is None:
        click.echo("No running daemon found")
        sys.exit(1)

    if send_stop(pid):
        click.echo(f"Shutdown signal sent to PID {pid}")
    else:
        click.echo(f"Failed to send stop signal to PID {pid} (process already gone?)")

    cleanup_daemon(DEFAULT_PID_FILE, DEFAULT_SOCKET_PATH)

# --- Goal commands ---
from heretek_swarm.cli.goal_commands import goal

cli.add_command(goal)

# =============================================================================
# Backward-compatible re-exports (tests and external consumers use these)
# =============================================================================

from heretek_swarm.cli.config_wizard import (
    AVAILABLE_PROVIDERS,
    add_provider,
    list_configured_providers,
    prompt_for_provider,
    remove_provider,
    run_wizard,
    set_default_provider,
    validate_provider,
)
from heretek_swarm.cli.display import (
    _display_consensus_results,
    _display_deliberation_results,
    _display_routed_result,
    _print_startup_banner,
)
from heretek_swarm.cli.status import (
    _display_daemon_status,
    _query_daemon_socket,
)

# =============================================================================
# Convenience alias — entry point compatibility
# =============================================================================

main = cli

if __name__ == "__main__":
    main()
