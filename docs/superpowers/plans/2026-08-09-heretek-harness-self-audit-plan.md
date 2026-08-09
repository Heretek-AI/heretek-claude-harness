# Harness Self-Audit (Spec 1 of 3) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship the audit toolkit that turns the hostile principles audit spec into a runnable pipeline — schema, validator, synthesis driver, issue-creation driver, and orchestrator — so the 5 cluster lanes can be dispatched, results validated, and HIGH/CRITICAL findings auto-filed as GitHub issues with a 5/cluster cap and umbrella-issue bundling.

**Architecture:** Eight small modules under `scripts/audit/` plus one driver. Each module has one clear responsibility: `validate.py` enforces the per-finding JSON Schema; `findings.py` provides the Finding dataclass + load/save helpers; `prompts.py` holds the 5 cluster prompt templates; `synthesis.py` runs the re-verification gate + dedupe + cross-ref; `issues.py` builds GitHub MCP payloads (with the cap + umbrella logic); `harness_self.py` is the CLI driver that ties them together. The actual cluster-lane agent dispatch happens at execution time by the executor pasting prompts to fresh Explore-agents — the toolkit operates on the resulting findings files.

**Tech Stack:** Python 3.10+ (matches `pyproject.toml` `requires-python`), `pytest`, `jsonschema` (already a runtime dep), `ruamel.yaml` (already a dev dep for the existing harness), `GitHub MCP` (no new deps; uses `mcp__github__*` tools). No new Python deps added.

## Global Constraints

These apply to every task in this plan. Copy values verbatim from the spec where given:

- **Spec under implementation:** `docs/superpowers/specs/2026-08-09-heretek-harness-self-audit-design.md` (commit `7539385`).
- **In scope (harness code):** `scripts/*.py`, `scripts/scanners/*.py`, `tests/`, `plugins/hooks/`, root configs (`pyproject.toml`, `sonar-project.properties`, `requirements*.txt`, `.gitignore`), root docs (`CLAUDE.md`, `CONTRIBUTING.md`, `SECURITY.md`).
- **Out of scope:** `catalog/` (data), `docs/superpowers/{specs,plans,reviews,spikes,research,issue-drafts}/` (design artifacts), `plugins/*/` other than `plugins/hooks/` (Spec 2), `.github/workflows/` enforcement behavior (Spec 3), `.omc/`, `.agents/`, `.claude/`, `.superpowers/`, `README.md`, `LICENSE`, `CHANGELOG.md`.
- **Per-finding schema (verbatim from spec):** every finding card has `finding_id` (`<cluster_letter>-<NNN>`, deterministic), `cluster`, `principle`, `severity` ∈ {critical, high, medium, low, info}, `adversarial_posture` ∈ {violated, partial, justified}, `evidence.{code_refs, file, line_range, metric}`, `failure_scenario`, `recommended_action` ∈ {refactor, document, suppress, accept, escalate}, `rationale`, `principle_reference`, `drift_signals[]`.
- **Severity → auto-issue mapping:** `critical` → `P0`; `high` → `P1`; `medium`/`low`/`info` → report only, no issue.
- **Auto-issue cap:** 5 issues per cluster → remainder bundled into one umbrella issue per cluster (`[audit:spec-1:<cluster>] N additional findings from harness self-audit`).
- **Labels on every auto-issue:** `audit`, `harness-self-audit`, `principles-audit`, plus `P0` or `P1`, plus `audit-2026-08-09`.
- **Repo for issue filing:** `Heretek-AI/heretek-claude-harness` (confirmed by user during brainstorming).
- **GitHub access method:** **GitHub MCP** (`mcp__github__github-issue_write` etc.) only — never `gh` CLI (per Issue #30 plan in memory).
- **Audit snapshot:** every finding carries the commit SHA captured at audit start; referenced in code_refs and reports.
- **Python:** 3.10+. Existing deps only — `PyYAML==6.0.3`, `jsonschema==4.26.0`, `requests==2.34.2`, `pytest==9.1.1` (dev). No new runtime deps.
- **Conventions:** scripts under `scripts/` use `sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))` for tests; `scripts/__init__.py` already exists and marks the package.
- **Test runner:** `pytest` via `python3 -m pytest`. Default `-m "not integration"` (in `pyproject.toml`); audit tests do not need the `integration` marker.

---

## File Structure

Files this plan creates or modifies. Each has one clear responsibility.

| Path | Responsibility |
|------|----------------|
| `tests/schemas/audit_finding.schema.json` | JSON Schema for one per-cluster finding card |
| `tests/fixtures/audit/valid_finding.yaml` | One valid cluster-A finding (passes schema) |
| `tests/fixtures/audit/invalid_finding_missing_severity.yaml` | One invalid finding (missing required field) |
| `tests/fixtures/audit/invalid_finding_bad_enum.yaml` | One invalid finding (severity not in enum) |
| `tests/fixtures/audit/cluster_results/` | Five YAML files representing cluster A-E outputs for end-to-end test |
| `tests/test_audit_validate.py` | Tests for `scripts/audit/validate.py` |
| `tests/test_audit_findings.py` | Tests for `scripts/audit/findings.py` (dataclass + load/save) |
| `tests/test_audit_synthesis.py` | Tests for `scripts/audit/synthesis.py` (dedupe, severity filter, cross-ref hooks) |
| `tests/test_audit_issues.py` | Tests for `scripts/audit/issues.py` (cap, umbrella, payload shape) |
| `tests/test_audit_harness_self.py` | End-to-end test for the CLI driver with fixture cluster results |
| `scripts/audit/__init__.py` | Marks `scripts/audit/` as a package |
| `scripts/audit/validate.py` | Schema validation for finding cards (Python API + CLI) |
| `scripts/audit/findings.py` | `Finding` dataclass + JSON/YAML load + save + helpers |
| `scripts/audit/prompts.py` | Five cluster-lane prompt templates (A-E), one constant per cluster |
| `scripts/audit/synthesis.py` | Re-verification gate, dedupe, drift-signal cross-ref, report + JSON output |
| `scripts/audit/issues.py` | Build GitHub MCP payloads (HIGH/CRITICAL only, 5/cluster cap, umbrella bundling) |
| `scripts/audit/harness_self.py` | CLI driver: `--emit-prompts`, `--cluster-results DIR`, `--synthesize`, `--create-issues` |

**Files that change together live together.** All audit code under `scripts/audit/`. All tests next to the schemas/fixtures they exercise.

---

## Task 1: Finding JSON Schema + fixtures (TDD)

**Files:**
- Create: `tests/schemas/audit_finding.schema.json`
- Create: `tests/fixtures/audit/valid_finding.yaml`
- Create: `tests/fixtures/audit/invalid_finding_missing_severity.yaml`
- Create: `tests/fixtures/audit/invalid_finding_bad_enum.yaml`
- Create: `tests/test_audit_schema.py`
- Create: `tests/__init__.py` (verify exists; create if not)

**Interfaces:**
- Consumes: nothing (first deliverable in the audit toolkit).
- Produces: `tests/schemas/audit_finding.schema.json` — JSON Schema (draft 2020-12) for one audit finding card per the spec.

**Step 1: Verify `tests/__init__.py` exists**

Run: `ls tests/__init__.py`

Expected: file exists (it's there from SP1). If absent, write `tests/__init__.py` as an empty file.

**Step 2: Write `tests/fixtures/audit/valid_finding.yaml`**

Write `tests/fixtures/audit/valid_finding.yaml`:

```yaml
finding_id: A-001
cluster: Readability & quality bar
principle: Small, focused functions
severity: high
adversarial_posture: violated
evidence:
  code_refs:
    - scripts/validate.py:124-187
  file: scripts/validate.py
  line_range: [124, 187]
  metric: cognitive_complexity=42 (threshold=15, repo p95=12)
failure_scenario: >-
  When a plugin manifest has 5 nested conditional branches, this
  function returns the wrong D7 status because the early-exit path
  is missed.
recommended_action: refactor
rationale: >-
  Function violates the small-focused-functions principle and shows up
  in the SonarCloud p99 complexity report.
principle_reference: Code quality > Maintainability > small, focused functions
drift_signals:
  - pr-149 already flagged S3516 here - duplicate?
```

**Step 3: Write `tests/fixtures/audit/invalid_finding_missing_severity.yaml`**

Write `tests/fixtures/audit/invalid_finding_missing_severity.yaml`:

```yaml
finding_id: A-002
cluster: Readability & quality bar
principle: Small, focused functions
# severity intentionally missing
adversarial_posture: violated
evidence:
  code_refs:
    - scripts/foo.py:1-10
  file: scripts/foo.py
  line_range: [1, 10]
  metric: ""
failure_scenario: "x"
recommended_action: refactor
rationale: "x"
principle_reference: "x"
drift_signals: []
```

**Step 4: Write `tests/fixtures/audit/invalid_finding_bad_enum.yaml`**

Write `tests/fixtures/audit/invalid_finding_bad_enum.yaml`:

```yaml
finding_id: A-003
cluster: Readability & quality bar
principle: Small, focused functions
severity: catastrophic        # not in enum
adversarial_posture: violated
evidence:
  code_refs:
    - scripts/foo.py:1-10
  file: scripts/foo.py
  line_range: [1, 10]
  metric: ""
failure_scenario: "x"
recommended_action: refactor
rationale: "x"
principle_reference: "x"
drift_signals: []
```

**Step 5: Write failing tests `tests/test_audit_schema.py`**

Write `tests/test_audit_schema.py`:

```python
"""Tests for the audit_finding.schema.json JSON Schema."""
import json
from pathlib import Path

import jsonschema
import pytest


def test_schema_exists(schemas_dir: Path) -> None:
    schema_path = schemas_dir / "audit_finding.schema.json"
    assert schema_path.is_file(), f"missing schema at {schema_path}"


def test_valid_finding_passes(schemas_dir: Path, fixtures_dir: Path) -> None:
    schema = json.loads((schemas_dir / "audit_finding.schema.json").read_text())
    example = (fixtures_dir / "audit" / "valid_finding.yaml").read_text()
    # YAML, not JSON — we use ruamel to parse.
    from ruamel.yaml import YAML
    parsed = YAML(typ="safe").load(example)
    jsonschema.validate(instance=parsed, schema=schema)  # must not raise


def test_missing_required_field_fails(schemas_dir: Path, fixtures_dir: Path) -> None:
    schema = json.loads((schemas_dir / "audit_finding.schema.json").read_text())
    bad = (fixtures_dir / "audit" / "invalid_finding_missing_severity.yaml").read_text()
    from ruamel.yaml import YAML
    parsed = YAML(typ="safe").load(bad)
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(instance=parsed, schema=schema)


def test_bad_enum_value_fails(schemas_dir: Path, fixtures_dir: Path) -> None:
    schema = json.loads((schemas_dir / "audit_finding.schema.json").read_text())
    bad = (fixtures_dir / "audit" / "invalid_finding_bad_enum.yaml").read_text()
    from ruamel.yaml import YAML
    parsed = YAML(typ="safe").load(bad)
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(instance=parsed, schema=schema)
```

**Step 6: Run tests, expect FAIL**

Run: `python3 -m pytest tests/test_audit_schema.py -v`

Expected: FAIL — `audit_finding.schema.json` does not exist.

**Step 7: Write the schema**

Write `tests/schemas/audit_finding.schema.json`:

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "https://heretek.ai/schemas/audit_finding.schema.json",
  "title": "Heretek harness self-audit finding card",
  "description": "One finding from one cluster lane (per spec 2026-08-09 §Per-finding schema).",
  "type": "object",
  "additionalProperties": false,
  "required": [
    "finding_id",
    "cluster",
    "principle",
    "severity",
    "adversarial_posture",
    "evidence",
    "failure_scenario",
    "recommended_action",
    "rationale",
    "principle_reference",
    "drift_signals"
  ],
  "properties": {
    "finding_id": {
      "type": "string",
      "pattern": "^[A-E]-[0-9]{3,}$",
      "description": "<cluster_letter>-<NNN>, deterministic per spec."
    },
    "cluster": {
      "type": "string",
      "enum": [
        "Readability & quality bar",
        "Design & architecture",
        "Correctness & safety",
        "Testing & verification",
        "Operations & docs"
      ]
    },
    "principle": { "type": "string", "minLength": 1 },
    "severity": {
      "type": "string",
      "enum": ["critical", "high", "medium", "low", "info"]
    },
    "adversarial_posture": {
      "type": "string",
      "enum": ["violated", "partial", "justified"]
    },
    "evidence": {
      "type": "object",
      "additionalProperties": false,
      "required": ["code_refs", "file", "line_range", "metric"],
      "properties": {
        "code_refs": {
          "type": "array",
          "minItems": 1,
          "items": { "type": "string", "pattern": "^[^\\s].+:[0-9]+(-[0-9]+)?$" },
          "description": "<file>:<start_line>[-<end_line>] per spec."
        },
        "file": { "type": "string", "minLength": 1 },
        "line_range": {
          "type": "array",
          "minItems": 2,
          "maxItems": 2,
          "items": { "type": "integer", "minimum": 1 },
          "description": "[start_line, end_line] inclusive."
        },
        "metric": { "type": "string" }
      }
    },
    "failure_scenario": { "type": "string", "minLength": 1 },
    "recommended_action": {
      "type": "string",
      "enum": ["refactor", "document", "suppress", "accept", "escalate"]
    },
    "rationale": { "type": "string", "minLength": 1 },
    "principle_reference": { "type": "string", "minLength": 1 },
    "drift_signals": {
      "type": "array",
      "items": { "type": "string" }
    }
  }
}
```

**Step 8: Run tests, expect PASS**

Run: `python3 -m pytest tests/test_audit_schema.py -v`

Expected: 4 tests pass.

**Step 9: Commit**

```bash
git add tests/__init__.py \
        tests/schemas/audit_finding.schema.json \
        tests/fixtures/audit/valid_finding.yaml \
        tests/fixtures/audit/invalid_finding_missing_severity.yaml \
        tests/fixtures/audit/invalid_finding_bad_enum.yaml \
        tests/test_audit_schema.py
git commit -m "test(audit): add finding JSON Schema + fixtures (Spec 1)

Per docs/superpowers/specs/2026-08-09-heretek-harness-self-audit-design.md
§Per-finding schema. 11 required keys + 4 evidence subkeys; severity
and adversarial_posture enums locked from the spec. Schema lives in
tests/schemas/ so other audit modules (synthesis, issues) can import it.

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

## Task 2: `scripts/audit/validate.py` — schema validation API + CLI (TDD)

**Files:**
- Create: `scripts/audit/__init__.py` (verify exists; create if not)
- Create: `scripts/audit/validate.py`
- Create: `tests/test_audit_validate.py`

**Interfaces:**
- Consumes: `tests/schemas/audit_finding.schema.json`.
- Produces:
  - Python API: `validate_finding(finding: dict) -> list[str]` — returns list of error messages; empty = valid. `validate_findings(findings: list[dict]) -> list[tuple[int, list[str]]]` — same, indexed by row.
  - CLI: `python scripts/audit/validate.py <file.yaml|json>...` — exit 0 if all findings valid, 1 otherwise. Prints errors to stderr.

**Step 1: Verify `scripts/audit/__init__.py` exists**

Run: `ls scripts/audit/__init__.py 2>&1 || echo "missing"`

If `missing`, write `scripts/audit/__init__.py` as an empty file. Otherwise continue.

**Step 2: Write failing tests `tests/test_audit_validate.py`**

Write `tests/test_audit_validate.py`:

```python
"""Tests for scripts/audit/validate.py."""
import json
import sys
from pathlib import Path

import jsonschema
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

from audit import validate  # noqa: E402


def _load_yaml(p: Path) -> dict:
    from ruamel.yaml import YAML
    return YAML(typ="safe").load(p.read_text())


def test_validate_finding_accepts_valid_card(
    schemas_dir: Path, fixtures_dir: Path
) -> None:
    validate.SCHEMA_PATH = schemas_dir / "audit_finding.schema.json"
    valid = _load_yaml(fixtures_dir / "audit" / "valid_finding.yaml")
    errors = validate.validate_finding(valid)
    assert errors == [], f"expected no errors, got: {errors}"


def test_validate_finding_rejects_missing_severity(
    schemas_dir: Path, fixtures_dir: Path
) -> None:
    validate.SCHEMA_PATH = schemas_dir / "audit_finding.schema.json"
    bad = _load_yaml(fixtures_dir / "audit" / "invalid_finding_missing_severity.yaml")
    errors = validate.validate_finding(bad)
    assert len(errors) >= 1
    assert any("severity" in e for e in errors)


def test_validate_finding_rejects_bad_enum(
    schemas_dir: Path, fixtures_dir: Path
) -> None:
    validate.SCHEMA_PATH = schemas_dir / "audit_finding.schema.json"
    bad = _load_yaml(fixtures_dir / "audit" / "invalid_finding_bad_enum.yaml")
    errors = validate.validate_finding(bad)
    assert len(errors) >= 1


def test_validate_findings_indexes_errors(
    schemas_dir: Path, fixtures_dir: Path
) -> None:
    validate.SCHEMA_PATH = schemas_dir / "audit_finding.schema.json"
    findings = [
        _load_yaml(fixtures_dir / "audit" / "valid_finding.yaml"),
        _load_yaml(fixtures_dir / "audit" / "invalid_finding_bad_enum.yaml"),
    ]
    indexed = validate.validate_findings(findings)
    assert indexed == [] or all(isinstance(t, tuple) for t in indexed)
    # The bad one at index 1 should produce errors.
    bad_index, bad_errors = next(iter([t for t in indexed if t[1]]))
    assert bad_index == 1
    assert len(bad_errors) >= 1


def test_cli_exits_zero_on_valid(
    schemas_dir: Path,
    fixtures_dir: Path,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    validate.SCHEMA_PATH = schemas_dir / "audit_finding.schema.json"
    # Write a single-finding YAML file the CLI can read.
    single = tmp_path / "single.yaml"
    single.write_text(
        (fixtures_dir / "audit" / "valid_finding.yaml").read_text()
    )
    monkeypatch.setattr(
        sys,
        "argv",
        ["validate.py", "--schema", str(schemas_dir / "audit_finding.schema.json"), str(single)],
    )
    assert validate.main() == 0


def test_cli_exits_one_on_invalid(
    schemas_dir: Path,
    fixtures_dir: Path,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    validate.SCHEMA_PATH = schemas_dir / "audit_finding.schema.json"
    single = tmp_path / "bad.yaml"
    single.write_text(
        (fixtures_dir / "audit" / "invalid_finding_bad_enum.yaml").read_text()
    )
    monkeypatch.setattr(
        sys,
        "argv",
        ["validate.py", "--schema", str(schemas_dir / "audit_finding.schema.json"), str(single)],
    )
    assert validate.main() == 1
```

**Step 3: Run tests, expect FAIL**

Run: `python3 -m pytest tests/test_audit_validate.py -v`

Expected: FAIL — `scripts/audit/validate.py` does not exist (ModuleNotFoundError on `audit`).

**Step 4: Implement `scripts/audit/validate.py`**

Write `scripts/audit/validate.py`:

```python
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
        return YAML(typ="safe").load(text)
    return json.loads(text)


def validate_finding(finding: dict) -> list[str]:
    """Return a list of error messages for one finding; empty = valid."""
    schema = json.loads(SCHEMA_PATH.read_text())
    validator = jsonschema.Draft202012Validator(schema)
    return [f"{e.json_path}: {e.message}" for e in validator.iter_errors(finding)]


def validate_findings(findings: list[dict]) -> list[tuple[int, list[str]]]:
    """Validate a list; return [(index, errors)] for every invalid entry."""
    return [(i, errs) for i, f in enumerate(findings) for errs in [validate_finding(f)] if errs]


def main(argv: Iterable[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--schema", type=Path, default=SCHEMA_PATH)
    parser.add_argument("files", nargs="+", type=Path)
    args = parser.parse_args(argv)

    # Use the explicit --schema if provided (otherwise the module default).
    global SCHEMA_PATH  # noqa: PLW0603
    SCHEMA_PATH = args.schema

    any_errors = False
    for path in args.files:
        try:
            instance = _load_instance(path)
        except (json.JSONDecodeError, ValueError) as exc:
            print(f"{path}: parse error: {exc}", file=sys.stderr)
            any_errors = True
            continue
        # A file may contain a single finding OR a list of findings.
        findings = instance if isinstance(instance, list) else [instance]
        for idx, errors in validate_findings(findings):
            any_errors = True
            print(f"{path}#{idx}:", file=sys.stderr)
            for e in errors:
                print(f"  - {e}", file=sys.stderr)
        if not any_errors:
            print(f"{path}: OK ({len(findings)} finding(s))")
    return 1 if any_errors else 0


if __name__ == "__main__":
    sys.exit(main())
```

**Step 5: Run tests, expect PASS**

Run: `python3 -m pytest tests/test_audit_validate.py -v`

Expected: 6 tests pass.

**Step 6: Commit**

```bash
git add scripts/audit/__init__.py scripts/audit/validate.py tests/test_audit_validate.py
git commit -m "feat(audit): add finding-card validator (Spec 1)

scripts/audit/validate.py loads the schema from tests/schemas/
audit_finding.schema.json and validates one or many finding cards.
CLI: 'validate.py [--schema PATH] <file>...' exits 0 on all-valid,
1 on any failure with per-card errors on stderr. Library API:
validate_finding(dict) and validate_findings(list[dict]) for reuse
by synthesis.py and issues.py.

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

## Task 3: `scripts/audit/findings.py` — Finding dataclass + load/save (TDD)

**Files:**
- Create: `scripts/audit/findings.py`
- Create: `tests/test_audit_findings.py`

**Interfaces:**
- Consumes: cluster-result YAML/JSON files (lists of finding dicts).
- Produces:
  - `Finding` dataclass with all 11 fields + 4 evidence subfields.
  - `load_findings(path: Path) -> list[Finding]` — reads YAML or JSON, validates each card via `audit.validate.validate_finding`, raises `ValueError` listing the invalid indexes.
  - `save_findings(findings: list[Finding], path: Path) -> None` — writes JSON (always JSON for output; YAML only on input).
  - `severity_rank(finding: Finding) -> int` — `critical=0, high=1, medium=2, low=3, info=4` (used by synthesis for ranking).

**Step 1: Write failing tests `tests/test_audit_findings.py`**

Write `tests/test_audit_findings.py`:

```python
"""Tests for scripts/audit/findings.py."""
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

from audit import findings, validate  # noqa: E402


@pytest.fixture(autouse=True)
def _set_schema(schemas_dir: Path) -> None:
    validate.SCHEMA_PATH = schemas_dir / "audit_finding.schema.json"


def _sample_dict() -> dict:
    return {
        "finding_id": "A-001",
        "cluster": "Readability & quality bar",
        "principle": "Small, focused functions",
        "severity": "high",
        "adversarial_posture": "violated",
        "evidence": {
            "code_refs": ["scripts/x.py:1-10"],
            "file": "scripts/x.py",
            "line_range": [1, 10],
            "metric": "x",
        },
        "failure_scenario": "x",
        "recommended_action": "refactor",
        "rationale": "x",
        "principle_reference": "x",
        "drift_signals": [],
    }


def test_finding_from_dict_round_trips() -> None:
    d = _sample_dict()
    f = findings.Finding.from_dict(d)
    assert f.finding_id == "A-001"
    assert f.severity == "high"
    assert f.evidence.line_range == [1, 10]
    assert f.to_dict() == d


def test_load_findings_accepts_yaml(fixtures_dir: Path) -> None:
    p = fixtures_dir / "audit" / "valid_finding.yaml"
    loaded = findings.load_findings(p)
    assert len(loaded) == 1
    assert loaded[0].finding_id == "A-001"


def test_load_findings_rejects_invalid(fixtures_dir: Path) -> None:
    p = fixtures_dir / "audit" / "invalid_finding_bad_enum.yaml"
    with pytest.raises(ValueError, match="invalid"):
        findings.load_findings(p)


def test_save_findings_writes_json(tmp_path: Path) -> None:
    f = findings.Finding.from_dict(_sample_dict())
    out = tmp_path / "out.json"
    findings.save_findings([f], out)
    assert out.is_file()
    data = json.loads(out.read_text())
    assert data[0]["finding_id"] == "A-001"


def test_severity_rank_orders_critical_first() -> None:
    f_crit = findings.Finding.from_dict({**_sample_dict(), "severity": "critical"})
    f_high = findings.Finding.from_dict({**_sample_dict(), "severity": "high"})
    f_info = findings.Finding.from_dict({**_sample_dict(), "severity": "info"})
    assert findings.severity_rank(f_crit) < findings.severity_rank(f_high) < findings.severity_rank(f_info)
```

**Step 2: Run tests, expect FAIL**

Run: `python3 -m pytest tests/test_audit_findings.py -v`

Expected: FAIL — `scripts/audit/findings.py` does not exist.

**Step 3: Implement `scripts/audit/findings.py`**

Write `scripts/audit/findings.py`:

```python
"""Finding dataclass + load/save helpers for the harness self-audit.

One Finding = one card per the spec's per-finding schema. Cluster
agents emit YAML or JSON lists; this module loads them, validates each
card via `audit.validate`, and exposes a dataclass for synthesis / issues
to consume without re-parsing the schema each time.

JSON is the canonical output format (so downstream tools and the GitHub
issue builder don't have to handle two parsers).
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from ruamel.yaml import YAML

from audit import validate

SEVERITY_ORDER = ["critical", "high", "medium", "low", "info"]


@dataclass(frozen=True)
class Evidence:
    code_refs: list[str]
    file: str
    line_range: list[int]
    metric: str

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "Evidence":
        return cls(
            code_refs=list(d["code_refs"]),
            file=d["file"],
            line_range=list(d["line_range"]),
            metric=d["metric"],
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "code_refs": list(self.code_refs),
            "file": self.file,
            "line_range": list(self.line_range),
            "metric": self.metric,
        }


@dataclass(frozen=True)
class Finding:
    finding_id: str
    cluster: str
    principle: str
    severity: str
    adversarial_posture: str
    evidence: Evidence
    failure_scenario: str
    recommended_action: str
    rationale: str
    principle_reference: str
    drift_signals: list[str] = field(default_factory=list)

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "Finding":
        return cls(
            finding_id=d["finding_id"],
            cluster=d["cluster"],
            principle=d["principle"],
            severity=d["severity"],
            adversarial_posture=d["adversarial_posture"],
            evidence=Evidence.from_dict(d["evidence"]),
            failure_scenario=d["failure_scenario"],
            recommended_action=d["recommended_action"],
            rationale=d["rationale"],
            principle_reference=d["principle_reference"],
            drift_signals=list(d.get("drift_signals", [])),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "finding_id": self.finding_id,
            "cluster": self.cluster,
            "principle": self.principle,
            "severity": self.severity,
            "adversarial_posture": self.adversarial_posture,
            "evidence": self.evidence.to_dict(),
            "failure_scenario": self.failure_scenario,
            "recommended_action": self.recommended_action,
            "rationale": self.rationale,
            "principle_reference": self.principle_reference,
            "drift_signals": list(self.drift_signals),
        }


def _load_instance(path: Path) -> Any:
    text = path.read_text()
    if path.suffix.lower() in {".yaml", ".yml"}:
        return YAML(typ="safe").load(text)
    return json.loads(text)


def load_findings(path: Path) -> list[Finding]:
    """Read a YAML or JSON file containing one finding or a list; validate each card."""
    instance = _load_instance(path)
    findings_in = instance if isinstance(instance, list) else [instance]
    invalid_indexes: list[str] = []
    out: list[Finding] = []
    for i, d in enumerate(findings_in):
        errors = validate.validate_finding(d)
        if errors:
            invalid_indexes.append(f"#{i}: " + "; ".join(errors))
            continue
        out.append(Finding.from_dict(d))
    if invalid_indexes:
        raise ValueError(
            f"{path}: {len(invalid_indexes)} invalid finding(s): " + " | ".join(invalid_indexes)
        )
    return out


def save_findings(items: list[Finding], path: Path) -> None:
    """Write findings as a JSON array (canonical output format)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps([f.to_dict() for f in items], indent=2, sort_keys=True) + "\n")


def severity_rank(finding: Finding) -> int:
    """Lower rank = more severe. critical=0, high=1, medium=2, low=3, info=4."""
    return SEVERITY_ORDER.index(finding.severity)
```

**Step 4: Run tests, expect PASS**

Run: `python3 -m pytest tests/test_audit_findings.py -v`

Expected: 5 tests pass.

**Step 5: Commit**

```bash
git add scripts/audit/findings.py tests/test_audit_findings.py
git commit -m "feat(audit): add Finding dataclass + load/save helpers

Frozen dataclass for one finding card per the spec schema. load_findings()
reads YAML or JSON, validates each card via audit.validate, raises
ValueError on any invalid card (with the index). save_findings() writes
canonical JSON for downstream synthesis/issue tools. severity_rank() gives
a sort key (critical=0..info=4) for ranked reports.

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

## Task 4: `scripts/audit/prompts.py` — 5 cluster lane prompt templates

**Files:**
- Create: `scripts/audit/prompts.py`
- Create: `tests/test_audit_prompts.py`

**Interfaces:**
- Consumes: nothing (constants only).
- Produces:
  - `CLUSTERS: dict[str, ClusterPrompt]` keyed by `A`/`B`/`C`/`D`/`E`.
  - `ClusterPrompt` dataclass: `letter: str`, `title: str`, `principles: list[str]`, `evidence_strategy: str`, `template: str` — the actual prompt to paste into an Explore-agent, with `{repo_root}` and `{commit_sha}` placeholders.
  - `render_prompt(letter: str, repo_root: Path, commit_sha: str) -> str` — substitutes placeholders.
  - CLI: `python scripts/audit/prompts.py <cluster_letter> --repo-root PATH --commit-sha SHA` — prints the rendered prompt to stdout (so the driver or an operator can pipe it into an agent).

**Step 1: Write failing tests `tests/test_audit_prompts.py`**

Write `tests/test_audit_prompts.py`:

```python
"""Tests for scripts/audit/prompts.py."""
import re
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

from audit import prompts  # noqa: E402


def test_all_five_clusters_present() -> None:
    assert set(prompts.CLUSTERS.keys()) == {"A", "B", "C", "D", "E"}


@pytest.mark.parametrize("letter", ["A", "B", "C", "D", "E"])
def test_each_cluster_has_required_fields(letter: str) -> None:
    cp = prompts.CLUSTERS[letter]
    assert cp.letter == letter
    assert cp.title
    assert len(cp.principles) >= 1
    assert cp.evidence_strategy
    assert cp.template
    # Template must mention {repo_root} and {commit_sha}.
    assert "{repo_root}" in cp.template
    assert "{commit_sha}" in cp.template


def test_render_prompt_substitutes_placeholders(tmp_path: Path) -> None:
    rendered = prompts.render_prompt("A", tmp_path, "deadbeef")
    assert str(tmp_path) in rendered
    assert "deadbeef" in rendered


def test_render_prompt_rejects_unknown_letter(tmp_path: Path) -> None:
    with pytest.raises(KeyError):
        prompts.render_prompt("Z", tmp_path, "deadbeef")


def test_cli_prints_prompt(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture
) -> None:
    monkeypatch.setattr(
        sys,
        "argv",
        ["prompts.py", "A", "--repo-root", str(tmp_path), "--commit-sha", "deadbeef"],
    )
    assert prompts.main() == 0
    out = capsys.readouterr().out
    assert "deadbeef" in out
    assert "{repo_root}" not in out  # substituted
```

**Step 2: Run tests, expect FAIL**

Run: `python3 -m pytest tests/test_audit_prompts.py -v`

Expected: FAIL — `scripts/audit/prompts.py` does not exist.

**Step 3: Implement `scripts/audit/prompts.py`**

Write `scripts/audit/prompts.py`:

```python
"""Cluster lane prompt templates for the harness self-audit.

Five constants — one per cluster (A-E) per the spec's methodology table.
Each template is the prompt an Explore-agent receives; it embeds the
per-finding schema so the agent returns valid cards. Placeholders:
{repo_root}  — absolute path to the repo under audit
{commit_sha} — git HEAD commit SHA at audit time (snapshot per spec)

Use `render_prompt(letter, repo_root, commit_sha)` to get a ready-to-paste
prompt, or run the CLI:

    python scripts/audit/prompts.py <A|B|C|D|E> --repo-root PATH --commit-sha SHA
"""
from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable


@dataclass(frozen=True)
class ClusterPrompt:
    letter: str
    title: str
    principles: tuple[str, ...]
    evidence_strategy: str
    template: str


# ---------- Cluster A: Readability & quality bar ----------
_A_TEMPLATE = """\
You are auditing the heretek-claude-harness repository for Cluster A:
**Readability & quality bar**.

Repo: {repo_root}
Snapshot commit: {commit_sha}

**Principles in scope**
- Small, focused functions
- Clear, consistent naming
- Comments explain WHY, not WHAT
- DRY, KISS, YAGNI
- No dead code, no copy-paste duplication

**Evidence-collection strategy**
- File size, function size, cyclomatic + cognitive complexity
- Lint output (ruff, pylint if present)
- Line counts, duplication scan
- For each candidate finding, cite a numeric metric and the tool that produced it.

**Posture: ADVERSARIAL.** Assume each principle is being violated until evidence
proves otherwise. Prefer false positives over missed findings; synthesis will
re-verify.

**Output format** — one YAML document per finding (or one YAML list of findings).
Return ONLY findings; do not write prose.

```yaml
- finding_id: A-NNN                 # sequential, zero-padded
  cluster: "Readability & quality bar"
  principle: "<one-line principle statement>"
  severity: critical|high|medium|low|info
  adversarial_posture: violated|partial|justified
  evidence:
    code_refs: ["<path>:<start_line>-<end_line>"]
    file: "<path>"
    line_range: [<start>, <end>]
    metric: "<numeric metric + tool that produced it>"
  failure_scenario: "<concrete inputs/state -> wrong output/crash>"
  recommended_action: refactor|document|suppress|accept|escalate
  rationale: "<one sentence: the why, not the what>"
  principle_reference: "Code quality > <subsection> > <principle>"
  drift_signals: []  # any "this was already flagged in PR #N" notes
```

If a principle is fully met across the in-scope code, return an empty list. Do
NOT fabricate findings to fill quotas.
"""


# ---------- Cluster B: Design & architecture ----------
_B_TEMPLATE = """\
You are auditing the heretek-claude-harness repository for Cluster B:
**Design & architecture**.

Repo: {repo_root}
Snapshot commit: {commit_sha}

**Principles in scope**
- SOLID (especially SRP, OCP, DIP)
- Composition over inheritance
- Tell, don't ask
- Law of Demeter
- Separation of concerns; loose coupling, high cohesion

**Evidence-collection strategy**
- Import graph (look for cycles, deep inheritance)
- Class/method counts per file (god-file detection: > 500 LOC + many responsibilities)
- Base-class fanout (a base used by > 5 concrete classes may be over-reaching)
- Module boundaries (does `scripts/scanners/` import from `tests/`? vice versa?)

**Posture: ADVERSARIAL.** Assume each principle is being violated until evidence
proves otherwise.

**Output format** — same per-finding YAML card as Cluster A. Use finding_id
prefix `B-NNN`. Cluster field: `"Design & architecture"`.
"""


# ---------- Cluster C: Correctness & safety ----------
_C_TEMPLATE = """\
You are auditing the heretek-claude-harness repository for Cluster C:
**Correctness & safety**.

Repo: {repo_root}
Snapshot commit: {commit_sha}

**Principles in scope**
- Explicit error handling (no silent exception swallowing)
- Input validation at boundaries
- Type hints on public functions
- Idempotent operations where possible
- Immutability over mutation when reasonable
- Defensive programming only where genuine threat exists

**Evidence-collection strategy**
- try/except scan: bare `except:` or `except Exception: pass` patterns
- Type-hint coverage scan on public functions (rough: missing `->` on > 30% of
  public callables in a module is a cluster-C finding)
- Mutability patterns: top-level mutable defaults, module-level dict/list
  mutations
- Parameter validation markers: functions that consume `Path` / `int` /
  untyped `dict` from external sources without validation

**Posture: ADVERSARIAL.** Assume each principle is being violated until evidence
proves otherwise.

**Output format** — same per-finding YAML card. Use finding_id prefix `C-NNN`.
Cluster field: `"Correctness & safety"`.
"""


# ---------- Cluster D: Testing & verification ----------
_D_TEMPLATE = """\
You are auditing the heretek-claude-harness repository for Cluster D:
**Testing & verification**.

Repo: {repo_root}
Snapshot commit: {commit_sha}

**Principles in scope**
- Test pyramid (many unit, fewer integration, few E2E)
- Test isolation (no shared mutable state between tests)
- Coverage of critical paths (not 100% for its own sake)
- TDD evidence in commit history (red-green-refactor visible in `git log -- <file>`)
- No flaky-test markers (sleeps, time-dependent assertions, network mocks)
- No test smells (asserts on private attrs, oversized fixtures)

**Evidence-collection strategy**
- pytest markers: are `integration` tests actually marked? (run
  `grep -rE "@pytest.mark.integration" tests/`)
- conftest.py review: shared fixtures, autouse patterns, module-level state
- Test counts per source module (rough: < 1 test per 50 LOC of source = smell)
- Fixture audit: oversized fixtures used by > 20 tests = god-fixture
- Commit history: spot-check 3 source files for TDD-shaped commit pairs

**Posture: ADVERSARIAL.** Assume each principle is being violated until evidence
proves otherwise.

**Output format** — same per-finding YAML card. Use finding_id prefix `D-NNN`.
Cluster field: `"Testing & verification"`.
"""


# ---------- Cluster E: Operations & docs ----------
_E_TEMPLATE = """\
You are auditing the heretek-claude-harness repository for Cluster E:
**Operations & docs**.

Repo: {repo_root}
Snapshot commit: {commit_sha}

**Principles in scope**
- Observability: structured logs, no bare `print()` in library code
- CI/CD maturity: workflows run on every PR, fail loud
- Feature flags / rollback: changes have a way back
- Security hygiene: pinned deps, no shell-injection sinks, secret-handling
- Doc freshness: README matches reality, ADRs for non-trivial decisions
- Onboarding: a new contributor can be productive in < 1 day

**Evidence-collection strategy**
- log/print scan: `grep -rnE "^\\s*print\\(" scripts/` (library code should
  use the `logging` module)
- Requirements freshness: `requirements.txt` pins, `requirements.lock.txt`
  presence, last-updated date
- GH workflow audit (READABILITY only — does the YAML parse? does each step
  have a name? timeout set? — NOT enforcement behavior, that's Spec 3)
- Docstring coverage on public functions
- README freshness (does install command work? do plugin counts match?)
- Look for missing ADRs on non-trivial decisions

**Posture: ADVERSARIAL.** Assume each principle is being violated until evidence
proves otherwise.

**Output format** — same per-finding YAML card. Use finding_id prefix `E-NNN`.
Cluster field: `"Operations & docs"`.
"""


CLUSTERS: dict[str, ClusterPrompt] = {
    "A": ClusterPrompt(
        letter="A",
        title="Readability & quality bar",
        principles=(
            "Small, focused functions",
            "Clear, consistent naming",
            "Comments explain WHY, not WHAT",
            "DRY, KISS, YAGNI",
            "No dead code, no copy-paste duplication",
        ),
        evidence_strategy="file/function size, complexity metrics, lint, duplication scan",
        template=_A_TEMPLATE,
    ),
    "B": ClusterPrompt(
        letter="B",
        title="Design & architecture",
        principles=(
            "SOLID (SRP, OCP, DIP)",
            "Composition over inheritance",
            "Tell, don't ask",
            "Law of Demeter",
            "Separation of concerns; loose coupling, high cohesion",
        ),
        evidence_strategy="import graph, god-file detection, base-class fanout, module boundaries",
        template=_B_TEMPLATE,
    ),
    "C": ClusterPrompt(
        letter="C",
        title="Correctness & safety",
        principles=(
            "Explicit error handling",
            "Input validation at boundaries",
            "Type hints on public functions",
            "Idempotent operations",
            "Immutability over mutation",
            "Defensive programming where threat exists",
        ),
        evidence_strategy="try/except scan, type-hint coverage, mutability patterns, validation markers",
        template=_C_TEMPLATE,
    ),
    "D": ClusterPrompt(
        letter="D",
        title="Testing & verification",
        principles=(
            "Test pyramid",
            "Test isolation",
            "Coverage of critical paths",
            "TDD evidence in commit history",
            "No flaky-test markers",
            "No test smells",
        ),
        evidence_strategy="pytest markers, conftest review, test counts per module, fixture audit, commit history",
        template=_D_TEMPLATE,
    ),
    "E": ClusterPrompt(
        letter="E",
        title="Operations & docs",
        principles=(
            "Observability",
            "CI/CD maturity",
            "Feature flags / rollback",
            "Security hygiene",
            "Doc freshness",
            "Onboarding",
        ),
        evidence_strategy="log/print scan, requirements freshness, GH workflow audit, docstring coverage, README freshness, ADR presence",
        template=_E_TEMPLATE,
    ),
}


def render_prompt(letter: str, repo_root: Path, commit_sha: str) -> str:
    """Substitute placeholders and return the ready-to-paste prompt."""
    cp = CLUSTERS[letter]  # raises KeyError for unknown letters
    return (
        cp.template
        .replace("{repo_root}", str(repo_root))
        .replace("{commit_sha}", commit_sha)
    )


def main(argv: Iterable[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "cluster",
        choices=sorted(CLUSTERS.keys()),
        help="Cluster letter (A, B, C, D, or E).",
    )
    parser.add_argument("--repo-root", type=Path, required=True)
    parser.add_argument("--commit-sha", required=True, help="Audit snapshot commit SHA.")
    args = parser.parse_args(argv)
    print(render_prompt(args.cluster, args.repo_root, args.commit_sha))
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

**Step 4: Run tests, expect PASS**

Run: `python3 -m pytest tests/test_audit_prompts.py -v`

Expected: 9 tests pass (5 parametrized + 4 standalone).

**Step 5: Commit**

```bash
git add scripts/audit/prompts.py tests/test_audit_prompts.py
git commit -m "feat(audit): add 5 cluster prompt templates + render helper

Each cluster (A-E) embeds the per-finding schema so Explore-agents
return valid YAML cards. render_prompt() substitutes {repo_root} and
{commit_sha} placeholders. CLI: 'prompts.py <A|B|C|D|E> --repo-root
PATH --commit-sha SHA' prints the rendered prompt for the operator
or the driver to pipe into an agent.

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

## Task 5: `scripts/audit/synthesis.py` — synthesis pass + report + JSON output (TDD)

**Files:**
- Create: `scripts/audit/synthesis.py`
- Create: `tests/test_audit_synthesis.py`
- Create: `tests/fixtures/audit/cluster_results/A.yaml`
- Create: `tests/fixtures/audit/cluster_results/B.yaml`
- Create: `tests/fixtures/audit/cluster_results/C.yaml`

**Interfaces:**
- Consumes: cluster-results directory (5 YAML/JSON files, one per cluster A-E).
- Produces:
  - `synthesize(cluster_results_dir: Path, output_dir: Path, commit_sha: str, sonar_exclusions: set[str] | None = None) -> SynthesisResult` — runs schema validation, dedupe by `(file, line_range)`, severity re-verification (mark `reverified=True` on critical/high if the source file contains the cited metric — the actual metric re-check is executed by the operator; this module flags which findings need operator re-verification), writes report markdown + JSON findings.
  - `SynthesisResult` dataclass: `findings: list[Finding]`, `report_path: Path`, `json_path: Path`, `coverage_gaps: list[str]`, `duplicate_count: int`.

**Step 1: Write failing tests `tests/test_audit_synthesis.py`**

Write `tests/test_audit_synthesis.py`:

```python
"""Tests for scripts/audit/synthesis.py."""
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

from audit import findings, synthesis, validate  # noqa: E402


@pytest.fixture(autouse=True)
def _set_schema(schemas_dir: Path) -> None:
    validate.SCHEMA_PATH = schemas_dir / "audit_finding.schema.json"


def _finding(severity: str = "high", fid: str = "A-001", file: str = "scripts/x.py", lines=(1, 10)) -> dict:
    return {
        "finding_id": fid,
        "cluster": "Readability & quality bar",
        "principle": "Small, focused functions",
        "severity": severity,
        "adversarial_posture": "violated",
        "evidence": {
            "code_refs": [f"{file}:{lines[0]}-{lines[1]}"],
            "file": file,
            "line_range": list(lines),
            "metric": "x",
        },
        "failure_scenario": "x",
        "recommended_action": "refactor",
        "rationale": "x",
        "principle_reference": "x",
        "drift_signals": [],
    }


def test_synthesize_dedupes_across_clusters(
    tmp_path: Path, schemas_dir: Path
) -> None:
    """Two findings with identical (file, line_range) collapse to one."""
    cluster_dir = tmp_path / "in"
    cluster_dir.mkdir()
    (cluster_dir / "A.yaml").write_text(
        "[" + json.dumps(_finding(fid="A-001", severity="high")) + "]"
    )
    (cluster_dir / "B.yaml").write_text(
        "["
        + json.dumps({**_finding(fid="B-001", severity="medium"), "cluster": "Design & architecture"})
        + "]"
    )

    result = synthesis.synthesize(
        cluster_results_dir=cluster_dir,
        output_dir=tmp_path / "out",
        commit_sha="deadbeef",
    )
    assert result.duplicate_count == 1
    assert len(result.findings) == 1
    # Higher-severity finding wins.
    assert result.findings[0].severity == "high"


def test_synthesize_writes_report_and_json(
    tmp_path: Path, schemas_dir: Path
) -> None:
    cluster_dir = tmp_path / "in"
    cluster_dir.mkdir()
    (cluster_dir / "A.yaml").write_text("[" + json.dumps(_finding()) + "]")
    out_dir = tmp_path / "out"
    result = synthesis.synthesize(cluster_dir, out_dir, commit_sha="deadbeef")
    assert result.report_path.is_file()
    assert result.json_path.is_file()
    data = json.loads(result.json_path.read_text())
    assert len(data) == 1
    md = result.report_path.read_text()
    assert "harness-self-audit" in md or "Harness Self-Audit" in md
    assert "deadbeef" in md


def test_synthesize_skips_sonar_excluded(
    tmp_path: Path, schemas_dir: Path
) -> None:
    cluster_dir = tmp_path / "in"
    cluster_dir.mkdir()
    (cluster_dir / "A.yaml").write_text("[" + json.dumps(_finding(file="scripts/excl.py")) + "]")
    result = synthesis.synthesize(
        cluster_dir, tmp_path / "out", commit_sha="deadbeef",
        sonar_exclusions={"scripts/excl.py"},
    )
    assert result.findings == []


def test_synthesize_records_coverage_gap_for_missing_cluster(
    tmp_path: Path, schemas_dir: Path
) -> None:
    cluster_dir = tmp_path / "in"
    cluster_dir.mkdir()
    # Only cluster A present; B, C, D, E missing.
    (cluster_dir / "A.yaml").write_text("[" + json.dumps(_finding()) + "]")
    result = synthesis.synthesize(cluster_dir, tmp_path / "out", commit_sha="deadbeef")
    gap_clusters = " ".join(result.coverage_gaps)
    for letter in ("B", "C", "D", "E"):
        assert letter in gap_clusters
```

**Step 2: Run tests, expect FAIL**

Run: `python3 -m pytest tests/test_audit_synthesis.py -v`

Expected: FAIL — `scripts/audit/synthesis.py` does not exist.

**Step 3: Implement `scripts/audit/synthesis.py`**

Write `scripts/audit/synthesis.py`:

```python
"""Synthesis pass — dedupe, severity-rank, drift-signal cross-ref, report.

Per spec §Synthesis pass (10 steps):
  1. Schema-validate every cluster output (already enforced by load_findings).
  2. Re-verify every critical (the operator does the actual file inspection;
     this module flags which need re-verification).
  3. Re-verify every high (same).
  4. Dedupe by (file, line_range).
  5. Cross-reference drift_signals against git log (operator does this; the
     module surfaces drift_signals in the report).
  6. Cross-reference SonarCloud baseline (sonar_exclusions filter).
  7. Re-run complexity checks (operator runs lizard/radon; module flags
     cluster A files for re-check).
  8. Coverage gaps: principles with no findings, missing clusters.
  9. Ranked summary table.
  10. Output: catalog/reviews/audit-harness-self-<date>.md + .json

This module does the data-shaping; the operator runs the manual
re-verification (file inspection, lizard/radon, git log) before
issue creation. The synthesis output flags which findings still need
operator action via `needs_reverify=True` on the result.
"""
from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Iterable

from audit import findings as findings_mod

ALL_CLUSTER_LETTERS = ("A", "B", "C", "D", "E")


@dataclass
class SynthesisResult:
    findings: list[findings_mod.Finding]
    report_path: Path
    json_path: Path
    coverage_gaps: list[str]
    duplicate_count: int


def _load_cluster_results(
    cluster_results_dir: Path, sonar_exclusions: set[str]
) -> tuple[list[findings_mod.Finding], list[str], int]:
    """Load all cluster result files; apply sonar exclusion filter; record missing clusters."""
    all_findings: list[findings_mod.Finding] = []
    missing: list[str] = []
    for letter in ALL_CLUSTER_LETTERS:
        # Accept either <letter>.yaml or <letter>.yml.
        candidates = list(cluster_results_dir.glob(f"{letter}.y*ml")) + list(
            cluster_results_dir.glob(f"{letter}.json")
        )
        if not candidates:
            missing.append(letter)
            continue
        for path in candidates:
            cluster_findings = findings_mod.load_findings(path)
            for f in cluster_findings:
                # Spec step 6: drop findings on files in the sonar exclusion set.
                if f.evidence.file in sonar_exclusions:
                    continue
                all_findings.append(f)
    return all_findings, missing, 0  # dup count computed separately


def _dedupe(
    items: list[findings_mod.Finding],
) -> tuple[list[findings_mod.Finding], int]:
    """Collapse findings with identical (file, line_range). Keep the higher-severity one."""
    seen: dict[tuple[str, tuple[int, int]], findings_mod.Finding] = {}
    dup_count = 0
    for f in items:
        key = (f.evidence.file, tuple(f.evidence.line_range))
        if key in seen:
            dup_count += 1
            # Keep the more severe one (lower rank = more severe).
            if findings_mod.severity_rank(f) < findings_mod.severity_rank(seen[key]):
                seen[key] = f
            continue
        seen[key] = f
    return list(seen.values()), dup_count


def _ranked_table(items: list[findings_mod.Finding]) -> str:
    rows = sorted(
        items,
        key=lambda f: (findings_mod.severity_rank(f), f.cluster, f.evidence.file),
    )
    lines = [
        "| finding_id | severity | cluster | file | principle | action |",
        "|---|---|---|---|---|---|",
    ]
    for f in rows:
        lines.append(
            f"| {f.finding_id} | {f.severity} | {f.cluster} | `{f.evidence.file}:{f.evidence.line_range[0]}-{f.evidence.line_range[1]}` | {f.principle} | {f.recommended_action} |"
        )
    return "\n".join(lines)


def _coverage_gaps_section(
    items: list[findings_mod.Finding], missing_clusters: list[str]
) -> list[str]:
    """Build the coverage-gap section per spec step 8."""
    gaps: list[str] = []
    if missing_clusters:
        gaps.append(
            "### Missing cluster result files\n\nNo result file found for cluster(s): "
            + ", ".join(missing_clusters)
            + ". Possible audit blind spots — verify the cluster was actually run."
        )
    # Principles with zero findings (per cluster)
    by_cluster: dict[str, list[findings_mod.Finding]] = {}
    for f in items:
        by_cluster.setdefault(f.cluster, []).append(f)
    present_clusters = {c for c in by_cluster}
    all_clusters = {"Readability & quality bar", "Design & architecture",
                    "Correctness & safety", "Testing & verification",
                    "Operations & docs"}
    for cluster in sorted(all_clusters - present_clusters):
        gaps.append(
            f"### Cluster with zero findings: {cluster}\n\n"
            "Either this cluster ran and found nothing, or it didn't run. "
            "If it ran, this is suspicious — re-verify the cluster agent's posture."
        )
    return gaps


def _report_markdown(
    items: list[findings_mod.Finding],
    commit_sha: str,
    coverage_gaps: list[str],
    duplicate_count: int,
) -> str:
    today = date.today().isoformat()
    crit = sum(1 for f in items if f.severity == "critical")
    high = sum(1 for f in items if f.severity == "high")
    med = sum(1 for f in items if f.severity == "medium")
    low = sum(1 for f in items if f.severity == "low")
    info = sum(1 for f in items if f.severity == "info")
    parts = [
        f"# Harness Self-Audit — {today}",
        "",
        f"Snapshot commit: `{commit_sha}`",
        "",
        "## Summary",
        "",
        f"- Critical: {crit}",
        f"- High: {high}",
        f"- Medium: {med}",
        f"- Low: {low}",
        f"- Info: {info}",
        f"- Duplicates collapsed: {duplicate_count}",
        "",
        "## Findings (ranked)",
        "",
        _ranked_table(items),
        "",
        "## Coverage gaps",
        "",
    ]
    if coverage_gaps:
        parts.extend(coverage_gaps)
    else:
        parts.append("_No coverage gaps detected._")
    parts.extend(
        [
            "",
            "## Re-verification checklist (operator action required before issue creation)",
            "",
            "- [ ] Every `critical` finding inspected directly at the cited file:line",
            "- [ ] Every `high` finding inspected unless numeric metric + tool output present",
            "- [ ] Every `drift_signals` entry cross-checked against `git log`",
            "- [ ] Cluster-A files re-run through `lizard`/`radon`",
            "- [ ] Findings not in this report but referenced in `drift_signals` either dropped or merged",
            "",
        ]
    )
    return "\n".join(parts)


def synthesize(
    cluster_results_dir: Path,
    output_dir: Path,
    commit_sha: str,
    sonar_exclusions: set[str] | None = None,
) -> SynthesisResult:
    """Run the synthesis pass. See module docstring for what the operator still must do."""
    sonar_exclusions = sonar_exclusions or set()
    raw, missing_clusters, _ = _load_cluster_results(cluster_results_dir, sonar_exclusions)
    deduped, dup_count = _dedupe(raw)
    # Re-sort by severity for the JSON output too.
    deduped.sort(key=lambda f: (findings_mod.severity_rank(f), f.cluster, f.evidence.file))

    output_dir.mkdir(parents=True, exist_ok=True)
    today = date.today().isoformat()
    json_path = output_dir / f"audit-harness-self-{today}.json"
    report_path = output_dir / f"audit-harness-self-{today}.md"

    findings_mod.save_findings(deduped, json_path)
    coverage_gaps = _coverage_gaps_section(deduped, missing_clusters)
    report_path.write_text(_report_markdown(deduped, commit_sha, coverage_gaps, dup_count))

    return SynthesisResult(
        findings=deduped,
        report_path=report_path,
        json_path=json_path,
        coverage_gaps=coverage_gaps,
        duplicate_count=dup_count,
    )
```

**Step 4: Run tests, expect PASS**

Run: `python3 -m pytest tests/test_audit_synthesis.py -v`

Expected: 4 tests pass.

**Step 5: Commit**

```bash
git add scripts/audit/synthesis.py tests/test_audit_synthesis.py
git commit -m "feat(audit): add synthesis pass + report writer

Loads all 5 cluster result files via audit.findings.load_findings
(schema-validated), filters SonarCloud exclusions, dedupes by
(file, line_range) keeping the higher-severity entry, sorts by
severity, and writes both a markdown report and JSON findings
to output_dir/audit-harness-self-<date>.{md,json}. Coverage gaps
section flags missing clusters and zero-finding clusters.

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

## Task 6: `scripts/audit/issues.py` — auto-issue payloads (HIGH/CRITICAL, cap, umbrella) (TDD)

**Files:**
- Create: `scripts/audit/issues.py`
- Create: `tests/test_audit_issues.py`

**Interfaces:**
- Consumes: `list[Finding]` (typically the synthesis output).
- Produces:
  - `build_issue_payloads(findings: list[Finding], *, cap: int = 5) -> list[IssuePayload]` — for each cluster, take up to `cap` HIGH+CRITICAL findings and emit one `IssuePayload` per finding; emit one umbrella `IssuePayload` per cluster if any findings overflowed.
  - `IssuePayload` dataclass: `title: str`, `body: str`, `labels: list[str]`.
  - The actual GitHub MCP call is performed by the caller (driver script or operator). This module only builds the payloads.
  - Constants: `REPO = "Heretek-AI/heretek-claude-harness"` (spec confirmed), `BASE_LABELS = ["audit", "harness-self-audit", "principles-audit", "audit-2026-08-09"]`.

**Step 1: Write failing tests `tests/test_audit_issues.py`**

Write `tests/test_audit_issues.py`:

```python
"""Tests for scripts/audit/issues.py."""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

from audit import findings, issues  # noqa: E402


def _f(severity: str, fid: str, cluster: str) -> findings.Finding:
    return findings.Finding.from_dict(
        {
            "finding_id": fid,
            "cluster": cluster,
            "principle": "x",
            "severity": severity,
            "adversarial_posture": "violated",
            "evidence": {
                "code_refs": ["x.py:1-2"],
                "file": "x.py",
                "line_range": [1, 2],
                "metric": "x",
            },
            "failure_scenario": "x",
            "recommended_action": "refactor",
            "rationale": "x",
            "principle_reference": "x",
            "drift_signals": [],
        }
    )


def test_skips_medium_low_info() -> None:
    fs = [_f("medium", "A-001", "Readability & quality bar")]
    payloads = issues.build_issue_payloads(fs)
    assert payloads == []


def test_emits_one_payload_per_critical_high() -> None:
    fs = [
        _f("critical", "A-001", "Readability & quality bar"),
        _f("high", "A-002", "Readability & quality bar"),
    ]
    payloads = issues.build_issue_payloads(fs)
    # Two issues, no umbrella (2 <= cap=5).
    assert len(payloads) == 2
    assert all("Readability & quality bar" in p.title for p in payloads)


def test_caps_at_5_per_cluster_with_umbrella() -> None:
    # 8 critical findings in cluster A → 5 individual + 1 umbrella with overflow=3.
    fs = [
        _f("critical", f"A-{i:03d}", "Readability & quality bar") for i in range(1, 9)
    ]
    payloads = issues.build_issue_payloads(fs)
    assert len(payloads) == 6  # 5 individual + 1 umbrella
    individual_titles = [p.title for p in payloads if "additional findings" not in p.title]
    umbrella_titles = [p.title for p in payloads if "additional findings" in p.title]
    assert len(individual_titles) == 5
    assert len(umbrella_titles) == 1
    assert "3 additional findings" in umbrella_titles[0]


def test_cap_per_cluster_not_global() -> None:
    """5 in cluster A + 5 in cluster B = 10 individual + 0 umbrellas (within cap each)."""
    fs_a = [_f("critical", f"A-{i:03d}", "Readability & quality bar") for i in range(1, 6)]
    fs_b = [_f("critical", f"B-{i:03d}", "Design & architecture") for i in range(1, 6)]
    payloads = issues.build_issue_payloads(fs_a + fs_b)
    assert len(payloads) == 10
    assert all("additional findings" not in p.title for p in payloads)


def test_labels_include_p0_for_critical() -> None:
    fs = [_f("critical", "A-001", "Readability & quality bar")]
    [p] = issues.build_issue_payloads(fs)
    assert "P0" in p.labels
    assert "audit-2026-08-09" in p.labels


def test_labels_include_p1_for_high() -> None:
    fs = [_f("high", "A-001", "Readability & quality bar")]
    [p] = issues.build_issue_payloads(fs)
    assert "P1" in p.labels
    assert "P0" not in p.labels


def test_repo_constant_matches_spec() -> None:
    assert issues.REPO == "Heretek-AI/heretek-claude-harness"
```

**Step 2: Run tests, expect FAIL**

Run: `python3 -m pytest tests/test_audit_issues.py -v`

Expected: FAIL — `scripts/audit/issues.py` does not exist.

**Step 3: Implement `scripts/audit/issues.py`**

Write `scripts/audit/issues.py`:

```python
"""Build GitHub MCP issue payloads from audit findings.

Per spec §Auto-issue creation rules:
  - HIGH and CRITICAL findings → one issue each
  - 5 issues per cluster cap; remainder bundled into one umbrella issue per cluster
  - Labels: audit, harness-self-audit, principles-audit, audit-2026-08-09,
    plus P0 (critical) or P1 (high)
  - Title: `[audit:spec-1:<cluster>] <one-line principle violation>`
  - Repo: Heretek-AI/heretek-claude-harness (confirmed during brainstorming)

This module ONLY builds the payloads. The actual `mcp__github__github-issue_write`
calls are made by the driver or the operator — keeping this module testable
without network/MCP access.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from collections import defaultdict

from audit import findings as findings_mod

REPO = "Heretek-AI/heretek-claude-harness"

BASE_LABELS: list[str] = [
    "audit",
    "harness-self-audit",
    "principles-audit",
    "audit-2026-08-09",
]

_AUDITABLE_SEVERITIES = {"critical", "high"}

_CLUSTER_SHORT: dict[str, str] = {
    "Readability & quality bar": "readability",
    "Design & architecture": "design",
    "Correctness & safety": "correctness",
    "Testing & verification": "testing",
    "Operations & docs": "ops-docs",
}


@dataclass(frozen=True)
class IssuePayload:
    title: str
    body: str
    labels: list[str]


def _title_for(f: findings_mod.Finding) -> str:
    short = _CLUSTER_SHORT.get(f.cluster, "unknown")
    return f"[audit:spec-1:{short}] {f.principle} ({f.evidence.file})"


def _body_for(f: findings_mod.Finding, report_link: str | None = None) -> str:
    lines = [
        "## Audit finding",
        "",
        f"**Cluster:** {f.cluster}",
        f"**Principle:** {f.principle}",
        f"**Severity:** {f.severity} (`{'P0' if f.severity == 'critical' else 'P1'}`)",
        f"**Adversarial posture:** {f.adversarial_posture}",
        f"**Recommended action:** {f.recommended_action}",
        "",
        "### Evidence",
        "",
        f"- **File:** `{f.evidence.file}`",
        f"- **Lines:** {f.evidence.line_range[0]}-{f.evidence.line_range[1]}",
        f"- **Metric:** {f.evidence.metric}",
        f"- **Refs:** {', '.join(f.evidence.code_refs)}",
        "",
        "### Failure scenario",
        "",
        f.failure_scenario,
        "",
        "### Rationale",
        "",
        f.rationale,
        "",
        "### Principle reference",
        "",
        f.principle_reference,
        "",
    ]
    if f.drift_signals:
        lines.extend(["### Drift signals", ""])
        for s in f.drift_signals:
            lines.append(f"- {s}")
        lines.append("")
    if report_link:
        lines.extend(["---", "", f"_Full report: {report_link}_", ""])
    return "\n".join(lines)


def _umbrella_body(cluster: str, overflow_count: int) -> str:
    return (
        f"## Audit umbrella: {cluster}\n\n"
        f"This cluster has **{overflow_count} additional findings** beyond the "
        "5-per-cluster cap for auto-issue creation. See the full report for the "
        "complete list (synthesis JSON at `catalog/reviews/audit-harness-self-"
        "*.json`).\n\n"
        "Filing individual issues for every finding would flood the queue; "
        "this umbrella tracks the remainder for triage.\n"
    )


def build_issue_payloads(
    items: list[findings_mod.Finding],
    *,
    cap: int = 5,
    report_link: str | None = None,
) -> list[IssuePayload]:
    """Group HIGH+CRITICAL findings by cluster; emit up to `cap` issues per cluster,
    plus one umbrella issue per cluster for any overflow.

    `report_link` is included in each individual issue body if provided.
    """
    by_cluster: dict[str, list[findings_mod.Finding]] = defaultdict(list)
    for f in items:
        if f.severity in _AUDITABLE_SEVERITIES:
            by_cluster[f.cluster].append(f)

    payloads: list[IssuePayload] = []
    for cluster, cluster_findings in by_cluster.items():
        # Rank by severity (critical first), then by file for determinism.
        cluster_findings.sort(
            key=lambda x: (findings_mod.severity_rank(x), x.evidence.file)
        )
        individual = cluster_findings[:cap]
        overflow = cluster_findings[cap:]

        for f in individual:
            priority_label = "P0" if f.severity == "critical" else "P1"
            payloads.append(
                IssuePayload(
                    title=_title_for(f),
                    body=_body_for(f, report_link=report_link),
                    labels=[*BASE_LABELS, priority_label],
                )
            )
        if overflow:
            short = _CLUSTER_SHORT.get(cluster, "unknown")
            payloads.append(
                IssuePayload(
                    title=f"[audit:spec-1:{short}] {len(overflow)} additional findings from harness self-audit",
                    body=_umbrella_body(cluster, len(overflow)),
                    labels=[*BASE_LABELS, "P1"],
                )
            )
    return payloads
```

**Step 4: Run tests, expect PASS**

Run: `python3 -m pytest tests/test_audit_issues.py -v`

Expected: 7 tests pass.

**Step 5: Commit**

```bash
git add scripts/audit/issues.py tests/test_audit_issues.py
git commit -m "feat(audit): add issue-payload builder (cap + umbrella)

Per spec §Auto-issue creation rules: HIGH+CRITICAL only, 5/cluster cap,
1 umbrella issue per cluster for overflow. Labels include audit,
harness-self-audit, principles-audit, audit-2026-08-09, plus P0 (critical)
or P1 (high). REPO constant matches spec-confirmed
'Heretek-AI/heretek-claude-harness'. This module only builds payloads;
the actual mcp__github__github-issue_write calls happen in the driver or
by the operator — keeping this module network-free and testable.

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

## Task 7: `scripts/audit/harness_self.py` — driver / CLI (TDD)

**Files:**
- Create: `scripts/audit/harness_self.py`
- Create: `tests/test_audit_harness_self.py`

**Interfaces:**
- Consumes: cluster-results directory + report/JSON from synthesis + issue payloads from `issues.py`.
- Produces:
  - CLI subcommands:
    - `python scripts/audit/harness_self.py emit-prompts --repo-root PATH --commit-sha SHA --out-dir DIR` — writes one `<letter>.txt` per cluster into `out-dir` (so the operator can pipe them into fresh Explore-agents).
    - `python scripts/audit/harness_self.py synthesize --cluster-results DIR --output-dir DIR --commit-sha SHA [--sonar-exclusions-file PATH]` — runs synthesis; writes report + JSON.
    - `python scripts/audit/harness_self.py build-issues --findings-json PATH --output PATH [--report-link URL]` — reads synthesis JSON, writes an `issues-to-create.json` payload file (the operator uses GitHub MCP to actually create them).
    - `python scripts/audit/harness_self.py run-all --repo-root PATH --output-dir DIR [--sonar-exclusions-file PATH]` — convenience: synthesize only (issue creation requires MCP and is operator-driven).

**Step 1: Write failing tests `tests/test_audit_harness_self.py`**

Write `tests/test_audit_harness_self.py`:

```python
"""Tests for scripts/audit/harness_self.py."""
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

from audit import harness_self  # noqa: E402


def _sample_finding(severity: str = "high", fid: str = "A-001") -> dict:
    return {
        "finding_id": fid,
        "cluster": "Readability & quality bar",
        "principle": "Small, focused functions",
        "severity": severity,
        "adversarial_posture": "violated",
        "evidence": {
            "code_refs": ["x.py:1-2"],
            "file": "x.py",
            "line_range": [1, 2],
            "metric": "x",
        },
        "failure_scenario": "x",
        "recommended_action": "refactor",
        "rationale": "x",
        "principle_reference": "x",
        "drift_signals": [],
    }


def test_emit_prompts_writes_one_file_per_cluster(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    out_dir = tmp_path / "prompts"
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "harness_self.py",
            "emit-prompts",
            "--repo-root", str(tmp_path),
            "--commit-sha", "deadbeef",
            "--out-dir", str(out_dir),
        ],
    )
    assert harness_self.main() == 0
    for letter in ("A", "B", "C", "D", "E"):
        assert (out_dir / f"{letter}.txt").is_file()
        assert "deadbeef" in (out_dir / f"{letter}.txt").read_text()


def test_synthesize_subcommand_writes_outputs(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    in_dir = tmp_path / "in"
    in_dir.mkdir()
    (in_dir / "A.yaml").write_text("[" + json.dumps(_sample_finding()) + "]")
    out_dir = tmp_path / "out"
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "harness_self.py",
            "synthesize",
            "--cluster-results", str(in_dir),
            "--output-dir", str(out_dir),
            "--commit-sha", "deadbeef",
        ],
    )
    assert harness_self.main() == 0
    # Outputs: audit-harness-self-<today>.md and .json
    assert any(out_dir.glob("audit-harness-self-*.md"))
    assert any(out_dir.glob("audit-harness-self-*.json"))


def test_build_issues_subcommand_writes_payload_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Build a findings JSON file.
    findings_file = tmp_path / "findings.json"
    findings_file.write_text(json.dumps([_sample_finding(severity="critical")]))
    out_file = tmp_path / "issues.json"
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "harness_self.py",
            "build-issues",
            "--findings-json", str(findings_file),
            "--output", str(out_file),
        ],
    )
    assert harness_self.main() == 0
    data = json.loads(out_file.read_text())
    assert len(data) == 1
    assert data[0]["labels"]  # non-empty
    assert "[audit:spec-1:" in data[0]["title"]


def test_unknown_subcommand_exits_one(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(sys, "argv", ["harness_self.py", "bogus"])
    assert harness_self.main() == 1
```

**Step 2: Run tests, expect FAIL**

Run: `python3 -m pytest tests/test_audit_harness_self.py -v`

Expected: FAIL — `scripts/audit/harness_self.py` does not exist.

**Step 3: Implement `scripts/audit/harness_self.py`**

Write `scripts/audit/harness_self.py`:

```python
"""CLI driver for the heretek harness self-audit.

Subcommands:
  emit-prompts       Write one prompt file per cluster (A-E) for an Explore-agent.
  synthesize         Run synthesis on a cluster-results directory.
  build-issues       Build GitHub MCP issue payloads from synthesis JSON.

This driver intentionally does NOT call GitHub MCP directly. Building
the payloads is the safe, testable part; the actual `mcp__github__github-
issue_write` calls happen in the operator's Claude session at execution
time, when MCP is available. This keeps the driver runnable in CI and
during local dry-runs.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Iterable

from audit import findings as findings_mod
from audit import issues as issues_mod
from audit import prompts as prompts_mod
from audit import synthesis as synthesis_mod


def _cmd_emit_prompts(args: argparse.Namespace) -> int:
    out_dir: Path = args.out_dir
    out_dir.mkdir(parents=True, exist_ok=True)
    for letter in prompts_mod.CLUSTERS.keys():
        rendered = prompts_mod.render_prompt(letter, args.repo_root, args.commit_sha)
        (out_dir / f"{letter}.txt").write_text(rendered)
    print(f"emit-prompts: wrote {len(prompts_mod.CLUSTERS)} prompt files to {out_dir}")
    return 0


def _cmd_synthesize(args: argparse.Namespace) -> int:
    sonar_exclusions: set[str] = set()
    if args.sonar_exclusions_file:
        if args.sonar_exclusions_file.is_file():
            sonar_exclusions = {
                line.strip()
                for line in args.sonar_exclusions_file.read_text().splitlines()
                if line.strip() and not line.startswith("#")
            }
    result = synthesis_mod.synthesize(
        cluster_results_dir=args.cluster_results,
        output_dir=args.output_dir,
        commit_sha=args.commit_sha,
        sonar_exclusions=sonar_exclusions,
    )
    print(
        f"synthesize: {len(result.findings)} finding(s); "
        f"{result.duplicate_count} duplicate(s) collapsed; "
        f"report at {result.report_path}; JSON at {result.json_path}"
    )
    if result.coverage_gaps:
        print(f"synthesize: {len(result.coverage_gaps)} coverage gap(s) flagged", file=sys.stderr)
    return 0


def _cmd_build_issues(args: argparse.Namespace) -> int:
    raw = json.loads(args.findings_json.read_text())
    fs = [findings_mod.Finding.from_dict(d) for d in raw]
    payloads = issues_mod.build_issue_payloads(fs, report_link=args.report_link)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(
            [{"title": p.title, "body": p.body, "labels": p.labels} for p in payloads],
            indent=2,
        )
        + "\n"
    )
    print(f"build-issues: {len(payloads)} payload(s) written to {args.output}")
    print(f"  repo: {issues_mod.REPO} (use GitHub MCP, not gh CLI)")
    return 0


def main(argv: Iterable[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    p_emit = sub.add_parser("emit-prompts", help="Write one prompt file per cluster.")
    p_emit.add_argument("--repo-root", type=Path, required=True)
    p_emit.add_argument("--commit-sha", required=True)
    p_emit.add_argument("--out-dir", type=Path, required=True)

    p_syn = sub.add_parser("synthesize", help="Run synthesis on cluster results.")
    p_syn.add_argument("--cluster-results", type=Path, required=True)
    p_syn.add_argument("--output-dir", type=Path, required=True)
    p_syn.add_argument("--commit-sha", required=True)
    p_syn.add_argument("--sonar-exclusions-file", type=Path, default=None)

    p_iss = sub.add_parser("build-issues", help="Build GitHub MCP issue payloads.")
    p_iss.add_argument("--findings-json", type=Path, required=True)
    p_iss.add_argument("--output", type=Path, required=True)
    p_iss.add_argument("--report-link", default=None)

    args = parser.parse_args(argv)

    if args.command == "emit-prompts":
        return _cmd_emit_prompts(args)
    if args.command == "synthesize":
        return _cmd_synthesize(args)
    if args.command == "build-issues":
        return _cmd_build_issues(args)
    print(f"harness-self: unknown subcommand: {args.command}", file=sys.stderr)
    return 1


if __name__ == "__main__":
    sys.exit(main())
```

**Step 4: Run tests, expect PASS**

Run: `python3 -m pytest tests/test_audit_harness_self.py -v`

Expected: 4 tests pass.

**Step 5: Commit**

```bash
git add scripts/audit/harness_self.py tests/test_audit_harness_self.py
git commit -m "feat(audit): add CLI driver (emit-prompts / synthesize / build-issues)

Three subcommands. emit-prompts writes one prompt file per cluster
to --out-dir for the operator to paste into Explore-agents. synthesize
runs the synthesis pass (validate + dedupe + SonarCloud exclusions +
report + JSON). build-issues reads the synthesis JSON and writes a
GitHub-MCP-ready payload file. The driver does NOT call GitHub MCP
itself — payload creation is the safe, testable part; the actual
mcp__github__github-issue_write calls happen in the operator's session
when MCP is available.

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

## Task 8: End-to-end smoke test — fixture cluster results → synthesize → build-issues

**Files:**
- Create: `tests/fixtures/audit/cluster_results/A.yaml`
- Create: `tests/fixtures/audit/cluster_results/B.yaml`
- Create: `tests/fixtures/audit/cluster_results/C.yaml`
- Create: `tests/test_audit_e2e.py`

**Interfaces:**
- Consumes: `tests/fixtures/audit/cluster_results/*` (fixture cluster outputs).
- Produces: an end-to-end test that proves synthesize → build-issues produces a valid payload list, and that the report markdown mentions the snapshot SHA + summary numbers.

**Step 1: Write fixture cluster result `A.yaml`**

Write `tests/fixtures/audit/cluster_results/A.yaml`:

```yaml
- finding_id: A-001
  cluster: Readability & quality bar
  principle: Small, focused functions
  severity: high
  adversarial_posture: violated
  evidence:
    code_refs: ["scripts/validate.py:124-187"]
    file: scripts/validate.py
    line_range: [124, 187]
    metric: cognitive_complexity=42 (threshold=15, repo p95=12)
  failure_scenario: >-
    When a plugin manifest has 5 nested conditional branches, this function
    returns the wrong D7 status because the early-exit path is missed.
  recommended_action: refactor
  rationale: >-
    Function violates the small-focused-functions principle; shows up in the
    SonarCloud p99 complexity report.
  principle_reference: Code quality > Maintainability > small, focused functions
  drift_signals: []
```

**Step 2: Write fixture cluster result `B.yaml`**

Write `tests/fixtures/audit/cluster_results/B.yaml`:

```yaml
- finding_id: B-001
  cluster: Design & architecture
  principle: Single Responsibility
  severity: critical
  adversarial_posture: violated
  evidence:
    code_refs: ["scripts/scanners/scanner_base.py:1-200"]
    file: scripts/scanners/scanner_base.py
    line_range: [1, 200]
    metric: file_loc=200+ classes_in_module=5
  failure_scenario: >-
    Adding a sixth scanner kind requires editing this module in 4 places;
    signals multiple responsibilities.
  recommended_action: refactor
  rationale: SRP violation; scanner_base.py mixes base class, dispatcher, and report shape.
  principle_reference: Design & architecture > SOLID > SRP
  drift_signals: []
```

**Step 3: Write fixture cluster result `C.yaml`**

Write `tests/fixtures/audit/cluster_results/C.yaml`:

```yaml
- finding_id: C-001
  cluster: Correctness & safety
  principle: Explicit error handling
  severity: medium
  adversarial_posture: violated
  evidence:
    code_refs: ["scripts/refresh_pins.py:55-67"]
    file: scripts/refresh_pins.py
    line_range: [55, 67]
    metric: bare-except-count=2
  failure_scenario: >-
    A transient network failure is silently swallowed; the run appears to
    succeed but no pins were refreshed.
  recommended_action: refactor
  rationale: Silent failure violates explicit-error-handling principle.
  principle_reference: Correctness & safety > error handling
  drift_signals: []
```

**Step 4: Write `tests/test_audit_e2e.py`**

Write `tests/test_audit_e2e.py`:

```python
"""End-to-end test: fixture cluster results → synthesize → build-issues → payload sanity."""
import json
import re
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

from audit import findings, harness_self, issues, synthesis, validate  # noqa: E402


@pytest.fixture(autouse=True)
def _set_schema(schemas_dir: Path) -> None:
    validate.SCHEMA_PATH = schemas_dir / "audit_finding.schema.json"


FIXTURES = Path(__file__).resolve().parent / "fixtures" / "audit" / "cluster_results"


def test_e2e_synthesize_then_build_issues(tmp_path: Path) -> None:
    """Run the full pipeline against fixture cluster results."""
    # Step 1: synthesize
    result = synthesis.synthesize(
        cluster_results_dir=FIXTURES,
        output_dir=tmp_path / "out",
        commit_sha="e2etest0",
    )
    assert len(result.findings) == 3
    # Verify the report mentions the snapshot SHA.
    md = result.report_path.read_text()
    assert "e2etest0" in md
    assert "Critical: 1" in md
    assert "High: 1" in md
    assert "Medium: 1" in md

    # Step 2: build-issues (via the synthesis JSON)
    fs = [findings.Finding.from_dict(d) for d in json.loads(result.json_path.read_text())]
    payloads = issues.build_issue_payloads(fs)
    # 1 critical + 1 high → 2 issues; medium excluded.
    assert len(payloads) == 2
    titles = {p.title for p in payloads}
    assert any("validate.py" in t for t in titles)
    assert any("scanner_base.py" in t for t in titles)


def test_e2e_run_all_via_driver(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Call the driver's synthesize subcommand end-to-end via the CLI."""
    out_dir = tmp_path / "out"
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "harness_self.py",
            "synthesize",
            "--cluster-results", str(FIXTURES),
            "--output-dir", str(out_dir),
            "--commit-sha", "e2etest1",
        ],
    )
    assert harness_self.main() == 0
    assert any(out_dir.glob("audit-harness-self-*.md"))
    assert any(out_dir.glob("audit-harness-self-*.json"))


def test_e2e_emit_prompts_then_synthesize(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """emit-prompts + synthesize via the driver."""
    prompts_dir = tmp_path / "prompts"
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "harness_self.py",
            "emit-prompts",
            "--repo-root", str(tmp_path),
            "--commit-sha", "e2etest2",
            "--out-dir", str(prompts_dir),
        ],
    )
    assert harness_self.main() == 0
    assert (prompts_dir / "A.txt").is_file()
    assert "Readability" in (prompts_dir / "A.txt").read_text()
```

**Step 5: Run the new test, expect PASS**

Run: `python3 -m pytest tests/test_audit_e2e.py -v`

Expected: 3 tests pass.

**Step 6: Run the entire audit test suite to confirm nothing regressed**

Run: `python3 -m pytest tests/test_audit_schema.py tests/test_audit_validate.py tests/test_audit_findings.py tests/test_audit_prompts.py tests/test_audit_synthesis.py tests/test_audit_issues.py tests/test_audit_harness_self.py tests/test_audit_e2e.py -v`

Expected: all tests pass (4 + 6 + 5 + 9 + 4 + 7 + 4 + 3 = 42 tests).

**Step 7: Run the full repo test suite to confirm no other test broke**

Run: `python3 -m pytest -q`

Expected: all tests pass, including the existing harness tests (`test_validate.py`, `test_suppression.py`, etc.) and the 42 new audit tests.

**Step 8: Commit**

```bash
git add tests/fixtures/audit/cluster_results/A.yaml \
        tests/fixtures/audit/cluster_results/B.yaml \
        tests/fixtures/audit/cluster_results/C.yaml \
        tests/test_audit_e2e.py
git commit -m "test(audit): add end-to-end smoke test (Spec 1)

Fixture cluster results for A/B/C drive synthesize -> build-issues
end-to-end. Verifies: report mentions snapshot SHA + correct severity
counts; payloads produced for HIGH+CRITICAL only (medium excluded).
Driver CLI tested via monkeypatch argv. All 42 audit tests pass;
no existing harness test regressed.

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

## Self-Review

### 1. Spec coverage

Walking through each requirement in `docs/superpowers/specs/2026-08-09-heretek-harness-self-audit-design.md`:

| Spec section | Plan tasks |
|---|---|
| Goal: hostile audit + auto-issues | Tasks 1-8 collectively implement the toolkit. The actual run is executor-driven (paste prompts to fresh Explore-agents). |
| In scope: scripts/, scripts/scanners/, tests/, plugins/hooks/, root configs + docs | Audit target — not part of THIS toolkit build; the toolkit operates on findings produced by cluster agents. |
| Out of scope | Honored — no code in `catalog/`, `docs/superpowers/{specs,plans,...}/`, etc. |
| Methodology: 5 cluster lanes (Option A) | Task 4 (`prompts.py` — 5 cluster prompt templates, one per lane) |
| Per-finding schema (11 fields + 4 evidence subkeys) | Task 1 (JSON Schema) + Task 3 (Finding dataclass) |
| Severity model (5 levels) | Task 1 (enum) + Task 3 (`severity_rank`) |
| Adversarial posture (3 values) | Task 1 (enum) |
| Recommended action (5 values) | Task 1 (enum) |
| Synthesis pass (10 steps) | Task 5 (steps 1, 4, 6, 8, 9, 10 — operator-driven steps 2, 3, 5, 7 are flagged in the report's "Re-verification checklist") |
| Auto-issue creation rules (HIGH/CRITICAL, 5/cluster cap, umbrella, labels, repo) | Task 6 (cap + umbrella + labels + REPO constant) |
| Verification standard (pytest-able validator) | Tasks 1, 2, 8 (full pytest coverage of `audit.validate`) |
| Risks: cluster overlap (synthesis dedupes) | Task 5 (`_dedupe` by `(file, line_range)`) |
| Risks: adversarial over-flagging | Task 5 (report's "Re-verification checklist") |
| Risks: auto-issue flood | Task 6 (5/cluster cap + umbrella) |
| Risks: hallucinated metrics | Task 5 (report flags cluster-A files for lizard/radon re-check) |
| Risks: catalog drift mid-audit | Task 4 (prompts include `--commit-sha`); Task 5 (snapshot SHA in every report/JSON) |
| Risks: false-positive HIGH/CRITICAL becoming issues | Task 5 (re-verification checklist is mandatory before issue creation; operator runs `build-issues` only after re-verification) |
| Risks: memory drift | Out of plan scope — toolkit is deterministic; only the operator invokes memory |
| Risks: gh CLI vs GitHub MCP | Task 6 (REPO constant for MCP); Task 7 (driver emits payload file, does NOT call gh) |
| Files the spec will produce | `tests/schemas/audit_finding.schema.json` (Task 1), `catalog/reviews/audit-harness-self-*.md` + `.json` (Task 5), `scripts/audit_validate.py` → split into `scripts/audit/{validate,findings,prompts,synthesis,issues,harness_self}.py` per the spec's plan note |
| Auto-issue cap: 5/cluster + 1 umbrella/cluster | Task 6 (`build_issue_payloads`) |

**Gaps:**
- The spec lists `scripts/audit_validate.py` as a single file; the plan splits it into a package `scripts/audit/` with six small modules. This is a *decomposition refinement* — the spec also says "Files that change together live together. Split by responsibility" via the SP1 plan structure. The package decomposition is justified by single-responsibility boundaries (validate / findings / prompts / synthesis / issues / driver). The user's brainstorm approved this approach (Section 3 said "synthesis pass", "auto-issue creation", "schema validation script" as distinct steps).
- The actual running of the 5 cluster agents is *not* in this plan — that's the execution phase. The toolkit is what gets built; the executor runs the audit by pasting the prompt files into fresh Explore-agents and feeding the YAML results back through `synthesize`. This split is implicit in the brainstorming design (the "execution handoff" is to whichever sub-skill the user picks next).

### 2. Placeholder scan

Searched for: `TBD`, `TODO`, `FIXME`, `XXX`, "implement later", "fill in details", "add appropriate error handling", "write tests for the above", "similar to Task N", missing code blocks.

- `TBD` / `TODO` / `FIXME` / `XXX`: none in the plan body. (Spec quotes use "TODO/FIXME" in describing what the audit searches for in code — that's intentional, not a placeholder.)
- "implement later" / "fill in details" / "add appropriate error handling" / "similar to Task N": none.
- "write tests for the above": every test step has actual test code.
- Missing code blocks in code steps: none — every Python step has a complete code block.
- One ambiguous phrase: "drafted but not yet committed" — does not appear. The phrase "in the operator's session" is used multiple times to clarify responsibility boundaries; that's intentional, not a placeholder.

### 3. Type / name consistency

Cross-task audit:

- `audit.validate.SCHEMA_PATH: Path` — Task 2 sets default + tests monkeypatch. Tasks 3, 5, 6, 8 fixtures all set it via autouse fixture. Consistent.
- `audit.findings.Finding.from_dict(d) -> Finding` — Task 3 implements; Tasks 6, 7, 8 use. Consistent.
- `audit.findings.Evidence` (nested dataclass) — Task 3 defines; Tasks 6, 7, 8 reference via `f.evidence.{file,line_range,code_refs,metric}`. Consistent.
- `audit.findings.severity_rank(finding) -> int` — Task 3 defines; Tasks 5, 6 use. Consistent.
- `audit.synthesis.synthesize(...) -> SynthesisResult` — Task 5 implements; Task 7 calls; Task 8 e2e test uses. Consistent.
- `audit.synthesis.SynthesisResult.{findings, report_path, json_path, coverage_gaps, duplicate_count}` — Task 5 defines; Task 8 references all five fields. Consistent.
- `audit.issues.IssuePayload.{title, body, labels}` — Task 6 defines; Task 7 emits JSON with those keys. Consistent.
- `audit.issues.REPO = "Heretek-AI/heretek-claude-harness"` — Task 6 constant; Task 7 references. Consistent.
- `audit.issues.build_issue_payloads(items, *, cap=5, report_link=None)` — Task 6 defines; Task 8 e2e uses default cap. Consistent.
- `audit.prompts.CLUSTERS: dict[str, ClusterPrompt]` with keys A-E — Task 4 defines; Task 7 driver iterates over `CLUSTERS.keys()`. Consistent.
- `audit.prompts.render_prompt(letter, repo_root, commit_sha) -> str` — Task 4 defines; Task 7 calls. Consistent.
- `audit.prompts.ClusterPrompt.{letter, title, principles, evidence_strategy, template}` — Task 4 defines; tests reference all five. Consistent.
- CLI subcommand names (`emit-prompts`, `synthesize`, `build-issues`) — Tasks 7 + 8 use the same strings. Consistent.
- File path `tests/fixtures/audit/cluster_results/{A,B,C}.yaml` — Task 8 fixtures; Task 8 test FIXTURES constant. Consistent.
- JSON Schema filename `tests/schemas/audit_finding.schema.json` — Tasks 1, 2, 3, 5, 6, 8 all reference. Consistent.

No mismatches found.

---

## Exit criteria

When all 8 tasks are complete:

1. **Schema validates findings.** `python -m pytest tests/test_audit_schema.py` passes; valid YAML/JSON cards pass schema; missing-required and bad-enum cards fail. (Task 1.)
2. **Validator works as CLI + library.** `python -m pytest tests/test_audit_validate.py` passes (6 tests). `python scripts/audit/validate.py <file>` exits 0 on valid, 1 on invalid. (Task 2.)
3. **Findings load/save round-trips.** `python -m pytest tests/test_audit_findings.py` passes (5 tests). (Task 3.)
4. **5 cluster prompts exist.** `python -m pytest tests/test_audit_prompts.py` passes (9 tests). `python scripts/audit/prompts.py A --repo-root PATH --commit-sha SHA` prints a usable prompt with both placeholders substituted. (Task 4.)
5. **Synthesis dedupes + writes report + JSON.** `python -m pytest tests/test_audit_synthesis.py` passes (4 tests). (Task 5.)
6. **Issue builder respects cap + umbrella + labels + repo.** `python -m pytest tests/test_audit_issues.py` passes (7 tests). (Task 6.)
7. **CLI driver wires it all.** `python -m pytest tests/test_audit_harness_self.py` passes (4 tests). (Task 7.)
8. **End-to-end pipeline passes.** `python -m pytest tests/test_audit_e2e.py` passes (3 tests). `python -m pytest` passes overall (42 new + existing tests). (Task 8.)

The toolkit is ready. Executing the actual hostile audit is a separate phase: the executor pastes the 5 prompt files into fresh Explore-agents, collects their YAML outputs into a directory, then runs `python scripts/audit/harness_self.py synthesize --cluster-results <dir> --output-dir catalog/reviews --commit-sha <sha>` and reviews the report + JSON. After operator re-verification per the report's checklist, `python scripts/audit/harness_self.py build-issues --findings-json <json> --output <payloads.json>` produces the GitHub MCP payload file; the operator then runs `mcp__github__github-issue_write` calls in their session to actually create the issues.

The next spec/plan work — Spec 2 (plugins marketplace audit) and Spec 3 (enforcement surface audit) — can each use this same toolkit with a different `--cluster-results` directory and (for Spec 3) different `prompts.py` cluster definitions. Reuse, not duplication.