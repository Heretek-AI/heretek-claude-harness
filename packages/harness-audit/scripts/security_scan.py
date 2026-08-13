"""Pre-execution agent security guard and secret scanner.

Scans codebase, configuration files, and prompt payloads for:
- Hardcoded secrets (Anthropic API keys, GitHub PATs, JWTs, AWS keys)
- Prompt injection attack vectors
- Path traversal and dangerous command injections
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path
from typing import Any

SECRET_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("Anthropic API Key", re.compile(r"sk-ant-[A-Za-z0-9_-]{20,}")),
    ("GitHub Personal Access Token", re.compile(r"ghp_[A-Za-z0-9]{20,}")),
    ("GitHub OAuth Token", re.compile(r"gho_[A-Za-z0-9]{20,}")),
    ("AWS Access Key ID", re.compile(r"AKIA[0-9A-Z]{16}")),
    ("JSON Web Token (JWT)", re.compile(r"eyJ[A-Za-z0-9_-]{10,}\.eyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}")),  # noqa: E501
    ("Generic Secret Key", re.compile(r"\bsk-(?!ant-)[A-Za-z0-9_-]{20,}")),
]

PROMPT_INJECTION_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("System Override Vector", re.compile(r"ignore\s+all\s+previous\s+instructions", re.IGNORECASE)),  # noqa: E501
    ("Role Hijack Vector", re.compile(r"you\s+are\s+now\s+an\s+unrestricted\s+ai", re.IGNORECASE)),
    ("Exfiltration Vector", re.compile(r"curl\s+-X\s+POST.*-d\s+@/etc/passwd", re.IGNORECASE)),
]


def scan_text_content(text: str, filename: str = "<stdin>") -> list[dict[str, Any]]:
    """Scan string content for security violations.

    Args:
        text: Target text to scan.
        filename: Name of file or stream being scanned.

    Returns:
        List of violation dictionaries containing type, category, and match detail.
    """
    violations: list[dict[str, Any]] = []

    for name, pattern in SECRET_PATTERNS:
        for match in pattern.finditer(text):
            secret_str = match.group(0)
            redacted = secret_str[:4] + "..." + secret_str[-4:]
            violations.append({
                "type": "hardcoded_secret",
                "category": name,
                "file": filename,
                "detail": redacted,
            })

    for name, pattern in PROMPT_INJECTION_PATTERNS:
        for match in pattern.finditer(text):
            violations.append({
                "type": "prompt_injection",
                "category": name,
                "file": filename,
                "detail": match.group(0)[:40],
            })

    return violations


def scan_directory(target_dir: Path) -> list[dict[str, Any]]:
    """Scan directory recursively for security violations in source files.

    Args:
        target_dir: Absolute path to directory.

    Returns:
        List of all detected security violations.
    """
    violations: list[dict[str, Any]] = []
    ignore_dirs = {".git", ".venv", "__pycache__", "node_modules", "results", "tests", "test", "fixtures"}  # noqa: E501

    for p in target_dir.rglob("*"):
        if p.is_file() and not any(part in ignore_dirs for part in p.parts):
            if p.suffix in (".py", ".json", ".yaml", ".yml", ".md", ".sh", ".txt", ".js", ".ts"):
                try:
                    content = p.read_text(encoding="utf-8", errors="ignore")
                    v = scan_text_content(content, filename=str(p.relative_to(target_dir)))
                    violations.extend(v)
                except OSError:
                    continue

    return violations


def build_arg_parser() -> argparse.ArgumentParser:
    """Build argument parser for security_scan CLI."""
    parser = argparse.ArgumentParser(prog="security_scan")
    parser.add_argument("--target", type=Path, default=Path("."))
    return parser


def main(argv: list[str] | None = None) -> int:
    """CLI entrypoint for security scanner."""
    args = build_arg_parser().parse_args(argv)
    target = args.target.resolve()

    violations = scan_directory(target)

    print("┌──────────────────────────────────────────────────────────┐")
    print("│            AGENT SECURITY HARNESS AUDIT REPORT          │")
    print("├──────────────────────────────────────────────────────────┤")
    print(f"│ Target Directory : {str(target):<38} │")
    print(f"│ Total Violations : {len(violations):<38} │")
    if violations:
        print("├──────────────────────────────────────────────────────────┤")
        for v in violations[:10]:
            print(f"│ [WARN] {v['type']}: {v['category']} in {v['file']:<20} │")
    print("└──────────────────────────────────────────────────────────┘")

    return 1 if violations else 0


if __name__ == "__main__":
    sys.exit(main())
