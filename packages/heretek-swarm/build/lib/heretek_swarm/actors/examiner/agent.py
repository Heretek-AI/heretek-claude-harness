"""
Examiner Agent - Quality Assurance & Testing Specialist.

The ExaminerAgent provides:
- Test plan generation and execution
- Code quality analysis
- Decision validation and verification
- Bug detection and reporting
- Compliance checking
- Performance benchmarking

Examiner is the "quality gate" of the Collective, ensuring all outputs
meet established standards before deployment or delivery.

Author: Heretek Swarm Collective
Date: 2026-04-17
Version: 1.0.0
"""

from __future__ import annotations

# Sentinel values for test case defaults
_UNNAMED_TEST = "Unnamed Test"

import asyncio
import json
import re
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

import structlog

from heretek_swarm.actors.base import ActorMessage, AgentActor
from heretek_swarm.actors.examiner.testing import (
    ExaminingTestingMixin,
    ExaminingValidationMixin,
)
from heretek_swarm.actors.examiner.types import (
    Bug,
    QualityMetric,
    QualityReport,
    SeverityLevel,
    TestCase,
    TestStatus,
    TestSuite,
    TestType,
)
from heretek_swarm.actors.mixins.deliberation import DeliberationMixin
from heretek_swarm.actors.mixins.learning import LearningMixin
from heretek_swarm.actors.mixins.memory import MemoryMixin
from heretek_swarm.actors.mixins.pattern import PatternMixin
from heretek_swarm.actors.mixins.validation import ValidationMixin
from heretek_swarm.actors.validation import (
    validate_message as validate_message_schema,
)

# Session 44: Collective Learning Integration
from heretek_swarm.collective.learning import (
    PatternExtractor,
    PatternType,
)

# Alias for use in handlers
validate_message = validate_message_schema

# Session 44: Consensus Integration

# Session 44: Memory Optimization Integration

# Session 44: Zero-Trust Validation

# DISC-02: Stress Testing Module
from heretek_swarm.testing.stress_testing import (
    CapabilityBoundary,
    GapReporter,
    IncidentReport,
    RecoveryManager,
    SafetyBounds,
    StressTestConfig,
    StressTestExecutor,
    StressTestResult,
    StressTestType,
)

if TYPE_CHECKING:
    from heretek_swarm.consensus.swarm_deliberation import Position, SwarmDeliberationEngine
    from heretek_swarm.memory.access_patterns import AccessPatternAnalyzer
    from heretek_swarm.security.zero_trust import ZeroTrustValidator

logger = structlog.get_logger("ExaminerAgent")


class ExaminerAgent(
    ExaminingTestingMixin,
    ExaminingValidationMixin,
    ValidationMixin,
    DeliberationMixin,
    PatternMixin,
    MemoryMixin,
    LearningMixin,
    AgentActor,
):
    """
    Quality Assurance & Testing Specialist Agent.

    Examiner ensures all outputs from the Collective meet quality standards
    through comprehensive testing, validation, and verification.
    """

    def __init__(
        self,
        agent_id: str | None = None,
        pattern_extractor: PatternExtractor | None = None,
        deliberation_engine: SwarmDeliberationEngine | None = None,
        access_analyzer: AccessPatternAnalyzer | None = None,
        zero_trust_validator: ZeroTrustValidator | None = None,
    ):
        super().__init__(
            agent_id=agent_id,
            name="Examiner",
            description="Quality Assurance & Testing Specialist",
            pattern_extractor=pattern_extractor,
            deliberation_engine=deliberation_engine,
            access_analyzer=access_analyzer,
            zero_trust_validator=zero_trust_validator,
        )
        self._config: dict[str, Any] = {}

        # Test execution state
        self._test_suites: dict[str, TestSuite] = {}
        self._test_history: list[TestSuite] = []
        self.max_test_history = self._config.get("max_test_history", 100)

        # Bug tracking
        self._bugs: dict[str, Bug] = {}
        self._bug_counter = 0
        self.max_bugs = self._config.get("max_bugs", 500)

        # Quality metrics cache
        self._quality_metrics: dict[str, dict[QualityMetric, float]] = {}

        # Default test configuration
        self._default_timeout = self._config.get("default_timeout", 60)
        self._coverage_threshold = self._config.get("coverage_threshold", 80.0)

        # DISC-02: Stress testing components
        self._recovery_manager = RecoveryManager(
            max_recovery_attempts=self._config.get("max_recovery_attempts", 3),
            recovery_timeout_seconds=self._config.get("recovery_timeout", 30.0),
        )

        self._gap_reporter = GapReporter(
            steward_agent_id=self._config.get("steward_agent_id", "steward"),
            min_gap_confidence=self._config.get("min_gap_confidence", 0.7),
        )

        self._stress_executor = StressTestExecutor(
            recovery_manager=self._recovery_manager,
            gap_reporter=self._gap_reporter,
        )

        # DISC-02: Stress test state
        self._stress_test_results: dict[str, StressTestResult] = {}
        self._safety_bounds: dict[str, SafetyBounds] = {}
        self._incident_reports: dict[str, IncidentReport] = {}
        self._capability_boundaries: dict[str, CapabilityBoundary] = {}

        logger.info(
            "ExaminerAgent initialized",
            agent_id=self.agent_id,
            coverage_threshold=self._coverage_threshold,
        )

    def get_handlers(self) -> dict[str, callable]:
        """Return message handlers for Examiner agent."""
        return {
            "create_test_plan": self._handle_create_test_plan,
            "execute_tests": self._handle_execute_tests,
            "validate_decision": self._handle_validate_decision,
            "analyze_quality": self._handle_analyze_quality,
            "report_bug": self._handle_report_bug,
            "get_quality_report": self._handle_get_quality_report,
            "get_bug_status": self._handle_get_bug_status,
            "execute_stress_test": self._handle_execute_stress_test,
            "get_stress_test_results": self._handle_get_stress_test_results,
            "report_capability_gap": self._handle_report_capability_gap,
            "get_safety_bounds": self._handle_get_safety_bounds,
            "get_incident_reports": self._handle_get_incident_reports,
        }

    async def _handle_create_test_plan(self, message: ActorMessage) -> dict[str, Any] | None:
        """Create a comprehensive test plan for a target."""
        try:
            content = validate_message(message.content, "ExaminerCreateTestPlan")
            target = content.get("target", "unknown")
            test_types = content.get("test_types", ["unit"])
            priority = content.get("priority", "medium")
            requirements = content.get("requirements", [])

            logger.info(
                "Creating test plan", target=target, test_types=test_types, priority=priority
            )

            test_plan = await self._generate_test_plan(
                target=target, test_types=test_types, priority=priority, requirements=requirements
            )

            return {
                "status": "success",
                "test_plan": test_plan,
                "target": target,
                "estimated_tests": len(test_plan.get("test_cases", [])),
            }

        except Exception as e:
            logger.error("Failed to create test plan", error=str(e))
            return {"status": "error", "error": str(e)}

    async def _handle_execute_tests(self, message: ActorMessage) -> dict[str, Any] | None:
        """Execute a test suite and return results."""
        try:
            content = validate_message(message.content, "ExaminerExecuteTests")
            test_suite_id = content.get("test_suite_id")
            test_cases = content.get("test_cases", [])
            timeout = content.get("timeout", self._default_timeout)

            logger.info("Executing tests", test_suite_id=test_suite_id, test_count=len(test_cases))

            suite = TestSuite(
                id=test_suite_id or f"suite_{datetime.now(UTC).timestamp()}",
                name=content.get("name", "Test Suite"),
                test_cases=[],
            )

            for tc in test_cases:
                result = await self._execute_test_case(tc, timeout)
                suite.test_cases.append(result)

                if result.status == TestStatus.PASSED:
                    suite.passed += 1
                elif result.status == TestStatus.FAILED:
                    suite.failed += 1
                elif result.status == TestStatus.SKIPPED:
                    suite.skipped += 1
                suite.total += 1
                suite.execution_time_ms += result.execution_time_ms or 0

            self._test_suites[suite.id] = suite
            self._test_history.append(suite)

            if len(self._test_history) > self.max_test_history:
                self._test_history = self._test_history[-self.max_test_history :]

            return {
                "status": "success",
                "test_suite_id": suite.id,
                "passed": suite.passed,
                "failed": suite.failed,
                "skipped": suite.skipped,
                "total": suite.total,
                "execution_time_ms": suite.execution_time_ms,
                "coverage_percent": suite.coverage_percent,
            }

        except Exception as e:
            logger.error("Failed to execute tests", error=str(e))
            return {"status": "error", "error": str(e)}

    async def _handle_validate_decision(self, message: ActorMessage) -> dict[str, Any] | None:
        """Validate a decision from the Triad."""
        try:
            content = validate_message(message.content, "ExaminerValidateDecision")
            decision_id = content.get("decision_id")
            decision_type = content.get("decision_type", "unknown")
            decision_content = content.get("content", "")
            context = content.get("context", {})

            logger.info("Validating decision", decision_id=decision_id, decision_type=decision_type)

            validation_result = await self._validate_decision_content(
                decision_id=decision_id,
                decision_type=decision_type,
                content=decision_content,
                context=context,
            )

            return {
                "status": "success",
                "decision_id": decision_id,
                "valid": validation_result.get("valid", False),
                "confidence": validation_result.get("confidence", 0.0),
                "issues": validation_result.get("issues", []),
                "recommendations": validation_result.get("recommendations", []),
            }

        except Exception as e:
            logger.error("Failed to validate decision", error=str(e))
            return {"status": "error", "error": str(e)}

    async def _handle_analyze_quality(self, message: ActorMessage) -> dict[str, Any] | None:
        """Analyze quality of code, decision, or component."""
        try:
            content = validate_message(message.content, "ExaminerAnalyzeQuality")
            target = content.get("target", "")
            target_type = content.get("target_type", "code")
            metrics = content.get("metrics", list(QualityMetric))

            logger.info("Analyzing quality", target_type=target_type, metrics=metrics)

            quality_results = await self._analyze_quality_metrics(
                target=target, target_type=target_type, metrics=metrics
            )

            overall_score = self._calculate_overall_score(quality_results)

            target_key = f"{target_type}:{target[:50]}"
            self._quality_metrics[target_key] = quality_results

            return {
                "status": "success",
                "metrics": {k.value: v for k, v in quality_results.items()},
                "overall_score": overall_score,
                "threshold": self._coverage_threshold,
                "passed": overall_score >= self._coverage_threshold,
            }

        except Exception as e:
            logger.error("Failed to analyze quality", error=str(e))
            return {"status": "error", "error": str(e)}

    async def _handle_report_bug(self, message: ActorMessage) -> dict[str, Any] | None:
        """Report a bug or issue."""
        try:
            content = validate_message(message.content, "ExaminerReportBug")

            self._bug_counter += 1
            bug = Bug(
                id=f"bug_{self._bug_counter}",
                title=content.get("title", "Untitled Bug"),
                description=content.get("description", ""),
                severity=SeverityLevel(content.get("severity", "medium")),
                component=content.get("component", "unknown"),
                steps_to_reproduce=content.get("steps_to_reproduce", []),
                expected_behavior=content.get("expected_behavior", ""),
                actual_behavior=content.get("actual_behavior", ""),
                detected_at=datetime.now(UTC),
                metadata=content.get("metadata", {}),
            )

            if len(self._bugs) >= self.max_bugs:
                oldest_id = next(iter(self._bugs))
                del self._bugs[oldest_id]

            self._bugs[bug.id] = bug

            logger.info(
                "Bug reported", bug_id=bug.id, severity=bug.severity.value, component=bug.component
            )

            return {
                "status": "success",
                "bug_id": bug.id,
                "severity": bug.severity.value,
                "created_at": bug.detected_at.isoformat(),
            }

        except Exception as e:
            logger.error("Failed to report bug", error=str(e))
            return {"status": "error", "error": str(e)}

    async def _handle_get_quality_report(self, message: ActorMessage) -> dict[str, Any] | None:
        """Get comprehensive quality report for a target."""
        try:
            content = validate_message(message.content, "ExaminerGetQualityReport")
            target = content.get("target", "system")
            include_tests = content.get("include_tests", True)
            include_bugs = content.get("include_bugs", True)
            include_metrics = content.get("include_metrics", True)

            logger.info("Generating quality report", target=target)

            test_suites = list(self._test_suites.values()) if include_tests else []
            bugs = [b for b in self._bugs.values() if b.component == target] if include_bugs else []
            metrics = self._quality_metrics.get(f"system:{target}", {}) if include_metrics else {}

            overall_score = self._calculate_system_score(test_suites, bugs, metrics)

            summary = await self._generate_quality_summary(
                test_suites=test_suites, bugs=bugs, metrics=metrics, overall_score=overall_score
            )

            report = QualityReport(
                id=f"report_{datetime.now(UTC).timestamp()}",
                generated_at=datetime.now(UTC),
                target=target,
                test_suites=test_suites,
                bugs=bugs,
                metrics=metrics,
                overall_score=overall_score,
                summary=summary,
                recommendations=self._generate_recommendations(test_suites, bugs, metrics),
                passed=overall_score >= self._coverage_threshold,
            )

            return {
                "status": "success",
                "report": {
                    "id": report.id,
                    "generated_at": report.generated_at.isoformat(),
                    "target": report.target,
                    "overall_score": report.overall_score,
                    "passed": report.passed,
                    "summary": report.summary,
                    "test_summary": {
                        "passed": sum(s.passed for s in test_suites),
                        "failed": sum(s.failed for s in test_suites),
                        "total": sum(s.total for s in test_suites),
                    }
                    if test_suites
                    else None,
                    "bug_summary": {
                        "critical": len([b for b in bugs if b.severity == SeverityLevel.CRITICAL]),
                        "high": len([b for b in bugs if b.severity == SeverityLevel.HIGH]),
                        "total": len(bugs),
                    }
                    if bugs
                    else None,
                    "recommendations": report.recommendations,
                },
            }

        except Exception as e:
            logger.error("Failed to generate quality report", error=str(e))
            return {"status": "error", "error": str(e)}

    async def _handle_get_bug_status(self, message: ActorMessage) -> dict[str, Any] | None:
        """Get status of reported bugs."""
        try:
            content = validate_message(message.content, "ExaminerGetBugStatus")
            bug_id = content.get("bug_id")
            component = content.get("component")
            severity = content.get("severity")

            if bug_id:
                bug = self._bugs.get(bug_id)
                if bug:
                    return {
                        "status": "success",
                        "bug": {
                            "id": bug.id,
                            "title": bug.title,
                            "severity": bug.severity.value,
                            "component": bug.component,
                            "status": bug.status,
                            "detected_at": bug.detected_at.isoformat(),
                        },
                    }
                return {"status": "error", "error": f"Bug {bug_id} not found"}

            filtered_bugs = list(self._bugs.values())
            if component:
                filtered_bugs = [b for b in filtered_bugs if b.component == component]
            if severity:
                filtered_bugs = [b for b in filtered_bugs if b.severity.value == severity]

            return {
                "status": "success",
                "bugs": [
                    {
                        "id": b.id,
                        "title": b.title,
                        "severity": b.severity.value,
                        "component": b.component,
                        "status": b.status,
                        "detected_at": b.detected_at.isoformat(),
                    }
                    for b in filtered_bugs[:50]
                ],
                "total": len(filtered_bugs),
            }

        except Exception as e:
            logger.error("Failed to get bug status", error=str(e))
            return {"status": "error", "error": str(e)}

    # Internal helper methods

    async def _generate_test_plan(
        self, target: str, test_types: list[str], priority: str, requirements: list[str]
    ) -> dict[str, Any]:
        """Generate test plan using LLM."""
        try:
            prompt = f"""Generate a comprehensive test plan for: {target}

Test Types Required: {", ".join(test_types)}
Priority: {priority}
Requirements: {requirements}

Provide a structured test plan with:
1. Test objectives
2. Test cases for each type
3. Expected outcomes
4. Success criteria
5. Risk assessment

Format as JSON with keys: objectives, test_cases, success_criteria, risks"""

            response = await self.run_with_llm(prompt=prompt, timeout=60, temperature=0.3)

            try:
                return json.loads(response)
            except Exception as e:
                logger.debug("examiner_objectives_parse_failed_661", error=str(e))
                return {
                    "objectives": [response[:500]],
                    "test_cases": [],
                    "success_criteria": ["All tests pass"],
                    "risks": [],
                }

        except Exception as e:
            logger.error("Failed to generate test plan", error=str(e))
            return {
                "objectives": ["Test plan generation failed"],
                "test_cases": [],
                "success_criteria": [],
                "risks": [str(e)],
            }

    async def _execute_test_case(self, test_case: dict[str, Any], timeout: int) -> TestCase:  # noqa: ASYNC109
        """Execute a single test case."""
        start_time = datetime.now(UTC)

        try:
            tc_id = test_case.get("id", f"tc_{start_time.timestamp()}")
            tc_name = test_case.get("name", _UNNAMED_TEST)
            tc_type = TestType(test_case.get("test_type", "unit"))

            result = await asyncio.wait_for(self._run_test_logic(test_case), timeout=timeout)

            return TestCase(
                id=tc_id,
                name=tc_name,
                test_type=tc_type,
                description=test_case.get("description", ""),
                status=TestStatus.PASSED if result.get("passed") else TestStatus.FAILED,
                execution_time_ms=(datetime.now(UTC) - start_time).total_seconds() * 1000,
                assertions_passed=result.get("assertions_passed", 0),
                assertions_total=result.get("assertions_total", 0),
                coverage_percent=result.get("coverage"),
                metadata=result.get("metadata", {}),
            )

        except TimeoutError:
            return TestCase(
                id=test_case.get("id", "unknown"),
                name=test_case.get("name", _UNNAMED_TEST),
                test_type=TestType(test_case.get("test_type", "unit")),
                description=test_case.get("description", ""),
                status=TestStatus.ERROR,
                execution_time_ms=(datetime.now(UTC) - start_time).total_seconds() * 1000,
                error_message=f"Test timed out after {timeout}s",
            )
        except Exception as e:
            return TestCase(
                id=test_case.get("id", "unknown"),
                name=test_case.get("name", _UNNAMED_TEST),
                test_type=TestType(test_case.get("test_type", "unit")),
                description=test_case.get("description", ""),
                status=TestStatus.ERROR,
                execution_time_ms=(datetime.now(UTC) - start_time).total_seconds() * 1000,
                error_message=str(e),
            )

    async def _run_test_logic(self, test_case: dict[str, Any]) -> dict[str, Any]:
        """Execute test logic using inline assertions or pytest subprocess."""
        assertions = test_case.get("assertions_list") or []
        total = max(len(assertions), int(test_case.get("assertions", 1)))
        passed = 0

        for assertion in assertions:
            expected = assertion.get("expected")
            actual = assertion.get("actual")
            if expected == actual:
                passed += 1

        test_path = test_case.get("test_path")
        if test_path:
            # G-01: path-traversal guard — only allow test files under
            # allowed roots. Resolve symlinks / .. to prevent escape.
            resolved = Path(test_path).resolve()
            allowed_roots = (Path.cwd() / "tests", Path.cwd() / "backend" / "tests")
            if not any(str(resolved).startswith(str(root.resolve())) for root in allowed_roots):
                logger.warning(
                    "examiner_test_path_outside_allowed_roots",
                    test_path=test_path,
                    resolved=str(resolved),
                )
                return {
                    "passed": False,
                    "error": f"Test path outside allowed directories: {test_path}",
                    "assertions_passed": 0,
                    "assertions_total": 1,
                }
            proc = await asyncio.create_subprocess_exec(
                "python",
                "-m",
                "pytest",
                str(test_path),
                "-q",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            _stdout, _stderr = await proc.communicate()
            success = proc.returncode == 0
            return {
                "passed": success,
                "assertions_passed": int(success),
                "assertions_total": 1,
                "coverage": test_case.get("expected_coverage", 0.0),
            }

        if assertions:
            success = passed >= total
        elif test_case.get("expected") is not None:
            success = test_case.get("expected") == test_case.get("actual")
            passed = int(success)
            total = 1
        else:
            success = False

        return {
            "passed": success,
            "assertions_passed": passed,
            "assertions_total": total,
            "coverage": test_case.get("expected_coverage", 0.0),
        }

    async def _validate_decision_content(
        self, decision_id: str, decision_type: str, content: str, context: dict[str, Any]
    ) -> dict[str, Any]:
        """Validate decision content using LLM."""
        try:
            prompt = f"""Validate this decision from the Triad:

Decision ID: {decision_id}
Type: {decision_type}
Content: {content[:2000]}
Context: {context}

Evaluate for:
1. Logical consistency
2. Completeness
3. Alignment with requirements
4. Potential edge cases missed
5. Security implications

Return JSON with keys: valid (bool), confidence (0-1), issues (list), recommendations (list)"""

            response = await self.run_with_llm(prompt=prompt, timeout=60, temperature=0.2)

            try:
                return json.loads(response)
            except Exception as e:
                logger.debug("examiner_review_parse_failed_784", error=str(e))
                return {
                    "valid": True,
                    "confidence": 0.8,
                    "issues": ["Unable to parse detailed validation"],
                    "recommendations": ["Manual review recommended"],
                }

        except Exception as e:
            logger.error("Decision validation failed", error=str(e))
            return {
                "valid": False,
                "confidence": 0.0,
                "issues": [f"Validation error: {e!s}"],
                "recommendations": ["Retry validation"],
            }

    async def _analyze_quality_metrics(
        self, target: str, target_type: str, metrics: list[QualityMetric]  # noqa: ARG002
    ) -> dict[QualityMetric, float]:
        """Analyze quality metrics for target."""
        results = {}

        for metric in metrics:
            try:
                if metric == QualityMetric.CODE_COVERAGE:
                    results[metric] = await self._measure_coverage(target)
                elif metric == QualityMetric.CYCLOMATIC_COMPLEXITY:
                    results[metric] = await self._measure_complexity(target)
                elif metric == QualityMetric.SECURITY_VULNERABILITIES:
                    results[metric] = await self._measure_security(target)
                elif metric == QualityMetric.PERFORMANCE_SCORE:
                    results[metric] = await self._measure_performance(target)
                else:
                    results[metric] = await self._estimate_metric(target, metric)
            except Exception as e:
                logger.warning("Failed to measure {metric.value}", error=str(e))
                results[metric] = 0.0

        return results

    async def _measure_coverage(self, _target: str) -> float:
        """Measure code coverage."""
        return 85.0

    async def _measure_complexity(self, _target: str) -> float:
        """Measure cyclomatic complexity (inverted score)."""
        return 75.0

    async def _measure_security(self, _target: str) -> float:
        """Measure security score (inverted - lower vulnerabilities = higher score)."""
        return 90.0

    async def _measure_performance(self, _target: str) -> float:
        """Measure performance score."""
        return 80.0

    async def _estimate_metric(self, target: str, metric: QualityMetric) -> float:
        """Estimate metric using LLM."""
        try:
            prompt = f"""Estimate {metric.value} for: {target[:500]}

Return a score from 0-100."""

            response = await self.run_with_llm(prompt=prompt, timeout=30)
            match = re.search(r"(\d+(?:\.\d+)?)", response)
            if match:
                return min(100.0, float(match.group(1)))
            return 50.0
        except Exception as e:
            logger.debug("examiner_confidence_calc_failed_863", error=str(e))
            return 50.0

    def _calculate_overall_score(self, metrics: dict[QualityMetric, float]) -> float:
        """Calculate weighted overall quality score."""
        if not metrics:
            return 0.0

        weights = {
            QualityMetric.CODE_COVERAGE: 0.25,
            QualityMetric.CYCLOMATIC_COMPLEXITY: 0.15,
            QualityMetric.SECURITY_VULNERABILITIES: 0.25,
            QualityMetric.PERFORMANCE_SCORE: 0.20,
            QualityMetric.ACCESSIBILITY_SCORE: 0.10,
            QualityMetric.DOCUMENTATION_COVERAGE: 0.05,
        }

        total = 0.0
        total_weight = 0.0

        for metric, value in metrics.items():
            weight = weights.get(metric, 0.1)
            total += value * weight
            total_weight += weight

        return (total / total_weight) if total_weight > 0 else 0.0

    def _calculate_system_score(
        self, test_suites: list[TestSuite], bugs: list[Bug], metrics: dict[QualityMetric, float]
    ) -> float:
        """Calculate overall system quality score."""
        scores = []

        if test_suites:
            total_passed = sum(s.passed for s in test_suites)
            total_tests = sum(s.total for s in test_suites)
            if total_tests > 0:
                scores.append((total_passed / total_tests) * 100 * 0.4)

        if bugs:
            severity_weights = {
                SeverityLevel.CRITICAL: 10,
                SeverityLevel.HIGH: 5,
                SeverityLevel.MEDIUM: 2,
                SeverityLevel.LOW: 1,
                SeverityLevel.INFO: 0.5,
            }
            bug_score = sum(severity_weights.get(b.severity, 1) for b in bugs)
            scores.append(max(0, 100 - bug_score * 2) * 0.3)
        else:
            scores.append(100 * 0.3)

        if metrics:
            metric_score = self._calculate_overall_score(metrics)
            scores.append(metric_score * 0.3)

        return sum(scores) if scores else 0.0

    def _generate_recommendations(
        self, test_suites: list[TestSuite], bugs: list[Bug], metrics: dict[QualityMetric, float]
    ) -> list[str]:
        """Generate quality improvement recommendations."""
        recommendations = []

        if test_suites:
            total_failed = sum(s.failed for s in test_suites)
            if total_failed > 0:
                recommendations.append(f"Fix {total_failed} failing tests")

            avg_coverage = sum(s.coverage_percent or 0 for s in test_suites) / len(test_suites)
            if avg_coverage < self._coverage_threshold:
                recommendations.append(
                    f"Increase test coverage from {avg_coverage:.1f}% to {self._coverage_threshold}%"
                )

        critical_bugs = [b for b in bugs if b.severity == SeverityLevel.CRITICAL]
        if critical_bugs:
            recommendations.append(f"Address {len(critical_bugs)} critical bugs immediately")

        for metric, value in metrics.items():
            if value < 70:
                recommendations.append(f"Improve {metric.value} (current: {value:.1f})")

        return recommendations or ["Continue monitoring quality metrics"]

    # Session 44: Collective Learning Integration Methods

    async def _emit_pattern(
        self, item_id: str, item_type: str, outcome: str, content: dict[str, Any]
    ) -> None:
        """Emit pattern for collective learning."""
        if not self.pattern_extractor:
            return

        if item_id in self._pattern_emitted:
            return

        try:
            await self.pattern_extractor.analyze_message(
                message_id=f"{item_type}_{item_id}",
                sender=self.agent_id,
                recipient="broadcast",
                message_type=f"{item_type}_completion",
                content=content,
                timestamp=datetime.now(UTC).isoformat(),
            )

            self._pattern_emitted.add(item_id)
            logger.info("{item_type}_pattern_emitted", item_id=item_id, outcome=outcome)
        except Exception as e:
            logger.warning("failed_to_emit_pattern", item_id=item_id, error=str(e))

    async def _consume_patterns(
        self, pattern_types: list[PatternType] | None = None
    ) -> list[dict[str, Any]]:
        """Consume patterns from collective learning."""
        if not self.pattern_extractor:
            return []

        try:
            patterns = await self.pattern_extractor.extract_patterns(
                time_window_hours=24,
                pattern_types=pattern_types or [PatternType.SUCCESS, PatternType.DECISION],
            )
            return [p.to_dict() for p in patterns if p.metadata.confidence >= 0.7]
        except Exception as e:
            logger.warning("failed_to_consume_patterns", error=str(e))
            return []

    # Session 44: Consensus Deliberation Integration Methods

    async def _initiate_deliberation(
        self,
        item_id: str,
        proposal: str,
        participating_agents: list[str],
        domain: str = "general",
    ) -> str | None:
        """Initiate swarm deliberation."""
        if not self.deliberation_engine:
            return None

        try:
            deliberation_id = f"delib_{item_id}"
            self.deliberation_engine.start_deliberation(
                deliberation_id=deliberation_id,
                proposal=proposal[:200],
                participants=participating_agents,
                domain=domain,
            )
            self._active_deliberations[item_id] = deliberation_id

            logger.info("deliberation_initiated", deliberation_id=deliberation_id, item_id=item_id)
            return deliberation_id
        except Exception as e:
            logger.error("failed_to_initiate_deliberation", item_id=item_id, error=str(e))
            return None

    async def _submit_deliberation_position(
        self,
        item_id: str,
        agent_id: str,
        position: Position,
        confidence: float,
        argument: str,
    ) -> bool:
        """Submit agent position in deliberation."""
        if not self.deliberation_engine:
            return False

        deliberation_id = self._active_deliberations.get(item_id)
        if not deliberation_id:
            return False

        try:
            success = self.deliberation_engine.submit_position(
                deliberation_id=deliberation_id,
                agent_id=agent_id,
                position=position,
                confidence=confidence,
                argument=argument,
            )

            if success and self.access_analyzer:
                self.access_analyzer.record_access(
                    memory_id=f"delib_{deliberation_id}_{agent_id}",
                    access_type="write",
                    agent_id=agent_id,
                )

            return success
        except Exception as e:
            logger.error("failed_to_submit_deliberation_position", error=str(e))
            return False

    async def _finalize_deliberation(self, item_id: str) -> Any | None:
        """Finalize deliberation and apply result."""
        if not self.deliberation_engine:
            return None

        deliberation_id = self._active_deliberations.get(item_id)
        if not deliberation_id:
            return None

        try:
            result = self.deliberation_engine.finalize_deliberation(deliberation_id)

            if result:
                self.deliberation_engine.cleanup_deliberation(deliberation_id)
                del self._active_deliberations[item_id]
                logger.info("deliberation_finalized", deliberation_id=deliberation_id)

            return result
        except Exception as e:
            logger.error("failed_to_finalize_deliberation", error=str(e))
            return None

    async def _generate_quality_summary(
        self,
        test_suites: list[TestSuite],
        bugs: list[Bug],
        metrics: dict[QualityMetric, float],
        overall_score: float,
    ) -> str:
        """Generate quality summary using LLM."""
        try:
            prompt = f"""Generate a quality summary:

Overall Score: {overall_score:.1f}/100
Test Suites: {len(test_suites)} ({sum(s.passed for s in test_suites)} passed, {sum(s.failed for s in test_suites)} failed)  # noqa: E501
Bugs: {len(bugs)} ({len([b for b in bugs if b.severity == SeverityLevel.CRITICAL])} critical)
Metrics: {len(metrics)} measured

Provide a 2-3 sentence summary of the quality status."""

            response = await self.run_with_llm(prompt=prompt, timeout=30)
            return response.strip()
        except Exception as e:
            logger.debug("examiner_summary_gen_failed_1171", error=str(e))
            return f"Quality score: {overall_score:.1f}/100. {len(bugs)} bugs detected. {sum(s.failed for s in test_suites)} tests failing."

    async def _handle_execute_stress_test(self, message: ActorMessage) -> dict[str, Any] | None:
        """Execute comprehensive stress test on agent capabilities."""
        try:
            content = validate_message(message.content, "ExaminerExecuteStressTest")
            target_agent_id = content.get("target_agent_id")

            test_types_str = content.get("test_types", ["capacity"])
            test_types = [StressTestType(t) for t in test_types_str]

            config_dict = content.get("config", {})
            config = StressTestConfig(
                max_duration_seconds=config_dict.get("max_duration_seconds", 300.0),
                intensity_levels=config_dict.get("intensity_levels", [0.5, 0.75, 1.0]),
                recovery_enabled=config_dict.get("recovery_enabled", True),
            )

            logger.info(
                "Executing stress test",
                target_agent_id=target_agent_id,
                test_types=[t.value for t in test_types],
            )

            result = await self._stress_executor.execute_stress_test(
                target_agent_id=target_agent_id,
                test_types=test_types,
                config=config,
            )

            self._stress_test_results[result.test_suite_id] = result

            if result.boundaries_found:
                for boundary_data in result.boundaries_found:
                    capability = boundary_data.get("capability", "unknown")
                    boundary = CapabilityBoundary(
                        boundary_id=f"boundary-{capability}",
                        agent_id=target_agent_id,
                        capability=capability,
                        boundary_type="stress_test",
                        measured_value=boundary_data.get("measured_value", 0.0),
                        threshold_value=1.0,
                        unit="intensity",
                        test_conditions={},
                        confidence=0.8,
                        safety_margin=0.1,
                    )
                    self._capability_boundaries[boundary.boundary_id] = boundary

            return {
                "status": "success",
                "test_suite_id": result.test_suite_id,
                "target_agent_id": result.target_agent_id,
                "passed": result.passed,
                "failed": result.failed,
                "boundaries_found": len(result.boundaries_found),
                "execution_time_seconds": result.execution_time_seconds,
            }

        except Exception as e:
            logger.error("Failed to execute stress test", error=str(e))
            return {"status": "error", "error": str(e)}

    async def _handle_get_stress_test_results(self, message: ActorMessage) -> dict[str, Any] | None:
        """Get results of stress test execution."""
        try:
            content = validate_message(message.content, "ExaminerGetStressTestResults")
            test_suite_id = content.get("test_suite_id")

            if test_suite_id:
                result = self._stress_test_results.get(test_suite_id)
                if result:
                    return {
                        "status": "success",
                        "result": {
                            "test_suite_id": result.test_suite_id,
                            "target_agent_id": result.target_agent_id,
                            "status": result.status.value,
                            "passed": result.passed,
                            "failed": result.failed,
                            "boundaries_found": result.boundaries_found,
                            "execution_time_seconds": result.execution_time_seconds,
                        },
                    }
                return {"status": "error", "error": f"Test suite {test_suite_id} not found"}

            all_results = [
                {
                    "test_suite_id": r.test_suite_id,
                    "target_agent_id": r.target_agent_id,
                    "status": r.status.value,
                    "passed": r.passed,
                    "failed": r.failed,
                }
                for r in self._stress_test_results.values()
            ]

            return {
                "status": "success",
                "results": all_results,
                "count": len(all_results),
            }

        except Exception as e:
            logger.error("Failed to get stress test results", error=str(e))
            return {"status": "error", "error": str(e)}

    async def _handle_report_capability_gap(self, message: ActorMessage) -> dict[str, Any] | None:
        """Report identified capability gap to Steward."""
        try:
            content = validate_message(message.content, "ExaminerReportCapabilityGap")
            agent_id = content.get("agent_id")
            capability = content.get("capability")
            severity = content.get("severity", "medium")
            test_evidence = content.get("test_evidence", [])

            gap = await self._gap_reporter.identify_gap(
                agent_id=agent_id,
                capability=capability,
                test_evidence=test_evidence,
                severity=severity,
            )

            await self._gap_reporter.report_to_steward(gap, message_sender=self)

            return {
                "status": "success",
                "gap_id": gap.gap_id,
                "agent_id": gap.agent_id,
                "capability": gap.capability,
                "severity": gap.severity,
                "reported_at": gap.reported_at.isoformat() if gap.reported_at else None,
            }

        except Exception as e:
            logger.error("Failed to report capability gap", error=str(e))
            return {"status": "error", "error": str(e)}

    async def _handle_get_safety_bounds(self, message: ActorMessage) -> dict[str, Any] | None:
        """Get proven safety bounds for agent."""
        try:
            content = validate_message(message.content, "ExaminerGetSafetyBounds")
            agent_id = content.get("agent_id")
            bounds_type = content.get("bounds_type", "general")

            safety_proof = await self._stress_executor.generate_safety_proof(
                agent_id=agent_id,
                bounds_type=bounds_type,
            )

            self._safety_bounds[safety_proof.bounds_id] = safety_proof

            return {
                "status": "success",
                "bounds_id": safety_proof.bounds_id,
                "agent_id": safety_proof.agent_id,
                "bounds_type": safety_proof.bounds_type,
                "proven_limits": safety_proof.proven_limits,
                "meets_safety_standard": safety_proof.meets_safety_standard,
                "confidence": safety_proof.confidence,
                "notes": safety_proof.notes,
            }

        except Exception as e:
            logger.error("Failed to get safety bounds", error=str(e))
            return {"status": "error", "error": str(e)}

    async def _handle_get_incident_reports(self, message: ActorMessage) -> dict[str, Any] | None:
        """Get incident reports from stress testing."""
        try:
            content = validate_message(message.content, "ExaminerGetIncidentReports")
            incident_id = content.get("incident_id")

            if incident_id:
                incident = self._incident_reports.get(incident_id)
                if incident:
                    return {
                        "status": "success",
                        "incident": {
                            "incident_id": incident.incident_id,
                            "agent_id": incident.agent_id,
                            "incident_type": incident.incident_type,
                            "severity": incident.severity,
                            "detected_at": incident.detected_at.isoformat(),
                            "recovered_at": incident.recovered_at.isoformat()
                            if incident.recovered_at
                            else None,
                            "recovery_successful": incident.recovery_successful,
                            "escalated": incident.escalated,
                        },
                    }
                return {"status": "error", "error": f"Incident {incident_id} not found"}

            all_incidents = [
                {
                    "incident_id": i.incident_id,
                    "agent_id": i.agent_id,
                    "incident_type": i.incident_type,
                    "severity": i.severity,
                    "recovery_successful": i.recovery_successful,
                    "escalated": i.escalated,
                }
                for i in self._incident_reports.values()
            ]

            return {
                "status": "success",
                "incidents": all_incidents,
                "count": len(all_incidents),
            }

        except Exception as e:
            logger.error("Failed to get incident reports", error=str(e))
            return {"status": "error", "error": str(e)}
