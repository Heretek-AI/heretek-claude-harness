# RE-AI

The agent-space monorepo that orchestrates the Heretek-RE per-MCP reverse-engineering toolchain. Contains 31 per-MCP server repos, 29 skill definitions, and shared catalog data.

## Structure

```
versions.lock           # Per-server git tag pins (e.g., "re-capa v0.1.0")
install.sh              # Clones all servers at pinned versions into servers/
.mcp.json               # Registers all 31 MCP servers (reads from servers/)
skills/                 # 29 SKILL.md files (agent workflows)
  re-static-triage/     # Workflow: fresh binary → catalog match → plan
  re-dynamic-analysis/  # Workflow: Frida attach → hook → decrypt
  re-decompile/         # Workflow: Ghidra/IDA decompile → IL lift
  re-malware-triage/    # Workflow: sample → YARA + capa + anti-analysis
  ...                   # (29 total)
data/                   # Shared catalogs
  anti-analysis-catalog.json
  apkid-signatures.json
  compiler-fingerprints.json
  drm-indicators.yaml
  ollvm-pass-catalog.json
servers/                # [git-ignored] Cloned per-MCP repos (populated by install.sh)
pyproject.toml          # Integration test runner
tests/integration/      # Cross-server integration tests
```

## Quick start

```bash
git clone https://github.com/Heretek-RE/RE-AI.git
cd RE-AI
./install.sh           # clones 31 per-MCP servers into servers/
```

## Build commands

### Install
```bash
./install.sh           # clone all servers at pinned versions
./install.sh --update  # re-clone at updated tags (edit versions.lock first)
./install.sh --clean   # remove all cloned servers
```

### Test
```bash
pip install -e ".[dev]"
pytest tests/integration/
```

### Individual server (standalone)
```bash
cd servers/re-capa
pip install -e .
re-capa                # starts MCP server on stdio
```

## How it works

1. `versions.lock` pins each per-MCP repo to a git tag
2. `install.sh` does `git clone --depth 1 --branch <tag>` for each
3. `.mcp.json` registers all 31 servers with Claude Code (reads from `servers/`)
4. `skills/` contains agent workflow definitions that compose the MCP tools
5. `data/` contains shared catalogs referenced by multiple servers

## Version management

Edit `versions.lock` to bump a server, then re-run `./install.sh --update`:

```
re-capa v0.2.0     # bumped
re-angr v0.1.0     # unchanged
```

## Conventions

- **Per-MCP repos** are independent: each has its own `pyproject.toml`, `src/`, tests, LICENSE
- **Skills** are agent-context files (SKILL.md), not executable code
- **Catalog data** is shared across servers; edits in `data/` affect the catalog matchers
- **No engagement references** in any committed file: no game titles, SOW codes, host paths, or per-target output paths

## Key files

- `versions.lock` — the version manifest for all 31 servers
- `install.sh` — the installer
- `.mcp.json` — the MCP server registry
- `README.md` — the public-facing overview
