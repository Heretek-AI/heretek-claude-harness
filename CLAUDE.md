# `heretek-claude-harness` — Plugin Marketplace & Distribution Engine

`heretek-claude-harness` is an open-source **plugin marketplace framework and distribution CLI** that installs mechanical quality guardrails (`ruff`, `pyright`, `cargo clippy`, `biome`, `ast-grep`), Claude Code hooks, MCP servers, and language packs into **target developer repositories**.

---

## Architectural Pillars

- **Catalog Registry** (`catalog/catalog.yaml`): Source of truth for available marketplace packages and dependency pins.
- **Marketplace Manifest** (`.claude-plugin/marketplace.json`): Generated marketplace index built from `catalog/catalog.yaml`.
- **Packaging Schemas** (`tests/schemas/`): JSON Schemas validating `plugin.json`, `hooks.json`, `.mcp.json`, `.lsp.json`, and `marketplace.json`.
- **Distribution CLI** (`scripts/heretek_cli.py`): Package manager installing assets into target repo `.claude/` directories.
- **Installable Plugin Packages** (`plugins/`): `python`, `rust`, `js-ts`, `hooks`, `mcp-pack`.

---

## Developer Workflows & Essential Commands

### Testing & Quality Checks
```bash
# 1. Run full unit and integration test suite
pytest

# 2. Run Ruff code quality checks
ruff check .

# 3. Run Pyright strict type checking
.venv/bin/basedpyright scripts

# 4. Run local CI pipeline (pytest + validate + build-catalog)
bash scripts/ci.sh
```

### Marketplace & Installer CLI (`heretek_cli.py`)
```bash
# Install a plugin pack into a target developer project
python scripts/heretek_cli.py install python --target /path/to/target/repo
python scripts/heretek_cli.py install hooks --target /path/to/target/repo

# Validate all marketplace and plugin manifests against JSON Schemas
python scripts/heretek_cli.py validate

# Re-index catalog.yaml and generate .claude-plugin/marketplace.json
python scripts/heretek_cli.py build-catalog
```

---

## Coding Standards & Development Rules

1. **Python Version & Typing**: Python 3.10+ with 100% explicit type annotations enforced by Pyright in strict mode (`typeCheckingMode = "strict"`).
2. **Never Hand-Edit Generated Manifests**: `marketplace.json` is generated from `catalog/catalog.yaml`. Use `python scripts/heretek_cli.py build-catalog` to regenerate it.
3. **Plugin Isolation**: Do not ship `hooks.json` outside the `plugins/hooks/` package.
4. **Schema Compliance**: Every plugin under `plugins/` must pass `python scripts/heretek_cli.py validate` against JSON Schemas in `tests/schemas/`.
