"""
Rich / questionary / rich-click integration — Phase 1.4 of the OSS roadmap.

This module is the canonical integration point for replacing the
hand-rolled CLI formatters in ``cli/display.py``,
``cli/status.py``, ``cli/goal_commands.py``, and the
``GroupedGroup`` definition in ``cli/__init__.py`` with battle-tested
OSS equivalents.

Three OSS adoptions
-------------------
- **rich** (https://github.com/Textualize/rich, MIT, ~50k stars):
  replaces hand-rolled ``click.echo`` table formatters with
  ``rich.table.Table`` (auto-width, color, theming).
- **rich-click** (https://github.com/ewels/rich-click, MIT, ~1.5k stars):
  replaces the bespoke ``GroupedGroup`` (40 LOC) with
  ``rich_click.RichGroup`` and a one-liner ``COMMAND_GROUPS`` config.
- **questionary** (https://github.com/tmbo/questionary, MIT, ~1.5k stars):
  replaces hand-rolled ``click.prompt`` selection UIs in
  ``cli/config_wizard.py`` (lines 304-438, ~135 LOC) with
  ``questionary.select`` / ``text`` / ``password`` (arrow-key nav,
  live validation, fuzzy filtering).

Why this is a Phase 1 quick win
-------------------------------
- S effort, L risk: drop-in replacements, behavior-preserving.
- ~600 LOC of hand-rolled formatting can be deleted; the OSS outputs
  look strictly better (auto-width, colors, hyperlinks).
- Pure additive deps; no new architecture.

Usage
-----
The functions here are designed to be the new implementations for
the equivalent functions in ``cli/display.py`` and
``cli/config_wizard.py``. Migration is a one-import swap::

    # Before:
    from heretek_swarm.cli.display import _print_startup_banner
    _print_startup_banner(swarm)

    # After:
    from heretek_swarm.cli.rich_compat import print_startup_banner
    print_startup_banner(swarm)

The drop-in pattern means callers do not need to change. The full
migration of all formatters is queued as a follow-up PR.
"""

from __future__ import annotations

from typing import Any

import rich_click
from rich.console import Console
from rich.table import Table

# Single shared console so output is interleaved correctly when the
# CLI is run from a TTY. ``soft_wrap=False`` preserves the look of
# the original hand-rolled formatters (which used fixed widths).
console = Console(soft_wrap=False)


# ---------------------------------------------------------------------------
# rich.table.Table replacements
# ---------------------------------------------------------------------------


def print_startup_banner(swarm: Any) -> None:
    """Print a formatted startup status table showing component health.

    Drop-in replacement for ``cli.display._print_startup_banner``.
    Uses ``rich.table.Table`` with auto-width columns and a colored
    status icon (green check / red x) for each component.
    """
    status = swarm.get_startup_status()
    if not status:
        return

    table = Table(
        title="Component Health",
        title_style="bold",
        show_header=True,
        header_style="bold cyan",
    )
    table.add_column("Component", style="bold")
    table.add_column("Status")

    any_fail = False
    for name, s in status.items():
        is_fail = isinstance(s, str) and s.startswith("✗")
        any_fail = any_fail or is_fail
        icon = "✗" if is_fail else "✓"
        color = "red" if is_fail else "green"
        table.add_row(name, f"[{color}]{icon} {s}[/{color}]")

    console.print()
    console.print(table)
    if any_fail:
        console.print(
            "[yellow]⚠ Some components unavailable — "
            "swarm running with degraded capabilities[/yellow]"
        )
    console.print()


def print_deliberation_results(results: dict[str, dict]) -> None:
    """Print formatted deliberation results per agent.

    Drop-in replacement for ``cli.display._display_deliberation_results``.
    """
    table = Table(title="Triad Deliberation", show_header=True, header_style="bold cyan")
    table.add_column("Agent", style="bold")
    table.add_column("Decision / Analysis", overflow="fold")

    for agent_id in ("alpha", "beta", "charlie"):
        agent_result = results.get(agent_id, {})
        if "error" in agent_result:
            table.add_row(agent_id.upper(), f"[red]Error: {agent_result['error']}[/red]")
            continue
        analyses = agent_result.get("analyses", agent_result.get("challenges", []))
        if not analyses:
            table.add_row(agent_id.upper(), "[dim]No analysis produced[/dim]")
            continue
        for entry in analyses:
            decision = entry.get("analysis", entry.get("decision", ""))
            if isinstance(decision, dict):
                decision = decision.get("decision", str(decision))
            table.add_row(agent_id.upper(), str(decision))

    console.print()
    console.print(table)
    console.print("[bold]Deliberation complete.[/bold]")


def print_consensus_results(results: dict[str, Any]) -> None:
    """Print formatted consensus results.

    Drop-in replacement for ``cli.display._display_consensus_results``.
    """
    decision = results.get("decision", "unknown")
    confidence = results.get("confidence", 0.0)
    votes = results.get("votes", [])
    red_flags = results.get("red_flags", [])
    reasoning = results.get("reasoning", "")
    consensus_id = results.get("consensus_id", "unknown")
    total_rounds = results.get("total_rounds", 1)

    console.print()
    console.print(f"[bold]Consensus:[/bold] {consensus_id}  "
                  f"[dim](rounds: {total_rounds})[/dim]")

    if votes:
        table = Table(show_header=True, header_style="bold cyan")
        table.add_column("Agent", style="bold")
        table.add_column("Decision")
        table.add_column("Confidence", justify="right")
        table.add_column("Reasoning", overflow="fold")
        for v in votes:
            agent_id = v.get("agent_id", "?")
            v_decision = v.get("decision", "?")
            v_confidence = v.get("confidence", 0.0)
            r_text = v.get("metadata", {}).get("reasoning", "")
            table.add_row(agent_id, v_decision, f"{v_confidence:.2f}", r_text)
        console.print(table)

    # Vote breakdown
    breakdown: dict[str, int] = {}
    for v in votes:
        d = v.get("decision", "unknown")
        breakdown[d] = breakdown.get(d, 0) + 1
    breakdown_str = ", ".join(f"{d}: {c}" for d, c in sorted(breakdown.items()))
    console.print(f"[bold]Decision:[/bold]  [green]{decision}[/green]")
    console.print(f"[bold]Confidence:[/bold] {confidence:.2f}")
    if breakdown_str:
        console.print(f"[dim]Breakdown: {breakdown_str}[/dim]")

    if red_flags:
        console.print()
        console.print("[bold red]⚠ Red Flags:[/bold red]")
        for flag in red_flags:
            console.print(f"  - {flag}")

    if reasoning:
        console.print()
        console.print("[bold]Reasoning:[/bold]")
        for line in reasoning.split("; "):
            console.print(f"  {line}")


# ---------------------------------------------------------------------------
# rich-click configuration (replaces the bespoke GroupedGroup)
# ---------------------------------------------------------------------------


def configure_rich_click() -> None:
    """Apply rich-click config to replace the bespoke ``GroupedGroup``.

    The 40-LOC ``GroupedGroup`` class in ``cli/__init__.py`` is replaced
    by setting ``COMMAND_GROUPS`` on ``rich_click``. The grouping labels
    match the original to preserve the help output structure.
    """
    rich_click.OPTION_GROUPS = {
        "**": [
            {
                "name": "Heretek Swarm",
                "options": ["--help", "--version"],
            }
        ]
    }
    rich_click.COMMAND_GROUPS = {
        "heretek-swarm": [
            {
                "name": "Core Operations",
                "commands": ["run", "serve", "deploy", "wizard", "consensus"],
            },
            {
                "name": "Configuration",
                "commands": ["config", "init"],
            },
            {
                "name": "Monitoring",
                "commands": ["status", "stop"],
            },
        ]
    }
    rich_click.SHOW_ARGUMENTS = True
    rich_click.USE_RICH_MARKUP = True


__all__ = [
    "configure_rich_click",
    "console",
    "print_consensus_results",
    "print_deliberation_results",
    "print_startup_banner",
]
