# RE-AI

The agent-space monorepo that orchestrates the Heretek-RE per-MCP reverse-engineering toolchain.

RE-AI does not contain server code itself. It contains:

- **`versions.lock`** — pins each per-MCP server to a specific git tag.
- **`install.sh`** — clones all 31 per-MCP servers at their pinned versions into `servers/`.
- **`.mcp.json`** — registers all 31 MCP servers with Claude Code (reads from `servers/`).
- **`skills/`** — 29 Claude Code skill definitions that compose the MCP tools into workflows.
- **`data/`** — shared catalog data (DRM indicators, compiler fingerprints, APKiD signatures, anti-analysis catalog, OLLVM pass catalog).

## Quick start

```bash
git clone https://github.com/Heretek-RE/RE-AI.git
cd RE-AI
./install.sh        # clones 31 per-MCP servers into servers/
```

Then register `.mcp.json` with your Claude Code session.

## Per-MCP servers

Each server is an independent repo at `https://github.com/Heretek-RE/re-<name>`. You can also use any server standalone without the agent-space orchestration:

```bash
# Standalone usage (any server)
git clone https://github.com/Heretek-RE/re-capa.git
cd re-capa
uv run re-capa     # starts the MCP server on stdio
```

See each server's README for its `.mcp.json` one-liner.

## Version management

Edit `versions.lock` to pin a server to a specific tag, then re-run `./install.sh --update`:

```
re-capa v0.2.0          # bumped to a newer release
re-angr v0.1.0          # unchanged
```

## Architecture

```
RE-AI/
├── .mcp.json            # MCP server registry (reads from servers/)
├── versions.lock        # per-server tag pins
├── install.sh           # installer (git clone --depth 1 --branch <tag>)
├── skills/              # 29 SKILL.md files (agent workflows)
├── data/                # shared catalogs (drm-indicators, compiler-fingerprints, ...)
├── servers/             # [git-ignored] cloned per-MCP repos
├── tests/integration/   # cross-server integration tests
├── pyproject.toml       # for integration test runner
├── LICENSE              # MIT
└── README.md
```

## License

MIT. The per-MCP servers carry their own licenses (see each server's LICENSE file).
