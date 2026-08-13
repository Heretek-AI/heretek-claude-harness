"""Pydantic-AI agent factory for the actor-model fallback LLM path.

Replaces ``backend/heretek_swarm/agents/agent_factory.py`` (which built
``swarms.Agent`` instances) with a pydantic-ai-backed implementation. Each
actor that previously got a ``swarms.Agent`` now gets a pydantic-ai
``Agent`` with MCP tools wired in as native Python functions.

The actor contract is unchanged: ``actor.pydantic_ai_agent`` exposes a
``.run(prompt) -> str`` method that ``actors/base/message_handling.py``
falls back to when ``ModelGarage`` is unavailable (e.g. ``--no-infra``
mode).

Env vars (read inside the function so module import stays fast):
- ``OPENAI_API_KEY`` (required)
- ``OPENAI_BASE_URL`` (optional, default OpenAI)
- ``LLM_MODEL`` (optional, default ``gpt-4.1``)
"""

from __future__ import annotations

import os
from typing import TYPE_CHECKING, Any

import structlog
from pydantic_ai import Agent
from pydantic_ai.models.openai import OpenAIChatModel
from pydantic_ai.providers.openai import OpenAIProvider

if TYPE_CHECKING:
    from heretek_swarm.tools.mcp_tools import MCPToolRegistry

logger = structlog.get_logger("pydantic_ai_agent_factory")


def _ensure_provider_prefix(model: str) -> str:
    """Prefix the model name with the OpenAI provider id if missing.

    Pydantic-AI expects model names in the form ``"<provider>:<model>"``
    when a custom OpenAI-compatible base URL is used. We treat any model
    name without a colon as an OpenAI model id (preserving the
    ``swarms``-era behaviour).
    """
    return model if ":" in model else f"openai:{model}"


def build_pydantic_ai_agent_for(
    agent_id: str,
    agent_class_name: str,
    system_prompt: str | None = None,
    mcp_registry: "MCPToolRegistry | None" = None,
) -> Agent:
    """Construct a pydantic-ai ``Agent`` configured from environment variables.

    If ``mcp_registry`` is provided, every tool it exposes is registered
    on the agent as a native Python tool (via ``@agent.tool_plain``).

    Parameters
    ----------
    agent_id : str
        Unique identifier for this agent instance. Recorded in logs.
    agent_class_name : str
        Human-readable class / type label (e.g. ``"AlphaAgent"``).
    system_prompt : str or None
        Optional system prompt. Pydantic-AI defaults to no prompt when
        ``None`` (the tool-only / empty-prompt case).
    mcp_registry : MCPToolRegistry or None
        Optional MCP tool registry. When supplied, every tool in the
        registry is registered on the agent.

    Returns
    -------
    pydantic_ai.Agent
        A fully configured pydantic-ai Agent instance.

    Raises
    ------
    ValueError
        If ``OPENAI_API_KEY`` is not set in the environment.
    """
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        raise ValueError(
            "OPENAI_API_KEY environment variable is not set. "
            "Pydantic-AI agent construction requires a valid "
            "OpenAI-compatible API key."
        )

    base_url = os.environ.get("OPENAI_BASE_URL", "https://api.openai.com/v1")
    model = _ensure_provider_prefix(os.environ.get("LLM_MODEL", "gpt-4.1"))

    provider = OpenAIProvider(base_url=base_url, api_key=api_key)
    model_obj = OpenAIChatModel(model, provider=provider)

    agent = Agent(model_obj, system_prompt=system_prompt or "")

    if mcp_registry is not None:
        _register_mcp_tools(agent, mcp_registry, agent_id=agent_id)

    logger.info(
        "pydantic_ai_agent_built",
        agent_id=agent_id,
        agent_class=agent_class_name,
        model=model,
        base_url=base_url,
    )
    return agent


def _register_mcp_tools(
    agent: Agent,
    registry: "MCPToolRegistry",
    *,
    agent_id: str,
) -> int:
    """Register every tool in *registry* as a native pydantic-ai tool."""
    import asyncio

    count = 0
    for tool_dict in registry.list_tools(category=None):
        name = tool_dict.get("name", "")
        if not name:
            continue
        tool_def = registry.get_tool(name)
        if tool_def is None:
            logger.warning(
                "pydantic_ai_tool_def_not_found", agent_id=agent_id, tool_name=name
            )
            continue
        original_handler = tool_def.handler

        def _make_tool_handler(handler):
            def _sync_tool(*args: Any, **kwargs: Any) -> Any:
                candidate = handler(kwargs or {}, None)
                if asyncio.iscoroutine(candidate):
                    return asyncio.run(candidate)
                return candidate

            return _sync_tool

        agent.tool_plain(_make_tool_handler(original_handler), name=name)
        count += 1
    logger.info(
        "pydantic_ai_tools_registered", agent_id=agent_id, count=count
    )
    return count