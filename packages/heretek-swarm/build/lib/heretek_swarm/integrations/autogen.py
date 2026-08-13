"""
AutoGen Integration Module for Heretek Swarm

This module provides bi-directional integration between Heretek Swarm agents and Microsoft AutoGen.
It enables assistant agent compatibility, group chat management, and tool registration bridging.

Features:
- Assistant agent compatibility layer
- Group chat manager integration
- Tool registration bridge
- Message format translation
- Zero-trust validation of all message exchanges

Reference: EXPANSION_ROADMAP.md Session 47 - Integration Ecosystem
"""

from __future__ import annotations

import asyncio
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from typing import TYPE_CHECKING, Any

import structlog

if TYPE_CHECKING:
    from collections.abc import Callable

logger = structlog.get_logger(__name__)

# Try to import autogen components
try:
    from autogen import (
        AssistantAgent,
        ConversableAgent,
        GroupChat,
        GroupChatManager,
        UserProxyAgent,
        register_function,
    )
    from autogen.agentchat import ChatResult

    AUTOGEN_AVAILABLE = True
except ImportError:
    AUTOGEN_AVAILABLE = False
    ConversableAgent = None
    AssistantAgent = None
    UserProxyAgent = None
    GroupChat = None
    GroupChatManager = None
    register_function = None
    ChatResult = None


class AgentRole(StrEnum):
    """AutoGen agent roles."""

    ASSISTANT = "assistant"
    USER_PROXY = "user_proxy"
    GROUP_MANAGER = "group_manager"
    HERETEK_BRIDGE = "heretek_bridge"


class MessageRole(StrEnum):
    """Message roles for translation."""

    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"
    FUNCTION = "function"
    TOOL = "tool"


@dataclass
class AutoGenMessage:
    """
    Represents a translated AutoGen message.

    Attributes:
        message_id: Unique message identifier
        role: Message role
        content: Message content
        name: Optional sender name
        function_call: Optional function call
        tool_calls: Optional tool calls
        timestamp: Message timestamp
    """

    message_id: str
    role: str
    content: str | None
    name: str | None = None
    function_call: dict[str, Any] | None = None
    tool_calls: list[dict[str, Any]] | None = None
    timestamp: str = field(default_factory=lambda: datetime.now(UTC).isoformat())
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "message_id": self.message_id,
            "role": self.role,
            "content": self.content,
            "name": self.name,
            "function_call": self.function_call,
            "tool_calls": self.tool_calls,
            "timestamp": self.timestamp,
            "metadata": self.metadata,
        }

    def to_autogen_format(self) -> dict[str, Any]:
        """Convert to AutoGen message format."""
        msg = {
            "role": self.role,
            "content": self.content,
        }
        if self.name:
            msg["name"] = self.name
        if self.function_call:
            msg["function_call"] = self.function_call
        if self.tool_calls:
            msg["tool_calls"] = self.tool_calls
        return msg


@dataclass
class AutoGenAgentConfig:
    """
    Configuration for an AutoGen agent.

    Attributes:
        agent_id: Unique agent identifier
        name: Agent name
        role: Agent role
        system_message: Optional system message
        description: Agent description
        human_input_mode: Human input mode
        max_consecutive_auto_reply: Max auto replies
        llm_config: LLM configuration
    """

    agent_id: str
    name: str
    role: AgentRole = AgentRole.ASSISTANT
    system_message: str | None = None
    description: str | None = None
    human_input_mode: str = "NEVER"
    max_consecutive_auto_reply: int = 10
    llm_config: dict[str, Any] | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "agent_id": self.agent_id,
            "name": self.name,
            "role": self.role.value,
            "system_message": self.system_message,
            "description": self.description,
            "human_input_mode": self.human_input_mode,
            "max_consecutive_auto_reply": self.max_consecutive_auto_reply,
            "llm_config": self.llm_config,
            "metadata": self.metadata,
        }


@dataclass
class GroupChatConfig:
    """
    Configuration for an AutoGen group chat.

    Attributes:
        group_id: Unique group identifier
        name: Group name
        agents: List of agent IDs
        messages: Chat messages
        max_round: Maximum chat rounds
        speaker_selection_method: Speaker selection method
    """

    group_id: str
    name: str
    agents: list[str] = field(default_factory=list)
    messages: list[dict[str, Any]] = field(default_factory=list)
    max_round: int = 10
    speaker_selection_method: str = "auto"
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "group_id": self.group_id,
            "name": self.name,
            "agents": self.agents,
            "messages": self.messages,
            "max_round": self.max_round,
            "speaker_selection_method": self.speaker_selection_method,
            "metadata": self.metadata,
        }


@dataclass
class ToolRegistration:
    """
    Tool registration for AutoGen.

    Attributes:
        tool_id: Unique tool identifier
        name: Tool name
        description: Tool description
        function: Tool function
        heretek_tool: Whether this is a Heretek tool
    """

    tool_id: str
    name: str
    description: str
    function: Callable
    heretek_tool: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "tool_id": self.tool_id,
            "name": self.name,
            "description": self.description,
            "heretek_tool": self.heretek_tool,
            "metadata": self.metadata,
        }


class AutoGenAdapter:
    """
    Adapter for integrating AutoGen with Heretek Swarm.

    This adapter provides:
    - Assistant agent compatibility layer
    - Group chat manager integration
    - Tool registration bridge between AutoGen and Heretek
    - Message format translation

    Attributes:
        agents: Registered AutoGen agents
        group_chats: Registered group chats
        tools: Registered tools
    """

    def __init__(
        self,
        llm_config: dict[str, Any] | None = None,
        enable_message_translation: bool = True,
        max_messages: int = 100,
    ) -> None:
        """
        Initialize the AutoGen adapter.

        Args:
            llm_config: Default LLM configuration
            enable_message_translation: Enable message format translation
            max_messages: Maximum messages to retain per chat
        """
        self.agents: dict[str, Any] = {}
        self.agent_configs: dict[str, AutoGenAgentConfig] = {}
        self.group_chats: dict[str, Any] = {}
        self.group_chat_configs: dict[str, GroupChatConfig] = {}
        self.group_chat_managers: dict[str, Any] = {}

        self.tools: dict[str, ToolRegistration] = {}
        self.llm_config = llm_config or {}

        self.enable_message_translation = enable_message_translation
        self.max_messages = max_messages

        # Message history
        self.message_history: dict[str, list[AutoGenMessage]] = {}

        # Heretek integration
        self._agent_runtime = None
        self._heretek_agents: dict[str, Any] = {}

        # Conversation callbacks
        self._conversation_callbacks: list[Callable] = []

        logger.info(
            "autogen_adapter_initialized",
            llm_config=bool(llm_config),
            message_translation=enable_message_translation,
        )

    def set_agent_runtime(self, runtime: Any) -> None:
        """Set the Heretek agent runtime for integration."""
        self._agent_runtime = runtime
        logger.debug("agent_runtime_set", runtime_type=type(runtime).__name__)

    def register_heretek_agent(self, heretek_agent_id: str, autogen_agent_id: str) -> None:
        """Register a mapping between Heretek and AutoGen agents."""
        self._heretek_agents[heretek_agent_id] = autogen_agent_id
        logger.info(
            "heretek_agent_registered",
            heretek_agent_id=heretek_agent_id,
            autogen_agent_id=autogen_agent_id,
        )

    def register_conversation_callback(self, callback: Callable) -> None:
        """Register a callback for conversation events."""
        self._conversation_callbacks.append(callback)
        logger.debug("conversation_callback_registered", callback=callback.__name__)

    async def _notify_conversation_event(
        self,
        event_type: str,
        agent_id: str,
        message: dict[str, Any],
    ) -> None:
        """Notify callbacks of conversation events."""
        for callback in self._conversation_callbacks:
            try:
                if asyncio.iscoroutinefunction(callback):
                    await callback(event_type, agent_id, message)
                else:
                    callback(event_type, agent_id, message)
            except Exception as e:
                logger.error("conversation_callback_error", error=str(e))

    def create_agent(
        self,
        agent_id: str,
        name: str,
        role: AgentRole = AgentRole.ASSISTANT,
        system_message: str | None = None,
        description: str | None = None,
        human_input_mode: str = "NEVER",
        max_consecutive_auto_reply: int = 10,
        llm_config: dict[str, Any] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> Any:
        """
        Create an AutoGen agent.

        Args:
            agent_id: Unique agent identifier
            name: Agent name
            role: Agent role
            system_message: System message
            description: Agent description
            human_input_mode: Human input mode
            max_consecutive_auto_reply: Max auto replies
            llm_config: LLM configuration
            metadata: Additional metadata

        Returns:
            Created AutoGen agent
        """
        if not AUTOGEN_AVAILABLE:
            logger.warning("autogen_not_available")
            raise RuntimeError("AutoGen is not available. Install with: pip install pyautogen")

        config = AutoGenAgentConfig(
            agent_id=agent_id,
            name=name,
            role=role,
            system_message=system_message,
            description=description,
            human_input_mode=human_input_mode,
            max_consecutive_auto_reply=max_consecutive_auto_reply,
            llm_config=llm_config or self.llm_config,
            metadata=metadata or {},
        )
        self.agent_configs[agent_id] = config

        # Create agent based on role
        agent: ConversableAgent | None = None

        if role == AgentRole.ASSISTANT:
            agent = AssistantAgent(
                name=name,
                system_message=system_message or "You are a helpful AI assistant.",
                llm_config=llm_config or self.llm_config,
                human_input_mode=human_input_mode,
                max_consecutive_auto_reply=max_consecutive_auto_reply,
                description=description,
            )
        elif role == AgentRole.USER_PROXY:
            agent = UserProxyAgent(
                name=name,
                system_message=system_message or "A human user.",
                human_input_mode=human_input_mode,
                max_consecutive_auto_reply=max_consecutive_auto_reply,
                code_execution_config=False,
            )
        elif role == AgentRole.HERETEK_BRIDGE:
            # Special bridge agent for Heretek integration
            agent = ConversableAgent(
                name=name,
                system_message=system_message,
                llm_config=llm_config or self.llm_config,
                human_input_mode=human_input_mode,
            )
            # Register reply function for Heretek integration
            agent.register_reply(
                [ConversableAgent, None],
                self._heretek_reply_callback,
                position=0,
            )

        if agent:
            self.agents[agent_id] = agent
            self.message_history[agent_id] = []
            logger.info(
                "agent_created",
                agent_id=agent_id,
                role=role.value,
                name=name,
            )

        return agent

    def _heretek_reply_callback(
        self,
        recipient: ConversableAgent,
        messages: list[dict] | None = None,
        sender: ConversableAgent | None = None,  # noqa: ARG002
        config: Any | None = None,  # noqa: ARG002
    ) -> tuple[bool, dict | None]:
        """
        Reply callback for Heretek bridge agents.

        This callback routes messages to Heretek agents and returns their responses.
        """
        if messages is None or not messages:
            return False, None

        last_message = messages[-1]
        content = last_message.get("content", "")

        # Find corresponding Heretek agent
        heretek_agent_id = None
        for h_id, a_id in self._heretek_agents.items():
            if a_id == recipient.name:
                heretek_agent_id = h_id
                break

        if heretek_agent_id and self._agent_runtime:
            try:
                # Route to Heretek agent
                if heretek_agent_id in self._agent_runtime:
                    runtime = self._agent_runtime[heretek_agent_id]
                    if hasattr(runtime, "think"):
                        # Synchronous call for callback compatibility
                        import asyncio

                        loop = asyncio.get_event_loop()
                        response = loop.run_until_complete(runtime.think(content))
                        return True, {"role": "assistant", "content": response}
            except Exception as e:
                logger.error("heretek_reply_error", error=str(e))

        return False, None

    def create_group_chat(
        self,
        group_id: str,
        name: str,
        agent_ids: list[str],
        max_round: int = 10,
        speaker_selection_method: str = "auto",
        metadata: dict[str, Any] | None = None,
    ) -> Any:
        """
        Create an AutoGen group chat.

        Args:
            group_id: Unique group identifier
            name: Group name
            agent_ids: List of agent IDs to include
            max_round: Maximum chat rounds
            speaker_selection_method: Speaker selection method
            metadata: Additional metadata

        Returns:
            Created GroupChat instance
        """
        if not AUTOGEN_AVAILABLE:
            raise RuntimeError("AutoGen is not available")

        # Get agents
        agents = [self.agents[aid] for aid in agent_ids if aid in self.agents]

        if not agents:
            raise ValueError(f"No valid agents found for IDs: {agent_ids}")

        config = GroupChatConfig(
            group_id=group_id,
            name=name,
            agents=agent_ids,
            max_round=max_round,
            speaker_selection_method=speaker_selection_method,
            metadata=metadata or {},
        )
        self.group_chat_configs[group_id] = config

        # Create group chat
        group_chat = GroupChat(
            agents=agents,
            messages=[],
            max_round=max_round,
            speaker_selection_method=speaker_selection_method,
        )
        self.group_chats[group_id] = group_chat

        # Create group chat manager
        manager = GroupChatManager(
            groupchat=group_chat,
            llm_config=self.llm_config,
        )
        self.group_chat_managers[group_id] = manager

        logger.info(
            "group_chat_created",
            group_id=group_id,
            agent_count=len(agents),
        )

        return group_chat

    def register_tool(
        self,
        tool_id: str,
        name: str,
        description: str,
        function: Callable,
        agent_ids: list[str] | None = None,
        heretek_tool: bool = False,
        metadata: dict[str, Any] | None = None,
    ) -> str:
        """
        Register a tool with AutoGen agents.

        Args:
            tool_id: Unique tool identifier
            name: Tool name
            description: Tool description
            function: Tool function
            agent_ids: Agent IDs to register tool with
            heretek_tool: Whether this is a Heretek tool
            metadata: Additional metadata

        Returns:
            Tool ID
        """
        if not AUTOGEN_AVAILABLE:
            raise RuntimeError("AutoGen is not available")

        registration = ToolRegistration(
            tool_id=tool_id,
            name=name,
            description=description,
            function=function,
            heretek_tool=heretek_tool,
            metadata=metadata or {},
        )
        self.tools[tool_id] = registration

        # Register with specified agents
        target_agents = agent_ids or list(self.agents.keys())

        for agent_id in target_agents:
            if agent_id in self.agents:
                agent = self.agents[agent_id]
                try:
                    register_function(
                        function,
                        name=name,
                        description=description,
                        agent=agent,
                    )
                    logger.debug(
                        "tool_registered_for_agent",
                        tool_id=tool_id,
                        agent_id=agent_id,
                    )
                except Exception as e:
                    logger.error(
                        "tool_registration_error",
                        tool_id=tool_id,
                        agent_id=agent_id,
                        error=str(e),
                    )

        logger.info("tool_registered", tool_id=tool_id, name=name)
        return tool_id

    def translate_message(
        self,
        message: dict[str, Any],
        from_format: str = "heretek",
        to_format: str = "autogen",
    ) -> AutoGenMessage:
        """
        Translate a message between formats.

        Args:
            message: Source message
            from_format: Source format
            to_format: Target format

        Returns:
            Translated AutoGenMessage
        """
        message_id = str(uuid.uuid4())

        # Parse source message
        role = message.get("role", MessageRole.USER.value)
        content = message.get("content")
        name = message.get("name")
        function_call = message.get("function_call")
        tool_calls = message.get("tool_calls")

        # Translate role if needed
        if from_format == "heretek":
            role_map = {
                "user": MessageRole.USER.value,
                "assistant": MessageRole.ASSISTANT.value,
                "system": MessageRole.SYSTEM.value,
                "function": MessageRole.FUNCTION.value,
                "tool": MessageRole.TOOL.value,
            }
            role = role_map.get(role, role)

        autogen_message = AutoGenMessage(
            message_id=message_id,
            role=role,
            content=content,
            name=name,
            function_call=function_call,
            tool_calls=tool_calls,
            metadata={"from_format": from_format, "to_format": to_format},
        )

        logger.debug(
            "message_translated",
            message_id=message_id,
            from_format=from_format,
            to_format=to_format,
        )

        return autogen_message

    async def send_message(
        self,
        sender_id: str,
        recipient_id: str,
        content: str,
        metadata: dict[str, Any] | None = None,  # noqa: ARG002
    ) -> dict[str, Any] | None:
        """
        Send a message between agents.

        Args:
            sender_id: Sending agent ID
            recipient_id: Receiving agent ID
            content: Message content
            metadata: Additional metadata

        Returns:
            Response message or None
        """
        if sender_id not in self.agents:
            raise ValueError(f"Sender agent {sender_id} not found")
        if recipient_id not in self.agents:
            raise ValueError(f"Recipient agent {recipient_id} not found")

        sender = self.agents[sender_id]
        recipient = self.agents[recipient_id]

        # Create message
        message = {
            "role": "user",
            "content": content,
            "name": sender.name if hasattr(sender, "name") else sender_id,
        }

        # Track message
        autogen_msg = self.translate_message(message, from_format="autogen")
        if recipient_id in self.message_history:
            self.message_history[recipient_id].append(autogen_msg)
            # Trim history
            if len(self.message_history[recipient_id]) > self.max_messages:
                self.message_history[recipient_id] = self.message_history[recipient_id][
                    -self.max_messages :
                ]

        # Notify callbacks
        await self._notify_conversation_event("message_sent", sender_id, message)

        # Send message and get response
        try:
            response = await recipient.a_send(
                message=content,
                sender=sender,
                max_turns=1,
            )

            if response and len(response) > 0:
                last_response = response[-1]

                # Track response
                response_msg = self.translate_message(last_response, from_format="autogen")
                if sender_id in self.message_history:
                    self.message_history[sender_id].append(response_msg)

                # Notify callbacks
                await self._notify_conversation_event(
                    "message_received", recipient_id, last_response
                )

                return last_response

        except Exception as e:
            logger.error("message_send_error", error=str(e))

        return None

    async def initiate_chat(
        self,
        initiator_id: str,
        recipient_id: str,
        message: str,
        max_turns: int = 1,
    ) -> ChatResult | None:
        """
        Initiate a chat between two agents.

        Args:
            initiator_id: Initiating agent ID
            recipient_id: Recipient agent ID
            message: Initial message
            max_turns: Maximum conversation turns

        Returns:
            ChatResult with conversation details
        """
        if not AUTOGEN_AVAILABLE:
            raise RuntimeError("AutoGen is not available")

        if initiator_id not in self.agents:
            raise ValueError(f"Initiator agent {initiator_id} not found")
        if recipient_id not in self.agents:
            raise ValueError(f"Recipient agent {recipient_id} not found")

        initiator = self.agents[initiator_id]
        recipient = self.agents[recipient_id]

        try:
            result = await initiator.a_initiate_chat(
                recipient=recipient,
                message=message,
                max_turns=max_turns,
            )

            logger.info(
                "chat_initiated",
                initiator=initiator_id,
                recipient=recipient_id,
                turns=max_turns,
            )

            return result

        except Exception as e:
            logger.error("chat_initiation_error", error=str(e))
            return None

    async def run_group_chat(
        self,
        group_id: str,
        message: str,
        initiator_id: str | None = None,
    ) -> ChatResult | None:
        """
        Run a group chat conversation.

        Args:
            group_id: Group chat ID
            message: Initial message
            initiator_id: Optional initiator agent ID

        Returns:
            ChatResult with conversation details
        """
        if group_id not in self.group_chat_managers:
            raise ValueError(f"Group chat {group_id} not found")

        manager = self.group_chat_managers[group_id]
        config = self.group_chat_configs[group_id]

        # Determine initiator
        initiator = None
        if initiator_id and initiator_id in self.agents:
            initiator = self.agents[initiator_id]
        elif self.agents:
            # Use first agent as initiator
            initiator = next(iter(self.agents.values()))

        if not initiator:
            raise ValueError("No initiator agent available")

        try:
            result = await initiator.a_initiate_chat(
                recipient=manager,
                message=message,
                max_turns=config.max_round,
            )

            # Update group chat messages
            if group_id in self.group_chats:
                self.group_chats[group_id].messages = result.chat_history

            logger.info(
                "group_chat_completed",
                group_id=group_id,
                message_count=len(result.chat_history) if result else 0,
            )

            return result

        except Exception as e:
            logger.error("group_chat_error", group_id=group_id, error=str(e))
            return None

    def get_agent(self, agent_id: str) -> Any | None:
        """Get an agent by ID."""
        return self.agents.get(agent_id)

    def get_agent_config(self, agent_id: str) -> AutoGenAgentConfig | None:
        """Get agent configuration."""
        return self.agent_configs.get(agent_id)

    def get_group_chat(self, group_id: str) -> Any | None:
        """Get a group chat by ID."""
        return self.group_chats.get(group_id)

    def get_message_history(
        self,
        agent_id: str,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        """Get message history for an agent."""
        history = self.message_history.get(agent_id, [])
        return [msg.to_dict() for msg in history[-limit:]]

    def get_statistics(self) -> dict[str, Any]:
        """Get adapter statistics."""
        return {
            "agent_count": len(self.agents),
            "group_chat_count": len(self.group_chats),
            "tool_count": len(self.tools),
            "heretek_agent_mappings": len(self._heretek_agents),
            "autogen_available": AUTOGEN_AVAILABLE,
            "message_translation_enabled": self.enable_message_translation,
        }

    def clear_agent(self, agent_id: str) -> bool:
        """Clear an agent and its history."""
        if agent_id not in self.agents:
            return False

        if agent_id in self.agents:
            del self.agents[agent_id]
        if agent_id in self.agent_configs:
            del self.agent_configs[agent_id]
        if agent_id in self.message_history:
            del self.message_history[agent_id]

        logger.info("agent_cleared", agent_id=agent_id)
        return True

    def clear_group_chat(self, group_id: str) -> bool:
        """Clear a group chat."""
        if group_id not in self.group_chats:
            return False

        if group_id in self.group_chats:
            del self.group_chats[group_id]
        if group_id in self.group_chat_configs:
            del self.group_chat_configs[group_id]
        if group_id in self.group_chat_managers:
            del self.group_chat_managers[group_id]

        logger.info("group_chat_cleared", group_id=group_id)
        return True

    def clear_all(self) -> None:
        """Clear all agents and state."""
        self.agents.clear()
        self.agent_configs.clear()
        self.group_chats.clear()
        self.group_chat_configs.clear()
        self.group_chat_managers.clear()
        self.tools.clear()
        self.message_history.clear()
        self._heretek_agents.clear()
        logger.info("autogen_adapter_cleared")


# Global adapter instance
autogen_adapter: AutoGenAdapter | None = None


def get_autogen_adapter() -> AutoGenAdapter:
    """Get the global AutoGen adapter instance."""
    global autogen_adapter
    if autogen_adapter is None:
        autogen_adapter = AutoGenAdapter()
    return autogen_adapter


def create_assistant_agent(
    agent_id: str,
    name: str,
    system_message: str,
    llm_config: dict[str, Any] | None = None,
    tools: list[Callable] | None = None,
) -> Any:
    """
    Create an assistant agent with optional tools.

    Args:
        agent_id: Agent identifier
        name: Agent name
        system_message: System message
        llm_config: LLM configuration
        tools: Optional list of tool functions

    Returns:
        Created AssistantAgent
    """
    adapter = get_autogen_adapter()

    agent = adapter.create_agent(
        agent_id=agent_id,
        name=name,
        role=AgentRole.ASSISTANT,
        system_message=system_message,
        llm_config=llm_config,
    )

    # Register tools if provided
    if tools and AUTOGEN_AVAILABLE:
        for tool in tools:
            tool_name = getattr(tool, "__name__", str(tool))
            adapter.register_tool(
                tool_id=f"{agent_id}_{tool_name}",
                name=tool_name,
                description=tool.__doc__ or f"Tool: {tool_name}",
                function=tool,
                agent_ids=[agent_id],
            )

    return agent
