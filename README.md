# `heretek-claude-harness`

> Open-source **plugin marketplace framework and distribution CLI** that installs mechanical quality guardrails, Claude Code hooks, MCP servers, and language packs into **target developer repositories**.

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Marketplace: heretek](https://img.shields.io/badge/marketplace-heretek-blueviolet)](https://github.com/Heretek-AI/heretek-claude-harness)
[![Python: 3.10+](https://img.shields.io/badge/python-3.10%2B-blue)](pyproject.toml)
[![Type Checking: Pyright Strict](https://img.shields.io/badge/pyright-strict-success)](pyproject.toml)
[![Linting: Ruff](https://img.shields.io/badge/ruff-passing-brightgreen)](pyproject.toml)

---

## Overview

`heretek-claude-harness` allows developers (and automated Claude Code sessions) to install curated, opinionated quality packages into any target project workspace.

These packages enforce deterministic, fast feedback loops (`ruff`, `basedpyright`, `cargo clippy`, `biome`, `fallow`, `semgrep`, `gitleaks`) directly inside target developer repositories to prevent model hallucinations, context bloat, and specification drift.

> [!IMPORTANT]
> **Key Architecture Principle**: This repository is the **packaging standard, marketplace catalog registry, installer CLI, and distribution engine**. Running `python scripts/heretek_cli.py install <pack>` projects standalone plugin assets, hooks, and LSP/MCP configs into user target repositories.

---

## The 9 Logical Quality Packs

`heretek` provides 9 out-of-the-box installable plugin pack categories:

| Package | Category | Description | Key Deployed Assets |
| :--- | :--- | :--- | :--- |
| **`plugins/best-practices`** | `cross` | Output & persona quality pack | `humanizer` (anti-slop rules), `i-have-adhd` (Action-First), `ponytail` (7-Rung Lazy Ladder), `caveman` (terse mode), `outline-driven-dev` |
| **`plugins/quality-audit`** | `cross` | Production audit & decay analysis | `launchworthy` (5-domain audit: Auth, Data, Frontend, Infra, Ops), `brooks-lint` (decay risks R1-R6, T1-T6) |
| **`plugins/pre-commit`** | `cross` | Git commit/push mechanical gates | SHA-pinned `.pre-commit-config.yaml` (`ruff`, `biome`, `cargo clippy`, `fallow`, `semgrep`, `gitleaks`, `shellcheck`), `install_precommit.sh` |
| **`plugins/ci-cd`** | `cross` | GitHub Actions workflow templates | `pre-commit.yml`, `security-scan-digest.yml`, `shellcheck.yml`, `validate.yml` |
| **`plugins/agents`** | `cross` | Specialized subagent team | `architecture-auditor`, `build-error-resolver`, `code-reviewer`, `database-reviewer`, `performance-optimizer`, `security-reviewer`, `test-engineer` |
| **`plugins/hooks`** | `quality-gate` | Core mechanical interceptor bundle | `ir_shell_parser.py` (IR shell parser & secret/destructive command block), `circuit_breaker.py` (consecutive error filter), `fast_gate.py`, `secrets_pre_tool.py` |
| **`plugins/mcp-pack`** | `tools` | Token-efficient MCP servers | Pre-configured `.mcp.json` (`codebase-memory-mcp` prefix trees, `context7` live docs, `claude-mem` 3-layer progressive disclosure, `github-mcp-server`) |
| **`plugins/lsp-pack`** | `tools` | 38+ Language Server suite | Pre-configured `.lsp.json` for 38+ language servers (`basedpyright`, `gopls`, `rust-analyzer`, `clangd`, `jdtls`, `vtsls`, `solidity-ls`) |
| **`plugins/{lang}`** | `task` | Language-specific task packs | `python`, `rust`, `js-ts`, `go`, `cpp`, `java`, `web-frontend` (LSP server declarations & `check` skills) |

---

## Architectural Pillars

1. **Marketplace Registry & Catalog** (`catalog/catalog.yaml`): The central index mapping first-party and curated third-party marketplace packages, version pins, and dependency relationships.
2. **Packaging Schemas** (`tests/schemas/`): JSON Schema definitions (Draft 2020-12) validating installable package manifests (`plugin.schema.json`, `hooks.schema.json`, `mcp.schema.json`, `lsp.schema.json`, `marketplace.schema.json`).
3. **Packaging & Distribution CLI** (`scripts/heretek_cli.py`):
   - `heretek install <pack-name>`: Deploys hooks, configs, LSP/MCP declarations, and interceptor scripts into target project `.claude/` directories.
   - `heretek validate`: Validates all plugin packages and marketplace manifests against JSON Schemas.
   - `heretek build-catalog`: Re-indexes `catalog/catalog.yaml` and builds canonical `.claude-plugin/marketplace.json`.

---

## Quick Start & Usage

### Installing Plugin Packs into Target Projects
To deploy a plugin pack into a target developer repository:

```bash
# Install Best Practices pack (Humanizer, Action-First, Ponytail) into target repository
python scripts/heretek_cli.py install best-practices --target /path/to/target/repo

# Install Production Quality Audit pack into target repository
python scripts/heretek_cli.py install quality-audit --target /path/to/target/repo

# Install Pre-Commit git hooks into target repository
python scripts/heretek_cli.py install pre-commit --target /path/to/target/repo

# Install Go language pack into target repository
python scripts/heretek_cli.py install go --target /path/to/target/repo
```

This populates the target workspace's `.claude/` directory with `.lsp.json`, `.mcp.json`, `hooks.json`, and supporting Python/Shell interceptor scripts.

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
ruff check plugins scripts tests

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
