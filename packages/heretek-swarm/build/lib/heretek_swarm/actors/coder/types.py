"""Coder types — Code language, task, and review data structures."""

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

import structlog

logger = structlog.get_logger(__name__)

class CodeLanguage(StrEnum):
    """Supported programming languages."""

    PYTHON = "python"
    JAVASCRIPT = "javascript"
    TYPESCRIPT = "typescript"
    GO = "go"
    RUST = "rust"
    JAVA = "java"
    CPP = "cpp"
    SQL = "sql"
    SHELL = "shell"
    YAML = "yaml"
    JSON = "json"
    MARKDOWN = "markdown"

class CodeTask(StrEnum):
    """Types of coding tasks."""

    IMPLEMENT = "implement"
    REVIEW = "review"
    REFACTOR = "refactor"
    DEBUG = "debug"
    TEST = "test"
    DOCUMENT = "document"
    EXPLAIN = "explain"
    OPTIMIZE = "optimize"

class ReviewSeverity(StrEnum):
    """Code review issue severity."""

    CRITICAL = "critical"  # Security vulnerability, crash
    ERROR = "error"  # Bug, incorrect logic
    WARNING = "warning"  # Code smell, potential issue
    INFO = "info"  # Suggestion, style note
    HINT = "hint"  # Minor improvement

@dataclass
class CodeSnippet:
    """Generated or analyzed code snippet."""

    id: str
    language: CodeLanguage
    code: str
    description: str
    created_at: datetime
    purpose: str = ""  # What this code does
    dependencies: list[str] = field(default_factory=list)
    complexity_score: float = 0.0  # 0-1 complexity estimate
    test_coverage: float = 0.0  # 0-1 test coverage
    metadata: dict[str, Any] = field(default_factory=dict)

@dataclass
class ReviewIssue:
    """Code review issue."""

    id: str
    line_number: int | None
    severity: ReviewSeverity
    category: str  # security/bug/style/performance/maintainability
    message: str
    suggestion: str | None = None
    code_context: str | None = None

@dataclass
class CodeReview:
    """Complete code review result."""

    id: str
    code_id: str
    reviewed_at: datetime
    issues: list[ReviewIssue]
    summary: str
    overall_score: float  # 0-100 quality score
    critical_count: int = 0
    error_count: int = 0
    warning_count: int = 0
    recommendations: list[str] = field(default_factory=list)

@dataclass
class DebugSession:
    """Debugging session record."""

    id: str
    code: str
    error_message: str
    symptoms: list[str]
    root_cause: str | None = None
    fix: str | None = None
    explanation: str | None = None
    started_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    resolved_at: datetime | None = None
    status: str = "investigating"  # investigating/identified/fixed/cannot_reproduce

@dataclass
class ImplementationTask:
    """Code implementation task."""

    id: str
    description: str
    requirements: list[str]
    language: CodeLanguage
    generated_code: str | None = None
    tests: str | None = None
    documentation: str | None = None
    status: str = "pending"  # pending/in_progress/completed/failed
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    completed_at: datetime | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
