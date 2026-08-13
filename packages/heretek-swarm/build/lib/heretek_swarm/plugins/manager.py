"""
Plugin Manager - Extensible plugin system for Heretek Swarm

Provides plugin loading, registration, lifecycle management, and execution.
Pattern inspired by elizaOS plugin system.
"""

import asyncio
import importlib
import inspect
from collections.abc import Callable
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Optional

import structlog

logger = structlog.get_logger(__name__)


class PluginState(Enum):
    """Plugin lifecycle states."""

    UNLOADED = "unloaded"
    LOADING = "loading"
    LOADED = "loaded"
    ACTIVE = "active"
    ERROR = "error"
    UNLOADING = "unloading"


@dataclass
class PluginMetadata:
    """
    Metadata for a plugin.

    Attributes:
        name: Plugin name
        version: Plugin version
        description: Plugin description
        author: Plugin author
        dependencies: List of plugin dependencies
    """

    name: str
    version: str
    description: str
    author: str
    dependencies: list[str] = field(default_factory=list)


@dataclass
class Plugin:
    """
    Base plugin class.

    Plugins should inherit from this class and implement the required methods.
    """

    metadata: PluginMetadata
    state: PluginState = PluginState.UNLOADED
    runtime: Optional["PluginRuntime"] = None

    async def on_load(self, runtime: "PluginRuntime") -> None:
        """
        Called when plugin is loaded.

        Args:
            runtime: Plugin runtime instance
        """
        self.runtime = runtime
        self.state = PluginState.LOADED
        logger.info("plugin_loaded", plugin=self.metadata.name, version=self.metadata.version)

    async def on_unload(self) -> None:
        """
        Called when plugin is unloaded.
        """
        self.state = PluginState.UNLOADED
        self.runtime = None
        logger.info("plugin_unloaded", plugin=self.metadata.name)

    async def on_message(self, _message: dict[str, Any]) -> dict[str, Any] | None:
        """
        Handle a message from the runtime.

        Args:
            message: Message dictionary

        Returns:
            Optional response message, or None if not handled
        """
        return None

    async def on_agent_spawn(self, agent_id: str) -> None:
        """
        Called when an agent is spawned.

        Args:
            agent_id: Agent identifier
        """

    async def on_agent_terminate(self, agent_id: str) -> None:
        """
        Called when an agent is terminated.

        Args:
            agent_id: Agent identifier
        """


@dataclass
class PluginRuntime:
    """
    Plugin runtime for managing plugins.

    Provides plugin discovery, loading, and execution.
    """

    plugins_dir: Path
    plugins: dict[str, Plugin] = field(default_factory=dict)
    message_handlers: dict[str, list[Callable]] = field(default_factory=dict)
    _running: bool = False

    def __init__(self, plugins_dir: Path | None = None):
        """
        Initialize plugin runtime.

        Args:
            plugins_dir: Directory to search for plugins
        """
        if plugins_dir is None:
            plugins_dir = Path(__file__).parent / "plugins"

        self.plugins_dir = Path(plugins_dir)
        self.plugins = {}
        self.message_handlers = {}
        self._running = False
        logger.info("plugin_runtime_initialized", plugins_dir=str(self.plugins_dir))

    async def discover_plugins(self) -> list[Plugin]:
        """
        Discover plugins in the plugins directory.

        Returns:
            List of discovered plugins
        """
        discovered = []

        if not self.plugins_dir.exists():
            logger.warning("plugins_dir_not_found", dir=str(self.plugins_dir))
            return discovered

        for plugin_path in self.plugins_dir.iterdir():
            if plugin_path.is_file() or plugin_path.name.startswith("_"):
                continue

            # Look for plugin.py file
            plugin_file = plugin_path / "plugin.py"
            if not plugin_file.exists():
                continue

            try:
                # Import plugin module
                spec = importlib.util.spec_from_file_location(plugin_path.name, str(plugin_file))
                module = importlib.util.module_from_spec(spec)

                # Find plugin class
                for _name, obj in inspect.getmembers(module):
                    if inspect.isclass(obj) and issubclass(obj, Plugin) and obj is not Plugin:
                        plugin = obj()
                        plugin.metadata = self._extract_metadata(plugin_path)
                        discovered.append(plugin)
                        logger.info(
                            "plugin_discovered",
                            plugin=plugin.metadata.name,
                            version=plugin.metadata.version,
                        )
                        break

            except Exception as e:
                logger.error("plugin_discovery_failed", plugin=plugin_path.name, error=str(e))

        return discovered

    def _extract_metadata(self, plugin_path: Path) -> PluginMetadata:
        """
        Extract metadata from plugin directory.

        Args:
            plugin_path: Path to plugin directory

        Returns:
            PluginMetadata
        """
        metadata_file = plugin_path / "metadata.json"

        if metadata_file.exists():
            import json

            with open(metadata_file) as f:  # noqa: PTH123
                data = json.load(f)
            return PluginMetadata(**data)

        # Default metadata
        return PluginMetadata(
            name=plugin_path.name, version="0.1.0", description="Plugin", author="Unknown"
        )

    async def load_plugin(self, plugin: Plugin) -> bool:
        """
        Load a plugin.

        Args:
            plugin: Plugin instance

        Returns:
            True if loaded successfully
        """
        if plugin.metadata.name in self.plugins:
            logger.warning("plugin_already_loaded", plugin=plugin.metadata.name)
            return False

        try:
            # Check dependencies
            for dep in plugin.metadata.dependencies:
                if dep not in self.plugins:
                    logger.warning(
                        "plugin_dependency_not_found", plugin=plugin.metadata.name, dependency=dep
                    )
                    return False

            # Load plugin
            await plugin.on_load(self)
            self.plugins[plugin.metadata.name] = plugin
            plugin.state = PluginState.ACTIVE

            # Register message handlers
            if hasattr(plugin, "on_message"):
                self.message_handlers[plugin.metadata.name] = plugin.on_message

            logger.info("plugin_loaded_successfully", plugin=plugin.metadata.name)
            return True

        except Exception as e:
            logger.error("plugin_load_failed", plugin=plugin.metadata.name, error=str(e))
            plugin.state = PluginState.ERROR
            return False

    async def unload_plugin(self, plugin_name: str) -> bool:
        """
        Unload a plugin.

        Args:
            plugin_name: Name of plugin to unload

        Returns:
            True if unloaded successfully
        """
        if plugin_name not in self.plugins:
            logger.warning("plugin_not_loaded", plugin=plugin_name)
            return False

        try:
            plugin = self.plugins[plugin_name]
            await plugin.on_unload()

            # Remove message handlers
            if plugin_name in self.message_handlers:
                del self.message_handlers[plugin_name]

            del self.plugins[plugin_name]
            logger.info("plugin_unloaded_successfully", plugin=plugin_name)
            return True

        except Exception as e:
            logger.error("plugin_unload_failed", plugin=plugin_name, error=str(e))
            return False

    async def load_all(self) -> dict[str, bool]:
        """
        Load all discovered plugins.

        Returns:
            Dictionary of plugin names to load status
        """
        results = {}
        discovered = await self.discover_plugins()

        for plugin in discovered:
            results[plugin.metadata.name] = await self.load_plugin(plugin)

        return results

    async def unload_all(self) -> None:
        """Unload all plugins."""
        plugin_names = list(self.plugins.keys())

        for plugin_name in plugin_names:
            await self.unload_plugin(plugin_name)

    async def execute_plugin(self, plugin_name: str, method: str, **kwargs) -> Any:
        """
        Execute a method on a plugin.

        Args:
            plugin_name: Name of plugin
            method: Method name to execute
            **kwargs: Arguments to pass

        Returns:
            Result from plugin method
        """
        if plugin_name not in self.plugins:
            raise ValueError(f"Plugin not loaded: {plugin_name}")

        plugin = self.plugins[plugin_name]

        if not hasattr(plugin, method):
            raise AttributeError(f"Plugin has no method: {method}")

        method_func = getattr(plugin, method)

        if not asyncio.iscoroutinefunction(method_func):
            return method_func(**kwargs)

        return await method_func(**kwargs)

    async def broadcast_message(self, message: dict[str, Any]) -> list[dict[str, Any]]:
        """
        Broadcast a message to all loaded plugins.

        Args:
            message: Message dictionary

        Returns:
            List of responses from plugins
        """
        responses = []

        for plugin_name, handler in self.message_handlers.items():
            try:
                response = await handler(message)
                if response:
                    responses.append({"plugin": plugin_name, "response": response})
            except Exception as e:
                logger.error("plugin_message_handler_failed", plugin=plugin_name, error=str(e))

        return responses

    def get_plugin(self, plugin_name: str) -> Plugin | None:
        """
        Get a loaded plugin by name.

        Args:
            plugin_name: Plugin name

        Returns:
            Plugin instance or None
        """
        return self.plugins.get(plugin_name)

    def list_plugins(self) -> list[PluginMetadata]:
        """
        List all loaded plugins.

        Returns:
            List of plugin metadata
        """
        return [plugin.metadata for plugin in self.plugins.values()]

    def get_plugin_count(self) -> int:
        """Get number of loaded plugins."""
        return len(self.plugins)


# Global plugin runtime instance
_global_runtime: PluginRuntime | None = None


def get_plugin_runtime() -> PluginRuntime:
    """
    Get the global plugin runtime instance (synchronous).

    Returns:
        PluginRuntime instance
    """
    global _global_runtime

    if _global_runtime is None:
        _global_runtime = PluginRuntime()

    return _global_runtime


# Sync alias for backwards compatibility
# NOTE: This is intentionally a new PluginRuntime instance, not the global one
# The async get_plugin_runtime should be used for the global instance
plugin_manager = PluginRuntime()


async def load_plugin_from_file(plugin_path: Path) -> Plugin | None:
    """
    Load a plugin from a file path.

    Args:
        plugin_path: Path to plugin file

    Returns:
        Plugin instance or None
    """
    await get_plugin_runtime()

    try:
        spec = importlib.util.spec_from_file_location("plugin", str(plugin_path))
        module = importlib.util.module_from_spec(spec)

        for name, obj in inspect.getmembers(module):
            if inspect.isclass(obj) and issubclass(obj, Plugin) and obj is not Plugin:
                plugin = obj()
                plugin.metadata = PluginMetadata(
                    name=name,
                    version="0.1.0",
                    description="Plugin loaded from file",
                    author="Unknown",
                )
                return plugin

    except Exception as e:
        logger.error("plugin_load_from_file_failed", path=str(plugin_path), error=str(e))
        return None
