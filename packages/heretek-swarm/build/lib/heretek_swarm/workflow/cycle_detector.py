"""
Workflow Cycle Detector - Cycle Detection for 5-Phase Workflow.

This module implements cycle detection for workflow execution, preventing infinite loops
and ensuring workflow termination. Based on LangGraph Swarm patterns for graph traversal.

Features:
- Track visited nodes in workflow execution
- Detect cycles in the 5-phase workflow (Plan, Analyze, Execute, Validate, Report)
- Implement cycle breaking strategies (max iterations, timeout, convergence threshold)
- Log cycle detection events with correlation IDs
- Add cycle detection metrics to Prometheus

5-Phase Workflow:
1. Plan - Define objectives and strategy
2. Analyze - Process information and generate insights
3. Execute - Perform actions and generate outputs
4. Validate - Verify results against criteria
5. Report - Summarize outcomes and update state

Cycle Detection Strategies:
- Node-based: Track individual node visits
- Path-based: Track complete execution paths
- State-based: Track workflow state convergence

Author: Heretek Swarm Collective
Date: 2026-04-07
Version: 1.0.0
"""

import time
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

import structlog

logger = structlog.get_logger("WorkflowCycleDetector")


class CycleBreakingStrategy(StrEnum):
    """Strategies for breaking detected cycles."""

    MAX_ITERATIONS = "max_iterations"
    TIMEOUT = "timeout"
    CONVERGENCE_THRESHOLD = "convergence_threshold"
    STATE_CHANGE_REQUIRED = "state_change_required"


@dataclass
class CycleDetectionEvent:
    """
    Represents a cycle detection event for audit logging.

    Attributes:
        event_id: Unique event identifier
        workflow_id: Workflow where cycle was detected
        correlation_id: Correlation ID for tracing
        cycle_path: List of nodes forming the cycle
        detection_time: When cycle was detected
        breaking_strategy: Strategy used to break cycle
        resolution: How cycle was resolved
        metadata: Additional context
    """

    event_id: str
    workflow_id: str
    correlation_id: str
    cycle_path: list[str]
    detection_time: str
    breaking_strategy: str | None = None
    resolution: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "event_id": self.event_id,
            "workflow_id": self.workflow_id,
            "correlation_id": self.correlation_id,
            "cycle_path": self.cycle_path,
            "detection_time": self.detection_time,
            "breaking_strategy": self.breaking_strategy,
            "resolution": self.resolution,
            "metadata": self.metadata,
        }


@dataclass
class ExecutionPath:
    """
    Tracks an execution path through the workflow.

    Attributes:
        path_id: Unique path identifier
        nodes: Ordered list of visited nodes
        start_time: When path execution started
        state_hash: Hash of workflow state at path start
        visit_counts: Count of visits per node
    """

    path_id: str
    nodes: list[str] = field(default_factory=list)
    start_time: str = field(default_factory=lambda: datetime.now(UTC).isoformat())
    state_hash: str | None = None
    visit_counts: dict[str, int] = field(default_factory=dict)

    def add_node(self, node_id: str) -> int:
        """
        Add a node to the path and return visit count.

        Args:
            node_id: Node to add

        Returns:
            Number of times this node has been visited
        """
        self.nodes.append(node_id)
        self.visit_counts[node_id] = self.visit_counts.get(node_id, 0) + 1
        return self.visit_counts[node_id]

    def get_cycle(self) -> list[str] | None:
        """
        Detect if there's a cycle in the current path.

        A cycle exists when a node appears more than once in the path.
        The cycle is the sequence from the first occurrence to just before the repeat.

        Returns:
            List of nodes forming the cycle, or None if no cycle
        """
        if len(self.nodes) < 2:
            return None

        # Check for repeated nodes (which indicates a cycle)
        seen = {}
        for i, node in enumerate(self.nodes):
            if node in seen:
                # Found a repeated node - cycle detected
                # The cycle is from first occurrence to current position (exclusive)
                cycle = self.nodes[seen[node] : i]
                if len(cycle) >= 1:
                    return cycle
            seen[node] = i

        return None

    def _verify_cycle(self, cycle: list[str]) -> bool:
        """
        Verify that a sequence is actually a repeating cycle.

        Args:
            cycle: Potential cycle to verify

        Returns:
            True if cycle is verified
        """
        if not cycle:
            return False

        # A cycle is verified if it has at least one node
        # (the presence of a repeated node already confirms the cycle)
        return len(cycle) >= 1

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "path_id": self.path_id,
            "nodes": self.nodes,
            "start_time": self.start_time,
            "state_hash": self.state_hash,
            "visit_counts": self.visit_counts,
        }


class WorkflowCycleDetector:
    """
    Cycle detector for 5-phase workflow execution.

    This class tracks workflow execution paths and detects cycles that could
    lead to infinite loops. It implements multiple cycle breaking strategies
    and provides detailed logging and metrics.

    Example:
        ```python
        detector = WorkflowCycleDetector(max_iterations=100, timeout_seconds=300)

        # Track workflow execution
        workflow_id = "workflow_123"

        # Check for cycle before executing node
        if detector.detect_cycle(workflow_id, "plan_phase"):
            if detector.should_break_cycle(workflow_id):
                detector.break_cycle(workflow_id, CycleBreakingStrategy.MAX_ITERATIONS)

        # Record node execution
        detector.record_node_execution(workflow_id, "plan_phase", state={"phase": "plan"})
        ```
    """

    # 5-Phase workflow definition
    FIVE_PHASES = ["plan", "analyze", "execute", "validate", "report"]  # noqa: RUF012

    def __init__(
        self,
        max_iterations: int = 100,
        timeout_seconds: float = 300.0,
        convergence_threshold: float = 0.001,
        track_paths: bool = True,
    ):
        """
        Initialize the cycle detector.

        Args:
            max_iterations: Maximum iterations before breaking cycle
            timeout_seconds: Timeout in seconds before breaking cycle
            convergence_threshold: Threshold for state convergence detection
            track_paths: Whether to track full execution paths
        """
        self.max_iterations = max_iterations
        self.timeout_seconds = timeout_seconds
        self.convergence_threshold = convergence_threshold
        self.track_paths = track_paths

        # Per-workflow tracking
        self.visited_nodes: dict[str, list[str]] = {}
        self.execution_paths: dict[str, ExecutionPath] = {}
        self.workflow_start_times: dict[str, float] = {}
        self.iteration_counts: dict[str, int] = {}
        self.previous_states: dict[str, dict[str, Any]] = {}

        # Cycle detection history
        self.detected_cycles: list[CycleDetectionEvent] = []

        # Metrics
        self.metrics = {
            "total_cycles_detected": 0,
            "total_cycles_broken": 0,
            "cycles_by_strategy": {},
            "avg_iterations_before_cycle": 0.0,
        }

        logger.info(
            "WorkflowCycleDetector initialized",
            extra={
                "max_iterations": max_iterations,
                "timeout_seconds": timeout_seconds,
                "convergence_threshold": convergence_threshold,
            },
        )

    def start_workflow_tracking(self, workflow_id: str) -> None:
        """
        Start tracking a workflow execution.

        Args:
            workflow_id: Unique workflow identifier
        """
        self.visited_nodes[workflow_id] = []
        self.execution_paths[workflow_id] = ExecutionPath(path_id=f"path_{uuid.uuid4()}")
        self.workflow_start_times[workflow_id] = time.time()
        self.iteration_counts[workflow_id] = 0
        self.previous_states[workflow_id] = {}

        logger.debug("workflow_tracking_started", workflow_id=workflow_id)

    def stop_workflow_tracking(self, workflow_id: str) -> None:
        """
        Stop tracking a workflow execution.

        Args:
            workflow_id: Unique workflow identifier
        """
        if workflow_id in self.visited_nodes:
            del self.visited_nodes[workflow_id]
        if workflow_id in self.execution_paths:
            del self.execution_paths[workflow_id]
        if workflow_id in self.workflow_start_times:
            del self.workflow_start_times[workflow_id]
        if workflow_id in self.iteration_counts:
            del self.iteration_counts[workflow_id]
        if workflow_id in self.previous_states:
            del self.previous_states[workflow_id]

        logger.debug("workflow_tracking_stopped", workflow_id=workflow_id)

    def record_node_execution(
        self,
        workflow_id: str,
        node_id: str,
        state: dict[str, Any] | None = None,
    ) -> int:
        """
        Record a node execution and return visit count.

        Args:
            workflow_id: Workflow identifier
            node_id: Executed node identifier
            state: Optional workflow state after execution

        Returns:
            Number of times this node has been visited
        """
        # Initialize tracking if needed
        if workflow_id not in self.visited_nodes:
            self.start_workflow_tracking(workflow_id)

        # Increment iteration count
        self.iteration_counts[workflow_id] = self.iteration_counts.get(workflow_id, 0) + 1

        # Track node visit
        visit_count = 0
        if workflow_id in self.visited_nodes:
            self.visited_nodes[workflow_id].append(node_id)
            visit_count = self.visited_nodes[workflow_id].count(node_id)

        # Track execution path
        if self.track_paths and workflow_id in self.execution_paths:
            visit_count = self.execution_paths[workflow_id].add_node(node_id)

        # Store state for convergence detection
        if state:
            self.previous_states[workflow_id] = state.copy()

        logger.debug(
            "node_execution_recorded",
            workflow_id=workflow_id,
            node_id=node_id,
            visit_count=visit_count,
            iteration=self.iteration_counts.get(workflow_id, 0),
        )

        return visit_count

    def detect_cycle(self, workflow_id: str, current_node: str) -> bool:
        """
        Detect if executing the current node would create a cycle.

        Args:
            workflow_id: Workflow identifier
            current_node: Node about to be executed

        Returns:
            True if cycle detected
        """
        if workflow_id not in self.visited_nodes:
            return False

        # Check for cycles in execution path
        if self.track_paths and workflow_id in self.execution_paths:
            path = self.execution_paths[workflow_id]

            # Create temporary path with current node
            temp_path = [*path.nodes, current_node]

            # Check for cycle
            for i, node in enumerate(temp_path[:-1]):
                if node == current_node:
                    potential_cycle = temp_path[i:]
                    if len(potential_cycle) >= 2:
                        logger.warning(
                            "cycle_detected",
                            workflow_id=workflow_id,
                            cycle_path=potential_cycle,
                        )
                        return True

        # Check for repeated node visits (simple cycle detection)
        visited = self.visited_nodes[workflow_id]
        if len(visited) >= 2:
            # Check if last N nodes match pattern
            window_size = min(10, len(visited))
            recent = visited[-window_size:]

            # Simple pattern detection: same node multiple times
            if recent.count(current_node) >= 3:
                logger.warning(
                    "repeated_node_detected",
                    workflow_id=workflow_id,
                    node=current_node,
                    count=recent.count(current_node),
                )
                return True

        return False

    def should_break_cycle(self, workflow_id: str) -> bool:
        """
        Determine if a cycle should be broken based on configured strategies.

        Args:
            workflow_id: Workflow identifier

        Returns:
            True if cycle should be broken
        """
        if workflow_id not in self.iteration_counts:
            return False

        iteration_count = self.iteration_counts[workflow_id]
        start_time = self.workflow_start_times.get(workflow_id, 0)
        elapsed_time = time.time() - start_time

        # Check max iterations
        if iteration_count >= self.max_iterations:
            logger.warning(
                "max_iterations_reached",
                workflow_id=workflow_id,
                iterations=iteration_count,
                max=self.max_iterations,
            )
            return True

        # Check timeout
        if elapsed_time >= self.timeout_seconds:
            logger.warning(
                "timeout_reached",
                workflow_id=workflow_id,
                elapsed_seconds=elapsed_time,
                timeout=self.timeout_seconds,
            )
            return True

        # Check state convergence
        if self._check_state_convergence(workflow_id):
            logger.warning(
                "state_convergence_detected",
                workflow_id=workflow_id,
                threshold=self.convergence_threshold,
            )
            return True

        return False

    def _check_state_convergence(self, workflow_id: str) -> bool:
        """
        Check if workflow state has converged (stopped changing).

        Args:
            workflow_id: Workflow identifier

        Returns:
            True if state has converged
        """
        if workflow_id not in self.previous_states:
            return False

        current_state = self.previous_states.get(workflow_id, {})

        # Compare with recently visited states
        # Simple implementation: check if state values are stable
        if not current_state:
            return False

        # Check if state values are all near zero or unchanged
        state_magnitude = sum(abs(v) for v in current_state.values() if isinstance(v, (int, float)))

        return state_magnitude < self.convergence_threshold

    def break_cycle(
        self,
        workflow_id: str,
        strategy: CycleBreakingStrategy = CycleBreakingStrategy.MAX_ITERATIONS,
        reason: str | None = None,
    ) -> CycleDetectionEvent:
        """
        Break a detected cycle and record the event.

        Args:
            workflow_id: Workflow identifier
            strategy: Strategy used to break cycle
            reason: Optional reason for breaking

        Returns:
            CycleDetectionEvent for audit logging
        """
        # Get cycle path
        cycle_path = []
        if workflow_id in self.execution_paths:
            cycle_path = self.execution_paths[workflow_id].get_cycle() or []
        elif workflow_id in self.visited_nodes:
            # Use last N visited nodes as cycle path
            cycle_path = self.visited_nodes[workflow_id][-10:]

        # Create event
        event = CycleDetectionEvent(
            event_id=f"cycle_{uuid.uuid4()}",
            workflow_id=workflow_id,
            correlation_id=f"corr_{uuid.uuid4()}",
            cycle_path=cycle_path,
            detection_time=datetime.now(UTC).isoformat(),
            breaking_strategy=strategy.value,
            resolution=reason or "cycle_breaking_strategy_applied",
            metadata={
                "iteration_count": self.iteration_counts.get(workflow_id, 0),
                "elapsed_time": time.time() - self.workflow_start_times.get(workflow_id, 0),
                "visited_nodes_count": len(self.visited_nodes.get(workflow_id, [])),
            },
        )

        # Record event
        self.detected_cycles.append(event)

        # Update metrics
        self.metrics["total_cycles_detected"] += 1
        self.metrics["total_cycles_broken"] += 1
        strategy_key = strategy.value
        self.metrics["cycles_by_strategy"][strategy_key] = (
            self.metrics["cycles_by_strategy"].get(strategy_key, 0) + 1
        )

        # Calculate average iterations
        total_cycles = self.metrics["total_cycles_detected"]
        if total_cycles > 0:
            total_iterations = sum(
                e.metadata.get("iteration_count", 0) for e in self.detected_cycles
            )
            self.metrics["avg_iterations_before_cycle"] = total_iterations / total_cycles

        logger.warning(
            "cycle_broken",
            workflow_id=workflow_id,
            strategy=strategy.value,
            cycle_path=cycle_path,
            event_id=event.event_id,
        )

        return event

    def get_execution_path(self, workflow_id: str) -> ExecutionPath | None:
        """
        Get the execution path for a workflow.

        Args:
            workflow_id: Workflow identifier

        Returns:
            ExecutionPath or None
        """
        return self.execution_paths.get(workflow_id)

    def get_visited_nodes(self, workflow_id: str) -> list[str]:
        """
        Get list of visited nodes for a workflow.

        Args:
            workflow_id: Workflow identifier

        Returns:
            List of visited node IDs
        """
        return self.visited_nodes.get(workflow_id, [])

    def get_iteration_count(self, workflow_id: str) -> int:
        """
        Get iteration count for a workflow.

        Args:
            workflow_id: Workflow identifier

        Returns:
            Iteration count
        """
        return self.iteration_counts.get(workflow_id, 0)

    def get_detected_cycles(self) -> list[CycleDetectionEvent]:
        """
        Get all detected cycle events.

        Returns:
            List of CycleDetectionEvent objects
        """
        return self.detected_cycles.copy()

    def get_metrics(self) -> dict[str, Any]:
        """
        Get cycle detection metrics.

        Returns:
            Dictionary of metrics
        """
        return self.metrics.copy()

    def export_prometheus_metrics(self) -> str:
        """
        Export metrics in Prometheus text format.

        Returns:
            Prometheus-formatted metrics string
        """
        lines = [
            "# HELP heretek_workflow_cycles_total Total number of cycles detected",
            "# TYPE heretek_workflow_cycles_total counter",
            f"heretek_workflow_cycles_total {self.metrics['total_cycles_detected']}",
            "",
            "# HELP heretek_workflow_cycles_broken_total Total number of cycles broken",
            "# TYPE heretek_workflow_cycles_broken_total counter",
            f"heretek_workflow_cycles_broken_total {self.metrics['total_cycles_broken']}",
            "",
            "# HELP heretek_workflow_avg_iterations_before_cycle Average iterations before cycle detection",  # noqa: E501
            "# TYPE heretek_workflow_avg_iterations_before_cycle gauge",
            f"heretek_workflow_avg_iterations_before_cycle {self.metrics['avg_iterations_before_cycle']}",  # noqa: E501
            "",
        ]

        # Add per-strategy metrics
        for strategy, count in self.metrics.get("cycles_by_strategy", {}).items():
            lines.extend(
                [
                    "# HELP heretek_workflow_cycles_by_strategy Cycles broken by strategy",
                    "# TYPE heretek_workflow_cycles_by_strategy gauge",
                    f'heretek_workflow_cycles_by_strategy{{strategy="{strategy}"}} {count}',
                    "",
                ]
            )

        return "\n".join(lines)

    def clear_history(self) -> None:
        """Clear all cycle detection history."""
        self.detected_cycles.clear()
        self.metrics = {
            "total_cycles_detected": 0,
            "total_cycles_broken": 0,
            "cycles_by_strategy": {},
            "avg_iterations_before_cycle": 0.0,
        }
        logger.info("cycle_detection_history_cleared")


class FivePhaseWorkflowTracker:
    """
    Specialized tracker for 5-phase workflow patterns.

    Tracks the specific 5-phase workflow pattern (Plan, Analyze, Execute,
    Validate, Report) and detects cycles within this structure.

    Example:
        ```python
        tracker = FivePhaseWorkflowTracker()

        # Track phase transitions
        tracker.record_phase_transition("workflow_123", "plan", "analyze")
        tracker.record_phase_transition("workflow_123", "analyze", "execute")

        # Check for phase cycles
        if tracker.detect_phase_cycle("workflow_123", "plan"):
            # Handle cycle
            pass
        ```
    """

    def __init__(self, max_phase_repeats: int = 3):
        """
        Initialize the 5-phase workflow tracker.

        Args:
            max_phase_repeats: Maximum times a phase can repeat before flagging
        """
        self.max_phase_repeats = max_phase_repeats
        self.phase_history: dict[str, list[str]] = {}
        self.phase_counts: dict[str, dict[str, int]] = {}
        self._cycle_detector = WorkflowCycleDetector()

    def record_phase_transition(
        self,
        workflow_id: str,
        from_phase: str,
        to_phase: str,
    ) -> None:
        """
        Record a phase transition.

        Args:
            workflow_id: Workflow identifier
            from_phase: Source phase
            to_phase: Target phase
        """
        if workflow_id not in self.phase_history:
            self.phase_history[workflow_id] = []
            self.phase_counts[workflow_id] = {}

        # Record transition
        self.phase_history[workflow_id].append(to_phase)
        self.phase_counts[workflow_id][to_phase] = (
            self.phase_counts[workflow_id].get(to_phase, 0) + 1
        )

        logger.debug(
            "phase_transition_recorded",
            workflow_id=workflow_id,
            from_phase=from_phase,
            to_phase=to_phase,
        )

    def detect_phase_cycle(self, workflow_id: str, next_phase: str) -> bool:
        """
        Detect if transitioning to next phase would create a cycle.

        Args:
            workflow_id: Workflow identifier
            next_phase: Phase to transition to

        Returns:
            True if cycle detected
        """
        if workflow_id not in self.phase_history:
            return False

        history = self.phase_history[workflow_id]

        # Check for phase repetition
        recent_phases = history[-5:]  # Last 5 phases
        if recent_phases.count(next_phase) >= self.max_phase_repeats:
            logger.warning(
                "phase_cycle_detected",
                workflow_id=workflow_id,
                next_phase=next_phase,
                recent_phases=recent_phases,
            )
            return True

        # Use underlying cycle detector for path-based detection
        return self._cycle_detector.detect_cycle(workflow_id, next_phase)

    def get_phase_statistics(self, workflow_id: str) -> dict[str, Any]:
        """
        Get phase statistics for a workflow.

        Args:
            workflow_id: Workflow identifier

        Returns:
            Dictionary of phase statistics
        """
        counts = self.phase_counts.get(workflow_id, {})
        history = self.phase_history.get(workflow_id, [])

        return {
            "total_transitions": len(history),
            "phase_counts": counts,
            "current_phase": history[-1] if history else None,
            "most_visited_phase": max(counts, key=counts.get) if counts else None,
        }
