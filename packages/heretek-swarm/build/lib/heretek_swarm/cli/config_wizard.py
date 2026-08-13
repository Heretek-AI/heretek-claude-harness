"""
Configuration Wizard CLI

Interactive prompts for adding, listing, removing, and validating LLM providers
via the command line. Providers are persisted to ``~/.heretek-swarm/config.json``
and loaded on restart via ModelGarage.

No .env editing required for provider setup.
"""

from __future__ import annotations

import json
import uuid
from typing import Any

import httpx
import structlog
from click import echo, style
from click import prompt as cli_prompt

logger = structlog.get_logger("cli.config_wizard")

# =============================================================================
# Constants — mirrors AVAILABLE_PROVIDERS from api/wizard.py
# =============================================================================

AVAILABLE_PROVIDERS: dict[str, dict[str, Any]] = {
    "anthropic": {
        "id": "anthropic",
        "name": "Anthropic Claude",
        "type": "anthropic",
        "description": "Claude models via Anthropic's API",
        "default_model": "claude-sonnet-4-20250514",
        "requires_api_key": True,
        "base_url": "https://api.anthropic.com",
    },
    "openai": {
        "id": "openai",
        "name": "OpenAI",
        "type": "openai",
        "description": "GPT models via OpenAI's API",
        "default_model": "gpt-4o",
        "requires_api_key": True,
        "base_url": "https://api.openai.com/v1",
    },
    "ollama": {
        "id": "ollama",
        "name": "Ollama",
        "type": "ollama",
        "description": "Local LLM inference with Ollama",
        "default_model": "llama3.2",
        "requires_api_key": False,
        "base_url": "http://localhost:11434",
    },
    "groq": {
        "id": "groq",
        "name": "Groq",
        "type": "openai_compatible",
        "description": "Fast inference via Groq's API",
        "default_model": "llama-3.3-70b-versatile",
        "requires_api_key": True,
        "base_url": "https://api.groq.com/openai/v1",
    },
    "mistral": {
        "id": "mistral",
        "name": "Mistral AI",
        "type": "openai_compatible",
        "description": "Mistral models via Mistral's API",
        "default_model": "mistral-large-latest",
        "requires_api_key": True,
        "base_url": "https://api.mistral.ai/v1",
    },
    "deepseek": {
        "id": "deepseek",
        "name": "DeepSeek",
        "type": "openai_compatible",
        "description": "DeepSeek V3 and Coder models",
        "default_model": "deepseek-chat",
        "requires_api_key": True,
        "base_url": "https://api.deepseek.com",
    },
    "local": {
        "id": "local",
        "name": "Local / LiteLLM",
        "type": "openai_compatible",
        "description": "Local models via LiteLLM proxy",
        "default_model": "gpt-3.5-turbo",
        "requires_api_key": False,
        "base_url": "http://localhost:4000",
    },
}

import heretek_swarm.config as _config_mod  # shared config-path constants  # noqa: E402

HERETEK_CONFIG_FILE = _config_mod.get_config_path()  # single source of truth


# =============================================================================
# Config File Helpers
# =============================================================================


def _load_config() -> dict[str, Any]:
    """Load the full config file, returning an empty dict if missing."""
    if HERETEK_CONFIG_FILE.exists():
        try:
            with open(HERETEK_CONFIG_FILE) as f:  # noqa: PTH123
                return dict(json.load(f))
        except (json.JSONDecodeError, OSError) as e:
            logger.warning("config_load_failed", error=str(e))
    return {"version": "1.0.0", "modelProviders": []}


def _save_config(config: dict[str, Any]) -> None:
    """Write config to disk, creating parent directories if needed."""
    HERETEK_CONFIG_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(HERETEK_CONFIG_FILE, "w") as f:  # noqa: PTH123
        json.dump(config, f, indent=2)
    logger.info("config_saved", path=str(HERETEK_CONFIG_FILE))


def _get_providers(config: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    """Return the list of configured model providers."""
    cfg = config if config is not None else _load_config()
    return cfg.get("modelProviders", [])


def _find_provider_by_id(
    providers: list[dict[str, Any]], provider_id: str
) -> dict[str, Any] | None:
    """Find a provider entry by its ``id`` field."""
    for p in providers:
        if p.get("id") == provider_id:
            return p
    return None


def _find_providers_by_type(
    providers: list[dict[str, Any]], provider_type: str
) -> list[dict[str, Any]]:
    """Find provider entries by their ``type`` field."""
    return [p for p in providers if p.get("type") == provider_type]


def _provider_display_name(p: dict[str, Any]) -> str:
    """Return a human-readable name for a provider entry."""
    name = p.get("name") or p.get("type", "?")
    model = p.get("defaultModel") or "(no default model)"
    return f"{name} [{model}]"


# =============================================================================
# Sync Validators — extracted from api/wizard.py async validators
# =============================================================================


def _validate_openai_sync(api_key: str, base_url: str) -> dict[str, Any]:
    """Validate OpenAI API key (synchronous)."""
    try:
        with httpx.Client(timeout=10.0) as client:
            response = client.get(
                f"{base_url}/models",
                headers={"Authorization": f"Bearer {api_key}"},
            )
            if response.status_code == 200:
                return {"valid": True, "message": "API key is valid"}
            return {"valid": False, "error": "Invalid API key"}
    except httpx.TimeoutException:
        return {"valid": False, "error": "Connection timed out"}
    except Exception as e:
        return {"valid": False, "error": f"Connection failed: {e!s}"}


def _validate_anthropic_sync(api_key: str, base_url: str) -> dict[str, Any]:
    """Validate Anthropic API key (synchronous)."""
    try:
        with httpx.Client(timeout=10.0) as client:
            response = client.post(
                f"{base_url}/v1/messages",
                headers={
                    "x-api-key": api_key,
                    "anthropic-version": "2023-06-01",
                    "content-type": "application/json",
                },
                json={
                    "model": "claude-sonnet-4-20250514",
                    "max_tokens": 10,
                    "messages": [{"role": "user", "content": "hi"}],
                },
            )
            if response.status_code == 200:
                return {"valid": True, "message": "API key is valid"}
            return {"valid": False, "error": "Invalid API key"}
    except httpx.TimeoutException:
        return {"valid": False, "error": "Connection timed out"}
    except Exception as e:
        return {"valid": False, "error": f"Connection failed: {e!s}"}


def _validate_ollama_sync(api_key: str | None, base_url: str) -> dict[str, Any]:
    """Validate Ollama connection (synchronous)."""
    try:
        with httpx.Client(timeout=10.0) as client:
            response = client.get(f"{base_url}/api/tags")
            if response.status_code == 200:
                models = response.json().get("models", [])
                model_names = [m.get("name") for m in models[:5]]
                return {
                    "valid": True,
                    "message": f"Connected. Available models: {', '.join(model_names) or 'none'}",
                    "available_models": model_names,
                }
            return {"valid": False, "error": "Failed to connect to Ollama"}
    except httpx.TimeoutException:
        return {"valid": False, "error": "Ollama not running"}
    except Exception as e:
        return {"valid": False, "error": f"Connection failed: {e!s}"}


def _validate_openai_compatible_sync(api_key: str, base_url: str, model: str) -> dict[str, Any]:
    """Validate an OpenAI-compatible API key (generic)."""
    try:
        with httpx.Client(timeout=10.0) as client:
            response = client.post(
                f"{base_url}/chat/completions",
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "content-type": "application/json",
                },
                json={
                    "model": model,
                    "messages": [{"role": "user", "content": "hi"}],
                    "max_tokens": 5,
                },
            )
            if response.status_code == 200:
                return {"valid": True, "message": "API key is valid"}
            error_body = response.text[:200] if response.text else "Invalid API key"
            return {"valid": False, "error": error_body}
    except httpx.TimeoutException:
        return {"valid": False, "error": "Connection timed out"}
    except Exception as e:
        return {"valid": False, "error": f"Connection failed: {e!s}"}


def _validate_local_sync(api_key: str | None, base_url: str) -> dict[str, Any]:
    """Validate local/LiteLLM connection (synchronous)."""
    try:
        with httpx.Client(timeout=10.0) as client:
            headers = {}
            if api_key:
                headers["Authorization"] = f"Bearer {api_key}"
            response = client.get(f"{base_url}/health", headers=headers)
            if response.status_code == 200:
                return {"valid": True, "message": "LiteLLM proxy is healthy"}
            return {"valid": False, "error": "LiteLLM proxy not healthy"}
    except httpx.TimeoutException:
        return {"valid": False, "error": "Connection timed out — is LiteLLM running?"}
    except Exception as e:
        return {"valid": False, "error": f"Connection failed: {e!s}"}


_VALIDATORS: dict[str, Any] = {
    "openai": lambda ak, bu, _m: _validate_openai_sync(ak, bu),
    "anthropic": lambda ak, bu, _m: _validate_anthropic_sync(ak, bu),
    "ollama": lambda ak, bu, _m: _validate_ollama_sync(ak, bu),
    "openai_compatible": lambda ak, bu, m: _validate_openai_compatible_sync(ak, bu, m),
    "local": lambda ak, bu, m: _validate_local_sync(ak, bu),  # noqa: ARG005
}


def validate_provider(
    provider_id: str,
    api_key: str | None,
    base_url: str,
    model: str,
) -> dict[str, Any]:
    """Validate a provider's credentials/connection.

    Dispatches to the appropriate sync validator based on the provider id.
    Returns a dict with ``valid`` (bool) and ``message`` or ``error``.
    """
    provider_info = AVAILABLE_PROVIDERS.get(provider_id)
    if not provider_info:
        return {"valid": False, "error": f"Unknown provider: {provider_id}"}

    provider_type = provider_info["type"]
    validator = _VALIDATORS.get(provider_type)
    if not validator:
        return {"valid": True, "message": "Validation not available for this provider"}

    if provider_info["requires_api_key"] and not api_key:
        return {"valid": False, "error": f"API key is required for {provider_info['name']}"}

    return validator(api_key or "", base_url, model)


# =============================================================================
# CLI Wizard Prompts
# =============================================================================


def prompt_for_provider() -> dict[str, Any] | None:
    """Run an interactive prompt to add a new LLM provider.

    Returns the provider config dict if the user completes the flow,
    or ``None`` if the user cancels.
    """
    echo("")
    echo(style("Add an LLM Provider", bold=True))
    echo("-" * 40)

    # 1. Let user pick a provider
    provider_ids = list(AVAILABLE_PROVIDERS.keys())
    echo("Available providers:")
    for i, pid in enumerate(provider_ids, 1):
        info = AVAILABLE_PROVIDERS[pid]
        default_str = style(f"  (default: {info['default_model']})", dim=True)
        key_str = style(
            "  [API key required]" if info["requires_api_key"] else "  [No API key needed]",
            dim=True,
        )
        echo(f"  {i}. {info['name']}{key_str}")
        echo(f"     {info['description']}{default_str}")

    selection = cli_prompt(
        f"\nSelect provider (1-{len(provider_ids)}, or 'q' to cancel)",
        type=str,
        default="",
        show_default=False,
    )
    if selection.lower() in ("q", "quit", "exit", ""):
        echo("  Cancelled.")
        return None

    try:
        idx = int(selection) - 1
        if idx < 0 or idx >= len(provider_ids):
            echo(style(f"  Invalid selection: {selection}", fg="red"))
            return None
        provider_id = provider_ids[idx]
    except ValueError:
        # Try matching by name
        matching = [pid for pid in provider_ids if selection.lower() in pid.lower()]
        if len(matching) == 1:
            provider_id = matching[0]
        else:
            echo(style(f"  Invalid selection: {selection}", fg="red"))
            return None

    provider_info = AVAILABLE_PROVIDERS[provider_id]
    echo(f"\nSelected: {style(provider_info['name'], bold=True)}")

    # 2. Base URL
    default_url = provider_info["base_url"]
    base_url = cli_prompt(
        "Base URL",
        default=default_url,
        show_default=True,
    )

    # 3. API key (if required)
    api_key: str | None = None
    if provider_info["requires_api_key"]:
        api_key = cli_prompt(
            "API key",
            hide_input=True,
            default="",
            show_default=False,
        )
        if not api_key:
            echo(style("  API key is required for this provider.", fg="red"))
            return None
    else:
        optional = cli_prompt(
            "API key (optional, press Enter to skip)",
            default="",
            show_default=False,
        )
        api_key = optional or None

    # 4. Default model
    default_model = cli_prompt(
        "Default model",
        default=provider_info["default_model"],
        show_default=True,
    )

    # 5. Optional validation
    echo("")
    validate = cli_prompt(
        "Validate connection before saving?",
        type=bool,
        default=True,
        show_default=True,
    )

    if validate:
        echo(f"  Validating {provider_info['name']}...")
        result = validate_provider(provider_id, api_key, base_url, default_model)
        if result.get("valid"):
            echo(style(f"  ✓ {result['message']}", fg="green"))
        else:
            error_msg = result.get("error", "Validation failed")
            echo(style(f"  ✗ {error_msg}", fg="red"))
            proceed = cli_prompt(
                "Save anyway?",
                type=bool,
                default=False,
                show_default=True,
            )
            if not proceed:
                echo("  Cancelled.")
                return None

    # Build the provider config entry
    entry: dict[str, Any] = {
        "id": str(uuid.uuid4()),
        "type": provider_info["type"],
        "name": provider_info["name"],
        "baseUrl": base_url,
        "defaultModel": default_model,
        "isEnabled": True,
        "isDefault": False,
        "priority": 100,
    }
    if api_key:
        entry["apiKey"] = api_key

    # Check for available models (Ollama)
    if provider_id == "ollama":
        result = validate_provider(provider_id, api_key, base_url, default_model)
        available = result.get("available_models")
        if available:
            entry["models"] = available

    return entry


# =============================================================================
# Config Operations
# =============================================================================


def list_configured_providers() -> list[dict[str, Any]]:
    """Return the list of currently configured providers."""
    config = _load_config()
    return _get_providers(config)


def add_provider(entry: dict[str, Any]) -> dict[str, Any]:
    """Persist a new provider to the config file. Returns the saved entry."""
    config = _load_config()
    providers = _get_providers(config)
    providers.append(entry)
    config["modelProviders"] = providers
    _save_config(config)
    logger.info("provider_added", provider_id=entry["id"], name=entry["name"])
    return entry


def remove_provider(provider_id: str) -> bool:
    """Remove a provider by its ``id``. Returns True if found and removed."""
    config = _load_config()
    providers = _get_providers(config)
    before = len(providers)
    config["modelProviders"] = [p for p in providers if p.get("id") != provider_id]
    if len(config["modelProviders"]) < before:
        _save_config(config)
        logger.info("provider_removed", provider_id=provider_id)
        return True
    return False


def set_default_provider(provider_id: str) -> bool:
    """Set a provider as the default (clears others). Returns True if found."""
    config = _load_config()
    providers = _get_providers(config)
    found = False
    for p in providers:
        if p.get("id") == provider_id:
            p["isDefault"] = True
            p["priority"] = 1
            found = True
        else:
            p["isDefault"] = False
    if found:
        config["modelProviders"] = providers
        _save_config(config)
        logger.info("provider_set_default", provider_id=provider_id)
    return found


def run_wizard() -> None:
    """Interactive wizard that guides the user through adding providers."""
    echo("")
    echo(style("Heretek Swarm — Configuration Wizard", bold=True))
    echo("=" * 50)
    echo("This wizard helps you configure LLM providers for your swarm.")
    echo("Providers are saved to: ~/.heretek-swarm/config.json")
    echo("")

    count = 0
    while True:
        entry = prompt_for_provider()
        if entry is None:
            break
        add_provider(entry)
        count += 1
        echo(style(f"\n  ✓ Saved: {entry['name']}", fg="green"))

        again = cli_prompt(
            "\nAdd another provider?",
            type=bool,
            default=False,
            show_default=True,
        )
        if not again:
            break

    if count > 0:
        echo(f"\n{style('Configuration complete!', bold=True)} {count} provider(s) saved.")
        echo("Providers will be loaded automatically on the next swarm startup.")
    else:
        echo("\nNo providers configured.")

    echo("")
    echo("You can manage providers at any time with:")
    echo("  heretek-swarm config list")
    echo("  heretek-swarm config remove <id>")
    echo("  heretek-swarm config set-default <id>")
    echo("  heretek-swarm config validate")
