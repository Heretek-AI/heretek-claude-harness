"""
Core module for AgentActor base class.

This module contains:
- ActorState enum
- ActorMessage dataclass (internal, not the Pydantic model)
- ActorStatus dataclass
- AgentActor core initialization and lifecycle methods

The Pydantic models for inter-actor messaging are in heretek_swarm.schemas.actors.
Import from there for validated message types::

    from heretek_swarm.schemas.actors import ActorMessage as PydanticActorMessage
"""

import asyncio
import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
from typing import Any

from pydantic import ValidationError
from swarms import Agent

import heretek_swarm.actors.stubs as _actor_stubs
from heretek_swarm.actors.validation import (
    validate_message,
)
from heretek_swarm.agents.skills import SkillCategory, SkillMetadata
from heretek_swarm.routing import (
    AgentModelRouter,
    get_router,
)
from heretek_swarm.state.repository import (
    AgentStateRecord,
    StateRepository,
)
from heretek_swarm.swarm_logging.config import get_logger


def _make_skill_metadata(capability: str) -> SkillMetadata:
    """Create skill metadata from a capability string."""
    return SkillMetadata(
        name=capability,
        description=f"Agent capability: {capability}",
        category=SkillCategory.CUSTOM,
        tags=[capability],
        source="runtime",
    )


logger = get_logger("AgentActor")


class ActorState(Enum):
    """Actor lifecycle states."""

    SPAWNING = "spawning"
    ACTIVE = "active"
    SUSPENDED = "suspended"
    TERMINATED = "terminated"
    ERROR = "error"


@dataclass
class ActorMessage:
    """
    Internal message structure for actor mailbox.

    Attributes:
        sender: ID of the sending actor
        message_type: Type identifier for the message
        content: Message payload
        timestamp: ISO8601 timestamp
        correlation_id: Optional correlation ID for request-response patterns
        reply_to: Optional topic for responses
        metadata: Additional metadata
    """

    sender: str
    message_type: str
    content: dict[str, Any]
    timestamp: str
    correlation_id: str | None = None
    reply_to: str | None = None
    recipient: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class ActorStatus:
    """
    Actor status information.

    Attributes:
        agent_id: Unique actor identifier
        state: Current lifecycle state
        message_count: Total messages processed
        created_at: Creation timestamp
        topics: Subscribed topics
        capabilities: Actor capabilities
        mailbox_size: Current mailbox queue size
        last_activity: Last activity timestamp
        error_count: Number of errors encountered
        mesh_type: Event mesh type ('real', 'stub', or 'none')
    """

    agent_id: str
    state: ActorState
    message_count: int
    created_at: str
    topics: list[str]
    capabilities: list[str]
    mailbox_size: int
    last_activity: str | None = None
    error_count: int = 0
    mesh_type: str = "none"


class AgentActor:
    """
    Base class for all actors in the Heretek Swarm system.

    This class implements the actor model pattern with:
    - Message passing via immutable messages
    - State isolation per actor
    - Mailbox-based sequential message processing
    - Integration with Swarms Agent for LLM capabilities

    Example:
        ```python
        class MyCustomAgent(AgentActor):
            async def process_message(self, message: ActorMessage) -> None:
                if message.message_type == "request":
                    response = await self.handle_request(message.content)
                    await self.send(message.reply_to, response)

            async def handle_request(self, content: Dict) -> Dict:
                # Custom logic here
                return {"result": "success"}

        # Usage
        actor = MyCustomAgent(
            agent_id="my-agent-1",
            name="My Custom Agent",
            topics=["requests", "responses"]
        )
        await actor.spawn()
        ```
    """

    # Class-level actor type identifier
    actor_type: str = "AgentActor"

    @classmethod
    def get_actor_type(cls) -> str:
        """
        Get the actor type identifier.

        Returns:
            Actor type string
        """
        return cls.actor_type

    def __init__(
        self,
        agent_id: str | None = None,
        name: str | None = None,
        description: str | None = None,
        topics: list[str] | None = None,
        capabilities: list[str] | None = None,
        swarms_agent: Agent | None = None,
        model_router: AgentModelRouter | None = None,
        max_mailbox_size: int = 1000,
        heartbeat_interval: float = 10.0,
        actor_type: str | None = None,
        state_repository: StateRepository | None = None,
        load_state_on_init: bool = True,
        persistence_interval: int | None = None,  # P0-1: Continuous persistence
        # Injectable dependency stubs (all optional — default to None for backward compat)
        access_analyzer: Any | None = None,
        pattern_extractor: Any | None = None,
        deliberation_engine: Any | None = None,
        tribunal: Any | None = None,
        llm_provider: Any | None = None,
        event_mesh: Any | None = None,
        **kwargs: Any,  # Accept additional kwargs for forward compatibility  # noqa: ARG002
    ) -> None:
        """
        Initialize an actor.

        Args:
            agent_id: Unique identifier for the actor (auto-generated if None)
            name: Human-readable name for the actor
            description: Actor description
            topics: Topics to subscribe to
            capabilities: Actor capabilities list
            swarms_agent: Optional Swarms Agent instance for LLM capabilities
            max_mailbox_size: Maximum mailbox queue size
            heartbeat_interval: Interval between heartbeats in seconds
            actor_type: Optional type identifier for factory registration
            state_repository: Optional state persistence repository
            load_state_on_init: Whether to load state from DB on initialization
            persistence_interval: Optional interval (in messages) for auto-persistence.
                                  If None, only persists on terminate (legacy behavior).
                                  Recommended: 10-100 for production use.
            access_analyzer: Optional AccessPatternAnalyzer stub for testing
                             (injected as ``self.access_analyzer`` for mixin access)
            pattern_extractor: Optional PatternExtractor stub for testing
                               (injected as ``self.pattern_extractor`` for mixin access)
            deliberation_engine: Optional SwarmDeliberationEngine stub for testing
                                 (injected as ``self.deliberation_engine`` for mixin access)
            tribunal: Optional Tribunal stub for testing
                      (injected as ``self.tribunal`` for mixin access)
            llm_provider: Optional LLM provider stub for testing
                          (injected as ``self._llm_provider``, falls back to
                          ``_actor_stubs.get_llm_provider()`` when None)
            event_mesh: Optional event mesh stub for testing
                        (injected as ``self._event_mesh``, falls back to
                        ``_actor_stubs.get_nats_event_mesh()`` when None)
        """
        # P1-7: Configuration validation
        if max_mailbox_size <= 0:
            raise ValueError("max_mailbox_size must be positive")
        if heartbeat_interval <= 0:
            raise ValueError("heartbeat_interval must be positive")

        # P1-10a fix: Use full 128-bit uuid for agent_id instead of truncated 32-bit
        self.agent_id = agent_id or f"actor_{uuid.uuid4().hex}"
        self.name = name or self.__class__.__name__
        self.description = description or f"Actor: {self.name}"
        self.topics = topics or []
        self.capabilities = capabilities or []
        self.swarms_agent = swarms_agent
        self.max_mailbox_size = max_mailbox_size
        self.heartbeat_interval = heartbeat_interval
        self.actor_type = actor_type or self.__class__.__name__

        # State persistence
        self._state_repository: StateRepository | None = state_repository
        self._state_record: AgentStateRecord | None = None
        self._load_state_on_init = load_state_on_init
        self._persistence_interval = persistence_interval  # P0-1: Continuous persistence
        self._messages_since_persist = 0  # P0-1: Track messages for auto-persist

        # Actor state
        self.state: ActorState = ActorState.SPAWNING
        self.mailbox: asyncio.Queue = asyncio.Queue(maxsize=max_mailbox_size)
        self.internal_state: dict[str, Any] = {}
        self.message_count = 0
        self.error_count = 0
        self.created_at = datetime.now(UTC).isoformat()
        self.last_activity: str | None = None

        # Processing tasks
        self._processing_task: asyncio.Task | None = None
        self._heartbeat_task: asyncio.Task | None = None
        self._running = False

        # Model router for multi-provider LLM routing (injectable, or auto-created)
        self._model_router: AgentModelRouter | None = model_router
        if self._model_router is None:
            # Auto-create a router for this agent using the global registry
            self._model_router = get_router(self.agent_id)

        # Injectable dependency stubs (optional kwargs, fall back to existing module stubs)
        self.access_analyzer: Any | None = access_analyzer
        self.pattern_extractor: Any | None = pattern_extractor
        self.deliberation_engine: Any | None = deliberation_engine
        self.tribunal: Any | None = tribunal
        # LLM and event mesh providers (injectable via stubs for testing)
        self._llm_provider: Any | None = llm_provider or _actor_stubs.get_llm_provider()
        self._event_mesh: Any | None = event_mesh or _actor_stubs.get_nats_event_mesh()

        # Message handlers registry
        self._message_handlers: dict[str, Callable] = {}
        self._register_default_handlers()

        # Register agent capabilities with the global skill registry
        self._register_agent_skills()

        logger.info(
            f"[{self.agent_id}] Actor initialized",  # noqa: G004
            extra={
                "agent_name": self.name,
                "topics": self.topics,
                "capabilities": self.capabilities,
            },
        )

    @property
    def is_alive(self) -> bool:
        """Return True if the actor is in ACTIVE state."""
        return self.state == ActorState.ACTIVE

    @property
    def mesh_type(self) -> str:
        """
        Return the mesh type for observability.

        Returns:
            'real' if ``_event_mesh`` is a NATS-based mesh instance,
            'stub' if it is a ``StubEventMesh``, or ``'none'`` if None.
        """
        mesh = self._event_mesh
        if mesh is None:
            return "none"
        # StubEventMesh check using the already-imported stubs module
        if isinstance(mesh, _actor_stubs.StubEventMesh):
            return "stub"
        # NATSEventMesh check via lazy import to avoid circular dependency
        try:
            from heretek_swarm.gateway.nats_event_mesh import NATSEventMesh

            if isinstance(mesh, NATSEventMesh):
                return "real"
        except ImportError:
            logger.debug(
                "NATSEventMesh import unavailable, falling back to class-name mesh type detection"
            )
        # Fallback: check class name for NATS substring (supports mocks)
        mesh_type_name = type(mesh).__name__
        if "NATS" in mesh_type_name:
            return "real"
        if "Stub" in mesh_type_name:
            return "stub"
        # Final fallback: inspect mesh_type attribute string
        mesh_type_attr = getattr(mesh, "mesh_type", "")
        if isinstance(mesh_type_attr, str):
            if "NATS" in mesh_type_attr:
                return "real"
            if "Stub" in mesh_type_attr:
                return "stub"
        return "real"  # assume non-stub, non-None mesh is real

    async def initialize(self) -> None:
        """Initialize the actor. Override in subclass for custom setup."""

    async def cleanup(self) -> None:
        """Cleanup actor resources. Override in subclass for custom teardown."""
        # Drain the mailbox
        while not self.mailbox.empty():
            try:
                self.mailbox.get_nowait()
            except asyncio.QueueEmpty:
                break

        # Clear internal state
        self.internal_state.clear()

        # Clear message handlers (no re-registration of defaults per test contract)
        self._message_handlers.clear()

        logger.info(f"[{self.agent_id}] Actor cleanup complete")

    def _register_default_handlers(self) -> None:
        """Register default message handlers."""
        self.register_handler("health_check", self._handle_health_check)
        self.register_handler("suspend", self._handle_suspend)
        self.register_handler("resume", self._handle_resume)
        self.register_handler("terminate", self._handle_terminate)
        self.register_handler("collective_task", self._handle_collective_task)
        self.register_handler("route_task", self._handle_route_task)

    def _register_agent_skills(self) -> None:
        """
        Register agent capabilities with the global skill registry.

        Non-fatal: skill registration failures are logged but do not
        prevent agent initialization.
        """
        if not self.capabilities:
            return

        try:
            from heretek_swarm.agents.skills import (
                SkillCategory,
                SkillMetadata,
                get_agent_skill_registry,
            )

            registry = get_agent_skill_registry()

            for capability in self.capabilities:
                # Check if skill already registered (from another agent)
                existing = registry.get_skill(capability)
                if existing:
                    # Add this agent to existing skill
                    if self.agent_id not in existing.agent_ids:
                        existing.agent_ids.append(self.agent_id)
                else:
                    # Create new skill metadata from capability
                    registry.register_skill(
                        agent_id=self.agent_id,
                        skill=SkillMetadata(
                            name=capability,
                            description=f"Agent capability: {capability}",
                            category=SkillCategory.CUSTOM,
                            tags=[capability],
                            source="runtime",
                        ),
                    )
        except Exception as e:
            logger.warning(
                f"[{self.agent_id}] Skill registration failed",  # noqa: G004
                error=str(e),
            )

    def _validate_message_content(self, message_type: str, content: dict[str, Any]) -> Any | None:
        """
        Validate message content using Pydantic models.

        Args:
            message_type: Type of message to validate
            content: Message content dict

        Returns:
            Validated model instance or None if validation not available

        Raises:
            ValueError: If validation fails
        """
        try:
            return validate_message(message_type, content)
        except ValidationError as e:
            logger.warning(
                f"[{self.agent_id}] Message validation failed for {message_type}: {e}",  # noqa: G004
                extra={"validation_errors": e.errors()},
            )
            raise ValueError(f"Invalid message format: {e.errors()}") from e
        except KeyError:
            # Unknown message type - skip validation
            logger.debug(f"[{self.agent_id}] No validator for message type: {message_type}")
            return None

    def register_handler(self, message_type: str, handler: Callable) -> None:
        """
        Register a message handler for a specific message type.

        Args:
            message_type: Type of message to handle
            handler: Async handler function
        """
        self._message_handlers[message_type] = handler
        logger.debug(
            f"[{self.agent_id}] Registered handler for {message_type}",  # noqa: G004
        )

    def unregister_handler(self, message_type: str) -> None:
        """
        Unregister a message handler for a specific message type.

        Args:
            message_type: Type of message to unregister
        """
        if message_type in self._message_handlers:
            del self._message_handlers[message_type]
            logger.debug(
                f"[{self.agent_id}] Unregistered handler for {message_type}",  # noqa: G004
            )

    async def spawn(self) -> None:
        """
        Spawn the actor and start processing messages.

        This method:
        1. Sets actor state to ACTIVE
        2. Starts mailbox processing loop
        3. Starts heartbeat loop
        4. Calls initialize() hook for subclass setup
        5. Loads state from database if configured
        """
        # P1-6: Idempotency check - prevent multiple spawns
        if self._running:
            logger.warning(f"[{self.agent_id}] Already running, ignoring spawn request")
            return

        try:
            logger.info(
                f"[{self.agent_id}] Agent spawned: {self.name}",  # noqa: G004
                extra={"state": self.state.value},
            )

            self._running = True
            self.state = ActorState.ACTIVE

            # Load state from database if configured
            if self._load_state_on_init:
                await self.load_state()

            # Start processing tasks
            self._processing_task = asyncio.create_task(self._process_mailbox())
            self._heartbeat_task = asyncio.create_task(self._heartbeat_loop())

            # Call initialization hook
            await self.initialize()

            logger.info(
                f"[{self.agent_id}] Actor spawn complete",  # noqa: G004
                extra={"mailbox_size": self.mailbox.qsize()},
            )
        except Exception:
            logger.exception(f"[{self.agent_id}] Spawn failed: {e}")
            self.state = ActorState.ERROR
            self.error_count += 1
            raise

    async def terminate(self) -> None:
        """
        Terminate the actor and cleanup resources.

        This method:
        1. Sets actor state to TERMINATED
        2. Cancels processing tasks
        3. Calls cleanup() hook for subclass teardown
        4. Saves final state
        """
        try:
            logger.info(f"[{self.agent_id}] Agent terminating...")

            self._running = False
            # P1-10c fix: Set state to TERMINATED AFTER cleanup completes, not before
            # First cancel all tasks
            await self._cancel_tasks()

            # Save final state
            await self.save_state()

            # Call cleanup hook
            await self.cleanup()

            # Now set state to TERMINATED after all cleanup is complete
            self.state = ActorState.TERMINATED

            logger.info(f"[{self.agent_id}] Agent terminated")
        except Exception:
            logger.exception(f"[{self.agent_id}] Terminate failed: {e}")
            self.state = ActorState.ERROR
            raise

    async def _cancel_tasks(self) -> None:
        """Cancel all running tasks with comprehensive exception handling."""
        tasks_to_cancel = []

        if self._processing_task and not self._processing_task.done():
            self._processing_task.cancel()
            tasks_to_cancel.append(self._processing_task)

        if self._heartbeat_task and not self._heartbeat_task.done():
            self._heartbeat_task.cancel()
            tasks_to_cancel.append(self._heartbeat_task)

        if tasks_to_cancel:
            try:
                # P1-10d fix: Catch all exceptions, not just CancelledError
                await asyncio.gather(*tasks_to_cancel, return_exceptions=True)
            except asyncio.CancelledError:
                # Expected during task cancellation
                logger.debug("Task cancellation complete during actor teardown")
            except Exception as e:
                # P1-10d fix: Log any other exceptions during task cancellation
                logger.exception(
                    f"[{self.agent_id}] Error during task cancellation: {e}"  # noqa: G004
                )


# Trigger mixin bindings when this module is imported

# Backward-compat: existing code that imports ActorMessage from actors.base.core
# gets the internal dataclass ActorMessage (defined above), not the Pydantic one.
# Use heretek_swarm.schemas.actors for the Pydantic models.
