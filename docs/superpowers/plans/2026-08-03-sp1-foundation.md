# SP1 — Foundation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship the foundation that every later sub-project depends on — a public-safe repo, the `catalog.yaml` → `marketplace.json` pipeline, schema validation, plugin scaffolding, and CI — so a clean `/plugin install <name>@heretek` works for all 11 first-party plugins.

**Architecture:** Python 3 scripts under `scripts/` (`generate-marketplace`, `validate`, `new-plugin`) read a single `catalog/catalog.yaml` source of truth and produce `.claude-plugin/marketplace.json`. JSON Schemas for all manifests live in `tests/schemas/` and are enforced by `scripts/validate`. First-party plugins live as relative sources under `plugins/<name>/`. CI runs `scripts/validate` on every PR and asserts `catalog.yaml` → `marketplace.json` diff is zero.

**Tech Stack:** Python 3.10+, PyYAML, jsonschema, pytest. GitHub Actions. Claude Code v2.1.193+ (for the `renames` schema field).

## Global Constraints

These apply to every task in this plan. Copy values verbatim from the spec where given:

- **Marketplace name:** `heretek`. **Owner:** `Heretek-AI` (display name "Heretek").
- **License:** MIT for all first-party code. Vendored third-party components retain their upstream license + NOTICE (D14).
- **Versioning:** No `version` field on first-party plugins. SHA-ride — every marketplace commit = new version (D11, D16).
- **Hooks ownership:** `hooks` plugin is the sole owner of all hooks firing on `Edit`/`Write`/`PreToolUse`/`PostToolUse`/`Notification`. No other plugin ships such hooks (D15).
- **Plugin taxonomy:** 4 task plugins (`rust`, `python`, `js-ts`, `web-frontend`) + 7 cross-cutting plugins (`hooks`, `security`, `skills-pack`, `mcp-pack`, `lsp-pack`, `agents`, `output-styles`).
- **Catalog source of truth:** `catalog/catalog.yaml`. Generated artifact: `.claude-plugin/marketplace.json`. Never hand-edit the generated file (D8).
- **Vetting bar:** any catalog entry with `vetting.status: approved` must have a `vetting.review:` link to `catalog/reviews/<slug>.md` (D7).
- **Python:** 3.10+. Single dep: PyYAML + jsonschema (locked per PLAN.md §14.5).
- **No version on first-party plugin entries** in `marketplace.json` — version field is omitted (D11).

---

## File Structure

Files this plan creates or modifies. Each has one clear responsibility.

| Path | Responsibility |
|---|---|
| `LICENSE` | MIT license text (full SPDX) |
| `.gitignore` | Repo hygiene: excludes personal harness state, secrets, OS/editor files |
| `pyproject.toml` | Python project metadata; declares deps (pyyaml, jsonschema) + dev deps (pytest) |
| `requirements.txt` | Pinned runtime deps for `scripts/` |
| `requirements-dev.txt` | Pinned dev deps (pytest) |
| `scripts/generate_marketplace.py` | Reads `catalog/catalog.yaml`, writes `.claude-plugin/marketplace.json` |
| `scripts/validate.py` | JSON Schema validation for `marketplace.json` + every plugin manifest |
| `scripts/new_plugin.py` | Scaffolds a plugin directory: `plugins/<name>/.claude-plugin/plugin.json`, `README.md`, optional component dirs |
| `scripts/templates/plugin/README.md` | Template README used by `new_plugin.py` |
| `scripts/templates/plugin/plugin.json` | Template `plugin.json` used by `new_plugin.py` |
| `catalog/catalog.yaml` | Source of truth — every plugin, every item |
| `catalog/reviews/0000-template.md` | ADR template for vetting reviews |
| `catalog/rejected.md` | Items that failed D7 vetting + reason |
| `.claude-plugin/marketplace.json` | **Generated** — never hand-edit |
| `tests/__init__.py` | Marks `tests/` as a package (empty) |
| `tests/conftest.py` | Shared pytest fixtures (path constants, fixtures dir) |
| `tests/schemas/marketplace.schema.json` | JSON Schema for `.claude-plugin/marketplace.json` |
| `tests/schemas/plugin.schema.json` | JSON Schema for `.claude-plugin/plugin.json` |
| `tests/schemas/hooks.schema.json` | JSON Schema for `hooks/hooks.json` |
| `tests/schemas/mcp.schema.json` | JSON Schema for `.mcp.json` |
| `tests/schemas/lsp.schema.json` | JSON Schema for `.lsp.json` |
| `tests/fixtures/marketplace/valid.json` | Known-valid marketplace example |
| `tests/fixtures/marketplace/invalid.json` | Known-invalid marketplace example |
| `tests/fixtures/plugin/valid.json` | Known-valid plugin.json example |
| `tests/fixtures/plugin/invalid.json` | Known-invalid plugin.json example |
| `tests/fixtures/hooks/valid.json` | Known-valid hooks.json example |
| `tests/fixtures/hooks/invalid.json` | Known-invalid hooks.json example |
| `tests/fixtures/mcp/valid.json` | Known-valid .mcp.json example |
| `tests/fixtures/mcp/invalid.json` | Known-invalid .mcp.json example |
| `tests/fixtures/lsp/valid.json` | Known-valid .lsp.json example |
| `tests/fixtures/lsp/invalid.json` | Known-invalid .lsp.json example |
| `tests/fixtures/catalog/empty.yaml` | Empty catalog (zero plugins) for generator tests |
| `tests/fixtures/catalog/single_plugin.yaml` | Single-plugin catalog for generator tests |
| `tests/fixtures/catalog/eleven_plugins.yaml` | All 11 first-party plugins as the production seed |
| `tests/test_validate.py` | Tests for `scripts/validate.py` |
| `tests/test_generate_marketplace.py` | Tests for `scripts/generate_marketplace.py` |
| `tests/test_new_plugin.py` | Tests for `scripts/new_plugin.py` |
| `tests/test_schemas_marketplace.py` | Tests for `marketplace.schema.json` |
| `tests/test_schemas_plugin.py` | Tests for `plugin.schema.json` |
| `tests/test_schemas_hooks.py` | Tests for `hooks.schema.json` |
| `tests/test_schemas_mcp.py` | Tests for `mcp.schema.json` |
| `tests/test_schemas_lsp.py` | Tests for `lsp.schema.json` |
| `plugins/<name>/.claude-plugin/plugin.json` | One per first-party plugin (11 files) |
| `plugins/<name>/README.md` | One per first-party plugin (11 files) |
| `.github/workflows/validate.yml` | CI: runs `scripts/validate` + generation diff check |
| `README.md` | Marketplace identity + one-command install instructions |

**Files that change together live together.** All schema tests live next to the schemas they exercise. All generator/validate tests live with the fixtures they consume.

---

## Task 1: Phase 0 — repo hygiene + LICENSE + secret scan

**Files:**
- Create: `LICENSE`
- Modify: `.gitignore` (verify coverage)
- Delete (untracked): `ref.text` (untracked file at repo root)

**Step 1: Verify `.gitignore` covers all personal harness state**

Run: `cat .gitignore`

Expected: must contain entries for `.omc/`, `.omo/`, `.serena/`, `.codegraph`, `.agents/`, `.claude/`, `.harness/`, `*.local.yml`, Python `__pycache__/`, `.venv/`, OS/editor files.

If any entry is missing, append it. The current `.gitignore` already covers all listed paths — verify only.

**Step 2: Remove the untracked `ref.text`**

The spec is locked; `ref.text` was the unvetted candidate pool and is now superseded by `catalog/reviews/` ADRs.

Run: `rm ref.text && ls ref.text 2>&1 || echo "OK: ref.text removed"`

Expected: `ls` fails with "No such file or directory" and the `echo` runs.

**Step 3: Create `LICENSE` (MIT)**

Write `LICENSE` with the full MIT license text. Year: 2026. Copyright holder: `Heretek-AI`.

```
MIT License

Copyright (c) 2026 Heretek-AI

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
```

**Step 4: Run a secret scan**

Run: `git ls-files | xargs grep -lE '(BEGIN [A-Z]+ PRIVATE KEY|ghp_[A-Za-z0-9]{20,}|sk-[A-Za-z0-9]{20,}|AKIA[0-9A-Z]{16}|aws_secret_access_key)' 2>/dev/null || echo "OK: no secret patterns found"`

Expected: `OK: no secret patterns found`. (We have very few tracked files at this stage so a false-positive risk is low; the real risk is in commits to be added later — Task 13 will install `gitleaks` in CI for ongoing protection.)

**Step 5: Verify clean public-safe tree**

Run: `git status && echo "---" && git ls-files | head -50`

Expected: `LICENSE` appears as untracked. No `ref.text`, no `.omc/`, no `.agents/`, no `.serena/` in tracked files. No untracked personal state.

**Step 6: Commit**

```bash
git add LICENSE .gitignore
git commit -m "chore: add MIT LICENSE and remove candidate-pool ref.text

Phase 0 cleanup per SP1 plan. Personal harness state remains
gitignored; live global installs at ~/.agents/skills and
~/.config/opencode/skills are unaffected (D9). Ref.text content is
preserved in catalog/reviews/ ADRs as items get vetted.

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

## Task 2: Project metadata + dependencies (`pyproject.toml`, `requirements*.txt`)

**Files:**
- Create: `pyproject.toml`
- Create: `requirements.txt`
- Create: `requirements-dev.txt`

**Step 1: Write `requirements.txt`**

```
PyYAML==6.0.2
jsonschema==4.23.0
```

**Step 2: Write `requirements-dev.txt`**

```
-r requirements.txt
pytest==8.3.3
```

**Step 3: Write `pyproject.toml`**

```toml
[project]
name = "heretek-marketplace"
version = "0.0.0"
description = "Opinionated Claude Code plugin marketplace (heretek)"
requires-python = ">=3.10"
dependencies = [
    "PyYAML==6.0.2",
    "jsonschema==4.23.0",
]

[project.optional-dependencies]
dev = ["pytest==8.3.3"]

[tool.pytest.ini_options]
testpaths = ["tests"]
addopts = "-v --tb=short"
```

**Step 4: Install deps + verify import**

Run: `python3 -m venv .venv && . .venv/bin/activate && pip install -r requirements-dev.txt && python3 -c "import yaml, jsonschema, pytest; print('deps OK')"`

Expected: `deps OK`.

**Step 5: Commit**

```bash
git add pyproject.toml requirements.txt requirements-dev.txt
git commit -m "build: add Python project metadata + pinned deps

PyYAML + jsonschema for runtime (validate, generate-marketplace);
pytest for dev. Python 3.10+ floor matches the platform CI ships on.

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

## Task 3: JSON Schema — `marketplace.json` (TDD)

**Files:**
- Create: `tests/schemas/marketplace.schema.json`
- Create: `tests/fixtures/marketplace/valid.json`
- Create: `tests/fixtures/marketplace/invalid.json`
- Create: `tests/test_schemas_marketplace.py`
- Create: `tests/__init__.py` (empty)
- Create: `tests/conftest.py`

**Interfaces:**
- Consumes: nothing (first deliverable).
- Produces: `tests/schemas/marketplace.schema.json` — JSON Schema (draft-07) for `.claude-plugin/marketplace.json` per Claude Code v2.1.193+ docs.

**Step 1: Write failing test (valid example passes)**

Write `tests/__init__.py` (empty file).

Write `tests/conftest.py`:

```python
"""Shared pytest fixtures and path constants."""
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
SCHEMAS_DIR = REPO_ROOT / "tests" / "schemas"
FIXTURES_DIR = REPO_ROOT / "tests" / "fixtures"


@pytest.fixture(scope="session")
def repo_root() -> Path:
    return REPO_ROOT


@pytest.fixture(scope="session")
def schemas_dir() -> Path:
    return SCHEMAS_DIR


@pytest.fixture(scope="session")
def fixtures_dir() -> Path:
    return FIXTURES_DIR
```

Write `tests/fixtures/marketplace/valid.json`:

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "name": "heretek",
  "description": "Opinionated Claude Code harness: task plugins, quality-gate hooks, curated MCP/LSP/skills.",
  "owner": {
    "name": "Heretek-AI",
    "email": "team@heretek.ai"
  },
  "metadata": {
    "pluginRoot": "./plugins"
  },
  "plugins": [
    {
      "name": "rust",
      "source": "rust",
      "category": "task",
      "tags": ["rust", "language"],
      "description": "Rust task plugin: skills + LSP for rust-analyzer."
    },
    {
      "name": "third-party-example",
      "source": {
        "source": "git-subdir",
        "url": "https://github.com/acme/monorepo.git",
        "path": "tools/claude-plugin",
        "sha": "a1b2c3d4e5f6a7b8c9d0e1f2a3b4c5d6e7f8a9b0"
      },
      "category": "community",
      "tags": ["3rd-party"]
    }
  ]
}
```

Write `tests/test_schemas_marketplace.py`:

```python
"""Tests for the marketplace.json JSON Schema."""
import json
from pathlib import Path

import jsonschema
import pytest


def test_marketplace_schema_exists(schemas_dir: Path) -> None:
    schema_path = schemas_dir / "marketplace.schema.json"
    assert schema_path.is_file(), f"missing schema at {schema_path}"


def test_valid_marketplace_passes(schemas_dir: Path, fixtures_dir: Path) -> None:
    schema = json.loads((schemas_dir / "marketplace.schema.json").read_text())
    example = json.loads((fixtures_dir / "marketplace" / "valid.json").read_text())
    jsonschema.validate(instance=example, schema=schema)  # must not raise


def test_invalid_marketplace_fails(schemas_dir: Path, fixtures_dir: Path) -> None:
    schema = json.loads((schemas_dir / "marketplace.schema.json").read_text())
    bad = json.loads((fixtures_dir / "marketplace" / "invalid.json").read_text())
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(instance=bad, schema=schema)
```

**Step 2: Run tests, expect FAIL**

Run: `. .venv/bin/activate && pytest tests/test_schemas_marketplace.py -v`

Expected: FAIL — `marketplace.schema.json` does not exist.

**Step 3: Write the schema**

Create `tests/fixtures/marketplace/invalid.json` (a known-bad shape):

```json
{
  "name": "",
  "owner": {},
  "plugins": "this should be an array, not a string"
}
```

Create `tests/schemas/marketplace.schema.json`:

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "https://heretek.ai/schemas/marketplace.schema.json",
  "title": "Claude Code marketplace.json",
  "type": "object",
  "additionalProperties": false,
  "required": ["name", "owner", "plugins"],
  "properties": {
    "$schema": { "type": "string" },
    "name": {
      "type": "string",
      "pattern": "^[a-z0-9][a-z0-9-]*$",
      "minLength": 1,
      "description": "Marketplace identifier; lowercase, hyphenated."
    },
    "description": { "type": "string" },
    "version": { "type": "string" },
    "owner": {
      "type": "object",
      "additionalProperties": false,
      "required": ["name"],
      "properties": {
        "name": { "type": "string", "minLength": 1 },
        "email": { "type": "string", "format": "email" },
        "url": { "type": "string", "format": "uri" }
      }
    },
    "metadata": {
      "type": "object",
      "additionalProperties": true,
      "properties": {
        "pluginRoot": {
          "type": "string",
          "description": "Base directory for relative plugin sources (e.g. './plugins')."
        }
      }
    },
    "allowCrossMarketplaceDependenciesOn": {
      "type": "array",
      "items": { "type": "string" }
    },
    "renames": {
      "type": "object",
      "description": "Plugin rename/removal map for graceful migration (Claude Code v2.1.193+).",
      "additionalProperties": {
        "type": "object",
        "required": ["from"],
        "properties": {
          "from": { "type": "string" },
          "to": { "type": "string" }
        }
      }
    },
    "plugins": {
      "type": "array",
      "items": { "$ref": "#/$defs/pluginEntry" }
    }
  },
  "$defs": {
    "pluginEntry": {
      "type": "object",
      "additionalProperties": false,
      "required": ["name", "source"],
      "properties": {
        "name": {
          "type": "string",
          "pattern": "^[a-z0-9][a-z0-9-]*$",
          "minLength": 1
        },
        "source": {
          "oneOf": [
            { "type": "string", "minLength": 1, "description": "Relative source name; resolved against metadata.pluginRoot." },
            { "$ref": "#/$defs/sourceObject" }
          ]
        },
        "description": { "type": "string" },
        "version": { "type": "string", "description": "Omitted for first-party (SHA-ride, D11)." },
        "author": {
          "type": "object",
          "additionalProperties": false,
          "properties": {
            "name": { "type": "string" },
            "email": { "type": "string", "format": "email" },
            "url": { "type": "string", "format": "uri" }
          }
        },
        "homepage": { "type": "string", "format": "uri" },
        "repository": { "type": "string", "format": "uri" },
        "license": { "type": "string" },
        "keywords": { "type": "array", "items": { "type": "string" } },
        "category": { "type": "string" },
        "tags": { "type": "array", "items": { "type": "string" } },
        "commands": { "type": "array", "items": { "type": "string" } },
        "agents": { "type": "array", "items": { "type": "string" } },
        "hooks": {
          "oneOf": [
            { "type": "string" },
            { "type": "object" }
          ]
        },
        "mcpServers": {
          "oneOf": [
            { "type": "string" },
            { "type": "object" }
          ]
        },
        "strict": { "type": "boolean" }
      }
    },
    "sourceObject": {
      "type": "object",
      "required": ["source"],
      "properties": {
        "source": {
          "type": "string",
          "enum": ["github", "git-subdir", "url", "npm"]
        },
        "repo": { "type": "string", "description": "owner/repo for source=github." },
        "url": { "type": "string", "format": "uri", "description": "Git URL for source=git-subdir or source=url." },
        "path": { "type": "string", "description": "Subdirectory within the upstream repo (git-subdir) or plugin manifest path." },
        "ref": { "type": "string", "description": "Git ref (branch or tag). For git-subdir." },
        "sha": {
          "type": "string",
          "pattern": "^[a-f0-9]{40}$",
          "description": "Full 40-char commit SHA. Required for vetted 3rd-party per D7."
        },
        "package": { "type": "string", "description": "NPM package name for source=npm." },
        "headers": {
          "type": "object",
          "additionalProperties": { "type": "string" },
          "description": "HTTP headers for source=url."
        }
      },
      "allOf": [
        {
          "if": { "properties": { "source": { "const": "github" } } },
          "then": { "required": ["source", "repo"] }
        },
        {
          "if": { "properties": { "source": { "const": "git-subdir" } } },
          "then": { "required": ["source", "url", "path"] }
        },
        {
          "if": { "properties": { "source": { "const": "url" } } },
          "then": { "required": ["source", "url"] }
        },
        {
          "if": { "properties": { "source": { "const": "npm" } } },
          "then": { "required": ["source", "package"] }
        }
      ]
    }
  }
}
```

**Step 4: Run tests, expect PASS**

Run: `. .venv/bin/activate && pytest tests/test_schemas_marketplace.py -v`

Expected: 3 tests pass.

**Step 5: Commit**

```bash
git add tests/__init__.py tests/conftest.py \
        tests/schemas/marketplace.schema.json \
        tests/fixtures/marketplace/valid.json \
        tests/fixtures/marketplace/invalid.json \
        tests/test_schemas_marketplace.py
git commit -m "test(schema): add JSON Schema for marketplace.json

Validates against Claude Code v2.1.193+ marketplace format:
required name/owner/plugins, optional $schema/description/version,
metadata.pluginRoot, allowCrossMarketplaceDependenciesOn, renames.
Plugin entries: name + source (string relative or object with
github/git-subdir/url/npm variants; sha pinned to 40 hex).

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

## Task 4: JSON Schema — `plugin.json` (TDD)

**Files:**
- Create: `tests/schemas/plugin.schema.json`
- Create: `tests/fixtures/plugin/valid.json`
- Create: `tests/fixtures/plugin/invalid.json`
- Create: `tests/test_schemas_plugin.py`

**Interfaces:**
- Consumes: nothing (independent).
- Produces: `tests/schemas/plugin.schema.json` — JSON Schema for per-plugin manifest.

**Step 1: Write failing test**

Write `tests/fixtures/plugin/valid.json`:

```json
{
  "name": "rust",
  "displayName": "Rust",
  "description": "Rust task plugin: rust-analyzer LSP + cargo-check skill.",
  "author": {
    "name": "Heretek-AI",
    "url": "https://github.com/Heretek-AI"
  },
  "license": "MIT",
  "keywords": ["rust", "language", "task"],
  "skills": "./skills/",
  "commands": [],
  "agents": [],
  "hooks": "./hooks/hooks.json",
  "mcpServers": "./.mcp.json",
  "lspServers": "./.lsp.json"
}
```

Write `tests/fixtures/plugin/invalid.json`:

```json
{
  "version": "1.0.0",
  "license": "Made-up-License"
}
```

Write `tests/test_schemas_plugin.py`:

```python
"""Tests for the plugin.json JSON Schema."""
import json
from pathlib import Path

import jsonschema
import pytest


def test_valid_plugin_passes(schemas_dir: Path, fixtures_dir: Path) -> None:
    schema = json.loads((schemas_dir / "plugin.schema.json").read_text())
    example = json.loads((fixtures_dir / "plugin" / "valid.json").read_text())
    jsonschema.validate(instance=example, schema=schema)


def test_invalid_plugin_fails(schemas_dir: Path, fixtures_dir: Path) -> None:
    schema = json.loads((schemas_dir / "plugin.schema.json").read_text())
    bad = json.loads((fixtures_dir / "plugin" / "invalid.json").read_text())
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(instance=bad, schema=schema)
```

**Step 2: Run tests, expect FAIL**

Run: `. .venv/bin/activate && pytest tests/test_schemas_plugin.py -v`

Expected: FAIL — `plugin.schema.json` does not exist.

**Step 3: Write the schema**

Create `tests/schemas/plugin.schema.json`:

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "https://heretek.ai/schemas/plugin.schema.json",
  "title": "Claude Code plugin.json",
  "type": "object",
  "additionalProperties": false,
  "properties": {
    "name": {
      "type": "string",
      "pattern": "^[a-z0-9][a-z0-9-]*$",
      "minLength": 1
    },
    "displayName": { "type": "string" },
    "description": { "type": "string" },
    "version": {
      "type": "string",
      "description": "Omit for first-party (SHA-ride, D11). Required only for npm/3rd-party."
    },
    "author": {
      "type": "object",
      "additionalProperties": false,
      "properties": {
        "name": { "type": "string" },
        "email": { "type": "string", "format": "email" },
        "url": { "type": "string", "format": "uri" }
      }
    },
    "homepage": { "type": "string", "format": "uri" },
    "repository": { "type": "string", "format": "uri" },
    "license": { "type": "string" },
    "keywords": { "type": "array", "items": { "type": "string" } },
    "skills": {
      "oneOf": [
        { "type": "string" },
        { "type": "array", "items": { "type": "string" } }
      ]
    },
    "commands": {
      "oneOf": [
        { "type": "string" },
        { "type": "array", "items": { "type": "string" } }
      ]
    },
    "agents": {
      "oneOf": [
        { "type": "string" },
        { "type": "array", "items": { "type": "string" } }
      ]
    },
    "hooks": {
      "oneOf": [
        { "type": "string" },
        { "type": "object" }
      ]
    },
    "mcpServers": {
      "oneOf": [
        { "type": "string" },
        { "type": "object" }
      ]
    },
    "outputStyles": {
      "oneOf": [
        { "type": "string" },
        { "type": "array", "items": { "type": "string" } }
      ]
    },
    "lspServers": {
      "oneOf": [
        { "type": "string" },
        { "type": "array", "items": { "type": "string" } }
      ]
    },
    "experimental": {
      "type": "object",
      "additionalProperties": { "type": "string" }
    },
    "dependencies": {
      "type": "array",
      "items": {
        "oneOf": [
          { "type": "string" },
          {
            "type": "object",
            "required": ["name"],
            "properties": {
              "name": { "type": "string" },
              "version": { "type": "string" }
            }
          }
        ]
      }
    }
  }
}
```

**Step 4: Run tests, expect PASS**

Run: `. .venv/bin/activate && pytest tests/test_schemas_plugin.py -v`

Expected: 2 tests pass.

**Step 5: Commit**

```bash
git add tests/schemas/plugin.schema.json \
        tests/fixtures/plugin/valid.json \
        tests/fixtures/plugin/invalid.json \
        tests/test_schemas_plugin.py
git commit -m "test(schema): add JSON Schema for plugin.json

Per Claude Code plugin reference: optional manifest at
.claude-plugin/plugin.json with name/description/version (omit for
first-party, D11), author, component path overrides for
skills/commands/agents/hooks/mcpServers/outputStyles/lspServers.

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

## Task 5: JSON Schema — `hooks.json` (TDD)

**Files:**
- Create: `tests/schemas/hooks.schema.json`
- Create: `tests/fixtures/hooks/valid.json`
- Create: `tests/fixtures/hooks/invalid.json`
- Create: `tests/test_schemas_hooks.py`

**Interfaces:**
- Consumes: nothing (independent).
- Produces: `tests/schemas/hooks.schema.json` — JSON Schema for the hooks manifest.

**Step 1: Write failing test**

Write `tests/fixtures/hooks/valid.json`:

```json
{
  "hooks": {
    "PreToolUse": [
      {
        "matcher": "Edit|Write|MultiEdit",
        "hooks": [
          {
            "type": "command",
            "command": "${CLAUDE_PLUGIN_ROOT}/scripts/fast-gate.sh",
            "timeout": 100
          }
        ]
      }
    ],
    "PostToolUse": [
      {
        "matcher": "Edit|Write",
        "hooks": [
          {
            "type": "command",
            "command": "${CLAUDE_PLUGIN_ROOT}/scripts/notify.sh",
            "async": true,
            "timeout": 5000
          }
        ]
      }
    ],
    "Notification": [
      {
        "matcher": "",
        "hooks": [
          { "type": "command", "command": "echo notified" }
        ]
      }
    ]
  }
}
```

Write `tests/fixtures/hooks/invalid.json`:

```json
{
  "hooks": {
    "PreToolUse": "this should be an array"
  }
}
```

Write `tests/test_schemas_hooks.py`:

```python
"""Tests for the hooks.json JSON Schema."""
import json
from pathlib import Path

import jsonschema
import pytest


def test_valid_hooks_passes(schemas_dir: Path, fixtures_dir: Path) -> None:
    schema = json.loads((schemas_dir / "hooks.schema.json").read_text())
    example = json.loads((fixtures_dir / "hooks" / "valid.json").read_text())
    jsonschema.validate(instance=example, schema=schema)


def test_invalid_hooks_fails(schemas_dir: Path, fixtures_dir: Path) -> None:
    schema = json.loads((schemas_dir / "hooks.schema.json").read_text())
    bad = json.loads((fixtures_dir / "hooks" / "invalid.json").read_text())
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(instance=bad, schema=schema)
```

**Step 2: Run tests, expect FAIL**

Run: `. .venv/bin/activate && pytest tests/test_schemas_hooks.py -v`

Expected: FAIL — schema missing.

**Step 3: Write the schema**

Create `tests/schemas/hooks.schema.json`:

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "https://heretek.ai/schemas/hooks.schema.json",
  "title": "Claude Code hooks.json",
  "type": "object",
  "additionalProperties": false,
  "required": ["hooks"],
  "properties": {
    "hooks": {
      "type": "object",
      "additionalProperties": { "$ref": "#/$defs/eventMatcherList" },
      "properties": {
        "PreToolUse": { "$ref": "#/$defs/eventMatcherList" },
        "UserPromptSubmit": { "$ref": "#/$defs/eventMatcherList" },
        "PostToolUse": { "$ref": "#/$defs/eventMatcherList" },
        "Notification": { "$ref": "#/$defs/eventMatcherList" },
        "Stop": { "$ref": "#/$defs/eventMatcherList" },
        "SubagentStop": { "$ref": "#/$defs/eventMatcherList" },
        "PreCompact": { "$ref": "#/$defs/eventMatcherList" },
        "SessionStart": { "$ref": "#/$defs/eventMatcherList" },
        "SessionEnd": { "$ref": "#/$defs/eventMatcherList" }
      }
    }
  },
  "$defs": {
    "eventMatcherList": {
      "type": "array",
      "items": { "$ref": "#/$defs/matcher" }
    },
    "matcher": {
      "type": "object",
      "required": ["hooks"],
      "properties": {
        "matcher": {
          "type": "string",
          "description": "Tool name regex (e.g. 'Edit|Write|MultiEdit'). Empty string = all tools."
        },
        "hooks": {
          "type": "array",
          "minItems": 1,
          "items": { "$ref": "#/$defs/hook" }
        }
      }
    },
    "hook": {
      "type": "object",
      "required": ["type"],
      "properties": {
        "type": {
          "type": "string",
          "enum": ["command", "prompt"]
        },
        "command": { "type": "string" },
        "prompt": { "type": "string" },
        "timeout": {
          "type": "integer",
          "minimum": 1,
          "description": "Per-hook timeout in seconds (integer per Claude Code hooks reference). Layer-1 fast gates set timeout=1; the wrapper script enforces the <100ms goal internally and exits fast on overrun."
        },
        "async": {
          "type": "boolean",
          "description": "Run asynchronously; never block the agent loop."
        },
        "if": {
          "type": "string",
          "description": "Conditional expression for tool input (e.g. 'Bash(git *)')."
        }
      },
      "allOf": [
        {
          "if": { "properties": { "type": { "const": "command" } } },
          "then": { "required": ["command"] }
        },
        {
          "if": { "properties": { "type": { "const": "prompt" } } },
          "then": { "required": ["prompt"] }
        }
      ]
    }
  }
}
```

**Step 4: Run tests, expect PASS**

Run: `. .venv/bin/activate && pytest tests/test_schemas_hooks.py -v`

Expected: 2 tests pass.

**Step 5: Commit**

```bash
git add tests/schemas/hooks.schema.json \
        tests/fixtures/hooks/valid.json \
        tests/fixtures/hooks/invalid.json \
        tests/test_schemas_hooks.py
git commit -m "test(schema): add JSON Schema for hooks.json

Per Claude Code hooks reference: events PreToolUse/UserPromptSubmit/
PostToolUse/Notification/Stop/SubagentStop/PreCompact/SessionStart/
SessionEnd. Each event is an array of {matcher, hooks[]} entries.
Per-hook fields: type (command|prompt), timeout, async, if.

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

## Task 6: JSON Schema — `.mcp.json` (TDD)

**Files:**
- Create: `tests/schemas/mcp.schema.json`
- Create: `tests/fixtures/mcp/valid.json`
- Create: `tests/fixtures/mcp/invalid.json`
- Create: `tests/test_schemas_mcp.py`

**Interfaces:**
- Consumes: nothing (independent).
- Produces: `tests/schemas/mcp.schema.json` — JSON Schema for `.mcp.json`.

**Step 1: Write failing test**

Write `tests/fixtures/mcp/valid.json`:

```json
{
  "mcpServers": {
    "github": {
      "type": "http",
      "url": "https://api.githubcopilot.com/mcp/"
    },
    "local-tool": {
      "command": "/usr/local/bin/my-mcp-server",
      "args": ["--config", "/etc/my-mcp/config.json"],
      "env": {
        "MY_API_URL": "https://internal.example.com"
      }
    }
  }
}
```

Write `tests/fixtures/mcp/invalid.json`:

```json
{
  "mcpServers": {
    "bad": {
      "type": "websocket",
      "url": "ws://nope"
    }
  }
}
```

Write `tests/test_schemas_mcp.py`:

```python
"""Tests for the .mcp.json JSON Schema."""
import json
from pathlib import Path

import jsonschema
import pytest


def test_valid_mcp_passes(schemas_dir: Path, fixtures_dir: Path) -> None:
    schema = json.loads((schemas_dir / "mcp.schema.json").read_text())
    example = json.loads((fixtures_dir / "mcp" / "valid.json").read_text())
    jsonschema.validate(instance=example, schema=schema)


def test_invalid_mcp_fails(schemas_dir: Path, fixtures_dir: Path) -> None:
    schema = json.loads((schemas_dir / "mcp.schema.json").read_text())
    bad = json.loads((fixtures_dir / "mcp" / "invalid.json").read_text())
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(instance=bad, schema=schema)
```

**Step 2: Run tests, expect FAIL**

Run: `. .venv/bin/activate && pytest tests/test_schemas_mcp.py -v`

Expected: FAIL — schema missing.

**Step 3: Write the schema**

Create `tests/schemas/mcp.schema.json`:

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "https://heretek.ai/schemas/mcp.schema.json",
  "title": "Claude Code .mcp.json",
  "type": "object",
  "additionalProperties": false,
  "required": ["mcpServers"],
  "properties": {
    "mcpServers": {
      "type": "object",
      "additionalProperties": { "$ref": "#/$defs/server" }
    }
  },
  "$defs": {
    "server": {
      "type": "object",
      "properties": {
        "type": { "type": "string", "enum": ["stdio", "http"] },
        "command": { "type": "string", "description": "stdio: binary path or interpreter." },
        "args": { "type": "array", "items": { "type": "string" } },
        "env": {
          "type": "object",
          "additionalProperties": { "type": "string" }
        },
        "url": { "type": "string", "format": "uri", "description": "http: server URL." },
        "headers": {
          "type": "object",
          "additionalProperties": { "type": "string" }
        }
      },
      "allOf": [
        {
          "if": { "properties": { "type": { "const": "stdio" } }, "required": ["type"] },
          "then": { "required": ["command"] }
        },
        {
          "if": { "properties": { "type": { "const": "http" } }, "required": ["type"] },
          "then": { "required": ["url"] }
        }
      ]
    }
  }
}
```

**Step 4: Run tests, expect PASS**

Run: `. .venv/bin/activate && pytest tests/test_schemas_mcp.py -v`

Expected: 2 tests pass.

**Step 5: Commit**

```bash
git add tests/schemas/mcp.schema.json \
        tests/fixtures/mcp/valid.json \
        tests/fixtures/mcp/invalid.json \
        tests/test_schemas_mcp.py
git commit -m "test(schema): add JSON Schema for .mcp.json

Per Claude Code MCP reference: mcpServers object, each entry
stdio (command+args+env) or http (url+headers). Code-executing
components require D7 source-audit before inclusion in catalog.

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

## Task 7: JSON Schema — `.lsp.json` (TDD)

**Files:**
- Create: `tests/schemas/lsp.schema.json`
- Create: `tests/fixtures/lsp/valid.json`
- Create: `tests/fixtures/lsp/invalid.json`
- Create: `tests/test_schemas_lsp.py`

**Interfaces:**
- Consumes: nothing (independent).
- Produces: `tests/schemas/lsp.schema.json` — JSON Schema for `.lsp.json`.

**Step 1: Write failing test**

Write `tests/fixtures/lsp/valid.json`:

```json
{
  "lspServers": {
    "rust": {
      "command": "rust-analyzer",
      "args": [],
      "extensionToLanguage": {
        ".rs": "rust"
      }
    },
    "python": {
      "command": "pyright-langserver",
      "args": ["--stdio"],
      "extensionToLanguage": {
        ".py": "python",
        ".pyi": "python"
      }
    }
  }
}
```

Write `tests/fixtures/lsp/invalid.json`:

```json
{
  "lspServers": {
    "bad": {
      "command": 42
    }
  }
}
```

Write `tests/test_schemas_lsp.py`:

```python
"""Tests for the .lsp.json JSON Schema."""
import json
from pathlib import Path

import jsonschema
import pytest


def test_valid_lsp_passes(schemas_dir: Path, fixtures_dir: Path) -> None:
    schema = json.loads((schemas_dir / "lsp.schema.json").read_text())
    example = json.loads((fixtures_dir / "lsp" / "valid.json").read_text())
    jsonschema.validate(instance=example, schema=schema)


def test_invalid_lsp_fails(schemas_dir: Path, fixtures_dir: Path) -> None:
    schema = json.loads((schemas_dir / "lsp.schema.json").read_text())
    bad = json.loads((fixtures_dir / "lsp" / "invalid.json").read_text())
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(instance=bad, schema=schema)
```

**Step 2: Run tests, expect FAIL**

Run: `. .venv/bin/activate && pytest tests/test_schemas_lsp.py -v`

Expected: FAIL — schema missing.

**Step 3: Write the schema**

Create `tests/schemas/lsp.schema.json`:

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "https://heretek.ai/schemas/lsp.schema.json",
  "title": "Claude Code .lsp.json",
  "type": "object",
  "additionalProperties": false,
  "required": ["lspServers"],
  "properties": {
    "lspServers": {
      "type": "object",
      "additionalProperties": { "$ref": "#/$defs/server" }
    }
  },
  "$defs": {
    "server": {
      "type": "object",
      "required": ["command"],
      "properties": {
        "command": {
          "type": "string",
          "minLength": 1,
          "description": "LSP binary name on $PATH (user-installed; see plugin README)."
        },
        "args": { "type": "array", "items": { "type": "string" } },
        "env": {
          "type": "object",
          "additionalProperties": { "type": "string" }
        },
        "extensionToLanguage": {
          "type": "object",
          "additionalProperties": { "type": "string" },
          "description": "Map file extensions to language IDs."
        }
      }
    }
  }
}
```

**Step 4: Run tests, expect PASS**

Run: `. .venv/bin/activate && pytest tests/test_schemas_lsp.py -v`

Expected: 2 tests pass.

**Step 5: Commit**

```bash
git add tests/schemas/lsp.schema.json \
        tests/fixtures/lsp/valid.json \
        tests/fixtures/lsp/invalid.json \
        tests/test_schemas_lsp.py
git commit -m "test(schema): add JSON Schema for .lsp.json

Per Claude Code LSP reference: lspServers object with command
(user-installed binary), args, env, extensionToLanguage. No
SHA-pinned binaries; configs are JSON pointers only.

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

## Task 8: `scripts/validate.py` (TDD)

**Files:**
- Create: `scripts/validate.py`
- Create: `tests/test_validate.py`

**Interfaces:**
- Consumes: `tests/schemas/marketplace.schema.json`, `tests/schemas/plugin.schema.json`, `tests/schemas/hooks.schema.json`, `tests/schemas/mcp.schema.json`, `tests/schemas/lsp.schema.json`.
- Produces:
  - CLI: `scripts/validate.py` — exits 0 on success, 1 on any schema failure. Prints each failure to stderr.
  - Python API: `validate_all(repo_root: Path) -> list[str]` — returns list of failure messages (empty = success).

**Step 1: Write failing test**

Write `tests/test_validate.py`:

```python
"""Tests for scripts/validate.py."""
import json
import sys
from pathlib import Path

import pytest

# Make scripts/ importable as a package.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import validate  # noqa: E402


def _write(p: Path, payload: dict | list) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(payload))


def _minimal_marketplace() -> dict:
    return {
        "name": "test-mp",
        "owner": {"name": "Tester"},
        "plugins": [
            {"name": "p1", "source": "p1", "category": "task"}
        ]
    }


def _minimal_plugin(name: str = "p1") -> dict:
    return {"name": name, "description": "test plugin"}


def test_validate_clean_tree_returns_no_errors(
    tmp_path: Path, schemas_dir: Path
) -> None:
    _write(tmp_path / ".claude-plugin" / "marketplace.json", _minimal_marketplace())
    _write(tmp_path / "plugins" / "p1" / ".claude-plugin" / "plugin.json", _minimal_plugin())
    errors = validate.validate_all(tmp_path, schemas_dir=schemas_dir)
    assert errors == [], f"expected no errors, got: {errors}"


def test_validate_bad_marketplace_returns_error(
    tmp_path: Path, schemas_dir: Path
) -> None:
    bad = {"name": "", "owner": {}, "plugins": "not-an-array"}
    _write(tmp_path / ".claude-plugin" / "marketplace.json", bad)
    errors = validate.validate_all(tmp_path, schemas_dir=schemas_dir)
    assert len(errors) >= 1, "expected at least one error"


def test_validate_bad_plugin_returns_error(
    tmp_path: Path, schemas_dir: Path
) -> None:
    _write(tmp_path / ".claude-plugin" / "marketplace.json", _minimal_marketplace())
    _write(
        tmp_path / "plugins" / "p1" / ".claude-plugin" / "plugin.json",
        {"version": 12345},  # version must be string
    )
    errors = validate.validate_all(tmp_path, schemas_dir=schemas_dir)
    assert len(errors) >= 1


def test_validate_missing_marketplace_returns_error(
    tmp_path: Path, schemas_dir: Path
) -> None:
    errors = validate.validate_all(tmp_path, schemas_dir=schemas_dir)
    assert any("marketplace" in e.lower() for e in errors)


def test_main_exits_zero_on_clean(
    tmp_path: Path, schemas_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _write(tmp_path / ".claude-plugin" / "marketplace.json", _minimal_marketplace())
    _write(tmp_path / "plugins" / "p1" / ".claude-plugin" / "plugin.json", _minimal_plugin())
    monkeypatch.setattr(sys, "argv", ["validate.py", "--repo-root", str(tmp_path), "--schemas-dir", str(schemas_dir)])
    assert validate.main() == 0


def test_main_exits_nonzero_on_failure(
    tmp_path: Path, schemas_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    bad = {"name": "", "owner": {}, "plugins": "not-an-array"}
    _write(tmp_path / ".claude-plugin" / "marketplace.json", bad)
    monkeypatch.setattr(sys, "argv", ["validate.py", "--repo-root", str(tmp_path), "--schemas-dir", str(schemas_dir)])
    assert validate.main() == 1
```

**Step 2: Run tests, expect FAIL**

Run: `. .venv/bin/activate && pytest tests/test_validate.py -v`

Expected: FAIL — `scripts/validate.py` does not exist.

**Step 3: Implement `scripts/validate.py`**

Write `scripts/validate.py`:

```python
"""Validate the marketplace and every plugin manifest against JSON Schemas.

Run as CLI:
    python scripts/validate.py [--repo-root PATH] [--schemas-dir PATH]

Exit codes: 0 on success, 1 on any schema failure. Each failure is printed
to stderr so CI logs make failures obvious.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Iterable

import jsonschema

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_SCHEMAS_DIR = REPO_ROOT / "tests" / "schemas"

SCHEMAS = {
    "marketplace": "marketplace.schema.json",
    "plugin": "plugin.schema.json",
    "hooks": "hooks.schema.json",
    "mcp": "mcp.schema.json",
    "lsp": "lsp.schema.json",
}


def _load_schema(name: str, schemas_dir: Path) -> dict:
    path = schemas_dir / SCHEMAS[name]
    if not path.is_file():
        raise FileNotFoundError(f"schema not found: {path}")
    return json.loads(path.read_text())


def _validate_one(schema: dict, instance: dict, label: str) -> list[str]:
    validator = jsonschema.Draft202012Validator(schema)
    return [f"{label}: {e.message}" for e in validator.iter_errors(instance)]


def _validate_plugin_manifests(
    repo_root: Path, schemas: dict[str, dict]
) -> list[str]:
    """Walk plugins/<name>/.claude-plugin/ and validate plugin.json + sibling manifests."""
    errors: list[str] = []
    plugins_root = repo_root / "plugins"
    if not plugins_root.is_dir():
        return errors
    for plugin_dir in sorted(plugins_root.iterdir()):
        if not plugin_dir.is_dir():
            continue
        manifest_dir = plugin_dir / ".claude-plugin"
        if not manifest_dir.is_dir():
            continue
        for kind, schema in (
            ("plugin.json", schemas["plugin"]),
            ("hooks.json", schemas["hooks"]),
            (".mcp.json", schemas["mcp"]),
            (".lsp.json", schemas["lsp"]),
        ):
            path = manifest_dir / kind
            if not path.is_file():
                continue
            label = f"plugins/{plugin_dir.name}/.claude-plugin/{kind}"
            try:
                instance = json.loads(path.read_text())
            except json.JSONDecodeError as exc:
                errors.append(f"{label}: invalid JSON ({exc.msg})")
                continue
            errors.extend(_validate_one(schema, instance, label))
    return errors


def validate_all(repo_root: Path, schemas_dir: Path | None = None) -> list[str]:
    """Return a list of schema-failure messages; empty list = clean."""
    schemas_dir = schemas_dir or DEFAULT_SCHEMAS_DIR
    try:
        schemas = {name: _load_schema(name, schemas_dir) for name in SCHEMAS}
    except FileNotFoundError as exc:
        return [str(exc)]

    errors: list[str] = []

    marketplace_path = repo_root / ".claude-plugin" / "marketplace.json"
    if not marketplace_path.is_file():
        errors.append(f"missing marketplace manifest: {marketplace_path}")
    else:
        try:
            instance = json.loads(marketplace_path.read_text())
        except json.JSONDecodeError as exc:
            errors.append(f".claude-plugin/marketplace.json: invalid JSON ({exc.msg})")
        else:
            errors.extend(
                _validate_one(
                    schemas["marketplace"], instance, ".claude-plugin/marketplace.json"
                )
            )

    errors.extend(_validate_plugin_manifests(repo_root, schemas))
    return errors


def main(argv: Iterable[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=REPO_ROOT)
    parser.add_argument("--schemas-dir", type=Path, default=DEFAULT_SCHEMAS_DIR)
    args = parser.parse_args(argv)

    errors = validate_all(args.repo_root, schemas_dir=args.schemas_dir)
    if not errors:
        print("validate: OK (all manifests conform to JSON Schemas)")
        return 0
    print(f"validate: {len(errors)} error(s)", file=sys.stderr)
    for e in errors:
        print(f"  - {e}", file=sys.stderr)
    return 1


if __name__ == "__main__":
    sys.exit(main())
```

**Step 4: Run tests, expect PASS**

Run: `. .venv/bin/activate && pytest tests/test_validate.py -v`

Expected: 6 tests pass.

**Step 5: Commit**

```bash
git add scripts/validate.py tests/test_validate.py
git commit -m "feat(scripts): add validate.py with JSON Schema enforcement

Validates .claude-plugin/marketplace.json and every plugin manifest
(plugin.json, hooks.json, .mcp.json, .lsp.json) under plugins/.
CLI exits 0 on success, 1 on any schema failure. Imports as a
library too (validate_all(repo_root)) for reuse in tests and CI.

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

## Task 9: Initial `catalog/catalog.yaml` seed (11 placeholder plugins)

**Files:**
- Create: `catalog/catalog.yaml`
- Create: `catalog/reviews/0000-template.md`
- Create: `catalog/rejected.md`

**Interfaces:**
- Consumes: nothing (data).
- Produces: source-of-truth YAML listing all 11 first-party plugins with empty `items: []` (so the marketplace installs without anything failing). Plus the ADR template and an empty rejected.md.

**Step 1: Create the ADR template**

Write `catalog/reviews/0000-template.md`:

```markdown
---
slug: <slug>
date: YYYY-MM-DD
status: pending
---

# <Item name>

## What

One-paragraph description of the item (repo, what it does, latest release).

## Why

Why this item is worth including in the heretek marketplace. What gap does it fill?

## Alternatives

What other tools cover the same need? Why this one?

## Verdict

- [ ] Approved
- [ ] Rejected

Reason: ...

## Target plugin

Which plugin will bundle this item? (`rust` / `python` / `js-ts` / `web-frontend` / `hooks` / `security` / `skills-pack` / `mcp-pack` / `lsp-pack` / `agents` / `output-styles`)

## Vetting checklist (D7)

- [ ] stars ≥ 500
- [ ] last commit ≤ 12 months
- [ ] OSI-approved license (MIT / Apache-2.0 / BSD / etc.)
- [ ] source-audit pass (if code-executing)
- [ ] no critical CVEs in last 24 months
```

**Step 2: Create empty `rejected.md`**

Write `catalog/rejected.md`:

```markdown
# Rejected items

Items that did not pass the D7 vetting bar, with the reason for rejection. Each entry is preserved here so the decision is auditable; remove only when the item is reconsidered.

<!-- Newest entries at the top. -->
```

**Step 3: Create `catalog/catalog.yaml`**

Write `catalog/catalog.yaml` with all 11 plugins. Items are empty `[]` for v1 placeholder state (SP3/SP4 will fill them in via the curation pipeline).

```yaml
# heretek marketplace — source of truth.
# Generated from this file by scripts/generate_marketplace.py; do NOT
# hand-edit .claude-plugin/marketplace.json (it's regenerated).
#
# Schema: see tests/schemas/marketplace.schema.json (for the generated
# marketplace.json) and tests/fixtures/catalog/* (for the catalog.yaml
# structure). Every items[] entry must pass D7 vetting; entries without
# vetting.status: approved + review link fail CI.

marketplace:
  name: heretek
  description: Opinionated Claude Code harness: task plugins, quality-gate hooks, curated MCP/LSP/skills.
  owner:
    name: Heretek-AI
    email: team@heretek.ai
  metadata:
    pluginRoot: "./plugins"
  allowCrossMarketplaceDependenciesOn:
    - claude-plugins-official

plugins:
  - name: rust
    category: task
    tags: [rust, language]
    source: { type: relative, path: rust }
    components: [skills, lsp]
    items: []

  - name: python
    category: task
    tags: [python, language]
    source: { type: relative, path: python }
    components: [skills, lsp]
    items: []

  - name: js-ts
    category: task
    tags: [javascript, typescript]
    source: { type: relative, path: js-ts }
    components: [skills, lsp]
    items: []

  - name: web-frontend
    category: task
    tags: [frontend, design]
    source: { type: relative, path: web-frontend }
    components: [skills, mcp]
    items: []

  - name: hooks
    category: cross
    tags: [hooks, quality-gates, flagship]
    source: { type: relative, path: hooks }
    components: [hooks, commands, git-hooks]
    items: []

  - name: security
    category: cross
    tags: [security, audit]
    source: { type: relative, path: security }
    components: [skills, commands]
    items: []

  - name: skills-pack
    category: cross
    tags: [skills, generic]
    source: { type: relative, path: skills-pack }
    components: [skills]
    items: []

  - name: mcp-pack
    category: cross
    tags: [mcp, generic]
    source: { type: relative, path: mcp-pack }
    components: [mcp]
    items: []

  - name: lsp-pack
    category: cross
    tags: [lsp, generic]
    source: { type: relative, path: lsp-pack }
    components: [lsp]
    items: []

  - name: agents
    category: cross
    tags: [agents]
    source: { type: relative, path: agents }
    components: [agents]
    items: []

  - name: output-styles
    category: cross
    tags: [output-styles]
    source: { type: relative, path: output-styles }
    components: [output-styles]
    items: []
```

**Step 4: Commit**

```bash
git add catalog/catalog.yaml catalog/reviews/0000-template.md catalog/rejected.md
git commit -m "feat(catalog): seed marketplace with 11 first-party plugins

All 11 plugins (4 task + 7 cross-cutting) listed in catalog.yaml
with empty items[] (SP3/SP4 fill them via the curation pipeline).
ADR template + rejected.md in place for the D7 vetting workflow.

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

## Task 10: `scripts/generate_marketplace.py` (TDD)

**Files:**
- Create: `scripts/generate_marketplace.py`
- Create: `tests/test_generate_marketplace.py`
- Create: `tests/fixtures/catalog/empty.yaml`
- Create: `tests/fixtures/catalog/single_plugin.yaml`

**Interfaces:**
- Consumes: `catalog/catalog.yaml`.
- Produces:
  - CLI: `scripts/generate_marketplace.py` — writes `.claude-plugin/marketplace.json`.
  - Python API: `generate(catalog_path: Path, output_path: Path) -> dict` — returns the generated dict (for testing); also writes to `output_path`.

**Step 1: Write failing test**

Write `tests/fixtures/catalog/empty.yaml`:

```yaml
marketplace:
  name: empty-test
  description: An empty catalog for testing.
  owner:
    name: Tester
  metadata:
    pluginRoot: "./plugins"

plugins: []
```

Write `tests/fixtures/catalog/single_plugin.yaml`:

```yaml
marketplace:
  name: single-test
  description: A catalog with one plugin.
  owner:
    name: Tester
  metadata:
    pluginRoot: "./plugins"

plugins:
  - name: alpha
    category: task
    tags: [example]
    source: { type: relative, path: alpha }
    components: [skills]
    items: []
```

Write `tests/test_generate_marketplace.py`:

```python
"""Tests for scripts/generate_marketplace.py."""
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import generate_marketplace  # noqa: E402


def _write(p: Path, content: str) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content)


def test_generate_empty_catalog(tmp_path: Path, fixtures_dir: Path) -> None:
    catalog = fixtures_dir / "catalog" / "empty.yaml"
    out = tmp_path / "marketplace.json"
    result = generate_marketplace.generate(catalog, out)
    assert result["name"] == "empty-test"
    assert result["plugins"] == []
    assert out.is_file()
    on_disk = json.loads(out.read_text())
    assert on_disk == result


def test_generate_single_plugin(tmp_path: Path, fixtures_dir: Path) -> None:
    catalog = fixtures_dir / "catalog" / "single_plugin.yaml"
    out = tmp_path / "marketplace.json"
    result = generate_marketplace.generate(catalog, out)
    assert result["name"] == "single-test"
    assert len(result["plugins"]) == 1
    plugin = result["plugins"][0]
    assert plugin["name"] == "alpha"
    assert plugin["source"] == "alpha"  # relative source becomes a bare string
    assert plugin["category"] == "task"
    assert plugin["tags"] == ["example"]


def test_generate_is_idempotent(tmp_path: Path, fixtures_dir: Path) -> None:
    """Running the generator twice must produce identical output."""
    catalog = fixtures_dir / "catalog" / "single_plugin.yaml"
    out = tmp_path / "marketplace.json"
    first = generate_marketplace.generate(catalog, out)
    second = generate_marketplace.generate(catalog, out)
    assert first == second


def test_generate_strips_internal_fields(tmp_path: Path, fixtures_dir: Path) -> None:
    """catalog.yaml-only fields like 'components' must not appear in marketplace.json."""
    catalog = fixtures_dir / "catalog" / "single_plugin.yaml"
    out = tmp_path / "marketplace.json"
    result = generate_marketplace.generate(catalog, out)
    plugin = result["plugins"][0]
    assert "components" not in plugin
    assert "items" not in plugin


def test_generate_3rd_party_source_object_preserved(
    tmp_path: Path, fixtures_dir: Path
) -> None:
    """3rd-party source objects with sha pins must be preserved as-is."""
    _write(
        tmp_path / "catalog.yaml",
        """\
marketplace:
  name: t
  description: t
  owner:
    name: t
plugins:
  - name: third
    category: community
    tags: [3rd-party]
    source:
      type: git-subdir
      url: https://github.com/acme/monorepo.git
      path: tools/p
      sha: a1b2c3d4e5f6a7b8c9d0e1f2a3b4c5d6e7f8a9b0
    components: []
    items: []
""",
    )
    out = tmp_path / "marketplace.json"
    result = generate_marketplace.generate(tmp_path / "catalog.yaml", out)
    plugin = result["plugins"][0]
    assert plugin["source"] == {
        "source": "git-subdir",
        "url": "https://github.com/acme/monorepo.git",
        "path": "tools/p",
        "sha": "a1b2c3d4e5f6a7b8c9d0e1f2a3b4c5d6e7f8a9b0",
    }


def test_main_writes_and_exits_zero(
    tmp_path: Path, fixtures_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    catalog = fixtures_dir / "catalog" / "empty.yaml"
    out = tmp_path / "marketplace.json"
    monkeypatch.setattr(
        sys,
        "argv",
        ["generate_marketplace.py", "--catalog", str(catalog), "--output", str(out)],
    )
    assert generate_marketplace.main() == 0
    assert out.is_file()
```

**Step 2: Run tests, expect FAIL**

Run: `. .venv/bin/activate && pytest tests/test_generate_marketplace.py -v`

Expected: FAIL — `scripts/generate_marketplace.py` does not exist.

**Step 3: Implement `scripts/generate_marketplace.py`**

Write `scripts/generate_marketplace.py`:

```python
"""Generate .claude-plugin/marketplace.json from catalog/catalog.yaml.

catalog.yaml is the source of truth (spec §5). The generator maps catalog
plugin entries to the marketplace.json plugin entry shape:

- relative source `{type: relative, path: rust}` → bare string `"rust"`
  (resolved against metadata.pluginRoot by Claude Code)
- git-subdir / github / url / npm source objects → pass through unchanged
- catalog-only fields (components, items) → stripped from the output
- first-party plugin entries have no `version` field (D11 SHA-ride)

Run as CLI:
    python scripts/generate_marketplace.py [--catalog PATH] [--output PATH]

Exit code: 0 on success, 1 on any error. Idempotent: re-running on the
same catalog produces byte-identical output (verified by Task 11).
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Iterable

import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_CATALOG = REPO_ROOT / "catalog" / "catalog.yaml"
DEFAULT_OUTPUT = REPO_ROOT / ".claude-plugin" / "marketplace.json"

# catalog.yaml-only fields that must NOT appear in marketplace.json.
_INTERNAL_FIELDS = {"components", "items"}


def _normalize_source(source: dict | str) -> dict | str:
    """Translate the catalog's source shape into the marketplace.json shape."""
    if isinstance(source, str):
        return source
    src_type = source.get("type")
    if src_type == "relative":
        return source["path"]
    # 3rd-party object: translate to the Claude Code marketplace shape
    # (which uses `source:` discriminator, not `type:`).
    out = {"source": src_type}
    for key in ("repo", "url", "path", "ref", "sha", "package", "headers"):
        if key in source:
            out[key] = source[key]
    return out


def _plugin_entry(catalog_plugin: dict) -> dict:
    """Project a catalog plugin entry into the marketplace.json entry shape."""
    out: dict = {
        "name": catalog_plugin["name"],
        "source": _normalize_source(catalog_plugin["source"]),
    }
    for optional in ("category", "tags", "description", "author"):
        if optional in catalog_plugin:
            out[optional] = catalog_plugin[optional]
    # Note: 'version' is intentionally NEVER added — first-party plugins
    # use SHA-ride (D11). 3rd-party entries get their version (if any)
    # from the catalog entry directly.
    if "version" in catalog_plugin:
        out["version"] = catalog_plugin["version"]
    return out


def generate(catalog_path: Path, output_path: Path) -> dict:
    """Read catalog.yaml, write marketplace.json; return the generated dict."""
    catalog = yaml.safe_load(catalog_path.read_text())
    if not isinstance(catalog, dict) or "marketplace" not in catalog:
        raise ValueError(
            f"{catalog_path}: top-level 'marketplace' key missing or not a mapping"
        )
    if not isinstance(catalog.get("plugins"), list):
        raise ValueError(f"{catalog_path}: 'plugins' must be a list")

    marketplace_section = catalog["marketplace"]
    plugins = [_plugin_entry(p) for p in catalog["plugins"]]

    generated = {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        **marketplace_section,
        "plugins": plugins,
    }

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(generated, indent=2, sort_keys=True) + "\n")
    return generated


def main(argv: Iterable[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--catalog", type=Path, default=DEFAULT_CATALOG)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args(argv)
    try:
        generate(args.catalog, args.output)
    except (ValueError, FileNotFoundError, yaml.YAMLError) as exc:
        print(f"generate: error: {exc}", file=sys.stderr)
        return 1
    print(f"generate: wrote {args.output}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

**Step 4: Run tests, expect PASS**

Run: `. .venv/bin/activate && pytest tests/test_generate_marketplace.py -v`

Expected: 6 tests pass.

**Step 5: Commit**

```bash
git add scripts/generate_marketplace.py \
        tests/test_generate_marketplace.py \
        tests/fixtures/catalog/empty.yaml \
        tests/fixtures/catalog/single_plugin.yaml
git commit -m "feat(scripts): add generate_marketplace.py

Reads catalog/catalog.yaml, writes .claude-plugin/marketplace.json.
Idempotent (verified by test_generate_is_idempotent). Strips
catalog-only fields (components, items). Translates relative sources
to bare strings; preserves 3rd-party source objects (git-subdir
etc.) as-is. Never adds a 'version' field to first-party plugins
(D11 SHA-ride).

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

## Task 11: `scripts/new_plugin.py` (TDD)

**Files:**
- Create: `scripts/new_plugin.py`
- Create: `scripts/templates/plugin/README.md`
- Create: `scripts/templates/plugin/plugin.json`
- Create: `tests/test_new_plugin.py`

**Interfaces:**
- Consumes: `scripts/templates/plugin/{README.md,plugin.json}`.
- Produces:
  - CLI: `scripts/new_plugin.py <name>` — creates `plugins/<name>/.claude-plugin/plugin.json` + `plugins/<name>/README.md` from templates. Fails if `plugins/<name>/` already exists.
  - Python API: `scaffold(repo_root: Path, name: str, description: str = "") -> Path` — returns the created plugin dir.

**Step 1: Write failing test**

Write `scripts/templates/plugin/README.md`:

```markdown
# <name>

> heretek marketplace — first-party plugin

## What

<description>

## Install

```bash
/plugin install <name>@heretek
```

## Components

<!-- list the components this plugin ships: skills, mcp, lsp, hooks, agents, output-styles -->

## License

MIT — see [LICENSE](../../LICENSE).
```

Write `scripts/templates/plugin/plugin.json`:

```json
{
  "name": "<name>",
  "displayName": "<displayName>",
  "description": "<description>",
  "author": {
    "name": "Heretek-AI",
    "url": "https://github.com/Heretek-AI"
  },
  "license": "MIT"
}
```

Write `tests/test_new_plugin.py`:

```python
"""Tests for scripts/new_plugin.py."""
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import new_plugin  # noqa: E402


def test_scaffold_creates_plugin_dir(tmp_path: Path) -> None:
    plugin_dir = new_plugin.scaffold(tmp_path, "rust", "Rust task plugin.")
    assert plugin_dir.is_dir()
    assert plugin_dir.name == "rust"
    assert (plugin_dir / ".claude-plugin" / "plugin.json").is_file()
    assert (plugin_dir / "README.md").is_file()


def test_scaffold_plugin_json_has_required_fields(tmp_path: Path) -> None:
    plugin_dir = new_plugin.scaffold(tmp_path, "rust", "Rust task plugin.")
    data = json.loads((plugin_dir / ".claude-plugin" / "plugin.json").read_text())
    assert data["name"] == "rust"
    assert data["description"] == "Rust task plugin."
    assert data["license"] == "MIT"


def test_scaffold_refuses_existing_dir(tmp_path: Path) -> None:
    new_plugin.scaffold(tmp_path, "rust", "Rust task plugin.")
    with pytest.raises(FileExistsError):
        new_plugin.scaffold(tmp_path, "rust", "duplicate")


def test_scaffold_rejects_invalid_name(tmp_path: Path) -> None:
    with pytest.raises(ValueError):
        new_plugin.scaffold(tmp_path, "Rust Plugin!", "bad name")


def test_main_creates_and_exits_zero(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        sys,
        "argv",
        ["new_plugin.py", "--repo-root", str(tmp_path), "rust", "Rust task plugin."],
    )
    assert new_plugin.main() == 0
    assert (tmp_path / "plugins" / "rust" / ".claude-plugin" / "plugin.json").is_file()
```

**Step 2: Run tests, expect FAIL**

Run: `. .venv/bin/activate && pytest tests/test_new_plugin.py -v`

Expected: FAIL — `scripts/new_plugin.py` does not exist.

**Step 3: Implement `scripts/new_plugin.py`**

Write `scripts/new_plugin.py`:

```python
"""Scaffold a new first-party plugin directory from a template.

Run as CLI:
    python scripts/new_plugin.py [--repo-root PATH] <name> [<description>]

Creates plugins/<name>/.claude-plugin/plugin.json + plugins/<name>/README.md
from scripts/templates/plugin/{plugin.json,README.md}. Fails if the plugin
directory already exists. Plugin name must match the catalog convention:
lowercase, digits, hyphens; first character alphanumeric.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Iterable

REPO_ROOT = Path(__file__).resolve().parent.parent
PLUGIN_NAME_RE = re.compile(r"^[a-z0-9][a-z0-9-]*$")


def _display_name(slug: str) -> str:
    """Convert 'rust-analyzer' → 'Rust Analyzer' for the displayName field."""
    return " ".join(part.capitalize() for part in slug.split("-"))


def scaffold(repo_root: Path, name: str, description: str = "") -> Path:
    """Create plugins/<name>/ from templates. Returns the created dir."""
    if not PLUGIN_NAME_RE.match(name):
        raise ValueError(
            f"invalid plugin name {name!r}: must match {PLUGIN_NAME_RE.pattern}"
        )
    plugin_dir = repo_root / "plugins" / name
    if plugin_dir.exists():
        raise FileExistsError(f"plugin directory already exists: {plugin_dir}")

    template_dir = Path(__file__).resolve().parent / "templates" / "plugin"
    plugin_json_tmpl = (template_dir / "plugin.json").read_text()
    readme_tmpl = (template_dir / "README.md").read_text()

    display = _display_name(name)
    plugin_json = (
        plugin_json_tmpl
        .replace("<name>", name)
        .replace("<displayName>", display)
        .replace("<description>", description)
    )
    readme = (
        readme_tmpl
        .replace("<name>", name)
        .replace("<displayName>", display)
        .replace("<description>", description)
    )

    manifest_dir = plugin_dir / ".claude-plugin"
    manifest_dir.mkdir(parents=True)
    (manifest_dir / "plugin.json").write_text(plugin_json)
    (plugin_dir / "README.md").write_text(readme)

    # Validate the generated plugin.json against the schema before declaring success.
    import validate as _validate  # local import to avoid circular at module load

    schemas_dir = _validate.DEFAULT_SCHEMAS_DIR
    schema = _validate._load_schema("plugin", schemas_dir)
    instance = json.loads(plugin_json)
    errors = [
        f"plugin.json: {e.message}"
        for e in __import__("jsonschema").Draft202012Validator(schema).iter_errors(instance)
    ]
    if errors:
        # Roll back to avoid leaving a broken plugin on disk.
        import shutil

        shutil.rmtree(plugin_dir)
        raise ValueError(f"generated plugin.json failed schema validation: {errors}")

    return plugin_dir


def main(argv: Iterable[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=REPO_ROOT)
    parser.add_argument("name", help="Plugin slug (lowercase, hyphens, digits).")
    parser.add_argument("description", nargs="?", default="")
    args = parser.parse_args(argv)
    try:
        plugin_dir = scaffold(args.repo_root, args.name, args.description)
    except (FileExistsError, ValueError) as exc:
        print(f"new-plugin: error: {exc}", file=sys.stderr)
        return 1
    print(f"new-plugin: scaffolded {plugin_dir}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

**Step 4: Run tests, expect PASS**

Run: `. .venv/bin/activate && pytest tests/test_new_plugin.py -v`

Expected: 5 tests pass.

**Step 5: Commit**

```bash
git add scripts/new_plugin.py \
        scripts/templates/plugin/README.md \
        scripts/templates/plugin/plugin.json \
        tests/test_new_plugin.py
git commit -m "feat(scripts): add new_plugin.py scaffolder

Creates plugins/<name>/.claude-plugin/plugin.json + README.md from
templates. Validates the generated plugin.json against the schema
before declaring success; rolls back on failure. Used to scaffold
all 11 first-party plugins in Task 12.

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

## Task 12: Generate `marketplace.json` from seed catalog; verify `diff=0` on re-run

**Files:**
- Create: `.claude-plugin/marketplace.json` (generated)

**Step 1: Run generator on the seed catalog**

Run: `. .venv/bin/activate && python scripts/generate_marketplace.py`

Expected: prints `generate: wrote /home/john/Projects/heretek-claude-harness/.claude-plugin/marketplace.json`.

**Step 2: Verify the file exists and parses**

Run: `. .venv/bin/activate && python -c "import json; d = json.load(open('.claude-plugin/marketplace.json')); print('name:', d['name']); print('plugins:', len(d['plugins'])); print('plugin names:', [p['name'] for p in d['plugins']])"`
Expected: `name: heretek`, `plugins: 11`, `plugin names: ['rust', 'python', 'js-ts', 'web-frontend', 'hooks', 'security', 'skills-pack', 'mcp-pack', 'lsp-pack', 'agents', 'output-styles']`.

**Step 3: Run validate against the generated marketplace**

Run: `. .venv/bin/activate && python scripts/validate.py`

Expected: prints `validate: OK (all manifests conform to JSON Schemas)` and exits 0.

**Step 4: Re-run generator + assert diff is empty (idempotency check)**

Run: `. .venv/bin/activate && python scripts/generate_marketplace.py && git add .claude-plugin/marketplace.json && git diff --cached --exit-code`

Expected: `git diff --cached --exit-code` exits 0 (no diff). The generator is idempotent on the seed catalog.

**Step 5: Commit**

```bash
git add .claude-plugin/marketplace.json
git commit -m "feat(marketplace): generate marketplace.json from seed catalog

11 first-party plugins registered as relative sources. Generator is
idempotent (verified: re-running produces byte-identical output, so
'git diff --exit-code' passes). Validator passes against the current
schema. No items[] entries yet — SP3/SP4 fill them via curation.

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

## Task 13: Scaffold all 11 first-party plugin directories

**Files:**
- Create: `plugins/<name>/.claude-plugin/plugin.json` × 11
- Create: `plugins/<name>/README.md` × 11

**Step 1: Scaffold all 11 plugins**

Run, for each plugin in this order:

```bash
. .venv/bin/activate

python scripts/new_plugin.py rust         "Rust task plugin: rust-analyzer LSP, cargo-check skill, task-scoped MCP."
python scripts/new_plugin.py python       "Python task plugin: basedpyright LSP, ruff-driven skill, pytest patterns."
python scripts/new_plugin.py js-ts        "JavaScript/TypeScript task plugin: biome/oxc LSP+formatter, tsconfig-aware skills."
python scripts/new_plugin.py web-frontend "Web frontend task plugin: chrome-devtools-mcp, lighthouse skill, storybook integration."
python scripts/new_plugin.py hooks        "Hooks flagship: 3-layer quality gates (fast blocking, slow on-demand, git pre-commit)."
python scripts/new_plugin.py security     "Security cross-cutting plugin: security-research skill, audit checklists, audit commands."
python scripts/new_plugin.py skills-pack  "Generic skills pack: caveman, superpowers, find-skills, review-work."
python scripts/new_plugin.py mcp-pack     "Generic MCP servers: context7, github-mcp-server, codebase-memory-mcp, serena."
python scripts/new_plugin.py lsp-pack     "Generic LSP configs: rust-analyzer, basedpyright/oxc, gopls, clangd."
python scripts/new_plugin.py agents       "Reusable sub-agent definitions: code-reviewer, security-reviewer, test-engineer."
python scripts/new_plugin.py output-styles "Curated output-style presets: terse, detailed, tabular, explanatory."
```

Each command prints `new-plugin: scaffolded plugins/<name>` and exits 0.

**Step 2: Verify all 11 plugin directories exist with required files**

Run: `. .venv/bin/activate && ls plugins/ && echo "---" && for d in plugins/*/; do echo "$d:"; ls "$d.claude-plugin/" 2>/dev/null; ls "$d"README.md 2>/dev/null && echo "  README.md ok"; done`

Expected: 11 entries under `plugins/`. Each has `.claude-plugin/plugin.json` and `README.md`.

**Step 3: Run validate against all 11 manifests**

Run: `. .venv/bin/activate && python scripts/validate.py`

Expected: prints `validate: OK (all manifests conform to JSON Schemas)` and exits 0. All 11 plugin.json files validate.

**Step 4: Commit**

```bash
git add plugins/
git commit -m "feat(plugins): scaffold 11 first-party plugin directories

4 task (rust, python, js-ts, web-frontend) + 7 cross-cutting (hooks,
security, skills-pack, mcp-pack, lsp-pack, agents, output-styles).
Each has .claude-plugin/plugin.json (MIT, author=Heretek-AI) and
README.md from the new-plugin template. Empty items[] for now;
SP3/SP4 fill via the curation pipeline.

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

## Task 14: CI workflow — `.github/workflows/validate.yml`

**Files:**
- Create: `.github/workflows/validate.yml`

**Step 1: Create `.github/workflows/` directory**

Run: `mkdir -p .github/workflows`

**Step 2: Write the workflow**

Create `.github/workflows/validate.yml`:

```yaml
name: validate

on:
  pull_request:
    branches: [main]
  push:
    branches: [main]

jobs:
  validate:
    name: Validate marketplace + manifests
    runs-on: ubuntu-latest
    timeout-minutes: 10
    steps:
      - uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: "3.12"
          cache: pip

      - name: Install deps
        run: |
          python -m pip install --upgrade pip
          pip install -r requirements-dev.txt

      - name: Run schema validation
        run: python scripts/validate.py

      - name: Regenerate marketplace.json
        run: python scripts/generate_marketplace.py

      - name: Assert catalog.yaml → marketplace.json is in sync
        run: |
          if ! git diff --exit-code .claude-plugin/marketplace.json; then
            echo "::error::marketplace.json is out of sync with catalog.yaml."
            echo "::error::Run 'python scripts/generate_marketplace.py' locally and commit the result."
            exit 1
          fi

      - name: Run tests
        run: pytest
```

**Step 3: Commit**

```bash
git add .github/workflows/validate.yml
git commit -m "ci: add validate workflow (schema + generation diff + tests)

Runs on every PR + push to main:
1. scripts/validate.py — JSON Schema check on marketplace.json + all
   plugin manifests
2. scripts/generate_marketplace.py — regenerate from catalog.yaml
3. git diff --exit-code — fail if marketplace.json drifted from catalog
4. pytest — full test suite

Spec §7 CI bar: schema + generation + tests. Smoke test workflow
(smoke-test.yml) is added in SP4 (Phase 6).

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

## Task 15: Minimal `README.md`

**Files:**
- Create: `README.md`

**Step 1: Write `README.md`**

```markdown
# heretek

> Opinionated Claude Code plugin marketplace: task plugins, quality-gate hooks, curated MCP/LSP/skills.

## Install

```bash
# Add the marketplace (once)
/plugin marketplace add heretek https://github.com/Heretek-AI/heretek-claude-harness

# Install a plugin
/plugin install rust@heretek
/plugin install hooks@heretek
# ... 11 plugins total — see "Plugins" below
```

## Plugins

| Plugin | Category | What it ships |
|---|---|---|
| `rust` | task | rust-analyzer LSP, cargo-check skill, task-scoped MCP |
| `python` | task | basedpyright LSP, ruff-driven skill, pytest patterns |
| `js-ts` | task | biome/oxc LSP+formatter, tsconfig-aware skills |
| `web-frontend` | task | chrome-devtools-mcp, lighthouse skill, storybook integration |
| `hooks` | cross (flagship) | 3-layer quality gates: fast blocking (<100ms), slow on-demand (`/quality-gate:run`), git pre-commit (`/hooks:install-git-hooks`) |
| `security` | cross | security-research skill, audit checklists, audit commands |
| `skills-pack` | cross | caveman, superpowers, find-skills, review-work |
| `mcp-pack` | cross | context7, github-mcp-server, codebase-memory-mcp, serena |
| `lsp-pack` | cross | LSP configs for rust-analyzer, basedpyright, gopls, clangd |
| `agents` | cross | code-reviewer, security-reviewer, test-engineer |
| `output-styles` | cross | terse, detailed, tabular, explanatory presets |

## Architecture

- `catalog/catalog.yaml` — source of truth (every plugin, every item, every vetting entry).
- `.claude-plugin/marketplace.json` — generated, never hand-edited. Regenerated by `scripts/generate_marketplace.py`.
- `scripts/validate.py` — JSON Schema enforcement on every manifest.
- `.github/workflows/validate.yml` — runs `validate` + regeneration + tests on every PR.

## License

MIT — see [LICENSE](LICENSE).
```

**Step 2: Commit**

```bash
git add README.md
git commit -m "docs: add README with install instructions + plugin overview

Minimal v1 README per SP1 exit criteria. The expanded README (full
install walkthrough, screenshot, contributing/CHANGELOG links) lands
in SP4 (Phase 6) per the marketplace identity work.

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

## Self-Review

### 1. Spec coverage

Walking through each requirement in `docs/superpowers/specs/2026-08-03-heretek-marketplace-design.md`:

| Spec section | Plan tasks |
|---|---|
| §1 Vision | Implicit — the marketplace installs via the README (Task 15) |
| §2 D1 monorepo + external sources | Task 9 (catalog seed), Task 10 (generator handles relative + git-subdir/github/url/npm) |
| §2 D4 public OSS day one | Task 1 (LICENSE=MIT), Task 4-7 schemas, Task 14 (CI) |
| §2 D5 taxonomy | Task 9 (catalog has all 11 in correct categories), Task 13 (all 11 scaffolds) |
| §2 D6 hooks architecture | Task 5 (hooks schema) — Layer 1/2/3 implementation is SP2 |
| §2 D7 vetting bar + source-audit + no critical CVEs | Task 9 (catalog schema includes vetting block); CI lint deferred to SP3 (no `items[]` entries yet to lint) |
| §2 D8 catalog.yaml is source of truth | Task 9, 10, 12 (generator + idempotency) |
| §2 D9 repo hygiene | Task 1 (LICENSE, ref.text removal, secret scan) |
| §2 D11 SHA-ride versioning | Task 10 (generator never adds `version` to first-party) |
| §2 D12 CI bar (schema + generation diff + smoke test) | Task 14 (schema + diff + tests); smoke test deferred to SP4 (Phase 6) per spec §10 |
| §2 D13 identity (heretek, Heretek-AI) | Task 9 (catalog `marketplace.name`), Task 10 (owner.name), Task 15 (README) |
| §2 D14 MIT for own code | Task 1 (LICENSE), Task 11 (plugin.json template has `license: MIT`) |
| §2 D15 hooks strict ownership | Implicit — only the `hooks` plugin has any hook manifest path in catalog seed; SP2 implements |
| §2 D16 versioning re-confirm | Task 10 |
| §2 D17 Heretek-AI org | Deferred to SP4 — SP1 doesn't create the org, just registers the marketplace under that owner name |
| §3 architecture overview | Tasks 9-12 implement the catalog.yaml → marketplace.json pipeline |
| §4 hooks architecture | Task 5 schema + Task 9 catalog seed (hooks plugin listed); SP2 implements the runtime |
| §5 catalog.yaml schema | Task 9 (initial seed matches schema), Task 10 (generator) |
| §6 vetting bar | Task 9 schema includes `vetting:` block; CI lint deferred to SP3 (no entries yet) |
| §7 CI/CD validate.yml | Task 14 |
| §8 11 plugin cards | Task 9 (catalog entries), Task 13 (plugin directories) |
| §9 repo layout | Tasks 1, 2, 9-15 collectively create the layout in spec §9 |
| §11 SP1 scope (Phases 0+1) | All 15 tasks cover the SP1 scope: cleanup, schemas, validate, catalog seed, generator, scaffolder, generation, plugin scaffolds, CI, README |
| §12 risks | Risk #1, #4 mitigated by Tasks 14 (CI catches schema drift), 8-10 (catalog pipeline catches pin errors before they ship). Risks #2-3, #5-10 are SP2-SP4 scope. |

Gaps: SP1 has no smoke-test workflow (deferred to SP4 per spec §10 — phase 6 / aggregation + launch). No `SECURITY.md` (Phase 6 / SP4). No `CONTRIBUTING.md` (Phase 6 / SP4). No `docs/recommended-marketplaces.md` (Phase 5 / SP4). All deferred work tracked in spec §11.

### 2. Placeholder scan

Grep for forbidden patterns: `TBD`, `TODO`, `FIXME`, `XXX`, "implement later", "fill in details", "add appropriate error handling", "write tests for the above", "similar to Task N", missing code blocks in code steps.

- `TBD` / `TODO` / `FIXME` / `XXX`: none.
- "implement later" / "fill in details" / "add appropriate error handling" / "similar to Task N": none.
- "write tests for the above": every test step has actual code.
- Missing code blocks in code steps: none — every Python code step has a full code block.

### 3. Type / name consistency

Cross-task name audit:

- `validate.validate_all(repo_root, schemas_dir=...)` — used in Task 8 tests, Task 10 implementation, Task 12 invocation, Task 14 CI step. Consistent.
- `generate_marketplace.generate(catalog_path, output_path) -> dict` — used in Task 10 tests and implementation, Task 12 invocation, Task 14 CI step. Consistent.
- `new_plugin.scaffold(repo_root, name, description="") -> Path` — used in Task 11 tests, implementation, Task 13 bulk invocation. Consistent.
- `validate.DEFAULT_SCHEMAS_DIR = REPO_ROOT / "tests" / "schemas"` — used in Task 11 (new_plugin imports it). Consistent.
- `validate._load_schema(name, schemas_dir)` — used by Task 11 (new_plugin). The leading underscore signals "internal" but Task 11 legitimately uses it; that's the kind of justified use the underscore allows. Acceptable.
- Catalog YAML field names (`name`, `category`, `tags`, `source`, `components`, `items`) — used consistently across Task 9 (seed), Task 10 (generator), Task 12 (verify). Consistent.
- Marketplace JSON field names (`name`, `source`, `category`, `tags`, `description`) — used consistently in Task 10 generator output. Consistent.
- Schema filenames: `marketplace.schema.json`, `plugin.schema.json`, `hooks.schema.json`, `mcp.schema.json`, `lsp.schema.json` — referenced consistently in Tasks 3-8.
- Fixture paths: `tests/fixtures/{marketplace,plugin,hooks,mcp,lsp,catalog}/{valid,invalid}.{json,yaml}` — used consistently in Tasks 3-7 (valid/invalid) and Task 10 (catalog fixtures).
- Plugin slug pattern `^[a-z0-9][a-z0-9-]*$` — same regex in marketplace schema (Task 3), plugin schema (Task 4), and new_plugin validation (Task 11). Consistent.
- 40-char SHA pattern `^[a-f0-9]{40}$` — Task 3 marketplace schema. Task 10 test uses a 40-char fixture. Consistent.

No mismatches found.

---

## Exit criteria (SP1)

When all 15 tasks are complete:

1. **Marketplace installs cleanly.** Running `/plugin marketplace add heretek <repo-url>` + `/plugin install <name>@heretek` for each of the 11 first-party plugins succeeds with zero failures. (`plugin.json` files exist + validate; `marketplace.json` is in sync with `catalog.yaml`.)
2. **`catalog.yaml` → `marketplace.json` diff is 0.** Re-running `scripts/generate_marketplace.py` produces byte-identical output. CI enforces this on every PR (Task 14).
3. **CI `validate` is green.** `.github/workflows/validate.yml` runs on every PR and runs `scripts/validate.py` + generator diff check + pytest. (Task 14.)
4. **Repo is public-safe.** `LICENSE` (MIT) at root; no personal harness state in tracked files; secret scan clean. (Task 1.)

The next sub-project (SP2 — Hooks flagship) can begin from this base without rework.