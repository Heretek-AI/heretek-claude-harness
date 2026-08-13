"""
Workflow Execution Strategies

Provides three execution modes for workflow graphs:
- DAG: Topological sort execution (nodes run in dependency order)
- Cycle: Feedback loop execution with cycle detection
- MajorityVote: Parallel execution with vote aggregation

Inspired by ChatDev's execution strategy patterns.
"""

import asyncio
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any

import structlog

from heretek_swarm.workflow.models import (
    Workflow,
    WorkflowNode,
)

logger = structlog.get_logger(__name__)


class WorkflowExecutionResult:
    """
    Result from a workflow execution strategy.

    Simplified result type for strategy-level reporting.
    The calling WorkflowEngine wraps this into its own WorkflowResult.
    """

    def __init__(
        self,
        workflow_id: str,
        success: bool,
        execution_time: float,
        node_results: dict[str, Any],
        error_message: str | None = None,
        node_status: dict[str, str] | None = None,
    ) -> None:
        self.workflow_id = workflow_id
        self.success = success
        self.execution_time = execution_time
        self.node_results = node_results
        self.error_message = error_message
        self.node_status = node_status or {}

    @property
    def status(self) -> str:
        """Human-readable status string."""
        if self.success:
            return "completed"
        return "failed"

    def __repr__(self) -> str:
        return (
            f"WorkflowExecutionResult(workflow_id={self.workflow_id!r}, "
            f"success={self.success}, node_results={len(self.node_results)})"
        )


class ExecutionStrategy(ABC):
    """
    Base class for workflow execution strategies.

    Subclasses implement execute() to define the execution order
    and aggregation behavior for different graph topologies.
    """

    @abstractmethod
    async def execute(
        self,
        workflow: Workflow,
        context: dict[str, Any],
        node_executor: callable,
    ) -> WorkflowExecutionResult:
        """
        Execute a workflow using this strategy.

        Args:
            workflow: Workflow to execute
            context: Execution context (input data, state, etc.)
            node_executor: Async callable(node_id, node_data) -> result

        Returns:
            WorkflowResult with node results and status
        """
        ...


@dataclass
class DAGStrategy(ExecutionStrategy):
    """
    Directed Acyclic Graph execution strategy.

    Nodes execute in topological sort order — a node's inputs are
    guaranteed to be complete before the node itself starts.
    This is the default strategy for tree-structured workflows.
    """

    max_parallel: int = 4  # Max concurrent nodes at same level
    timeout_seconds: float = 300.0

    async def execute(
        self,
        workflow: Workflow,
        context: dict[str, Any],
        node_executor: callable,
    ) -> WorkflowExecutionResult:
        """
        Execute workflow nodes in topological order with parallel batching.
        """
        node_results: dict[str, Any] = {}
        failed_nodes: list[str] = []

        # Build dependency map: node_id -> list of input node ids
        {node.id: node.inputs for node in workflow.nodes}

        # Compute in-degree (number of unmet dependencies)
        in_degree: dict[str, int] = {node.id: len(node.inputs) for node in workflow.nodes}

        # Start with nodes that have no unmet dependencies
        ready: list[str] = [node_id for node_id, degree in in_degree.items() if degree == 0]

        while ready:
            newly_ready = await self._execute_batch(
                ready, workflow, node_executor, context, node_results, failed_nodes, in_degree
            )
            ready = newly_ready

        return self._build_dag_result(workflow, node_results, failed_nodes, in_degree, context)

    async def _execute_batch(
        self,
        ready: list[str],
        workflow: Workflow,
        node_executor: callable,
        context: dict[str, Any],
        node_results: dict[str, Any],
        failed_nodes: list[str],
        in_degree: dict[str, int],
    ) -> list[str]:
        """Execute a batch of ready nodes in parallel."""
        batch = ready[: self.max_parallel]
        ready = ready[self.max_parallel :]

        async def run_node(node_id: str) -> tuple[str, Any | None, str | None]:
            node = next(n for n in workflow.nodes if n.id == node_id)
            try:
                result = await asyncio.wait_for(
                    node_executor(node_id, node.data),
                    timeout=self.timeout_seconds,
                )
                return node_id, result, None
            except TimeoutError:
                return node_id, None, f"Timeout after {self.timeout_seconds}s"
            except Exception as e:
                return node_id, None, str(e)

        results = await asyncio.gather(*[run_node(nid) for nid in batch])

        newly_ready: list[str] = []
        for node_id, result, error in results:
            if error:
                failed_nodes.append(node_id)
                node_results[node_id] = {"error": error}
                logger.warning(
                    "dag_node_failed",
                    node_id=node_id,
                    error=error,
                    execution_id=context.get("execution_id"),
                )
            else:
                node_results[node_id] = result

            for other_node in workflow.nodes:
                if node_id in other_node.inputs:
                    in_degree[other_node.id] -= 1
                    if in_degree[other_node.id] == 0:
                        newly_ready.append(other_node.id)

        return newly_ready

    def _build_dag_result(
        self,
        workflow: Workflow,
        node_results: dict[str, Any],
        failed_nodes: list[str],
        in_degree: dict[str, int],
        context: dict[str, Any],
    ) -> WorkflowExecutionResult:
        """Build the final DAG execution result."""
        remaining = [nid for nid, deg in in_degree.items() if deg > 0]
        if remaining and not failed_nodes:
            return WorkflowExecutionResult(
                workflow_id=workflow.id,
                success=False,
                execution_time=0.0,
                node_results=node_results,
                error_message=f"Cycle detected in DAG workflow: nodes {remaining} form a cycle",
                node_status=dict.fromkeys(remaining, "failed"),
            )

        success = len(failed_nodes) == 0 and len(remaining) == 0
        return WorkflowExecutionResult(
            workflow_id=workflow.id,
            success=success,
            execution_time=context.get("elapsed", 0.0),
            node_results=node_results,
            error_message=None if success else f"Failed nodes: {failed_nodes}",
            node_status={
                nid: "failed" if nid in failed_nodes else "completed" for nid in node_results
            },
        )


@dataclass
class CycleStrategy(ExecutionStrategy):
    """
    Feedback loop execution strategy.

    Designed for workflows with cycles (approval loops, iterative refinement,
    consensus building). Tracks iteration count, convergence, and divergence.
    Unlike DAG strategy, cycles are intentional and monitored.
    """

    max_iterations: int = 10
    convergence_threshold: float = 0.05  # State change below this = converged
    divergence_threshold: float = 1.5  # State change above this = diverging
    timeout_seconds: float = 600.0

    async def execute(
        self,
        workflow: Workflow,
        context: dict[str, Any],
        node_executor: callable,
    ) -> WorkflowExecutionResult:
        """
        Execute workflow with cycle detection and convergence monitoring.
        """
        node_results: dict[str, Any] = {}
        iteration_count = 0
        last_state: dict[str, Any] = {}
        status = "running"

        cycle_edges = self._find_cycle_edges(workflow)
        node_timeout = self.timeout_seconds / self.max_iterations

        while iteration_count < self.max_iterations and status == "running":
            iteration_count += 1
            logger.info(
                "cycle_iteration",
                iteration=iteration_count,
                execution_id=context.get("execution_id"),
            )

            await self._execute_non_cycle_nodes(workflow, cycle_edges, node_executor, node_timeout, node_results)
            cycle_state_changed = await self._execute_cycle_nodes(
                workflow, cycle_edges, node_executor, node_timeout, node_results
            )

            status = self._check_cycle_status(
                cycle_state_changed, iteration_count, last_state, node_results, context
            )
            if status != "running":
                break
            last_state = dict(node_results)

        if iteration_count >= self.max_iterations and status == "running":
            status = "max_iterations"

        success = status in ("converged", "completed")
        return WorkflowExecutionResult(
            workflow_id=workflow.id,
            success=success,
            execution_time=context.get("elapsed", 0.0),
            node_results=node_results,
            error_message=None if success else f"Status: {status} at iteration {iteration_count}",
            node_status=dict.fromkeys(node_results, status),
        )

    async def _execute_non_cycle_nodes(
        self,
        workflow: Workflow,
        cycle_edges: set[str],
        node_executor: callable,
        timeout: float,
        node_results: dict[str, Any],
    ) -> None:
        """Execute nodes that are not part of cycles."""
        for node in workflow.nodes:
            if node.id not in cycle_edges:
                try:
                    result = await asyncio.wait_for(
                        node_executor(node.id, node.data), timeout=timeout
                    )
                    node_results[node.id] = result
                except Exception as e:
                    logger.error("cycle_node_failed", node_id=node.id, error=str(e))
                    node_results[node.id] = {"error": str(e)}

    async def _execute_cycle_nodes(
        self,
        workflow: Workflow,
        cycle_edges: set[str],
        node_executor: callable,
        timeout: float,
        node_results: dict[str, Any],
    ) -> bool:
        """Execute cycle nodes and return whether state changed."""
        cycle_state_changed = False
        for node_id in cycle_edges:
            node = next(n for n in workflow.nodes if n.id == node_id)
            try:
                result = await asyncio.wait_for(
                    node_executor(node_id, node.data), timeout=timeout
                )
                old_val = node_results.get(node_id, {})
                node_results[node_id] = result
                if isinstance(result, dict):
                    delta = self._compute_state_delta(old_val, result)
                    if delta > self.convergence_threshold:
                        cycle_state_changed = True
            except Exception as e:
                logger.error("cycle_node_failed", node_id=node_id, error=str(e))
        return cycle_state_changed

    def _check_cycle_status(
        self,
        cycle_state_changed: bool,
        iteration_count: int,
        last_state: dict[str, Any],
        node_results: dict[str, Any],
        context: dict[str, Any],
    ) -> str:
        """Check convergence/divergence and return status."""
        if not cycle_state_changed:
            logger.info(
                "cycle_converged",
                iterations=iteration_count,
                execution_id=context.get("execution_id"),
            )
            return "converged"

        total_change = self._compute_state_delta(last_state, node_results)
        if total_change > self.divergence_threshold * iteration_count:
            logger.warning(
                "cycle_diverging",
                iterations=iteration_count,
                total_change=total_change,
                execution_id=context.get("execution_id"),
            )
            return "diverging"

        return "running"

    def _find_cycle_edges(self, workflow: Workflow) -> set[str]:
        """Identify nodes involved in cycles."""
        # Simple approach: nodes with edges pointing to already-executed nodes
        # A full implementation would use Tarjan's algorithm
        # For now, identify nodes that have edges pointing back (feedback edges)
        cycle_nodes: set[str] = set()

        for edge in workflow.edges:
            # If there's a condition on the edge, it likely indicates a cycle
            if edge.condition:
                cycle_nodes.add(edge.target)

        return cycle_nodes

    def _compute_state_delta(
        self,
        old: dict[str, Any],
        new: dict[str, Any],
    ) -> float:
        """Compute normalized state change between iterations."""
        if not old:
            return 1.0

        changed_keys = sum(1 for k in new if old.get(k) != new[k])
        total_keys = max(len(new), 1)
        return changed_keys / total_keys


@dataclass
class MajorityVoteStrategy(ExecutionStrategy):
    """
    Parallel execution with majority vote aggregation.

    All nodes execute concurrently, then their outputs are aggregated
    using majority vote (for classification) or weighted average (for scores).
    Designed for parallel agent consensus scenarios.
    """

    min_votes: int = 1
    agreement_threshold: float = 0.6  # 60% agreement required
    timeout_seconds: float = 300.0

    async def execute(
        self,
        workflow: Workflow,
        context: dict[str, Any],
        node_executor: callable,
    ) -> WorkflowExecutionResult:
        """
        Execute all nodes in parallel, then aggregate via majority vote.
        """

        # Execute all nodes concurrently
        async def run_all() -> list[tuple[str, Any | None, str | None]]:
            async def run_node(node: WorkflowNode) -> tuple[str, Any | None, str | None]:
                try:
                    result = await asyncio.wait_for(
                        node_executor(node.id, node.data),
                        timeout=self.timeout_seconds,
                    )
                    return node.id, result, None
                except TimeoutError:
                    return node.id, None, f"Timeout after {self.timeout_seconds}s"
                except Exception as e:
                    return node.id, None, str(e)

            return await asyncio.gather(*[run_node(n) for n in workflow.nodes])

        results = await run_all()

        node_results: dict[str, Any] = {}
        failed_nodes: list[str] = []

        for node_id, result, error in results:
            if error:
                failed_nodes.append(node_id)
                node_results[node_id] = {"error": error}
            else:
                node_results[node_id] = result

        # Aggregate results via majority vote
        aggregated = self._majority_vote(
            list(node_results.values()),
            threshold=self.agreement_threshold,
        )

        if len(failed_nodes) > len(node_results) - self.min_votes:
            return WorkflowExecutionResult(
                workflow_id=workflow.id,
                success=False,
                execution_time=context.get("elapsed", 0.0),
                node_results=node_results,
                error_message=f"Too many failures: {failed_nodes}",
                node_status=dict.fromkeys(failed_nodes, "failed"),
            )

        return WorkflowExecutionResult(
            workflow_id=workflow.id,
            success=True,
            execution_time=context.get("elapsed", 0.0),
            node_results={
                "votes": node_results,
                "aggregated": aggregated,
            },
            error_message=None,
            node_status=dict.fromkeys(node_results, "completed"),
        )

    def _majority_vote(
        self,
        results: list[Any],
        threshold: float,
    ) -> Any:
        """
        Aggregate results using majority vote.

        For dict/list results: count most common value per key
        For scalar results: return most common value
        """
        if not results:
            return None

        # If results are scalars (strings, numbers), count occurrences
        if all(isinstance(r, (str, int, float, bool)) or r is None for r in results):
            from collections import Counter

            counter = Counter(results)
            most_common, count = counter.most_common(1)[0]
            if count / len(results) >= threshold:
                return most_common
            # No majority — return all with votes
            return {
                "votes": dict(counter),
                "winner": most_common,
                "agreement": count / len(results),
            }

        # For dict results, aggregate per key
        if all(isinstance(r, dict) for r in results):
            aggregated: dict[str, Any] = {}
            for key in results[0]:
                values = [r.get(key) for r in results if isinstance(r, dict)]
                # Recursively vote on each key
                aggregated[key] = self._majority_vote(values, threshold)
            return aggregated

        # Fallback: return the first result
        return results[0]
