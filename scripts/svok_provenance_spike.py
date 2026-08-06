"""SVoK / provenance comments spike (#48) — prototype.

Given a code snippet, identifies external-API usages and emits provenance
comments naming the doc-version consulted (from the freshness cache).

This is research code. Production integration is a follow-up issue if
the prototype proves out.
"""
from __future__ import annotations

import re
from datetime import datetime, timezone
from pathlib import Path

import yaml

CACHE_DIR = Path(__file__).resolve().parent.parent / "catalog" / "freshness"
# Match `import X` / `from X import Y` for top-level imports + common usage forms
IMPORT_RE = re.compile(r"^(?:from|import)\s+([a-zA-Z_][a-zA-Z0-9_.]*)", re.MULTILINE)
USAGE_RE = re.compile(r"\b([a-zA-Z_][a-zA-Z0-9_.]*)\.")
# Python import name -> catalog/freshness name aliases (catalog files are
# spelled by package name on PyPI, not by import name).
_PACKAGE_ALIASES: dict[str, str] = {
    "yaml": "pyyaml",
    "ruamel": "ruamel-yaml",
}


def _doc_version_for(lib: str) -> str | None:
    cache_file = CACHE_DIR / f"{lib.lower().replace('.', '-')}.yaml"
    if not cache_file.exists():
        return None
    try:
        data = yaml.safe_load(cache_file.read_text())
    except yaml.YAMLError:
        return None
    return data.get("latest_version")


def _stdlib_libs() -> set[str]:
    """Approximation — Python stdlib modules (limited set; production would be complete)."""
    return {
        "os", "sys", "json", "re", "pathlib", "collections", "typing",
        "datetime", "time", "itertools", "functools", "subprocess",
        "math", "random", "hashlib", "logging", "unittest", "io",
    }


def emit_provenance_comments(code: str) -> str:
    """Emit provenance comments naming doc-version for external APIs used."""
    imports = set()
    for match in IMPORT_RE.finditer(code):
        imports.add(match.group(1).split(".")[0])

    external = imports - _stdlib_libs()
    today = datetime.now(timezone.utc).date().isoformat()
    provenance_lines = []

    for lib in sorted(external):
        catalog_name = _PACKAGE_ALIASES.get(lib, lib)
        version = _doc_version_for(catalog_name)
        if version:
            provenance_lines.append(
                f"# generated against {catalog_name} docs v{version} (fetched {today})"
            )

    if not provenance_lines:
        return code

    # Insert provenance block after the first import line (or at top if no imports)
    lines = code.splitlines()
    insert_idx = 0
    for i, line in enumerate(lines):
        if line.startswith("import ") or line.startswith("from "):
            insert_idx = i + 1
            break

    return "\n".join(lines[:insert_idx] + [""] + provenance_lines + [""] + lines[insert_idx:])


if __name__ == "__main__":
    import sys
    print(emit_provenance_comments(sys.stdin.read()))
