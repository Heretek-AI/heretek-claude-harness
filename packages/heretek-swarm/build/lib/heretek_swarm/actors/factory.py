"""
ActorFactory - Factory pattern for creating and managing actor instances.

This module provides:
- Registration of actor classes with initialization parameters
- Actor instantiation from stored configurations
- Retrieval of actor configuration information
"""

from dataclasses import dataclass, field
from typing import Any

import structlog

from heretek_swarm.actors.base import AgentActor

logger = structlog.get_logger("ActorFactory")


@dataclass
class ActorConfig:
    """
    Configuration for an actor instance.

    Attributes:
        actor_type: Type identifier for the actor class
        class_ref: Reference to the actor class
        init_kwargs: Keyword arguments for actor initialization
        capabilities: List of actor capabilities
        actor_id: Unique identifier for the actor instance
    """

    actor_type: str
    class_ref: type[AgentActor]
    init_kwargs: dict[str, Any]
    capabilities: list[str] = field(default_factory=list)
    actor_id: str | None = None


class ActorFactory:
    """
    Factory for creating and managing actor instances.

    The ActorFactory provides a registry pattern for storing actor class
    information and instantiation parameters, enabling actor recreation
    after failure.

    Example:
        ```python
        factory = ActorFactory()

        # Register an actor class
        factory.register_actor_class(
            "my-actor",
            MyCustomActor,
            {"name": "My Actor", "topics": ["topic1"]}
        )

        # Create actor instance
        actor = factory.create_actor("my-actor", actor_id="instance-1")

        # Get configuration info
        config = factory.get_actor_info("instance-1")
        ```
    """

    def __init__(self) -> None:
        """Initialize the actor factory."""
        self._registry: dict[str, type[AgentActor]] = {}
        self._default_kwargs: dict[str, dict[str, Any]] = {}
        self._instances: dict[str, ActorConfig] = {}

        logger.info("[ActorFactory] Factory initialized")

    def register_actor_class(
        self,
        name: str,
        cls: type[AgentActor],
        kwargs: dict[str, Any] | None = None,
    ) -> None:
        """
        Register an actor class with optional default parameters.

        Args:
            name: Unique identifier for this actor type
            cls: Actor class to register
            kwargs: Default initialization parameters

        Raises:
            ValueError: If name is already registered
        """
        if name in self._registry:
            raise ValueError(f"Actor type '{name}' is already registered")

        self._registry[name] = cls
        self._default_kwargs[name] = kwargs or {}

        logger.info(
            f"[ActorFactory] Registered actor class '{name}'",  # noqa: G004
            extra={"class_name": cls.__name__},
        )

    def create_actor(
        self,
        actor_type: str,
        actor_id: str | None = None,  # noqa: ARG002
        **override_kwargs: Any,
    ) -> AgentActor:
        """
        Create an actor instance from registered configuration.

        Args:
            actor_type: Registered actor type identifier
            actor_id: Optional actor ID (overrides stored value)
            **override_kwargs: Override default initialization parameters

        Returns:
            New actor instance

        Raises:
            ValueError: If actor_type is not registered
        """
        if actor_type not in self._registry:
            raise ValueError(f"Actor type '{actor_type}' is not registered")

        cls = self._registry[actor_type]
        base_kwargs = self._default_kwargs.get(actor_type, {})

        # Merge base kwargs with overrides
        init_kwargs = {**base_kwargs, **override_kwargs}

        # Create actor instance
        actor = cls(**init_kwargs)

        # Store configuration for future recreation
        config = ActorConfig(
            actor_type=actor_type,
            class_ref=cls,
            init_kwargs=init_kwargs,
            capabilities=actor.capabilities.copy(),
            actor_id=actor.agent_id,
        )
        self._instances[actor.agent_id] = config

        logger.info(
            f"[ActorFactory] Created actor instance '{actor.agent_id}'",  # noqa: G004
            extra={"actor_type": actor_type},
        )

        return actor

    def get_actor_info(self, actor_id: str) -> ActorConfig | None:
        """
        Retrieve stored configuration for an actor instance.

        Args:
            actor_id: Actor instance identifier

        Returns:
            ActorConfig if found, None otherwise
        """
        return self._instances.get(actor_id)

    def get_registered_types(self) -> list[str]:
        """
        Get list of registered actor types.

        Returns:
            List of registered actor type names
        """
        return list(self._registry.keys())

    def get_instance_configs(self) -> dict[str, ActorConfig]:
        """
        Get all stored actor instance configurations.

        Returns:
            Dictionary of actor_id to ActorConfig mappings
        """
        return self._instances.copy()

    def unregister_actor_class(self, name: str) -> None:
        """
        Unregister an actor class.

        Args:
            name: Actor type name to unregister

        Raises:
            ValueError: If name is not registered
        """
        if name not in self._registry:
            raise ValueError(f"Actor type '{name}' is not registered")

        del self._registry[name]
        if name in self._default_kwargs:
            del self._default_kwargs[name]

        logger.info("[ActorFactory] Unregistered actor class '{name}'")

    def clear_instances(self) -> None:
        """Clear all stored actor instance configurations."""
        self._instances.clear()
        logger.info("[ActorFactory] Cleared all instance configurations")


# Global factory instance
_global_factory: ActorFactory | None = None


def get_factory() -> ActorFactory:
    """
    Get global actor factory instance.

    Returns:
        ActorFactory instance
    """
    global _global_factory

    if _global_factory is None:
        _global_factory = ActorFactory()

    return _global_factory
