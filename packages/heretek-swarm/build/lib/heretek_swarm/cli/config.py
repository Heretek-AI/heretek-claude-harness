"""
``config`` command group — manage LLM provider configuration.

Subcommands delegate to the ``config_wizard`` module for provider CRUD
and interactive wizard flows.
"""

from __future__ import annotations

from typing import Any

import click
import structlog

from heretek_swarm.cli.config_wizard import (
    AVAILABLE_PROVIDERS,
    list_configured_providers,
    remove_provider,
    run_wizard,
    set_default_provider,
    validate_provider,
)

logger = structlog.get_logger("cli.config")


# ---------------------------------------------------------------------------
# Parent group
# ---------------------------------------------------------------------------


@click.group()
def config() -> None:
    """
    Manage LLM provider configuration.

    Configure providers (OpenAI, Ollama, Anthropic, etc.) interactively
    via the wizard, or manage them directly with subcommands.
    Providers are persisted to ``~/.heretek-swarm/config.json`` and loaded
    on the next swarm startup.
    """


# ---------------------------------------------------------------------------
# Subcommands
# ---------------------------------------------------------------------------


@config.command("wizard")
def config_wizard() -> None:
    """
    Interactive configuration wizard for adding LLM providers.

    Prompts you through selecting a provider, entering API keys and
    endpoints, validating the connection, and saving to config.
    No .env editing required.
    """
    logger.info("config_wizard_command")
    run_wizard()


@config.command("list")
def config_list() -> None:
    """
    List all configured LLM providers.

    Shows provider name, type, default model, status, and whether
    each is the default provider.
    """
    logger.info("config_list_command")
    providers = list_configured_providers()

    if not providers:
        click.echo("No LLM providers configured.")
        click.echo("Run 'heretek-swarm config wizard' to add one.")
        return

    click.echo("")
    click.echo(f"Configured LLM Providers ({len(providers)})")
    click.echo("=" * 60)

    for p in providers:
        name = p.get("name", p.get("type", "?"))
        pid = p.get("id", "?")
        model = p.get("defaultModel", "(none)")
        ptype = p.get("type", "?")
        enabled = p.get("isEnabled", True)
        is_default = p.get("isDefault", False)
        base_url = p.get("baseUrl", "?")

        status_icon = "[+]" if enabled else "[-]"
        default_tag = click.style(" [default]", bold=True) if is_default else ""

        click.echo(f"\n  {name}{default_tag}")
        click.echo(f"    ID:      {pid[:8]}...{pid[-4:]}")
        click.echo(f"    Type:    {ptype}")
        click.echo(f"    Model:   {model}")
        click.echo(f"    URL:     {base_url}")
        click.echo(f"    Status:  {status_icon} {'Enabled' if enabled else 'Disabled'}")

    click.echo("")


@config.command("remove")
@click.argument("provider_id")
def config_remove(provider_id: str) -> None:
    """
    Remove a configured LLM provider by its ID (full or partial).

    PROVIDER_ID is the provider's UUID (you can provide the first
    8+ characters for partial matching).
    """
    logger.info("config_remove_command", provider_id=provider_id)
    providers = list_configured_providers()

    match = _find_provider(providers, provider_id)
    if match is None:
        click.echo(f"Provider with ID '{provider_id}' not found.")
        click.echo("Run 'heretek-swarm config list' to see configured providers.")
        return

    name = match.get("name", match.get("type", "?"))
    confirm = click.prompt(
        f"Remove provider '{name}' ({match['id'][:8]}...)?",
        type=bool,
        default=False,
        show_default=True,
    )
    if not confirm:
        click.echo("Cancelled.")
        return

    if remove_provider(match["id"]):
        click.echo(f"✓ Removed provider: {name}")
    else:
        click.echo("Failed to remove provider.")


@config.command("set-default")
@click.argument("provider_id")
def config_set_default(provider_id: str) -> None:
    """
    Set a provider as the default for routing.

    PROVIDER_ID is the provider's UUID (first 8+ chars for partial match).
    """
    logger.info("config_set_default_command", provider_id=provider_id)
    providers = list_configured_providers()

    match = _find_provider(providers, provider_id)
    if match is None:
        click.echo(f"Provider with ID '{provider_id}' not found.")
        click.echo("Run 'heretek-swarm config list' to see configured providers.")
        return

    if set_default_provider(match["id"]):
        name = match.get("name", match.get("type", "?"))
        click.echo(f"✓ {name} set as default provider.")
    else:
        click.echo("Failed to set default provider.")


@config.command("validate")
@click.argument("provider_id", required=False, default=None)
def config_validate(provider_id: str | None) -> None:
    """
    Validate connectivity for configured providers.

    If PROVIDER_ID is given (first 8+ chars), validates only that
    provider. Otherwise validates all configured providers.
    """
    logger.info("config_validate_command", provider_id=provider_id)
    providers = list_configured_providers()

    if not providers:
        click.echo("No providers configured. Run 'heretek-swarm config wizard' first.")
        return

    targets: list[dict[str, Any]] = []
    if provider_id:
        match = _find_provider(providers, provider_id)
        if match is None:
            click.echo(f"Provider with ID '{provider_id}' not found.")
            return
        targets = [match]
    else:
        targets = providers

    click.echo("")
    click.echo("Provider Validation")
    click.echo("=" * 50)

    all_passed = True
    for p in targets:
        name = p.get("name", p.get("type", "?"))
        pid = p.get("id", "")[:8]
        ptype = p.get("type", "")
        base_url = p.get("baseUrl", "")
        api_key = p.get("apiKey")
        default_model = p.get("defaultModel", "")

        provider_lookup_id = None
        for pid_candidate, info in AVAILABLE_PROVIDERS.items():
            if info["type"] == ptype:
                provider_lookup_id = pid_candidate
                break

        click.echo(f"\n  {name} ({pid}...)")
        click.echo(f"    URL:   {base_url}")
        click.echo(f"    Model: {default_model}")

        if provider_lookup_id is None:
            click.echo(
                click.style("    ✗ Unknown provider type, skipping validation", fg="yellow")
            )
            all_passed = False
            continue

        result = validate_provider(provider_lookup_id, api_key, base_url, default_model)
        if result.get("valid"):
            msg = result.get("message", "Valid")
            click.echo(click.style(f"    [+] {msg}", fg="green"))
        else:
            err = result.get("error", "Unknown error")
            click.echo(click.style(f"    [-] {err}", fg="red"))
            all_passed = False

    click.echo("")
    if all_passed:
        click.echo(click.style(" [+] All validations passed", fg="green"))
    else:
        click.echo(click.style(" [-] Some validations failed", fg="red"))
    click.echo("")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _find_provider(
    providers: list[dict[str, Any]], provider_id: str
) -> dict[str, Any] | None:
    """Find a provider by exact or partial ID match."""
    for p in providers:
        if p.get("id") == provider_id:
            return p
    for p in providers:
        pid = p.get("id", "")
        if pid.startswith(provider_id):
            return p
    return None
