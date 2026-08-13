"""
CrewAI Integration Module for Heretek Swarm

This module provides bi-directional integration between Heretek Swarm agents and CrewAI.
It enables crew task delegation, agent role mapping, process orchestration, and memory sharing.

Features:
- Crew task delegation
- Agent role mapping
- Process orchestration (sequential, hierarchical)
- Memory sharing bridge
- Zero-trust validation of all task assignments

Reference: EXPANSION_ROADMAP.md Session 47 - Integration Ecosystem
"""

import asyncio
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

import structlog

logger = structlog.get_logger(__name__)

# Try to import crewai components
try:
    from crewai import Agent, Crew, Process, Task
    from crewai.task import TaskOutput
    from crewai_tools import BaseTool

    CREWAI_AVAILABLE = True
except ImportError:
    CREWAI_AVAILABLE = False
    Agent = None
    Task = None
    Crew = None
    Process = None
    TaskOutput = None
    BaseTool = None


class CrewProcess(StrEnum):
    """CrewAI process types."""

    SEQUENTIAL = "sequential"
    HIERARCHICAL = "hierarchical"


class TaskStatus(StrEnum):
    """Task execution status."""

    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    DELEGATED = "delegated"


class AgentRole(StrEnum):
    """CrewAI agent roles."""

    RESEARCHER = "researcher"
    ANALYST = "analyst"
    WRITER = "writer"
    DEVELOPER = "developer"
    MANAGER = "manager"
    SPECIALIST = "specialist"
    HERETEK_BRIDGE = "heretek_bridge"


@dataclass
class CrewAgentConfig:
    """
    Configuration for a CrewAI agent.

    Attributes:
        agent_id: Unique agent identifier
        role: Agent role
        goal: Agent goal
        backstory: Agent backstory
        verbose: Enable verbose logging
        allow_delegation: Allow task delegation
        max_iter: Maximum iterations
        max_rpm: Maximum requests per minute
        cache: Enable caching
    """

    agent_id: str
    role: str
    goal: str
    backstory: str = ""
    verbose: bool = True
    allow_delegation: bool = False
    max_iter: int = 15
    max_rpm: int | None = None
    cache: bool = True
    tools: list[Any] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "agent_id": self.agent_id,
            "role": self.role,
            "goal": self.goal,
            "backstory": self.backstory,
            "verbose": self.verbose,
            "allow_delegation": self.allow_delegation,
            "max_iter": self.max_iter,
            "max_rpm": self.max_rpm,
            "cache": self.cache,
            "tool_count": len(self.tools),
            "metadata": self.metadata,
        }


@dataclass
class CrewTaskConfig:
    """
    Configuration for a CrewAI task.

    Attributes:
        task_id: Unique task identifier
        description: Task description
        expected_output: Expected output description
        agent_id: Assigned agent ID
        async_execution: Enable async execution
        context: Task context from previous tasks
        output_file: Output file path
        output_json: Output as JSON
        output_pydantic: Output as Pydantic model
    """

    task_id: str
    description: str
    expected_output: str
    agent_id: str | None = None
    async_execution: bool = False
    context: list[Any] = field(default_factory=list)
    output_file: str | None = None
    output_json: dict[str, Any] | None = None
    output_pydantic: Any | None = None
    tools: list[Any] = field(default_factory=list)
    callback: Callable | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "task_id": self.task_id,
            "description": self.description,
            "expected_output": self.expected_output,
            "agent_id": self.agent_id,
            "async_execution": self.async_execution,
            "context_count": len(self.context),
            "output_file": self.output_file,
            "tool_count": len(self.tools),
            "has_callback": self.callback is not None,
            "metadata": self.metadata,
        }


@dataclass
class TaskExecutionResult:
    """
    Result of task execution.

    Attributes:
        task_id: Task identifier
        status: Execution status
        output: Task output
        agent_id: Executing agent ID
        execution_time_ms: Execution time
        raw: Raw output
        json_dict: JSON output if applicable
    """

    task_id: str
    status: TaskStatus
    output: str | None
    agent_id: str | None
    execution_time_ms: float
    raw: Any | None = None
    json_dict: dict[str, Any] | None = None
    error: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "task_id": self.task_id,
            "status": self.status.value,
            "output": self.output,
            "agent_id": self.agent_id,
            "execution_time_ms": self.execution_time_ms,
            "json_dict": self.json_dict,
            "error": self.error,
            "metadata": self.metadata,
        }


@dataclass
class CrewExecutionResult:
    """
    Result of crew execution.

    Attributes:
        crew_id: Crew identifier
        status: Execution status
        task_results: Results from individual tasks
        execution_time_ms: Total execution time
        token_usage: Token usage statistics
        process_type: Process type used
    """

    crew_id: str
    status: str
    task_results: list[TaskExecutionResult]
    execution_time_ms: float
    token_usage: dict[str, Any] = field(default_factory=dict)
    process_type: CrewProcess = CrewProcess.SEQUENTIAL
    error: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "crew_id": self.crew_id,
            "status": self.status,
            "task_results": [r.to_dict() for r in self.task_results],
            "execution_time_ms": self.execution_time_ms,
            "token_usage": self.token_usage,
            "process_type": self.process_type.value,
            "error": self.error,
            "metadata": self.metadata,
        }


class CrewAIAdapter:
    """
    Adapter for integrating CrewAI with Heretek Swarm.

    This adapter provides:
    - Crew task delegation
    - Agent role mapping between Heretek and CrewAI
    - Process orchestration (sequential, hierarchical)
    - Memory sharing bridge

    Attributes:
        agents: Registered CrewAI agents
        tasks: Registered tasks
        crews: Registered crews
    """

    def __init__(
        self,
        verbose: bool = True,
        memory_enabled: bool = False,
        cache_enabled: bool = True,
        max_rpm: int | None = None,
    ) -> None:
        """
        Initialize the CrewAI adapter.

        Args:
            verbose: Enable verbose logging
            memory_enabled: Enable memory sharing
            cache_enabled: Enable result caching
            max_rpm: Maximum requests per minute
        """
        self.agents: dict[str, Any] = {}
        self.agent_configs: dict[str, CrewAgentConfig] = {}
        self.tasks: dict[str, Any] = {}
        self.task_configs: dict[str, CrewTaskConfig] = {}
        self.task_results: dict[str, TaskExecutionResult] = {}
        self.crews: dict[str, Any] = {}
        self.crew_configs: dict[str, dict[str, Any]] = {}

        self.verbose = verbose
        self.memory_enabled = memory_enabled
        self.cache_enabled = cache_enabled
        self.max_rpm = max_rpm

        # Heretek integration
        self._agent_runtime = None
        self._heretek_agent_mappings: dict[str, str] = {}

        # Task callbacks
        self._task_callbacks: list[Callable] = []

        # Memory bridge
        self._shared_memory: dict[str, Any] = {}

        logger.info(
            "crewai_adapter_initialized",
            verbose=verbose,
            memory_enabled=memory_enabled,
            cache_enabled=cache_enabled,
        )

    def set_agent_runtime(self, runtime: Any) -> None:
        """Set the Heretek agent runtime for integration."""
        self._agent_runtime = runtime
        logger.debug("agent_runtime_set", runtime_type=type(runtime).__name__)

    def register_heretek_agent_mapping(
        self,
        heretek_agent_id: str,
        crewai_agent_id: str,
    ) -> None:
        """Register a mapping between Heretek and CrewAI agents."""
        self._heretek_agent_mappings[heretek_agent_id] = crewai_agent_id
        logger.info(
            "heretek_agent_mapping_registered",
            heretek_agent_id=heretek_agent_id,
            crewai_agent_id=crewai_agent_id,
        )

    def register_task_callback(self, callback: Callable) -> None:
        """Register a callback for task events."""
        self._task_callbacks.append(callback)
        logger.debug("task_callback_registered", callback=callback.__name__)

    async def _notify_task_event(
        self,
        event_type: str,
        task_id: str,
        result: TaskExecutionResult | None = None,
    ) -> None:
        """Notify callbacks of task events."""
        for callback in self._task_callbacks:
            try:
                if asyncio.iscoroutinefunction(callback):
                    await callback(event_type, task_id, result)
                else:
                    callback(event_type, task_id, result)
            except Exception as e:
                logger.error("task_callback_error", error=str(e))

    def create_agent(
        self,
        agent_id: str,
        role: str,
        goal: str,
        backstory: str = "",
        verbose: bool = True,
        allow_delegation: bool = False,
        max_iter: int = 15,
        tools: list[Any] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> Any:
        """
        Create a CrewAI agent.

        Args:
            agent_id: Unique agent identifier
            role: Agent role
            goal: Agent goal
            backstory: Agent backstory
            verbose: Enable verbose logging
            allow_delegation: Allow task delegation
            max_iter: Maximum iterations
            tools: List of tools
            metadata: Additional metadata

        Returns:
            Created CrewAI Agent
        """
        if not CREWAI_AVAILABLE:
            logger.warning("crewai_not_available")
            raise RuntimeError("CrewAI is not available. Install with: pip install crewai")

        config = CrewAgentConfig(
            agent_id=agent_id,
            role=role,
            goal=goal,
            backstory=backstory,
            verbose=verbose,
            allow_delegation=allow_delegation,
            max_iter=max_iter,
            max_rpm=self.max_rpm,
            cache=self.cache_enabled,
            tools=tools or [],
            metadata=metadata or {},
        )
        self.agent_configs[agent_id] = config

        # Create CrewAI agent
        agent = Agent(
            role=role,
            goal=goal,
            backstory=backstory,
            verbose=verbose,
            allow_delegation=allow_delegation,
            max_iter=max_iter,
            max_rpm=self.max_rpm,
            cache=self.cache_enabled,
            tools=tools or [],
        )

        self.agents[agent_id] = agent
        logger.info(
            "agent_created",
            agent_id=agent_id,
            role=role,
        )

        return agent

    def create_heretek_bridge_agent(
        self,
        agent_id: str,
        heretek_agent_id: str,
        role: str = "Heretek Bridge Agent",
        goal: str = "Coordinate with Heretek swarm agents",
        backstory: str = "You are a bridge between CrewAI and Heretek Swarm systems.",
    ) -> Any:
        """
        Create a bridge agent that connects to a Heretek agent.

        Args:
            agent_id: CrewAI agent ID
            heretek_agent_id: Corresponding Heretek agent ID
            role: Agent role
            goal: Agent goal
            backstory: Agent backstory

        Returns:
            Created bridge agent
        """
        # Register mapping
        self.register_heretek_agent_mapping(heretek_agent_id, agent_id)

        # Create agent with custom handler for Heretek integration
        agent = self.create_agent(
            agent_id=agent_id,
            role=role,
            goal=goal,
            backstory=backstory,
            allow_delegation=True,
        )

        logger.info(
            "heretek_bridge_agent_created",
            agent_id=agent_id,
            heretek_agent_id=heretek_agent_id,
        )

        return agent

    def create_task(
        self,
        task_id: str,
        description: str,
        expected_output: str,
        agent_id: str | None = None,
        async_execution: bool = False,
        context: list[str] | None = None,
        tools: list[Any] | None = None,
        callback: Callable[[TaskOutput], None] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> Any:
        """
        Create a CrewAI task.

        Args:
            task_id: Unique task identifier
            description: Task description
            expected_output: Expected output description
            agent_id: Assigned agent ID
            async_execution: Enable async execution
            context: Context from previous task outputs
            tools: List of tools
            callback: Completion callback
            metadata: Additional metadata

        Returns:
            Created CrewAI Task
        """
        if not CREWAI_AVAILABLE:
            raise RuntimeError("CrewAI is not available")

        # Get context tasks if provided
        context_tasks = []
        if context:
            for ctx_task_id in context:
                if ctx_task_id in self.tasks:
                    context_tasks.append(self.tasks[ctx_task_id])  # noqa: PERF401

        # Get agent if specified
        agent = None
        if agent_id and agent_id in self.agents:
            agent = self.agents[agent_id]

        config = CrewTaskConfig(
            task_id=task_id,
            description=description,
            expected_output=expected_output,
            agent_id=agent_id,
            async_execution=async_execution,
            context=context_tasks,
            tools=tools or [],
            callback=callback,
            metadata=metadata or {},
        )
        self.task_configs[task_id] = config

        # Create CrewAI task
        task = Task(
            description=description,
            expected_output=expected_output,
            agent=agent,
            async_execution=async_execution,
            context=context_tasks if context_tasks else None,
            tools=tools or [],
            output_file=config.output_file,
        )

        self.tasks[task_id] = task
        logger.info(
            "task_created",
            task_id=task_id,
            agent_id=agent_id,
        )

        return task

    def create_crew(
        self,
        crew_id: str,
        name: str,
        agent_ids: list[str],
        task_ids: list[str],
        process: CrewProcess = CrewProcess.SEQUENTIAL,
        verbose: bool = True,
        memory: Any | None = None,
        cache: bool = True,
        max_rpm: int | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> Any:
        """
        Create a CrewAI crew.

        Args:
            crew_id: Unique crew identifier
            name: Crew name
            agent_ids: List of agent IDs
            task_ids: List of task IDs
            process: Process type (sequential/hierarchical)
            verbose: Enable verbose logging
            memory: Optional memory instance
            cache: Enable caching
            max_rpm: Maximum requests per minute
            metadata: Additional metadata

        Returns:
            Created CrewAI Crew
        """
        if not CREWAI_AVAILABLE:
            raise RuntimeError("CrewAI is not available")

        # Get agents and tasks
        agents = [self.agents[aid] for aid in agent_ids if aid in self.agents]
        tasks = [self.tasks[tid] for tid in task_ids if tid in self.tasks]

        if not agents:
            raise ValueError(f"No valid agents found for IDs: {agent_ids}")
        if not tasks:
            raise ValueError(f"No valid tasks found for IDs: {task_ids}")

        # Convert process type
        crew_process = (
            Process.SEQUENTIAL if process == CrewProcess.SEQUENTIAL else Process.HIERARCHICAL
        )

        config = {
            "crew_id": crew_id,
            "name": name,
            "agent_ids": agent_ids,
            "task_ids": task_ids,
            "process": process,
            "verbose": verbose,
            "memory": memory,
            "cache": cache,
            "max_rpm": max_rpm or self.max_rpm,
            "metadata": metadata or {},
        }
        self.crew_configs[crew_id] = config

        # Create CrewAI crew
        crew = Crew(
            agents=agents,
            tasks=tasks,
            process=crew_process,
            verbose=verbose,
            memory=memory if memory else self.memory_enabled,
            cache=cache,
            max_rpm=max_rpm or self.max_rpm,
        )

        self.crews[crew_id] = crew
        logger.info(
            "crew_created",
            crew_id=crew_id,
            agent_count=len(agents),
            task_count=len(tasks),
            process=process.value,
        )

        return crew

    async def execute_task(
        self,
        task_id: str,
        context: dict[str, Any] | None = None,
    ) -> TaskExecutionResult:
        """
        Execute a single task.

        Args:
            task_id: Task to execute
            context: Optional context for execution

        Returns:
            TaskExecutionResult
        """
        if task_id not in self.tasks:
            raise ValueError(f"Task {task_id} not found")

        start_time = datetime.now(UTC)
        config = self.task_configs.get(
            task_id,
            CrewTaskConfig(
                task_id=task_id,
                description="",
                expected_output="",
            ),
        )

        result = TaskExecutionResult(
            task_id=task_id,
            status=TaskStatus.IN_PROGRESS,
            output=None,
            agent_id=config.agent_id,
            execution_time_ms=0,
        )

        try:
            task = self.tasks[task_id]

            # Notify task start
            await self._notify_task_event("task_started", task_id, result)

            # Execute task (synchronously for now, as CrewAI doesn't have native async)
            loop = asyncio.get_event_loop()
            output = await loop.run_in_executor(None, task.execute, context)

            end_time = datetime.now(UTC)
            execution_time_ms = (end_time - start_time).total_seconds() * 1000

            result.status = TaskStatus.COMPLETED
            result.output = str(output) if output else ""
            result.raw = output
            result.execution_time_ms = execution_time_ms

            if hasattr(output, "json_dict"):
                result.json_dict = output.json_dict

            # Store result
            self.task_results[task_id] = result

            # Notify task completion
            await self._notify_task_event("task_completed", task_id, result)

            logger.info(
                "task_executed",
                task_id=task_id,
                status=TaskStatus.COMPLETED.value,
                execution_time_ms=execution_time_ms,
            )

        except Exception as e:
            end_time = datetime.now(UTC)
            execution_time_ms = (end_time - start_time).total_seconds() * 1000

            result.status = TaskStatus.FAILED
            result.error = str(e)
            result.execution_time_ms = execution_time_ms

            self.task_results[task_id] = result

            await self._notify_task_event("task_failed", task_id, result)

            logger.error("task_execution_failed", task_id=task_id, error=str(e))

        return result

    async def execute_crew(
        self,
        crew_id: str,
        inputs: dict[str, Any] | None = None,
    ) -> CrewExecutionResult:
        """
        Execute a crew.

        Args:
            crew_id: Crew to execute
            inputs: Optional inputs for the crew

        Returns:
            CrewExecutionResult
        """
        if crew_id not in self.crews:
            raise ValueError(f"Crew {crew_id} not found")

        start_time = datetime.now(UTC)
        config = self.crew_configs.get(crew_id, {})
        process_type = config.get("process", CrewProcess.SEQUENTIAL)

        task_results: list[TaskExecutionResult] = []
        error: str | None = None
        status = "running"
        token_usage: dict[str, Any] = {}

        try:
            crew = self.crews[crew_id]

            logger.info("crew_execution_started", crew_id=crew_id)

            # Execute crew (synchronously for now)
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(None, crew.kickoff, inputs)

            end_time = datetime.now(UTC)
            execution_time_ms = (end_time - start_time).total_seconds() * 1000

            # Collect task results
            for task_id in config.get("task_ids", []):
                if task_id in self.task_results:
                    task_results.append(self.task_results[task_id])  # noqa: PERF401

            status = "completed"

            # Extract token usage if available
            if hasattr(result, "token_usage"):
                token_usage = result.token_usage

            logger.info(
                "crew_execution_completed",
                crew_id=crew_id,
                execution_time_ms=execution_time_ms,
            )

            return CrewExecutionResult(
                crew_id=crew_id,
                status=status,
                task_results=task_results,
                execution_time_ms=execution_time_ms,
                token_usage=token_usage,
                process_type=process_type,
            )

        except Exception as e:
            end_time = datetime.now(UTC)
            execution_time_ms = (end_time - start_time).total_seconds() * 1000

            status = "failed"
            error = str(e)

            logger.error("crew_execution_failed", crew_id=crew_id, error=str(e))

            return CrewExecutionResult(
                crew_id=crew_id,
                status=status,
                task_results=task_results,
                execution_time_ms=execution_time_ms,
                token_usage=token_usage,
                process_type=process_type,
                error=error,
            )

    def share_memory(self, key: str, value: Any, heretek_agents: list[str] | None = None) -> None:
        """
        Share memory between CrewAI and Heretek agents.

        Args:
            key: Memory key
            value: Memory value
            heretek_agents: List of Heretek agents to share with
        """
        self._shared_memory[key] = value

        # Share with Heretek agents if specified
        if heretek_agents and self._agent_runtime:
            for agent_id in heretek_agents:
                if agent_id in self._agent_runtime:
                    runtime = self._agent_runtime[agent_id]
                    if hasattr(runtime, "update_context"):
                        asyncio.create_task(runtime.update_context({f"crewai_{key}": value}))  # noqa: RUF006

        logger.info("memory_shared", key=key, heretek_agents=heretek_agents)

    def get_memory(self, key: str) -> Any | None:
        """Get a shared memory value."""
        return self._shared_memory.get(key)

    def get_shared_memory_status(self) -> dict[str, Any]:
        """Get shared memory status."""
        return {
            "memory_keys": list(self._shared_memory.keys()),
            "memory_count": len(self._shared_memory),
            "heretek_mappings": len(self._heretek_agent_mappings),
        }

    def get_agent(self, agent_id: str) -> Any | None:
        """Get an agent by ID."""
        return self.agents.get(agent_id)

    def get_agent_config(self, agent_id: str) -> CrewAgentConfig | None:
        """Get agent configuration."""
        return self.agent_configs.get(agent_id)

    def get_task(self, task_id: str) -> Any | None:
        """Get a task by ID."""
        return self.tasks.get(task_id)

    def get_task_config(self, task_id: str) -> CrewTaskConfig | None:
        """Get task configuration."""
        return self.task_configs.get(task_id)

    def get_task_result(self, task_id: str) -> TaskExecutionResult | None:
        """Get task execution result."""
        return self.task_results.get(task_id)

    def get_crew(self, crew_id: str) -> Any | None:
        """Get a crew by ID."""
        return self.crews.get(crew_id)

    def get_statistics(self) -> dict[str, Any]:
        """Get adapter statistics."""
        return {
            "agent_count": len(self.agents),
            "task_count": len(self.tasks),
            "crew_count": len(self.crews),
            "heretek_mappings": len(self._heretek_agent_mappings),
            "shared_memory_count": len(self._shared_memory),
            "crewai_available": CREWAI_AVAILABLE,
            "memory_enabled": self.memory_enabled,
            "cache_enabled": self.cache_enabled,
        }

    def clear_agent(self, agent_id: str) -> bool:
        """Clear an agent."""
        if agent_id not in self.agents:
            return False

        if agent_id in self.agents:
            del self.agents[agent_id]
        if agent_id in self.agent_configs:
            del self.agent_configs[agent_id]

        # Remove from mappings
        heretek_id = None
        for h_id, c_id in self._heretek_agent_mappings.items():
            if c_id == agent_id:
                heretek_id = h_id
                break
        if heretek_id:
            del self._heretek_agent_mappings[heretek_id]

        logger.info("agent_cleared", agent_id=agent_id)
        return True

    def clear_task(self, task_id: str) -> bool:
        """Clear a task."""
        if task_id not in self.tasks:
            return False

        if task_id in self.tasks:
            del self.tasks[task_id]
        if task_id in self.task_configs:
            del self.task_configs[task_id]
        if task_id in self.task_results:
            del self.task_results[task_id]

        logger.info("task_cleared", task_id=task_id)
        return True

    def clear_crew(self, crew_id: str) -> bool:
        """Clear a crew."""
        if crew_id not in self.crews:
            return False

        if crew_id in self.crews:
            del self.crews[crew_id]
        if crew_id in self.crew_configs:
            del self.crew_configs[crew_id]

        logger.info("crew_cleared", crew_id=crew_id)
        return True

    def clear_all(self) -> None:
        """Clear all agents, tasks, crews, and state."""
        self.agents.clear()
        self.agent_configs.clear()
        self.tasks.clear()
        self.task_configs.clear()
        self.task_results.clear()
        self.crews.clear()
        self.crew_configs.clear()
        self._shared_memory.clear()
        self._heretek_agent_mappings.clear()
        logger.info("crewai_adapter_cleared")


# Global adapter instance
crewai_adapter: CrewAIAdapter | None = None


def get_crewai_adapter() -> CrewAIAdapter:
    """Get the global CrewAI adapter instance."""
    global crewai_adapter
    if crewai_adapter is None:
        crewai_adapter = CrewAIAdapter()
    return crewai_adapter


def create_sequential_crew(
    crew_id: str,
    name: str,
    agents: list[dict[str, str]],
    tasks: list[dict[str, str]],
) -> CrewAIAdapter:
    """
    Create a sequential crew from configuration.

    Args:
        crew_id: Crew identifier
        name: Crew name
        agents: List of agent configs (role, goal, backstory)
        tasks: List of task configs (description, expected_output)

    Returns:
        Configured CrewAIAdapter
    """
    adapter = get_crewai_adapter()

    # Create agents
    agent_ids = []
    for i, agent_config in enumerate(agents):
        agent_id = f"{crew_id}_agent_{i}"
        adapter.create_agent(
            agent_id=agent_id,
            role=agent_config.get("role", "Assistant"),
            goal=agent_config.get("goal", "Help the user"),
            backstory=agent_config.get("backstory", ""),
        )
        agent_ids.append(agent_id)

    # Create tasks
    task_ids = []
    prev_task_id = None
    for i, task_config in enumerate(tasks):
        task_id = f"{crew_id}_task_{i}"
        context = [prev_task_id] if prev_task_id else None
        adapter.create_task(
            task_id=task_id,
            description=task_config.get("description", ""),
            expected_output=task_config.get("expected_output", ""),
            agent_id=agent_ids[i % len(agent_ids)],
            context=context,
        )
        task_ids.append(task_id)
        prev_task_id = task_id

    # Create crew
    adapter.create_crew(
        crew_id=crew_id,
        name=name,
        agent_ids=agent_ids,
        task_ids=task_ids,
        process=CrewProcess.SEQUENTIAL,
    )

    logger.info("sequential_crew_created", crew_id=crew_id)
    return adapter
