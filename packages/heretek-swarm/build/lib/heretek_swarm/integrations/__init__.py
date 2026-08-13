"""
Integration Modules for Heretek Swarm

This package provides comprehensive integration capabilities for the heretek-swarm collective,
enabling seamless integration with external AI platforms, communication channels, and
orchestration frameworks.

Available Integrations:
- LangGraph: Graph-based workflow orchestration
- AutoGen: Microsoft AutoGen agent compatibility
- CrewAI: Crew task delegation and role mapping
- OpenAI Assistants: OpenAI Assistants API integration
- Anthropic Claude: Anthropic Messages API integration
- Discord/Slack/Telegram: Communication platform bots
- Praison: PraisonAI handoff patterns

Example Usage:
    ```python
    from heretek_swarm.integrations import (
        get_langgraph_adapter,
        get_autogen_adapter,
        get_crewai_adapter,
        get_openai_assistants_adapter,
        get_anthropic_adapter,
        get_integration_manager,
        IntegrationManager,
        IntegrationType,
    )

    # Get adapters
    langgraph = get_langgraph_adapter()
    autogen = get_autogen_adapter()
    crewai = get_crewai_adapter()
    openai = get_openai_assistants_adapter(api_key="your-key")
    anthropic = get_anthropic_adapter(api_key="your-key")

    # Use integration manager
    manager = get_integration_manager()
    await manager.register_integration(
        integration_id="my_langgraph",
        integration_type=IntegrationType.LANGGRAPH,
        name="My LangGraph Workflow",
    )
    await manager.start()
    ```

Reference: EXPANSION_ROADMAP.md Session 47 - Integration Ecosystem
"""

import structlog

from .anthropic import (
    ANTHROPIC_AVAILABLE,
    AnthropicAdapter,
    AnthropicMessageRole,
    ConversationContext,
    ConversationMessage,
    StopReason,
    ToolDefinition,
    ToolUseRequest,
    create_conversation,
    get_anthropic_adapter,
)
from .autogen import (
    AUTOGEN_AVAILABLE,
    AutoGenAdapter,
    AutoGenAgentConfig,
    AutoGenMessage,
    GroupChatConfig,
    ToolRegistration,
    create_assistant_agent,
    get_autogen_adapter,
)
from .autogen import (
    AgentRole as AutoGenAgentRole,
)
from .autogen import (
    MessageRole as AutoGenMessageRole,
)
from .crewai import (
    CREWAI_AVAILABLE,
    CrewAgentConfig,
    CrewAIAdapter,
    CrewExecutionResult,
    CrewProcess,
    CrewTaskConfig,
    TaskExecutionResult,
    TaskStatus,
    create_sequential_crew,
    get_crewai_adapter,
)
from .crewai import (
    AgentRole as CrewAIAgentRole,
)
from .langgraph import (
    LANGGRAPH_AVAILABLE,
    GraphCheckpoint,
    GraphEdge,
    GraphExecutionResult,
    GraphNode,
    GraphState,
    LangGraphAdapter,
    NodeStatus,
    create_workflow_graph,
    get_langgraph_adapter,
)
from .manager import (
    HealthCheckResult,
    HealthStatus,
    IntegrationConfig,
    IntegrationEvent,
    IntegrationManager,
    IntegrationState,
    IntegrationStatus,
    IntegrationType,
    get_integration_manager,
    initialize_integrations,
)
from .openai_assistants import (
    OPENAI_AVAILABLE,
    AssistantConfig,
    FunctionCallRequest,
    OpenAIAssistantsAdapter,
    RunContext,
    RunStatus,
    ThreadContext,
    create_assistant,
    get_openai_assistants_adapter,
)
from .openai_assistants import (
    MessageRole as OpenAIMessageRole,
)

logger = structlog.get_logger(__name__)

__all__ = [
    "ANTHROPIC_AVAILABLE",
    "AUTOGEN_AVAILABLE",
    "CREWAI_AVAILABLE",
    # Legacy integrations
    "LANGGRAPH_AVAILABLE",
    "OPENAI_AVAILABLE",
    # Anthropic
    "AnthropicAdapter",
    "AnthropicMessageRole",
    "AssistantConfig",
    # AutoGen
    "AutoGenAdapter",
    "AutoGenAgentConfig",
    "AutoGenAgentRole",
    "AutoGenMessage",
    "AutoGenMessageRole",
    "ConversationContext",
    "ConversationMessage",
    # CrewAI
    "CrewAIAdapter",
    "CrewAIAgentRole",
    "CrewAgentConfig",
    "CrewExecutionResult",
    "CrewProcess",
    "CrewTaskConfig",
    "FunctionCallRequest",
    "GraphCheckpoint",
    "GraphEdge",
    "GraphExecutionResult",
    "GraphNode",
    "GraphState",
    "GroupChatConfig",
    "HealthCheckResult",
    "HealthStatus",
    "IntegrationConfig",
    "IntegrationEvent",
    # Integration Manager
    "IntegrationManager",
    "IntegrationState",
    "IntegrationStatus",
    "IntegrationType",
    # LangGraph
    "LangGraphAdapter",
    "NodeStatus",
    # OpenAI Assistants
    "OpenAIAssistantsAdapter",
    "OpenAIMessageRole",
    "RunContext",
    "RunStatus",
    "StopReason",
    "TaskExecutionResult",
    "TaskStatus",
    "ThreadContext",
    "ToolDefinition",
    "ToolRegistration",
    "ToolUseRequest",
    "create_assistant",
    "create_assistant_agent",
    "create_conversation",
    "create_sequential_crew",
    "create_workflow_graph",
    "get_anthropic_adapter",
    "get_autogen_adapter",
    "get_crewai_adapter",
    "get_integration_manager",
    "get_langgraph_adapter",
    "get_openai_assistants_adapter",
    "initialize_integrations",
]

# Package version
__version__ = "0.2.0"

# Integration ecosystem version
INTEGRATION_ECOSYSTEM_VERSION = "47.0.0"
