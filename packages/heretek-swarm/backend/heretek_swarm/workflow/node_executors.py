"""
Node Executors — Specialized async functions for executing workflow node types.

Extracted from workflow/engine.py to keep the engine under 800 lines.
Each function receives the engine instance as its first parameter (replacing
``self``) and follows the same signature pattern:
    (engine, node, input_data, context) -> Any
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

import structlog

from heretek_swarm.workflow.models import NodeStatus

if TYPE_CHECKING:
    from heretek_swarm.workflow.engine import WorkflowEngine
    from heretek_swarm.workflow.models import WorkflowContext, WorkflowNode

logger = structlog.get_logger(__name__)


# ---------------------------------------------------------------------------
# Agent node
# ---------------------------------------------------------------------------


async def execute_agent_node(
    engine: WorkflowEngine,
    node: WorkflowNode,
    input_data: dict[str, Any],
    context: WorkflowContext,
) -> Any:
    """Execute an agent node.

    Looks up the actor from the supervisor's actor registry and calls
    run_with_llm() with the prompt from input_data.

    Raises:
        ValueError: If agent_id is missing from node.data
        RuntimeError: If the agent is not found or not active
    """
    from heretek_swarm.actors.supervisor import get_supervisor

    agent_id = node.data.get("agent_id")
    if not agent_id:
        raise ValueError("Agent node requires agent_id")

    supervisor = engine._supervisor or get_supervisor()

    actor = supervisor.actors.get(agent_id)
    if actor is None:
        raise RuntimeError(f"Agent not found: {agent_id}")

    agent_status = await supervisor.get_actor_status(agent_id)
    if not agent_status or agent_status.state != "active":
        raise RuntimeError(f"Agent not active: {agent_id}")

    prompt = (
        input_data.get("prompt")
        or input_data.get("message")
        or input_data.get(agent_id)
        or context.variables.get("prompt")
        or context.variables.get("message")
    )
    if not prompt:
        for key, val in context.variables.items():
            if key.startswith("node_") and key.endswith("_output") and isinstance(val, str):
                prompt = val
                break
    if not prompt:
        raise ValueError("Agent node requires a prompt or message in input_data")

    timeout = node.data.get("timeout", 60)

    logger.info(
        "agent_node_started",
        workflow_id=context.workflow_id,
        node_id=node.id,
        agent_id=agent_id,
        prompt_length=len(prompt),
    )

    return await actor.run_with_llm(prompt, timeout=timeout)


# ---------------------------------------------------------------------------
# LLM node
# ---------------------------------------------------------------------------


async def execute_llm_node(
    engine: WorkflowEngine,
    node: WorkflowNode,
    input_data: dict[str, Any],
    context: WorkflowContext,
) -> str:
    """Execute a standalone LLM node.

    Runs a prompt through the LLM without requiring a pre-spawned actor.
    Uses the supervisor's first available active actor as the LLM conduit,
    or raises if none are available.

    Raises:
        ValueError: If no prompt is provided
        RuntimeError: If no active actor is available
    """
    from heretek_swarm.actors.supervisor import get_supervisor

    prompt = node.data.get("prompt") or input_data.get("prompt") or input_data.get("message", "")
    if not prompt:
        raise ValueError("LLM node requires a 'prompt' in node.data or input_data")

    timeout = node.data.get("timeout", 60)
    temperature = node.data.get("temperature")

    supervisor = engine._supervisor or get_supervisor()

    actor = None
    for actor_id, candidate in supervisor.actors.items():
        status = await supervisor.get_actor_status(actor_id)
        if status and status.state == "active":
            actor = candidate
            break

    if actor is None:
        raise RuntimeError(
            "LLM node requires at least one active actor in the supervisor "
            "to serve as an LLM conduit."
        )

    logger.info(
        "llm_node_started",
        workflow_id=context.workflow_id,
        node_id=node.id,
        actor_id=actor.agent_id,
        prompt_length=len(prompt),
        temperature=temperature,
    )

    kwargs: dict[str, Any] = {}
    if temperature is not None:
        kwargs["temperature"] = temperature

    return await actor.run_with_llm(prompt, timeout=timeout, **kwargs)


# ---------------------------------------------------------------------------
# Tool node
# ---------------------------------------------------------------------------


async def execute_tool_node(
    engine: WorkflowEngine,
    node: WorkflowNode,
    input_data: dict[str, Any],
    context: WorkflowContext,
) -> Any:
    """Execute a tool node."""
    from heretek_swarm.runtime.tools import ToolRegistry

    tool_registry = ToolRegistry()
    tool_name = node.data.get("tool_name")
    if not tool_name:
        raise ValueError("Tool node requires tool_name")

    tool_params = input_data.get("params", {})
    return await tool_registry.execute(tool_name, **tool_params)


# ---------------------------------------------------------------------------
# Chain node
# ---------------------------------------------------------------------------


async def execute_chain_node(
    engine: WorkflowEngine,
    node: WorkflowNode,
    input_data: dict[str, Any],
    context: WorkflowContext,
) -> Any:
    """Execute a chain node (sequential processing)."""
    chain_nodes = node.data.get("nodes", [])
    if not chain_nodes:
        raise ValueError("Chain node requires nodes")

    output = input_data.get("input", "")
    for chain_node_id in chain_nodes:
        if chain_node_id in context.node_results:
            node_result = context.node_results[chain_node_id]
            if node_result.status == NodeStatus.COMPLETED:
                output = node_result.output
            else:
                raise RuntimeError(f"Chain node not completed: {chain_node_id}")

    return output


# ---------------------------------------------------------------------------
# Memory node
# ---------------------------------------------------------------------------


async def execute_memory_node(
    engine: WorkflowEngine,
    node: WorkflowNode,
    input_data: dict[str, Any],
    context: WorkflowContext,
) -> Any:
    """Execute a memory node (store or retrieve)."""
    from heretek_swarm_core.memory.cognee_reader import CogneeMemoryReader
    from heretek_swarm_core.memory.cognee_writer import CogneeMemoryWriter

    operation = node.data.get("operation", "store")
    if operation not in ["store", "retrieve", "search"]:
        raise ValueError(f"Invalid memory operation: {operation}")

    if operation == "store":
        content = input_data.get("content", "")
        dataset = input_data.get("dataset", "default")

        writer = CogneeMemoryWriter()
        await writer.store(content=content, dataset=dataset)
        return {"stored": True}

    if operation == "retrieve":
        query = input_data.get("query", "")
        limit = input_data.get("limit", 10)

        reader = CogneeMemoryReader()
        results = await reader.read(query=query, top_k=limit)
        return {"results": results}

    if operation == "search":
        return await execute_memory_node(engine, node, input_data, context)
    return None


# ---------------------------------------------------------------------------
# Consensus node
# ---------------------------------------------------------------------------


async def execute_consensus_node(
    engine: WorkflowEngine,
    node: WorkflowNode,
    input_data: dict[str, Any],
    context: WorkflowContext,
) -> dict[str, Any]:
    """Execute a consensus node (MAKER voting as a workflow step).

    Uses ConsensusCoordinator.run_consensus() to execute multi-agent
    voting on a question derived from node configuration or upstream outputs.

    Raises:
        ValueError: If no question is provided
        RuntimeError: If consensus_coordinator is not configured
    """
    if engine._consensus_coordinator is None:
        raise RuntimeError(
            "Consensus node requires a ConsensusCoordinator. "
            "Pass consensus_coordinator to WorkflowEngine constructor."
        )

    question = node.data.get("question") or input_data.get("question")
    if not question:
        raise ValueError("Consensus node requires a 'question' in node.data or input_data.")

    timeout = node.data.get("timeout", 120)
    max_rounds = node.data.get("max_rounds", 1)

    logger.info(
        "consensus_node_started",
        workflow_id=context.workflow_id,
        node_id=node.id,
        question=question[:200],
        timeout=timeout,
        max_rounds=max_rounds,
    )

    try:
        result = await engine._consensus_coordinator.run_consensus(
            question=question,
            timeout=timeout,
            max_rounds=max_rounds,
        )

        if result is None:
            logger.warning(
                "consensus_node_completed",
                workflow_id=context.workflow_id,
                node_id=node.id,
                consensus_reached=False,
            )
            return {
                "consensus_reached": False,
                "decision": None,
                "confidence": 0.0,
                "votes": [],
                "red_flags": [],
            }

        result_dict = {
            "consensus_reached": True,
            "decision": result.decision,
            "confidence": result.confidence,
            "votes": [
                {
                    "agent_id": v.agent_id,
                    "decision": v.decision,
                    "confidence": v.confidence,
                    "metadata": v.metadata,
                }
                for v in result.votes
            ],
            "red_flags": result.red_flags,
            "metadata": result.metadata,
        }

        logger.info(
            "consensus_node_completed",
            workflow_id=context.workflow_id,
            node_id=node.id,
            consensus_reached=True,
            decision=result.decision,
            confidence=result.confidence,
            vote_count=len(result.votes),
        )

        return result_dict

    except Exception as exc:
        logger.error(
            "consensus_node_failed",
            workflow_id=context.workflow_id,
            node_id=node.id,
            error=str(exc)[:200],
        )
        raise


# ---------------------------------------------------------------------------
# Execute-and-capture (used by strategies)
# ---------------------------------------------------------------------------


async def execute_and_capture(
    engine: WorkflowEngine,
    workflow: Any,
    node_id: str,
    context: WorkflowContext,
    node: WorkflowNode,
) -> Any:
    """Execute a node and capture the result.

    Used by strategy wrappers to capture results without writing to context.
    Returns the output directly for strategy aggregation.
    """
    input_data = engine._get_node_input(workflow, node, context)
    datetime.now(UTC)  # no-op: intentional timestamp placeholder

    try:
        if node.type == "agent":
            return await execute_agent_node(engine, node, input_data, context)
        if node.type == "tool":
            return await execute_tool_node(engine, node, input_data, context)
        if node.type == "chain":
            return await execute_chain_node(engine, node, input_data, context)
        if node.type == "memory":
            return await execute_memory_node(engine, node, input_data, context)
        if node.type == "consensus":
            return await execute_consensus_node(engine, node, input_data, context)
        if node.type == "llm":
            return await execute_llm_node(engine, node, input_data, context)
        return {"error": f"Unknown node type: {node.type}"}
    except Exception as e:
        logger.error("node_execution_failed", node_id=node_id, error=str(e))
        return {"error": str(e)}
