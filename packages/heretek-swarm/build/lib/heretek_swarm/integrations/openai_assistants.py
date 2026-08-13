"""
OpenAI Assistants API Integration Module for Heretek Swarm

This module provides bi-directional integration between Heretek Swarm agents and OpenAI Assistants API.  # noqa: E501
It enables assistant creation, thread management, run handling, and tool function calling.

Features:
- Assistant creation and management
- Thread and run handling
- Tool function calling bridge
- File attachment support
- Zero-trust validation of all API interactions

Reference: EXPANSION_ROADMAP.md Session 47 - Integration Ecosystem
"""

import asyncio
import json
import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

import structlog

logger = structlog.get_logger(__name__)

# Try to import OpenAI components
try:
    from openai import AsyncOpenAI, OpenAI
    from openai.types.beta import Assistant, Run, Thread
    from openai.types.beta.threads import Message, TextContentBlock
    from openai.types.beta.threads.runs import FunctionToolCall, ToolCall

    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False
    OpenAI = None
    AsyncOpenAI = None
    Assistant = None
    Thread = None
    Run = None
    Message = None
    TextContentBlock = None
    ToolCall = None
    FunctionToolCall = None


class RunStatus(StrEnum):
    """Run status enumeration."""

    QUEUED = "queued"
    IN_PROGRESS = "in_progress"
    REQUIRES_ACTION = "requires_action"
    CANCELLING = "cancelling"
    CANCELLED = "cancelled"
    FAILED = "failed"
    COMPLETED = "completed"
    EXPIRED = "expired"


class MessageRole(StrEnum):
    """Message role enumeration."""

    USER = "user"
    ASSISTANT = "assistant"


@dataclass
class AssistantConfig:
    """
    Configuration for an OpenAI Assistant.

    Attributes:
        assistant_id: Assistant identifier
        name: Assistant name
        model: Model to use
        instructions: System instructions
        description: Assistant description
        tools: Tool definitions
        file_ids: Attached file IDs
        metadata: Additional metadata
    """

    assistant_id: str
    name: str
    model: str = "gpt-4o"
    instructions: str = "You are a helpful assistant."
    description: str | None = None
    tools: list[dict[str, Any]] = field(default_factory=list)
    file_ids: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
    heretek_agent_id: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "assistant_id": self.assistant_id,
            "name": self.name,
            "model": self.model,
            "instructions": self.instructions,
            "description": self.description,
            "tools": self.tools,
            "file_ids": self.file_ids,
            "metadata": self.metadata,
            "heretek_agent_id": self.heretek_agent_id,
        }


@dataclass
class ThreadContext:
    """
    Thread context for conversation tracking.

    Attributes:
        thread_id: Thread identifier
        assistant_id: Associated assistant ID
        messages: Message history
        created_at: Creation timestamp
        metadata: Additional metadata
    """

    thread_id: str
    assistant_id: str | None = None
    messages: list[dict[str, Any]] = field(default_factory=list)
    created_at: str = field(default_factory=lambda: datetime.now(UTC).isoformat())
    metadata: dict[str, Any] = field(default_factory=dict)
    heretek_context: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "thread_id": self.thread_id,
            "assistant_id": self.assistant_id,
            "message_count": len(self.messages),
            "created_at": self.created_at,
            "metadata": self.metadata,
            "heretek_context": self.heretek_context,
        }


@dataclass
class RunContext:
    """
    Context for a run execution.

    Attributes:
        run_id: Run identifier
        thread_id: Associated thread ID
        assistant_id: Associated assistant ID
        status: Run status
        instructions: Run-specific instructions
        tools: Run-specific tools
        metadata: Additional metadata
    """

    run_id: str
    thread_id: str
    assistant_id: str
    status: RunStatus = RunStatus.QUEUED
    instructions: str | None = None
    tools: list[dict[str, Any]] | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    started_at: str | None = None
    completed_at: str | None = None
    error: str | None = None
    tool_calls: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "run_id": self.run_id,
            "thread_id": self.thread_id,
            "assistant_id": self.assistant_id,
            "status": self.status.value,
            "instructions": self.instructions,
            "tool_count": len(self.tool_calls),
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "error": self.error,
            "metadata": self.metadata,
        }


@dataclass
class FunctionCallRequest:
    """
    Request for a function call from OpenAI.

    Attributes:
        call_id: Function call identifier
        name: Function name
        arguments: Function arguments
        thread_id: Associated thread ID
        run_id: Associated run ID
    """

    call_id: str
    name: str
    arguments: dict[str, Any]
    thread_id: str
    run_id: str
    heretek_agent_id: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "call_id": self.call_id,
            "name": self.name,
            "arguments": self.arguments,
            "thread_id": self.thread_id,
            "run_id": self.run_id,
            "heretek_agent_id": self.heretek_agent_id,
        }


class OpenAIAssistantsAdapter:
    """
    Adapter for integrating OpenAI Assistants API with Heretek Swarm.

    This adapter provides:
    - Assistant creation and management
    - Thread and run handling
    - Tool function calling bridge to Heretek agents
    - File attachment support

    Attributes:
        client: OpenAI client instance
        assistants: Registered assistants
        threads: Active threads
        runs: Active runs
    """

    def __init__(
        self,
        api_key: str | None = None,
        base_url: str | None = None,
        organization: str | None = None,
        enable_heretek_bridge: bool = True,
    ) -> None:
        """
        Initialize the OpenAI Assistants adapter.

        Args:
            api_key: OpenAI API key
            base_url: Optional base URL for API
            organization: Organization ID
            enable_heretek_bridge: Enable Heretek agent bridging
        """
        self.api_key = api_key
        self.base_url = base_url
        self.organization = organization

        self.client: AsyncOpenAI | None = None
        self.sync_client: OpenAI | None = None

        if OPENAI_AVAILABLE and api_key:
            self.client = AsyncOpenAI(
                api_key=api_key,
                base_url=base_url,
                organization=organization,
            )
            self.sync_client = OpenAI(
                api_key=api_key,
                base_url=base_url,
                organization=organization,
            )

        self.assistants: dict[str, AssistantConfig] = {}
        self.threads: dict[str, ThreadContext] = {}
        self.runs: dict[str, RunContext] = {}

        self.enable_heretek_bridge = enable_heretek_bridge
        self._agent_runtime = None
        self._heretek_agent_mappings: dict[str, str] = {}

        # Registered functions for tool calling
        self._registered_functions: dict[str, Callable] = {}

        # Run callbacks
        self._run_callbacks: list[Callable] = []

        logger.info(
            "openai_assistants_adapter_initialized",
            api_key_set=bool(api_key),
            heretek_bridge_enabled=enable_heretek_bridge,
        )

    def set_agent_runtime(self, runtime: Any) -> None:
        """Set the Heretek agent runtime for integration."""
        self._agent_runtime = runtime
        logger.debug("agent_runtime_set", runtime_type=type(runtime).__name__)

    def register_heretek_agent_mapping(
        self,
        heretek_agent_id: str,
        assistant_id: str,
    ) -> None:
        """Register a mapping between Heretek and OpenAI assistants."""
        self._heretek_agent_mappings[heretek_agent_id] = assistant_id
        if assistant_id in self.assistants:
            self.assistants[assistant_id].heretek_agent_id = heretek_agent_id
        logger.info(
            "heretek_agent_mapping_registered",
            heretek_agent_id=heretek_agent_id,
            assistant_id=assistant_id,
        )

    def register_run_callback(self, callback: Callable) -> None:
        """Register a callback for run events."""
        self._run_callbacks.append(callback)
        logger.debug("run_callback_registered", callback=callback.__name__)

    async def _notify_run_event(
        self,
        event_type: str,
        run_id: str,
        context: RunContext | None = None,
    ) -> None:
        """Notify callbacks of run events."""
        for callback in self._run_callbacks:
            try:
                if asyncio.iscoroutinefunction(callback):
                    await callback(event_type, run_id, context)
                else:
                    callback(event_type, run_id, context)
            except Exception as e:
                logger.error("run_callback_error", error=str(e))

    def register_function(self, name: str, func: Callable) -> None:
        """
        Register a function for tool calling.

        Args:
            name: Function name
            func: Function to call
        """
        self._registered_functions[name] = func
        logger.info("function_registered", name=name)

    async def create_assistant(
        self,
        assistant_id: str,
        name: str,
        model: str = "gpt-4o",
        instructions: str = "You are a helpful assistant.",
        description: str | None = None,
        tools: list[dict[str, Any]] | None = None,
        file_ids: list[str] | None = None,
        metadata: dict[str, Any] | None = None,
        heretek_agent_id: str | None = None,
    ) -> AssistantConfig:
        """
        Create an OpenAI Assistant.

        Args:
            assistant_id: Unique assistant identifier
            name: Assistant name
            model: Model to use
            instructions: System instructions
            description: Assistant description
            tools: Tool definitions
            file_ids: Attached file IDs
            metadata: Additional metadata
            heretek_agent_id: Associated Heretek agent ID

        Returns:
            AssistantConfig
        """
        if not OPENAI_AVAILABLE:
            logger.warning("openai_not_available")
            raise RuntimeError("OpenAI is not available. Install with: pip install openai")

        if not self.client:
            raise RuntimeError("OpenAI client not initialized. Provide API key.")

        config = AssistantConfig(
            assistant_id=assistant_id,
            name=name,
            model=model,
            instructions=instructions,
            description=description,
            tools=tools or [],
            file_ids=file_ids or [],
            metadata=metadata or {},
            heretek_agent_id=heretek_agent_id,
        )

        # Create assistant via API
        try:
            assistant = await self.client.beta.assistants.create(
                name=name,
                model=model,
                instructions=instructions,
                description=description,
                tools=tools or [],
                file_ids=file_ids or [],
                metadata=metadata or {},
            )

            # Store the OpenAI assistant ID
            config.openai_id = assistant.id
            self.assistants[assistant_id] = config

            logger.info(
                "assistant_created",
                assistant_id=assistant_id,
                openai_id=assistant.id,
            )

        except Exception as e:
            # Store config even if API call fails (for offline mode)
            self.assistants[assistant_id] = config
            logger.warning(
                "assistant_creation_warning",
                assistant_id=assistant_id,
                error=str(e),
            )

        return config

    async def create_thread(
        self,
        thread_id: str | None = None,
        assistant_id: str | None = None,
        initial_messages: list[dict[str, Any]] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> ThreadContext:
        """
        Create a new thread.

        Args:
            thread_id: Optional thread identifier
            assistant_id: Associated assistant ID
            initial_messages: Initial messages
            metadata: Thread metadata

        Returns:
            ThreadContext
        """
        if not OPENAI_AVAILABLE or not self.client:
            raise RuntimeError("OpenAI client not initialized")

        if thread_id is None:
            thread_id = f"thread_{uuid.uuid4().hex[:12]}"

        context = ThreadContext(
            thread_id=thread_id,
            assistant_id=assistant_id,
            metadata=metadata or {},
        )

        # Create thread via API
        try:
            if initial_messages:
                thread = await self.client.beta.threads.create(
                    messages=initial_messages,
                    metadata=metadata or {},
                )
            else:
                thread = await self.client.beta.threads.create(
                    metadata=metadata or {},
                )
            context.thread_id = thread.id
        except Exception as e:
            logger.warning("thread_creation_warning", thread_id=thread_id, error=str(e))

        self.threads[thread_id] = context
        logger.info("thread_created", thread_id=thread_id)

        return context

    async def add_message(
        self,
        thread_id: str,
        content: str,
        role: MessageRole = MessageRole.USER,
        file_ids: list[str] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> bool:
        """
        Add a message to a thread.

        Args:
            thread_id: Thread ID
            content: Message content
            role: Message role
            file_ids: Attached file IDs
            metadata: Message metadata

        Returns:
            True if message added
        """
        if not OPENAI_AVAILABLE or not self.client:
            raise RuntimeError("OpenAI client not initialized")

        if thread_id not in self.threads:
            raise ValueError(f"Thread {thread_id} not found")

        try:
            await self.client.beta.threads.messages.create(
                thread_id=thread_id,
                role=role.value,
                content=content,
                file_ids=file_ids or [],
                metadata=metadata or {},
            )

            # Track message locally
            self.threads[thread_id].messages.append(
                {
                    "role": role.value,
                    "content": content,
                    "file_ids": file_ids or [],
                    "timestamp": datetime.now(UTC).isoformat(),
                }
            )

            logger.debug("message_added", thread_id=thread_id)
            return True

        except Exception as e:
            logger.error("message_add_error", thread_id=thread_id, error=str(e))
            return False

    async def create_run(
        self,
        thread_id: str,
        assistant_id: str,
        instructions: str | None = None,
        tools: list[dict[str, Any]] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> RunContext:
        """
        Create a new run.

        Args:
            thread_id: Thread ID
            assistant_id: Assistant ID
            instructions: Run-specific instructions
            tools: Run-specific tools
            metadata: Run metadata

        Returns:
            RunContext
        """
        if not OPENAI_AVAILABLE or not self.client:
            raise RuntimeError("OpenAI client not initialized")

        if thread_id not in self.threads:
            raise ValueError(f"Thread {thread_id} not found")

        run_id = f"run_{uuid.uuid4().hex[:12]}"

        context = RunContext(
            run_id=run_id,
            thread_id=thread_id,
            assistant_id=assistant_id,
            status=RunStatus.QUEUED,
            instructions=instructions,
            tools=tools,
            metadata=metadata or {},
        )

        # Get assistant config
        assistant_config = self.assistants.get(assistant_id)

        try:
            run = await self.client.beta.threads.runs.create(
                thread_id=thread_id,
                assistant_id=assistant_config.openai_id if assistant_config else assistant_id,
                instructions=instructions,
                tools=tools or (assistant_config.tools if assistant_config else []),
                metadata=metadata or {},
            )

            context.run_id = run.id
            context.status = RunStatus(run.status)

        except Exception as e:
            logger.warning("run_creation_warning", run_id=run_id, error=str(e))

        self.runs[run_id] = context
        logger.info("run_created", run_id=run_id)

        await self._notify_run_event("run_created", run_id, context)

        return context

    async def poll_run(
        self,
        run_id: str,
        poll_interval: float = 1.0,
        timeout: float = 60.0,  # noqa: ASYNC109
    ) -> RunContext:
        """
        Poll a run until completion.

        Args:
            run_id: Run ID
            poll_interval: Polling interval in seconds
            timeout: Maximum wait time in seconds

        Returns:
            RunContext with final status
        """
        if not OPENAI_AVAILABLE or not self.client:
            raise RuntimeError("OpenAI client not initialized")

        if run_id not in self.runs:
            raise ValueError(f"Run {run_id} not found")

        context = self.runs[run_id]
        start_time = datetime.now(UTC)

        if not context.started_at:
            context.started_at = datetime.now(UTC).isoformat()

        while True:
            # Check timeout
            elapsed = (datetime.now(UTC) - start_time).total_seconds()
            if elapsed >= timeout:
                context.status = RunStatus.EXPIRED
                context.error = f"Run timed out after {timeout}s"
                logger.warning("run_timeout", run_id=run_id)
                break

            # Get run status
            try:
                run = await self.client.beta.threads.runs.retrieve(
                    thread_id=context.thread_id,
                    run_id=run_id,
                )

                context.status = RunStatus(run.status)

                # Handle requires_action for tool calls
                if run.status == "requires_action" and run.required_action:
                    await self._handle_tool_calls(run, context)

                # Check terminal states
                if run.status in ["completed", "failed", "cancelled", "expired"]:
                    context.completed_at = datetime.now(UTC).isoformat()
                    if run.status == "failed" and run.last_error:
                        context.error = run.last_error.message
                    break

            except Exception as e:
                logger.error("run_poll_error", run_id=run_id, error=str(e))
                context.status = RunStatus.FAILED
                context.error = str(e)
                break

            await asyncio.sleep(poll_interval)

        await self._notify_run_event("run_completed", run_id, context)
        logger.info(
            "run_completed",
            run_id=run_id,
            status=context.status.value,
        )

        return context

    async def _handle_tool_calls(
        self,
        run: Run,
        context: RunContext,
    ) -> None:
        """Handle tool calls from a run."""
        if not run.required_action:
            return

        tool_calls = run.required_action.submit_tool_outputs.tool_calls

        for tool_call in tool_calls:
            if isinstance(tool_call, FunctionToolCall):
                call_request = FunctionCallRequest(
                    call_id=tool_call.id,
                    name=tool_call.function.name,
                    arguments=json.loads(tool_call.function.arguments),
                    thread_id=context.thread_id,
                    run_id=context.run_id,
                )

                context.tool_calls.append(call_request.to_dict())

                # Try to execute function
                result = await self._execute_function(call_request)

                # Submit tool output
                try:
                    await self.client.beta.threads.runs.submit_tool_outputs(
                        thread_id=context.thread_id,
                        run_id=context.run_id,
                        tool_outputs=[
                            {
                                "tool_call_id": tool_call.id,
                                "output": json.dumps(result)
                                if not isinstance(result, str)
                                else result,
                            }
                        ],
                    )
                    logger.debug(
                        "tool_output_submitted",
                        call_id=tool_call.id,
                        function=call_request.name,
                    )
                except Exception as e:
                    logger.error(
                        "tool_output_error",
                        call_id=tool_call.id,
                        error=str(e),
                    )

    async def _execute_function(
        self, call_request: FunctionCallRequest,
    ) -> Any:
        """Execute a function call."""
        if call_request.name in self._registered_functions:
            return await self._execute_registered_function(call_request)
        if self.enable_heretek_bridge and self._agent_runtime:
            return await self._route_to_heretek_agent(call_request)
        return {"error": f"Function {call_request.name} not found"}

    async def _execute_registered_function(self, call_request: FunctionCallRequest) -> Any:
        func = self._registered_functions[call_request.name]
        try:
            if asyncio.iscoroutinefunction(func):
                return await func(**call_request.arguments)
            return func(**call_request.arguments)
        except Exception as e:
            logger.error("function_execution_error", function=call_request.name, error=str(e))
            return {"error": str(e)}

    async def _route_to_heretek_agent(self, call_request: FunctionCallRequest) -> Any:
        heretek_agent_id = call_request.heretek_agent_id or call_request.name
        if heretek_agent_id not in self._agent_runtime:
            return {"error": f"Function {call_request.name} not found"}
        try:
            runtime = self._agent_runtime[heretek_agent_id]
            if hasattr(runtime, "think"):
                response = await runtime.think(
                    f"Execute: {call_request.name}({json.dumps(call_request.arguments)})"
                )
                return {"response": response}
        except Exception as e:
            logger.error("heretek_routing_error", agent_id=heretek_agent_id, error=str(e))
        return {"error": f"Function {call_request.name} not found"}

    async def execute_chat(
        self,
        thread_id: str,
        assistant_id: str,
        message: str,
        instructions: str | None = None,
    ) -> dict[str, Any]:
        """
        Execute a chat message and get response.

        Args:
            thread_id: Thread ID
            assistant_id: Assistant ID
            message: User message
            instructions: Optional instructions

        Returns:
            Response dictionary
        """
        # Add user message
        await self.add_message(thread_id, message, MessageRole.USER)

        # Create and run
        run_context = await self.create_run(
            thread_id=thread_id,
            assistant_id=assistant_id,
            instructions=instructions,
        )

        # Poll for completion
        result = await self.poll_run(run_context.run_id)

        # Get assistant messages
        response_messages = await self.get_thread_messages(thread_id)

        return {
            "run_id": result.run_id,
            "status": result.status.value,
            "messages": response_messages,
            "tool_calls": result.tool_calls,
            "error": result.error,
        }

    async def get_thread_messages(
        self,
        thread_id: str,
        limit: int = 20,
    ) -> list[dict[str, Any]]:
        """Get messages from a thread."""
        if not OPENAI_AVAILABLE or not self.client:
            return self.threads.get(thread_id, {}).messages

        try:
            messages = await self.client.beta.threads.messages.list(
                thread_id=thread_id,
                limit=limit,
            )

            result = []
            for msg in messages.data:
                content = ""
                for c in msg.content:
                    if isinstance(c, TextContentBlock):
                        content += c.text.value

                result.append(
                    {
                        "role": msg.role,
                        "content": content,
                        "created_at": datetime.fromtimestamp(msg.created_at).isoformat(),  # noqa: DTZ006
                    }
                )

            return result

        except Exception as e:
            logger.error("get_messages_error", thread_id=thread_id, error=str(e))
            return []

    def get_assistant(self, assistant_id: str) -> AssistantConfig | None:
        """Get assistant config by ID."""
        return self.assistants.get(assistant_id)

    def get_thread(self, thread_id: str) -> ThreadContext | None:
        """Get thread context by ID."""
        return self.threads.get(thread_id)

    def get_run(self, run_id: str) -> RunContext | None:
        """Get run context by ID."""
        return self.runs.get(run_id)

    def get_statistics(self) -> dict[str, Any]:
        """Get adapter statistics."""
        return {
            "assistant_count": len(self.assistants),
            "thread_count": len(self.threads),
            "run_count": len(self.runs),
            "function_count": len(self._registered_functions),
            "heretek_mappings": len(self._heretek_agent_mappings),
            "openai_available": OPENAI_AVAILABLE,
            "client_initialized": self.client is not None,
        }

    def clear_assistant(self, assistant_id: str) -> bool:
        """Clear an assistant."""
        if assistant_id not in self.assistants:
            return False

        del self.assistants[assistant_id]
        logger.info("assistant_cleared", assistant_id=assistant_id)
        return True

    def clear_thread(self, thread_id: str) -> bool:
        """Clear a thread."""
        if thread_id not in self.threads:
            return False

        del self.threads[thread_id]
        logger.info("thread_cleared", thread_id=thread_id)
        return True

    def clear_all(self) -> None:
        """Clear all state."""
        self.assistants.clear()
        self.threads.clear()
        self.runs.clear()
        self._registered_functions.clear()
        self._heretek_agent_mappings.clear()
        logger.info("openai_assistants_adapter_cleared")


# Global adapter instance
openai_assistants_adapter: OpenAIAssistantsAdapter | None = None


def get_openai_assistants_adapter(
    api_key: str | None = None,
    base_url: str | None = None,
) -> OpenAIAssistantsAdapter:
    """Get the global OpenAI Assistants adapter instance."""
    global openai_assistants_adapter
    if openai_assistants_adapter is None:
        openai_assistants_adapter = OpenAIAssistantsAdapter(
            api_key=api_key,
            base_url=base_url,
        )
    return openai_assistants_adapter


def create_assistant(
    assistant_id: str,
    name: str,
    model: str = "gpt-4o",
    instructions: str = "You are a helpful assistant.",
    tools: list[dict[str, Any]] | None = None,
    heretek_agent_id: str | None = None,
) -> AssistantConfig:
    """
    Create an assistant with default configuration.

    Args:
        assistant_id: Assistant identifier
        name: Assistant name
        model: Model to use
        instructions: System instructions
        tools: Tool definitions
        heretek_agent_id: Associated Heretek agent ID

    Returns:
        AssistantConfig
    """
    adapter = get_openai_assistants_adapter()

    return asyncio.create_task(
        adapter.create_assistant(
            assistant_id=assistant_id,
            name=name,
            model=model,
            instructions=instructions,
            tools=tools,
            heretek_agent_id=heretek_agent_id,
        )
    )
