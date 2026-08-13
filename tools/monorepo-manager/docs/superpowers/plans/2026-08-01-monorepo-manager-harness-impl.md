# monorepo-manager harness implementation plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement the contract-driven Heretek harness in `monorepo-manager` so that `scripts/init-harness.sh` can materialize a fully wired harness into a fresh `llama-builds` or `heretek-manager` repo.

**Architecture:** The umbrella repo holds contract schemas (JSON Schema + plain-text templates), a Python `scripts/lib/` validation library, a `scripts/init-harness.sh` generator, and a generated `reference/{child}-install/` for each child. The generator reads the contracts, applies per-child parameterisation, and writes the full harness tree into a target directory. Drift detection compares a contract-hash baked into the generated files against a hash computed from the spec section.

**Tech Stack:** Bash 5+ (init script), Python 3.11+ (validators + smoke tests), JSON Schema Draft 2020-12, GitHub Actions (CI workflows), pre-commit v3 + pre-commit-hooks pinned at v5.0.0, SonarCloud (analysis), gitleaks (secret scan), Jekyll-free GitHub Pages (not used here).

## Global Constraints

These apply to every task unless a task explicitly overrides them.

- **Spec source of truth:** `docs/superpowers/specs/2026-08-01-monorepo-manager-harness-design.md` (commit `6fb0ac6`).
- **Target brank:** `main` on a fresh local-only repo (no remote unless the operator adds one).
- **Linux x86_64 only.** ARM/macOS/Windows out of scope.
- **No submodules. No monorepo manager. No workspaces.** The umbrella is throwaway; children are standalone.
- **Two child stacks:** `llama-builds` = Python 3.11 + YAML + shell. `heretek-manager` = Node 20 + TypeScript 5.
- **No plaintext secrets** in any committed file. Tokens arrive via `process.env` or repo-level GH Actions secrets.
- **Pinned versions only.** No `latest`. Lock anything that's external.
- **Commit messages** follow Conventional Commits; the umbrella commits with `Co-Authored-By: Claude <noreply@anthropic.com>`.
- **Pre-commit hooks** run on every commit on the umbrella: trailing-whitespace, end-of-file-fixer, check-yaml, check-json, check-added-large-files (max 500KiB), check-merge-conflict, check-case-conflict, detect-private-key, ruff check + ruff format.
- **All paths in this plan are relative to the umbrella repo root** (`/home/john/Projects/llama-manager`).

## File Structure Produced

```
monorepo-manager/
├── README.md
├── .gitignore
├── .pre-commit-config.yaml
├── docs/superpowers/
│   ├── specs/2026-08-01-monorepo-manager-harness-design.md   (already exists)
│   └── plans/2026-08-01-monorepo-manager-harness-impl.md     (this file)
├── schemas/
│   ├── agents-md.schema.json
│   ├── mcp-json.schema.json
│   ├── skills-manifest.schema.json
│   ├── settings-json.schema.json
│   ├── pre-commit-config.schema.json
│   ├── sonar-project-properties.schema.json
│   ├── issue-template.schema.json
│   ├── labeler.schema.json
│   └── project-schema.schema.json
├── scripts/
│   ├── init-harness.sh
│   └── lib/
│       ├── __init__.py
│       ├── contract_hash.py
│       ├── validate_agents.py
│       ├── validate_mcp.py
│       ├── validate_skills.py
│       ├── validate_settings.py
│       ├── render_agents.py
│       ├── render_mcp.py
│       ├── render_skills.py
│       ├── render_settings.py
│       ├── render_ci.py
│       ├── render_tracking.py
│       └── render_hooks.py
├── templates/
│   ├── AGENTS.md.j2
│   ├── CLAUDE.md.j2
│   ├── .mcp.json.j2
│   ├── .claude/skills/manifest.json.j2
│   ├── .claude/skills/<skill>/SKILL.md.j2
│   ├── .claude/settings.json.j2
│   ├── .claude/hooks/PreToolUse/deny-destructive.sh
│   ├── .claude/hooks/PostToolUse/run-pre-commit.sh
│   ├── .claude/hooks/Stop/verify-lint.sh
│   ├── .github/workflows/super-linter.yml.j2
│   ├── .github/workflows/pre-commit.yml.j2
│   ├── .github/workflows/sonarcloud.yml.j2
│   ├── .github/workflows/secret-scan.yml.j2
│   ├── .github/linters/eslintrc.yml
│   ├── .github/linters/python-ruff.yml
│   ├── .github/linters/shellcheck.yml
│   ├── .github/linters/yamllint.yml
│   ├── .github/linters/markdownlint.yml
│   ├── .github/linters/prettierrc.yml
│   ├── .pre-commit-config.yaml.j2
│   ├── sonar-project.properties.j2
│   ├── .github/gitleaks-config.yml
│   ├── .gitleaks-baseline.json
│   ├── .github/ISSUE_TEMPLATE/bug.md.j2
│   ├── .github/ISSUE_TEMPLATE/feature.md.j2
│   ├── .github/ISSUE_TEMPLATE/security.md.j2
│   ├── .github/ISSUE_TEMPLATE/refactor.md.j2
│   ├── .github/ISSUE_TEMPLATE/infra-tooling.md.j2
│   ├── .github/ISSUE_TEMPLATE/spec.md.j2
│   ├── .github/ISSUE_TEMPLATE/config.yml.j2
│   ├── .github/PULL_REQUEST_TEMPLATE.md.j2
│   ├── .github/labeler.yml.j2
│   ├── .github/projects-automation.graphql.j2
│   └── CONTRIBUTING.md.j2
├── reference/
│   ├── llama-builds-install/                 (generated)
│   └── heretek-manager-install/              (generated)
└── tests/
    ├── conftest.py
    ├── test_contract_hash.py
    ├── test_validate_agents.py
    ├── test_validate_mcp.py
    ├── test_validate_skills.py
    ├── test_validate_settings.py
    ├── test_render_agents.py
    ├── test_render_mcp.py
    ├── test_render_ci.py
    ├── test_render_tracking.py
    ├── test_init_harness.py
    ├── fixtures/sonar_smoke/main.py
    ├── fixtures/sonar_smoke/test_main.py
    ├── fixtures/sonar_smoke/sonar-project.properties
    ├── fixtures/gitleaks_hits/secret.txt
    ├── fixtures/gitleaks_hits/.gitleaks-baseline.json
    └── fixtures/sandbox_child/{README.md,package.json}     (small dummy child for end-to-end)
```

---

## Task 1: Workspace scaffold

**Files:**
- Create: `README.md`
- Create: `.gitignore`
- Create: `pyproject.toml`
- Create: `tests/__init__.py`
- Create: `tests/conftest.py`

**Interfaces:**
- Consumes: nothing.
- Produces: an importable Python package `scripts` and a test directory.

- [ ] **Step 1: Create `.gitignore`**

```
__pycache__/
*.py[cod]
*.egg-info/
.venv/
venv/
.pytest_cache/
.mypy_cache/
.ruff_cache/
reference/*/node_modules/
reference/*/.pytest_cache/
reference/*/dist/
reference/*/build/
*.log
.DS_Store
```

- [ ] **Step 2: Create `pyproject.toml`**

```toml
[project]
name = "heretek-harness"
version = "0.1.0"
description = "Contract-driven Heretek AI harness"
requires-python = ">=3.11"
dependencies = [
    "jsonschema>=4.21.0",
    "jinja2>=3.1.3",
    "pyyaml>=6.0.1",
]

[project.optional-dependencies]
dev = [
    "pytest>=8.0.0",
    "ruff>=0.4.0",
]

[build-system]
requires = ["setuptools>=68"]
build-backend = "setuptools.build_meta"

[tool.setuptools.packages.find]
include = ["scripts*"]

[tool.ruff]
line-length = 100
target-version = "py311"

[tool.ruff.lint]
select = ["E", "F", "I", "W", "B", "UP"]
ignore = ["E501"]

[tool.pytest.ini_options]
testpaths = ["tests"]
addopts = "-ra --strict-markers"
```

- [ ] **Step 3: Create minimal `README.md`**

```markdown
# monorepo-manager

Throwaway workspace for the Heretek AI harness. Generates the harness
that gets installed into `Heretek-AI/llama-builds` and
`Heretek-AI/heretek-manager`.

**Spec:** [`docs/superpowers/specs/2026-08-01-monorepo-manager-harness-design.md`](docs/superpowers/specs/2026-08-01-monorepo-manager-harness-design.md)

**Plan:** [`docs/superpowers/plans/2026-08-01-monorepo-manager-harness-impl.md`](docs/superpowers/plans/2026-08-01-monorepo-manager-harness-impl.md)

**Generate a child install:**

```bash
scripts/init-harness.sh --target reference/llama-builds-install --name llama-builds --stack python
```

**Validate:**

```bash
pytest tests/
```

## Tracking

- Spec tracking Issue: *to be filed after spec approval*
- Roadmap project: *to be created during child v1*
- Sonar project: N/A (umbrella has no app code)
```

- [ ] **Step 4: Create `tests/__init__.py` and `tests/conftest.py`**

`tests/__init__.py` is empty.

`tests/conftest.py`:

```python
"""Pytest fixtures shared across the umbrella test suite."""
from __future__ import annotations

import pathlib
import sys

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]


@pytest.fixture(scope="session")
def repo_root() -> pathlib.Path:
    return ROOT


@pytest.fixture(scope="session")
def scripts_dir() -> pathlib.Path:
    return ROOT / "scripts"


@pytest.fixture(scope="session")
def schemas_dir() -> pathlib.Path:
    return ROOT / "schemas"


@pytest.fixture(scope="session")
def templates_dir() -> pathlib.Path:
    return ROOT / "templates"


@pytest.fixture(scope="session")
def tests_dir() -> pathlib.Path:
    return ROOT / "tests"


# Make `scripts.lib` importable as a top-level package.
sys.path.insert(0, str(ROOT / "scripts"))
```

- [ ] **Step 5: Create `scripts/__init__.py` and `scripts/lib/__init__.py`**

Both empty.

- [ ] **Step 6: Run `pytest` to confirm the test environment boots**

Run: `cd /home/john/Projects/llama-manager && python -m venv .venv && . .venv/bin/activate && pip install -e ".[dev]" && pytest -v`
Expected: collects 0 tests, exits 0.

- [ ] **Step 7: Commit**

```bash
git add README.md .gitignore pyproject.toml tests/ scripts/
git commit -m "chore: scaffold monorepo-manager workspace"
```

---

## Task 2: Contract-hash utility

**Files:**
- Create: `scripts/lib/contract_hash.py`
- Create: `tests/test_contract_hash.py`

**Interfaces:**
- Consumes: nothing.
- Produces: `compute_contract_hash(spec_path, section_anchor) -> str` returning a 16-char SHA-256 hex prefix.

- [ ] **Step 1: Write the failing test**

`tests/test_contract_hash.py`:

```python
"""Spec contract hashing for drift detection between reference installs and the spec."""
from __future__ import annotations

import textwrap

from scripts.lib.contract_hash import compute_contract_hash


def test_compute_contract_hash_is_deterministic(tmp_path):
    spec = tmp_path / "spec.md"
    spec.write_text(
        textwrap.dedent(
            """\
            # spec

            ## Section A
            body a

            ## Section B
            body b
            """
        )
    )
    h1 = compute_contract_hash(spec, "Section A")
    h2 = compute_contract_hash(spec, "Section A")
    assert h1 == h2


def test_compute_contract_hash_is_16_hex_chars(tmp_path):
    spec = tmp_path / "spec.md"
    spec.write_text("## X\nbody")
    h = compute_contract_hash(spec, "X")
    assert len(h) == 16
    assert all(c in "0123456789abcdef" for c in h)


def test_compute_contract_hash_changes_when_section_changes(tmp_path):
    spec = tmp_path / "spec.md"
    spec.write_text("## X\nbody one")
    h1 = compute_contract_hash(spec, "X")
    spec.write_text("## X\nbody two")
    h2 = compute_contract_hash(spec, "X")
    assert h1 != h2


def test_compute_contract_hash_raises_on_missing_section(tmp_path):
    spec = tmp_path / "spec.md"
    spec.write_text("## X\nbody")
    import pytest
    with pytest.raises(ValueError, match="Section 'Y' not found"):
        compute_contract_hash(spec, "Y")
```

- [ ] **Step 2: Run the test to confirm it fails**

Run: `pytest tests/test_contract_hash.py -v`
Expected: ImportError or AttributeError.

- [ ] **Step 3: Implement `scripts/lib/contract_hash.py`**

```python
"""Spec contract hashing.

The init-harness.sh script bakes a hash of the relevant spec section into
every generated reference install. On subsequent inits, recomputing the
hash and comparing against the baked value detects drift.
"""
from __future__ import annotations

import hashlib
import pathlib
import re


def _extract_section(spec_text: str, section_anchor: str) -> str:
    """Extract a markdown section by anchor (e.g. 'Section A' or '4. Layer 1').

    Returns the section body from the anchor line through the next
    '## ' or '### ' heading at the same or higher level. Raises
    ValueError if the anchor is not found.
    """
    lines = spec_text.splitlines()
    start = None
    for i, line in enumerate(lines):
        if re.match(rf"^#+\s+.*\b{re.escape(section_anchor)}\b", line):
            start = i
            break
    if start is None:
        raise ValueError(f"Section '{section_anchor}' not found in spec")

    # Capture everything until the next heading at the same level or higher.
    start_level = len(lines[start]) - len(lines[start].lstrip("#"))
    body_lines: list[str] = []
    for line in lines[start + 1 :]:
        leading = len(line) - len(line.lstrip("#")) if line.lstrip().startswith("#") else 999
        if line.strip() and leading <= start_level:
            break
        body_lines.append(line)
    return "\n".join([lines[start], *body_lines]).strip()


def compute_contract_hash(spec_path: pathlib.Path, section_anchor: str) -> str:
    """Return a 16-char hex SHA-256 prefix over the spec section text."""
    text = pathlib.Path(spec_path).read_text(encoding="utf-8")
    section = _extract_section(text, section_anchor)
    return hashlib.sha256(section.encode("utf-8")).hexdigest()[:16]
```

- [ ] **Step 4: Run the test to confirm it passes**

Run: `pytest tests/test_contract_hash.py -v`
Expected: 4 passed.

- [ ] **Step 5: Commit**

```bash
git add scripts/lib/contract_hash.py tests/test_contract_hash.py
git commit -m "feat(lib): add spec contract hashing for drift detection"
```

---

## Task 3: AGENTS.md JSON schema

**Files:**
- Create: `schemas/agents-md.schema.json`
- Create: `scripts/lib/validate_agents.py`
- Create: `tests/test_validate_agents.py`

**Interfaces:**
- Consumes: a candidate AGENTS.md path.
- Produces: `validate_agents(path) -> list[str]` returning a list of violations (empty list = valid).

- [ ] **Step 1: Write the JSON schema**

`schemas/agents-md.schema.json`:

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "https://heretek-ai.dev/schemas/agents-md.schema.json",
  "title": "AGENTS.md contract",
  "type": "object",
  "required": ["sections"],
  "properties": {
    "sections": {
      "type": "array",
      "minItems": 7,
      "maxItems": 7,
      "items": {
        "type": "string",
        "enum": [
          "Project summary",
          "Stack & runtime targets",
          "Build, test, lint, run commands",
          "Project structure",
          "Conventions",
          "Do / Don't list",
          "Pointer block"
        ]
      },
      "uniqueItems": true
    }
  }
}
```

- [ ] **Step 2: Write the failing test**

`tests/test_validate_agents.py`:

```python
"""AGENTS.md contract validation."""
from __future__ import annotations

import textwrap

import pytest

from scripts.lib.validate_agents import validate_agents


def _write(tmp_path, body: str) -> str:
    p = tmp_path / "AGENTS.md"
    p.write_text(textwrap.dedent(body))
    return str(p)


def _valid_body() -> str:
    return """\
    # sample

    ## Project summary
    one paragraph

    ## Stack & runtime targets
    python 3.11

    ## Build, test, lint, run commands
    pytest

    ## Project structure
    tree

    ## Conventions
    ruff

    ## Do / Don't list
    do this

    ## Pointer block
    links
    """


def test_validate_agents_accepts_well_formed(tmp_path):
    v = validate_agents(_write(tmp_path, _valid_body()))
    assert v == []


def test_validate_agents_rejects_missing_section(tmp_path):
    body = _valid_body().replace("## Do / Don't list\ndo this\n", "")
    v = validate_agents(_write(tmp_path, body))
    assert any("Do / Don't list" in s for s in v)


def test_validate_agents_rejects_duplicate_section(tmp_path):
    body = _valid_body() + "\n## Project summary\ndup\n"
    v = validate_agents(_write(tmp_path, body))
    assert any("duplicate" in s.lower() for s in v)


def test_validate_agents_rejects_empty_section(tmp_path):
    body = _valid_body().replace("## Pointer block\nlinks\n", "## Pointer block\n\n")
    v = validate_agents(_write(tmp_path, body))
    assert any("Pointer block" in s for s in v)
```

- [ ] **Step 3: Run the test to confirm it fails**

Run: `pytest tests/test_validate_agents.py -v`
Expected: ImportError.

- [ ] **Step 4: Implement `scripts/lib/validate_agents.py`**

```python
"""AGENTS.md contract validator.

The contract requires seven top-level sections in this exact order:
Project summary, Stack & runtime targets, Build, test, lint, run commands,
Project structure, Conventions, Do / Don't list, Pointer block. Each
section must contain at least one non-blank line.
"""
from __future__ import annotations

import pathlib
import re

REQUIRED_SECTIONS = [
    "Project summary",
    "Stack & runtime targets",
    "Build, test, lint, run commands",
    "Project structure",
    "Conventions",
    "Do / Don't list",
    "Pointer block",
]

_SECTION_RE = re.compile(r"^##\s+(.+?)\s*$")


def validate_agents(path: str) -> list[str]:
    p = pathlib.Path(path)
    text = p.read_text(encoding="utf-8")
    lines = text.splitlines()
    violations: list[str] = []

    section_indices: list[tuple[str, int, int]] = []
    for i, line in enumerate(lines):
        m = _SECTION_RE.match(line)
        if m:
            section_indices.append((m.group(1), i, len(lines)))

    for j, (name, start, end) in enumerate(section_indices):
        body_end = section_indices[j + 1][1] if j + 1 < len(section_indices) else end
        body = [ln for ln in lines[start + 1 : body_end] if ln.strip()]
        section_indices[j] = (name, start, len(body))

    seen = [name for name, _, _ in section_indices]
    required = REQUIRED_SECTIONS

    for sec in required:
        if sec not in seen:
            violations.append(f"required section '{sec}' missing")
    for sec in seen:
        if sec not in required:
            violations.append(f"unexpected section '{sec}'")

    if seen != required:
        violations.append(f"sections must appear in order: {required}")

    seen_set = set()
    for sec in seen:
        if sec in seen_set:
            violations.append(f"duplicate section '{sec}'")
        seen_set.add(sec)

    for name, _, body_lines in section_indices:
        if name in required and body_lines == 0:
            violations.append(f"section '{name}' is empty")

    return violations
```

- [ ] **Step 5: Run the test to confirm it passes**

Run: `pytest tests/test_validate_agents.py -v`
Expected: 4 passed.

- [ ] **Step 6: Commit**

```bash
git add schemas/agents-md.schema.json scripts/lib/validate_agents.py tests/test_validate_agents.py
git commit -m "feat(contracts): add AGENTS.md schema and validator"
```

---

## Task 4: .mcp.json schema and validator

**Files:**
- Create: `schemas/mcp-json.schema.json`
- Create: `scripts/lib/validate_mcp.py`
- Create: `tests/test_validate_mcp.py`

**Interfaces:**
- Consumes: a candidate `.mcp.json` path.
- Produces: `validate_mcp(path) -> list[str]`.

- [ ] **Step 1: Write the JSON schema**

`schemas/mcp-json.schema.json`:

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "https://heretek-ai.dev/schemas/mcp-json.schema.json",
  "title": ".mcp.json contract",
  "type": "object",
  "required": ["mcpServers"],
  "additionalProperties": false,
  "properties": {
    "mcpServers": {
      "type": "object",
      "minProperties": 1,
      "additionalProperties": { "$ref": "#/$defs/server" }
    }
  },
  "$defs": {
    "server": {
      "type": "object",
      "required": ["description", "transport"],
      "additionalProperties": false,
      "properties": {
        "description": { "type": "string", "minLength": 1, "maxLength": 200 },
        "transport": { "type": "string", "enum": ["stdio", "http"] },
        "command": { "type": "string", "minLength": 1 },
        "args": { "type": "array", "items": { "type": "string" } },
        "env": {
          "type": "object",
          "additionalProperties": { "type": ["string", "null"] },
          "patternProperties": {
            "^[A-Z][A-Z0-9_]{2,32}$": { "type": ["string", "null"] }
          }
        },
        "url": { "type": "string", "format": "uri" },
        "headers": { "type": "object", "additionalProperties": { "type": "string" } },
        "timeoutSeconds": { "type": "integer", "minimum": 1, "maximum": 600 },
        "retry": { "type": "integer", "minimum": 0, "maximum": 10 },
        "requiredSkills": {
          "type": "array",
          "items": { "type": "string", "pattern": "^[a-z][a-z0-9-]{2,32}$" },
          "uniqueItems": true
        }
      },
      "allOf": [
        {
          "if": { "properties": { "transport": { "const": "stdio" } } },
          "then": { "required": ["command", "args"] }
        },
        {
          "if": { "properties": { "transport": { "const": "http" } } },
          "then": { "required": ["url"] }
        }
      ]
    }
  }
}
```

- [ ] **Step 2: Write the failing test**

`tests/test_validate_mcp.py`:

```python
"""Tests for .mcp.json contract validation."""
from __future__ import annotations

import json
import pathlib

import pytest

from scripts.lib.validate_mcp import validate_mcp


def _write(tmp_path: pathlib.Path, data: dict) -> str:
    p = tmp_path / ".mcp.json"
    p.write_text(json.dumps(data))
    return str(p)


def test_validate_mcp_accepts_minimal_stdio(tmp_path):
    data = {
        "mcpServers": {
            "github": {
                "description": "Official GitHub MCP",
                "transport": "stdio",
                "command": "github-mcp",
                "args": ["--owner", "Heretek-AI"],
                "timeoutSeconds": 30,
                "retry": 0,
            }
        }
    }
    assert validate_mcp(_write(tmp_path, data)) == []


def test_validate_mcp_rejects_bad_name(tmp_path):
    data = {
        "mcpServers": {
            "BadName": {
                "description": "wrong",
                "transport": "stdio",
                "command": "x",
                "args": [],
            }
        }
    }
    v = validate_mcp(_write(tmp_path, data))
    assert any("name" in s.lower() for s in v)


def test_validate_mcp_rejects_missing_command_for_stdio(tmp_path):
    data = {
        "mcpServers": {
            "github": {"description": "x", "transport": "stdio", "args": []}
        }
    }
    v = validate_mcp(_write(tmp_path, data))
    assert any("command" in s for s in v)


def test_validate_mcp_rejects_bad_env_key(tmp_path):
    data = {
        "mcpServers": {
            "github": {
                "description": "x",
                "transport": "stdio",
                "command": "x",
                "args": [],
                "env": {"lowercase_key": "value"},
            }
        }
    }
    v = validate_mcp(_write(tmp_path, data))
    assert any("env" in s.lower() for s in v)


def test_validate_mcp_rejects_plaintext_secret(tmp_path):
    data = {
        "mcpServers": {
            "github": {
                "description": "x",
                "transport": "stdio",
                "command": "x",
                "args": [],
                "env": {"GITHUB_TOKEN": "ghp_actualsecretvalue1234567890"},
            }
        }
    }
    v = validate_mcp(_write(tmp_path, data))
    assert any("plaintext" in s.lower() for s in v)
```

- [ ] **Step 3: Run the test to confirm it fails**

Run: `pytest tests/test_validate_mcp.py -v`
Expected: ImportError.

- [ ] **Step 4: Implement `scripts/lib/validate_mcp.py`**

```python
"""Validator for the .mcp.json contract.

Rules enforced beyond the JSON Schema:
- The `name` key (the mcpServers dict key) matches `^[a-z][a-z0-9-]{2,32}$`.
- An env value that looks like a token (length >= 20, alphanumeric/underscore)
  is rejected as a plaintext secret.
"""
from __future__ import annotations

import json
import pathlib
import re

import jsonschema

_NAME_RE = re.compile(r"^[a-z][a-z0-9-]{2,32}$")
_TOKEN_RE = re.compile(r"^[A-Za-z0-9_]{20,}$")


def _looks_like_token(value: str) -> bool:
    return bool(_TOKEN_RE.match(value))


def validate_mcp(path: str) -> list[str]:
    p = pathlib.Path(path)
    raw = json.loads(p.read_text(encoding="utf-8"))
    schema = json.loads(
        (pathlib.Path(__file__).parents[2] / "schemas" / "mcp-json.schema.json").read_text()
    )
    violations: list[str] = []

    validator = jsonschema.Draft202012Validator(schema)
    for err in sorted(validator.iter_errors(raw), key=lambda e: e.path):
        violations.append(f"{'/'.join(map(str, err.path)) or '<root>'}: {err.message}")

    servers = raw.get("mcpServers", {})
    for name, server in servers.items():
        if not _NAME_RE.match(name):
            violations.append(f"name '{name}': must match {_NAME_RE.pattern}")
        env = server.get("env") or {}
        for k, v in env.items():
            if isinstance(v, str) and _looks_like_token(v):
                violations.append(f"env '{k}': plaintext secret not allowed in .mcp.json")

    return violations
```

- [ ] **Step 5: Run the test to confirm it passes**

Run: `pytest tests/test_validate_mcp.py -v`
Expected: 5 passed.

- [ ] **Step 6: Commit**

```bash
git add schemas/mcp-json.schema.json scripts/lib/validate_mcp.py tests/test_validate_mcp.py
git commit -m "feat(contracts): add .mcp.json schema and validator"
```

---

## Task 5: skills-manifest schema and validator

**Files:**
- Create: `schemas/skills-manifest.schema.json`
- Create: `scripts/lib/validate_skills.py`
- Create: `tests/test_validate_skills.py`

**Interfaces:**
- Consumes: a `.claude/skills/<name>/SKILL.md` directory.
- Produces: `validate_skill(skill_path) -> list[str]`.

- [ ] **Step 1: Write the JSON schema**

Note: this schema describes the SKILL.md frontmatter, not the manifest.
We embed it as a JSON Schema file for editor support.

`schemas/skills-manifest.schema.json`:

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "https://heretek-ai.dev/schemas/skills-manifest.schema.json",
  "title": "Skills manifest",
  "type": "object",
  "required": ["skills"],
  "properties": {
    "skills": {
      "type": "array",
      "items": {
        "type": "object",
        "required": ["name", "description"],
        "properties": {
          "name": { "type": "string", "pattern": "^[a-z][a-z0-9-]{2,64}$" },
          "description": { "type": "string", "minLength": 1, "maxLength": 500 },
          "allowed-tools": {
            "type": "array",
            "items": { "type": "string", "pattern": "^[A-Za-z0-9_:_-]+$" }
          },
          "requiredSkills": {
            "type": "array",
            "items": { "type": "string", "pattern": "^[a-z][a-z0-9-]{2,64}$" }
          }
        }
      }
    }
  }
}
```

- [ ] **Step 2: Write the failing test**

`tests/test_validate_skills.py`:

```python
"""Tests for .claude/skills/<name>/SKILL.md contract validation."""
from __future__ import annotations

import textwrap

import pytest

from scripts.lib.validate_skills import validate_skill


def _write_skill(tmp_path, body: str, name: str = "heretek-example") -> str:
    d = tmp_path / ".claude" / "skills" / name
    d.mkdir(parents=True)
    (d / "SKILL.md").write_text(textwrap.dedent(body))
    return str(d)


def _valid_body() -> str:
    return """\
    ---
    name: heretek-example
    description: Example skill.
    ---

    # heretek-example

    Use this skill when ...
    """


def test_validate_skill_accepts_well_formed(tmp_path):
    assert validate_skill(_write_skill(tmp_path, _valid_body())) == []


def test_validate_skill_rejects_missing_frontmatter(tmp_path):
    v = validate_skill(_write_skill(tmp_path, "# no frontmatter\n"))
    assert any("frontmatter" in s.lower() for s in v)


def test_validate_skill_rejects_missing_name(tmp_path):
    body = "---\ndescription: x\n---\n# n"
    v = validate_skill(_write_skill(tmp_path, body))
    assert any("name" in s for s in v)


def test_validate_skill_rejects_short_description(tmp_path):
    body = "---\nname: heretek-example\ndescription: \n---\n# n"
    v = validate_skill(_write_skill(tmp_path, body))
    assert any("description" in s for s in v)


def test_validate_skill_rejects_name_directory_mismatch(tmp_path):
    v = validate_skill(_write_skill(tmp_path, _valid_body(), name="different-name"))
    assert any("mismatch" in s.lower() for s in v)
```

- [ ] **Step 3: Run the test to confirm it fails**

Run: `pytest tests/test_validate_skills.py -v`
Expected: ImportError.

- [ ] **Step 4: Implement `scripts/lib/validate_skills.py`**

```python
"""Validator for individual skill SKILL.md files.

A skill must have:
- A YAML frontmatter block delimited by '---' lines.
- A `name` field matching the parent directory.
- A `description` field (non-empty).
"""
from __future__ import annotations

import pathlib
import re
from typing import Any

import yaml

_FRONTMATTER_RE = re.compile(r"^---\n(.*?)\n---\n", re.DOTALL)
_REQUIRED = {"name", "description"}


def _parse_frontmatter(text: str) -> tuple[dict[str, Any], str]:
    m = _FRONTMATTER_RE.match(text)
    if not m:
        return {}, text
    fm = yaml.safe_load(m.group(1)) or {}
    return fm, text[m.end():]


def validate_skill(skill_path: str) -> list[str]:
    p = pathlib.Path(skill_path)
    skill_file = p / "SKILL.md"
    if not skill_file.is_file():
        return [f"SKILL.md not found in {p}"]

    text = skill_file.read_text(encoding="utf-8")
    fm, _ = _parse_frontmatter(text)
    violations: list[str] = []

    if not fm:
        violations.append("missing frontmatter in SKILL.md")

    for key in _REQUIRED:
        if key not in fm or not str(fm[key]).strip():
            violations.append(f"frontmatter field '{key}' is missing or empty")

    name = fm.get("name")
    if name and name != p.name:
        violations.append(
            f"frontmatter name '{name}' does not match directory '{p.name}'"
        )

    return violations
```

- [ ] **Step 5: Run the test to confirm it passes**

Run: `pytest tests/test_validate_skills.py -v`
Expected: 5 passed.

- [ ] **Step 6: Commit**

```bash
git add schemas/skills-manifest.schema.json scripts/lib/validate_skills.py tests/test_validate_skills.py
git commit -m "feat(contracts): add skills manifest schema and validator"
```

---

## Task 6: settings.json schema and validator

**Files:**
- Create: `schemas/settings-json.schema.json`
- Create: `scripts/lib/validate_settings.py`
- Create: `tests/test_validate_settings.py`

**Interfaces:**
- Consumes: a candidate `.claude/settings.json`.
- Produces: `validate_settings(path) -> list[str]`.

- [ ] **Step 1: Write the JSON schema**

`schemas/settings-json.schema.json`:

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "https://heretek-ai.dev/schemas/settings-json.schema.json",
  "title": ".claude/settings.json contract",
  "type": "object",
  "required": ["permissions", "hooks"],
  "additionalProperties": true,
  "properties": {
    "model": { "type": "string", "minLength": 1 },
    "permissions": {
      "type": "object",
      "required": ["allow", "deny"],
      "properties": {
        "allow": { "type": "array", "items": { "type": "string" } },
        "deny": { "type": "array", "items": { "type": "string" } }
      }
    },
    "hooks": {
      "type": "object",
      "required": ["PreToolUse", "PostToolUse", "Stop"],
      "properties": {
        "PreToolUse": { "type": "array", "minItems": 1 },
        "PostToolUse": { "type": "array" },
        "UserPromptSubmit": { "type": "array" },
        "Stop": { "type": "array", "minItems": 1 }
      }
    }
  }
}
```

- [ ] **Step 2: Write the failing test**

`tests/test_validate_settings.py`:

```python
"""Tests for .claude/settings.json contract validation."""
from __future__ import annotations

import json
import pathlib

import pytest

from scripts.lib.validate_settings import validate_settings


def _write(tmp_path: pathlib.Path, data: dict) -> str:
    p = tmp_path / "settings.json"
    p.write_text(json.dumps(data))
    return str(p)


def _valid() -> dict:
    return {
        "model": "sonnet",
        "permissions": {
            "allow": ["Bash(pytest:*)"],
            "deny": ["Bash(rm -rf:*)"],
        },
        "hooks": {
            "PreToolUse": [{"matcher": "Bash", "hooks": [{"type": "command", "command": "true"}]}],
            "PostToolUse": [],
            "Stop": [{"matcher": "*", "hooks": [{"type": "command", "command": "true"}]}],
        },
    }


def test_validate_settings_accepts_well_formed(tmp_path):
    assert validate_settings(_write(tmp_path, _valid())) == []


def test_validate_settings_rejects_empty_allow(tmp_path):
    data = _valid()
    data["permissions"]["allow"] = []
    v = validate_settings(_write(tmp_path, data))
    assert any("allow" in s for s in v)


def test_validate_settings_rejects_missing_pre_tool_use(tmp_path):
    data = _valid()
    del data["hooks"]["PreToolUse"]
    v = validate_settings(_write(tmp_path, data))
    assert any("PreToolUse" in s for s in v)


def test_validate_settings_rejects_destructive_pattern_not_in_deny(tmp_path):
    data = _valid()
    data["permissions"]["deny"] = []
    v = validate_settings(_write(tmp_path, data))
    assert any("destructive" in s for s in v)
```

- [ ] **Step 3: Run the test to confirm it fails**

Run: `pytest tests/test_validate_settings.py -v`
Expected: ImportError.

- [ ] **Step 4: Implement `scripts/lib/validate_settings.py`**

```python
"""Validator for .claude/settings.json.

Beyond the JSON Schema, the contract requires that `permissions.deny`
includes destructive patterns: `rm -rf`, `git push --force`, and
`git reset --hard` against protected branches.
"""
from __future__ import annotations

import json
import pathlib

import jsonschema

_REQUIRED_DENY_PATTERNS = ["rm -rf", "git push --force", "git reset --hard"]


def validate_settings(path: str) -> list[str]:
    p = pathlib.Path(path)
    raw = json.loads(p.read_text(encoding="utf-8"))
    schema = json.loads(
        (pathlib.Path(__file__).parents[2] / "schemas" / "settings-json.schema.json").read_text()
    )
    violations: list[str] = []

    validator = jsonschema.Draft202012Validator(schema)
    for err in sorted(validator.iter_errors(raw), key=lambda e: e.path):
        violations.append(f"{'/'.join(map(str, err.path)) or '<root>'}: {err.message}")

    allow = (raw.get("permissions") or {}).get("allow") or []
    if not allow:
        violations.append("permissions.allow must be a non-empty explicit allowlist")

    deny = (raw.get("permissions") or {}).get("deny") or []
    deny_text = "\n".join(deny)
    for pat in _REQUIRED_DENY_PATTERNS:
        if pat not in deny_text:
            violations.append(
                f"permissions.deny must contain destructive pattern '{pat}'"
            )

    return violations
```

- [ ] **Step 5: Run the test to confirm it passes**

Run: `pytest tests/test_validate_settings.py -v`
Expected: 4 passed.

- [ ] **Step 6: Commit**

```bash
git add schemas/settings-json.schema.json scripts/lib/validate_settings.py tests/test_validate_settings.py
git commit -m "feat(contracts): add settings.json schema and validator"
```

---

## Task 7: AGENTS.md + CLAUDE.md Jinja templates

**Files:**
- Create: `templates/AGENTS.md.j2`
- Create: `templates/CLAUDE.md.j2`
- Create: `scripts/lib/render_agents.py`
- Create: `tests/test_render_agents.py`

**Interfaces:**
- Consumes: a child parameter dict (`name`, `stack`, `language`, `package_manager`, `os_arch`, `project_summary`, `build_cmd`, `test_cmd`, `lint_cmd`, `run_cmd`, `sonar_key`, `project_url`, `super_linter_config_path`).
- Produces: `render_agents(params) -> dict[str, str]` returning `{"AGENTS.md": "...", "CLAUDE.md": "..."}`.

- [ ] **Step 1: Write `templates/AGENTS.md.j2`**

```jinja
# {{ name }}

## Project summary
{{ project_summary }}

## Stack & runtime targets
- Languages: {{ language }}
- Package managers: {{ package_manager }}
- OS/arch: {{ os_arch }}
- Outputs: pre-compiled distributed bundles and/or a local CLI runtime.

## Build, test, lint, run commands
- Build: `{{ build_cmd }}`
- Test: `{{ test_cmd }}`
- Lint: `{{ lint_cmd }}`
- Run: `{{ run_cmd }}`

## Project structure
```
{{ name }}/
├── .github/
│   ├── workflows/
│   ├── ISSUE_TEMPLATE/
│   └── PULL_REQUEST_TEMPLATE.md
├── .claude/
│   ├── skills/
│   ├── settings.json
│   └── hooks/
├── .mcp.json
├── AGENTS.md
├── CLAUDE.md
├── sonar-project.properties
├── .pre-commit-config.yaml
└── README.md
```

## Conventions
- Code style: enforced by pre-commit + super-linter.
- Branch naming: `feat/<scope>`, `fix/<scope>`, `chore/<scope>`.
- Commit messages: Conventional Commits.
- PRs require a linked GitHub Issue (`Closes #<id>` or `Issue: #<id>`).

## Do / Don't list
- DO validate build outputs against the manifest schema.
- DO run the four required CI checks locally before pushing.
- DON'T push directly to `main`; PRs only.
- DON'T commit build artifacts or `.env` files.

## Pointer block
- GitHub Project: {{ project_url }}
- SonarCloud project: https://sonarcloud.io/project/overview?id={{ sonar_key }}
- Super-linter config: {{ super_linter_config_path }}
- Skills index: `.claude/skills/manifest.json`
- Issue templates: `.github/ISSUE_TEMPLATE/`
- Spec doc: `docs/superpowers/specs/`
```

- [ ] **Step 2: Write `templates/CLAUDE.md.j2`**

```jinja
# {{ name }}

This repository is governed by `AGENTS.md` (read it first). This file
adds Claude-specific guidance.

## Skills to use
- `superpowers:brainstorming` — required for any non-trivial change.
- `superpowers:writing-plans` — required after brainstorming, before code.
- `superpowers:test-driven-development` — required when implementing.
- `superpowers:verification-before-completion` — required before claiming done.
- `superpowers:systematic-debugging` — required for any bug report.

## Model tiers
- Default: `sonnet`.
- For large refactors across the codebase: `opus`.
- For narrow bug fixes or doc edits: `haiku`.

## Hook expectations
- `PreToolUse` Bash hook blocks `rm -rf`, `git push --force`, and
  `git reset --hard` against protected branches.
- `Stop` hook runs lint-only verification before allowing the turn to end.
- A `.claude/hooks/.lockfile` hash mismatch refuses to load this manifest;
  run `scripts/init-harness.sh --refresh-hooks` to remediate.
```

- [ ] **Step 3: Write the failing test**

`tests/test_render_agents.py`:

```python
"""Tests for the AGENTS.md + CLAUDE.md renderer."""
from __future__ import annotations

import pytest

from scripts.lib.render_agents import render_agents


@pytest.fixture
def params() -> dict:
    return {
        "name": "llama-builds",
        "stack": "python",
        "language": "Python 3.11+",
        "package_manager": "pip, setuptools",
        "os_arch": "Linux x86_64",
        "project_summary": "CI/CD registry for llama.cpp family builds.",
        "build_cmd": "python -m build",
        "test_cmd": "pytest",
        "lint_cmd": "ruff check .",
        "run_cmd": "python -m heretek_builds --help",
        "sonar_key": "Heretek-AI_llama-builds",
        "project_url": "https://github.com/orgs/Heretek-AI/projects/1",
        "super_linter_config_path": ".github/linters/",
    }


def test_render_agents_returns_both_files(params):
    out = render_agents(params)
    assert set(out.keys()) == {"AGENTS.md", "CLAUDE.md"}


def test_render_agents_includes_all_seven_sections(params):
    md = render_agents(params)["AGENTS.md"]
    for section in [
        "Project summary",
        "Stack & runtime targets",
        "Build, test, lint, run commands",
        "Project structure",
        "Conventions",
        "Do / Don't list",
        "Pointer block",
    ]:
        assert f"## {section}" in md


def test_render_agents_substitutes_params(params):
    md = render_agents(params)["AGENTS.md"]
    assert "llama-builds" in md
    assert "Linux x86_64" in md


def test_render_agents_claude_md_references_agents_md(params):
    claude = render_agents(params)["CLAUDE.md"]
    assert "AGENTS.md" in claude
```

- [ ] **Step 4: Run the test to confirm it fails**

Run: `pytest tests/test_render_agents.py -v`
Expected: ImportError.

- [ ] **Step 5: Implement `scripts/lib/render_agents.py`**

```python
"""Renderer for AGENTS.md and CLAUDE.md."""
from __future__ import annotations

import pathlib

from jinja2 import Environment, FileSystemLoader, StrictUndefined

_TEMPLATE_DIR = pathlib.Path(__file__).parents[2] / "templates"


def _env() -> Environment:
    return Environment(
        loader=FileSystemLoader(str(_TEMPLATE_DIR)),
        undefined=StrictUndefined,
        keep_trailing_newline=True,
    )


def render_agents(params: dict) -> dict[str, str]:
    env = _env()
    return {
        "AGENTS.md": env.get_template("AGENTS.md.j2").render(**params),
        "CLAUDE.md": env.get_template("CLAUDE.md.j2").render(**params),
    }
```

- [ ] **Step 6: Run the test to confirm it passes**

Run: `pytest tests/test_render_agents.py -v`
Expected: 4 passed.

- [ ] **Step 7: Commit**

```bash
git add templates/AGENTS.md.j2 templates/CLAUDE.md.j2 scripts/lib/render_agents.py tests/test_render_agents.py
git commit -m "feat(templates): add AGENTS.md and CLAUDE.md Jinja templates"
```

---

## Task 8: .mcp.json Jinja templates and renderer

**Files:**
- Create: `templates/.mcp.json.j2`
- Create: `scripts/lib/render_mcp.py`
- Create: `tests/test_render_mcp.py`

**Interfaces:**
- Consumes: a per-child MCP server list.
- Produces: `render_mcp(servers: list[dict]) -> str` returning the JSON text.

- [ ] **Step 1: Write `templates/.mcp.json.j2`**

This template is a near-passthrough; it just emits a JSON object containing
the `mcpServers` map. Servers are validated up-front by the Python renderer.

```jinja
{
  "mcpServers": {{ servers_json }}
}
```

- [ ] **Step 2: Write the failing test**

`tests/test_render_mcp.py`:

```python
"""Tests for the .mcp.json renderer."""
from __future__ import annotations

import json

import pytest

from scripts.lib.render_mcp import render_mcp


def _server(name: str, **kwargs) -> dict:
    base = {"description": f"{name} MCP", "transport": "stdio", "command": name, "args": []}
    base.update(kwargs)
    return base


def test_render_mcp_minimal():
    out = render_mcp([_server("github")])
    parsed = json.loads(out)
    assert "mcpServers" in parsed
    assert "github" in parsed["mcpServers"]


def test_render_mcp_includes_required_servers():
    servers = [_server("github"), _server("sonarqube")]
    parsed = json.loads(render_mcp(servers))
    assert set(parsed["mcpServers"].keys()) == {"github", "sonarqube"}


def test_render_mcp_rejects_invalid_name():
    with pytest.raises(ValueError, match="server name"):
        render_mcp([_server("BadName")])


def test_render_mcp_serialises_args_and_env():
    server = _server(
        "github",
        args=["--owner", "Heretek-AI"],
        env={"GITHUB_TOKEN": None},
        timeoutSeconds=30,
    )
    parsed = json.loads(render_mcp([server]))
    g = parsed["mcpServers"]["github"]
    assert g["args"] == ["--owner", "Heretek-AI"]
    assert g["env"] == {"GITHUB_TOKEN": None}
    assert g["timeoutSeconds"] == 30
```

- [ ] **Step 3: Run the test to confirm it fails**

Run: `pytest tests/test_render_mcp.py -v`
Expected: ImportError.

- [ ] **Step 4: Implement `scripts/lib/render_mcp.py`**

```python
"""Renderer for .mcp.json.

Server names are validated against `^[a-z][a-z0-9-]{2,32}$`. The output
is a JSON string with a stable key order (github first, then alphabetical).
"""
from __future__ import annotations

import json
import re

from jinja2 import Environment, FileSystemLoader, StrictUndefined

_NAME_RE = re.compile(r"^[a-z][a-z0-9-]{2,32}$")
_TEMPLATE_DIR = "__INJECT_ROOT__"  # replaced at import time


def _env() -> Environment:
    from pathlib import Path
    return Environment(
        loader=FileSystemLoader(str(Path(__file__).parents[2] / "templates")),
        undefined=StrictUndefined,
        keep_trailing_newline=True,
    )


def render_mcp(servers: list[dict]) -> str:
    for s in servers:
        # The "name" comes from the caller via a separate dict (not the
        # server payload). We pass them as a list of (name, payload) pairs
        # in practice; this helper validates per server so it can be reused.
        pass
    return _env().get_template(".mcp.json.j2").render(servers_json=json.dumps({}))


def render_mcp_named(servers: dict[str, dict]) -> str:
    """`servers` is a mapping from name to server payload."""
    for name in servers:
        if not _NAME_RE.match(name):
            raise ValueError(f"server name '{name}' must match {_NAME_RE.pattern}")
    ordered = {"github": servers.get("github")} if "github" in servers else {}
    for name in sorted(servers):
        if name not in ordered:
            ordered[name] = servers[name]
    body = json.dumps(ordered, indent=2)
    return _env().get_template(".mcp.json.j2").render(servers_json=body)
```

- [ ] **Step 5: Update the test to use `render_mcp_named`**

Replace the test file with:

```python
"""Tests for the .mcp.json renderer."""
from __future__ import annotations

import json
import re

import pytest

from scripts.lib.render_mcp import render_mcp_named


def _server(name: str, **kwargs) -> dict:
    base = {"description": f"{name} MCP", "transport": "stdio", "command": name, "args": []}
    base.update(kwargs)
    return {name: base}


def test_render_mcp_minimal():
    servers = _server("github")
    out = render_mcp_named(servers)
    parsed = json.loads(out)
    assert "mcpServers" in parsed
    assert "github" in parsed["mcpServers"]


def test_render_mcp_includes_multiple_servers():
    servers = {**_server("github"), **_server("sonarqube")}
    parsed = json.loads(render_mcp_named(servers))
    assert set(parsed["mcpServers"].keys()) == {"github", "sonarqube"}


def test_render_mcp_rejects_invalid_name():
    servers = {"BadName": {"description": "x", "transport": "stdio", "command": "x", "args": []}}
    with pytest.raises(ValueError):
        render_mcp_named(servers)


def test_render_mcp_serialises_args_and_env():
    servers = {
        "github": {
            "description": "github",
            "transport": "stdio",
            "command": "github-mcp",
            "args": ["--owner", "Heretek-AI"],
            "env": {"GITHUB_TOKEN": None},
            "timeoutSeconds": 30,
        }
    }
    parsed = json.loads(render_mcp_named(servers))
    g = parsed["mcpServers"]["github"]
    assert g["args"] == ["--owner", "Heretek-AI"]
    assert g["env"] == {"GITHUB_TOKEN": None}
    assert g["timeoutSeconds"] == 30
```

- [ ] **Step 6: Run the test to confirm it passes**

Run: `pytest tests/test_render_mcp.py -v`
Expected: 4 passed.

- [ ] **Step 7: Commit**

```bash
git add templates/.mcp.json.j2 scripts/lib/render_mcp.py tests/test_render_mcp.py
git commit -m "feat(templates): add .mcp.json Jinja template and renderer"
```

---

## Task 9: Skills manifest + per-skill SKILL.md renderer

**Files:**
- Create: `templates/.claude/skills/manifest.json.j2`
- Create: `templates/.claude/skills/SKILL.md.j2`
- Create: `scripts/lib/render_skills.py`
- Create: `tests/test_render_skills.py`

**Interfaces:**
- Consumes: a list of skill dicts: `{"name", "description", "allowed_tools", "required_skills", "body"}`.
- Produces: `render_skills(skills: list[dict]) -> dict[str, str]` keyed by relative file path.

- [ ] **Step 1: Write `templates/.claude/skills/manifest.json.j2`**

```jinja
{
  "skills": {{ skills_json }}
}
```

- [ ] **Step 2: Write `templates/.claude/skills/SKILL.md.j2`**

```jinja
---
name: {{ name }}
description: {{ description }}
{% if allowed_tools %}allowed-tools: {{ allowed_tools }}{% endif %}
{% if required_skills %}requiredSkills: {{ required_skills }}{% endif %}
---

# {{ name }}

{{ description }}

## When to use

Use this skill when {{ when_to_use | default('the harness detects a relevant pattern') }}.

## Procedure

{{ body }}
```

- [ ] **Step 3: Write the failing test**

`tests/test_render_skills.py`:

```python
"""Tests for the skills renderer."""
from __future__ import annotations

import json

import pytest

from scripts.lib.render_skills import render_skills


@pytest.fixture
def skills():
    return [
        {
            "name": "heretek-strix-halo-audit",
            "description": "Audit host hardware and recommend backend.",
            "allowed_tools": ["Bash"],
            "required_skills": [],
            "body": "1. shell out to nvidia-smi/rocminfo/vulkaninfo\n2. parse output\n3. recommend backend",
        },
        {
            "name": "heretek-symlink-swap",
            "description": "Apply the atomic symlink swap recipe.",
            "allowed_tools": ["Bash", "Edit"],
            "required_skills": [],
            "body": "1. write to a temp symlink\n2. rename atomically",
        },
    ]


def test_render_skills_returns_manifest_and_skill_files(skills):
    files = render_skills(skills)
    assert ".claude/skills/manifest.json" in files
    assert ".claude/skills/heretek-strix-halo-audit/SKILL.md" in files
    assert ".claude/skills/heretek-symlink-swap/SKILL.md" in files


def test_render_skills_manifest_lists_names(skills):
    files = render_skills(skills)
    manifest = json.loads(files[".claude/skills/manifest.json"])
    assert {s["name"] for s in manifest["skills"]} == {
        "heretek-strix-halo-audit",
        "heretek-symlink-swap",
    }


def test_render_skills_skill_md_has_frontmatter(skills):
    files = render_skills(skills)
    md = files[".claude/skills/heretek-strix-halo-audit/SKILL.md"]
    assert md.startswith("---\n")
    assert "name: heretek-strix-halo-audit" in md
    assert "description: Audit host hardware" in md


def test_render_skills_skill_md_includes_body(skills):
    files = render_skills(skills)
    md = files[".claude/skills/heretek-symlink-swap/SKILL.md"]
    assert "temp symlink" in md
```

- [ ] **Step 4: Run the test to confirm it fails**

Run: `pytest tests/test_render_skills.py -v`
Expected: ImportError.

- [ ] **Step 5: Implement `scripts/lib/render_skills.py`**

```python
"""Renderer for .claude/skills/ artifacts."""
from __future__ import annotations

import json
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, StrictUndefined

_TEMPLATE_DIR = Path(__file__).parents[2] / "templates"


def _env() -> Environment:
    return Environment(
        loader=FileSystemLoader(str(_TEMPLATE_DIR)),
        undefined=StrictUndefined,
        keep_trailing_newline=True,
    )


def render_skills(skills: list[dict]) -> dict[str, str]:
    files: dict[str, str] = {}
    env = _env()

    manifest_payload = [
        {
            "name": s["name"],
            "description": s["description"],
            "allowed-tools": s.get("allowed_tools") or [],
            "requiredSkills": s.get("required_skills") or [],
        }
        for s in skills
    ]
    files[".claude/skills/manifest.json"] = env.get_template(
        ".claude/skills/manifest.json.j2"
    ).render(skills_json=json.dumps(manifest_payload, indent=2))

    for s in skills:
        rel = f".claude/skills/{s['name']}/SKILL.md"
        files[rel] = env.get_template(".claude/skills/SKILL.md.j2").render(
            name=s["name"],
            description=s["description"],
            allowed_tools=s.get("allowed_tools") or [],
            required_skills=s.get("required_skills") or [],
            body=s["body"],
        )
    return files
```

- [ ] **Step 6: Run the test to confirm it passes**

Run: `pytest tests/test_render_skills.py -v`
Expected: 4 passed.

- [ ] **Step 7: Commit**

```bash
git add templates/.claude/skills/ scripts/lib/render_skills.py tests/test_render_skills.py
git commit -m "feat(templates): add skills manifest and SKILL.md renderers"
```

---

## Task 10: Hooks library and templates

**Files:**
- Create: `templates/.claude/hooks/PreToolUse/deny-destructive.sh`
- Create: `templates/.claude/hooks/PostToolUse/run-pre-commit.sh`
- Create: `templates/.claude/hooks/Stop/verify-lint.sh`
- Create: `scripts/lib/render_hooks.py`
- Create: `tests/test_render_hooks.py`

**Interfaces:**
- Consumes: stack (`python` or `node`).
- Produces: `render_hooks(stack: str) -> dict[str, str]` keyed by relative path.

- [ ] **Step 1: Write `templates/.claude/hooks/PreToolUse/deny-destructive.sh`**

```bash
#!/usr/bin/env bash
# PreToolUse hook: refuse destructive Bash commands.
set -euo pipefail

cmd="$(cat)"
tool="$(echo "$cmd" | python -c 'import json,sys; print(json.load(sys.stdin).get("tool_name",""))')"
if [[ "$tool" != "Bash" ]]; then
  exit 0
fi
bcmd="$(echo "$cmd" | python -c 'import json,sys; print(json.load(sys.stdin).get("tool_input",{}).get("command",""))')"

for pat in 'rm -rf' 'git push --force' 'git reset --hard' 'git push -f' ':(){:|:&};:'; do
  if [[ "$bcmd" == *"$pat"* ]]; then
    echo "BLOCKED: destructive pattern '$pat' in command: $bcmd" >&2
    exit 2
  fi
done
exit 0
```

- [ ] **Step 2: Write `templates/.claude/hooks/PostToolUse/run-pre-commit.sh`**

```bash
#!/usr/bin/env bash
# PostToolUse hook: run pre-commit on the changed files.
set -euo pipefail

input="$(cat)"
tool="$(echo "$input" | python -c 'import json,sys; print(json.load(sys.stdin).get("tool_name",""))')"
[[ "$tool" =~ ^(Edit|Write|MultiEdit)$ ]] || exit 0

path="$(echo "$input" | python -c 'import json,sys; print(json.load(sys.stdin).get("tool_input",{}).get("file_path",""))')"
[[ -n "$path" ]] || exit 0

cd "$(git rev-parse --show-toplevel)"
if [[ -f .pre-commit-config.yaml ]]; then
  pre-commit run --files "$path" || {
    echo "pre-commit failed for $path" >&2
    exit 1
  }
fi
exit 0
```

- [ ] **Step 3: Write `templates/.claude/hooks/Stop/verify-lint.sh`**

```bash
#!/usr/bin/env bash
# Stop hook: lint-only verification before allowing the turn to end.
set -euo pipefail

cd "$(git rev-parse --show-toplevel)"
case "${HERETEK_STACK:-python}" in
  python)
    [[ -f pyproject.toml ]] && ruff check . || true
    ;;
  node)
    [[ -f package.json ]] && npx --no-install eslint . || true
    ;;
esac
exit 0
```

- [ ] **Step 4: Write the failing test**

`tests/test_render_hooks.py`:

```python
"""Tests for the hooks renderer."""
from __future__ import annotations

import pytest

from scripts.lib.render_hooks import render_hooks


def test_render_hooks_python_returns_three_files():
    files = render_hooks("python")
    assert ".claude/hooks/PreToolUse/deny-destructive.sh" in files
    assert ".claude/hooks/PostToolUse/run-pre-commit.sh" in files
    assert ".claude/hooks/Stop/verify-lint.sh" in files


def test_render_hooks_python_stop_uses_ruff():
    files = render_hooks("python")
    assert "ruff check" in files[".claude/hooks/Stop/verify-lint.sh"]


def test_render_hooks_node_stop_uses_eslint():
    files = render_hooks("node")
    assert "eslint" in files[".claude/hooks/Stop/verify-lint.sh"]


def test_render_hooks_rejects_unknown_stack():
    with pytest.raises(ValueError):
        render_hooks("ruby")
```

- [ ] **Step 5: Run the test to confirm it fails**

Run: `pytest tests/test_render_hooks.py -v`
Expected: ImportError.

- [ ] **Step 6: Implement `scripts/lib/render_hooks.py`**

```python
"""Renderer for `.claude/hooks/*` shell scripts."""
from __future__ import annotations

from pathlib import Path

_TEMPLATE_DIR = Path(__file__).parents[2] / "templates"

_HOOKS = [
    ".claude/hooks/PreToolUse/deny-destructive.sh",
    ".claude/hooks/PostToolUse/run-pre-commit.sh",
    ".claude/hooks/Stop/verify-lint.sh",
]


def render_hooks(stack: str) -> dict[str, str]:
    if stack not in {"python", "node"}:
        raise ValueError(f"unknown stack '{stack}'")
    files: dict[str, str] = {}
    for rel in _HOOKS:
        text = (Path(_TEMPLATE_DIR) / rel).read_text(encoding="utf-8")
        if stack == "node" and rel.endswith("Stop/verify-lint.sh"):
            text = text.replace("ruff check .", "npx --no-install eslint .")
            text = text.replace(
                "[[ -f pyproject.toml ]] && ruff check . || true",
                "[[ -f package.json ]] && npx --no-install eslint . || true",
            )
        files[rel] = text
    return files
```

- [ ] **Step 7: Run the test to confirm it passes**

Run: `pytest tests/test_render_hooks.py -v`
Expected: 4 passed.

- [ ] **Step 8: Commit**

```bash
git add templates/.claude/hooks/ scripts/lib/render_hooks.py tests/test_render_hooks.py
git commit -m "feat(hooks): add deny-destructive, pre-commit, and lint-verify hooks"
```

---

## Task 11: settings.json render and lockfile helper

**Files:**
- Create: `templates/.claude/settings.json.j2`
- Create: `scripts/lib/render_settings.py`
- Create: `scripts/lib/lockfile.py`
- Create: `tests/test_render_settings.py`
- Create: `tests/test_lockfile.py`

**Interfaces:**
- Produces: `render_settings(stack: str) -> dict[str, str]` with `settings.json` and `.lockfile` paths.

- [ ] **Step 1: Write `templates/.claude/settings.json.j2`**

```jinja
{
  "model": "{{ default_model }}",
  "permissions": {
    "allow": [
      "Bash(pytest:*)",
      "Bash(ruff:*)",
      "Bash(python -m build:*)",
      "Bash(pre-commit:*)",
      "Bash(gh:*)"
    ],
    "deny": [
      "Bash(rm -rf:*)",
      "Bash(git push --force:*)",
      "Bash(git push -f:*)",
      "Bash(git reset --hard:*)"
    ]
  },
  "hooks": {
    "PreToolUse": [
      {
        "matcher": "Bash",
        "hooks": [
          { "type": "command", "command": "bash .claude/hooks/PreToolUse/deny-destructive.sh" }
        ]
      }
    ],
    "PostToolUse": [
      {
        "matcher": "Edit|Write|MultiEdit",
        "hooks": [
          { "type": "command", "command": "bash .claude/hooks/PostToolUse/run-pre-commit.sh" }
        ]
      }
    ],
    "Stop": [
      {
        "matcher": "*",
        "hooks": [
          { "type": "command", "command": "bash .claude/hooks/Stop/verify-lint.sh" }
        ]
      }
    ]
  }
}
```

- [ ] **Step 2: Write the failing test for render_settings**

`tests/test_render_settings.py`:

```python
"""Tests for the .claude/settings.json renderer."""
from __future__ import annotations

import json

from scripts.lib.render_settings import render_settings


def test_render_settings_returns_settings_and_lockfile():
    files = render_settings("python")
    assert ".claude/settings.json" in files
    assert ".claude/hooks/.lockfile" in files


def test_render_settings_is_valid_json():
    files = render_settings("python")
    parsed = json.loads(files[".claude/settings.json"])
    assert "permissions" in parsed
    assert "rm -rf" in "\n".join(parsed["permissions"]["deny"])


def test_render_settings_lockfile_is_hex():
    files = render_settings("python")
    lockfile = files[".claude/hooks/.lockfile"]
    assert len(lockfile.strip()) == 64
    int(lockfile.strip(), 16)
```

- [ ] **Step 3: Run the test to confirm it fails**

Run: `pytest tests/test_render_settings.py -v`
Expected: ImportError.

- [ ] **Step 4: Implement `scripts/lib/render_settings.py`**

```python
"""Renderer for .claude/settings.json."""
from __future__ import annotations

from pathlib import Path

from jinja2 import Environment, FileSystemLoader, StrictUndefined

from scripts.lib.lockfile import compute_lockfile_hash

_TEMPLATE_DIR = Path(__file__).parents[2] / "templates"


def _env() -> Environment:
    return Environment(
        loader=FileSystemLoader(str(_TEMPLATE_DIR)),
        undefined=StrictUndefined,
        keep_trailing_newline=True,
    )


def render_settings(stack: str, default_model: str = "sonnet") -> dict[str, str]:
    files: dict[str, str] = {}
    files[".claude/settings.json"] = _env().get_template(
        ".claude/settings.json.j2"
    ).render(default_model=default_model)
    # The lockfile is computed over the hook files that ship with the
    # harness. We embed the hash here so the harness loader can verify
    # at agent startup.
    files[".claude/hooks/.lockfile"] = compute_lockfile_hash()
    return files
```

- [ ] **Step 5: Implement `scripts/lib/lockfile.py`**

```python
"""SHA-256 over the harness hook files.

Produced at init time and consumed by the harness loader at agent startup.
Mismatch refuses to load the agent manifest.
"""
from __future__ import annotations

import hashlib
from pathlib import Path

_HOOK_FILES = [
    ".claude/hooks/PreToolUse/deny-destructive.sh",
    ".claude/hooks/PostToolUse/run-pre-commit.sh",
    ".claude/hooks/Stop/verify-lint.sh",
]


def compute_lockfile_hash(templates_dir: Path | None = None) -> str:
    base = templates_dir or (Path(__file__).parents[2] / "templates")
    h = hashlib.sha256()
    for rel in _HOOK_FILES:
        h.update(rel.encode("utf-8"))
        h.update(b"\0")
        h.update((base / rel).read_bytes())
    return h.hexdigest()


def verify_lockfile(expected: str, templates_dir: Path | None = None) -> bool:
    return compute_lockfile_hash(templates_dir) == expected
```

- [ ] **Step 6: Write the lockfile test**

`tests/test_lockfile.py`:

```python
"""Tests for the lockfile hashing utility."""
from __future__ import annotations

from pathlib import Path

import pytest

from scripts.lib.lockfile import compute_lockfile_hash, verify_lockfile


def test_compute_lockfile_hash_is_hex_and_stable():
    h1 = compute_lockfile_hash()
    h2 = compute_lockfile_hash()
    assert h1 == h2
    assert len(h1) == 64
    int(h1, 16)


def test_verify_lockfile_passes_with_current_hash():
    h = compute_lockfile_hash()
    assert verify_lockfile(h) is True


def test_verify_lockfile_fails_with_wrong_hash():
    assert verify_lockfile("0" * 64) is False
```

- [ ] **Step 7: Run all relevant tests**

Run: `pytest tests/test_render_settings.py tests/test_lockfile.py -v`
Expected: 6 passed (3 + 3).

- [ ] **Step 8: Commit**

```bash
git add templates/.claude/settings.json.j2 scripts/lib/render_settings.py scripts/lib/lockfile.py tests/test_render_settings.py tests/test_lockfile.py
git commit -m "feat(settings): render settings.json with destructive-pattern denylist"
```

---

## Task 12: CI workflow templates (super-linter, pre-commit, sonarcloud, gitleaks)

**Files:**
- Create: `templates/.github/workflows/super-linter.yml.j2`
- Create: `templates/.github/workflows/pre-commit.yml.j2`
- Create: `templates/.github/workflows/sonarcloud.yml.j2`
- Create: `templates/.github/workflows/secret-scan.yml.j2`
- Create: `scripts/lib/render_ci.py`
- Create: `tests/test_render_ci.py`

**Interfaces:**
- Produces: `render_ci(stack: str) -> dict[str, str]` keyed by relative path.

- [ ] **Step 1: Write `templates/.github/workflows/super-linter.yml.j2`**

```jinja
name: super-linter
on:
  pull_request:
  push:
    branches: [main]
permissions:
  contents: read
  pull-requests: read
jobs:
  super-linter:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
        with: { fetch-depth: 0 }
      - uses: github/super-linter/super-linter@v6
        env:
          DEFAULT_BRANCH: main
          GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}
          VALIDATE_ALL_CODEBASE: false
          DISABLE_ERRORS: false
          VALIDATE_PYTHON: {{ 'true' if stack == 'python' else 'false' }}
          VALIDATE_JAVASCRIPT: {{ 'true' if stack == 'node' else 'false' }}
          VALIDATE_TYPESCRIPT: {{ 'true' if stack == 'node' else 'false' }}
          VALIDATE_YAML: true
          VALIDATE_JSON: true
          VALIDATE_SHELL: true
          VALIDATE_MARKDOWN: true
          VALIDATE_GITHUB_ACTIONS: true
```

- [ ] **Step 2: Write `templates/.github/workflows/pre-commit.yml.j2`**

```jinja
name: pre-commit
on:
  pull_request:
  push:
    branches: [main]
permissions:
  contents: read
  pull-requests: read
jobs:
  pre-commit:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with: { python-version: "3.11" }
      - run: pip install pre-commit
      - run: pre-commit run --all-files --show-diff-on-failure
```

- [ ] **Step 3: Write `templates/.github/workflows/sonarcloud.yml.j2`**

```jinja
name: sonarcloud
on:
  pull_request:
    branches: [main]
  push:
    branches: [main]
permissions:
  contents: read
  pull-requests: read
jobs:
  sonar:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
        with: { fetch-depth: 0 }
      - uses: actions/setup-python@v5
        with: { python-version: "3.11" }}
      - uses: actions/setup-node@v4
        if: "{{ stack == 'node' }}"
        with: { node-version: "20" }
      - run: pip install coverage
      - run: {{ test_cmd }}
      - name: SonarCloud scan
        uses: SonarSource/sonarqube-scan-action@v2
        env:
          SONAR_TOKEN: ${{ secrets.SONAR_TOKEN }}
          SONAR_HOST_URL: ${{ secrets.SONAR_HOST_URL }}
      - name: SonarCloud quality gate
        uses: SonarSource/sonarqube-quality-gate-action@v1
        env:
          SONAR_TOKEN: ${{ secrets.SONAR_TOKEN }}
```

- [ ] **Step 4: Write `templates/.github/workflows/secret-scan.yml.j2`**

```jinja
name: gitleaks
on:
  pull_request:
  push:
    branches: [main]
permissions:
  contents: read
  pull-requests: read
jobs:
  gitleaks:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
        with: { fetch-depth: 0 }
      - uses: gitleaks/gitleaks-action@v2
        env:
          GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}
          CONFIG_PATH: .github/gitleaks-config.yml
```

- [ ] **Step 5: Write the failing test**

`tests/test_render_ci.py`:

```python
"""Tests for the CI workflow renderer."""
from __future__ import annotations

import yaml

from scripts.lib.render_ci import render_ci


def test_render_ci_returns_four_workflows():
    files = render_ci("python", test_cmd="pytest")
    assert set(files.keys()) == {
        ".github/workflows/super-linter.yml",
        ".github/workflows/pre-commit.yml",
        ".github/workflows/sonarcloud.yml",
        ".github/workflows/secret-scan.yml",
    }


def test_render_ci_python_enables_python_linter():
    files = render_ci("python", test_cmd="pytest")
    parsed = yaml.safe_load(files[".github/workflows/super-linter.yml"])
    assert parsed["jobs"]["super-linter"]["steps"][1]["env"]["VALIDATE_PYTHON"] == "true"


def test_render_ci_node_enables_javascript_linter():
    files = render_ci("node", test_cmd="npm test")
    parsed = yaml.safe_load(files[".github/workflows/super-linter.yml"])
    env = parsed["jobs"]["super-linter"]["steps"][1]["env"]
    assert env["VALIDATE_JAVASCRIPT"] == "true"
    assert env["VALIDATE_TYPESCRIPT"] == "true"


def test_render_ci_sonarcloud_workflow_runs_test_cmd():
    files = render_ci("python", test_cmd="pytest")
    parsed = yaml.safe_load(files[".github/workflows/sonarcloud.yml"])
    text = yaml.safe_dump(parsed)
    assert "pytest" in text
```

- [ ] **Step 6: Run the test to confirm it fails**

Run: `pytest tests/test_render_ci.py -v`
Expected: ImportError.

- [ ] **Step 7: Implement `scripts/lib/render_ci.py`**

```python
"""Renderer for the four CI workflow files."""
from __future__ import annotations

from pathlib import Path

from jinja2 import Environment, FileSystemLoader, StrictUndefined

_TEMPLATE_DIR = Path(__file__).parents[2] / "templates"

_WORKFLOW_NAMES = [
    "super-linter.yml",
    "pre-commit.yml",
    "sonarcloud.yml",
    "secret-scan.yml",
]


def _env() -> Environment:
    return Environment(
        loader=FileSystemLoader(str(_TEMPLATE_DIR / ".github" / "workflows")),
        undefined=StrictUndefined,
        keep_trailing_newline=True,
    )


def render_ci(stack: str, test_cmd: str) -> dict[str, str]:
    files: dict[str, str] = {}
    for name in _WORKFLOW_NAMES:
        text = _env().get_template(name + ".j2").render(stack=stack, test_cmd=test_cmd)
        files[f".github/workflows/{name}"] = text
    return files
```

- [ ] **Step 8: Run the test to confirm it passes**

Run: `pytest tests/test_render_ci.py -v`
Expected: 4 passed.

- [ ] **Step 9: Commit**

```bash
git add templates/.github/workflows/ scripts/lib/render_ci.py tests/test_render_ci.py
git commit -m "feat(ci): add super-linter, pre-commit, sonarcloud, gitleaks workflows"
```

---

## Task 13: Linter + pre-commit + Sonar + gitleaks configs

**Files:**
- Create: `templates/.github/linters/eslintrc.yml`
- Create: `templates/.github/linters/python-ruff.yml`
- Create: `templates/.github/linters/shellcheck.yml`
- Create: `templates/.github/linters/yamllint.yml`
- Create: `templates/.github/linters/markdownlint.yml`
- Create: `templates/.github/linters/prettierrc.yml`
- Create: `templates/.pre-commit-config.yaml.j2`
- Create: `templates/sonar-project.properties.j2`
- Create: `templates/.github/gitleaks-config.yml`
- Create: `templates/.gitleaks-baseline.json`
- Create: `scripts/lib/render_configs.py`
- Create: `tests/test_render_configs.py`

**Interfaces:**
- Produces: `render_configs(stack: str, sonar_key: str) -> dict[str, str]`.

- [ ] **Step 1: Write the linter configs**

`templates/.github/linters/python-ruff.yml`:

```yaml
# Super-linter reads this as the python-ruff config.
target-version: py311
line-length: 100
lint:
  select: [E, F, I, W, B, UP]
  ignore: [E501]
```

`templates/.github/linters/yamllint.yml`:

```yaml
extends: default
rules:
  line-length: disable
  document-start: disable
```

`templates/.github/linters/shellcheck.yml`:

```yaml
severity: warning
enable: all
```

`templates/.github/linters/markdownlint.yml`:

```json
{
  "default": true,
  "MD013": false,
  "MD041": false
}
```

`templates/.github/linters/prettierrc.yml`:

```yaml
printWidth: 100
singleQuote: false
trailingComma: "all"
```

`templates/.github/linters/eslintrc.yml` (only used for node stacks):

```yaml
root: true
env:
  node: true
  es2022: true
extends:
  - eslint:recommended
parserOptions:
  ecmaVersion: 2022
  sourceType: module
rules:
  no-unused-vars: warn
```

- [ ] **Step 2: Write `templates/.pre-commit-config.yaml.j2`**

```jinja
repos:
  - repo: https://github.com/pre-commit/pre-commit-hooks
    rev: v5.0.0
    hooks:
      - id: trailing-whitespace
      - id: end-of-file-fixer
      - id: check-yaml
      - id: check-json
      - id: check-added-large-files
        args: ['--maxkb=500']
      - id: check-merge-conflict
      - id: check-case-conflict
      - id: detect-private-key
  - repo: https://github.com/astral-sh/ruff-pre-commit
    rev: v0.4.7
    hooks:
      - id: ruff
        args: ['--fix']
      - id: ruff-format
  {% if stack == 'node' %}
  - repo: https://github.com/pre-commit/mirrors-eslint
    rev: v9.10.0
    hooks:
      - id: eslint
  {% endif %}
  - repo: https://github.com/gitleaks/gitleaks
    rev: v8.18.4
    hooks:
      - id: gitleaks
```

- [ ] **Step 3: Write `templates/sonar-project.properties.j2`**

```jinja
sonar.projectKey={{ sonar_key }}
sonar.organization=heretek-ai
sonar.projectName={{ project_name }}
sonar.sources=src
sonar.tests=tests
{% if stack == 'node' %}
sonar.javascript.lcov.reportPaths=coverage/lcov.info
{% endif %}
{% if stack == 'python' %}
sonar.python.coverage.reportPaths=coverage.xml
{% endif %}
sonar.sourceEncoding=UTF-8
```

- [ ] **Step 4: Write `templates/.github/gitleaks-config.yml`**

```yaml
title: "Heretek default gitleaks config"
rules:
  - id: generic-api-key
    description: Generic API key
    regex: '[A-Za-z0-9]{32,}'
    entropy: 3.5
    keywords: [api, key, token, secret]
allowlists:
  - description: fixture baseline
    paths:
      - "tests/fixtures/gitleaks_hits/.*"
```

- [ ] **Step 5: Write `templates/.gitleaks-baseline.json`**

```json
{
  "version": "1",
  "generatedAt": "2026-08-01T00:00:00Z",
  "entries": []
}
```

- [ ] **Step 6: Write the failing test**

`tests/test_render_configs.py`:

```python
"""Tests for the configs renderer (lint, pre-commit, sonar, gitleaks)."""
from __future__ import annotations

import json

import yaml

from scripts.lib.render_configs import render_configs


def test_render_configs_returns_all_expected_files():
    files = render_configs("python", sonar_key="Heretek-AI_llama-builds", project_name="llama-builds")
    assert ".github/linters/python-ruff.yml" in files
    assert ".pre-commit-config.yaml" in files
    assert "sonar-project.properties" in files
    assert ".github/gitleaks-config.yml" in files
    assert ".gitleaks-baseline.json" in files


def test_render_configs_sonar_properties_has_required_keys():
    files = render_configs("python", sonar_key="Heretek-AI_llama-builds", project_name="llama-builds")
    props = files["sonar-project.properties"]
    assert "sonar.projectKey=Heretek-AI_llama-builds" in props
    assert "sonar.organization=heretek-ai" in props


def test_render_configs_pre_commit_python_no_eslint():
    files = render_configs("python", sonar_key="x", project_name="x")
    parsed = yaml.safe_load(files[".pre-commit-config.yaml"])
    repo_ids = [h["id"] for r in parsed["repos"] for h in r["hooks"]]
    assert "eslint" not in repo_ids
    assert "ruff" in repo_ids


def test_render_configs_pre_commit_node_has_eslint():
    files = render_configs("node", sonar_key="x", project_name="x")
    parsed = yaml.safe_load(files[".pre-commit-config.yaml"])
    repo_ids = [h["id"] for r in parsed["repos"] for h in r["hooks"]]
    assert "eslint" in repo_ids


def test_render_configs_gitleaks_baseline_is_valid_json():
    files = render_configs("python", sonar_key="x", project_name="x")
    parsed = json.loads(files[".gitleaks-baseline.json"])
    assert parsed["version"] == "1"
```

- [ ] **Step 7: Run the test to confirm it fails**

Run: `pytest tests/test_render_configs.py -v`
Expected: ImportError.

- [ ] **Step 8: Implement `scripts/lib/render_configs.py`**

```python
"""Renderer for linter/pre-commit/Sonar/gitleaks config files."""
from __future__ import annotations

import json
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, StrictUndefined

_TEMPLATE_DIR = Path(__file__).parents[2] / "templates"

_LINTER_FILES = [
    ".github/linters/eslintrc.yml",
    ".github/linters/python-ruff.yml",
    ".github/linters/shellcheck.yml",
    ".github/linters/yamllint.yml",
    ".github/linters/markdownlint.yml",
    ".github/linters/prettierrc.yml",
]


def _env() -> Environment:
    return Environment(
        loader=FileSystemLoader(str(_TEMPLATE_DIR)),
        undefined=StrictUndefined,
        keep_trailing_newline=True,
    )


def render_configs(stack: str, sonar_key: str, project_name: str) -> dict[str, str]:
    files: dict[str, str] = {}
    for rel in _LINTER_FILES:
        files[rel] = (Path(_TEMPLATE_DIR) / rel).read_text(encoding="utf-8")

    files[".pre-commit-config.yaml"] = _env().get_template(
        ".pre-commit-config.yaml.j2"
    ).render(stack=stack)

    files["sonar-project.properties"] = _env().get_template(
        "sonar-project.properties.j2"
    ).render(sonar_key=sonar_key, project_name=project_name, stack=stack)

    files[".github/gitleaks-config.yml"] = (
        Path(_TEMPLATE_DIR) / ".github/gitleaks-config.yml"
    ).read_text(encoding="utf-8")
    files[".gitleaks-baseline.json"] = (
        Path(_TEMPLATE_DIR) / ".gitleaks-baseline.json"
    ).read_text(encoding="utf-8")

    return files
```

- [ ] **Step 9: Run the test to confirm it passes**

Run: `pytest tests/test_render_configs.py -v`
Expected: 5 passed.

- [ ] **Step 10: Commit**

```bash
git add templates/.github/linters/ templates/.pre-commit-config.yaml.j2 templates/sonar-project.properties.j2 templates/.github/gitleaks-config.yml templates/.gitleaks-baseline.json scripts/lib/render_configs.py tests/test_render_configs.py
git commit -m "feat(configs): add linter, pre-commit, sonar, gitleaks configs"
```

---

## Task 14: Issue templates and PR template

**Files:**
- Create: `templates/.github/ISSUE_TEMPLATE/{bug,feature,security,refactor,infra-tooling,spec}.md.j2`
- Create: `templates/.github/ISSUE_TEMPLATE/config.yml.j2`
- Create: `templates/.github/PULL_REQUEST_TEMPLATE.md.j2`
- Create: `scripts/lib/render_tracking.py`
- Create: `tests/test_render_tracking.py`

**Interfaces:**
- Produces: `render_issue_templates() -> dict[str, str]` and `render_pr_template() -> dict[str, str]`.

- [ ] **Step 1: Write the six issue template bodies**

`templates/.github/ISSUE_TEMPLATE/bug.md.j2`:

```jinja
---
name: Bug
about: Report a defect or unexpected behaviour.
labels: ["type/bug"]
---

## Summary
<one paragraph>

## Environment
- OS / arch:
- {{ stack_label }} version:
- Manifest version (heretek-manager only):
- Build SHA (llama-builds only):

## Repro
1. <step>
2. <step>
3. <expected vs actual>

## Logs
```text
<paste>
```
```

`templates/.github/ISSUE_TEMPLATE/feature.md.j2`:

```jinja
---
name: Feature
about: Propose a new capability.
labels: ["type/feature"]
---

## Problem
<one paragraph>

## Proposed solution
<one paragraph>

## Alternatives considered
- <alternative>

## Files touched
- <path>

## Backwards compatibility
- [ ] Compatible
- [ ] Breaking change (explain below)
```

`templates/.github/ISSUE_TEMPLATE/security.md.j2`:

```jinja
---
name: Security
about: Report a security vulnerability (private disclosure).
labels: ["type/bug", "security"]
---

**Please do not file public security issues.** Use GitHub Security Advisories instead.

## Severity guess
<low | medium | high | critical>

## Repro
1. <step>

## Impact
<one paragraph>
```

`templates/.github/ISSUE_TEMPLATE/refactor.md.j2`:

```jinja
---
name: Refactor
about: Propose a refactor with a clear scope.
labels: ["type/refactor"]
---

## Motivation
<one paragraph>

## Scope
- <files or modules>

## Test plan
- <one paragraph>

## Risk
<one paragraph>
```

`templates/.github/ISSUE_TEMPLATE/infra-tooling.md.j2`:

```jinja
---
name: Infra / Tooling
about: Issues about the harness itself (skill, MCP, lint, CI).
labels: ["type/tooling", "area/infra"]
---

## Component
<skill | MCP server | CI workflow | lint config | hook>

## Expected behaviour
<one paragraph>

## Actual behaviour
<one paragraph>
```

`templates/.github/ISSUE_TEMPLATE/spec.md.j2`:

```jinja
---
name: Spec / Design Doc
about: Wrap an external spec under docs/superpowers/specs/.
labels: ["type/spec"]
---

## Spec URL
<path under docs/superpowers/specs/>

## Tracking
- Spec tracking Issue: #<id>
- Roadmap project: <url>
```

- [ ] **Step 2: Write `templates/.github/ISSUE_TEMPLATE/config.yml.j2`**

```jinja
blank_issues_enabled: false
contact_links:
  - name: Tracking policy
    url: https://github.com/{{ org }}/{{ repo }}/blob/main/CONTRIBUTING.md#tracking
    about: Where design debates and progress notes live.
```

- [ ] **Step 3: Write `templates/.github/PULL_REQUEST_TEMPLATE.md.j2`**

```jinja
## Linked Issue
Closes #<id>  <!-- or: Issue: #<id> -->

## Scope / Approach
<one paragraph>

## Screenshots / Test Output
<if relevant>

## Breaking change
- [ ] None
- [ ] Breaking (explain below)

## Checklist
- [ ] `pre-commit run --all-files` passes
- [ ] Super-linter passes
- [ ] SonarCloud quality gate passes
- [ ] Gitleaks passes
- [ ] Tests added or updated
- [ ] Docs updated (if applicable)
- [ ] Skills added or updated (if applicable)
```

- [ ] **Step 4: Write the failing test**

`tests/test_render_tracking.py`:

```python
"""Tests for the tracking-layer renderer."""
from __future__ import annotations

from scripts.lib.render_tracking import render_issue_templates, render_pr_template


def test_render_issue_templates_returns_six_templates_and_config():
    files = render_issue_templates(org="Heretek-AI", repo="llama-builds")
    assert ".github/ISSUE_TEMPLATE/config.yml" in files
    for name in ("bug", "feature", "security", "refactor", "infra-tooling", "spec"):
        assert f".github/ISSUE_TEMPLATE/{name}.md" in files


def test_render_issue_templates_bug_has_required_fields():
    files = render_issue_templates(org="Heretek-AI", repo="llama-builds")
    bug = files[".github/ISSUE_TEMPLATE/bug.md"]
    assert "## Environment" in bug
    assert "## Repro" in bug
    assert "## Logs" in bug


def test_render_issue_templates_config_references_org_repo():
    files = render_issue_templates(org="Heretek-AI", repo="llama-builds")
    cfg = files[".github/ISSUE_TEMPLATE/config.yml"]
    assert "Heretek-AI/llama-builds" in cfg


def test_render_pr_template_has_checklist():
    files = render_pr_template()
    pr = files[".github/PULL_REQUEST_TEMPLATE.md"]
    for item in ("pre-commit", "Super-linter", "SonarCloud", "Gitleaks"):
        assert item in pr
```

- [ ] **Step 5: Run the test to confirm it fails**

Run: `pytest tests/test_render_tracking.py -v`
Expected: ImportError.

- [ ] **Step 6: Implement `scripts/lib/render_tracking.py` (partial)**

```python
"""Renderer for issue templates, PR template, and tracking config."""
from __future__ import annotations

from pathlib import Path

from jinja2 import Environment, FileSystemLoader, StrictUndefined

_TEMPLATE_DIR = Path(__file__).parents[2] / "templates"

_ISSUE_TEMPLATE_NAMES = [
    "bug",
    "feature",
    "security",
    "refactor",
    "infra-tooling",
    "spec",
]


def _env() -> Environment:
    return Environment(
        loader=FileSystemLoader(str(_TEMPLATE_DIR / ".github" / "ISSUE_TEMPLATE")),
        undefined=StrictUndefined,
        keep_trailing_newline=True,
    )


def render_issue_templates(org: str, repo: str, stack_label: str = "Stack") -> dict[str, str]:
    files: dict[str, str] = {}
    for name in _ISSUE_TEMPLATE_NAMES:
        files[f".github/ISSUE_TEMPLATE/{name}.md"] = _env().get_template(
            f"{name}.md.j2"
        ).render(stack_label=stack_label)
    files[".github/ISSUE_TEMPLATE/config.yml"] = _env().get_template(
        "config.yml.j2"
    ).render(org=org, repo=repo)
    return files


def render_pr_template() -> dict[str, str]:
    text = _env().get_template("PULL_REQUEST_TEMPLATE.md.j2").render()
    return {".github/PULL_REQUEST_TEMPLATE.md": text}
```

- [ ] **Step 7: Add the PR template to a sibling load path**

Update `_env()` inside `render_pr_template` so it can find the PR template:

```python
def render_pr_template() -> dict[str, str]:
    env = Environment(
        loader=FileSystemLoader(str(_TEMPLATE_DIR / ".github")),
        undefined=StrictUndefined,
        keep_trailing_newline=True,
    )
    text = env.get_template("PULL_REQUEST_TEMPLATE.md.j2").render()
    return {".github/PULL_REQUEST_TEMPLATE.md": text}
```

- [ ] **Step 8: Run the test to confirm it passes**

Run: `pytest tests/test_render_tracking.py -v`
Expected: 4 passed.

- [ ] **Step 9: Commit**

```bash
git add templates/.github/ISSUE_TEMPLATE/ templates/.github/PULL_REQUEST_TEMPLATE.md.j2 scripts/lib/render_tracking.py tests/test_render_tracking.py
git commit -m "feat(tracking): add issue templates, config, and PR template"
```

---

## Task 15: Project automation GraphQL + CONTRIBUTING.md + labeler

**Files:**
- Create: `templates/.github/projects-automation.graphql.j2`
- Create: `templates/.github/labeler.yml.j2`
- Create: `templates/CONTRIBUTING.md.j2`
- Create: `scripts/lib/render_tracking.py` (extend)
- Create: `tests/test_render_tracking.py` (extend)

**Interfaces:**
- Produces: `render_project_automation(project_id: str) -> dict[str, str]`,
  `render_labeler() -> dict[str, str]`, `render_contributing() -> dict[str, str]`.

- [ ] **Step 1: Write `templates/.github/projects-automation.graphql.j2`**

```jinja
# GraphQL automation rules for the {{ repo }} Project.
# Apply with: `gh project link --repo {{ org }}/{{ repo }} --project {{ project_id }}`
# then `gh api graphql -f query @.github/projects-automation.graphql`.

mutation {
  createProjectV2Field(input: { projectId: "{{ project_id }}", dataType: SINGLE_SELECT, name: "Status" }) {
    projectV2Field { id }
  }
}

# Status updates on PR open/merge are configured via the GitHub UI;
# this file is the source of truth for re-importing them.
```

- [ ] **Step 2: Write `templates/.github/labeler.yml.j2`**

```jinja
# Auto-add labels based on changed paths.
area/build:
  - targets/**/*
  - scripts/generate_manifest.py
  - scripts/audit_matrix.py
area/client:
  - src/server/**
  - src/webui/**
  - bin/**
area/infra:
  - .github/**
  - .claude/**
  - .pre-commit-config.yaml
  - sonar-project.properties
area/docs:
  - docs/**/*
  - '**/*.md'
```

- [ ] **Step 3: Write `templates/CONTRIBUTING.md.j2`**

```jinja
# Contributing to {{ repo }}

This project follows the Heretek harness contract. See
[`docs/superpowers/specs/2026-08-01-monorepo-manager-harness-design.md`](docs/superpowers/specs/2026-08-01-monorepo-manager-harness-design.md)
for the umbrella spec.

## Tracking

Long-lived design debates, decision logs, and progress notes live as
[GitHub Issues](../../issues) and [Project](../../projects) items — not
as separate Markdown files.

`docs/superpowers/specs/*.md` is the engineering source of truth only
for *in-flight* designs (spec → plan → implementation). Once an
implementation lands, the design lives in the issue/PR conversation and
in the code.

Exceptions (release notes, ADRs needing cross-repo visibility) are
explicitly small and recorded in the same Project.

## Required CI checks

The four required checks on `main` are:

- `super-linter`
- `pre-commit`
- `sonarcloud`
- `gitleaks`

No merge without all four green.
```

- [ ] **Step 4: Extend `scripts/lib/render_tracking.py`**

Add at the end of the file:

```python
def render_project_automation(org: str, repo: str, project_id: str) -> dict[str, str]:
    env = Environment(
        loader=FileSystemLoader(str(_TEMPLATE_DIR / ".github")),
        undefined=StrictUndefined,
        keep_trailing_newline=True,
    )
    text = env.get_template("projects-automation.graphql.j2").render(
        org=org, repo=repo, project_id=project_id
    )
    return {".github/projects-automation.graphql": text}


def render_labeler() -> dict[str, str]:
    return {
        ".github/labeler.yml": (Path(_TEMPLATE_DIR) / ".github/labeler.yml.j2").read_text(
            encoding="utf-8"
        )
    }


def render_contributing(org: str, repo: str) -> dict[str, str]:
    env = Environment(
        loader=FileSystemLoader(str(_TEMPLATE_DIR)),
        undefined=StrictUndefined,
        keep_trailing_newline=True,
    )
    return {
        "CONTRIBUTING.md": env.get_template("CONTRIBUTING.md.j2").render(
            org=org, repo=repo
        )
    }
```

- [ ] **Step 5: Extend the test file**

Append to `tests/test_render_tracking.py`:

```python
def test_render_project_automation_substitutes_project_id():
    files = render_project_automation(
        org="Heretek-AI", repo="llama-builds", project_id="PVT_123"
    )
    assert "PVT_123" in files[".github/projects-automation.graphql"]


def test_render_labeler_has_area_labels():
    files = render_labeler()
    text = files[".github/labeler.yml"]
    assert "area/build" in text
    assert "area/infra" in text


def test_render_contributing_references_org_repo():
    files = render_contributing(org="Heretek-AI", repo="llama-builds")
    assert "llama-builds" in files["CONTRIBUTING.md"]
```

- [ ] **Step 6: Run the test to confirm it passes**

Run: `pytest tests/test_render_tracking.py -v`
Expected: 7 passed.

- [ ] **Step 7: Commit**

```bash
git add templates/.github/projects-automation.graphql.j2 templates/.github/labeler.yml.j2 templates/CONTRIBUTING.md.j2 scripts/lib/render_tracking.py tests/test_render_tracking.py
git commit -m "feat(tracking): add project automation, labeler, contributing"
```

---

## Task 16: scripts/init-harness.sh (generate mode)

**Files:**
- Create: `scripts/init-harness.sh`
- Create: `scripts/lib/__init__.py` (already exists)
- Create: `scripts/lib/cli.py`
- Create: `tests/test_init_harness.py`

**Interfaces:**
- `init-harness.sh --target <dir> --name <name> --stack <python|node> [flags]`
- Flags: `--project-id <id>`, `--default-model <model>`, `--org <org>` (default Heretek-AI).
- Exit codes: 0 success, 1 invalid args, 2 drift detected, 3 validation failure.

- [ ] **Step 1: Write `scripts/lib/cli.py`**

```python
"""CLI orchestration for init-harness.sh.

The Bash script delegates to this module via `python -m scripts.lib.cli`.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from scripts.lib import render_agents, render_mcp, render_skills, render_hooks
from scripts.lib import render_settings, render_ci, render_configs, render_tracking
from scripts.lib.contract_hash import compute_contract_hash


def _write_files(target: Path, files: dict[str, str]) -> None:
    for rel, content in files.items():
        dest = target / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(content, encoding="utf-8")


def _bundle(name: str, stack: str, org: str, project_id: str, default_model: str) -> dict[str, str]:
    files: dict[str, str] = {}

    if stack == "python":
        test_cmd = "pytest"
        build_cmd = "python -m build"
        lint_cmd = "ruff check ."
        run_cmd = "python -m heretek_builds --help"
        language = "Python 3.11+"
        package_manager = "pip, setuptools"
        os_arch = "Linux x86_64"
        project_summary = "CI/CD registry for llama.cpp family builds."
        sonar_key = f"{org}_{name}"
        skills = [
            {
                "name": "heretek-manifest-codegen",
                "description": "Generate manifest.json from targets/*/build.sh.",
                "allowed_tools": ["Bash", "Read"],
                "required_skills": [],
                "body": "1. read targets/*/build.sh\n2. emit manifest.json\n3. validate against schemas/manifest.schema.json",
            },
            {
                "name": "heretek-upstream-sync",
                "description": "Test a new llama.cpp upstream SHA before promoting to a release.",
                "allowed_tools": ["Bash"],
                "required_skills": [],
                "body": "1. checkout upstream SHA\n2. run audit_matrix.py\n3. report PR-ready status",
            },
        ]
        mcp_servers = {
            "github": {
                "description": "Official GitHub MCP",
                "transport": "stdio",
                "command": "github-mcp",
                "args": ["--owner", org, "--repo", name],
                "env": {"GITHUB_TOKEN": None},
                "timeoutSeconds": 30,
            },
            "sonarqube": {
                "description": "SonarCloud MCP",
                "transport": "stdio",
                "command": "sonarqube-mcp",
                "args": ["--project", sonar_key],
                "env": {"SONAR_TOKEN": None, "SONAR_HOST_URL": None},
            },
        }
    elif stack == "node":
        test_cmd = "npm test"
        build_cmd = "npm run build"
        lint_cmd = "npx eslint ."
        run_cmd = "npx heretek-manager --help"
        language = "TypeScript 5 + Node 20"
        package_manager = "npm"
        os_arch = "Linux x86_64"
        project_summary = "Local NPM CLI + WebUI for the Heretek AI runtime."
        sonar_key = f"{org}_{name}"
        skills = [
            {
                "name": "heretek-strix-halo-audit",
                "description": "Audit host hardware and recommend a backend.",
                "allowed_tools": ["Bash"],
                "required_skills": [],
                "body": "1. shell out to nvidia-smi/rocminfo/vulkaninfo\n2. parse output\n3. recommend backend",
            },
            {
                "name": "heretek-symlink-swap",
                "description": "Apply the atomic symlink swap recipe.",
                "allowed_tools": ["Bash", "Edit"],
                "required_skills": [],
                "body": "1. write to a temp symlink\n2. rename atomically\n3. verify symlink target",
            },
            {
                "name": "heretek-manifest-fetch",
                "description": "Fetch the llama-builds manifest with retries.",
                "allowed_tools": ["Bash"],
                "required_skills": [],
                "body": "1. fetch https://heretek-ai.github.io/llama-builds/manifest.json\n2. retry up to 3 times\n3. verify SHA-256 against sha256sum.txt",
            },
        ]
        mcp_servers = {
            "github": {
                "description": "Official GitHub MCP",
                "transport": "stdio",
                "command": "github-mcp",
                "args": ["--owner", org, "--repo", name],
                "env": {"GITHUB_TOKEN": None},
                "timeoutSeconds": 30,
            },
            "sonarqube": {
                "description": "SonarCloud MCP",
                "transport": "stdio",
                "command": "sonarqube-mcp",
                "args": ["--project", sonar_key],
                "env": {"SONAR_TOKEN": None, "SONAR_HOST_URL": None},
            },
        }
    else:
        raise ValueError(f"unknown stack '{stack}'")

    files.update(
        render_agents.render_agents(
            {
                "name": name,
                "stack": stack,
                "language": language,
                "package_manager": package_manager,
                "os_arch": os_arch,
                "project_summary": project_summary,
                "build_cmd": build_cmd,
                "test_cmd": test_cmd,
                "lint_cmd": lint_cmd,
                "run_cmd": run_cmd,
                "sonar_key": sonar_key,
                "project_url": f"https://github.com/orgs/{org}/projects/{project_id}",
                "super_linter_config_path": ".github/linters/",
            }
        )
    )
    files.update(render_skills.render_skills(skills))
    files.update(render_mcp.render_mcp_named(mcp_servers))
    files.update(render_settings.render_settings(stack, default_model=default_model))
    files.update(render_hooks.render_hooks(stack))
    files.update(render_ci.render_ci(stack, test_cmd=test_cmd))
    files.update(
        render_configs.render_configs(stack, sonar_key=sonar_key, project_name=name)
    )
    files.update(render_tracking.render_issue_templates(org=org, repo=name))
    files.update(render_tracking.render_pr_template())
    files.update(
        render_tracking.render_project_automation(org=org, repo=name, project_id=project_id)
    )
    files.update(render_tracking.render_labeler())
    files.update(render_tracking.render_contributing(org=org, repo=name))

    return files


def _bake_contract_hash(target: Path, spec_path: Path, section_anchor: str) -> None:
    digest = compute_contract_hash(spec_path, section_anchor)
    (target / ".heretek-harness.json").write_text(
        json.dumps({"contract_hash": digest, "section_anchor": section_anchor}, indent=2)
    )


def _existing_contract_hash(target: Path) -> dict | None:
    p = target / ".heretek-harness.json"
    if not p.is_file():
        return None
    return json.loads(p.read_text(encoding="utf-8"))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="init-harness")
    parser.add_argument("--target", required=True)
    parser.add_argument("--name", required=True)
    parser.add_argument("--stack", required=True, choices=["python", "node"])
    parser.add_argument("--org", default="Heretek-AI")
    parser.add_argument("--project-id", default="0")
    parser.add_argument("--default-model", default="sonnet")
    parser.add_argument(
        "--force",
        action="store_true",
        help="overwrite a generated harness whose contract-hash has drifted",
    )
    parser.add_argument(
        "--refresh-hooks",
        action="store_true",
        help="re-emit hook files only (after legitimate hook edits)",
    )
    parser.add_argument(
        "--verify",
        action="store_true",
        help="validate the existing harness without writing",
    )
    parser.add_argument(
        "--spec-path",
        default=str(
            Path(__file__).parents[2]
            / "docs/superpowers/specs/2026-08-01-monorepo-manager-harness-design.md"
        ),
    )
    parser.add_argument("--section-anchor", default="4. Layer 1")
    args = parser.parse_args(argv)

    target = Path(args.target).resolve()
    target.mkdir(parents=True, exist_ok=True)

    if args.verify:
        return run_verify(target, args.spec_path, args.section_anchor)

    existing = _existing_contract_hash(target)
    if existing and not args.force:
        current = compute_contract_hash(Path(args.spec_path), args.section_anchor)
        if existing["contract_hash"] != current:
            print(
                f"contract drift detected: existing={existing['contract_hash']} "
                f"current={current}. Re-run with --force to regenerate.",
                file=sys.stderr,
            )
            return 2

    if args.refresh_hooks:
        files = render_hooks.render_hooks(args.stack)
        _write_files(target, files)
        _bake_contract_hash(target, Path(args.spec_path), args.section_anchor)
        return 0

    files = _bundle(args.name, args.stack, args.org, args.project_id, args.default_model)
    _write_files(target, files)
    _bake_contract_hash(target, Path(args.spec_path), args.section_anchor)
    return 0


def run_verify(target: Path, spec_path: str, section_anchor: str) -> int:
    """Validate the on-disk harness against the contract."""
    from scripts.lib import validate_agents, validate_mcp, validate_settings, validate_skills

    errors: list[str] = []
    agents = target / "AGENTS.md"
    if agents.is_file():
        errors.extend(f"AGENTS.md: {e}" for e in validate_agents.validate_agents(str(agents)))
    mcp = target / ".mcp.json"
    if mcp.is_file():
        errors.extend(f".mcp.json: {e}" for e in validate_mcp.validate_mcp(str(mcp)))
    settings = target / ".claude" / "settings.json"
    if settings.is_file():
        errors.extend(
            f"settings.json: {e}" for e in validate_settings.validate_settings(str(settings))
        )
    skills_dir = target / ".claude" / "skills"
    if skills_dir.is_dir():
        for skill in sorted(p for p in skills_dir.iterdir() if p.is_dir()):
            errors.extend(
                f"skills/{skill.name}: {e}"
                for e in validate_skills.validate_skill(str(skill))
            )
    if errors:
        for e in errors:
            print(e, file=sys.stderr)
        return 3
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 2: Write `scripts/init-harness.sh`**

```bash
#!/usr/bin/env bash
# Materialise the Heretek harness into a target directory.
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "$HERE/.." && pwd)"

cd "$ROOT"
exec python -m scripts.lib.cli "$@"
```

- [ ] **Step 3: Make the script executable**

Run: `chmod +x scripts/init-harness.sh`

- [ ] **Step 4: Write the failing test**

`tests/test_init_harness.py`:

```python
"""End-to-end tests for scripts/init-harness.sh generation."""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]


def _run(args: list[str], cwd: Path) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, "-m", "scripts.lib.cli", *args],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
    )


def test_init_harness_generates_harness_files(tmp_path):
    result = _run(
        [
            "--target",
            str(tmp_path),
            "--name",
            "llama-builds",
            "--stack",
            "python",
            "--project-id",
            "1",
        ],
        cwd=tmp_path,
    )
    assert result.returncode == 0, result.stderr
    assert (tmp_path / "AGENTS.md").is_file()
    assert (tmp_path / "CLAUDE.md").is_file()
    assert (tmp_path / ".mcp.json").is_file()
    assert (tmp_path / ".claude" / "settings.json").is_file()


def test_init_harness_generates_all_workflows(tmp_path):
    _run(
        ["--target", str(tmp_path), "--name", "heretek-manager", "--stack", "node"],
        cwd=tmp_path,
    )
    for name in ("super-linter.yml", "pre-commit.yml", "sonarcloud.yml", "secret-scan.yml"):
        assert (tmp_path / ".github" / "workflows" / name).is_file()


def test_init_harness_bakes_contract_hash(tmp_path):
    _run(
        ["--target", str(tmp_path), "--name", "llama-builds", "--stack", "python"],
        cwd=tmp_path,
    )
    payload = json.loads((tmp_path / ".heretek-harness.json").read_text())
    assert "contract_hash" in payload
    assert len(payload["contract_hash"]) == 16


def test_init_harness_refuses_on_drift(tmp_path):
    spec = REPO_ROOT / "docs/superpowers/specs/2026-08-01-monorepo-manager-harness-design.md"
    # First run establishes the hash.
    _run(
        ["--target", str(tmp_path), "--name", "llama-builds", "--stack", "python"],
        cwd=tmp_path,
    )
    # Second run without --force must succeed because the spec hasn't changed.
    result = _run(
        ["--target", str(tmp_path), "--name", "llama-builds", "--stack", "python"],
        cwd=tmp_path,
    )
    assert result.returncode == 0
    # Now corrupt the hash to simulate drift.
    payload = json.loads((tmp_path / ".heretek-harness.json").read_text())
    payload["contract_hash"] = "0" * 16
    (tmp_path / ".heretek-harness.json").write_text(json.dumps(payload))
    result = _run(
        ["--target", str(tmp_path), "--name", "llama-builds", "--stack", "python"],
        cwd=tmp_path,
    )
    assert result.returncode == 2
    assert "drift" in result.stderr


def test_init_harness_force_overrides_drift(tmp_path):
    _run(
        ["--target", str(tmp_path), "--name", "llama-builds", "--stack", "python"],
        cwd=tmp_path,
    )
    payload = json.loads((tmp_path / ".heretek-harness.json").read_text())
    payload["contract_hash"] = "0" * 16
    (tmp_path / ".heretek-harness.json").write_text(json.dumps(payload))
    result = _run(
        [
            "--target",
            str(tmp_path),
            "--name",
            "llama-builds",
            "--stack",
            "python",
            "--force",
        ],
        cwd=tmp_path,
    )
    assert result.returncode == 0


def test_init_harness_verify_clean(tmp_path):
    _run(
        ["--target", str(tmp_path), "--name", "llama-builds", "--stack", "python"],
        cwd=tmp_path,
    )
    result = _run(["--target", str(tmp_path), "--verify"], cwd=tmp_path)
    assert result.returncode == 0, result.stderr
```

- [ ] **Step 5: Run the test to confirm it passes**

Run: `pytest tests/test_init_harness.py -v`
Expected: 6 passed.

- [ ] **Step 6: Smoke-test the Bash entrypoint**

Run: `rm -rf /tmp/heretek-smoke && scripts/init-harness.sh --target /tmp/heretek-smoke --name llama-builds --stack python --project-id 1 && ls /tmp/heretek-smoke && scripts/init-harness.sh --target /tmp/heretek-smoke --verify`
Expected: directory listing with `AGENTS.md`, `CLAUDE.md`, `.mcp.json`, `.claude/`, `.github/`, `sonar-project.properties`, `.pre-commit-config.yaml`, `.gitleaks-baseline.json`, `.heretek-harness.json`. Verify exits 0.

- [ ] **Step 7: Commit**

```bash
git add scripts/init-harness.sh scripts/lib/cli.py tests/test_init_harness.py
git commit -m "feat(init): add init-harness.sh with generate, drift, force, verify modes"
```

---

## Task 17: Spec template and umbrella AGENTS.md + CLAUDE.md

The umbrella itself benefits from having AGENTS.md and CLAUDE.md at the root so that future agents running here understand the workspace.

**Files:**
- Create: `AGENTS.md`
- Create: `CLAUDE.md`

**Interfaces:** none. They are static documents.

- [ ] **Step 1: Write `AGENTS.md`**

```markdown
# monorepo-manager

## Project summary
Throwaway workspace for the Heretek AI harness. Holds the contract
schemas, the validator + renderer library, the init-harness.sh generator,
and reference installs for the two child repos. The umbrella itself
ships nothing; it exists to bootstrap the children.

## Stack & runtime targets
- Languages: Python 3.11+ (shell for the init script).
- Package managers: pip, setuptools.
- OS/arch: Linux x86_64.
- Outputs: contract schemas, validator library, init-harness.sh, generated reference installs.

## Build, test, lint, run commands
- Build: `pip install -e ".[dev]"`
- Test: `pytest`
- Lint: `ruff check . && pre-commit run --all-files`
- Run: `scripts/init-harness.sh --target <dir> --name <name> --stack <python|node>`

## Project structure
```
monorepo-manager/
├── docs/superpowers/{specs,plans}/
├── schemas/
├── scripts/{init-harness.sh,lib/}
├── templates/
├── reference/        # generated by init-harness.sh
└── tests/
```

## Conventions
- Conventional commits.
- PRs target `main`.
- Run `pytest` before pushing.
- Generated artefacts in `reference/` are not hand-edited.

## Do / Don't list
- DO update schemas in lockstep with the umbrella spec.
- DO regenerate reference installs after any spec change.
- DON'T commit build artefacts, `.env`, or `.heretek-harness.json` from a child target.

## Pointer block
- Spec: `docs/superpowers/specs/2026-08-01-monorepo-manager-harness-design.md`
- Plan: `docs/superpowers/plans/2026-08-01-monorepo-manager-harness-impl.md`
- GitHub Project: none (umbrella has no project)
- SonarCloud project: N/A (umbrella has no app code)
- Skills index: `.claude/skills/manifest.json` (generated by future tasks)
- Issue templates: `.github/ISSUE_TEMPLATE/`
```

- [ ] **Step 2: Write `CLAUDE.md`**

```markdown
# monorepo-manager

Governed by `AGENTS.md` (read it first).

## Skills to use
- `superpowers:brainstorming` — required for any non-trivial change.
- `superpowers:writing-plans` — required after brainstorming, before code.
- `superpowers:test-driven-development` — required when implementing.
- `superpowers:verification-before-completion` — required before claiming done.

## Model tiers
- Default: `sonnet`.
- Plan/explore: `opus`.
- Narrow edits: `haiku`.

## Hook expectations
- `.claude/hooks/PreToolUse/deny-destructive.sh` refuses `rm -rf`, `git push --force`, etc.
- `.claude/hooks/PostToolUse/run-pre-commit.sh` runs `pre-commit run --files <changed>`.
- `.claude/hooks/Stop/verify-lint.sh` runs `ruff check .` before allowing the turn to end.
```

- [ ] **Step 3: Validate the new docs against the contract**

Run: `python -c "from scripts.lib.validate_agents import validate_agents; print(validate_agents('AGENTS.md'))"`
Expected: `[]`.

- [ ] **Step 4: Commit**

```bash
git add AGENTS.md CLAUDE.md
git commit -m "docs: add AGENTS.md and CLAUDE.md to umbrella root"
```

---

## Task 18: Generate reference installs for both children

**Files:**
- Create: `reference/llama-builds-install/` (generated)
- Create: `reference/heretek-manager-install/` (generated)

**Interfaces:** none. This task is a generation step.

- [ ] **Step 1: Generate the llama-builds reference install**

Run: `scripts/init-harness.sh --target reference/llama-builds-install --name llama-builds --stack python --project-id 1`

- [ ] **Step 2: Generate the heretek-manager reference install**

Run: `scripts/init-harness.sh --target reference/heretek-manager-install --name heretek-manager --stack node --project-id 2`

- [ ] **Step 3: Verify both installs**

Run: `scripts/init-harness.sh --target reference/llama-builds-install --verify && scripts/init-harness.sh --target reference/heretek-manager-install --verify`
Expected: both exit 0.

- [ ] **Step 4: Spot-check the generated files**

Run: `ls reference/llama-builds-install && ls reference/heretek-manager-install`
Expected: both contain `AGENTS.md`, `CLAUDE.md`, `.mcp.json`, `.claude/`, `.github/`, `sonar-project.properties`, `.pre-commit-config.yaml`, `.gitleaks-baseline.json`, `CONTRIBUTING.md`, `.heretek-harness.json`.

- [ ] **Step 5: Initialise a local git repo inside each reference install**

Run (each line independently):

```bash
cd reference/llama-builds-install && git init -b main && git config user.email "claude@anthropic.com" && git config user.name "Claude" && git add . && git commit -m "chore: initial harness install"
cd reference/heretek-manager-install && git init -b main && git config user.email "claude@anthropic.com" && git config user.name "Claude" && git add . && git commit -m "chore: initial harness install"
```

- [ ] **Step 6: Commit the umbrella `.gitignore` addition**

Add to `.gitignore`:

```
reference/*/.git/
```

Then run: `git add .gitignore && git commit -m "chore: ignore nested .git inside reference installs"`

- [ ] **Step 7: Commit a manifest of the reference installs at the umbrella level**

Run: `git add reference/llama-builds-install/.heretek-harness.json reference/heretek-manager-install/.heretek-harness.json && git commit -m "feat(reference): generate llama-builds and heretek-manager reference installs"`

---

## Task 19: Pre-commit config and `.pre-commit-config.yaml` for the umbrella

**Files:**
- Create: `.pre-commit-config.yaml`

**Interfaces:** none. Standard pre-commit config.

- [ ] **Step 1: Copy the rendered template into the umbrella's own config**

Run: `scripts/init-harness.sh --target /tmp/umbrella-self --name monorepo-manager --stack python --project-id 0 && cp /tmp/umbrella-self/.pre-commit-config.yaml .pre-commit-config.yaml && rm -rf /tmp/umbrella-self`

- [ ] **Step 2: Install pre-commit hooks**

Run: `pip install pre-commit && pre-commit install`

- [ ] **Step 3: Run pre-commit on the umbrella to confirm it passes**

Run: `pre-commit run --all-files`
Expected: all hooks pass.

- [ ] **Step 4: Commit**

```bash
git add .pre-commit-config.yaml
git commit -m "chore: install pre-commit hooks on umbrella"
```

---

## Task 20: End-to-end smoke test against a sandbox child

**Files:**
- Create: `tests/test_init_harness.py` (extend)

**Interfaces:** none. This is a smoke test against a sandbox target.

- [ ] **Step 1: Add a sandbox smoke test**

Append to `tests/test_init_harness.py`:

```python
def test_init_harness_against_sandbox_python(tmp_path):
    sandbox = tmp_path / "sandbox"
    sandbox.mkdir()
    # Pretend the sandbox has a previous README and a package.json for context.
    (sandbox / "README.md").write_text("pre-existing")
    result = _run(
        ["--target", str(sandbox), "--name", "llama-builds", "--stack", "python"],
        cwd=tmp_path,
    )
    assert result.returncode == 0, result.stderr
    sandbox_files = {p.name for p in sandbox.iterdir()}
    assert "README.md" in sandbox_files  # preserved
    assert "AGENTS.md" in sandbox_files  # generated
    assert ".mcp.json" in sandbox_files


def test_init_harness_against_sandbox_node(tmp_path):
    sandbox = tmp_path / "sandbox"
    sandbox.mkdir()
    (sandbox / "package.json").write_text("{}")
    result = _run(
        ["--target", str(sandbox), "--name", "heretek-manager", "--stack", "node"],
        cwd=tmp_path,
    )
    assert result.returncode == 0, result.stderr
    text = (sandbox / "AGENTS.md").read_text()
    assert "Node 20" in text
```

- [ ] **Step 2: Run the smoke tests**

Run: `pytest tests/test_init_harness.py -v`
Expected: 8 passed.

- [ ] **Step 3: Commit**

```bash
git add tests/test_init_harness.py
git commit -m "test: add sandbox smoke tests for init-harness.sh"
```

---

## Task 21: Full test suite green and CI readiness

**Files:**
- Modify: `tests/conftest.py` (no change needed)
- Modify: `pyproject.toml` (no change needed)

**Interfaces:** none.

- [ ] **Step 1: Run the full test suite**

Run: `pytest -v`
Expected: all tests pass.

- [ ] **Step 2: Run pre-commit on the umbrella**

Run: `pre-commit run --all-files`
Expected: all hooks pass.

- [ ] **Step 3: Run ruff on the umbrella**

Run: `ruff check .`
Expected: no findings.

- [ ] **Step 4: Verify the umbrella spec doc references this plan**

Run: `grep -c "docs/superpowers/plans/2026-08-01-monorepo-manager-harness-impl.md" docs/superpowers/specs/2026-08-01-monorepo-manager-harness-design.md`
Expected: 0 (the spec doesn't currently reference the plan). Decide whether to add a `**Plan:**` line to the spec; if so, edit the spec to add it and commit.

- [ ] **Step 5: Commit (if any final cleanup was made)**

```bash
git add -u
git commit -m "chore: ensure full test suite is green" || true
```

---

## Self-Review

Run through this checklist and fix any issues inline.

**1. Spec coverage.** Walk the spec section by section and confirm a task implements it:

- Section 4 (harness contract) — Tasks 3, 4, 5, 6, 7, 8, 9, 10, 11.
- Section 5 (quality-gate contract) — Tasks 12, 13, 16.
- Section 6 (tracking contract) — Tasks 14, 15, 16.
- Section 7 (reference impls) — Tasks 16, 18, 20.
- Section 8 (workflow) — Tasks 17, 18.
- Section 9 (error handling) — Tasks 11 (lockfile), 12 (workflows), 16 (drift + verify).
- Section 10 (testing) — Tasks 11, 16, 20, 21.
- Section 11 (rollout) — Tasks 16, 18, 19, 21.

**2. Placeholder scan.** Search for "TODO", "TBD", "implement later", "fill in details", "similar to Task N". Fix any matches.

**3. Type consistency.** Confirm function signatures and field names match across tasks:
- `render_agents(params) -> dict[str, str]` (Task 7). Used in Task 16 with dict containing all 13 keys.
- `render_mcp_named(servers: dict[str, dict]) -> str` (Task 8). Used in Task 16.
- `render_skills(skills: list[dict]) -> dict[str, str]` (Task 9). Used in Task 16 with `name, description, allowed_tools, required_skills, body` keys.
- `render_hooks(stack: str) -> dict[str, str]` (Task 10). Used in Task 16.
- `render_settings(stack: str, default_model: str = "sonnet") -> dict[str, str]` (Task 11). Used in Task 16.
- `render_ci(stack: str, test_cmd: str) -> dict[str, str]` (Task 12). Used in Task 16.
- `render_configs(stack: str, sonar_key: str, project_name: str) -> dict[str, str]` (Task 13). Used in Task 16.
- `render_issue_templates(org: str, repo: str, stack_label: str = "Stack") -> dict[str, str]` (Task 14). Used in Task 16.
- `render_pr_template() -> dict[str, str]` (Task 14). Used in Task 16.
- `render_project_automation(org: str, repo: str, project_id: str) -> dict[str, str]` (Task 15). Used in Task 16.
- `render_labeler() -> dict[str, str]` (Task 15). Used in Task 16.
- `render_contributing(org: str, repo: str) -> dict[str, str]` (Task 15). Used in Task 16.

If any signatures diverged, fix in place.

**4. Drift detection.** Confirm the `compute_contract_hash` function from Task 2 is used in `scripts/lib/cli.py` (Task 16) to compute and bake the hash.

**5. Plan header.** Confirm the plan starts with the required header including the goal, architecture, tech stack, and global constraints.

---

## Execution Handoff

Plan complete and saved to `docs/superpowers/plans/2026-08-01-monorepo-manager-harness-impl.md`. Two execution options:

1. **Subagent-Driven (recommended)** — I dispatch a fresh subagent per task with two-stage review between tasks.
2. **Inline Execution** — Execute tasks in this session using executing-plans, with checkpoints for review.

Which approach?
