"""
Core module for AgentActor base class.

This module contains:
- ActorState enum
- ActorMessage dataclass (internal, not the Pydantic model)
- ActorStatus dataclass
- AgentActor core initialization and lifecycle methods

The Pydantic models for inter-actor messaging are in heretek_swarm_core.schemas.actors.
Import from there for validated message types::

    from heretek_swarm_core.schemas.actors import ActorMessage as PydanticActorMessage
"""

import asyncio
import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
from typing import TYPE_CHECKING, Any, Protocol, runtime_checkable

from pydantic import ValidationError

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


# ---------------------------------------------------------------------------
# Phase 0 freeze: AgentActor interface contract
# ---------------------------------------------------------------------------
# This module defines the canonical ``AgentActor`` class used by all 23
# in-house agents. The interface is the gate for Phase 3 framework
# migrations (AgentScope, langgraph, Temporal, consensus, the official
# ``mcp`` SDK integration). The version constant below is bumped on any
# breaking change to the public surface.
#
# Stability policy:
# - ``AGENT_ACTOR_INTERFACE_VERSION`` is bumped on any breaking change.
# - Adding a new optional parameter to ``__init__`` or a new
#   non-required method/attribute is NOT a breaking change (minor).
# - Removing or renaming a public attribute, method, or constructor
#   parameter IS a breaking change (major).
# - Changing the signature of a method (positional arg rename, return
#   type narrowing) IS a breaking change.
#
# The contract covers the four orthogonal surfaces the swarm depends on:
#   * input  — process_message() + handler registry
#   * output — send() + reply_to correlation
#   * state  — ActorState + internal_state + persistence hooks
#   * trace  — observability.context.TraceContext propagation hooks
#
# See :class:`AgentActorProtocol` below for the runtime-checkable
# Protocol that all 23 agents must satisfy. Subclasses of ``AgentActor``
# satisfy it automatically; independent implementations (e.g. an
# AgentScope node wrapped in a thin adapter) must implement the
# Protocol explicitly.
AGENT_ACTOR_INTERFACE_VERSION: str = "1.0.0"


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

    # Phase 0 freeze: every concrete AgentActor carries the
    # AGENT_ACTOR_INTERFACE_VERSION of the contract it satisfies.
    # External adapters (AgentScope, Temporal, etc.) must set the
    # same value on their wrapper class to be considered compliant.
    AGENT_ACTOR_INTERFACE_VERSION: str = AGENT_ACTOR_INTERFACE_VERSION

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
        pydantic_ai_agent: Any | None = None,
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
        **kwargs: Any,  # Accept additional kwargs for forward compatibility
    ) -> None:
        """
        Initialize an actor.

        Args:
            agent_id: Unique identifier for the actor (auto-generated if None)
            name: Human-readable name for the actor
            description: Actor description
            topics: Topics to subscribe to
            capabilities: Actor capabilities list
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
        self.pydantic_ai_agent = pydantic_ai_agent
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
            f"[{self.agent_id}] Actor initialized",
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
            logger.debug("NATSEventMesh import unavailable, falling back to class-name mesh type detection")
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

    # ------------------------------------------------------------------
    # Trace surface (Phase 0 freeze)
    # ------------------------------------------------------------------
    # Default implementations of the AgentActorProtocol's trace hooks.
    # They delegate to the FROZEN contract in
    # :mod:`heretek_swarm.observability.context`, so the existing 23
    # agents satisfy ``isinstance(actor, AgentActorProtocol)`` without
    # any per-agent retrofit. Subclasses that maintain their own span
    # bookkeeping (e.g. when wrapping an external framework like
    # AgentScope) SHOULD override these to surface the framework-native
    # span as the actor's current context.
    @property
    def trace_context(self) -> "TraceContext | None":
        """Return the actor's current :class:`TraceContext` or ``None``.

        Default: derive from the active OTel context via
        :func:`heretek_swarm.observability.context.get_current_trace_context`.
        Long-lived actors that span many sequential operations will see
        different contexts across their lifetime; this property
        always reports the *current* one.
        """
        from heretek_swarm.observability.context import get_current_trace_context

        return get_current_trace_context()

    def with_trace_context(self, context: "TraceContext"):
        """Bind ``context`` for the duration of a block.

        Default: return a context manager from
        :func:`heretek_swarm.observability.context.use_trace_context`.
        The returned object is awaitable in ``async with`` form. See
        :meth:`AgentActorProtocol.with_trace_context` for the full
        contract.
        """
        from heretek_swarm.observability.context import use_trace_context

        return use_trace_context(context)

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
                f"[{self.agent_id}] Skill registration failed",
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
                f"[{self.agent_id}] Message validation failed for {message_type}: {e}",
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
            f"[{self.agent_id}] Registered handler for {message_type}",
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
                f"[{self.agent_id}] Unregistered handler for {message_type}",
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
                f"[{self.agent_id}] Agent spawned: {self.name}",
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
                f"[{self.agent_id}] Actor spawn complete",
                extra={"mailbox_size": self.mailbox.qsize()},
            )
        except Exception as e:
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
        except Exception as e:
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
                logger.exception(f"[{self.agent_id}] Error during task cancellation: {e}")


# Trigger mixin bindings when this module is imported

# Backward-compat: existing code that imports ActorMessage from actors.base.core
# gets the internal dataclass ActorMessage (defined above), not the Pydantic one.
# Use heretek_swarm_core.schemas.actors for the Pydantic models.


# ---------------------------------------------------------------------------
# Phase 0 freeze: AgentActorProtocol
# ---------------------------------------------------------------------------
# A ``typing.Protocol`` that captures the minimum surface every agent
# implementation must satisfy. The Protocol is ``runtime_checkable`` so
# frameworks (e.g. AgentScope, langgraph, the ``mcp`` SDK) that want to
# duck-type a foreign actor can be validated against it with
# ``isinstance(obj, AgentActorProtocol)``.
#
# The four contract surfaces (input / output / state / trace) correspond
# to the four orthogonal dimensions of agent operation:
#
#   input  — :meth:`process_message` consumes a typed ``ActorMessage``;
#            handler-typed dispatches go through
#            :meth:`register_handler` / :meth:`unregister_handler`.
#   output — :meth:`send` writes to a peer identified by topic or
#            agent_id; correlation is via ``ActorMessage.correlation_id``
#            and ``ActorMessage.reply_to``.
#   state  — :attr:`state` exposes the public lifecycle enum
#            (``ActorState``); :attr:`internal_state` is a free-form
#            ``dict`` for mixin-owned state; persistence hooks
#            (:meth:`load_state`, :meth:`save_state`) integrate with
#            ``StateRepository`` when configured.
#   trace  — :attr:`trace_context` exposes the current
#            :class:`TraceContext` so callers can correlate spans
#            across services; :meth:`with_trace_context` returns an
#            async context manager that binds a context for the
#            duration of a block. This is the slice that the Phase 0
#            ``observability.context`` contract (FROZEN 2026-06-03)
#            gates on.
#
# Adding a new optional method or attribute to this Protocol is a
# minor change. Removing or renaming anything below is a major change
# and requires a ``AGENT_ACTOR_INTERFACE_VERSION`` bump.

if TYPE_CHECKING:
    from heretek_swarm.observability.context import TraceContext


@runtime_checkable
class AgentActorProtocol(Protocol):
    """Runtime-checkable contract every Heretek agent must satisfy.

    See module docstring (the "Phase 0 freeze: AgentActor interface
    contract" block) for the full stability policy. The Protocol is
    a TypeScript-style structural interface: any class that exposes
    the attributes and methods listed below is a valid agent for
    the purposes of Phase 3 framework migration (AgentScope,
    langgraph, Temporal) and Phase 2 telemetry binding
    (``observability.context.TraceContext``).
    """

    # --- Identity (state) --------------------------------------------------
    agent_id: str
    """Unique actor identifier. Stable across the actor's lifetime."""

    name: str
    """Human-readable name. Defaults to ``self.__class__.__name__``."""

    actor_type: str
    """Class-level type identifier used by ``ActorFactory`` registration."""

    state: ActorState
    """Current lifecycle state. Mutations are actor-internal."""

    internal_state: dict[str, Any]
    """Free-form dict for mixin-owned state. Treat as opaque from outside."""

    # --- Required methods (input / output / state / trace) ----------------

    async def process_message(self, message: ActorMessage) -> None:
        """Consume a single mailbox message.

        Subclasses MAY override; the default dispatcher in
        :class:`AgentActor` delegates to the registered handler for
        ``message.message_type``. This returns ``None``; the
        ``send(...)`` side effect is the public return contract.
        """
        ...

    async def send(
        self,
        topic: str,
        content: dict[str, Any],
        message_type: str = "default",
        reply_to: str | None = None,
        correlation_id: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> str:
        """Publish a message to ``topic`` (or peer ``agent_id``).

        Args:
            topic: Target topic name (or peer agent_id).
            content: Message payload (Pydantic-validated downstream).
            message_type: Type identifier for the message.
            reply_to: Optional topic the recipient should respond on.
            correlation_id: Optional id for request/response correlation.
            metadata: Additional metadata. **Trace context**
                propagation is conveyed via this dict: callers SHOULD
                include a ``"trace_context"`` key with a serialized
                :class:`TraceContext` (use :meth:`TraceContext.to_dict`)
                so the receiver can bind the parent's span.

        Returns:
            The generated message id (a UUID4 hex string).
        """
        ...

    def register_handler(self, message_type: str, handler: Callable) -> None:
        """Register an async handler for ``message_type``."""
        ...

    def unregister_handler(self, message_type: str) -> None:
        """Remove a previously-registered handler (no-op if missing)."""
        ...

    async def spawn(self) -> None:
        """Start the actor's mailbox and heartbeat loops.

        Idempotent: a second call on an already-spawned actor MUST be
        a no-op (logged at debug).
        """
        ...

    async def terminate(self) -> None:
        """Stop loops, cancel pending tasks, and persist state.

        Idempotent and exception-safe: callers may invoke it from
        finally blocks without additional guards.
        """
        ...

    async def initialize(self) -> None:
        """Subclass-specific setup hook invoked once at spawn()."""
        ...

    async def cleanup(self) -> None:
        """Subclass-specific teardown hook invoked at terminate()."""
        ...

    # --- Trace surface (the Phase 0 freeze) -------------------------------

    @property
    def trace_context(self) -> "TraceContext | None":
        """Return the actor's current :class:`TraceContext` or ``None``.

        Implementations may derive this from the active OTel context
        or from an attribute they set during ``send`` / message
        handling. The contract is "current", not "root": a long-lived
        actor may have many sequential contexts across its lifetime.
        """
        ...

    def with_trace_context(
        self,
        context: "TraceContext",
    ) -> Any:
        """Return a context manager that binds ``context`` for a block.

        Typical usage::

            async with actor.with_trace_context(ctx):
                await actor.process_message(msg)

        Implementations may return either a synchronous
        ``contextlib.contextmanager``-decorated object or an
        ``asynccontextmanager``-decorated one. The return type is
        ``Any`` so the Protocol accommodates both. Adapters that
        wrap framework-native objects (AgentScope, Temporal) MUST
        preserve the W3C-compliant contract from
        :mod:`heretek_swarm.observability.context`.
        """
        ...


__all__ = [
    "AGENT_ACTOR_INTERFACE_VERSION",
    "ActorMessage",
    "ActorState",
    "ActorStatus",
    "AgentActor",
    "AgentActorProtocol",
]
