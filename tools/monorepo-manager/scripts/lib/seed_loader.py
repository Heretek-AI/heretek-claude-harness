"""Seed loader: validate seeds/*.yaml and emit GitHub-issue body markdown."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

import yaml
from jsonschema import Draft202012Validator

_SCHEMA_PATH = Path(__file__).parents[2] / "schemas" / "seed.schema.json"
_LABELS_PATH = Path(__file__).parents[2] / "seeds" / "labels.yaml"
_ID_PATTERN = re.compile(r"^[a-z]{2}-[0-9]{4}$")
_BODY_FOOTER = (
    "_Filed by scripts/seed-issues.sh from seeds/<repo>.yaml. Re-running the "
    "script with the same seed is idempotent (issues are matched by seed-id: "
    "<id> HTML comment at the top)._"
)


class SeedValidationError(Exception):
    """Raised when a seed fails schema or cross-reference validation."""


def _load_schema() -> dict:
    return json.loads(_SCHEMA_PATH.read_text(encoding="utf-8"))


def load_seed(path: str, known_labels: list[str] | None = None) -> dict:
    """Load and validate a seed YAML file. Raises SeedValidationError on failure.

    If ``known_labels`` is provided, it is used directly for per-issue label
    validation. Otherwise the loader reads ``seeds/labels.yaml`` adjacent to
    the seed file (sibling in the same directory) and uses that as the
    canonical label set.
    """
    try:
        schema = _load_schema()
    except OSError as e:
        raise SeedValidationError(f"could not read schema: {e}") from e
    except json.JSONDecodeError as e:
        raise SeedValidationError(f"invalid schema JSON: {e}") from e
    try:
        with open(path, encoding="utf-8") as f:
            data = yaml.safe_load(f)
    except OSError as e:
        raise SeedValidationError(f"could not read seed file {path!r}: {e}") from e
    except yaml.YAMLError as e:
        raise SeedValidationError(f"invalid YAML in {path!r}: {e}") from e
    validator = Draft202012Validator(schema)
    errors = sorted(validator.iter_errors(data), key=lambda e: e.path)
    if errors:
        msgs = [
            f"{'/'.join(str(p) for p in e.absolute_path) or '<root>'}: {e.message}" for e in errors
        ]
        raise SeedValidationError("seed schema violation:\n  " + "\n  ".join(msgs))

    # Duplicate-id guard: schema enforces per-id uniqueness, but cross-ref
    # validation downstream needs a stable set; check explicitly so we can
    # surface a clear error path before per-issue runs.
    ids_seen: set[str] = set()
    duplicates: list[str] = []
    for issue in data["issues"]:
        iid = issue["id"]
        if iid in ids_seen:
            duplicates.append(iid)
        ids_seen.add(iid)
    if duplicates:
        dup_list = ", ".join(sorted(set(duplicates)))
        raise SeedValidationError(f"seed has duplicate issue ids: {dup_list}")

    # Per-issue semantic validation against the canonical label set runs
    # BEFORE cross-reference checks so unknown-label errors surface first.
    if known_labels is None:
        try:
            known_labels = _load_known_labels(path)
        except SeedValidationError as e:
            raise SeedValidationError(f"could not load labels for {path!r}: {e}") from e
    issue_errors: list[str] = []
    for issue in data["issues"]:
        for err in validate_issue(issue, known_labels):
            issue_errors.append(f"{issue['id']}: {err}")
    if issue_errors:
        raise SeedValidationError("seed issue validation:\n  " + "\n  ".join(issue_errors))

    known_ids = ids_seen
    extra: list[str] = []
    for issue in data["issues"]:
        for dep in issue.get("depends_on", []):
            if dep not in known_ids:
                extra.append(f"{issue['id']}: depends_on {dep!r} not present in seed")
    if extra:
        raise SeedValidationError("seed cross-reference violation:\n  " + "\n  ".join(extra))
    return data


def _load_known_labels(seed_path: str | None = None) -> list[str]:
    """Load the canonical label set from the umbrella's seeds/labels.yaml.

    Falls back to a sibling ``labels.yaml`` next to ``seed_path`` if the
    umbrella file is unavailable (e.g. when the seed lives in a child repo
    that has its own ``.github/labels/labels.yaml`` copy).
    """
    candidates: list[Path] = []
    if seed_path is not None:
        candidates.append(Path(seed_path).resolve().parent / "labels.yaml")
    candidates.append(_LABELS_PATH)
    for labels_path in candidates:
        try:
            with open(labels_path, encoding="utf-8") as f:
                data = yaml.safe_load(f)
        except OSError:
            continue
        except yaml.YAMLError as e:
            raise SeedValidationError(f"invalid YAML in {labels_path}: {e}") from e
        if not isinstance(data, dict) or "labels" not in data:
            continue
        return [str(label["name"]) for label in data["labels"]]
    raise SeedValidationError(f"could not find a valid labels.yaml (tried {candidates})")


def validate_issue(issue: dict, known_labels: list[str]) -> list[str]:
    """Return a list of human-readable errors for an issue dict; empty if valid."""
    errors: list[str] = []
    label_axes = {
        "phase": issue.get("phase"),
        "component": issue.get("component"),
        "status": issue.get("status"),
    }
    for axis, label in label_axes.items():
        if label not in known_labels:
            errors.append(f"{axis}: unknown label {label!r}")
    issue_id = issue.get("id")
    if not issue_id or not _ID_PATTERN.match(issue_id):
        errors.append(f"id: must match ^[a-z]{{2}}-[0-9]{{4}}$ (got {issue_id!r})")
    if not issue.get("acceptance"):
        errors.append("acceptance: must contain at least one item")
    if not issue.get("title"):
        errors.append("title: must not be empty")
    return errors


def emit_body_markdown(issue: dict) -> str:
    """Render the 5-section body markdown for one issue (without any title or labels)."""
    src = issue["source"]
    deps = issue.get("depends_on", []) or []
    deps_block = "\n".join(f"- `{d}`" for d in deps) if deps else "_None._"
    oos = issue.get("out_of_scope", []) or []
    oos_block = "\n".join(f"- {line}" for line in oos) if oos else "_None._"
    acceptance = "\n".join(f"- [ ] {line}" for line in issue["acceptance"])
    return (
        f"<!-- seed-id: {issue['id']} -->\n"
        f"## Source\n"
        f"- Doc: `{src['doc']}`\n"
        f"- Section: {src['section']}\n"
        f"- Repo: {issue.get('_repo', 'Heretek-AI/<repo>')}\n"
        f"\n"
        f"## Goal\n"
        f"{issue['goal'].strip()}\n"
        f"\n"
        f"## Acceptance criteria\n"
        f"{acceptance}\n"
        f"\n"
        f"## Out of scope\n"
        f"{oos_block}\n"
        f"\n"
        f"## Dependencies\n"
        f"{deps_block}\n"
        f"\n"
        f"---\n"
        f"{_BODY_FOOTER}\n"
    )


def _main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="seed_loader")
    parser.add_argument("command", choices=["validate", "emit"])
    parser.add_argument("path")
    parser.add_argument("id", nargs="?", default=None)
    args = parser.parse_args(argv)

    try:
        seed = load_seed(args.path)
    except SeedValidationError as e:
        print(str(e), file=sys.stderr)
        return 2

    if args.command == "validate":
        return 0

    if args.id is None:
        print("emit: id is required", file=sys.stderr)
        return 2
    for issue in seed["issues"]:
        if issue["id"] == args.id:
            issue = dict(issue)
            issue["_repo"] = seed["repo"]
            sys.stdout.write(emit_body_markdown(issue))
            return 0
    print(f"emit: id {args.id!r} not found in {args.path}", file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(_main())
