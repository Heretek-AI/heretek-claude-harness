"""
Enhanced Agent Registry for Heretek Swarm.

This module provides dynamic agent discovery, metadata extraction, and lifecycle management.
It extends the base registry with programmatic deployment capabilities.

Features:
- Dynamic agent discovery from backend/heretek_swarm/actors/
- Agent metadata extraction (name, description, capabilities)
- Agent lifecycle management (spawn, terminate, suspend, resume)
- Integration with existing wire_agents.py
"""

import importlib
import inspect
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any

import structlog

from heretek_swarm.actors.base import AgentActor

logger = structlog.get_logger("registry_enhanced")


class AgentLifecycleState(Enum):
    """Agent lifecycle states for management."""

    AVAILABLE = "available"
    DEPLOYED = "deployed"
    RUNNING = "running"
    STOPPED = "stopped"
    SUSPENDED = "suspended"
    ERROR = "error"


@dataclass
class AgentTypeMetadata:
    """
    Metadata about an agent type.

    Attributes:
        type_name: Agent type/class name
        module_path: Python module path
        description: Agent description
        capabilities: List of capabilities
        topics: Default topics subscribed
        config_schema: JSON schema for configuration
        actor_type: Actor type identifier
    """

    type_name: str
    module_path: str
    description: str = ""
    capabilities: list[str] = field(default_factory=list)
    topics: list[str] = field(default_factory=list)
    config_schema: dict[str, Any] = field(default_factory=dict)
    actor_type: str = ""


@dataclass
class AgentInstance:
    """
    Runtime instance of an agent.

    Attributes:
        instance_id: Unique instance identifier
        agent_type: Type of agent
        config: Runtime configuration
        state: Current lifecycle state
        actor: Reference to the running actor
        metadata: Agent type metadata
    """

    instance_id: str
    agent_type: str
    config: dict[str, Any]
    state: AgentLifecycleState
    actor: AgentActor | None = None
    metadata: AgentTypeMetadata | None = None


class EnhancedAgentRegistry:
    """
    Enhanced agent registry with lifecycle management.

    Provides:
    - Dynamic discovery of agent types from actors directory
    - Metadata extraction for each agent type
    - Lifecycle management (deploy, start, stop, suspend, resume)
    - Configuration management
    """

    def __init__(self, actors_dir: Path | None = None):
        """
        Initialize the enhanced registry.

        Args:
            actors_dir: Directory containing agent actor files.
                       Defaults to backend/heretek_swarm/actors/
        """
        if actors_dir is None:
            actors_dir = Path(__file__).parent.parent / "actors"

        self.actors_dir = Path(actors_dir)
        self._agent_types: dict[str, AgentTypeMetadata] = {}
        self._instances: dict[str, AgentInstance] = {}
        self._loaded = False
        self._supervisor = None

        logger.info("EnhancedAgentRegistry initialized with actors_dir: {self.actors_dir}")

    def _get_supervisor(self) -> Any | None:
        """Get the supervisor instance for actor management."""
        if self._supervisor is None:
            try:
                from heretek_swarm.actors.supervisor import get_supervisor

                self._supervisor = get_supervisor()
            except (ImportError, Exception):
                logger.warning("Could not get supervisor: {e}")
        return self._supervisor

    def discover_agents(self) -> dict[str, AgentTypeMetadata]:
        """
        Discover all available agent types from the actors directory.

        Returns:
            Dictionary mapping agent type names to their metadata
        """
        if not self.actors_dir.exists():
            logger.warning("Actors directory does not exist: {self.actors_dir}")
            return {}

        discovered = {}

        # Scan for Python files in actors directory
        for actor_file in self.actors_dir.glob("*.py"):
            if actor_file.name.startswith("_"):
                continue  # Skip __init__.py and private files

            try:
                module_name = f"heretek_swarm.actors.{actor_file.stem}"
                metadata = self._extract_agent_metadata(module_name, actor_file.stem)
                if metadata:
                    discovered[metadata.type_name] = metadata
                    logger.debug("Discovered agent type: {metadata.type_name}")
            except Exception:
                logger.warning("Failed to discover agent from {actor_file.name}: {e}")

        self._agent_types = discovered
        self._loaded = True
        logger.info("Discovered {len(discovered)} agent types")
        return discovered

    def _extract_agent_metadata(
        self, module_name: str, actor_name: str
    ) -> AgentTypeMetadata | None:
        """
        Extract metadata from an agent module.

        Args:
            module_name: Python module path
            actor_name: Name of the actor/class

        Returns:
            AgentTypeMetadata if found, None otherwise
        """
        try:
            # Import the module
            module = importlib.import_module(module_name)

            # Look for agent class in module
            agent_class = None
            class_name = "".join(part.capitalize() for part in actor_name.split("_"))

            if hasattr(module, class_name):
                agent_class = getattr(module, class_name)
            elif hasattr(module, f"{class_name}Agent"):
                # Try with "Agent" suffix (e.g., BetaAgent for beta.py)
                agent_class = getattr(module, f"{class_name}Agent")
            else:
                # Try to find a class whose name starts with the expected prefix
                for _name, obj in inspect.getmembers(module, inspect.isclass):
                    if (
                        issubclass(obj, AgentActor)
                        and obj != AgentActor
                        and obj.__name__.startswith(class_name)
                    ):
                        agent_class = obj
                        break

                # Last resort: find any AgentActor subclass
                if not agent_class:
                    for _name, obj in inspect.getmembers(module, inspect.isclass):
                        if issubclass(obj, AgentActor) and obj != AgentActor:
                            agent_class = obj
                            break

            if not agent_class:
                return None

            # Use the actual class name, not the PascalCase filename conversion
            class_name = agent_class.__name__

            # Extract metadata
            actor_type = getattr(agent_class, "actor_type", class_name)

            # Get docstring as description
            description = (agent_class.__doc__ or "").strip().split("\n")[0] or ""

            # Default topics and capabilities
            topics = []
            capabilities = []

            # Try to get from class attributes
            if hasattr(agent_class, "default_topics"):
                topics = getattr(agent_class, "default_topics", [])
            if hasattr(agent_class, "capabilities"):
                capabilities = getattr(agent_class, "capabilities", [])

            # Generate config schema
            config_schema = self._generate_config_schema(agent_class)

            return AgentTypeMetadata(
                type_name=class_name,
                module_path=module_name,
                description=description,
                capabilities=capabilities,
                topics=topics,
                config_schema=config_schema,
                actor_type=actor_type,
            )

        except Exception:
            logger.warning("Failed to extract metadata from {module_name}: {e}")
            return None

    def _generate_config_schema(self, _agent_class: type[AgentActor]) -> dict[str, Any]:
        """
        Generate a JSON schema for agent configuration.

        Args:
            agent_class: Agent class to generate schema for

        Returns:
            JSON schema dictionary
        """
        return {
            "type": "object",
            "properties": {
                "name": {"type": "string", "description": "Human-readable name for the agent"},
                "description": {"type": "string", "description": "Agent description"},
                "topics": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Topics to subscribe to",
                },
                "capabilities": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Agent capabilities",
                },
                "max_mailbox_size": {
                    "type": "integer",
                    "default": 1000,
                    "description": "Maximum mailbox queue size",
                },
                "heartbeat_interval": {
                    "type": "number",
                    "default": 10.0,
                    "description": "Heartbeat interval in seconds",
                },
                "persistence_interval": {
                    "type": "integer",
                    "nullable": True,
                    "description": "Messages between auto-persistence",
                },
            },
            "additionalProperties": True,
        }

    def get_available_agents(self) -> list[AgentTypeMetadata]:
        """
        Get all available agent types.

        Returns:
            List of available agent type metadata
        """
        if not self._loaded:
            self.discover_agents()
        return list(self._agent_types.values())

    def get_agent_metadata(self, agent_type: str) -> AgentTypeMetadata | None:
        """
        Get metadata for a specific agent type.

        Args:
            agent_type: Agent type name

        Returns:
            AgentTypeMetadata if found, None otherwise
        """
        if not self._loaded:
            self.discover_agents()
        return self._agent_types.get(agent_type)

    async def deploy_agent(
        self,
        agent_type: str,
        config: dict[str, Any] | None = None,
        instance_id: str | None = None,
    ) -> AgentInstance | None:
        """
        Deploy a new agent instance.

        Args:
            agent_type: Type of agent to deploy
            config: Optional configuration dictionary
            instance_id: Optional custom instance ID

        Returns:
            AgentInstance if deployed successfully, None otherwise
        """
        import uuid

        if not self._loaded:
            self.discover_agents()

        metadata = self._agent_types.get(agent_type)
        if not metadata:
            logger.error("Unknown agent type: {agent_type}")
            return None

        # Generate instance ID
        if instance_id is None:
            instance_id = f"{agent_type.lower()}_{uuid.uuid4().hex[:8]}"

        # Merge with default config
        default_config = {
            "agent_id": instance_id,
            "name": config.get("name") if config else None,
            "description": config.get("description") if config else None,
            "topics": config.get("topics") if config else None,
            "capabilities": config.get("capabilities") if config else None,
            "max_mailbox_size": config.get("max_mailbox_size", 1000) if config else 1000,
            "heartbeat_interval": config.get("heartbeat_interval", 10.0) if config else 10.0,
            "persistence_interval": config.get("persistence_interval") if config else None,
        }

        # Create instance record
        instance = AgentInstance(
            instance_id=instance_id,
            agent_type=agent_type,
            config=default_config,
            state=AgentLifecycleState.DEPLOYED,
            metadata=metadata,
        )

        self._instances[instance_id] = instance
        logger.info("Deployed agent instance: {instance_id} of type {agent_type}")

        return instance

    async def start_agent(self, instance_id: str) -> bool:
        """
        Start a deployed agent instance.

        Args:
            instance_id: Instance ID to start

        Returns:
            True if started successfully, False otherwise
        """
        instance = self._instances.get(instance_id)
        if not instance:
            logger.error("Instance not found: {instance_id}")
            return False

        if instance.state not in [
            AgentLifecycleState.DEPLOYED,
            AgentLifecycleState.STOPPED,
            AgentLifecycleState.SUSPENDED,
        ]:
            logger.warning("Cannot start agent in state: {instance.state.value}")
            return False

        try:
            # Get supervisor
            supervisor = self._get_supervisor()
            if not supervisor:
                logger.error("Supervisor not available")
                return False

            # Import and instantiate the agent class
            metadata = instance.metadata
            if not metadata:
                logger.error("No metadata for instance: {instance_id}")
                return False

            module = importlib.import_module(metadata.module_path)
            class_name = metadata.type_name
            agent_class = getattr(module, class_name)

            # Filter config to only include params the agent class accepts
            # This avoids "got multiple values for keyword argument" errors
            # when agents hardcode topics/capabilities in their constructors
            import inspect

            sig = inspect.signature(agent_class.__init__)
            valid_params = set(sig.parameters.keys()) - {"self", "kwargs"}
            has_kwargs = "kwargs" in sig.parameters

            if has_kwargs:
                filtered_config = instance.config
            else:
                filtered_config = {
                    k: v for k, v in instance.config.items() if k in valid_params
                }

            # Always pass agent_id at minimum
            filtered_config.setdefault("agent_id", instance.instance_id)

            # Create agent instance
            agent = agent_class(**filtered_config)

            # Spawn via supervisor
            await supervisor.spawn_actor(agent)

            instance.actor = agent
            instance.state = AgentLifecycleState.RUNNING

            logger.info("Started agent instance: {instance_id}")
            return True

        except Exception:
            logger.exception("Failed to start agent {instance_id}: {e}")
            instance.state = AgentLifecycleState.ERROR
            return False

    async def stop_agent(self, instance_id: str) -> bool:
        """
        Stop a running agent instance.

        Args:
            instance_id: Instance ID to stop

        Returns:
            True if stopped successfully, False otherwise
        """
        instance = self._instances.get(instance_id)
        if not instance:
            logger.error("Instance not found: {instance_id}")
            return False

        if instance.state != AgentLifecycleState.RUNNING:
            logger.warning("Cannot stop agent in state: {instance.state.value}")
            return False

        try:
            if instance.actor:
                await instance.actor.terminate()

            instance.actor = None
            instance.state = AgentLifecycleState.STOPPED

            logger.info("Stopped agent instance: {instance_id}")
            return True

        except Exception:
            logger.exception("Failed to stop agent {instance_id}: {e}")
            return False

    async def suspend_agent(self, instance_id: str) -> bool:
        """
        Suspend a running agent instance.

        Args:
            instance_id: Instance ID to suspend

        Returns:
            True if suspended successfully, False otherwise
        """
        instance = self._instances.get(instance_id)
        if not instance:
            logger.error("Instance not found: {instance_id}")
            return False

        if instance.state != AgentLifecycleState.RUNNING:
            logger.warning("Cannot suspend agent in state: {instance.state.value}")
            return False

        try:
            if instance.actor:
                await instance.actor.suspend()

            instance.state = AgentLifecycleState.SUSPENDED

            logger.info("Suspended agent instance: {instance_id}")
            return True

        except Exception:
            logger.exception("Failed to suspend agent {instance_id}: {e}")
            return False

    async def resume_agent(self, instance_id: str) -> bool:
        """
        Resume a suspended agent instance.

        Args:
            instance_id: Instance ID to resume

        Returns:
            True if resumed successfully, False otherwise
        """
        instance = self._instances.get(instance_id)
        if not instance:
            logger.error("Instance not found: {instance_id}")
            return False

        if instance.state != AgentLifecycleState.SUSPENDED:
            logger.warning("Cannot resume agent in state: {instance.state.value}")
            return False

        try:
            if instance.actor:
                await instance.actor.resume()

            instance.state = AgentLifecycleState.RUNNING

            logger.info("Resumed agent instance: {instance_id}")
            return True

        except Exception:
            logger.exception("Failed to resume agent {instance_id}: {e}")
            return False

    async def remove_agent(self, instance_id: str) -> bool:
        """
        Remove an agent instance.

        Args:
            instance_id: Instance ID to remove

        Returns:
            True if removed successfully, False otherwise
        """
        instance = self._instances.get(instance_id)
        if not instance:
            logger.error("Instance not found: {instance_id}")
            return False

        # Stop if running
        if instance.state == AgentLifecycleState.RUNNING:
            await self.stop_agent(instance_id)

        # Remove from instances
        del self._instances[instance_id]

        logger.info("Removed agent instance: {instance_id}")
        return True

    def get_instance(self, instance_id: str) -> AgentInstance | None:
        """
        Get an agent instance by ID.

        Args:
            instance_id: Instance ID

        Returns:
            AgentInstance if found, None otherwise
        """
        return self._instances.get(instance_id)

    def get_all_instances(self) -> dict[str, AgentInstance]:
        """
        Get all agent instances.

        Returns:
            Dictionary mapping instance IDs to instances
        """
        return self._instances.copy()

    def get_instances_by_type(self, agent_type: str) -> list[AgentInstance]:
        """
        Get all instances of a specific agent type.

        Args:
            agent_type: Agent type name

        Returns:
            List of matching instances
        """
        return [inst for inst in self._instances.values() if inst.agent_type == agent_type]

    def update_agent_config(self, instance_id: str, config: dict[str, Any]) -> bool:
        """
        Update an agent's configuration.

        Args:
            instance_id: Instance ID
            config: New configuration dictionary

        Returns:
            True if updated successfully, False otherwise
        """
        instance = self._instances.get(instance_id)
        if not instance:
            logger.error("Instance not found: {instance_id}")
            return False

        # Merge config
        instance.config.update(config)

        logger.info("Updated config for agent instance: {instance_id}")
        return True

    def get_registry_stats(self) -> dict[str, Any]:
        """
        Get statistics about the registry.

        Returns:
            Dictionary with registry statistics
        """
        if not self._loaded:
            self.discover_agents()

        instances_by_state = {}
        for inst in self._instances.values():
            state = inst.state.value
            instances_by_state[state] = instances_by_state.get(state, 0) + 1

        return {
            "total_agent_types": len(self._agent_types),
            "total_instances": len(self._instances),
            "instances_by_state": instances_by_state,
            "agent_types": list(self._agent_types.keys()),
        }


# Singleton instance
_enhanced_registry: EnhancedAgentRegistry | None = None


def get_enhanced_registry(actors_dir: Path | None = None) -> EnhancedAgentRegistry:
    """
    Get the global enhanced registry instance.

    Args:
        actors_dir: Optional actors directory (only used on first call)

    Returns:
        The global EnhancedAgentRegistry instance
    """
    global _enhanced_registry
    if _enhanced_registry is None:
        _enhanced_registry = EnhancedAgentRegistry(actors_dir)
    return _enhanced_registry
