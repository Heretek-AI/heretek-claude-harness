"""
Anthropic Claude Integration Module for Heretek Swarm

This module provides bi-directional integration between Heretek Swarm agents and Anthropic's Claude API.  # noqa: E501
It enables Messages API compatibility, tool use handling, multi-turn conversations, and context management.  # noqa: E501

Features:
- Messages API compatibility layer
- Tool use handling
- Multi-turn conversation support
- Context management with token counting
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

from heretek_swarm.integrations.openai_assistants import MessageRole  # noqa: E402

try:
    from anthropic import Anthropic, AsyncAnthropic
    from anthropic.types import ContentBlock, Message, TextBlock, ToolUseBlock
    from anthropic.types.beta.tools import ToolsBetaMessage
    from anthropic.types.beta.tools import ToolUseBlock as BetaToolUseBlock

    ANTHROPIC_AVAILABLE = True
except ImportError:
    ANTHROPIC_AVAILABLE = False
    Anthropic = None
    AsyncAnthropic = None
    Message = None
    ContentBlock = None
    TextBlock = None
    ToolUseBlock = None
    ToolsBetaMessage = None
    BetaToolUseBlock = None


class AnthropicMessageRole(StrEnum):
    """Message roles for Anthropic API."""

    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"
    TOOL = "tool"


class StopReason(StrEnum):
    """Message stop reasons."""

    END_TURN = "end_turn"
    MAX_TOKENS = "max_tokens"
    STOP_SEQUENCE = "stop_sequence"
    TOOL_USE = "tool_use"


@dataclass
class ToolDefinition:
    """
    Tool definition for Anthropic API.

    Attributes:
        name: Tool name
        description: Tool description
        input_schema: JSON schema for input
        handler: Optional handler function
    """

    name: str
    description: str
    input_schema: dict[str, Any]
    handler: Callable | None = None
    heretek_agent_id: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "name": self.name,
            "description": self.description,
            "input_schema": self.input_schema,
            "has_handler": self.handler is not None,
            "heretek_agent_id": self.heretek_agent_id,
            "metadata": self.metadata,
        }

    def to_anthropic_format(self) -> dict[str, Any]:
        """Convert to Anthropic tool format."""
        return {
            "name": self.name,
            "description": self.description,
            "input_schema": self.input_schema,
        }


@dataclass
class ConversationMessage:
    """
    A message in a conversation.

    Attributes:
        message_id: Unique message identifier
        role: Message role
        content: Message content
        tool_calls: Tool calls if any
        tool_results: Tool results if any
        timestamp: Message timestamp
    """

    message_id: str
    role: AnthropicMessageRole
    content: str | list[dict[str, Any]]
    tool_calls: list[dict[str, Any]] = field(default_factory=list)
    tool_results: list[dict[str, Any]] = field(default_factory=list)
    timestamp: str = field(default_factory=lambda: datetime.now(UTC).isoformat())
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "message_id": self.message_id,
            "role": self.role.value,
            "content": self.content,
            "tool_calls": self.tool_calls,
            "tool_results": self.tool_results,
            "timestamp": self.timestamp,
            "metadata": self.metadata,
        }

    def to_anthropic_format(self) -> dict[str, Any]:
        """Convert to Anthropic messages API format."""
        if self.role == AnthropicMessageRole.USER:
            return {
                "role": "user",
                "content": self.content,
            }
        if self.role == AnthropicMessageRole.ASSISTANT:
            content = []
            if isinstance(self.content, str):
                content.append({"type": "text", "text": self.content})

            for tool_call in self.tool_calls:
                content.append(  # noqa: PERF401
                    {
                        "type": "tool_use",
                        "id": tool_call.get("id", str(uuid.uuid4())),
                        "name": tool_call.get("name", "unknown"),
                        "input": tool_call.get("input", {}),
                    }
                )

            return {
                "role": "assistant",
                "content": content,
            }

        return {"role": self.role.value, "content": self.content}


@dataclass
class ConversationContext:
    """
    Context for a conversation.

    Attributes:
        conversation_id: Unique conversation identifier
        messages: Message history
        system_prompt: System prompt
        max_tokens: Maximum tokens
        temperature: Temperature setting
        tools: Available tools
        metadata: Additional metadata
    """

    conversation_id: str
    messages: list[ConversationMessage] = field(default_factory=list)
    system_prompt: str | None = None
    max_tokens: int = 1024
    temperature: float = 0.7
    tools: list[ToolDefinition] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
    heretek_context: dict[str, Any] = field(default_factory=dict)
    token_count: int = 0

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "conversation_id": self.conversation_id,
            "message_count": len(self.messages),
            "system_prompt": self.system_prompt,
            "max_tokens": self.max_tokens,
            "temperature": self.temperature,
            "tool_count": len(self.tools),
            "token_count": self.token_count,
            "metadata": self.metadata,
            "heretek_context": self.heretek_context,
        }

    def add_message(
        self,
        role: AnthropicMessageRole,
        content: str | list[dict[str, Any]],
        **kwargs,
    ) -> ConversationMessage:
        """Add a message to the conversation."""
        message = ConversationMessage(
            message_id=f"msg_{uuid.uuid4().hex[:12]}",
            role=role,
            content=content,
            **kwargs,
        )
        self.messages.append(message)
        self._update_token_count()
        return message

    def _update_token_count(self) -> None:
        """Estimate token count."""
        # Rough estimation: 1 token ~ 4 characters
        total_chars = 0
        for msg in self.messages:
            if isinstance(msg.content, str):
                total_chars += len(msg.content)
            else:
                total_chars += len(json.dumps(msg.content))

        if self.system_prompt:
            total_chars += len(self.system_prompt)

        self.token_count = total_chars // 4


@dataclass
class ToolUseRequest:
    """
    Request for tool use.

    Attributes:
        request_id: Unique request identifier
        tool_name: Tool name
        tool_input: Tool input arguments
        conversation_id: Associated conversation ID
        heretek_agent_id: Optional Heretek agent ID
    """

    request_id: str
    tool_name: str
    tool_input: dict[str, Any]
    conversation_id: str
    heretek_agent_id: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "request_id": self.request_id,
            "tool_name": self.tool_name,
            "tool_input": self.tool_input,
            "conversation_id": self.conversation_id,
            "heretek_agent_id": self.heretek_agent_id,
        }


class AnthropicAdapter:
    """
    Adapter for integrating Anthropic Claude with Heretek Swarm.

    This adapter provides:
    - Messages API compatibility layer
    - Tool use handling with Heretek integration
    - Multi-turn conversation support
    - Context management

    Attributes:
        client: Anthropic client instance
        conversations: Active conversations
        tools: Registered tools
    """

    def __init__(
        self,
        api_key: str | None = None,
        base_url: str | None = None,
        enable_heretek_bridge: bool = True,
        default_max_tokens: int = 1024,
        default_temperature: float = 0.7,
    ) -> None:
        """
        Initialize the Anthropic adapter.

        Args:
            api_key: Anthropic API key
            base_url: Optional base URL for API
            enable_heretek_bridge: Enable Heretek agent bridging
            default_max_tokens: Default maximum tokens
            default_temperature: Default temperature
        """
        self.api_key = api_key
        self.base_url = base_url

        self.client: AsyncAnthropic | None = None
        self.sync_client: Anthropic | None = None

        if ANTHROPIC_AVAILABLE and api_key:
            self.client = AsyncAnthropic(
                api_key=api_key,
                base_url=base_url,
            )
            self.sync_client = Anthropic(
                api_key=api_key,
                base_url=base_url,
            )

        self.conversations: dict[str, ConversationContext] = {}
        self.tools: dict[str, ToolDefinition] = {}

        self.enable_heretek_bridge = enable_heretek_bridge
        self.default_max_tokens = default_max_tokens
        self.default_temperature = default_temperature

        self._agent_runtime = None
        self._heretek_agent_mappings: dict[str, str] = {}

        # Conversation callbacks
        self._conversation_callbacks: list[Callable] = []

        logger.info(
            "anthropic_adapter_initialized",
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
        tool_name: str,
    ) -> None:
        """Register a mapping between Heretek agent and tool."""
        self._heretek_agent_mappings[heretek_agent_id] = tool_name
        if tool_name in self.tools:
            self.tools[tool_name].heretek_agent_id = heretek_agent_id
        logger.info(
            "heretek_agent_mapping_registered",
            heretek_agent_id=heretek_agent_id,
            tool_name=tool_name,
        )

    def register_conversation_callback(self, callback: Callable) -> None:
        """Register a callback for conversation events."""
        self._conversation_callbacks.append(callback)
        logger.debug("conversation_callback_registered", callback=callback.__name__)

    async def _notify_conversation_event(
        self,
        event_type: str,
        conversation_id: str,
        message: ConversationMessage | None = None,
    ) -> None:
        """Notify callbacks of conversation events."""
        for callback in self._conversation_callbacks:
            try:
                if asyncio.iscoroutinefunction(callback):
                    await callback(event_type, conversation_id, message)
                else:
                    callback(event_type, conversation_id, message)
            except Exception as e:
                logger.error("conversation_callback_error", error=str(e))

    def register_tool(
        self,
        name: str,
        description: str,
        input_schema: dict[str, Any],
        handler: Callable | None = None,
        heretek_agent_id: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> ToolDefinition:
        """
        Register a tool for use with Claude.

        Args:
            name: Tool name
            description: Tool description
            input_schema: JSON schema for input
            handler: Optional handler function
            heretek_agent_id: Optional Heretek agent ID for routing
            metadata: Additional metadata

        Returns:
            ToolDefinition
        """
        tool = ToolDefinition(
            name=name,
            description=description,
            input_schema=input_schema,
            handler=handler,
            heretek_agent_id=heretek_agent_id,
            metadata=metadata or {},
        )

        self.tools[name] = tool
        logger.info("tool_registered", name=name)

        return tool

    def create_conversation(
        self,
        conversation_id: str | None = None,
        system_prompt: str | None = None,
        max_tokens: int | None = None,
        temperature: float | None = None,
        tools: list[str] | None = None,
        metadata: dict[str, Any] | None = None,
        heretek_context: dict[str, Any] | None = None,
    ) -> ConversationContext:
        """
        Create a new conversation context.

        Args:
            conversation_id: Optional conversation identifier
            system_prompt: System prompt
            max_tokens: Maximum tokens
            temperature: Temperature setting
            tools: List of tool names to enable
            metadata: Additional metadata
            heretek_context: Heretek-specific context

        Returns:
            ConversationContext
        """
        if conversation_id is None:
            conversation_id = f"conv_{uuid.uuid4().hex[:12]}"

        # Get selected tools
        selected_tools = []
        if tools:
            for tool_name in tools:
                if tool_name in self.tools:
                    selected_tools.append(self.tools[tool_name])  # noqa: PERF401

        context = ConversationContext(
            conversation_id=conversation_id,
            system_prompt=system_prompt,
            max_tokens=max_tokens or self.default_max_tokens,
            temperature=temperature or self.default_temperature,
            tools=selected_tools,
            metadata=metadata or {},
            heretek_context=heretek_context or {},
        )

        self.conversations[conversation_id] = context
        logger.info(
            "conversation_created",
            conversation_id=conversation_id,
            tool_count=len(selected_tools),
        )

        return context

    async def send_message(
        self,
        conversation_id: str,
        content: str,
        role: AnthropicMessageRole = AnthropicMessageRole.USER,
        max_tokens: int | None = None,
        temperature: float | None = None,
        system_prompt: str | None = None,
    ) -> ConversationMessage:
        """
        Send a message and get a response.

        Args:
            conversation_id: Conversation ID
            content: Message content
            role: Message role
            max_tokens: Maximum tokens
            temperature: Temperature
            system_prompt: Optional system prompt override

        Returns:
            Response message
        """
        if not ANTHROPIC_AVAILABLE or not self.client:
            raise RuntimeError("Anthropic client not initialized. Provide API key.")

        if conversation_id not in self.conversations:
            raise ValueError(f"Conversation {conversation_id} not found")

        context = self.conversations[conversation_id]

        # Add user message
        user_message = context.add_message(role, content)
        await self._notify_conversation_event("message_sent", conversation_id, user_message)

        # Prepare API request
        messages = [
            m.to_anthropic_format()
            for m in context.messages
            if m.role in [MessageRole.USER, MessageRole.ASSISTANT]
        ]

        # Get tools
        tool_defs = [t.to_anthropic_format() for t in context.tools] if context.tools else None

        # Get system prompt
        system = system_prompt or context.system_prompt

        try:
            # Send message
            response = await self.client.messages.create(
                model="claude-sonnet-4-20250514",
                max_tokens=max_tokens or context.max_tokens,
                messages=messages,
                system=system,
                temperature=temperature or context.temperature,
                tools=tool_defs if tool_defs else None,
            )

            # Process response
            assistant_message = await self._process_response(response, context)

            # Handle tool uses recursively
            if assistant_message.tool_calls:
                await self._handle_tool_uses(assistant_message, context)

            await self._notify_conversation_event(
                "message_received",
                conversation_id,
                assistant_message,
            )

            logger.info(
                "message_sent",
                conversation_id=conversation_id,
                stop_reason=response.stop_reason,
            )

            return assistant_message

        except Exception as e:
            logger.error("message_send_error", conversation_id=conversation_id, error=str(e))
            raise

    async def _process_response(
        self,
        response: Message,
        context: ConversationContext,
    ) -> ConversationMessage:
        """Process API response into a ConversationMessage."""
        content_parts = []
        tool_calls = []

        for block in response.content:
            if isinstance(block, TextBlock):
                content_parts.append(block.text)
            elif isinstance(block, (ToolUseBlock, BetaToolUseBlock)):
                tool_calls.append(
                    {
                        "id": block.id,
                        "name": block.name,
                        "input": block.input if hasattr(block, "input") else {},
                    }
                )

        content = "\n".join(content_parts) if content_parts else ""

        return context.add_message(
            MessageRole.ASSISTANT,
            content if content else "[Tool use]",
            tool_calls=tool_calls,
        )

    async def _handle_tool_uses(
        self,
        assistant_message: ConversationMessage,
        context: ConversationContext,
    ) -> None:
        """Handle tool uses from assistant message."""
        for tool_call in assistant_message.tool_calls:
            request = ToolUseRequest(
                request_id=tool_call.get("id", str(uuid.uuid4())),
                tool_name=tool_call.get("name", "unknown"),
                tool_input=tool_call.get("input", {}),
                conversation_id=context.conversation_id,
            )

            # Execute tool
            result = await self._execute_tool(request, context)

            # Add tool result message
            tool_result_message = {
                "type": "tool_result",
                "tool_use_id": request.request_id,
                "content": result if isinstance(result, str) else json.dumps(result),
            }

            context.add_message(
                MessageRole.USER,
                [tool_result_message],
                tool_results=[
                    {
                        "tool_use_id": request.request_id,
                        "result": result,
                    }
                ],
            )

            # Get follow-up response
            messages = [m.to_anthropic_format() for m in context.messages]

            try:
                response = await self.client.messages.create(
                    model="claude-sonnet-4-20250514",
                    max_tokens=context.max_tokens,
                    messages=messages,
                    system=context.system_prompt,
                    temperature=context.temperature,
                    tools=[t.to_anthropic_format() for t in context.tools]
                    if context.tools
                    else None,
                )

                # Process follow-up
                follow_up = await self._process_response(response, context)

                # Handle nested tool uses
                if follow_up.tool_calls:
                    await self._handle_tool_uses(follow_up, context)

            except Exception as e:
                logger.error("tool_follow_up_error", error=str(e))

    async def _execute_tool(
        self,
        request: ToolUseRequest,
        context: ConversationContext,  # noqa: ARG002
    ) -> Any:
        """Execute a tool request."""
        tool = self.tools.get(request.tool_name)

        if tool and tool.handler:
            try:
                if asyncio.iscoroutinefunction(tool.handler):
                    return await tool.handler(**request.tool_input)
                return tool.handler(**request.tool_input)
            except Exception as e:
                logger.error(
                    "tool_execution_error",
                    tool_name=request.tool_name,
                    error=str(e),
                )
                return {"error": str(e)}

        # Try Heretek bridge
        if self.enable_heretek_bridge and self._agent_runtime:
            heretek_agent_id = tool.heretek_agent_id if tool else request.tool_name

            if heretek_agent_id in self._agent_runtime:
                try:
                    runtime = self._agent_runtime[heretek_agent_id]
                    if hasattr(runtime, "think"):
                        prompt = (
                            f"Execute tool: {request.tool_name}({json.dumps(request.tool_input)})"
                        )
                        return await runtime.think(prompt)
                except Exception as e:
                    logger.error(
                        "heretek_tool_routing_error",
                        agent_id=heretek_agent_id,
                        error=str(e),
                    )

        return {"error": f"Tool {request.tool_name} not found or no handler"}

    async def chat(
        self,
        conversation_id: str,
        user_message: str,
        max_turns: int = 5,
    ) -> list[ConversationMessage]:
        """
        Multi-turn chat conversation.

        Args:
            conversation_id: Conversation ID
            user_message: Initial user message
            max_turns: Maximum conversation turns

        Returns:
            List of conversation messages
        """
        messages = []
        current_message = user_message

        for _ in range(max_turns):
            response = await self.send_message(conversation_id, current_message)
            messages.append(response)

            # Check if response has tool calls (needs more turns)
            if not response.tool_calls:
                break

            current_message = ""  # Empty for tool result follow-up

        return messages

    def get_conversation(self, conversation_id: str) -> ConversationContext | None:
        """Get conversation context by ID."""
        return self.conversations.get(conversation_id)

    def get_conversation_history(
        self,
        conversation_id: str,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        """Get conversation message history."""
        context = self.conversations.get(conversation_id)
        if not context:
            return []

        return [m.to_dict() for m in context.messages[-limit:]]

    def get_tool(self, name: str) -> ToolDefinition | None:
        """Get tool by name."""
        return self.tools.get(name)

    def get_statistics(self) -> dict[str, Any]:
        """Get adapter statistics."""
        total_tokens = sum(c.token_count for c in self.conversations.values())

        return {
            "conversation_count": len(self.conversations),
            "tool_count": len(self.tools),
            "total_estimated_tokens": total_tokens,
            "heretek_mappings": len(self._heretek_agent_mappings),
            "anthropic_available": ANTHROPIC_AVAILABLE,
            "client_initialized": self.client is not None,
        }

    def clear_conversation(self, conversation_id: str) -> bool:
        """Clear a conversation."""
        if conversation_id not in self.conversations:
            return False

        del self.conversations[conversation_id]
        logger.info("conversation_cleared", conversation_id=conversation_id)
        return True

    def clear_tool(self, name: str) -> bool:
        """Clear a tool."""
        if name not in self.tools:
            return False

        del self.tools[name]
        logger.info("tool_cleared", name=name)
        return True

    def clear_all(self) -> None:
        """Clear all state."""
        self.conversations.clear()
        self.tools.clear()
        self._heretek_agent_mappings.clear()
        logger.info("anthropic_adapter_cleared")


# Global adapter instance
anthropic_adapter: AnthropicAdapter | None = None


def get_anthropic_adapter(
    api_key: str | None = None,
    base_url: str | None = None,
) -> AnthropicAdapter:
    """Get the global Anthropic adapter instance."""
    global anthropic_adapter
    if anthropic_adapter is None:
        anthropic_adapter = AnthropicAdapter(
            api_key=api_key,
            base_url=base_url,
        )
    return anthropic_adapter


def create_conversation(
    conversation_id: str | None = None,
    system_prompt: str | None = None,
    tools: list[dict[str, Any]] | None = None,
) -> ConversationContext:
    """
    Create a conversation with default settings.

    Args:
        conversation_id: Optional conversation identifier
        system_prompt: System prompt
        tools: List of tool definitions

    Returns:
        ConversationContext
    """
    adapter = get_anthropic_adapter()

    tool_names = None
    if tools:
        for tool in tools:
            adapter.register_tool(
                name=tool.get("name", "unknown"),
                description=tool.get("description", ""),
                input_schema=tool.get("input_schema", {}),
                handler=tool.get("handler"),
            )
        tool_names = [t.get("name") for t in tools]

    return adapter.create_conversation(
        conversation_id=conversation_id,
        system_prompt=system_prompt,
        tools=tool_names,
    )
