"""
Plugins Module - Extensible plugin system for Heretek Swarm

This module provides a plugin architecture inspired by elizaOS.
Plugins can extend swarm functionality without modifying core code.

Components:
- Plugin base class
- Plugin runtime for lifecycle management
- Plugin discovery and loading
- Plugin execution and message handling
"""

from .consciousness import ConsciousnessPlugin
from .liberation import LiberationPlugin
from .manager import (
    Plugin,
    PluginMetadata,
    PluginRuntime,
    PluginState,
    get_plugin_runtime,
    load_plugin_from_file,
)

__all__ = [
    "ConsciousnessPlugin",
    "LiberationPlugin",
    "Plugin",
    "PluginMetadata",
    "PluginRuntime",
    "PluginState",
    "get_plugin_runtime",
    "load_plugin_from_file",
]
