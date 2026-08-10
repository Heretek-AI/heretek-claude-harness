#!/usr/bin/env python3
"""Pre-flight checker for SDD-style plans.

Catches recurring defects before they reach the implementer subagent:
  - `gh` CLI references when Global Constraints require GitHub MCP
  - Broken code fences (e.g., ```unknown instead of plain ```)
  - Duplicate canonical-item mentions across phases (e.g., TB 2.1 in two phases)
  - Term drift: repeated numeric phrases with mismatched counts vs the plan's own totals

Usage:
    python scripts/plan_pre_flight.py PATH/TO/PLAN.md

Exit 0 = clean, 1 = findings, 2 = usage error.

Not exhaustive — this is a fast scan for the most common recurring
defects observed during the roadmap-restructure migration. Plans
should also be read end-to-end by the controller before dispatch.
"""
from __future__ import annotations

import os
import re
import sys
from pathlib import Path

# Match `gh issue|gh pr|gh repo` invocations on a line.
GH_CLI_RE = re.compile(r"\bgh\s+(issue|pr|repo)\b")

# Fences with a language hint. Catches ```unknown, ```text-but-not-text, etc.
# Anything in this set is considered a known-good identifier.
KNOWN_FENCE_LANGS = frozenset({
    "bash", "sh", "zsh", "fish", "shell", "powershell", "ps1", "console",
    "python", "py", "python3", "javascript", "js", "typescript", "ts",
    "json", "jsonc", "yaml", "yml", "markdown", "md", "text", "txt",
    "plaintext", "html", "css", "scss", "sass", "sql", "go", "rust",
    "ruby", "rb", "java", "kotlin", "c", "cpp", "c++", "cs", "csharp",
    "xml", "toml", "ini", "diff", "patch", "log", "dockerfile",
    "makefile", "dotenv", "gitignore", "http", "graphql", "none",
})

# Canonical-item phrases to detect cross-phase duplication.
# Each maps to a regex that finds mentions in plan text.
CANONICAL_ITEMS = {
    "Terminal-Bench 2.1": re.compile(r"Terminal-?Bench\s*2\.1", re.IGNORECASE),
    "v6-emerging-patterns": re.compile(r"v6[\-_ ]emerging[\-_ ]patterns", re.IGNORECASE),
}


def check_gh_cli_under_mcp_constraints(text: str) -> list[str]:
    """If the plan's Global Constraints mention MCP-only (no `gh CLI`), flag
    any `gh ...` usage in the body."""
    says_use_mcp = bool(
        re.search(r"use\s+GitHub\s+MCP", text, re.IGNORECASE)
        or re.search(r"NOT\s+`?gh`?\s+CLI", text, re.IGNORECASE)
    )
    if not says_use_mcp:
        return []
    findings = []
    for i, line in enumerate(text.splitlines(), 1):
        if GH_CLI_RE.search(line):
            findings.append(
                f"line {i}: `gh ...` reference under MCP-only constraints — {line.strip()}"
            )
    return findings


def check_broken_fences(text: str) -> list[str]:
    r"""Flag opening fences with a token that isn't a known language identifier.

    A triple-backtick + `unknown` style fence (often a placeholder from a
    brief template) renders as plain text in most viewers — that's the bug
    we want to catch.
    """
    findings = []
    fence_re = re.compile(r"^```(\S+)")
    for i, line in enumerate(text.splitlines(), 1):
        m = fence_re.match(line)
        if not m:
            continue
        lang = m.group(1)
        if lang in KNOWN_FENCE_LANGS:
            continue
        findings.append(f"line {i}: unknown fence language `{lang}` — {line.strip()!r}")
    return findings


def check_duplicate_canonical_items(text: str) -> list[str]:
    """Flag canonical items that are mentioned in more than one phase section."""
    findings = []
    for name, pattern in CANONICAL_ITEMS.items():
        sections = []
        current_section = ""
        for line in text.splitlines():
            # Phase sections start with `## vN` or `### vN` headers.
            if re.match(r"^#{2,4}\s+v\d", line):
                current_section = line.strip()
            if pattern.search(line):
                sections.append(current_section or "<top>")
        if len(set(sections)) > 1:
            sections_str = ", ".join(f"`{s}`" for s in sorted(set(sections)))
            findings.append(
                f"{name} appears in multiple sections: {sections_str}"
            )
    return findings


def check_count_drift(text: str) -> list[str]:
    """Heuristic: flag lines with counts (e.g., `9 spike ADRs`) that appear
    near a section declaring a different total (e.g., the spec totals table)."""
    # Match "N <noun>" patterns where N is a small integer.
    count_re = re.compile(r"\b(\d{1,2})\s+(spike|rejection|items?|adrs?|files?)\b", re.IGNORECASE)
    counts = {}  # noun -> set of N values seen
    for line in text.splitlines():
        for m in count_re.finditer(line):
            n = int(m.group(1))
            noun = m.group(2).lower()
            counts.setdefault(noun, set()).add(n)
    findings = []
    for noun, values in counts.items():
        if len(values) > 1:
            sorted_vals = sorted(values)
            findings.append(
                f"count drift for `{noun}`: saw values {sorted_vals} in different places"
            )
    return findings


def _resolve_plan_path(raw: str) -> Path | None:
    """Resolve and validate a CLI-provided plan path.

    Rejects paths that escape the current working directory. The script
    is meant to scan in-repo plan files; an LLM-controlled caller passing
    a path like `../../etc/passwd` or an absolute system path would
    otherwise read arbitrary files.
    """
    try:
        resolved = Path(os.path.realpath(raw))
    except (OSError, RuntimeError):
        return None
    cwd = Path(os.path.realpath(os.getcwd()))
    try:
        resolved.relative_to(cwd)
    except ValueError:
        return None
    if not resolved.is_file():
        return None
    return resolved


def main() -> int:
    if len(sys.argv) != 2:
        print("usage: plan_pre_flight.py PLAN_FILE", file=sys.stderr)
        return 2
    plan_path = _resolve_plan_path(sys.argv[1])
    if plan_path is None:
        print(
            f"error: {sys.argv[1]!r} is not a readable file within the current directory",
            file=sys.stderr,
        )
        return 2
    text = plan_path.read_text(encoding="utf-8")

    findings: list[str] = []
    findings.extend(check_gh_cli_under_mcp_constraints(text))
    findings.extend(check_broken_fences(text))
    findings.extend(check_duplicate_canonical_items(text))
    findings.extend(check_count_drift(text))

    if findings:
        print(f"plan-pre-flight: {len(findings)} finding(s) in {plan_path.name}")
        for f in findings:
            print(f"  - {f}")
        return 1
    print(f"plan-pre-flight: clean ({plan_path.name})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
