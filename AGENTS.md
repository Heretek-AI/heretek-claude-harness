# AI Coding Assistant Operational Guidelines (`AGENTS.md`)

This document defines mandatory operational rules and architectural constraints for AI agents (Claude Code, Gemini, Antigravity, or subagents) contributing to or maintaining `heretek-claude-harness`.

---

## 1. Primary Directive

`heretek-claude-harness` is an open-source **plugin marketplace framework and distribution CLI** designed to install mechanical quality guardrails (`ruff`, `pyright`, `cargo clippy`, `biome`, `ast-grep`), Claude Code hooks, MCP servers, and language packs into **target developer repositories**.

> [!IMPORTANT]
> **Crucial Distinction**: Do not simply configure static linters for *this* harness repository. You are building the **package schemas, marketplace catalog registry, installer CLI, and installable plugin assets** that get deployed into target user repositories.

---

## 2. Marketplace Architecture & 16-Pack Catalog

The Heretek Marketplace consists of **16 first-party plugin packages**:

| Plugin Package | Category | Description | Primary Components |
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

## 3. Zero-Chuff Architecture Principles

1. **No Multi-Agent Driver Loops**: Do NOT re-introduce multi-stage subagent loop frameworks, breakdowner/critic prompt chains, or over-engineered multi-agent orchestrations.
2. **Lean Reference Runner**: `scripts/issue_runner.py` is the single reference runner demonstrating the feedback loop (read task -> execute -> mechanical gate intercept -> feed errors back on failure -> pass).
3. **Deterministic Interceptors**: All hooks in `plugins/hooks/scripts/` must be fast, self-contained, fail-open when appropriate, and complete within tight latency boundaries (<100ms for fast gates).
4. **Pristine Root Structure**: Keep the repository root clean and minimal (`pyproject.toml`, `.gitignore`, `LICENSE`, `README.md`, `CLAUDE.md`, `AGENTS.md`). Do not pollute the root directory with temporary logs, scratch files, or unvetted specs.

---

## 4. Distribution CLI Subcommands (`heretek`)

- `heretek init [--target DIR]`: Auto-detects target project language manifests (9 languages supported) and deploys matching plugin packs.
- `heretek status [--target DIR]`: Displays terminal quality scorecard (0-100 pts), deployed plugins inventory, and pre-commit state.
- `heretek metrics`: Benchmarks local fast-gate hook execution latencies to enforce <100ms response SLA.
- `heretek install <pack-name>`: Installs a specific plugin package into a target directory.
- `heretek validate`: Validates all plugin manifests and marketplace catalog against JSON Schemas.
- `heretek build-catalog`: Regenerates `.claude-plugin/marketplace.json` from `catalog/catalog.yaml`.
- `heretek telemetry <show|grep|diff|export>`: Inspects local hook event logs.

---

## 5. Verification Protocol for AI Agents

Before declaring any task or feature complete, you MUST execute and confirm zero errors on:

```bash
# 1. Full test suite
pytest

# 2. Marketplace & plugin schema validation
python scripts/heretek_cli.py validate

# 3. Strict Pyright type checking
.venv/bin/basedpyright scripts

# 4. Ruff linter check
ruff check plugins scripts tests
```

---

## 6. Artifact Protocol

When working on non-trivial plans or rebuild tasks:
1. Maintain **`task_list.md`** as a step-by-step checklist.
2. Maintain **`implementation_plan.md`** detailing component changes.
3. Maintain **`verification.md`** documenting concrete execution logs.
4. Update **`walkthrough.md`** summarizing architectural changes and verification outputs.
