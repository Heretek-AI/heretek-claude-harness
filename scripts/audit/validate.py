"""Validate audit finding cards against the finding JSON Schema.

Run as CLI:
    python scripts/audit/validate.py [--schema PATH] <file1.yaml|json> [file2 ...]
Exit codes: 0 if every card validates, 1 if any fails. Errors are printed
to stderr; per-file summary goes to stdout.
Library API:
    validate_finding(finding: dict) -> list[str]
    validate_findings(findings: list[dict]) -> list[tuple[int, list[str]]]
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Iterable

import jsonschema
from ruamel.yaml import YAML

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_SCHEMA = REPO_ROOT / "tests" / "schemas" / "audit_finding.schema.json"

SCHEMA_PATH: Path = DEFAULT_SCHEMA  # tests may monkeypatch


def _load_instance(path: Path) -> dict:
    text = path.read_text()
    if path.suffix.lower() in {".yaml", ".yml"}:
        result = YAML(typ="safe").load(text)
        if result is None:
            raise ValueError(f"empty or whitespace-only YAML in {path}")
        return result
    return json.loads(text)


def validate_finding(finding: dict) -> list[str]:
    """Return a list of error messages for one finding; empty = valid."""
    schema = json.loads(SCHEMA_PATH.read_text())
    validator = jsonschema.Draft202012Validator(schema)
    return [f"{e.json_path}: {e.message}" for e in validator.iter_errors(finding)]


def validate_findings(findings: list[dict]) -> list[tuple[int, list[str]]]:
    """Validate a list; return [(index, errors)] for every invalid entry."""
    return [
        (i, errs)
        for i, f in enumerate(findings)
        for errs in [validate_finding(f)]
        if errs
    ]


def main(argv: Iterable[str] | None = None) -> int:
    global SCHEMA_PATH  # noqa: PLW0603
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--schema", type=Path, default=SCHEMA_PATH)
    parser.add_argument("files", nargs="+", type=Path)
    args = parser.parse_args(argv)

    SCHEMA_PATH = args.schema

    any_errors = False
    for path in args.files:
        file_has_errors = False
        try:
            instance = _load_instance(path)
        except (json.JSONDecodeError, ValueError) as exc:
            print(f"{path}: parse error: {exc}", file=sys.stderr)
            any_errors = True
            file_has_errors = True
            continue

        # A file may contain a single finding OR a list of findings.
        findings = instance if isinstance(instance, list) else [instance]
        for idx, errors in validate_findings(findings):
            file_has_errors = True
            print(f"{path}#{idx}:", file=sys.stderr)
            for e in errors:
                print(f"  - {e}", file=sys.stderr)

        if not file_has_errors:
            print(f"{path}: OK ({len(findings)} finding(s))")
        else:
            any_errors = True

    return 1 if any_errors else 0


if __name__ == "__main__":
    sys.exit(main())
