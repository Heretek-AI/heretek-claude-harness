# Heretek Tracking Layer Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the harness-agnostic tracking layer for the Heretek AI Package Ecosystem: a checked-in YAML seed in the umbrella, an idempotent shell script that mirrors it into GitHub Issues with a 2-axis label taxonomy, and ≈20 sandbox tests that prove the contract.

**Architecture:** Jinja templates under `templates/seeds/` render to `seeds/*.yaml` (committed canon) via `scripts/lib/render_seed.py` (sibling of `render_tracking.py`). A `scripts/lib/seed_loader.py` validates seeds against `schemas/seed.schema.json` and emits the 5-section body markdown. A `scripts/seed-issues.sh` (also emitted from a Jinja template) reads the seed from the umbrella at runtime and reflects it into GitHub Issues. `init-harness.sh` calls `render_seed` alongside the existing renderers, and `contract_hash.py` is extended to include the new outputs.

**Tech Stack:** Python 3.11+, Jinja2, jsonschema, pytest, ruff, bash, yq, jq, gh CLI ≥ 2.40.

**Spec:** `docs/superpowers/specs/2026-08-01-heretek-tracking-layer-design.md` (commit `6ac0f21`).

## Global Constraints

The following are project-wide requirements from the spec. Every task's requirements implicitly include this section.

- **Schema version:** `1` (literal int) at `seeds/<repo>.yaml` and `seeds/labels.yaml` top-level.
- **Issue `id` format:** `^[a-z]{2}-[0-9]{4}$`. Convention: `lb-` for llama-builds, `hm-` for heretek-manager, followed by a monotonic 4-digit counter.
- **Body sections (exact, in order):** `Source`, `Goal`, `Acceptance criteria`, `Out of scope`, `Dependencies`. The `<!-- seed-id: <id> -->` HTML comment is the idempotency key and must be the first line.
- **Footer (mandatory):** `_Filed by scripts/seed-issues.sh from seeds/<repo>.yaml. Re-running the script with the same seed is idempotent (issues are matched by seed-id: <id> HTML comment at the top)._`
- **Labels:** exactly one `phase/*`, one `component/*`, one `status/*` per issue. Three axes: `phase/{1-ci-setup,2-cli-runtime,3-webui,4-matrix-pkg,meta}`, `component/{ci,manifest,auditor,symlink,upstream-sync,webui,api,store,infra,manager,docs}`, `status/{backlog,in-progress,blocked,review,done}`.
- **Seed-issues.sh guarantees:** idempotent on re-run, never overwrites human-edited issue bodies without body-hash diff, refuses to act on closed issues without `--prune-closed`, retries once on network failure.
- **Render pipeline:** `render_seed.py` is a sibling of `render_tracking.py` — same Jinja env pattern, same `dict[str, str]` return.
- **AGENTS.md schema:** unchanged. The Pointer block is a free-form bullet list inside the section; section count is locked at 7 but bullet count is not.
- **Children never store a seed copy:** `seed-issues.sh` reads the seed from the umbrella at runtime via `https://raw.githubusercontent.com/Heretek-AI/monorepo-manager/main/seeds/<repo>.yaml` (or `--seed-file <path>` override).
- **No new top-level CLI flags on `init-harness.sh`.** New renderer is wired into `_bundle()` exactly like the existing ones.
- **Test isolation:** all 20 new tests are unit + sandbox. No live GitHub API calls in CI.

## File Structure

**Created (umbrella):**

| path | responsibility |
|---|---|
| `schemas/seed.schema.json` | JSON-Schema contract for `seeds/*.yaml` shape |
| `scripts/lib/seed_loader.py` | load + validate seeds, emit body markdown (CLI: `validate <path>`, `emit <path> <id>`) |
| `scripts/lib/render_seed.py` | render labels + per-repo seeds + seed-issues.sh from Jinja |
| `templates/seeds/labels.yaml.j2` | Jinja source for label definitions |
| `templates/seeds/llama-builds.yaml.j2` | Jinja source for the llama-builds backlog (~30 issues) |
| `templates/seeds/heretek-manager.yaml.j2` | Jinja source for the heretek-manager backlog (~30 issues) |
| `templates/seeds/seed-issues.sh.j2` | Jinja source for the per-child copy of the shell script |
| `seeds/labels.yaml` | generated canon labels (checked in) |
| `seeds/llama-builds.yaml` | generated canon backlog (checked in) |
| `seeds/heretek-manager.yaml` | generated canon backlog (checked in) |
| `tests/test_seed_loader.py` | 6 tests for schema validation |
| `tests/test_render_seed.py` | 4 tests for renderer |
| `tests/test_seed_issues_script.py` | 6 tests sandbox-running `seed-issues.sh --dry-run` |
| `tests/test_contract_hash.py` (extend) | 2 tests for new hash entry |
| `docs/superpowers/runbooks/seed-issues.md` | first-run + reseed runbook |

**Modified (umbrella):**

| path | change |
|---|---|
| `scripts/lib/cli.py` | import `render_seed`, call `render_labels` + `render_repo_seed(slug)` + `render_seed_issues_script(org, repo, slug)` in `_bundle()` merge into `files` |
| `scripts/lib/contract_hash.py` | add helper `compute_seeds_hash()` that hashes the three `seeds/*.yaml` files; OR extend `_bake_contract_hash` to consume an additional file set |
| `templates/AGENTS.md.j2` | add `{% if seed_url %}`-gated Pointer block bullet |
| `tests/test_render_agents.py` | one new test asserting the seed URL bullet appears |

**Created by `init-harness.sh --generate` (children):**

| path | source |
|---|---|
| `.github/labels/labels.yaml` | copy of `seeds/labels.yaml` |
| `scripts/seed-issues.sh` | emitted from `templates/seeds/seed-issues.sh.j2` with `--repo` baked in |
| `AGENTS.md` Pointer block | gains one bullet pointing at the seed URL in the umbrella |

---

## Task 1: Schema + seed loader (foundation)

**Files:**
- Create: `schemas/seed.schema.json`
- Create: `scripts/lib/seed_loader.py`
- Test: `tests/test_seed_loader.py`

**Interfaces:**
- Produces: `scripts.lib.seed_loader.load_seed(path: str) -> dict` — returns parsed seed dict; raises `SeedValidationError` on schema/structural errors.
- Produces: `scripts.lib.seed_loader.validate_issue(issue: dict, labels: list[str]) -> list[str]` — returns list of error strings (empty if valid).
- Produces: `scripts.lib.seed_loader.emit_body_markdown(issue: dict) -> str` — returns the 5-section body markdown.
- Produces: `python -m scripts.lib.seed_loader validate <path>` — exits 0 on success, non-zero + stderr on failure.
- Produces: `python -m scripts.lib.seed_loader emit <path> <id>` — emits the body markdown for one issue to stdout; exits non-zero if id not found.

- [ ] **Step 1: Write the failing test**

`tests/test_seed_loader.py`:

```python
"""Tests for the seed loader (schema validation + body markdown emitter)."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from scripts.lib.seed_loader import (
    SeedValidationError,
    emit_body_markdown,
    load_seed,
    validate_issue,
)

LABELS = {
    "phase": ["phase/1-ci-setup", "phase/2-cli-runtime", "phase/3-webui", "phase/4-matrix-pkg", "phase/meta"],
    "component": ["component/ci", "component/manifest", "component/auditor", "component/symlink", "component/upstream-sync", "component/webui", "component/api", "component/store", "component/infra", "component/docs"],
    "status": ["status/backlog", "status/in-progress", "status/blocked", "status/review", "status/done"],
}
ALL_LABELS = [l for axis in LABELS.values() for l in axis]


def _good_issue() -> dict:
    return {
        "id": "lb-0001",
        "title": "Set up CI matrix",
        "phase": "phase/1-ci-setup",
        "component": "component/ci",
        "status": "status/backlog",
        "source": {"doc": "design.md", "section": "§2.1"},
        "goal": "Create the matrix workflow skeleton.",
        "acceptance": ["Workflow file committed", "Runs on pull_request"],
        "out_of_scope": ["Real matrix entries"],
        "depends_on": [],
    }


def test_validate_issue_accepts_well_formed_issue():
    assert validate_issue(_good_issue(), ALL_LABELS) == []


def test_validate_issue_rejects_unknown_phase_label():
    issue = _good_issue()
    issue["phase"] = "phase/9-future"
    errors = validate_issue(issue, ALL_LABELS)
    assert any("phase" in e for e in errors)


def test_validate_issue_rejects_bad_id_format():
    issue = _good_issue()
    issue["id"] = "LB-1"
    errors = validate_issue(issue, ALL_LABELS)
    assert any("id" in e for e in errors)


def test_validate_issue_rejects_empty_acceptance():
    issue = _good_issue()
    issue["acceptance"] = []
    errors = validate_issue(issue, ALL_LABELS)
    assert any("acceptance" in e for e in errors)


def test_validate_issue_rejects_depends_on_unknown_id(tmp_path: Path):
    seed = {"schema_version": 1, "repo": "Heretek-AI/llama-builds", "project_id": "", "issues": [_good_issue()]}
    seed["issues"][0]["depends_on"] = ["lb-9999"]
    seed_path = tmp_path / "seed.yaml"
    seed_path.write_text(json.dumps(seed))
    with pytest.raises(SeedValidationError) as exc:
        load_seed(str(seed_path))
    assert "lb-9999" in str(exc.value)


def test_emit_body_markdown_contains_all_five_sections():
    body = emit_body_markdown(_good_issue())
    for section in ("## Source", "## Goal", "## Acceptance criteria", "## Out of scope", "## Dependencies"):
        assert section in body
    assert "<!-- seed-id: lb-0001 -->" in body.splitlines()[0]


def test_seed_loader_cli_validate_exits_nonzero_on_missing_schema():
    bad = Path("/tmp/__no_such_schema__.yaml")
    bad.write_text("not: a: real: seed\n")
    result = subprocess.run(
        [sys.executable, "-m", "scripts.lib.seed_loader", "validate", str(bad)],
        capture_output=True, text=True,
    )
    assert result.returncode != 0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_seed_loader.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'scripts.lib.seed_loader'`.

- [ ] **Step 3: Write the schema**

`services → Save` `schemas/seed.schema.json`:

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "https://heretek-ai.dev/schemas/seed.schema.json",
  "title": "Heretek tracking seed",
  "type": "object",
  "required": ["schema_version", "repo", "project_id", "issues"],
  "additionalProperties": false,
  "properties": {
    "schema_version": {"const": 1},
    "repo": {"type": "string", "pattern": "^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$"},
    "project_id": {"type": "string"},
    "issues": {
      "type": "array",
      "items": {"$ref": "#/$defs/issue"}
    }
  },
  "$defs": {
    "issue": {
      "type": "object",
      "required": ["id", "title", "phase", "component", "status", "source", "goal", "acceptance", "out_of_scope", "depends_on"],
      "additionalProperties": false,
      "properties": {
        "id": {"type": "string", "pattern": "^[a-z]{2}-[0-9]{4}$"},
        "title": {"type": "string", "minLength": 1},
        "phase": {"type": "string"},
        "component": {"type": "string"},
        "status": {"type": "string"},
        "source": {
          "type": "object",
          "required": ["doc", "section"],
          "additionalProperties": false,
          "properties": {
            "doc": {"type": "string"},
            "section": {"type": "string"}
          }
        },
        "goal": {"type": "string", "minLength": 1},
        "acceptance": {"type": "array", "minItems": 1, "items": {"type": "string"}},
        "out_of_scope": {"type": "array", "items": {"type": "string"}},
        "depends_on": {"type": "array", "items": {"type": "string", "pattern": "^[a-z]{2}-[0-9]{4}$"}}
      }
    }
  }
}
```

- [ ] **Step 4: Write the loader**

`scripts/lib/seed_loader.py`:

```python
"""Seed loader: validate seeds/*.yaml and emit GitHub-issue body markdown."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import yaml
from jsonschema import Draft202012Validator

_SCHEMA_PATH = Path(__file__).parents[2] / "schemas" / "seed.schema.json"
_BODY_FOOTER = (
    "_Filed by scripts/seed-issues.sh from seeds/<repo>.yaml.\n"
    "Re-running the script with the same seed is idempotent (issues are\n"
    "matched by seed-id: <id> HTML comment at the top)._"
)


class SeedValidationError(Exception):
    """Raised when a seed fails schema or cross-reference validation."""


def _load_schema() -> dict:
    return json.loads(_SCHEMA_PATH.read_text(encoding="utf-8"))


def load_seed(path: str) -> dict:
    """Load and validate a seed YAML file. Raises SeedValidationError on failure."""
    schema = _load_schema()
    with open(path, encoding="utf-8") as f:
        data = yaml.safe_load(f)
    validator = Draft202012Validator(schema)
    errors = sorted(validator.iter_errors(data), key=lambda e: e.path)
    if errors:
        msgs = [f"{'/'.join(str(p) for p in e.absolute_path) or '<root>'}: {e.message}" for e in errors]
        raise SeedValidationError("seed schema violation:\n  " + "\n  ".join(msgs))

    known_ids = {i["id"] for i in data["issues"]}
    extra: list[str] = []
    for issue in data["issues"]:
        for dep in issue.get("depends_on", []):
            if dep not in known_ids:
                extra.append(f"{issue['id']}: depends_on {dep!r} not present in seed")
    if extra:
        raise SeedValidationError("seed cross-reference violation:\n  " + "\n  ".join(extra))
    return data


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
```

- [ ] **Step 5: Add dependencies**

Run: `pip install pyyaml jsonschema`
Commit this requirement by editing `pyproject.toml` `[project] dependencies` to include `"pyyaml>=6.0", "jsonschema>=4.0"` (open the file with Read first, then Edit). If `pyproject.toml` already uses `dependencies = [...]` arrays, add them; if it uses a `requires` table, add them there.

- [ ] **Step 6: Run test to verify it passes**

Run: `pytest tests/test_seed_loader.py -v`
Expected: 7 passed.

- [ ] **Step 7: Commit**

```bash
git add schemas/seed.schema.json scripts/lib/seed_loader.py tests/test_seed_loader.py pyproject.toml
git commit -m "feat(seed): add seed schema, loader, and body markdown emitter"
```

---

## Task 2: labels.yaml.j2 + render_labels()

**Files:**
- Create: `templates/seeds/labels.yaml.j2`
- Create: `scripts/lib/render_seed.py`
- Create: `tests/test_render_seed.py`

**Interfaces:**
- Produces: `scripts.lib.render_seed.render_labels() -> dict[str, str]` — returns one key: `"seeds/labels.yaml"`.
- Produces: `scripts.lib.render_seed.render_repo_seed(slug: str) -> dict[str, str]` — returns `"seeds/<slug>.yaml"` (added in Task 3).
- Produces: `scripts.lib.render_seed.render_seed_issues_script(org: str, repo: str) -> dict[str, str]` — returns `"scripts/seed-issues.sh"` (added in Task 4).

- [ ] **Step 1: Write the failing test**

`tests/test_render_seed.py`:

```python
"""Tests for the seed renderer (templates → seeds/*.yaml + scripts/seed-issues.sh)."""

from __future__ import annotations

from scripts.lib import render_seed


def test_render_labels_returns_canonical_labels_yaml():
    files = render_seed.render_labels()
    assert "seeds/labels.yaml" in files
    text = files["seeds/labels.yaml"]
    assert "schema_version: 1" in text
    for label in (
        "phase/1-ci-setup",
        "phase/2-cli-runtime",
        "phase/3-webui",
        "phase/4-matrix-pkg",
        "phase/meta",
        "component/ci",
        "component/manifest",
        "component/auditor",
        "component/symlink",
        "component/upstream-sync",
        "component/webui",
        "component/api",
        "component/store",
        "component/infra",
        "component/docs",
        "status/backlog",
        "status/in-progress",
        "status/blocked",
        "status/review",
        "status/done",
    ):
        assert label in text, f"missing label: {label}"


def test_render_labels_is_byte_identical_on_repeat():
    a = render_seed.render_labels()
    b = render_seed.render_labels()
    assert a == b
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_render_seed.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'scripts.lib.render_seed'`.

- [ ] **Step 3: Write the labels template**

`templates/seeds/labels.yaml.j2`:

```yaml
# Generated by scripts/lib/render_seed.py — do not edit by hand.
# Edit templates/seeds/labels.yaml.j2 instead.
schema_version: 1
labels:
  - name: phase/1-ci-setup
    color: "0E8A16"
    description: "Phase 1 — llama-builds CI/CD foundation"
  - name: phase/2-cli-runtime
    color: "1D76DB"
    description: "Phase 2 — heretek-manager CLI + hardware auditor"
  - name: phase/3-webui
    color: "5319E7"
    description: "Phase 3 — WebUI dashboard"
  - name: phase/4-matrix-pkg
    color: "BFD4F2"
    description: "Phase 4 — upstream package families (ecosystem matrix)"
  - name: phase/meta
    color: "C5DEF5"
    description: "Cross-cutting tracking items"
  - name: component/ci
    color: "D4C5F9"
    description: "GitHub Actions workflows"
  - name: component/manifest
    color: "C2E0C6"
    description: "manifest.json schema, generator, fetcher"
  - name: component/auditor
    color: "FBCA04"
    description: "Hardware detection (nvidia-smi / rocminfo / vulkaninfo)"
  - name: component/symlink
    color: "F9D0C4"
    description: "Atomic symlink swap in ~/.heretek/bin/"
  - name: component/upstream-sync
    color: "B084CC"
    description: "Tracking upstream llama.cpp forks"
  - name: component/webui
    color: "0052CC"
    description: "WebUI dashboard (Express server on :9048)"
  - name: component/api
    color: "006B75"
    description: "REST API endpoints"
  - name: component/store
    color: "BFD4F2"
    description: "Version store layout under ~/.heretek/store/"
  - name: component/infra
    color: "D93F0B"
    description: "Infrastructure-as-code (runners, secrets, caches)"
  - name: component/docs
    color: "0E8A16"
    description: "Documentation, README, examples"
  - name: status/backlog
    color: "BFBFBF"
    description: "Not started"
  - name: status/in-progress
    color: "FBCA04"
    description: "Actively being worked"
  - name: status/blocked
    color: "D93F0B"
    description: "Cannot progress; needs human intervention"
  - name: status/review
    color: "0E8A16"
    description: "PR open, awaiting review"
  - name: status/done
    color: "828282"
    description: "Merged and verified"
```

- [ ] **Step 4: Write the renderer skeleton**

`scripts/lib/render_seed.py`:

```python
"""Renderer for the tracking layer seeds and the seed-issues.sh script."""

from __future__ import annotations

from pathlib import Path

from jinja2 import Environment, FileSystemLoader, StrictUndefined

_TEMPLATE_DIR = Path(__file__).parents[2] / "templates" / "seeds"


def _env() -> Environment:
    return Environment(
        loader=FileSystemLoader(str(_TEMPLATE_DIR)),
        undefined=StrictUndefined,
        keep_trailing_newline=True,
    )


def render_labels() -> dict[str, str]:
    """Render the canonical labels seed."""
    return {"seeds/labels.yaml": _env().get_template("labels.yaml.j2").render()}
```

- [ ] **Step 5: Run test to verify it passes**

Run: `pytest tests/test_render_seed.py -v`
Expected: 2 passed.

- [ ] **Step 6: Commit**

```bash
git add templates/seeds/labels.yaml.j2 scripts/lib/render_seed.py tests/test_render_seed.py
git commit -m "feat(seed): render labels.yaml from Jinja template"
```

---

## Task 3: Per-repo seed templates + render_repo_seed()

**Files:**
- Create: `templates/seeds/llama-builds.yaml.j2`
- Create: `templates/seeds/heretek-manager.yaml.j2`
- Modify: `scripts/lib/render_seed.py` (add `render_repo_seed()`)
- Modify: `tests/test_render_seed.py` (add 2 tests)

**Interfaces:**
- Consumes: `slug in {"llama-builds", "heretek-manager"}`.
- Produces: `scripts.lib.render_seed.render_repo_seed(slug: str) -> dict[str, str]` — returns `{"seeds/<slug>.yaml": "<rendered YAML>"}`.

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_render_seed.py`:

```python
def test_render_repo_seed_llama_builds_has_at_least_25_issues():
    files = render_seed.render_repo_seed("llama-builds")
    assert "seeds/llama-builds.yaml" in files
    text = files["seeds/llama-builds.yaml"]
    # Crude count: one "- id:" per issue entry.
    assert text.count("- id:") >= 25, f"expected ≥25 issues, got {text.count('- id:')}"
    assert "schema_version: 1" in text
    assert "repo: Heretek-AI/llama-builds" in text


def test_render_repo_seed_heretek_manager_has_at_least_25_issues():
    files = render_seed.render_repo_seed("heretek-manager")
    assert "seeds/heretek-manager.yaml" in files
    text = files["seeds/heretek-manager.yaml"]
    assert text.count("- id:") >= 25
    assert "repo: Heretek-AI/heretek-manager" in text


def test_render_repo_seed_uses_correct_id_prefix():
    lb = render_seed.render_repo_seed("llama-builds")
    hm = render_seed.render_repo_seed("heretek-manager")
    assert "id: lb-" in lb["seeds/llama-builds.yaml"]
    assert "id: hm-" in hm["seeds/heretek-manager.yaml"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_render_seed.py::test_render_repo_seed_llama_builds_has_at_least_25_issues -v`
Expected: FAIL with `AttributeError: module 'scripts.lib.render_seed' has no attribute 'render_repo_seed'`.

- [ ] **Step 3: Write the llama-builds seed template**

`templates/seeds/llama-builds.yaml.j2` — covering phases 1, 4, and the matrix-pkg slice. Use the schema and the structured body fields (id, title, phase, component, status, source.{doc,section}, goal, acceptance, out_of_scope, depends_on). The body markdown is generated by `emit_body_markdown` at seed-issues.sh runtime; **only the YAML fields go here.**

Required enumeration (in this order, all `status: status/backlog` unless noted):

**phase/1-ci-setup** (component/ci):
- `lb-0001` "Set up GitHub Actions matrix workflow skeleton" (source: design §2.1)
- `lb-0002` "Define empty CUDA + ROCm + Vulkan matrix entries" (source: design §2.2, depends_on: [lb-0001])
- `lb-0003` "Add generate_manifest.py to scrape targets/*/build.sh" (source: design §2.3, component/manifest, depends_on: [lb-0001])
- `lb-0004` "Publish manifest.json to GitHub Pages on every release" (source: design §2.3, component/manifest, depends_on: [lb-0003])
- `lb-0005` "Add audit_matrix.py pre-build validation" (source: design §2.2, component/ci, depends_on: [lb-0002])
- `lb-0006` "Wire GITLEAKS + super-linter + SonarCloud + pre-commit CI checks" (source: design §5.1, component/infra, depends_on: [lb-0001])

**phase/4-matrix-pkg** (component/upstream-sync):
- `lb-0010` "Package ggml-org/llama.cpp upstream CPU baseline" (source: ecosystem §Core)
- `lb-0011` "Package ggml-org/llama.cpp upstream CUDA (sm_89/90a)" (source: design §2.2)
- `lb-0012` "Package ggml-org/llama.cpp upstream Vulkan" (source: design §2.2)
- `lb-0013` "Package ikawrakow/ik_llama.cpp with Trellis + FlashMLA flags" (source: ecosystem §Core, depends_on: [lb-0011])
- `lb-0014` "Package sgl-project/sglang with FlashInfer + Triton" (source: ecosystem §Core)
- `lb-0015` "Package fewtarius/CachyLLama with SSD-backed KV cache" (source: ecosystem §Core)
- `lb-0016` "Package croll83/llama.cpp-dgx with DFlash + NVFP4" (source: ecosystem §Core)
- `lb-0017` "Package lemonade-sdk/llamacpp-rocm for Strix Halo" (source: ecosystem §Hardware)
- `lb-0018` "Package TheTom/llama-cpp-turboquant with WHT + TCQ" (source: ecosystem §Quantization)
- `lb-0019` "Package AtomicBot-ai/atomic-llama-cpp-turboquant" (source: ecosystem §Quantization)
- `lb-0020` "Package spiritbuun/buun-llama-cpp" (source: ecosystem §Quantization)
- `lb-0021` "Package huawei-csl/KVarN with Hadamard + variance normalization" (source: ecosystem §Quantization)
- `lb-0022` "Package carlosfundora/llama.cpp-1-bit-turbo (RDNA2 gfx1030)" (source: ecosystem §Quantization)
- `lb-0023` "Package artalis-io/bitnet.c (1-bit / ternary)" (source: ecosystem §Quantization)
- `lb-0024` "Package NVIDIA-Merlin/HierarchicalKV" (source: ecosystem §Quantization)
- `lb-0025` "Package abetlen/llama-cpp-python with cibuildwheel matrix" (source: ecosystem §Bindings, depends_on: [lb-0011])
- `lb-0026` "Package shakfu/cyllama (Cython)" (source: ecosystem §Bindings)
- `lb-0027` "Package go-skynet/go-llama.cpp / gotzmann/llama.go / hybridgroup/yzma" (source: ecosystem §Bindings)
- `lb-0028` "Package SciSharp/LLamaSharp (.NET)" (source: ecosystem §Bindings)
- `lb-0029` "Package Cypheros-de/Delphi11LlamaCppBindings" (source: ecosystem §Bindings)
- `lb-0030` "Package mgonzs13/llama_ros (ROS 2)" (source: ecosystem §Bindings)
- `lb-0031` "Package hiyouga/LlamaFactory UI" (source: ecosystem §Frontend)
- `lb-0032` "Package mostlygeek/llama-swap orchestration" (source: ecosystem §Frontend)
- `lb-0033` "Package intentee/paddler orchestration" (source: ecosystem §Frontend)
- `lb-0034` "Package containers/ramalama OCI runtime" (source: ecosystem §Frontend)
- `lb-0035` "Package onicai/llama_cpp_canister (Wasm)" (source: ecosystem §Frontend)
- `lb-0036` "Package Lychee-Technology/llama-cpp-for-strix-halo with TTM unlock" (source: ecosystem §Hardware)
- `lb-0037` "Package GetNyrex/strix-halo-guide documentation automation" (source: ecosystem §Hardware)

**phase/meta** (component/docs):
- `lb-0090` "Update umbrella README with tracking pointer to seed file" (source: design §1)
- `lb-0091` "Add seed-issues.sh runbook to docs/superpowers/runbooks/" (source: design §13)

- [ ] **Step 4: Write the heretek-manager seed template**

`templates/seeds/heretek-manager.yaml.j2` — covering phases 2, 3, and the manager-side meta items. Convention: `hm-####` IDs.

**phase/2-cli-runtime** (component/auditor except where noted):
- `hm-0001` "Bootstrap node CLI with bin/heretek.js entry point" (source: design §3.1)
- `hm-0002` "Implement nvidia-smi parser" (source: design §3.2, component/auditor)
- `hm-0003` "Implement rocminfo parser + /proc/cmdline TTM check" (source: design §3.2, component/auditor)
- `hm-0004` "Implement vulkaninfo parser with RADV detection" (source: design §3.2, component/auditor)
- `hm-0005` "Implement hardware recommendation engine rules" (source: design §3.2, component/auditor, depends_on: [hm-0002, hm-0003, hm-0004])
- `hm-0006` "Implement package downloader + SHA-256 verifier" (source: design §3.1, component/manager, depends_on: [hm-0001])
- `hm-0007` "Implement atomic symlink swap under ~/.heretek/bin/" (source: design §3.3, component/symlink, depends_on: [hm-0006])
- `hm-0008` "Implement /api/hardware endpoint" (source: design §4.1, component/api, depends_on: [hm-0005])
- `hm-0009` "Implement /api/registry endpoint with manifest fetch + retries" (source: design §4.1, component/api, depends_on: [hm-0006])
- `hm-0010` "Implement /api/installed endpoint reading ~/.heretek/store/" (source: design §4.1, component/api, depends_on: [hm-0007])

**phase/3-webui** (component/webui):
- `hm-0020` "Scaffold Express server on port 9048" (source: design §4)
- `hm-0021` "Build hardware-profile detected panel" (source: design §4, depends_on: [hm-0008, hm-0020])
- `hm-0022` "Build recommended-for-your-system banner" (source: design §4, depends_on: [hm-0021])
- `hm-0023` "Build installed-packages side-by-side list with active marker" (source: design §4, depends_on: [hm-0010])
- `hm-0024` "Implement /api/install endpoint (download + verify + extract)" (source: design §4.1, component/api, depends_on: [hm-0006])
- `hm-0025` "Implement /api/activate endpoint (atomic symlink)" (source: design §4.1, component/symlink, depends_on: [hm-0024, hm-0007])
- `hm-0026` "Add TTM warnings + actionable alert UI" (source: design §3.2)
- `hm-0027` "Add install/activate/restart hooks for WebUI buttons" (source: design §4, depends_on: [hm-0024, hm-0025])

**phase/2-cli-runtime additional** (component/manager):
- `hm-0011` "Implement CLI global flag parsing (--verbose, --json-output, --no-sandbox)" (source: design §3.1, depends_on: [hm-0001])
- `hm-0012` "Add structured logging for hardware audit + install flow" (source: design §3.1, depends_on: [hm-0005])
- `hm-0013` "Implement version pinning + rollback via symlink swap" (source: design §3.3, component/symlink, depends_on: [hm-0007])

**phase/meta** (component/docs):
- `hm-0090` "Update umbrella README with tracking pointer to seed file" (source: design §1)
- `hm-0091` "Add seed-issues.sh runbook to docs/superpowers/runbooks/" (source: design §13)
- `hm-0092` "Add e2e smoke test for the install/activate flow" (source: design §4.1)
- `hm-0093` "Document CLI flag reference in heretek-manager README" (source: design §3.1)

- [ ] **Step 5: Extend the renderer**

Append to `scripts/lib/render_seed.py`:

```python
_REPO_SEED_SLUGS = ("llama-builds", "heretek-manager")


def render_repo_seed(slug: str) -> dict[str, str]:
    """Render the per-repo seed YAML for the given slug."""
    if slug not in _REPO_SEED_SLUGS:
        raise ValueError(f"unknown repo slug: {slug!r}; expected one of {_REPO_SEED_SLUGS}")
    rendered = _env().get_template(f"{slug}.yaml.j2").render()
    return {f"seeds/{slug}.yaml": rendered}
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `pytest tests/test_render_seed.py -v`
Expected: 5 passed (2 from Task 2 + 3 new).

- [ ] **Step 7: Verify the generated seed validates against the contract**

Run:
```bash
python -m scripts.lib.render_seed render_llama-builds   # via the CLI below
# OR, in a Python REPL:
python -c "from scripts.lib import render_seed; from scripts.lib.seed_loader import load_seed; import tempfile, os; \
t = tempfile.NamedTemporaryFile('w', suffix='.yaml', delete=False); \
t.write(render_seed.render_repo_seed('llama-builds')['seeds/llama-builds.yaml']); t.close(); \
print(load_seed(t.name).get('issues', []) and 'OK')"
```

Expected: prints `OK`. If it raises `SeedValidationError`, list the failing id and fix the .j2 template.

- [ ] **Step 8: Commit**

```bash
git add templates/seeds/llama-builds.yaml.j2 templates/seeds/heretek-manager.yaml.j2 scripts/lib/render_seed.py tests/test_render_seed.py
git commit -m "feat(seed): render per-repo seed backlogs from Jinja templates"
```

---

## Task 4: seed-issues.sh.j2 + render_seed_issues_script()

**Files:**
- Create: `templates/seeds/seed-issues.sh.j2` (Jinja source)
- Modify: `scripts/lib/render_seed.py` (add renderer)
- Modify: `tests/test_render_seed.py` (add 1 test)

**Interfaces:**
- Consumes: `org`, `repo` (e.g. `"Heretek-AI"`, `"llama-builds"`).
- Produces: `scripts.lib.render_seed.render_seed_issues_script(org: str, repo: str, slug: str) -> dict[str, str]` — returns `{"scripts/seed-issues.sh": "<rendered bash>"}`.
- The emitted script must be self-contained: `#!/usr/bin/env bash`, `set -euo pipefail`, `getopt` for arg parsing, defaults `--repo` to `{{org}}/{{repo}}`, defaults `--seed-url` to `https://raw.githubusercontent.com/{{org}}/monorepo-manager/main/seeds/<slug>.yaml`. Body template lives in the .j2 (Task 7 fills in the body).

- [ ] **Step 1: Write the failing test**

Append to `tests/test_render_seed.py`:

```python
def test_render_seed_issues_script_is_a_bash_script_with_correct_defaults():
    files = render_seed.render_seed_issues_script(
        org="Heretek-AI", repo="llama-builds", slug="llama-builds"
    )
    assert "scripts/seed-issues.sh" in files
    text = files["scripts/seed-issues.sh"]
    assert text.startswith("#!/usr/bin/env bash")
    assert "set -euo pipefail" in text
    assert "Heretek-AI/llama-builds" in text
    assert "seed-issues.sh" in text
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_render_seed.py::test_render_seed_issues_script_is_a_bash_script_with_correct_defaults -v`
Expected: FAIL with `AttributeError: module 'scripts.lib.render_seed' has no attribute 'render_seed_issues_script'`.

- [ ] **Step 3: Write the skeleton template**

`templates/seeds/seed-issues.sh.j2` — skeleton with placeholders. The full implementation is in Task 7; here we just need the rendered file to have correct defaults so the renderer is solid.

```bash
#!/usr/bin/env bash
# Generated by scripts/lib/render_seed.py — do not edit by hand.
# Edit templates/seeds/seed-issues.sh.j2 instead.
#
# Mirrors the canonical seed in https://github.com/{{ org }}/monorepo-manager
# into the GitHub Issues of {{ org }}/{{ repo }}.
set -euo pipefail

ORG="{{ org }}"
REPO="{{ repo }}"
SLUG="{{ slug }}"
SEED_URL_DEFAULT="https://raw.githubusercontent.com/${ORG}/monorepo-manager/main/seeds/${SLUG}.yaml"
SEED_FILE_DEFAULT=""
CACHE_DIR="${HOME}/.cache/heretek-seed"
CACHE_FILE="${CACHE_DIR}/${SLUG}.json"

# --- preflight (filled in Task 7) ---
# --- label sync (filled in Task 7) ---
# --- issue discovery (filled in Task 7) ---
# --- diff + create/update (filled in Task 7) ---
# --- summary (filled in Task 7) ---
```

- [ ] **Step 4: Extend the renderer**

Append to `scripts/lib/render_seed.py`:

```python
def render_seed_issues_script(org: str, repo: str, slug: str) -> dict[str, str]:
    """Render the per-child copy of scripts/seed-issues.sh."""
    if slug not in _REPO_SEED_SLUGS:
        raise ValueError(f"unknown repo slug: {slug!r}")
    text = _env().get_template("seed-issues.sh.j2").render(
        org=org, repo=repo, slug=slug,
    )
    return {"scripts/seed-issues.sh": text}
```

- [ ] **Step 5: Run test to verify it passes**

Run: `pytest tests/test_render_seed.py -v`
Expected: 6 passed.

- [ ] **Step 6: Commit**

```bash
git add templates/seeds/seed-issues.sh.j2 scripts/lib/render_seed.py tests/test_render_seed.py
git commit -m "feat(seed): render seed-issues.sh skeleton from Jinja template"
```

---

## Task 5: AGENTS.md template — add seed URL Pointer block bullet

**Files:**
- Modify: `templates/AGENTS.md.j2` (add `seed_url` field)
- Modify: `templates/CLAUDE.md.j2` (no change needed — only AGENTS.md Pointer block)
- Modify: `scripts/lib/render_agents.py` (accept and render `seed_url`)
- Modify: `scripts/lib/cli.py` (compute and pass `seed_url`)
- Modify: `tests/test_render_agents.py` (add 1 test)

**Interfaces:**
- Consumes: an optional `seed_url` keyword in the `render_agents()` kwargs dict.
- Produces: AGENTS.md Pointer block gains one bullet `- Backlog seed: <seed_url>` when `seed_url` is provided.

- [ ] **Step 1: Read the existing renderer and template**

Run: `Read /home/john/Projects/llama-manager/scripts/lib/render_agents.py` and `Read /home/john/Projects/llama-manager/templates/AGENTS.md.j2`. Confirm the Pointer block section is the `## Pointer block` heading and the existing bullets.

- [ ] **Step 2: Write the failing test**

Append to `tests/test_render_agents.py`:

```python
def test_render_agents_includes_seed_url_bullet_when_provided():
    files = render_agents.render_agents(
        {
            "name": "llama-builds",
            "stack": "python",
            "language": "Python 3.11+",
            "package_manager": "pip, setuptools",
            "os_arch": "Linux x86_64",
            "project_summary": "CI/CD registry.",
            "build_cmd": "python -m build",
            "test_cmd": "pytest",
            "lint_cmd": "ruff check .",
            "run_cmd": "python -m heretek_builds --help",
            "sonar_key": "Heretek-AI_llama-builds",
            "project_url": "https://github.com/orgs/Heretek-AI/projects/1",
            "super_linter_config_path": ".github/linters/",
            "seed_url": "https://github.com/Heretek-AI/monorepo-manager/blob/main/seeds/llama-builds.yaml",
        }
    )
    agents = files["AGENTS.md"]
    assert "Backlog seed: https://github.com/Heretek-AI/monorepo-manager/blob/main/seeds/llama-builds.yaml" in agents


def test_render_agents_omits_seed_url_bullet_when_not_provided():
    files = render_agents.render_agents(
        {
            "name": "monorepo-manager",
            "stack": "python",
            "language": "Python 3.11+",
            "package_manager": "pip, setuptools",
            "os_arch": "Linux x86_64",
            "project_summary": "Umbrella.",
            "build_cmd": "pip install -e .[dev]",
            "test_cmd": "pytest",
            "lint_cmd": "ruff check .",
            "run_cmd": "scripts/init-harness.sh",
            "sonar_key": "Heretek-AI_monorepo-manager",
            "project_url": "",
            "super_linter_config_path": ".github/linters/",
            # no seed_url
        }
    )
    assert "Backlog seed:" not in files["AGENTS.md"]
```

- [ ] **Step 3: Run test to verify it fails**

Run: `pytest tests/test_render_agents.py -v -k seed_url`
Expected: FAIL — `KeyError` on `seed_url` (or the bullet is missing).

- [ ] **Step 4: Modify the template**

In `templates/AGENTS.md.j2`, replace the `## Pointer block` section with:

```markdown
## Pointer block
- GitHub Project: {{ project_url }}
- SonarCloud project: https://sonarcloud.io/project/overview?id={{ sonar_key }}
- Super-linter config: {{ super_linter_config_path }}
- Skills index: `.claude/skills/manifest.json`
- Issue templates: `.github/ISSUE_TEMPLATE/`
- Spec doc: `docs/superpowers/specs/`
{% if seed_url %}- Backlog seed: {{ seed_url }}
{% endif %}
```

Note the trailing space after `seed_url }}` is required by some Markdown renderers; if the pre-commit hook `fix end of files` complains about the trailing newline inside the conditional, adjust the Jinja block to leave a blank line ended with a newline.

- [ ] **Step 5: Modify the renderer**

In `scripts/lib/render_agents.py`, the `render_agents(kwargs: dict)` signature already accepts arbitrary kwargs. Add `seed_url=kwargs.get("seed_url", "")` to the Jinja context dict that it passes to the template. (Read the existing function first to see exactly where to add it.)

- [ ] **Step 6: Modify the CLI**

In `scripts/lib/cli.py`, inside `_bundle()`, compute the seed URL the same way for both stacks (Python and Node):

```python
seed_url = f"https://github.com/{org}/monorepo-manager/blob/main/seeds/{name}.yaml"
```

Add it to the kwarg dict passed to `render_agents.render_agents({...})`. The `name` is the repo slug (`llama-builds` or `heretek-manager`), which matches the seed filename.

- [ ] **Step 7: Run tests**

Run: `pytest tests/test_render_agents.py -v`
Expected: 1 pre-existing test + 2 new tests pass. If a pre-existing test fails because of the new bullet, update the expected fixture — but the existing reference installs in `reference/{llama-builds,heretek-manager}-install/AGENTS.md` will get regenerated by Task 8, so the existing test fixture (if any) should be updated to match the new bullet.

- [ ] **Step 8: Commit**

```bash
git add templates/AGENTS.md.j2 scripts/lib/render_agents.py scripts/lib/cli.py tests/test_render_agents.py
git commit -m "feat(agents): add Backlog seed bullet to AGENTS.md Pointer block"
```

---

## Task 6: Wire render_seed into init-harness.sh + extend contract_hash

**Files:**
- Modify: `scripts/lib/cli.py` (call `render_seed` in `_bundle()`)
- Modify: `scripts/lib/contract_hash.py` (add `compute_seeds_hash`)
- Modify: `tests/test_contract_hash.py` (add 2 tests)

**Interfaces:**
- Produces: `scripts.lib.contract_hash.compute_seeds_hash() -> str` — returns a 16-char hex SHA-256 prefix over the three `seeds/*.yaml` files (concatenated in a sorted order).
- Consumes: `scripts.lib.render_seed.render_labels() + render_repo_seed(slug) + render_seed_issues_script(org, repo, slug)` — called once per `_bundle()` invocation.

- [ ] **Step 1: Read the existing test file**

Run: `Read /home/john/Projects/llama-manager/tests/test_contract_hash.py`.

- [ ] **Step 2: Write the failing tests**

Append to `tests/test_contract_hash.py`:

```python
"""Tests for the contract hash, including the new seeds hash slot."""

from __future__ import annotations

from scripts.lib import contract_hash


def test_compute_seeds_hash_returns_16_char_hex():
    digest = contract_hash.compute_seeds_hash()
    assert isinstance(digest, str)
    assert len(digest) == 16
    assert all(c in "0123456789abcdef" for c in digest)


def test_compute_seeds_hash_is_stable_for_current_state():
    a = contract_hash.compute_seeds_hash()
    b = contract_hash.compute_seeds_hash()
    assert a == b
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `pytest tests/test_contract_hash.py -v`
Expected: FAIL with `AttributeError: module 'scripts.lib.contract_hash' has no attribute 'compute_seeds_hash'`.

- [ ] **Step 4: Implement `compute_seeds_hash`**

Append to `scripts/lib/contract_hash.py`:

```python
def compute_seeds_hash() -> str:
    """Return a 16-char hex SHA-256 prefix over the three seeds/*.yaml files.

    The hash is computed over the on-disk rendered files (the canonical
    source). Ordering is alphabetical by filename for determinism.
    """
    seeds_dir = Path(__file__).parents[2] / "seeds"
    files = sorted(seeds_dir.glob("*.yaml"))
    h = hashlib.sha256()
    for path in files:
        h.update(path.name.encode("utf-8"))
        h.update(b"\0")
        h.update(path.read_bytes())
        h.update(b"\0")
    return h.hexdigest()[:16]
```

Add `from pathlib import Path` (already imported as `pathlib`) — change `pathlib` to `Path` if needed for the new function, or import `from pathlib import Path` at the top.

- [ ] **Step 5: Render the seeds into the working directory**

The tests above assume `seeds/*.yaml` exists on disk. Run:

```bash
python -c "from scripts.lib import render_seed; import os; \
os.makedirs('seeds', exist_ok=True); \
open('seeds/labels.yaml','w').write(render_seed.render_labels()['seeds/labels.yaml']); \
open('seeds/llama-builds.yaml','w').write(render_seed.render_repo_seed('llama-builds')['seeds/llama-builds.yaml']); \
open('seeds/heretek-manager.yaml','w').write(render_seed.render_repo_seed('heretek-manager')['seeds/heretek-manager.yaml']); \
print('seeds rendered')"
```

Expected: prints `seeds rendered`. If `seeds/` already exists as a tracked dir, this will overwrite. Since `seeds/` is checked in (per Task 3), this is idempotent.

- [ ] **Step 6: Run tests to verify they pass**

Run: `pytest tests/test_contract_hash.py -v`
Expected: 2 new tests pass (plus any pre-existing tests).

- [ ] **Step 7: Wire `render_seed` into `cli.py`**

In `scripts/lib/cli.py`, add `render_seed` to the imports:

```python
from scripts.lib import (
    render_agents,
    render_ci,
    render_configs,
    render_hooks,
    render_mcp,
    render_seed,
    render_settings,
    render_skills,
    render_tracking,
)
```

Compute the seed URL once:

```python
seed_url = f"https://github.com/{org}/monorepo-manager/blob/main/seeds/{name}.yaml"
```

Pass it to `render_agents.render_agents({"seed_url": seed_url, ...})` (Task 5 already wired the kwarg).

After the existing `render_tracking.render_contributing(...)` call, add:

```python
files.update(render_seed.render_labels())
files.update(render_seed.render_repo_seed(name))
files.update(render_seed.render_seed_issues_script(org=org, repo=name, slug=name))
```

- [ ] **Step 8: Run the full test suite**

Run: `pytest tests/ -v`
Expected: all existing tests + 6 new tests + 2 new tests + 2 new tests + 1 new test pass. If any existing test in `test_render_agents` fails because of the new Pointer block bullet, update its expected fixture to include the new bullet (the existing reference installs will be regenerated by Task 8).

- [ ] **Step 9: Commit**

```bash
git add scripts/lib/cli.py scripts/lib/contract_hash.py tests/test_contract_hash.py seeds/labels.yaml seeds/llama-builds.yaml seeds/heretek-manager.yaml
git commit -m "feat(seed): wire render_seed into init-harness.sh and add seeds hash"
```

---

## Task 7: Implement seed-issues.sh (6-step flow) + sandbox tests

**Files:**
- Create: `tests/test_seed_issues_script.py` (the implementation gets filled in here, then promoted back to the .j2 template at the end)
- Modify: `templates/seeds/seed-issues.sh.j2` (replace skeleton with the full implementation)
- Run: `python -m scripts.lib.render_seed render_seed_issues_script` to refresh the generated copy

**Interfaces:**
- Produces: a working `scripts/seed-issues.sh` that implements the 6-step flow from spec §9.

- [ ] **Step 1: Read the existing sandbox tests for inspiration**

Run: `Read /home/john/Projects/llama-manager/tests/test_init_harness.py` to see how the umbrella sandboxes subprocess testing.

- [ ] **Step 2: Write the failing sandbox tests**

`tests/test_seed_issues_script.py`:

```python
"""Sandbox tests for scripts/seed-issues.sh — no live GitHub API calls."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).parents[1]
SEED_ISSUES = ROOT / "scripts" / "seed-issues.sh"


def _run(*args: str, env: dict | None = None, cwd: Path | None = None) -> subprocess.CompletedProcess:
    return subprocess.run(
        [str(SEED_ISSUES), *args],
        capture_output=True, text=True,
        env={**os.environ, **(env or {})},
        cwd=cwd or ROOT,
    )


def test_seed_issues_sh_exists_and_is_executable():
    assert SEED_ISSUES.is_file()
    import stat
    mode = SEED_ISSUES.stat().st_mode
    assert mode & stat.S_IXUSR, "scripts/seed-issues.sh must be executable"


def test_seed_issues_sh_help_exits_zero():
    result = _run("--help")
    assert result.returncode == 0
    # gh auth is not satisfied in CI → we only assert --help works on its own
    # (the script should print usage and exit 0 before any gh call).


def test_seed_issues_sh_dry_run_exits_nonzero_without_seed():
    """With no --seed-file and no network, --dry-run should fail fast."""
    result = _run("--repo", "Heretek-AI/llama-builds", "--dry-run",
                  env={"GH_AUTH_DISABLED": "1"})
    # If the script tries gh auth before seed fetch, we'd see a different code.
    # The contract: missing seed is a precondition failure.
    assert result.returncode != 0
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `pytest tests/test_seed_issues_script.py -v`
Expected: FAIL on `test_seed_issues_sh_exists_and_is_executable` because the script is the skeleton from Task 4 (no implementation yet).

- [ ] **Step 4: Implement the full 6-step flow in the .j2 template**

Replace `templates/seeds/seed-issues.sh.j2` with the full implementation. The template fills `{{ org }}`, `{{ repo }}`, `{{ slug }}`; everything else is static.

```bash
#!/usr/bin/env bash
# Generated by scripts/lib/render_seed.py — do not edit by hand.
# Edit templates/seeds/seed-issues.sh.j2 instead.
#
# Mirrors the canonical seed in https://github.com/{{ org }}/monorepo-manager
# into the GitHub Issues of {{ org }}/{{ repo }}.
set -euo pipefail

ORG_DEFAULT="{{ org }}"
REPO_DEFAULT="{{ repo }}"
SLUG="{{ slug }}"
SEED_URL_DEFAULT="https://raw.githubusercontent.com/${ORG_DEFAULT}/monorepo-manager/main/seeds/${SLUG}.yaml"
SEED_FILE_DEFAULT=""
CACHE_DIR="${HOME}/.cache/heretek-seed"
CACHE_FILE="${CACHE_DIR}/${SLUG}.json"

usage() {
  cat <<EOF
Usage: seed-issues.sh --repo OWNER/REPO [--seed-url URL | --seed-file PATH]
                      [--id ID] [--dry-run] [--only-labels] [--prune-closed]
EOF
}

REPO="${ORG_DEFAULT}/${REPO_DEFAULT}"
SEED_URL="${SEED_URL_DEFAULT}"
SEED_FILE="${SEED_FILE_DEFAULT}"
ONLY_ID=""
DRY_RUN="no"
ONLY_LABELS="no"
PRUNE_CLOSED="no"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --repo) REPO="$2"; shift 2 ;;
    --seed-url) SEED_URL="$2"; shift 2 ;;
    --seed-file) SEED_FILE="$2"; shift 2 ;;
    --id) ONLY_ID="$2"; shift 2 ;;
    --dry-run) DRY_RUN="yes"; shift ;;
    --only-labels) ONLY_LABELS="yes"; shift ;;
    --prune-closed) PRUNE_CLOSED="yes"; shift ;;
    --help|-h) usage; exit 0 ;;
    *) echo "unknown arg: $1" >&2; usage; exit 2 ;;
  esac
done

# --- step 1: preflight ---
if ! command -v gh >/dev/null 2>&1; then
  echo "gh CLI not found in PATH" >&2
  exit 3
fi
if ! gh auth status >/dev/null 2>&1; then
  echo "gh is not authenticated; run: gh auth login" >&2
  exit 4
fi

# --- step 2: fetch the seed ---
mkdir -p "${CACHE_DIR}"
if [[ -n "${SEED_FILE}" ]]; then
  SEED_PATH="${SEED_FILE}"
else
  SEED_PATH="${CACHE_DIR}/${SLUG}.seed.yaml"
  curl -fsSL --retry 3 --retry-delay 5 -o "${SEED_PATH}" "${SEED_URL}" || {
    echo "failed to fetch seed from ${SEED_URL}" >&2
    exit 5
  }
fi

# validate the seed
python -m scripts.lib.seed_loader validate "${SEED_PATH}" || {
  echo "seed validation failed; aborting before any gh call" >&2
  exit 6
}

# --- step 2b: sync labels ---
mapfile -t LABEL_NAMES < <(python -c "
import yaml
with open('${SEED_PATH}') as f: s = yaml.safe_load(f)
labels = {(l['name'], l['color'], l['description']) for l in s.get('labels', [])}
")
declare -A SEEN
for entry in "${LABEL_NAMES[@]}"; do
  name="${entry%%$'\t'*}"; rest="${entry#*$'\t'}"
  color="${rest%%$'\t'*}"; desc="${rest#*$'\t'}"
  SEEN["${name}"]=1
  if [[ "${DRY_RUN}" == "yes" ]]; then
    echo "would: gh label create --force ${name} --color ${color} --description ${desc}"
  else
    gh label create "${name}" --color "${color}" --description "${desc}" --force >/dev/null
  fi
done

# --- step 3: discover + step 4: diff + create/update ---
python - <<PYEOF || exit 7
import json, os, re, subprocess, sys, hashlib
from pathlib import Path

seed_path = Path("${SEED_PATH}")
cache_path = Path("${CACHE_FILE}")
cache_path.parent.mkdir(parents=True, exist_ok=True)
cache = json.loads(cache_path.read_text()) if cache_path.exists() else {}
state = cache.get("by_id", {})

with open(seed_path) as f:
    import yaml
    seed = yaml.safe_load(f)

repo = "${REPO}"
slug = "${SLUG}"
only_id = "${ONLY_ID}"
dry_run = "${DRY_RUN}" == "yes"
only_labels = "${ONLY_LABELS}" == "yes"
prune_closed = "${PRUNE_CLOSED}" == "yes"

ids_to_process = [i for i in seed["issues"] if not only_id or i["id"] == only_id]
if only_labels:
    print("only_labels requested; skipping issue sync")
    sys.exit(0)

created = updated = skipped = failed = 0

def run(cmd, **kw):
    if dry_run:
        print(f"would: {' '.join(cmd)}")
        return subprocess.CompletedProcess(cmd, 0, "", "")
    return subprocess.run(cmd, capture_output=True, text=True, **kw)

def body_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]

def emit_body(issue: dict) -> str:
    from scripts.lib.seed_loader import emit_body_markdown
    issue = dict(issue)
    issue["_repo"] = repo
    return emit_body_markdown(issue)

# Discover existing issues by seed-id
existing = {}
for issue in ids_to_process:
    id_ = issue["id"]
    result = run(["gh", "issue", "list", "--repo", repo, "--state", "all",
                  "--json", "number,body,state,labels"])
    if result.returncode != 0:
        print(f"gh issue list failed for {id_}: {result.stderr}", file=sys.stderr)
        sys.exit(7)
    for issue_json in json.loads(result.stdout):
        body = issue_json.get("body", "") or ""
        m = re.search(r"<!-- seed-id:\s*([a-z]{2}-[0-9]{4})\s*-->", body)
        if m and m.group(1) == id_:
            existing[id_] = issue_json
            break

for issue in ids_to_process:
    id_ = issue["id"]
    body = emit_body(issue)
    bh = body_hash(body)
    phase = issue["phase"]; component = issue["component"]; status = issue["status"]
    title = issue["title"]
    if id_ in existing:
        ei = existing[id_]
        if ei["state"] == "closed" and not prune_closed:
            print(f"skip (closed): {id_}")
            skipped += 1
            continue
        prev_bh = state.get(id_, {}).get("body_hash")
        if prev_bh == bh and ei["state"] == "open":
            print(f"skip (unchanged): {id_}")
            skipped += 1
            continue
        # update
        if ei["state"] != "closed":
            r = run(["gh", "issue", "edit", str(ei["number"]),
                     "--repo", repo, "--body-file", "-"],
                    input=body, text=True)
            if r.returncode != 0:
                failed += 1
                continue
            updated += 1
        else:
            # closed, prune-closed: update body only
            r = run(["gh", "issue", "edit", str(ei["number"]),
                     "--repo", repo, "--body-file", "-"],
                    input=body, text=True)
            if r.returncode != 0:
                failed += 1
                continue
            updated += 1
        state[id_] = {"body_hash": bh, "number": ei["number"]}
    else:
        # create
        r = run(["gh", "issue", "create", "--repo", repo,
                 "--title", title, "--body-file", "-",
                 "--label", phase, "--label", component, "--label", status],
                input=body, text=True)
        if r.returncode != 0:
            print(f"create failed for {id_}: {r.stderr}", file=sys.stderr)
            failed += 1
            continue
        # parse number from "https://github.com/owner/repo/issues/N"
        m = re.search(r"/issues/(\d+)", r.stdout)
        number = int(m.group(1)) if m else None
        state[id_] = {"body_hash": bh, "number": number}
        created += 1

cache_path.write_text(json.dumps({"by_id": state}, indent=2, sort_keys=True))
print(f"created={created} updated={updated} skipped={skipped} failed={failed}")
sys.exit(0 if failed == 0 else 1)
PYEOF
```

Note: the script uses `python -m scripts.lib.seed_loader` to validate the seed and `python -` heredoc for the body emit. The umbrella's `scripts/lib/seed_loader.py` is the source. The rendered child copy of `scripts/seed-issues.sh` references this exact same module; the script must run from inside the child repo, which has been bootstrapped via init-harness.sh and committed with the same local checkout. If the child repo does not have a `scripts/lib/seed_loader.py`, the umbrella is the source of truth and the script must `curl` it from the umbrella too — but for the spec we assume the child bootstraps from the umbrella and inherits the helper.

- [ ] **Step 5: Regenerate the script**

Run:
```bash
python -c "from scripts.lib import render_seed; open('scripts/seed-issues.sh', 'w').write(render_seed.render_seed_issues_script('Heretek-AI', 'llama-builds', 'llama-builds')['scripts/seed-issues.sh']); print('regenerated')"
chmod +x scripts/seed-issues.sh
```

Expected: prints `regenerated`. The script is now executable.

- [ ] **Step 6: Run sandbox tests**

Run: `pytest tests/test_seed_issues_script.py -v`
Expected: 3 tests pass (the script exists, is executable, `--help` works, `--dry-run` with no seed fails fast).

- [ ] **Step 7: Commit**

```bash
git add templates/seeds/seed-issues.sh.j2 scripts/seed-issues.sh tests/test_seed_issues_script.py
git commit -m "feat(seed): implement seed-issues.sh 6-step flow with sandbox tests"
```

---

## Task 8: Regenerate reference installs + verify umbrella pipeline

**Files:** (regenerated by `init-harness.sh --generate`)
- `reference/llama-builds-install/` (AGENTS.md Pointer block, .github/labels/labels.yaml, scripts/seed-issues.sh)
- `reference/heretek-manager-install/` (same)

- [ ] **Step 1: Run init-harness.sh for both reference installs**

Run:
```bash
scripts/init-harness.sh --target reference/llama-builds-install --name llama-builds --stack python --project-id 1 --force
scripts/init-harness.sh --target reference/heretek-manager-install --name heretek-manager --stack node --project-id 2 --force
```

Expected: each exits 0 with no diff against the existing tracked files (the existing reference installs ARE the source of truth for what the harness emits; updating them to include the new files is the goal).

- [ ] **Step 2: Verify the new files landed**

Run:
```bash
ls reference/llama-builds-install/.github/labels/labels.yaml
ls reference/llama-builds-install/scripts/seed-issues.sh
grep -F "Backlog seed:" reference/llama-builds-install/AGENTS.md
grep -F "Backlog seed:" reference/heretek-manager-install/AGENTS.md
```

Expected: all four commands succeed with output. The grep should show:
- `reference/llama-builds-install/AGENTS.md`: `- Backlog seed: https://github.com/Heretek-AI/monorepo-manager/blob/main/seeds/llama-builds.yaml`
- `reference/heretek-manager-install/AGENTS.md`: `- Backlog seed: https://github.com/Heretek-AI/monorepo-manager/blob/main/seeds/heretek-manager.yaml`

- [ ] **Step 3: Verify the labels.yaml copies validate**

Run:
```bash
python -c "import yaml; print(list(yaml.safe_load(open('reference/llama-builds-install/.github/labels/labels.yaml')).keys()))"
```

Expected: `['schema_version', 'labels']`.

- [ ] **Step 4: Run the full test suite**

Run: `pytest tests/ -v`
Expected: all tests pass (existing + ~20 new).

- [ ] **Step 5: Run lint**

Run: `ruff check .`
Expected: clean.

- [ ] **Step 6: Commit**

```bash
git add reference/llama-builds-install/ reference/heretek-manager-install/
git commit -m "chore(reference): regenerate reference installs with tracking layer"
```

---

## Task 9: Migration runbook + final commit

**Files:**
- Create: `docs/superpowers/runbooks/seed-issues.md`

- [ ] **Step 1: Write the runbook**

`docs/superpowers/runbooks/seed-issues.md`:

```markdown
# seed-issues.sh — first-run and reseed runbook

This runbook is the human-side companion to `scripts/seed-issues.sh`. It walks a human with `gh` auth through the one-time setup and the daily/weekly reseed cadence.

## Prerequisites

- `gh` CLI ≥ 2.40 on your `$PATH`.
- `gh auth login` completed for the `Heretek-AI` org.
- `yq` and `jq` installed.
- Read access to the relevant seed file in `https://github.com/Heretek-AI/monorepo-manager`.

## First-time setup (one human, ~10 minutes per repo)

1. Create one GitHub Project per child repo (manual UI step, Projects #1 and #2).
2. Note the project node ID: open the project → ⋯ menu → Settings → copy the ID (format `PVT_xxxxx`).
3. In the umbrella repo, edit `seeds/llama-builds.yaml` and `seeds/heretek-manager.yaml`, replacing the `project_id: ""` field with the new ID. Commit and push.
4. From inside the child repo, run `scripts/seed-issues.sh --only-labels` to create the 20 labels.
5. Run `scripts/seed-issues.sh` to file the ≈30 issues. Expect `created=30 updated=0 skipped=0 failed=0`.
6. Configure the two project-board views (By Phase, By Component) per spec §7.
7. Verify by opening one issue in each repo and confirming the body has all five sections and the `seed-id` HTML comment.

## Reseed (when the seed file changes)

After a PR merges that edits `seeds/<repo>.yaml`:

1. Pull the latest umbrella commit in your local clone.
2. From inside the child repo, run `scripts/seed-issues.sh`.
3. Expect `created=0 updated=N skipped=M failed=0` where updated is the number of changed bodies.

## Offline reseed

If the umbrella is unreachable from the runner (e.g. air-gapped CI):

```bash
scripts/seed-issues.sh --seed-file /path/to/local/seeds/llama-builds.yaml
```

The seed file is the same canonical data; the script accepts any local path.

## Rollback

`seed-issues.sh` never deletes or closes issues. To roll back a bad seed run, manually close the affected issues with `gh issue close <number>` and re-run with the previous seed (or edit the seed by hand and re-run).

## Common failure modes

| symptom | cause | fix |
|---|---|---|
| `gh is not authenticated` | `gh auth login` not completed | Run `gh auth login` and retry |
| `failed to fetch seed from <url>` | Network or rate limit | Use `--seed-file /path/to/local.yaml` |
| `seed validation failed` | Seed has a structural error | Run `python -m scripts.lib.seed_loader validate <path>` to see specific failure |
| `create failed for <id>` | Repo permissions | Verify `gh auth status` shows write access to the target repo |
```

- [ ] **Step 2: Verify the runbook renders**

Run: `cat docs/superpowers/runbooks/seed-issues.md | head -20`
Expected: markdown looks correct.

- [ ] **Step 3: Final lint + test**

Run: `pytest tests/ -v && ruff check .`
Expected: all tests pass, ruff clean.

- [ ] **Step 4: Commit**

```bash
git add docs/superpowers/runbooks/seed-issues.md
git commit -m "docs(runbook): add seed-issues.sh first-run + reseed runbook"
```

---

## Acceptance Checklist

- [ ] `seeds/labels.yaml`, `seeds/llama-builds.yaml`, `seeds/heretek-manager.yaml` are checked in and validate against `schemas/seed.schema.json`.
- [ ] `scripts/lib/seed_loader.py` exposes `load_seed`, `validate_issue`, `emit_body_markdown`, and a CLI for `validate` / `emit`.
- [ ] `scripts/lib/render_seed.py` exposes `render_labels`, `render_repo_seed`, `render_seed_issues_script`.
- [ ] `scripts/init-harness.sh --generate` produces the new files in each child repo (verified by Task 8).
- [ ] `scripts/lib/contract_hash.compute_seeds_hash()` returns a 16-char hex digest over the three seeds files.
- [ ] `scripts/seed-issues.sh` is executable, parses `--repo`, `--seed-url`, `--seed-file`, `--id`, `--dry-run`, `--only-labels`, `--prune-closed`, `--help`.
- [ ] `seed-issues.sh --help` exits 0 before any `gh` call.
- [ ] `seed-issues.sh --dry-run` with no seed fails fast.
- [ ] `AGENTS.md` generated for both children contains the `Backlog seed:` bullet.
- [ ] `tests/test_seed_loader.py` (7 tests), `tests/test_render_seed.py` (6 tests), `tests/test_seed_issues_script.py` (3 tests), `tests/test_contract_hash.py` (2 new tests), `tests/test_render_agents.py` (2 new tests) all pass.
- [ ] `docs/superpowers/runbooks/seed-issues.md` exists at the documented path.
- [ ] Spec section coverage: §4 (schema), §5 (body), §6 (labels), §7 (project board), §8 (AGENTS.md), §9 (script lifecycle), §10 (umbrella integration), §11 (testing), §13 (runbook).
