"""Stub detection patterns using regex and AST analysis."""

from __future__ import annotations

import ast
import re
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

import structlog

logger = structlog.get_logger(__name__)

# ---------------------------------------------------------------------------
# Pattern definitions
# ---------------------------------------------------------------------------


@dataclass
class Pattern:
    """A stub detection pattern."""

    name: str
    severity: str  # "CRITICAL", "WARNING", "INFO"
    description: str
    pattern_type: str  # "regex" | "ast"


# Regex patterns keyed by name
REGEX_PATTERNS: dict[str, Pattern] = {
    "PassOnlyStatement": Pattern(
        name="PassOnlyStatement",
        severity="CRITICAL",
        description="Function body contains only a `pass` statement — no real logic.",
        pattern_type="regex",
    ),
    "ReturnEmptyDict": Pattern(
        name="ReturnEmptyDict",
        severity="CRITICAL",
        description="Function returns an empty dict `{}` — indicates placeholder return.",
        pattern_type="regex",
    ),
    "ReturnNone": Pattern(
        name="ReturnNone",
        severity="CRITICAL",
        description="Function unconditionally returns None — data expected but nothing provided.",
        pattern_type="regex",
    ),
    "RaiseNotImplementedError": Pattern(
        name="RaiseNotImplementedError",
        severity="CRITICAL",
        description="Function raises NotImplementedError — method not yet implemented.",
        pattern_type="regex",
    ),
    "SetIntervalJavaScript": Pattern(
        name="SetIntervalJavaScript",
        severity="WARNING",
        description="`setInterval` detected — likely demo/timer code in production.",
        pattern_type="regex",
    ),
    "GenerateRandomFunction": Pattern(
        name="GenerateRandomFunction",
        severity="WARNING",
        description="Function named `generateRandom` detected — may be test/sample utility.",
        pattern_type="regex",
    ),
    "MathRandomJavaScript": Pattern(
        name="MathRandomJavaScript",
        severity="INFO",
        description="`Math.random` usage in JS/TS — may indicate non-deterministic stub.",
        pattern_type="regex",
    ),
}

# AST-based pattern names
AST_PATTERNS: dict[str, type] = {
    "PassOnlyFunction": ast.Pass,  # checked at function level
    "ReturnEmptyDictFunction": ast.Dict,  # checked at function return level
    "NotImplementedModule": ast.Raise,  # checked at module level
    "DuplicateClassDefinition": ast.ClassDef,
    "SampleDataGenerator": ast.FunctionDef,
}

# Regex patterns to scan
REGEX_RE_LIST = [
    (re.compile(r"^\s*pass\s*(?:#.*)?$"), "PassOnlyStatement"),
    (re.compile(r"^\s*return\s+{}\s*(?:#.*)?$"), "ReturnEmptyDict"),
    (re.compile(r"^\s*return\s+None\s*(?:#.*)?$"), "ReturnNone"),
    (re.compile(r"^\s*raise\s+NotImplementedError\b"), "RaiseNotImplementedError"),
    (re.compile(r"\bsetInterval\s*\("), "SetIntervalJavaScript"),
    (re.compile(r"\bgenerateRandom\b"), "GenerateRandomFunction"),
    (re.compile(r"\bMath\.random\b"), "MathRandomJavaScript"),
]

# Files with these extensions will be scanned
DEFAULT_EXTENSIONS = {".py", ".js", ".ts", ".jsx", ".tsx"}

# Exclusion patterns
EXCLUDED_DIRS = {
    "tests",
    "__pycache__",
    ".venv",
    "node_modules",
    ".git",
    ".pytest_cache",
}
EXCLUDED_NAME_PARTS = re.compile(r"_sample|_test|_demo")

# Files excluded from scanning (self-referential: audit tool detecting its own code)
EXCLUDED_FILES = frozenset(
    {
        "stub_patterns.py",  # self-referential: generateRandom is the audit tool's own utility
    }
)

# Function names excluded from SampleDataGenerator pattern
# These match the naming convention but are legitimate production utilities
EXCLUDED_FUNCTIONS = frozenset(
    {
        # Production utility in collective/agency_tracking.py, exported and used in API
        "create_sample_metrics",
    }
)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

if TYPE_CHECKING:
    from heretek_swarm.audit.report import AuditFinding


def scan_file(
    path: str | Path,
    patterns: list[str] | None = None,
) -> list[AuditFinding]:
    """Scan a single file for stub patterns.

    Args:
        path: Path to the file to scan.
        patterns: Optional list of pattern names to match. Defaults to all.

    Returns:
        List of AuditFinding objects for each match.
    """
    from heretek_swarm.audit.report import AuditFinding

    findings: list[AuditFinding] = []
    path = Path(path)

    # Apply exclusions by filename
    if EXCLUDED_NAME_PARTS.search(path.name):
        return findings

    # Skip self-referential files (audit tool detecting its own utility functions)
    if path.name in EXCLUDED_FILES:
        return findings

    if not path.is_file():
        return findings

    try:
        content = path.read_text(encoding="utf-8", errors="ignore")
    except (OSError, UnicodeDecodeError) as e:
        return findings

    # Filter pattern names if provided
    active_pattern_names = set(patterns) if patterns else set(REGEX_PATTERNS)
    active_re_list = [
        (compiled_re, name) for compiled_re, name in REGEX_RE_LIST if name in active_pattern_names
    ]

    # Regex scan
    for line_no, line in enumerate(content.splitlines(), start=1):
        for compiled_re, name in active_re_list:
            if compiled_re.search(line):
                findings.append(
                    AuditFinding(
                        file=str(path),
                        line=line_no,
                        pattern_name=name,
                        severity=REGEX_PATTERNS[name].severity,
                        description=REGEX_PATTERNS[name].description,
                    )
                )

    # AST scan for Python files
    if path.suffix == ".py":
        findings.extend(_scan_ast(content, str(path), patterns))

    return findings


def _scan_ast(
    source: str,
    filename: str,
    patterns: list[str] | None,
) -> list[AuditFinding]:
    """Scan Python source with AST analysis."""
    from heretek_swarm.audit.report import AuditFinding

    findings: list[AuditFinding] = []

    try:
        tree = ast.parse(source, filename=filename)
    except SyntaxError as e:
        return findings

    active_pattern_names = set(patterns) if patterns else set(AST_PATTERNS)

    for node in ast.walk(tree):
        _check_not_implemented_module(node, active_pattern_names, filename, findings)
        _check_duplicate_class(node, active_pattern_names, filename, tree, findings)
        _check_sample_data_generator(node, active_pattern_names, filename, findings)

    return findings


def _check_not_implemented_module(
    node: ast.AST, active: set[str], filename: str, findings: list[AuditFinding],
) -> None:
    """Check for module-level raise NotImplementedError."""
    if (
        "NotImplementedModule" in active
        and isinstance(node, ast.Raise)
        and isinstance(node.exc, ast.Name)
        and node.exc.id == "NotImplementedError"
        and getattr(node, "col_offset", -1) == 0
    ):
        findings.append(
            AuditFinding(
                file=filename, line=node.lineno or 0,
                pattern_name="NotImplementedModule", severity="CRITICAL",
                description="Module-level `raise NotImplementedError` detected — entire module is unimplemented.",
            )
        )


def _check_duplicate_class(
    node: ast.AST, active: set[str], filename: str,
    tree: ast.Module, findings: list[AuditFinding],
) -> None:
    """Check for duplicate class definitions at module level."""
    if "DuplicateClassDefinition" not in active or not isinstance(node, ast.ClassDef):
        return
    if node not in tree.body:
        return
    class_count = sum(
        1 for n in tree.body if isinstance(n, ast.ClassDef) and n.name == node.name
    )
    if class_count > 1:
        findings.append(
            AuditFinding(
                file=filename, line=node.lineno or 0,
                pattern_name="DuplicateClassDefinition", severity="INFO",
                description=f"Class `{node.name}` defined multiple times at module scope.",
            )
        )


def _check_sample_data_generator(
    node: ast.AST, active: set[str], filename: str, findings: list[AuditFinding],
) -> None:
    """Check for sample data generator functions."""
    if "SampleDataGenerator" in active and isinstance(node, ast.FunctionDef):
            node, (ast.FunctionDef, ast.AsyncFunctionDef)
        ):
            name = node.name
            if name.startswith(("create_sample_", "_sample_")):
                # Exclude known legitimate production utilities
                if name in EXCLUDED_FUNCTIONS:
                    continue
                findings.append(
                    AuditFinding(
                        file=filename,
                        line=node.lineno or 0,
                        pattern_name="SampleDataGenerator",
                        severity="WARNING",
                        description=f"Function `{name}` is a sample data generator.",
                    )
                )

    return findings


def scan_directory(
    root: str | Path,
    patterns: list[str] | None = None,
    extensions: set[str] | None = None,
) -> list[AuditFinding]:
    """Recursively scan a directory for stub patterns.

    Args:
        root: Root directory to scan.
        patterns: Optional list of pattern names to match.
        extensions: Set of file extensions to scan (e.g. {".py"}). Defaults to all.

    Returns:
        Combined list of AuditFinding from all scanned files.
    """
    findings: list[AuditFinding] = []
    root = Path(root)
    extensions = extensions or DEFAULT_EXTENSIONS

    for path in root.rglob("*"):
        if any(part in path.parts for part in EXCLUDED_DIRS):
            continue
        if not path.is_file():
            continue
        if path.suffix not in extensions:
            continue
        findings.extend(scan_file(path, patterns))

    return findings
