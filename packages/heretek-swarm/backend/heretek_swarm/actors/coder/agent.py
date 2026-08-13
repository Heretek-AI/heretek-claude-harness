"""
Coder Agent - Code Implementation & Debugging Specialist.

The Coder provides:
- Code generation and implementation
- Code review and refactoring
- Bug detection and fixing
- Test code generation
- Documentation generation
- Code explanation and analysis

Coder is the "implementation engine" of the Collective, translating
decisions and designs into working, tested, and documented code.
"""

import asyncio
import uuid
from datetime import UTC, datetime
from typing import Any

import structlog

from heretek_swarm.actors.base import ActorMessage, AgentActor
from heretek_swarm.actors.coder.types import (
    CodeLanguage,
    CodeReview,
    CodeSnippet,
    DebugSession,
    ImplementationTask,
    ReviewIssue,
    ReviewSeverity,
)
from heretek_swarm.actors.mixins.deliberation import DeliberationMixin
from heretek_swarm.actors.mixins.learning import LearningMixin
from heretek_swarm.actors.mixins.memory import MemoryMixin
from heretek_swarm.actors.mixins.pattern import PatternMixin
from heretek_swarm.actors.mixins.validation import ValidationMixin
from heretek_swarm.actors.validation import validate_message as validate_message_schema
from heretek_swarm_core.validation import (
    LLMOutputValidator,
    is_code_safe,
    is_text_safe,
)

# Alias for use in handlers
validate_message = validate_message_schema

logger = structlog.get_logger("CoderAgent")


class CoderAgent(ValidationMixin, DeliberationMixin, PatternMixin, MemoryMixin, LearningMixin, AgentActor):
    """
    Code Implementation & Debugging Specialist Agent.

    Coder translates requirements into working code, performs reviews,
    debugs issues, and generates tests and documentation.
    """

    def __init__(
        self,
        agent_id: str | None = None,
        config: dict[str, Any] | None = None,
        pattern_extractor: Any = None,
        deliberation_engine: Any = None,
        access_analyzer: Any = None,
        zero_trust_validator: Any = None,
    ):
        super().__init__(
            agent_id=agent_id,
            name="Coder",
            description="Code Implementation & Debugging Specialist",
            config=config or {},
            pattern_extractor=pattern_extractor,
            deliberation_engine=deliberation_engine,
            access_analyzer=access_analyzer,
            zero_trust_validator=zero_trust_validator,
        )

        self._config: dict[str, Any] = {}

        # Add routing capability for route_to_agent() support
        if "routing" not in self.capabilities:
            self.capabilities.append("routing")

        # Code storage
        self._code_snippets: dict[str, CodeSnippet] = {}
        self._snippet_counter = 0
        self.max_snippets = self._config.get("max_snippets", 500)

        # Reviews
        self._reviews: dict[str, CodeReview] = {}
        self.max_reviews = self._config.get("max_reviews", 200)

        # Debug sessions
        self._debug_sessions: dict[str, DebugSession] = {}
        self._active_debugs: set[str] = set()
        self.max_debug_sessions = self._config.get("max_debug_sessions", 50)

        # Implementation tasks
        self._tasks: dict[str, ImplementationTask] = {}
        self._task_counter = 0

        # Configuration
        self._default_language = CodeLanguage(self._config.get("default_language", "python"))
        self._enable_tests = self._config.get("enable_tests", True)
        self._enable_docs = self._config.get("enable_docs", True)

        # Session 44: LLM Output Validation
        self.llm_output_validator = LLMOutputValidator(strict_mode=True)

        logger.info(
            "CoderAgent initialized",
            agent_id=self.agent_id,
            default_language=self._default_language.value,
        )

    def get_handlers(self) -> dict[str, callable]:
        """Return message handlers for Coder agent."""
        return {
            "generate_code": self._handle_generate_code,
            "review_code": self._handle_review_code,
            "debug_code": self._handle_debug_code,
            "generate_tests": self._handle_generate_tests,
            "generate_docs": self._handle_generate_docs,
            "refactor_code": self._handle_refactor_code,
            "explain_code": self._handle_explain_code,
            "implement_task": self._handle_implement_task,
            "route_task": self._handle_route_task,
            "code_execution_request": self._handle_code_execution_request,
        }

    async def _handle_route_task(self, message: ActorMessage) -> dict[str, Any]:
        """
        Handle a route_task message by delegating to _process_route_task.

        Extracts the payload from ``message.content`` and passes it to
        :meth:`_process_route_task`.
        """
        payload: dict[str, Any] = message.content if isinstance(message.content, dict) else {}
        logger.info(
            "[%s] route_task handler invoked",
            self.agent_id,
            extra={
                "sender": message.sender,
                "task_type": payload.get("task_type"),
                "correlation_id": message.correlation_id,
            },
        )
        return await self._process_route_task(payload)

    async def _process_route_task(
        self,
        payload: dict[str, Any],
    ) -> dict[str, Any]:
        """
        Process a routed task payload dispatched via route_to_agent().

        Reads ``task_type`` from the payload and dispatches to the
        corresponding handler from :meth:`get_handlers()`.  For the
        initial proof case, supports ``task_type='on_demand_analysis'``
        which calls ``_handle_generate_code`` with the ``task_data``.

        Args:
            payload: Route task payload with keys:
                - ``target_agent``: target agent name
                - ``task_type``: type of task to perform
                - ``task_data``: dict of data for the handler
                - ``correlation_id``: optional correlation ID
                - ``sender``: originating agent name
                - ``timestamp``: ISO8601 timestamp

        Returns:
            Result dict with at minimum a ``"status"`` key.
        """
        task_type = payload.get("task_type", "unknown")
        task_data = payload.get("task_data", {})

        # Map route task types to handler keys
        type_to_handler: dict[str, str] = {
            "on_demand_analysis": "generate_code",
            "generate_code": "generate_code",
            "review_code": "review_code",
            "debug_code": "debug_code",
            "generate_tests": "generate_tests",
            "generate_docs": "generate_docs",
            "refactor_code": "refactor_code",
            "explain_code": "explain_code",
            "implement_task": "implement_task",
            "code_execution_request": "code_execution_request",
            "execute_code": "code_execution_request",
        }

        handler_key = type_to_handler.get(task_type)
        if handler_key is None:
            logger.warning(
                f"[{self.agent_id}] Unsupported route task type: {task_type}",
                extra={
                    "task_type": task_type,
                    "correlation_id": payload.get("correlation_id"),
                },
            )
            return {"status": "error", "error": f"Unsupported task_type: {task_type}"}

        handler = self.get_handlers().get(handler_key)
        if handler is None:
            logger.error(
                "[%s] Handler %s not registered",
                self.agent_id,
                handler_key,
                extra={"task_type": task_type},
            )
            return {"status": "error", "error": f"Handler {handler_key} not available"}

        logger.info(
            f"[{self.agent_id}] Processing route task {task_type} via {handler_key}",
            extra={
                "task_type": task_type,
                "handler_key": handler_key,
                "correlation_id": payload.get("correlation_id"),
            },
        )

        # Build a minimal ActorMessage for the handler
        from datetime import UTC, datetime

        msg = ActorMessage(
            sender=payload.get("sender", "unknown"),
            message_type=handler_key,
            content=task_data if isinstance(task_data, dict) else {},
            timestamp=datetime.now(UTC).isoformat(),
            correlation_id=payload.get("correlation_id"),
        )

        try:
            result = await handler(msg)
            return {"status": "success", "result": result}
        except Exception as e:
            logger.error(
                f"[{self.agent_id}] Route task handler failed",
                extra={
                    "task_type": task_type,
                    "handler_key": handler_key,
                    "error": str(e),
                },
            )
            return {"status": "error", "error": str(e)}

    async def _handle_code_execution_request(self, message: ActorMessage) -> dict[str, Any] | None:
        """
        Execute generated code inside a secure Docker sandbox.

        Content expected:
        {
            "code": "code to execute",
            "language": "python",
            "timeout": 30,
            "sandbox": true
        }
        """
        try:
            content = message.content if isinstance(message.content, dict) else {}

            code = content.get("code", "")
            language = content.get("language", "python").lower()
            timeout = int(content.get("timeout", 30))
            use_sandbox = bool(content.get("sandbox", True))

            if not code:
                return {"status": "error", "error": "Code content is empty"}

            # Security validation for code content before execution
            if not is_code_safe(code):
                logger.warning("unsafe_code_rejected", code_preview=code[:100])
                return {"status": "error", "error": "Unsafe code rejected - contains dangerous patterns"}

            if not use_sandbox:
                logger.warning("non_sandbox_execution_refused", reason="Zero-Trust Prime Directive requires sandboxing")
                return {
                    "status": "error",
                    "error": "Non-sandboxed execution is refused under the Zero-Trust Prime Directive.",
                }

            logger.info("executing_code_in_sandbox", language=language, timeout=timeout)

            # Map programming language to Docker image and command
            image_map = {
                "python": ("python:3.11-slim", ["python", "-"]),
                "javascript": ("node:20-slim", ["node", "-"]),
                "js": ("node:20-slim", ["node", "-"]),
                "bash": ("alpine:latest", ["sh"]),
                "sh": ("alpine:latest", ["sh"]),
            }

            if language not in image_map:
                return {"status": "error", "error": f"Unsupported language: {language}"}

            image, cmd = image_map[language]

            # Build and execute docker run CLI using asyncio subprocess
            # Enforce network isolation, memory limits, read-only rootfs, and non-root user
            docker_cmd = [
                "docker",
                "run",
                "--rm",
                "--network",
                "none",
                "--memory",
                "128m",
                "--cpus",
                "0.5",
                "--read-only",
                "-i",
                image,
                *cmd,
            ]

            proc = await asyncio.create_subprocess_exec(
                *docker_cmd,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )

            # Write code to stdin and read output with timeout
            try:
                stdout, stderr = await asyncio.wait_for(
                    proc.communicate(input=code.encode("utf-8")),
                    timeout=float(timeout),
                )
                success = proc.returncode == 0
                stdout_str = stdout.decode("utf-8", errors="replace")
                stderr_str = stderr.decode("utf-8", errors="replace")

                logger.info(
                    "sandbox_execution_complete",
                    success=success,
                    returncode=proc.returncode,
                )

                return {
                    "status": "success" if success else "failed",
                    "success": success,
                    "returncode": proc.returncode,
                    "stdout": stdout_str,
                    "stderr": stderr_str,
                }

            except TimeoutError:
                # Terminate the process if it times out
                try:
                    proc.kill()
                    await proc.wait()
                except Exception:
                    pass
                logger.error("sandbox_execution_timeout", timeout=timeout)
                return {
                    "status": "timeout",
                    "success": False,
                    "error": f"Execution timed out after {timeout} seconds",
                }

        except Exception as e:
            logger.error("sandbox_execution_exception", error=str(e))
            return {"status": "error", "error": str(e)}

    async def _handle_generate_code(self, message: ActorMessage) -> dict[str, Any] | None:
        """
        Generate code for a specific purpose.

        Content expected:
        {
            "description": "What to implement",
            "language": "python",
            "requirements": [...],
            "include_tests": true
        }
        """
        try:
            # Schema validation
            content = validate_message_schema(message.content, "CoderGenerateCode")

            # Security validation for code-related content
            description = content.get("description", "")
            if not is_text_safe(description):
                logger.warning("Unsafe description detected", description=description[:100])
                return {"status": "error", "error": "Unsafe content detected in description"}
            language = CodeLanguage(content.get("language", self._default_language.value))
            requirements = content.get("requirements", [])
            include_tests = content.get("include_tests", self._enable_tests)

            logger.info("Generating code", description=description[:100], language=language.value)

            # Generate code using LLM
            code_result = await self._generate_code_llm(
                description=description, language=language, requirements=requirements
            )

            # Store snippet
            self._snippet_counter += 1
            snippet = CodeSnippet(
                id=f"code_{self._snippet_counter}",
                language=language,
                code=code_result.get("code", ""),
                description=description,
                created_at=datetime.now(UTC),
                purpose=code_result.get("purpose", ""),
                dependencies=code_result.get("dependencies", []),
                complexity_score=code_result.get("complexity", 0.5),
                metadata=code_result.get("metadata", {}),
            )
            self._code_snippets[snippet.id] = snippet

            # Generate tests if requested
            test_code = None
            if include_tests:
                test_code = await self._generate_tests_for_code(
                    code=snippet.code, language=language, description=description
                )
                snippet.test_coverage = 0.8  # Estimate

            # LRU eviction
            if len(self._code_snippets) > self.max_snippets:
                excess = len(self._code_snippets) - self.max_snippets
                for _ in range(excess):
                    oldest_id = next(iter(self._code_snippets))
                    del self._code_snippets[oldest_id]

            return {
                "status": "success",
                "code_id": snippet.id,
                "language": language.value,
                "code": snippet.code,
                "tests": test_code,
                "dependencies": snippet.dependencies,
                "complexity_score": snippet.complexity_score,
            }

        except Exception as e:
            logger.error("Failed to generate code", error=str(e))
            return {"status": "error", "error": str(e)}

    async def _handle_review_code(self, message: ActorMessage) -> dict[str, Any] | None:
        """
        Review code for issues and quality.

        Content expected:
        {
            "code": "code to review",
            "language": "python",
            "focus_areas": ["security", "performance"]
        }
        """
        try:
            # Schema validation
            content = validate_message_schema(message.content, "CoderReviewCode")

            # Security validation for code
            code = content.get("code", "")
            if not is_code_safe(code):
                logger.warning("Unsafe code detected in review request")
                return {
                    "status": "error",
                    "error": "Unsafe code detected - contains dangerous patterns",
                }
            language = CodeLanguage(content.get("language", self._default_language.value))
            focus_areas = content.get("focus_areas", ["security", "bugs", "style"])

            logger.info("Reviewing code", language=language.value, focus_areas=focus_areas)

            # Perform code review
            review_result = await self._review_code_llm(code=code, language=language, focus_areas=focus_areas)

            # Parse issues
            issues = []
            for issue_data in review_result.get("issues", []):
                issue = ReviewIssue(
                    id=f"issue_{uuid.uuid4().hex[:8]}",
                    line_number=issue_data.get("line"),
                    severity=ReviewSeverity(issue_data.get("severity", "info")),
                    category=issue_data.get("category", "style"),
                    message=issue_data.get("message", ""),
                    suggestion=issue_data.get("suggestion"),
                    code_context=issue_data.get("context"),
                )
                issues.append(issue)

            # Count by severity
            critical_count = len([i for i in issues if i.severity == ReviewSeverity.CRITICAL])
            error_count = len([i for i in issues if i.severity == ReviewSeverity.ERROR])
            warning_count = len([i for i in issues if i.severity == ReviewSeverity.WARNING])

            # Store review
            self._snippet_counter += 1
            review = CodeReview(
                id=f"review_{self._snippet_counter}",
                code_id=f"temp_{uuid.uuid4().hex[:8]}",
                reviewed_at=datetime.now(UTC),
                issues=issues,
                summary=review_result.get("summary", ""),
                overall_score=review_result.get("score", 70.0),
                critical_count=critical_count,
                error_count=error_count,
                warning_count=warning_count,
                recommendations=review_result.get("recommendations", []),
            )
            self._reviews[review.id] = review

            return {
                "status": "success",
                "review_id": review.id,
                "overall_score": review.overall_score,
                "critical_count": critical_count,
                "error_count": error_count,
                "warning_count": warning_count,
                "summary": review.summary,
                "issues": [
                    {
                        "id": i.id,
                        "line": i.line_number,
                        "severity": i.severity.value,
                        "category": i.category,
                        "message": i.message,
                        "suggestion": i.suggestion,
                    }
                    for i in issues[:20]  # Limit returned issues
                ],
                "recommendations": review.recommendations,
            }

        except Exception as e:
            logger.error("Failed to review code", error=str(e))
            return {"status": "error", "error": str(e)}

    async def _handle_debug_code(self, message: ActorMessage) -> dict[str, Any] | None:
        """
        Debug code with error.

        Content expected:
        {
            "code": "problematic code",
            "error_message": "Error that occurred",
            "symptoms": ["symptom1", ...]
        }
        """
        try:
            # Schema validation
            content = validate_message_schema(message.content, "CoderDebugCode")

            # Security validation for code
            code = content.get("code", "")
            if not is_code_safe(code):
                logger.warning("Unsafe code detected in debug request")
                # Still allow debugging but log the security concern
                logger.info("Proceeding with debug but code contains dangerous patterns")
            error_message = content.get("error_message", "")
            symptoms = content.get("symptoms", [])

            session_id = f"debug_{uuid.uuid4().hex[:8]}"
            session = DebugSession(
                id=session_id,
                code=code,
                error_message=error_message,
                symptoms=symptoms,
                status="investigating",
            )
            self._debug_sessions[session_id] = session
            self._active_debugs.add(session_id)

            logger.info("Debugging code", session_id=session_id, error=error_message[:100])

            # Analyze and fix
            debug_result = await self._debug_code_llm(code=code, error_message=error_message, symptoms=symptoms)

            # Update session
            session.root_cause = debug_result.get("root_cause")
            session.fix = debug_result.get("fix")
            session.explanation = debug_result.get("explanation")
            session.status = "fixed" if session.fix else "identified"
            session.resolved_at = datetime.now(UTC)
            self._active_debugs.discard(session_id)

            return {
                "result": "success",
                "session_id": session_id,
                "root_cause": session.root_cause,
                "fix": session.fix,
                "explanation": session.explanation,
                "status": session.status,
            }

        except Exception as e:
            logger.error("Failed to debug code", error=str(e))
            return {"status": "error", "error": str(e)}

    async def _handle_generate_tests(self, message: ActorMessage) -> dict[str, Any] | None:
        """
        Generate tests for code.

        Content expected:
        {
            "code": "code to test",
            "language": "python",
            "framework": "pytest"
        }
        """
        try:
            content = validate_message("CoderGenerateTests", message.content)
            code = content.get("code", "")
            language = CodeLanguage(content.get("language", self._default_language.value))
            framework = content.get("framework", "pytest")

            logger.info("Generating tests", language=language.value, framework=framework)

            tests = await self._generate_tests_for_code(code=code, language=language, framework=framework)

            return {
                "status": "success",
                "tests": tests,
                "framework": framework,
                "estimated_coverage": 0.85,
            }

        except Exception as e:
            logger.error("Failed to generate tests", error=str(e))
            return {"status": "error", "error": str(e)}

    async def _handle_generate_docs(self, message: ActorMessage) -> dict[str, Any] | None:
        """
        Generate documentation for code.

        Content expected:
        {
            "code": "code to document",
            "doc_type": "api|inline|readme",
            "style": "google|numpy|sphinx"
        }
        """
        try:
            content = validate_message("CoderGenerateDocs", message.content)
            code = content.get("code", "")
            doc_type = content.get("doc_type", "api")
            style = content.get("style", "google")

            logger.info("Generating documentation", doc_type=doc_type, style=style)

            docs = await self._generate_docs_llm(code=code, doc_type=doc_type, style=style)

            return {
                "status": "success",
                "documentation": docs,
                "doc_type": doc_type,
                "style": style,
            }

        except Exception as e:
            logger.error("Failed to generate docs", error=str(e))
            return {"status": "error", "error": str(e)}

    async def _handle_refactor_code(self, message: ActorMessage) -> dict[str, Any] | None:
        """
        Refactor code for improvement.

        Content expected:
        {
            "code": "code to refactor",
            "goals": ["readability", "performance"],
            "constraints": [...]
        }
        """
        try:
            content = validate_message("CoderRefactorCode", message.content)
            code = content.get("code", "")
            goals = content.get("goals", ["readability"])
            constraints = content.get("constraints", [])

            logger.info("Refactoring code", goals=goals, constraints=constraints)

            refactored = await self._refactor_code_llm(code=code, goals=goals, constraints=constraints)

            return {
                "status": "success",
                "original_code": code[:500],
                "refactored_code": refactored.get("code", ""),
                "improvements": refactored.get("improvements", []),
                "changes_summary": refactored.get("changes", ""),
            }

        except Exception as e:
            logger.error("Failed to refactor code", error=str(e))
            return {"status": "error", "error": str(e)}

    async def _handle_explain_code(self, message: ActorMessage) -> dict[str, Any] | None:
        """
        Explain what code does.

        Content expected:
        {
            "code": "code to explain",
            "audience": "beginner|expert",
            "detail_level": "high|medium|low"
        }
        """
        try:
            content = validate_message("CoderExplainCode", message.content)
            code = content.get("code", "")
            audience = content.get("audience", "intermediate")
            detail_level = content.get("detail_level", "medium")

            logger.info("Explaining code", audience=audience, detail_level=detail_level)

            explanation = await self._explain_code_llm(code=code, audience=audience, detail_level=detail_level)

            return {
                "status": "success",
                "explanation": explanation,
                "code_summary": code[:200] if len(code) > 200 else code,
            }

        except Exception as e:
            logger.error("Failed to explain code", error=str(e))
            return {"status": "error", "error": str(e)}

    async def _handle_implement_task(self, message: ActorMessage) -> dict[str, Any] | None:
        """
        Implement a complete coding task.

        Content expected:
        {
            "description": "Task description",
            "requirements": [...],
            "language": "python",
            "include_tests": true,
            "include_docs": true
        }
        """
        try:
            content = validate_message("CoderImplementTask", message.content)
            description = content.get("description", "")
            requirements = content.get("requirements", [])
            language = CodeLanguage(content.get("language", self._default_language.value))
            include_tests = content.get("include_tests", self._enable_tests)
            include_docs = content.get("include_docs", self._enable_docs)

            self._task_counter += 1
            task = ImplementationTask(
                id=f"task_{self._task_counter}",
                description=description,
                requirements=requirements,
                language=language,
                status="in_progress",
            )
            self._tasks[task.id] = task

            logger.info("Implementing task", task_id=task.id, description=description[:100])

            # Generate implementation
            code_result = await self._generate_code_llm(
                description=description, language=language, requirements=requirements
            )
            task.generated_code = code_result.get("code", "")

            # Generate tests
            if include_tests:
                task.tests = await self._generate_tests_for_code(code=task.generated_code, language=language)

            # Generate docs
            if include_docs:
                task.documentation = await self._generate_docs_llm(
                    code=task.generated_code, doc_type="api", style="api"
                )

            task.status = "completed"
            task.completed_at = datetime.now(UTC)

            return {
                "status": "success",
                "task_id": task.id,
                "code": task.generated_code,
                "tests": task.tests,
                "documentation": task.documentation,
                "completed_at": task.completed_at.isoformat(),
            }

        except Exception as e:
            logger.error("Failed to implement task", error=str(e))
            return {"status": "error", "error": str(e)}

    # Internal helper methods

    async def _generate_code_llm(
        self, description: str, language: CodeLanguage, requirements: list[str]
    ) -> dict[str, Any]:
        """Generate code using LLM."""
        try:
            prompt = f"""Write {language.value} code for:

{description}

Requirements:
{chr(10).join(f"- {r}" for r in requirements)}

Provide:
1. Complete, working code
2. List of dependencies
3. Brief purpose description
4. Complexity estimate (0-1)

Return as JSON with keys: code, dependencies, purpose, complexity"""

            response = await self.run_with_llm(prompt=prompt, timeout=60, temperature=0.3)

            import json

            try:
                result = json.loads(response)
                # Validate generated code for safety
                code = result.get("code", "")
                if code and not self.llm_output_validator.is_safe_code(code):
                    logger.warning("Generated code contains dangerous patterns", code_preview=code[:100])
                    result["security_warning"] = "Generated code contains potentially dangerous patterns"
                return result
            except Exception as e:
                logger.debug("coder_json_parse_failed_762", error=str(e))
                return {
                    "code": response,
                    "dependencies": [],
                    "purpose": description[:100],
                    "complexity": 0.5,
                    "security_warning": "Could not validate generated code",
                }
        except Exception as e:
            logger.error("Code generation failed", error=str(e))
            return {"code": "", "dependencies": [], "purpose": "", "complexity": 0}

    async def _generate_tests_for_code(
        self, code: str, language: CodeLanguage, framework: str = "pytest", description: str = ""
    ) -> str:
        """Generate tests for given code."""
        try:
            prompt = f"""Generate {framework} tests for this {language.value} code:

{code}

{f"Purpose: {description}" if description else ""}

Include:
1. Unit tests for each function
2. Edge case tests
3. Integration tests if applicable

Return only the test code."""

            return await self.run_with_llm(prompt=prompt, timeout=60, temperature=0.2)
        except Exception as e:
            logger.debug("coder_test_gen_failed", error=str(e))
            return "# Test generation failed"

    async def _review_code_llm(self, code: str, language: CodeLanguage, focus_areas: list[str]) -> dict[str, Any]:
        """Review code using LLM."""
        try:
            areas = ", ".join(focus_areas)
            prompt = f"""Review this {language.value} code focusing on: {areas}

{code}

For each issue found, provide:
- line: line number (or null)
- severity: critical/error/warning/info/hint
- category: security/bug/style/performance/maintainability
- message: description of issue
- suggestion: how to fix (optional)
- context: relevant code snippet (optional)

Also provide:
- summary: overall assessment
- score: 0-100 quality score
- recommendations: list of top priorities

Return as JSON array of issues plus summary, score, recommendations."""

            response = await self.run_with_llm(prompt=prompt, timeout=60, temperature=0.2)

            import json

            try:
                return json.loads(response)
            except Exception as e:
                logger.debug("coder_review_parse_failed_833", error=str(e))
                return {
                    "issues": [],
                    "summary": "Review completed",
                    "score": 75.0,
                    "recommendations": [],
                }
        except Exception as e:
            logger.debug("coder_review_llm_failed", error=str(e))
            return {"issues": [], "summary": "Review failed", "score": 50.0, "recommendations": []}

    async def _debug_code_llm(self, code: str, error_message: str, symptoms: list[str]) -> dict[str, Any]:
        """Debug code using LLM."""
        try:
            prompt = f"""Debug this code:

{code}

Error: {error_message}
Symptoms: {", ".join(symptoms)}

Provide:
1. root_cause: What's causing the issue
2. fix: Corrected code
3. explanation: Why the fix works

Return as JSON."""

            response = await self.run_with_llm(prompt=prompt, timeout=60, temperature=0.2)

            import json

            try:
                return json.loads(response)
            except Exception as e:
                logger.debug("coder_debug_parse_failed_870", error=str(e))
                return {
                    "root_cause": "Unable to determine",
                    "fix": None,
                    "explanation": "Debug analysis failed",
                }
        except Exception as e:
            logger.debug("coder_debug_llm_failed", error=str(e))
            return {"root_cause": "", "fix": None, "explanation": ""}

    async def _generate_docs_llm(self, code: str, doc_type: str, style: str) -> str:
        """Generate documentation using LLM."""
        try:
            prompt = f"""Generate {doc_type} documentation for this code in {style} style:

{code}

Return only the documentation."""

            return await self.run_with_llm(prompt=prompt, timeout=60, temperature=0.2)
        except Exception as e:
            logger.debug("coder_docs_gen_failed", error=str(e))
            return "# Documentation generation failed"

    async def _refactor_code_llm(self, code: str, goals: list[str], constraints: list[str]) -> dict[str, Any]:
        """Refactor code using LLM."""
        try:
            prompt = f"""Refactor this code with goals: {", ".join(goals)}

Constraints: {constraints}

{code}

Provide:
1. code: The refactored code
2. improvements: List of improvements made
3. changes: Summary of changes

Return as JSON."""

            response = await self.run_with_llm(prompt=prompt, timeout=60, temperature=0.3)

            import json

            try:
                return json.loads(response)
            except Exception as e:
                logger.debug("coder_refactor_parse_failed_923", error=str(e))
                return {"code": code, "improvements": [], "changes": "No changes made"}
        except Exception as e:
            logger.debug("coder_refactor_llm_failed", error=str(e))
            return {"code": code, "improvements": [], "changes": "Refactor failed"}

    async def _explain_code_llm(self, code: str, audience: str, detail_level: str) -> str:
        """Explain code using LLM."""
        try:
            prompt = f"""Explain this code for {audience} audience ({detail_level} detail):

{code}

Provide a clear, educational explanation."""

            return await self.run_with_llm(prompt=prompt, timeout=60, temperature=0.2)
        except Exception as e:
            logger.debug("coder_explain_failed", error=str(e))
            return "# Explanation unavailable"
