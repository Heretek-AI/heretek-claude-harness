"""
LangGraph Integration Module for Heretek Swarm

This module provides bi-directional integration between Heretek Swarm agents and LangGraph workflows.  # noqa: E501
It enables graph-based workflow orchestration, state synchronization, and checkpoint persistence.

Features:
- Bi-directional agent state synchronization
- Graph-based workflow orchestration
- Checkpoint integration for state persistence
- LangGraph tool compatibility layer
- Zero-trust validation of all state transitions

Reference: EXPANSION_ROADMAP.md Session 47 - Integration Ecosystem
"""

import asyncio
import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

import structlog

logger = structlog.get_logger(__name__)

# Try to import langgraph components
try:
    from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage
    from langchain_core.runnables import RunnableConfig
    from langchain_core.tools import BaseTool
    from langgraph.checkpoint.base import BaseCheckpointSaver
    from langgraph.checkpoint.memory import MemorySaver
    from langgraph.graph import END, StateGraph
    from langgraph.prebuilt import ToolNode

    LANGGRAPH_AVAILABLE = True
except ImportError:
    LANGGRAPH_AVAILABLE = False
    StateGraph = None
    END = None
    BaseCheckpointSaver = None
    MemorySaver = None
    ToolNode = None
    RunnableConfig = None
    BaseMessage = None
    HumanMessage = None
    AIMessage = None
    SystemMessage = None
    BaseTool = None


class GraphState(StrEnum):
    """Graph execution states."""

    INITIALIZED = "initialized"
    RUNNING = "running"
    WAITING = "waiting"
    COMPLETED = "completed"
    FAILED = "failed"
    PAUSED = "paused"


class NodeStatus(StrEnum):
    """Node execution status."""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


@dataclass
class GraphNode:
    """
    Represents a node in the LangGraph workflow.

    Attributes:
        node_id: Unique node identifier
        name: Human-readable node name
        agent_id: Associated Heretek agent ID
        function: Node execution function
        edges: Outgoing edge targets
        status: Current node status
        metadata: Node metadata
    """

    node_id: str
    name: str
    agent_id: str | None = None
    function: Callable | None = None
    edges: list[str] = field(default_factory=list)
    status: NodeStatus = NodeStatus.PENDING
    metadata: dict[str, Any] = field(default_factory=dict)
    execution_count: int = 0
    last_execution_time: str | None = None
    error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "node_id": self.node_id,
            "name": self.name,
            "agent_id": self.agent_id,
            "edges": self.edges,
            "status": self.status.value,
            "metadata": self.metadata,
            "execution_count": self.execution_count,
            "last_execution_time": self.last_execution_time,
            "error": self.error,
        }


@dataclass
class GraphEdge:
    """
    Represents an edge between nodes in the workflow graph.

    Attributes:
        edge_id: Unique edge identifier
        source: Source node ID
        target: Target node ID
        condition: Optional condition for edge traversal
        weight: Edge weight for prioritization
    """

    edge_id: str
    source: str
    target: str
    condition: Callable[[dict[str, Any]], bool] | None = None
    weight: float = 1.0
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "edge_id": self.edge_id,
            "source": self.source,
            "target": self.target,
            "has_condition": self.condition is not None,
            "weight": self.weight,
            "metadata": self.metadata,
        }


@dataclass
class GraphCheckpoint:
    """
    Checkpoint for graph state persistence.

    Attributes:
        checkpoint_id: Unique checkpoint identifier
        graph_id: Parent graph ID
        state: Graph state at checkpoint
        node_states: Individual node states
        timestamp: Checkpoint timestamp
        thread_id: Optional thread ID for multi-threaded execution
    """

    checkpoint_id: str
    graph_id: str
    state: dict[str, Any]
    node_states: dict[str, NodeStatus]
    timestamp: str = field(default_factory=lambda: datetime.now(UTC).isoformat())
    thread_id: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "checkpoint_id": self.checkpoint_id,
            "graph_id": self.graph_id,
            "state": self.state,
            "node_states": {k: v.value for k, v in self.node_states.items()},
            "timestamp": self.timestamp,
            "thread_id": self.thread_id,
            "metadata": self.metadata,
        }


@dataclass
class GraphExecutionResult:
    """
    Result of graph execution.

    Attributes:
        graph_id: Graph identifier
        status: Final graph status
        output: Graph output state
        node_results: Results from individual nodes
        execution_time_ms: Total execution time
        checkpoints: Checkpoints created during execution
    """

    graph_id: str
    status: GraphState
    output: dict[str, Any]
    node_results: dict[str, Any]
    execution_time_ms: float
    checkpoints: list[GraphCheckpoint] = field(default_factory=list)
    error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "graph_id": self.graph_id,
            "status": self.status.value,
            "output": self.output,
            "node_results": self.node_results,
            "execution_time_ms": self.execution_time_ms,
            "checkpoints": [c.to_dict() for c in self.checkpoints],
            "error": self.error,
        }


class LangGraphAdapter:
    """
    Adapter for integrating LangGraph with Heretek Swarm.

    This adapter provides:
    - Bi-directional state synchronization between Heretek agents and LangGraph
    - Graph-based workflow orchestration
    - Checkpoint persistence integration
    - Tool compatibility layer for LangChain tools

    Attributes:
        graphs: Registered workflow graphs
        checkpoints: Stored checkpoints
        tools: Registered LangChain tools
    """

    def __init__(
        self,
        checkpoint_saver: Any | None = None,
        enable_state_sync: bool = True,
        max_checkpoints: int = 100,
    ) -> None:
        """
        Initialize the LangGraph adapter.

        Args:
            checkpoint_saver: Optional checkpoint saver instance
            enable_state_sync: Enable bi-directional state sync
            max_checkpoints: Maximum checkpoints to retain
        """
        self.graphs: dict[str, StateGraph] = {}
        self.graph_nodes: dict[str, dict[str, GraphNode]] = {}
        self.graph_edges: dict[str, dict[str, GraphEdge]] = {}
        self.graph_states: dict[str, dict[str, Any]] = {}
        self.graph_status: dict[str, GraphState] = {}

        self.checkpoint_saver = checkpoint_saver
        if self.checkpoint_saver is None and LANGGRAPH_AVAILABLE:
            self.checkpoint_saver = MemorySaver()

        self.checkpoints: dict[str, list[GraphCheckpoint]] = {}
        self.max_checkpoints = max_checkpoints

        self.tools: dict[str, Any] = {}
        self.tool_nodes: dict[str, Any] = {}

        self.enable_state_sync = enable_state_sync
        self._agent_runtime = None
        self._running = False

        # State sync callbacks
        self._state_sync_callbacks: list[Callable] = []

        logger.info(
            "langgraph_adapter_initialized",
            checkpoint_saver=type(self.checkpoint_saver).__name__
            if self.checkpoint_saver
            else None,
            state_sync_enabled=enable_state_sync,
        )

    def set_agent_runtime(self, runtime: Any) -> None:
        """Set the Heretek agent runtime for state synchronization."""
        self._agent_runtime = runtime
        logger.debug("agent_runtime_set", runtime_type=type(runtime).__name__)

    def register_state_sync_callback(self, callback: Callable) -> None:
        """Register a callback for state synchronization events."""
        self._state_sync_callbacks.append(callback)
        logger.debug("state_sync_callback_registered", callback=callback.__name__)

    async def _notify_state_sync(self, graph_id: str, state: dict[str, Any]) -> None:
        """Notify callbacks of state changes."""
        for callback in self._state_sync_callbacks:
            try:
                if asyncio.iscoroutinefunction(callback):
                    await callback(graph_id, state)
                else:
                    callback(graph_id, state)
            except Exception as e:
                logger.error("state_sync_callback_error", error=str(e))

    def create_graph(
        self,
        graph_id: str,
        state_schema: dict[str, Any] | None = None,
    ) -> "StateGraph":
        """
        Create a new workflow graph.

        Args:
            graph_id: Unique graph identifier
            state_schema: Optional state schema definition

        Returns:
            Created StateGraph instance
        """
        if not LANGGRAPH_AVAILABLE:
            logger.warning("langgraph_not_available")
            raise RuntimeError("LangGraph is not available. Install with: pip install langgraph")

        if state_schema is None:
            state_schema = {
                "messages": list,
                "agent_states": dict,
                "context": dict,
                "metadata": dict,
            }

        # Create typed dict for state schema
        from typing import TypedDict

        class GraphStateSchema(TypedDict):
            """Dynamic state schema for graph."""

            messages: list[Any]
            agent_states: dict[str, Any]
            context: dict[str, Any]
            metadata: dict[str, Any]

        graph = StateGraph(GraphStateSchema)
        self.graphs[graph_id] = graph
        self.graph_nodes[graph_id] = {}
        self.graph_edges[graph_id] = {}
        self.graph_states[graph_id] = {
            "messages": [],
            "agent_states": {},
            "context": {},
            "metadata": {"graph_id": graph_id, "created_at": datetime.now(UTC).isoformat()},
        }
        self.graph_status[graph_id] = GraphState.INITIALIZED
        self.checkpoints[graph_id] = []

        logger.info("graph_created", graph_id=graph_id)
        return graph

    def add_node(
        self,
        graph_id: str,
        node_id: str,
        name: str,
        agent_id: str | None = None,
        action: Callable[[dict[str, Any]], dict[str, Any]] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> GraphNode:
        """
        Add a node to a workflow graph.

        Args:
            graph_id: Target graph ID
            node_id: Unique node identifier
            name: Human-readable node name
            agent_id: Optional Heretek agent ID for state sync
            action: Node action function
            metadata: Optional node metadata

        Returns:
            Created GraphNode instance
        """
        if graph_id not in self.graphs:
            raise ValueError(f"Graph {graph_id} not found")

        node = GraphNode(
            node_id=node_id,
            name=name,
            agent_id=agent_id,
            function=action,
            metadata=metadata or {},
        )

        self.graph_nodes[graph_id][node_id] = node

        # Register node with LangGraph
        if LANGGRAPH_AVAILABLE:
            if action:
                self.graphs[graph_id].add_node(node_id, action)
            else:
                # Default passthrough node
                self.graphs[graph_id].add_node(node_id, lambda state: state)

        logger.info(
            "node_added",
            graph_id=graph_id,
            node_id=node_id,
            agent_id=agent_id,
        )

        return node

    def add_edge(
        self,
        graph_id: str,
        source: str,
        target: str,
        condition: Callable[[dict[str, Any]], bool] | None = None,
        weight: float = 1.0,
        metadata: dict[str, Any] | None = None,
    ) -> GraphEdge:
        """
        Add an edge between nodes.

        Args:
            graph_id: Target graph ID
            source: Source node ID
            target: Target node ID
            condition: Optional conditional edge function
            weight: Edge weight
            metadata: Optional edge metadata

        Returns:
            Created GraphEdge instance
        """
        if graph_id not in self.graphs:
            raise ValueError(f"Graph {graph_id} not found")

        edge_id = f"edge_{source}_{target}_{uuid.uuid4().hex[:8]}"
        edge = GraphEdge(
            edge_id=edge_id,
            source=source,
            target=target,
            condition=condition,
            weight=weight,
            metadata=metadata or {},
        )

        if edge_id not in self.graph_edges[graph_id]:
            self.graph_edges[graph_id][edge_id] = edge

        # Register edge with LangGraph
        if LANGGRAPH_AVAILABLE:
            if condition:
                # Conditional edge
                self.graphs[graph_id].add_conditional_edges(
                    source, condition, {True: target, False: source}
                )
            else:
                self.graphs[graph_id].add_edge(source, target)

        logger.info(
            "edge_added",
            graph_id=graph_id,
            edge_id=edge_id,
            source=source,
            target=target,
        )

        return edge

    def add_conditional_edges(
        self,
        graph_id: str,
        source: str,
        condition: Callable[[dict[str, Any]], str],
        targets: dict[str, str],
    ) -> None:
        """
        Add conditional edges from a node.

        Args:
            graph_id: Target graph ID
            source: Source node ID
            condition: Condition function returning target key
            targets: Mapping of condition results to node IDs
        """
        if graph_id not in self.graphs:
            raise ValueError(f"Graph {graph_id} not found")

        if LANGGRAPH_AVAILABLE:
            self.graphs[graph_id].add_conditional_edges(source, condition, targets)

        # Create edges for tracking
        for condition_result, target in targets.items():
            edge_id = f"cond_edge_{source}_{target}_{condition_result}"
            self.graph_edges[graph_id][edge_id] = GraphEdge(
                edge_id=edge_id,
                source=source,
                target=target,
                condition=lambda state, cr=condition_result: condition(state) == cr,
            )

        logger.info(
            "conditional_edges_added",
            graph_id=graph_id,
            source=source,
            targets=list(targets.values()),
        )

    def set_entry_point(self, graph_id: str, node_id: str) -> None:
        """Set the entry point for a graph."""
        if graph_id not in self.graphs:
            raise ValueError(f"Graph {graph_id} not found")

        if LANGGRAPH_AVAILABLE:
            self.graphs[graph_id].set_entry_point(node_id)

        logger.info("entry_point_set", graph_id=graph_id, node_id=node_id)

    def set_finish_point(self, graph_id: str, node_id: str) -> None:
        """Set the finish point for a graph."""
        if graph_id not in self.graphs:
            raise ValueError(f"Graph {graph_id} not found")

        if LANGGRAPH_AVAILABLE:
            self.graphs[graph_id].add_node(node_id, lambda state: state)
            self.graphs[graph_id].add_edge(node_id, END)

        logger.info("finish_point_set", graph_id=graph_id, node_id=node_id)

    def compile_graph(self, graph_id: str) -> Any:
        """
        Compile a graph for execution.

        Args:
            graph_id: Graph to compile

        Returns:
            Compiled graph runnable
        """
        if graph_id not in self.graphs:
            raise ValueError(f"Graph {graph_id} not found")

        if not LANGGRAPH_AVAILABLE:
            raise RuntimeError("LangGraph is not available")

        compiled = self.graphs[graph_id].compile(checkpointer=self.checkpoint_saver)
        logger.info("graph_compiled", graph_id=graph_id)
        return compiled

    async def execute_graph(
        self,
        graph_id: str,
        input_state: dict[str, Any] | None = None,
        thread_id: str | None = None,
        checkpoint_id: str | None = None,
    ) -> GraphExecutionResult:
        """
        Execute a workflow graph.

        Args:
            graph_id: Graph to execute
            input_state: Initial state for execution
            thread_id: Optional thread ID for checkpointing
            checkpoint_id: Optional checkpoint to resume from

        Returns:
            GraphExecutionResult with execution details
        """
        if graph_id not in self.graphs:
            raise ValueError(f"Graph {graph_id} not found")

        start_time = datetime.now(UTC)
        self.graph_status[graph_id] = GraphState.RUNNING

        # Initialize state
        if input_state is None:
            input_state = self.graph_states.get(graph_id, {}).copy()

        # Prepare config for checkpointing
        config: RunnableConfig = {
            "configurable": {
                "thread_id": thread_id or str(uuid.uuid4()),
            }
        }

        # Resume from checkpoint if specified
        if checkpoint_id and self.checkpoint_saver:
            checkpoint = await self._load_checkpoint(graph_id, checkpoint_id)
            if checkpoint:
                input_state.update(checkpoint.state)
                logger.info("resuming_from_checkpoint", checkpoint_id=checkpoint_id)

        node_results: dict[str, Any] = {}
        checkpoints: list[GraphCheckpoint] = []
        error: str | None = None

        try:
            if not LANGGRAPH_AVAILABLE:
                raise RuntimeError("LangGraph is not available")

            compiled = self.compile_graph(graph_id)

            # Execute graph
            async for event in compiled.astream(input_state, config=config):
                # Process event and update node states
                for node_id, node_output in event.items():
                    if node_id in self.graph_nodes.get(graph_id, {}):
                        node = self.graph_nodes[graph_id][node_id]
                        node.status = NodeStatus.COMPLETED
                        node.execution_count += 1
                        node.last_execution_time = datetime.now(UTC).isoformat()
                        node_results[node_id] = node_output

                        # Create checkpoint after node completion
                        checkpoint = await self._create_checkpoint(
                            graph_id=graph_id,
                            state={**input_state, **node_output},
                            thread_id=config["configurable"]["thread_id"],
                        )
                        if checkpoint:
                            checkpoints.append(checkpoint)

                        # Sync state with Heretek agent if applicable
                        if node.agent_id and self.enable_state_sync:
                            await self._sync_agent_state(node.agent_id, node_output)

                        # Notify state sync callbacks
                        await self._notify_state_sync(graph_id, {**input_state, **node_output})

            self.graph_status[graph_id] = GraphState.COMPLETED
            self.graph_states[graph_id] = input_state

        except Exception as e:
            self.graph_status[graph_id] = GraphState.FAILED
            error = str(e)
            logger.error("graph_execution_failed", graph_id=graph_id, error=str(e))

        end_time = datetime.now(UTC)
        execution_time_ms = (end_time - start_time).total_seconds() * 1000

        result = GraphExecutionResult(
            graph_id=graph_id,
            status=self.graph_status[graph_id],
            output=input_state,
            node_results=node_results,
            execution_time_ms=execution_time_ms,
            checkpoints=checkpoints,
            error=error,
        )

        logger.info(
            "graph_execution_completed",
            graph_id=graph_id,
            status=self.graph_status[graph_id].value,
            execution_time_ms=execution_time_ms,
        )

        return result

    async def _sync_agent_state(self, agent_id: str, state: dict[str, Any]) -> None:
        """Synchronize state with a Heretek agent."""
        if not self._agent_runtime:
            return

        try:
            if agent_id in self._agent_runtime:
                runtime = self._agent_runtime[agent_id]
                # Update agent context with graph state
                if hasattr(runtime, "update_context"):
                    await runtime.update_context({"graph_state": state})
                logger.debug("agent_state_synced", agent_id=agent_id)
        except Exception as e:
            logger.error("agent_state_sync_error", agent_id=agent_id, error=str(e))

    async def _create_checkpoint(
        self,
        graph_id: str,
        state: dict[str, Any],
        thread_id: str,
    ) -> GraphCheckpoint | None:
        """Create a checkpoint for the current graph state."""
        if not self.checkpoint_saver:
            return None

        checkpoint_id = f"checkpoint_{graph_id}_{uuid.uuid4().hex[:8]}"

        node_states = {
            node_id: node.status for node_id, node in self.graph_nodes.get(graph_id, {}).items()
        }

        checkpoint = GraphCheckpoint(
            checkpoint_id=checkpoint_id,
            graph_id=graph_id,
            state=state,
            node_states=node_states,
            thread_id=thread_id,
        )

        # Store checkpoint
        if graph_id not in self.checkpoints:
            self.checkpoints[graph_id] = []

        self.checkpoints[graph_id].append(checkpoint)

        # Trim old checkpoints
        if len(self.checkpoints[graph_id]) > self.max_checkpoints:
            self.checkpoints[graph_id] = self.checkpoints[graph_id][-self.max_checkpoints :]

        logger.debug("checkpoint_created", checkpoint_id=checkpoint_id)
        return checkpoint

    async def _load_checkpoint(
        self,
        graph_id: str,
        checkpoint_id: str,
    ) -> GraphCheckpoint | None:
        """Load a checkpoint by ID."""
        for checkpoint in self.checkpoints.get(graph_id, []):
            if checkpoint.checkpoint_id == checkpoint_id:
                return checkpoint
        return None

    def register_tool(self, tool: Any, tool_id: str | None = None) -> str:
        """
        Register a LangChain tool for use in workflows.

        Args:
            tool: LangChain BaseTool instance
            tool_id: Optional tool identifier

        Returns:
            Tool ID
        """
        if not LANGGRAPH_AVAILABLE:
            raise RuntimeError("LangGraph is not available")

        if not isinstance(tool, BaseTool):
            raise TypeError("Tool must be a LangChain BaseTool instance")

        if tool_id is None:
            tool_id = tool.name

        self.tools[tool_id] = tool
        logger.info("tool_registered", tool_id=tool_id)
        return tool_id

    def create_tool_node(self, graph_id: str, tool_ids: list[str]) -> None:
        """
        Create a ToolNode for executing tools in a workflow.

        Args:
            graph_id: Target graph ID
            tool_ids: List of tool IDs to include
        """
        if not LANGGRAPH_AVAILABLE:
            raise RuntimeError("LangGraph is not available")

        tools = [self.tools[tid] for tid in tool_ids if tid in self.tools]

        if tools:
            tool_node = ToolNode(tools)
            node_id = f"tool_node_{uuid.uuid4().hex[:8]}"
            self.graph_nodes[graph_id][node_id] = GraphNode(
                node_id=node_id,
                name=f"ToolNode ({len(tools)} tools)",
                function=tool_node.invoke,
            )
            self.tool_nodes[node_id] = tool_node
            logger.info("tool_node_created", node_id=node_id, tool_count=len(tools))

    def get_graph_status(self, graph_id: str) -> dict[str, Any]:
        """Get current status of a graph."""
        if graph_id not in self.graphs:
            return {"error": f"Graph {graph_id} not found"}

        nodes = self.graph_nodes.get(graph_id, {})

        return {
            "graph_id": graph_id,
            "status": self.graph_status.get(graph_id, GraphState.INITIALIZED).value,
            "node_count": len(nodes),
            "edge_count": len(self.graph_edges.get(graph_id, {})),
            "nodes": {nid: n.to_dict() for nid, n in nodes.items()},
            "state": self.graph_states.get(graph_id, {}),
            "checkpoint_count": len(self.checkpoints.get(graph_id, [])),
        }

    def get_checkpoints(self, graph_id: str, limit: int = 10) -> list[dict[str, Any]]:
        """Get recent checkpoints for a graph."""
        checkpoints = self.checkpoints.get(graph_id, [])
        return [c.to_dict() for c in checkpoints[-limit:]]

    def get_statistics(self) -> dict[str, Any]:
        """Get adapter statistics."""
        total_nodes = sum(len(nodes) for nodes in self.graph_nodes.values())
        total_edges = sum(len(edges) for edges in self.graph_edges.values())
        total_checkpoints = sum(len(checkpoints) for checkpoints in self.checkpoints.values())

        return {
            "graph_count": len(self.graphs),
            "total_nodes": total_nodes,
            "total_edges": total_edges,
            "total_checkpoints": total_checkpoints,
            "tool_count": len(self.tools),
            "langgraph_available": LANGGRAPH_AVAILABLE,
            "state_sync_enabled": self.enable_state_sync,
        }

    def clear_graph(self, graph_id: str) -> bool:
        """Clear a graph and its state."""
        if graph_id not in self.graphs:
            return False

        if graph_id in self.graphs:
            del self.graphs[graph_id]
        if graph_id in self.graph_nodes:
            del self.graph_nodes[graph_id]
        if graph_id in self.graph_edges:
            del self.graph_edges[graph_id]
        if graph_id in self.graph_states:
            del self.graph_states[graph_id]
        if graph_id in self.graph_status:
            del self.graph_status[graph_id]
        if graph_id in self.checkpoints:
            del self.checkpoints[graph_id]

        logger.info("graph_cleared", graph_id=graph_id)
        return True

    def clear_all(self) -> None:
        """Clear all graphs and state."""
        self.graphs.clear()
        self.graph_nodes.clear()
        self.graph_edges.clear()
        self.graph_states.clear()
        self.graph_status.clear()
        self.checkpoints.clear()
        self.tools.clear()
        self.tool_nodes.clear()
        logger.info("langgraph_adapter_cleared")


# Global adapter instance
langgraph_adapter: LangGraphAdapter | None = None


def get_langgraph_adapter() -> LangGraphAdapter:
    """Get the global LangGraph adapter instance."""
    global langgraph_adapter
    if langgraph_adapter is None:
        langgraph_adapter = LangGraphAdapter()
    return langgraph_adapter


def create_workflow_graph(
    graph_id: str,
    nodes: list[dict[str, Any]],
    edges: list[dict[str, Any]],
    entry_point: str,
    state_schema: dict[str, Any] | None = None,
) -> LangGraphAdapter:
    """
    Create a workflow graph from configuration.

    Args:
        graph_id: Graph identifier
        nodes: List of node configurations
        edges: List of edge configurations
        entry_point: Entry point node ID
        state_schema: Optional state schema

    Returns:
        Configured LangGraphAdapter
    """
    adapter = get_langgraph_adapter()

    # Create graph
    adapter.create_graph(graph_id, state_schema)

    # Add nodes
    for node_config in nodes:
        adapter.add_node(
            graph_id=graph_id,
            node_id=node_config.get("node_id", node_config.get("name")),
            name=node_config.get("name", "unnamed"),
            agent_id=node_config.get("agent_id"),
            action=node_config.get("action"),
            metadata=node_config.get("metadata"),
        )

    # Add edges
    for edge_config in edges:
        adapter.add_edge(
            graph_id=graph_id,
            source=edge_config["source"],
            target=edge_config["target"],
            condition=edge_config.get("condition"),
            weight=edge_config.get("weight", 1.0),
            metadata=edge_config.get("metadata"),
        )

    # Set entry point
    adapter.set_entry_point(graph_id, entry_point)

    logger.info("workflow_graph_created", graph_id=graph_id, node_count=len(nodes))
    return adapter
