# `heretek-claude-harness` (DEPRECATED & ARCHIVED)

> [!WARNING]
> **This repository is deprecated, superseded, and archived.**
> Please use **[`@heretek-ai/agent-proof`](https://github.com/Heretek-AI/Agent-Proof)** ([npm: `@heretek-ai/agent-proof`](https://www.npmjs.com/package/@heretek-ai/agent-proof)) for sub-second mechanical hard-gate AI governance, LSP diagnostic streaming, and zero-dependency pre-commit enforcement.

---

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
> **Key Architecture Principle**: This repository is the **packaging standard, marketplace catalog registry, installer CLI, and distribution engine**. Running `npx heretek init` projects standalone plugin assets, hooks, and LSP/MCP configs into user target repositories in under 1 second.

---

## Quick Start & Usage

### Zero-Config Auto-Detection (`npx heretek init`)
To automatically inspect any repository and deploy matching quality packs:

```bash
# Auto-detect target repository project type and install matching packs
npx heretek init --target /path/to/target/repo
```

### Terminal Scorecard TUI (`npx heretek status`)
To view repository agentic readiness score (0-100 pts), deployed plugins inventory, and pre-commit status:

```bash
npx heretek status --target /path/to/target/repo
```

### Latency Benchmark (`npx heretek metrics`)
To benchmark local fast-gate hook execution latencies:

```bash
npx heretek metrics
```

---

## The 16 Marketplace Plugin Packs

`heretek` provides 16 first-party installable plugin packages:

| Package | Category | Description | Key Deployed Assets |
| :--- | :--- | :--- | :--- |
| **`python`** | `task` | Python language pack with basedpyright LSP and ruff checker | LSP, `skills/python-check` |
| **`rust`** | `task` | Rust language pack with rust-analyzer LSP and clippy checker | LSP, `skills/rust-check` |
| **`typescript`** | `task` | TypeScript/JS pack with vtsls LSP and biome/tsc checker | LSP, `skills/ts-check` |
| **`go`** | `task` | Go language pack with gopls LSP and go vet checker | LSP, `skills/go-check` |
| **`cpp`** | `task` | C/C++ language pack with clangd LSP and clang-tidy checker | LSP, `skills/cpp-check` |
| **`java`** | `task` | Java language pack with jdtls LSP and spotbugs checker | LSP, `skills/java-check` |
| **`ruby`** | `task` | Ruby language pack with solargraph LSP and rubocop checker | LSP, `skills/ruby-check` |
| **`elixir`** | `task` | Elixir language pack with elixir-ls LSP and mix credo checker | LSP, `skills/elixir-check` |
| **`csharp`** | `task` | C# / .NET language pack with csharp-ls LSP and dotnet format | LSP, `skills/csharp-check` |
| **`web-frontend`** | `task` | Web UI & DevTools pack with Chrome DevTools MCP & skills | MCP, `skills/frontend-design` |
| **`fallow`** | `task` | Dead code & token blast-radius auditor for Rust & TS | `skills/fallow-check` |
| **`best-practices`** | `cross` | Quality & communication skills (`caveman`, `humanizer`, etc.) | `skills/*` |
| **`quality-audit`** | `cross` | Codebase agentic readiness scorecard and quality audit | `skills/agentic-readiness` |
| **`pre-commit`** | `cross` | Pre-commit guard configuration with SHA-pinned hooks | `scripts/install_precommit.sh` |
| **`ci-cd`** | `cross` | GitHub Actions workflow templates (`pre-commit.yml`, etc.) | `.github/workflows/` |
| **`hooks`** | `core` | Fast-gate (<100ms), secrets scanner, circuit breaker, & protection | `hooks.json`, `scripts/*.py` |

---

## 9-Language Task Matrix

Heretek's `init` command auto-detects and configures standard language tools across **9 languages**:

| Language | LSP Server | Linter / Checker Skill | Manifest Detection File(s) |
| :--- | :--- | :--- | :--- |
| **Python** | `basedpyright` | `ruff` + `basedpyright` | `pyproject.toml`, `setup.py`, `requirements.txt` |
| **Rust** | `rust-analyzer` | `cargo clippy` + `rustfmt` | `Cargo.toml` |
| **TypeScript / JS**| `vtsls` | `biome` / `oxlint` + `tsc` | `package.json`, `tsconfig.json` |
| **Go** | `gopls` | `go vet` + `staticcheck` | `go.mod` |
| **C / C++** | `clangd` | `clang-tidy` + `cppcheck` | `CMakeLists.txt`, `Makefile`, `compile_commands.json` |
| **Java** | `jdtls` | `checkstyle` + `spotbugs` | `pom.xml`, `build.gradle` |
| **Ruby** | `solargraph` | `rubocop` | `Gemfile`, `.rubocop.yml`, `Rakefile` |
| **Elixir** | `elixir-ls` | `mix credo` + `mix format` | `mix.exs` |
| **C# / .NET** | `csharp-ls` | `dotnet format` + `dotnet build` | `*.csproj`, `*.sln`, `global.json` |

---

## Developer Workflows

### Testing & Quality Protocol

```bash
# 1. Run full test suite
pytest

# 2. Enforce strict Pyright type checking
.venv/bin/basedpyright scripts

# 3. Enforce Ruff code quality rules
ruff check plugins scripts tests

# 4. Validate all plugin manifests against JSON Schemas
python scripts/heretek_cli.py validate

# 5. Execute full local CI pipeline
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
