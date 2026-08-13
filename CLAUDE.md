# `heretek-claude-harness` — Plugin Marketplace & Distribution Engine

`heretek-claude-harness` is an open-source **plugin marketplace framework and distribution CLI** that installs mechanical quality guardrails (`ruff`, `pyright`, `cargo clippy`, `biome`, `ast-grep`), Claude Code hooks, MCP servers, and language packs into **target developer repositories**.

---

## Architectural Pillars

- **Catalog Registry** (`catalog/catalog.yaml`): Source of truth for available marketplace packages, dependency pins, and D7 vetting ADRs.
- **Marketplace Manifest** (`.claude-plugin/marketplace.json`): Generated marketplace index built from `catalog/catalog.yaml`.
- **Packaging Schemas** (`tests/schemas/`): JSON Schemas validating `plugin.json`, `hooks.json`, `.mcp.json`, `.lsp.json`, and `marketplace.json`.
- **Distribution CLI Launcher** (`bin/heretek.js` & `scripts/heretek_cli.py`): Package manager installing assets into target repo `.claude/` directories. Exposes `heretek init`, `status`, `metrics`, `install`, `validate`, `build-catalog`, `telemetry`.
- **Installable Plugin Packages** (`plugins/`): 16 first-party plugin packages covering Python, Rust, TypeScript, Go, C/C++, Java, Ruby, Elixir, C#, Web Frontend, Fallow, Best Practices, Quality Audit, Pre-commit, CI-CD, Hooks.

---

## Developer Workflows & Essential Commands

### Testing & Verification Suite
```bash
# 1. Run full unit and integration test suite
pytest

# 2. Run Ruff code quality checks
ruff check plugins scripts tests

# 3. Run Pyright strict type checking
.venv/bin/basedpyright scripts

# 4. Validate plugin manifests against JSON Schemas
python scripts/heretek_cli.py validate

# 5. Run local CI pipeline (pytest + validate + build-catalog)
bash scripts/ci.sh
```

### Marketplace & Installer CLI (`heretek`)
```bash
# Auto-detect target repository project type and install matching packs
npx heretek init --target /path/to/target/repo

# View terminal quality scorecard (0-100 pts) and deployed pack inventory
npx heretek status --target /path/to/target/repo

# Benchmark fast-gate hook execution latencies to enforce <100ms SLA
npx heretek metrics

# Install a specific plugin pack into a target project
npx heretek install python --target /path/to/target/repo

# Re-index catalog.yaml and generate .claude-plugin/marketplace.json
python scripts/heretek_cli.py build-catalog
```

---

## Coding Standards & Development Rules

1. **Python Version & Typing**: Python 3.10+ with 100% explicit type annotations enforced by Pyright in strict mode (`typeCheckingMode = "strict"`).
2. **Never Hand-Edit Generated Manifests**: `marketplace.json` is generated from `catalog/catalog.yaml`. Use `python scripts/heretek_cli.py build-catalog` to regenerate it.
3. **Plugin Isolation**: Do not ship `hooks.json` outside the `plugins/hooks/` package.
4. **Schema Compliance**: Every plugin under `plugins/` must pass `python scripts/heretek_cli.py validate` against JSON Schemas in `tests/schemas/`.
