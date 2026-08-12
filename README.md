# `heretek-claude-harness`

> Open-source **plugin marketplace framework and distribution CLI** that installs mechanical quality guardrails, Claude Code hooks, MCP servers, and language packs into **target developer repositories**.

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Marketplace: heretek](https://img.shields.io/badge/marketplace-heretek-blueviolet)](https://github.com/Heretek-AI/heretek-claude-harness)
[![Python: 3.10+](https://img.shields.io/badge/python-3.10%2B-blue)](pyproject.toml)
[![Type Checking: Pyright Strict](https://img.shields.io/badge/pyright-strict-success)](pyproject.toml)
[![Linting: Ruff](https://img.shields.io/badge/ruff-passing-brightgreen)](pyproject.toml)

---

## Overview

`heretek-claude-harness` is designed to allow developers (and automated Claude Code sessions) to install curated marketplace packages into any project workspace.

These installed packages enforce deterministic, fast feedback loops (`ruff`, `pyright`, `cargo clippy`, `biome`, `ast-grep`) directly inside target developer repositories to prevent model hallucinations, context bloat, and specification drift—especially when executing smaller models like Qwen 3.6 27B.

> [!IMPORTANT]
> **Key Architecture Principle**: This repository is the **packaging standard, marketplace catalog registry, installer CLI, and distribution engine**. Running `heretek install` projects standalone plugin assets, hooks, and LSP/MCP configs into user target repositories.

---

## Architectural Pillars

1. **Marketplace Registry & Catalog** (`catalog/catalog.yaml`): The central index mapping first-party and curated third-party marketplace packages, version pins, and dependency relationships.
2. **Packaging Schemas** (`tests/schemas/`): JSON Schema definitions (Draft 2020-12) validating installable package manifests (`plugin.schema.json`, `hooks.schema.json`, `mcp.schema.json`, `lsp.schema.json`, `marketplace.schema.json`).
3. **Packaging & Distribution CLI** (`scripts/heretek_cli.py`):
   - `heretek install <pack-name>`: Deploys hooks, configs, LSP/MCP declarations, and interceptor scripts into target project `.claude/` directories.
   - `heretek validate`: Validates all plugin packages and marketplace manifests against JSON Schemas.
   - `heretek build-catalog`: Re-indexes `catalog/catalog.yaml` and builds canonical `.claude-plugin/marketplace.json`.
4. **LLM Diagnostic Error Translator**: A lightweight utility in the hook bundle (`plugins/hooks/scripts/error_translator.py`) that converts verbose compiler and linter stderr/stdout into minimalist high-signal error blocks (e.g. `[ERROR] main.py:12:5 - Type mismatch: expected str, got int`).

---

## Installable Marketplace Packages (`plugins/`)

`heretek` provides out-of-the-box installable plugin packages:

| Package | Category | Description | Key Assets Deployed |
| :--- | :--- | :--- | :--- |
| **`plugins/python`** | `task` | Python language pack | `pyright` & `ruff-lsp` declarations (`.lsp.json`), fast quality skills |
| **`plugins/rust`** | `task` | Rust language pack | `rust-analyzer` declaration (`.lsp.json`), `cargo check` / `cargo clippy` skills |
| **`plugins/js-ts`** | `task` | JavaScript & TypeScript pack | `biome` & `tsc` declarations (`.lsp.json`), typecheck skills |
| **`plugins/hooks`** | `quality-gate` | Core mechanical hook bundle | `hooks.json`, `secrets_pre_tool.py`, `fast_gate.py`, `stale_dep_intercept.py`, `error_translator.py` |
| **`plugins/mcp-pack`** | `tools` | Codebase memory & context tools | Pre-configured `.mcp.json` server declarations (`codebase-memory-mcp`, `context7`, `serena`) |

---

## Quick Start & Usage

### Installing Plugin Packs into Target Projects
To deploy a plugin pack into a target developer repository:

```bash
# Install Python language pack into target repository
python scripts/heretek_cli.py install python --target /path/to/target/repo

# Install mechanical quality hooks & interceptors into target repository
python scripts/heretek_cli.py install hooks --target /path/to/target/repo

# Install MCP codebase memory servers into target repository
python scripts/heretek_cli.py install mcp-pack --target /path/to/target/repo
```

This populates the target workspace's `.claude/` directory with `.lsp.json`, `.mcp.json`, `hooks.json`, and supporting Python interceptor scripts.

### Schema Validation & Catalog Building
```bash
# Validate all marketplace and plugin manifests against JSON Schemas
python scripts/heretek_cli.py validate

# Re-generate .claude-plugin/marketplace.json from catalog/catalog.yaml
python scripts/heretek_cli.py build-catalog
```

---

## Developer Workflows

### Quality Protocol & Commands

```bash
# 1. Run full test suite
pytest

# 2. Enforce strict Pyright type checking
.venv/bin/basedpyright scripts

# 3. Enforce Ruff code quality rules
ruff check .

# 4. Execute full local CI pipeline
bash scripts/ci.sh
```

---

## Documentation

- **[`CLAUDE.md`](CLAUDE.md)** — Quick-reference guide for developer workflows, commands, and repository architecture.
- **[`AGENTS.md`](AGENTS.md)** — Operational guidelines for AI coding assistants working on or extending this repository.
- **[`CONTRIBUTING.md`](CONTRIBUTING.md)** — Guidelines for contributing new plugin packages and marketplace catalog entries.
- **[`SECURITY.md`](SECURITY.md)** — Supply-chain security policy and vulnerability reporting.

---

## License

Distributed under the MIT License. See [`LICENSE`](LICENSE) for details.
