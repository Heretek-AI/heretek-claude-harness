"""Agent Evaluator Framework for testing agent quality."""

import asyncio
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Optional

import structlog

logger = structlog.get_logger(__name__)

_evaluator_instance: AgentEvaluator | None = None


class EvaluationMetric(Enum):
    """Metrics used to score agent evaluation runs."""

    ACCURACY = "accuracy"
    LATENCY = "latency"
    CONSTRAINT_COMPLIANCE = "constraint_compliance"
    OUTPUT_QUALITY = "output_quality"
    COMPLETENESS = "completeness"


class EvaluationStatus(Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    PASSED = "passed"
    FAILED = "failed"
    SKIPPED = "skipped"


@dataclass
class OutputConstraints:
    max_tokens: int = 1000
    format: str = "text"
    max_length: int | None = None
    required_keys: list[str] | None = None
    forbidden_patterns: list[str] | None = None
    schema: dict[str, Any] | None = None


@dataclass
class TestCase:
    id: str
    name: str
    description: str = ""
    input_data: dict[str, Any] = field(default_factory=dict)
    expected_output: dict[str, Any] | None = None
    constraints: OutputConstraints | None = None
    evaluation_criteria: list[EvaluationMetric] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class MetricResult:
    metric: EvaluationMetric
    score: float
    details: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "metric": self.metric.value,
            "score": self.score,
            "details": self.details,
        }


@dataclass
class TestCaseExecution:
    """Result of running one test case against an agent."""

    test_case: TestCase
    status: EvaluationStatus
    start_time: str
    end_time: str | None = None
    results: list[MetricResult] = field(default_factory=list)
    output: Any = None
    error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "test_case_id": self.test_case.id,
            "test_case_name": self.test_case.name,
            "status": self.status.value,
            "start_time": self.start_time,
            "end_time": self.end_time,
            "results": [r.to_dict() for r in self.results],
            "output": self.output,
            "error": self.error,
        }


@dataclass
class EvaluationResult:
    evaluation_id: str
    agent_id: str
    status: EvaluationStatus
    started_at: str | None = None
    completed_at: str | None = None
    total_time: float = 0.0
    metrics: Optional["EvaluationMetrics"] = None
    test_results: list["TestResult"] | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "evaluation_id": self.evaluation_id,
            "agent_id": self.agent_id,
            "status": self.status.value,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "total_time": self.total_time,
            "metrics": self.metrics.to_dict() if self.metrics else None,
        }


@dataclass
class EvaluationMetrics:
    success_rate: float = 0.0
    constraint_compliance: float = 0.0
    output_quality: float = 0.0
    latency_ms: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "success_rate": self.success_rate,
            "constraint_compliance": self.constraint_compliance,
            "output_quality": self.output_quality,
            "latency_ms": self.latency_ms,
        }


@dataclass
class TestResult:
    test_id: str
    success: bool
    error: Any | None = None
    validation_errors: list[str] | None = None
    execution_time_ms: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "test_id": self.test_id,
            "success": self.success,
            "error": str(self.error) if self.error else None,
            "validation_errors": self.validation_errors or [],
            "execution_time_ms": self.execution_time_ms,
        }


@dataclass
class AgentEvaluationSummary:
    agent_id: str
    total_runs: int = 0
    passed_runs: int = 0
    failed_runs: int = 0
    average_success_rate: float = 0.0
    last_evaluated_at: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "agent_id": self.agent_id,
            "total_runs": self.total_runs,
            "passed_runs": self.passed_runs,
            "failed_runs": self.failed_runs,
            "average_success_rate": self.average_success_rate,
            "last_evaluated_at": self.last_evaluated_at,
        }


def get_evaluator() -> AgentEvaluator:
    """Return the module-level evaluator singleton."""
    global _evaluator_instance
    if _evaluator_instance is None:
        _evaluator_instance = AgentEvaluator()
    return _evaluator_instance


class AgentEvaluator:
    """Agent evaluation framework."""

    def __init__(self, timeout: float = 30.0, parallel: bool = True):
        self.timeout = timeout
        self.parallel = parallel
        self.results: list[EvaluationResult] = []
        self._evaluations: dict[str, EvaluationResult] = {}
        self.test_cases: dict[str, TestCase] = {}
        self._agent_summaries: dict[str, AgentEvaluationSummary] = {}

    def load_test_cases(self, cases: list[TestCase]) -> None:
        """Register test cases for future evaluations."""
        for case in cases:
            self.test_cases[case.id] = case

    async def _run_single_test_case(
        self,
        agent: Any,
        tc: TestCase,
    ) -> tuple[TestResult, bool]:
        """Run a single test case and return result plus success flag."""
        start = datetime.now()  # noqa: DTZ005
        error = None
        validation_errors: list[str] = []

        try:
            input_data = (
                tc.input_data if isinstance(tc.input_data, dict) else {"query": tc.input_data}
            )
            output = await asyncio.wait_for(agent.execute(input_data), timeout=self.timeout)

            if tc.expected_output is not None:
                validation_errors.extend(self._validate_expected_output(output, tc.expected_output))
            if tc.constraints:
                validation_errors.extend(self._validate_constraints(output, tc.constraints))

            success = len(validation_errors) == 0
        except TimeoutError as e:
            error = e
            validation_errors = [f"Execution timeout after {self.timeout}s"]
            success = False
        except Exception as e:
            error = e
            validation_errors = [str(e)]
            success = False

        end = datetime.now()  # noqa: DTZ005
        execution_time = (end - start).total_seconds() * 1000
        return TestResult(
            test_id=tc.id,
            success=success,
            error=error,
            validation_errors=validation_errors if validation_errors else None,
            execution_time_ms=execution_time,
        ), success

    async def evaluate_agent_with_agent(
        self,
        agent_id: str,
        agent: Any,
        test_cases: list[TestCase],
        evaluation_id: str | None = None,
    ) -> EvaluationResult:
        """Evaluate an agent instance against test cases."""
        eval_id = evaluation_id or f"eval_{agent_id}_{datetime.now().timestamp()}"  # noqa: DTZ005
        started = datetime.now().isoformat()  # noqa: DTZ005

        test_results = []
        passed_count = 0

        for tc in test_cases:
            result, success = await self._run_single_test_case(agent, tc)
            test_results.append(result)
            if success:
                passed_count += 1

        total = len(test_cases)
        success_rate = (passed_count / total * 100) if total > 0 else 0.0

        metrics = EvaluationMetrics(
            success_rate=success_rate,
            constraint_compliance=success_rate,
            output_quality=success_rate,
        )

        completed = datetime.now().isoformat()  # noqa: DTZ005
        evaluation = EvaluationResult(
            evaluation_id=eval_id,
            agent_id=agent_id,
            status=EvaluationStatus.PASSED if passed_count == total and total > 0 else EvaluationStatus.FAILED,
            started_at=started,
            completed_at=completed,
            total_time=(
                datetime.fromisoformat(completed) - datetime.fromisoformat(started)
            ).total_seconds(),
            metrics=metrics,
            test_results=test_results,
        )

        self.results.append(evaluation)
        self._evaluations[eval_id] = evaluation
        self._update_summary(agent_id, evaluation)
        return evaluation

    async def evaluate_agent(
        self,
        agent_id: str,
        test_case_ids: list[str] | None = None,
    ) -> list[TestCaseExecution]:
        """Evaluate a supervisor-managed agent by ID (API entry point)."""
        from heretek_swarm.actors.supervisor import get_supervisor

        supervisor = get_supervisor()
        if not supervisor or agent_id not in supervisor.actors:
            raise ValueError(f"Agent not found: {agent_id}")

        agent = supervisor.actors[agent_id]
        if test_case_ids:
            cases = [self.test_cases[tid] for tid in test_case_ids if tid in self.test_cases]
        else:
            cases = list(self.test_cases.values())

        if not cases:
            raise ValueError("No test cases available for evaluation")

        executions: list[TestCaseExecution] = []
        for tc in cases:
            started = datetime.now().isoformat()  # noqa: DTZ005
            test_result, success = await self._run_single_test_case(agent, tc)
            ended = datetime.now().isoformat()  # noqa: DTZ005
            score = 100.0 if success else 0.0
            criteria = tc.evaluation_criteria or [EvaluationMetric.ACCURACY]
            metric_results = [
                MetricResult(metric=m, score=score, details="automated evaluation")
                for m in criteria
            ]
            executions.append(
                TestCaseExecution(
                    test_case=tc,
                    status=EvaluationStatus.PASSED if success else EvaluationStatus.FAILED,
                    start_time=started,
                    end_time=ended,
                    results=metric_results,
                    output=None,
                    error=str(test_result.error) if test_result.error else None,
                )
            )

        passed = sum(1 for e in executions if e.status == EvaluationStatus.PASSED)
        eval_result = EvaluationResult(
            evaluation_id=f"eval_{uuid.uuid4().hex[:12]}",
            agent_id=agent_id,
            status=EvaluationStatus.PASSED if passed == len(executions) else EvaluationStatus.FAILED,
            started_at=executions[0].start_time if executions else None,
            completed_at=executions[-1].end_time if executions else None,
            metrics=EvaluationMetrics(
                success_rate=(passed / len(executions) * 100) if executions else 0.0,
                constraint_compliance=(passed / len(executions) * 100) if executions else 0.0,
                output_quality=(passed / len(executions) * 100) if executions else 0.0,
            ),
        )
        self.results.append(eval_result)
        self._evaluations[eval_result.evaluation_id] = eval_result
        self._update_summary(agent_id, eval_result)
        return executions

    def _update_summary(self, agent_id: str, result: EvaluationResult) -> None:
        summary = self._agent_summaries.get(agent_id) or AgentEvaluationSummary(agent_id=agent_id)
        summary.total_runs += 1
        if result.status == EvaluationStatus.PASSED:
            summary.passed_runs += 1
        else:
            summary.failed_runs += 1
        if result.metrics:
            prior = summary.average_success_rate * (summary.total_runs - 1)
            summary.average_success_rate = (
                prior + result.metrics.success_rate
            ) / summary.total_runs
        summary.last_evaluated_at = result.completed_at
        self._agent_summaries[agent_id] = summary

    def get_agent_summary(self, agent_id: str) -> dict[str, Any]:
        summary = self._agent_summaries.get(agent_id)
        if summary is None:
            return AgentEvaluationSummary(agent_id=agent_id).to_dict()
        return summary.to_dict()

    def get_all_summaries(self) -> list[dict[str, Any]]:
        return [s.to_dict() for s in self._agent_summaries.values()]

    def _validate_expected_output(self, output: Any, expected: dict[str, Any]) -> list[str]:
        """Validate output against expected output."""
        errors = []
        if isinstance(expected, dict) and isinstance(output, dict):
            for key, value in expected.items():
                if key not in output:
                    errors.append(f"Missing expected key: {key}")
                elif output[key] != value:
                    errors.append(f"Expected {key}={value}, got {output[key]}")
        return errors

    def _validate_constraints(self, output: Any, constraints: OutputConstraints) -> list[str]:
        """Validate output against constraints."""
        errors = []

        if constraints.required_keys and isinstance(output, dict):
            for key in constraints.required_keys:
                if key not in output:
                    errors.append(f"Missing required key: {key}")  # noqa: PERF401

        if hasattr(constraints, "max_length") and constraints.max_length:
            output_str = str(output)
            if len(output_str) > constraints.max_length:
                errors.append(
                    f"Output exceeds max length: {len(output_str)} > {constraints.max_length}"
                )

        if constraints.forbidden_patterns and isinstance(output, str):
            import re

            for pattern in constraints.forbidden_patterns:
                if re.search(pattern, output):
                    errors.append("forbidden pattern detected in output")  # noqa: PERF401

        return errors

    def get_evaluation(self, evaluation_id: str) -> EvaluationResult | None:
        """Get evaluation by ID."""
        return self._evaluations.get(evaluation_id)

    def list_evaluations(self) -> list[EvaluationResult]:
        """List all evaluations."""
        return list(self._evaluations.values())

    def compare_agents(self, results: dict[str, EvaluationResult]) -> dict[str, EvaluationMetrics]:
        """Compare evaluation results across agents."""
        comparison = {}
        for agent_id, result in results.items():
            if result.metrics:
                comparison[agent_id] = result.metrics
        return comparison

    def get_stats(self) -> dict[str, Any]:
        """Get evaluation statistics."""
        total = len(self.results)
        passed = sum(1 for r in self.results if r.status == EvaluationStatus.PASSED)
        return {
            "total": total,
            "passed": passed,
            "failed": total - passed,
            "pass_rate": passed / total if total > 0 else 0.0,
        }
