"""
Configuration module for Heretek Swarm.

Provides:
- get_config_path(): canonical config file location (env-var-overridable)
- ConfigurationService, ConfigLoader, ConfigCache: database-backed config management
- SecretsLoader: SOPS-encrypted secrets decryption at startup

Usage:
    from heretek_swarm.config import get_config_path, ConfigurationService, SecretsLoader
"""

from __future__ import annotations

import os
from pathlib import Path

from .cache import ConfigCache
from .loader import (
    ConfigLoader,
    get_config,
    get_config_loader,
    get_config_with_source,
    initialize_config_loader,
    reload_config,
)
from .secrets_loader import SecretsLoader, get_secrets_loader
from .service import (
    ConfigurationService,
    get_config_service,
    initialize_config_service,
    shutdown_config_service,
)

# =============================================================================
# Canonical config path — single source of truth for provider config location.
# =============================================================================

HEREKET_CONFIG_DIR = Path.home() / ".heretek-swarm"
"""Default directory for Heretek Swarm configuration files."""

HEREKET_CONFIG_FILE = HEREKET_CONFIG_DIR / "config.json"
"""Default path for the provider configuration file."""


def get_config_path() -> Path:
    """Return the canonical path to the provider configuration file.

    Checks ``HEREKET_CONFIG_PATH`` environment variable first (for test
    isolation), then falls back to ``~/.heretek-swarm/config.json``.

    Returns:
        Full Path to the config file (does NOT guarantee it exists).
    """
    env_override = os.environ.get("HEREKET_CONFIG_PATH")
    if env_override:
        return Path(env_override)
    return HEREKET_CONFIG_FILE


__all__ = [
    # Config path
    "HEREKET_CONFIG_DIR",
    "HEREKET_CONFIG_FILE",
    # Cache
    "ConfigCache",
    # Loader
    "ConfigLoader",
    # Service
    "ConfigurationService",
    # Secrets
    "SecretsLoader",
    "get_config",
    "get_config_loader",
    "get_config_path",
    "get_config_service",
    "get_config_with_source",
    "get_secrets_loader",
    "initialize_config_loader",
    "initialize_config_service",
    "reload_config",
    "shutdown_config_service",
]
