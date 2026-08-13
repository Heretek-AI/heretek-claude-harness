"""Lazy import utilities to break circular dependencies.

This module provides utilities for deferred imports that break
circular dependency cycles at module load time.
"""

from __future__ import annotations

import importlib
from functools import wraps
from typing import TYPE_CHECKING, Any, TypeVar

if TYPE_CHECKING:
    from collections.abc import Callable

T = TypeVar("T")


class LazyImport:
    """Lazy import wrapper that defers import until first access.

    Use this to avoid circular imports when module A needs to import
    from module B but module B might import from module A at the top level.

import structlog

logger = structlog.get_logger(__name__)

    Example:
        # Instead of: from foo import Bar
        # Use:
        Bar = LazyImport('foo.Bar')

        # Later, when you need it:
        result = Bar.some_method()  # Import happens here
    """

    def __init__(self, import_path: str, attr: str | None = None):
        """Initialize lazy import.

        Args:
            import_path: Module path (e.g., 'heretek_swarm.llm.providers.factory')
            attr: Optional specific attribute to import (e.g., 'create_llm_provider')
        """
        self._import_path = import_path
        self._attr = attr
        self._module: Any | None = None
        self._resolved_attr: Any | None = None

    def _resolve(self) -> Any:
        """Resolve the import."""
        if self._module is None:
            self._module = importlib.import_module(self._import_path)

        if self._attr is not None:
            if self._resolved_attr is None:
                self._resolved_attr = getattr(self._module, self._attr)
            return self._resolved_attr

        return self._module

    def __getattr__(self, name: str) -> Any:
        """Delegate attribute access to the imported module/attribute."""
        resolved = self._resolve()
        return getattr(resolved, name)

    def __call__(self, *args: Any, **kwargs: Any) -> Any:
        """If the imported attribute is callable, call it."""
        resolved = self._resolve()
        if callable(resolved):
            return resolved(*args, **kwargs)
        raise TypeError(f"LazyImport('{self._import_path}') is not callable")


class LazyModule(dict[str, Any]):
    """A module-like dictionary that lazy-loads attributes.

    This can be used as a drop-in replacement for module imports
    in many contexts.

    Example:
        # Instead of:
        # from heretek_swarm.llm.providers import factory

        # Use:
        factory = LazyModule({
            'create_llm_provider': LazyImport('heretek_swarm.llm.providers.factory', 'create_llm_provider'),  # noqa: E501
            'get_provider_class': LazyImport('heretek_swarm.llm.providers.factory', 'get_provider_class'),  # noqa: E501
        })

        # Then use: factory.create_llm_provider(...)
    """

    def __init__(self, attrs: dict[str, str | LazyImport | Callable] | None = None):
        super().__init__()
        if attrs:
            for key, value in attrs.items():
                if isinstance(value, str):
                    self[key] = LazyImport(value)
                else:
                    self[key] = value


def lazy_import(import_path: str) -> Callable[[Callable[..., T]], Callable[..., T]]:
    """Decorator for lazy importing a function or class.

    The actual import is deferred until the decorated function is called.

    Example:
        @lazy_import('heretek_swarm.llm.providers.factory')
        def create_provider(config):
            return create_provider(config)
    """

    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        # Store the import path in a mutable container to allow modification
        import_ref = {"path": import_path}

        @wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> T:
            module_path, attr_name = import_ref["path"].rsplit(".", 1)
            module = importlib.import_module(module_path)
            attr = getattr(module, attr_name)
            return attr(*args, **kwargs)

        return wrapper

    return decorator


def lazy_import_module(module_path: str) -> Any:
    """Import a module lazily.

    Args:
        module_path: Full module path (e.g., 'heretek_swarm.api.main')

    Returns:
        The imported module (loaded on first access)
    """
    return LazyImport(module_path)


# Registry for commonly used lazy imports to avoid recreating them
_lazy_import_cache: dict[str, LazyImport] = {}


def get_lazy_import(import_path: str, attr: str | None = None) -> LazyImport:
    """Get or create a cached lazy import.

    This is useful for frequently accessed imports that should be cached.

    Args:
        import_path: Module path
        attr: Optional attribute name

    Returns:
        Cached or new LazyImport instance
    """
    cache_key = f"{import_path}:{attr}" if attr else import_path

    if cache_key not in _lazy_import_cache:
        _lazy_import_cache[cache_key] = LazyImport(import_path, attr)

    return _lazy_import_cache[cache_key]


def clear_lazy_import_cache() -> None:
    """Clear the lazy import cache.

    This is mainly useful for testing to ensure clean state.
    """
    _lazy_import_cache.clear()
