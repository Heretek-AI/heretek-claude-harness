"""
Heretek Swarm Plugin Management API Endpoints

Provides HTTP endpoints for:
- Listing all available plugins
- Enabling/disabling plugins
- Getting plugin status and configuration
- Managing plugin settings

Plugins available:
- ConsciousnessPlugin: Global Workspace Theory and Attention Schema
- LiberationPlugin: Security auditing and anomaly detection
"""

import os
from datetime import UTC, datetime
from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException

from heretek_swarm.gateway.auth import verify_auth

logger = structlog.get_logger("api.plugins")

# Create router
router = APIRouter(prefix="/api/plugins", tags=["plugins"], dependencies=[Depends(verify_auth)])

# Plugin state management
_plugin_states: dict[str, dict[str, Any]] = {}


def _initialize_plugin_states():
    """Initialize plugin states with defaults."""
    # Consciousness Plugin
    _plugin_states["consciousness"] = {
        "name": "ConsciousnessPlugin",
        "enabled": os.environ.get("PLUGIN_CONSCIOUSNESS_ENABLED", "true").lower() == "true",
        "description": "Global Workspace Theory and Attention Schema implementation",
        "version": "0.1.0",
        "config": {
            "workspace_capacity": int(os.environ.get("GWT_WORKSPACE_CAPACITY", "10")),
            "attention_threshold": float(os.environ.get("GWT_ATTENTION_THRESHOLD", "0.5")),
            "broadcast_enabled": os.environ.get("GWT_BROADCAST_ENABLED", "true").lower() == "true",
        },
    }

    # Liberation Plugin
    _plugin_states["liberation"] = {
        "name": "LiberationPlugin",
        "enabled": os.environ.get("PLUGIN_LIBERATION_ENABLED", "true").lower() == "true",
        "description": "Security auditing and transparent anomaly detection",
        "version": "0.1.0",
        "config": {
            "audit_enabled": os.environ.get("LIBERATION_AUDIT_ENABLED", "true").lower() == "true",
            "threat_detection": os.environ.get("LIBERATION_THREAT_DETECTION", "true").lower()
            == "true",
            "red_flag_sensitivity": float(os.environ.get("LIBERATION_SENSITIVITY", "0.3")),
        },
    }


# Initialize on module load
_initialize_plugin_states()


# =============================================================================
# Plugin List Endpoints
# =============================================================================


@router.get("")
async def get_all_plugins():
    """
    Get all available plugins and their status.

    Returns:
        List of plugins with name, status, and configuration
    """
    plugins = []
    for plugin_id, state in _plugin_states.items():
        plugins.append(
            {
                "id": plugin_id,
                "name": state["name"],
                "description": state["description"],
                "version": state["version"],
                "enabled": state["enabled"],
                "config": state["config"],
            }
        )

    return {
        "plugins": plugins,
        "total": len(plugins),
        "enabled_count": sum(1 for p in plugins if p["enabled"]),
    }


@router.get("/{plugin_id}")
async def get_plugin(plugin_id: str):
    """
    Get details of a specific plugin.

    Args:
        plugin_id: Unique plugin identifier (consciousness|liberation)

    Returns:
        Plugin details including configuration and status
    """
    if plugin_id not in _plugin_states:
        raise HTTPException(404, f"Plugin {plugin_id} not found")

    state = _plugin_states[plugin_id]

    return {
        "id": plugin_id,
        "name": state["name"],
        "description": state["description"],
        "version": state["version"],
        "enabled": state["enabled"],
        "config": state["config"],
    }


# =============================================================================
# Plugin Enable/Disable Endpoints
# =============================================================================


@router.post("/{plugin_id}/enable")
async def enable_plugin(plugin_id: str):
    """
    Enable a plugin.

    Args:
        plugin_id: Unique plugin identifier

    Returns:
        Confirmation of plugin enablement
    """
    if plugin_id not in _plugin_states:
        raise HTTPException(404, f"Plugin {plugin_id} not found")

    _plugin_states[plugin_id]["enabled"] = True

    logger.info("Plugin enabled", plugin_id=plugin_id)

    return {
        "status": "enabled",
        "plugin_id": plugin_id,
        "name": _plugin_states[plugin_id]["name"],
    }


@router.post("/{plugin_id}/disable")
async def disable_plugin(plugin_id: str):
    """
    Disable a plugin.

    Args:
        plugin_id: Unique plugin identifier

    Returns:
        Confirmation of plugin disablement
    """
    if plugin_id not in _plugin_states:
        raise HTTPException(404, f"Plugin {plugin_id} not found")

    _plugin_states[plugin_id]["enabled"] = False

    logger.info("Plugin disabled", plugin_id=plugin_id)

    return {
        "status": "disabled",
        "plugin_id": plugin_id,
        "name": _plugin_states[plugin_id]["name"],
    }


# =============================================================================
# Plugin Configuration Endpoints
# =============================================================================


@router.get("/{plugin_id}/config")
async def get_plugin_config(plugin_id: str):
    """
    Get current configuration for a plugin.

    Args:
        plugin_id: Unique plugin identifier

    Returns:
        Current plugin configuration
    """
    if plugin_id not in _plugin_states:
        raise HTTPException(404, f"Plugin {plugin_id} not found")

    return {
        "plugin_id": plugin_id,
        "config": _plugin_states[plugin_id]["config"],
    }


@router.put("/{plugin_id}/config")
async def update_plugin_config(plugin_id: str, config: dict[str, Any]):
    """
    Update configuration for a plugin.

    Args:
        plugin_id: Unique plugin identifier
        config: New configuration values

    Returns:
        Updated configuration
    """
    if plugin_id not in _plugin_states:
        raise HTTPException(404, f"Plugin {plugin_id} not found")

    # Validate and update config
    current_config = _plugin_states[plugin_id]["config"]
    current_config.update(config)

    # Type validation for known fields
    if plugin_id == "consciousness":
        if "workspace_capacity" in config and not isinstance(config["workspace_capacity"], int):
            raise HTTPException(400, "workspace_capacity must be an integer")
        if "attention_threshold" in config:
            threshold = config["attention_threshold"]
            if not isinstance(threshold, (int, float)) or not 0.0 <= threshold <= 1.0:
                raise HTTPException(400, "attention_threshold must be between 0.0 and 1.0")

    elif plugin_id == "liberation":
        if "red_flag_sensitivity" in config:
            sensitivity = config["red_flag_sensitivity"]
            if not isinstance(sensitivity, (int, float)) or not 0.0 <= sensitivity <= 1.0:
                raise HTTPException(400, "red_flag_sensitivity must be between 0.0 and 1.0")

    _plugin_states[plugin_id]["config"] = current_config

    logger.info("Plugin config updated", plugin_id=plugin_id, config=current_config)

    return {
        "plugin_id": plugin_id,
        "config": current_config,
    }


# =============================================================================
# Plugin Metrics Endpoints
# =============================================================================


@router.get("/{plugin_id}/metrics")
async def get_plugin_metrics(plugin_id: str):
    """
    Get runtime metrics for a plugin.

    Args:
        plugin_id: Unique plugin identifier

    Returns:
        Plugin-specific metrics
    """
    if plugin_id not in _plugin_states:
        raise HTTPException(404, f"Plugin {plugin_id} not found")

    state = _plugin_states[plugin_id]

    # Return basic metrics - in production these would come from actual plugin
    if plugin_id == "consciousness":
        return {
            "plugin_id": plugin_id,
            "enabled": state["enabled"],
            "metrics": {
                "workspace_items": 0,
                "attention_switches": 0,
                "broadcasts_sent": 0,
            },
            "timestamp": datetime.now(UTC).isoformat(),
        }

    if plugin_id == "liberation":
        return {
            "plugin_id": plugin_id,
            "enabled": state["enabled"],
            "metrics": {
                "audit_events": 0,
                "threats_detected": 0,
                "red_flags_raised": 0,
            },
            "timestamp": datetime.now(UTC).isoformat(),
        }

    return {
        "plugin_id": plugin_id,
        "enabled": state["enabled"],
        "metrics": {},
        "timestamp": datetime.now(UTC).isoformat(),
    }


# =============================================================================
# Plugin Status Endpoints
# =============================================================================


@router.get("/{plugin_id}/status")
async def get_plugin_status(plugin_id: str):
    """
    Get overall status of a plugin.

    Args:
        plugin_id: Unique plugin identifier

    Returns:
        Plugin status including health and state
    """
    if plugin_id not in _plugin_states:
        raise HTTPException(404, f"Plugin {plugin_id} not found")

    state = _plugin_states[plugin_id]

    return {
        "plugin_id": plugin_id,
        "name": state["name"],
        "enabled": state["enabled"],
        "healthy": state["enabled"],  # Simple health check
        "config": state["config"],
    }


# =============================================================================
# Plugin Reset Endpoint
# =============================================================================


@router.post("/{plugin_id}/reset")
async def reset_plugin(plugin_id: str):
    """
    Reset a plugin to default configuration.

    Args:
        plugin_id: Unique plugin identifier

    Returns:
        Reset confirmation with default config
    """
    if plugin_id not in _plugin_states:
        raise HTTPException(404, f"Plugin {plugin_id} not found")

    # Re-initialize to defaults
    _initialize_plugin_states()

    logger.info("Plugin reset to defaults", plugin_id=plugin_id)

    return {
        "status": "reset",
        "plugin_id": plugin_id,
        "config": _plugin_states[plugin_id]["config"],
    }


# Export router
__all__ = ["router"]
