"""
Workflow Data Models

Pure data classes, enums, and helper functions for workflow definitions.
Extracted from engine.py to keep the engine focused on execution logic.

Provides:
- SafeExpressionEvaluator for secure expression evaluation
- WorkflowState TypedDict for state management
- Enums: WorkflowStatus, NodeStatus
- Dataclasses: WorkflowNode, WorkflowEdge, Workflow, WorkflowContext,
  NodeResult, WorkflowResult
- State merge utilities
"""

import ast
import operator
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
from typing import Annotated, Any, TypeVar

import structlog
from typing_extensions import TypedDict

logger = structlog.get_logger(__name__)

# Safe operators for comparison and boolean logic
SAFE_OPERATORS = {
    ast.Eq: operator.eq,
    ast.NotEq: operator.ne,
    ast.Lt: operator.lt,
    ast.LtE: operator.le,
    ast.Gt: operator.gt,
    ast.GtE: operator.ge,
    ast.Is: operator.is_,
    ast.IsNot: operator.is_not,
    ast.In: lambda x, y: x in y,
    ast.NotIn: lambda x, y: x not in y,
}

SAFE_BOOL_OPS = {
    ast.And: lambda x, y: x and y,
    ast.Or: lambda x, y: x or y,
}

SAFE_UNARY_OPS = {
    ast.Not: operator.not_,
    ast.USub: operator.neg,
    ast.UAdd: operator.pos,
}


class SafeExpressionEvaluator:
    """
    Safe expression evaluator using AST validation.

    This class provides a secure alternative to eval() by:
    1. Parsing expressions into an AST
    2. Validating that only safe node types are present
    3. Rejecting dangerous operations (function calls, attribute access, imports)
    4. Safely evaluating the validated AST

    Supported operations:
    - Literal values (numbers, strings, booleans, None, lists, dicts, tuples)
    - Comparison operators (==, !=, <, <=, >, >=, is, in)
    - Boolean operators (and, or, not)
    - Unary operators (+, -, not)
    - Variable substitution (via context)

    Security: Prevents code injection through object introspection attacks
    by never allowing execution of arbitrary Python code.
    """

    # AST node types that are safe to evaluate
    SAFE_NODE_TYPES = (
        ast.Expression,
        ast.Constant,  # Literal values (Python 3.8+)
        ast.List,
        ast.Tuple,
        ast.Dict,
        ast.Compare,
        ast.BoolOp,
        ast.UnaryOp,
        ast.BinOp,
        ast.Name,  # Variable names (validated against allowed context)
        ast.Subscript,  # Indexing (e.g., list[0], dict['key'])
        # Context nodes (required for variable access)
        ast.Load,
        ast.Store,
        ast.Del,
        # Boolean operator nodes
        ast.And,
        ast.Or,
        # Comparison operator nodes
        ast.Eq,
        ast.NotEq,
        ast.Lt,
        ast.LtE,
        ast.Gt,
        ast.GtE,
        ast.Is,
        ast.IsNot,
        ast.In,
        ast.NotIn,
        # Binary operator nodes
        ast.Add,
        ast.Sub,
        ast.Mult,
        ast.Div,
        ast.FloorDiv,
        ast.Mod,
        ast.Pow,
        # Unary operator nodes
        ast.Not,
        ast.USub,
        ast.UAdd,
    )

    # Safe binary operators
    SAFE_BIN_OPS = {
        ast.Add: operator.add,
        ast.Sub: operator.sub,
        ast.Mult: operator.mul,
        ast.Div: operator.truediv,
        ast.FloorDiv: operator.floordiv,
        ast.Mod: operator.mod,
        ast.Pow: operator.pow,
    }

    def __init__(self, allowed_variables: dict[str, Any] | None = None):
        """
        Initialize the evaluator with allowed variables.

        Args:
            allowed_variables: Dict of variable names to values that can be
                               referenced in expressions
        """
        self.allowed_variables = allowed_variables or {}

    def validate_and_eval(self, expr: str) -> Any:
        """
        Safely validate and evaluate an expression.

        Args:
            expr: Expression string to evaluate

        Returns:
            Result of the evaluation

        Raises:
            ValueError: If expression contains unsafe operations
            SyntaxError: If expression is not valid Python syntax
        """
        # Parse the expression into an AST
        try:
            tree = ast.parse(expr, mode="eval")
        except SyntaxError as e:
            raise ValueError(f"Invalid expression syntax: {e}") from e

        # Validate the AST contains only safe nodes
        self._validate_ast(tree)

        # Safely evaluate the validated AST
        return self._eval_node(tree.body)

    def _validate_ast(self, node: ast.AST) -> None:
        """
        Recursively validate that an AST contains only safe node types.

        Args:
            node: AST node to validate

        Raises:
            ValueError: If node contains unsafe operations
        """
        # Check if this node type is safe
        if not isinstance(node, self.SAFE_NODE_TYPES):
            raise ValueError(
                f"Unsafe node type '{type(node).__name__}' in expression. "
                f"Only literals, comparisons, and boolean logic are allowed."
            )

        # Special validation for Name nodes (variable access)
        if isinstance(node, ast.Name) and node.id not in self.allowed_variables:
            raise ValueError(
                f"Variable '{node.id}' is not in the allowed variables list. "
                f"Allowed: {list(self.allowed_variables.keys())}"
            )

        # Recursively validate all child nodes
        for _field, value in ast.iter_fields(node):
            if isinstance(value, list):
                for item in value:
                    if isinstance(item, ast.AST):
                        self._validate_ast(item)
            elif isinstance(value, ast.AST):
                self._validate_ast(value)

    def _eval_node(self, node: ast.AST) -> Any:
        """
        Recursively evaluate a validated AST node.

        Args:
            node: AST node to evaluate

        Returns:
            Result of evaluating the node

        Raises:
            ValueError: If node type is not supported
        """
        # Handle literal values
        if isinstance(node, ast.Constant):  # Python 3.8+
            return node.value

        # Handle variable references
        if isinstance(node, ast.Name):
            return self.allowed_variables[node.id]

        # Handle lists
        if isinstance(node, ast.List):
            return [self._eval_node(elt) for elt in node.elts]

        # Handle tuples
        if isinstance(node, ast.Tuple):
            return tuple(self._eval_node(elt) for elt in node.elts)

        # Handle dicts
        if isinstance(node, ast.Dict):
            return {
                self._eval_node(k): self._eval_node(v)
                for k, v in zip(node.keys, node.values, strict=False)
                if k is not None
            }

        # Handle comparison operations
        if isinstance(node, ast.Compare):
            left = self._eval_node(node.left)
            result = True
            for op, comparator in zip(node.ops, node.comparators, strict=False):
                op_func = SAFE_OPERATORS.get(type(op))
                if op_func is None:
                    raise ValueError(f"Unsupported comparison operator: {type(op).__name__}")
                right = self._eval_node(comparator)
                result = result and op_func(left, right)
                left = right
            return result

        # Handle boolean operations (and, or)
        if isinstance(node, ast.BoolOp):
            op_func = SAFE_BOOL_OPS.get(type(node.op))
            if op_func is None:
                raise ValueError(f"Unsupported boolean operator: {type(node.op).__name__}")
            result = self._eval_node(node.values[0])
            for value in node.values[1:]:
                result = op_func(result, self._eval_node(value))
            return result

        # Handle unary operations (not, -, +)
        if isinstance(node, ast.UnaryOp):
            op_func = SAFE_UNARY_OPS.get(type(node.op))
            if op_func is None:
                raise ValueError(f"Unsupported unary operator: {type(node.op).__name__}")
            return op_func(self._eval_node(node.operand))

        # Handle binary operations (+, -, *, /, etc.)
        if isinstance(node, ast.BinOp):
            op_func = self.SAFE_BIN_OPS.get(type(node.op))
            if op_func is None:
                raise ValueError(f"Unsupported binary operator: {type(node.op).__name__}")
            left = self._eval_node(node.left)
            right = self._eval_node(node.right)
            return op_func(left, right)

        # Handle subscript (indexing)
        if isinstance(node, ast.Subscript):
            value = self._eval_node(node.value)
            slice_val = self._eval_node(node.slice)
            return value[slice_val]

        raise ValueError(f"Unsupported node type: {type(node).__name__}")


class WorkflowState(TypedDict, total=False):
    """
    Typed workflow state with annotations for state transitions.

    LangGraph pattern: Uses Annotated types to specify how state fields
    should be updated during workflow execution.

    Attributes:
        messages: List of messages (append-only accumulation)
        results: Dict of node results (merge updates)
        current_phase: Current workflow phase identifier
        metadata: Additional metadata dict
        checkpoint: Optional checkpoint for resumption
        cycle_count: Counter for cycle detection
    """

    messages: Annotated[list[dict[str, Any]], "append"]
    results: Annotated[dict[str, Any], "merge"]
    current_phase: str
    metadata: dict[str, Any]
    checkpoint: dict[str, Any] | None
    cycle_count: int


# Type variable for generic workflow state
T = TypeVar("T", bound=WorkflowState)


class WorkflowStatus(Enum):
    """Workflow execution states."""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    PAUSED = "paused"
    CANCELLED = "cancelled"


class NodeStatus(Enum):
    """Node execution states."""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


@dataclass
class WorkflowNode:
    """
    A node in a workflow.

    Attributes:
        id: Unique node identifier
        type: Node type (agent, tool, chain, etc.)
        data: Node configuration data
        inputs: List of input node IDs
        outputs: List of output node IDs
        position: Position on canvas
    """

    id: str
    type: str
    data: dict[str, Any]
    inputs: list[str] = field(default_factory=list)
    outputs: list[str] = field(default_factory=list)
    position: dict[str, float] = field(default_factory=dict)


@dataclass
class WorkflowEdge:
    """
    A connection between two nodes.

    Attributes:
        id: Unique edge identifier
        source: Source node ID
        target: Target node ID
        condition: Optional condition for execution
    """

    id: str
    source: str
    target: str
    condition: str | None = None


@dataclass
class Workflow:
    """
    A complete workflow definition.

    Attributes:
        id: Unique workflow identifier
        name: Workflow name
        nodes: List of workflow nodes
        edges: List of workflow edges
        metadata: Additional metadata
        created_at: Creation timestamp
    """

    id: str
    name: str
    nodes: list[WorkflowNode]
    edges: list[WorkflowEdge]
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: str = field(default_factory=lambda: datetime.now(UTC).isoformat())


def _merge_state_field(current: Any, update: Any, annotation: str) -> Any:
    """
    Merge a state field based on its annotation type.

    LangGraph pattern: Uses annotations to specify how fields should be updated.

    Args:
        current: Current field value
        update: New value to merge
        annotation: Annotation type ("append", "merge", "replace")

    Returns:
        Merged field value
    """
    if annotation == "append":
        # Append-only accumulation (for messages lists)
        if isinstance(current, list) and isinstance(update, list):
            return current + update
        return update
    if annotation == "merge":
        # Dict merge (for results dicts)
        if isinstance(current, dict) and isinstance(update, dict):
            return {**current, **update}
        return update

    return update


def merge_workflow_states(
    current: WorkflowState,
    update: WorkflowState,
) -> WorkflowState:
    """
    Merge two workflow states using Annotated type hints.

    LangGraph pattern: Applies state transition rules based on field annotations.

    Args:
        current: Current workflow state
        update: State updates to apply

    Returns:
        New merged workflow state
    """
    result: WorkflowState = {}

    # Get all keys from both states
    all_keys = set(current.keys()) | set(update.keys())

    for key in all_keys:
        if key in update and key in current:
            # Both have this key - apply merge logic
            if key == "messages":
                result["messages"] = _merge_state_field(
                    current.get("messages", []), update.get("messages", []), "append"
                )
            elif key == "results":
                result["results"] = _merge_state_field(
                    current.get("results", {}), update.get("results", {}), "merge"
                )
            else:
                # Default: use update value
                result[key] = update[key]
        elif key in update:
            result[key] = update[key]
        else:
            result[key] = current[key]

    return result


@dataclass
class WorkflowContext:
    """
    Execution context for a workflow.

    Supports LangGraph-style typed state with checkpointing for resumption.

    Attributes:
        workflow_id: Workflow ID
        execution_id: Unique execution ID
        node_results: Results from executed nodes
        variables: Runtime variables
        start_time: Execution start time
        state: Current workflow state (TypedDict)
        checkpoints: List of checkpoints for resumption
        error: Optional error if failed
    """

    workflow_id: str
    execution_id: str
    node_results: dict[str, Any] = field(default_factory=dict)
    variables: dict[str, Any] = field(default_factory=dict)
    start_time: datetime = field(default_factory=lambda: datetime.now(UTC))
    state: WorkflowStatus = field(default_factory=lambda: WorkflowStatus.PENDING)
    checkpoints: list[dict[str, Any]] = field(default_factory=list)
    error: Exception | None = None


@dataclass
class NodeResult:
    """
    Result from executing a node.

    Attributes:
        node_id: Node ID
        status: Execution status
        output: Node output
        error: Optional error if failed
        execution_time: Time taken to execute
    """

    node_id: str
    status: NodeStatus
    output: Any = None
    error: Exception | None = None
    execution_time: float = 0.0


@dataclass
class WorkflowResult:
    """
    Result from executing a workflow.

    Attributes:
        workflow_id: Workflow ID
        execution_id: Execution ID
        status: Final workflow status
        node_results: All node results
        variables: Final variables
        start_time: Start time
        end_time: End time
        error: Optional error if workflow failed
    """

    workflow_id: str
    execution_id: str
    status: WorkflowStatus
    node_results: dict[str, NodeResult]
    variables: dict[str, Any]
    start_time: datetime
    end_time: datetime | None = None
    error: Exception | None = None
