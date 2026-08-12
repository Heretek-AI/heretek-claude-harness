# AI Coding Assistant Operational Guidelines (`AGENTS.md`)

This document defines mandatory operational rules and architectural constraints for AI agents (Claude Code, Gemini, Antigravity, or subagents) contributing to or maintaining `heretek-claude-harness`.

---

## 1. Primary Directive

`heretek-claude-harness` is an open-source **plugin marketplace framework and distribution CLI** designed to install mechanical quality guardrails (`ruff`, `pyright`, `cargo clippy`, `biome`, `ast-grep`), Claude Code hooks, MCP servers, and language packs into **target developer repositories**.

> [!IMPORTANT]
> **Crucial Distinction**: Do not simply configure static linters for *this* harness repository. You are building the **package schemas, marketplace catalog registry, installer CLI, and installable plugin assets** that get deployed into target user repositories.

---

## 2. Zero-Chuff Architecture Principles

1. **No Multi-Agent Driver Loops**: Do NOT re-introduce multi-stage subagent loop frameworks, breakdowner/critic prompt chains, or over-engineered multi-agent orchestrations.
2. **Lean Reference Runner**: `scripts/issue_runner.py` is the single reference runner demonstrating the feedback loop (read task -> execute -> mechanical gate intercept -> feed errors back on failure -> pass).
3. **Deterministic Interceptors**: All hooks in `plugins/hooks/scripts/` must be fast, self-contained, fail-open when appropriate, and complete within tight latency boundaries (<100ms for fast gates).
4. **Pristine Root Structure**: Keep the repository root clean and minimal (`pyproject.toml`, `.gitignore`, `LICENSE`, `README.md`, `CLAUDE.md`, `AGENTS.md`). Do not pollute the root directory with temporary logs, scratch files, or unvetted specs.

---

## 3. Plugin Authoring & Packaging Standard

Every installable package under `plugins/` must follow this structure:

```
plugins/<pack-name>/
├── .claude-plugin/
│   └── plugin.json            # Plugin manifest (validated against tests/schemas/plugin.schema.json)
├── .lsp.json                  # LSP server declarations (optional)
├── .mcp.json                  # MCP server declarations (optional)
├── hooks.json                 # Claude Code hook interceptors (ONLY in plugins/hooks/)
├── scripts/                   # Interceptor and helper scripts
└── skills/                    # Fast gate skills & markdown guides
```

### Schema Rules:
- **`plugin.json`**: Must declare `name`, `displayName`, `description`, `author`, `license`, and component paths.
- **`hooks.json`**: Only `plugins/hooks/` may declare `hooks.json`.
- **`catalog/catalog.yaml`**: Every first-party plugin package must be registered in `catalog/catalog.yaml`.

---

## 4. Verification Protocol for AI Agents

Before declaring any task or feature complete, you MUST execute and confirm zero errors on:

```bash
# 1. Full test suite
pytest

# 2. Marketplace & plugin schema validation
python scripts/heretek_cli.py validate

# 3. Strict Pyright type checking
.venv/bin/basedpyright scripts

# 4. Ruff linter check
ruff check .
```

---

## 5. Artifact Protocol

When working on non-trivial plans or rebuild tasks:
1. Maintain **`task_list.md`** as a step-by-step checklist.
2. Maintain **`implementation_plan.md`** detailing component changes.
3. Produce **`verification.md`** documenting concrete execution logs.
4. Update **`walkthrough.md`** summarizing architectural changes and verification outputs.
