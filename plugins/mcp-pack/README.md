# mcp-pack

> heretek marketplace — first-party plugin

## What

Generic (not language-specific) MCP servers for Claude Code: a live
library-documentation fetcher, the official GitHub API server, a
cross-module code-graph server, and an LSP-backed symbol/reference
server. Together they give the agent the same diagnostic surface a
human developer has — current docs, full repo context, every callsite,
every definition — without leaving the prompt.

## Install

```bash
/plugin install mcp-pack@heretek
```

## Components

- **MCP: `context7`** — Upstash's `@upstash/context7-mcp` server,
  launched via `npx -y @upstash/context7-mcp@latest`. Fetches
  version-pinned documentation for a named library
  (`/vercel/next.js`, `/packages/<name>`, `/llmstxt/<source>`,
  `/websites/<id>`) and returns it as an MCP tool result. Eliminates
  the "hallucinated API" failure mode for the libraries the model
  actually works in. See
  `catalog/reviews/mcp-pack-context7.md` for the vetting record.
- **MCP: `github`** — GitHub's official `github-mcp-server`, launched
  via `npx -y @modelcontextprotocol/server-github`. Exposes the
  GitHub REST and GraphQL APIs as a curated set of MCP tools
  (repositories, issues, pull_requests, actions, code_search,
  notifications, secret_scanning, dependabot, security_advisories,
  etc.) with OAuth scope hints on every tool. See
  `catalog/reviews/mcp-pack-github-mcp-server.md`.
- **MCP: `codebase-memory-mcp`** — `DeusData/codebase-memory-mcp`,
  distributed as a single static C binary. Indexes the working
  directory into a SQLite-backed knowledge graph and answers
  "who calls this", "what does this import", "trace this call chain"
  as structured MCP tool calls. Pairs with `serena` for a complete
  code-navigation surface. See
  `catalog/reviews/mcp-pack-codebase-memory-mcp.md`.
- **MCP: `serena`** — `oraios/serena`, launched via `uvx serena-mcp`.
  LSP-backed symbol lookup (`find_symbol`, `find_referencing_symbols`,
  `get_symbols_overview`) plus filesystem wrappers
  (`read_file`, `create_text_file`, `replace_content`,
  `list_dir`, `find_file`, `search_for_pattern`) and project-memory
  tools (`read_memory`, `write_memory`). Adapters for Python,
  TypeScript, Java, C/C++, Rust, Go, C#, Kotlin, and more via
  `solidlsp`. See `catalog/reviews/mcp-pack-serena.md`.

## Requirements

- **Node.js 22 LTS or later** — `context7` and `github-mcp-server`
  fetch via `npx` on first MCP launch.
- **`uv`** (Astral) — `serena` fetches via `uvx` on first MCP launch.
  Install with `curl -LsSf https://astral.sh/uv/install.sh | sh`.
- **`codebase-memory-mcp` binary** — download the static binary for
  your platform (Linux x86_64 / macOS arm64) from the
  `DeusData/codebase-memory-mcp` GitHub releases page and place it
  on `$PATH` as `codebase-memory-mcp`. Other platforms need a from-
  source build per the upstream README.
- **`GITHUB_PERSONAL_ACCESS_TOKEN`** env var (recommended) — the
  `github` MCP server needs an authenticated GitHub identity. A
  classic PAT with `repo`, `read:org`, `read:user`, and `workflow`
  scopes covers the typical tool surface; the `github-mcp-server`
  upstream README documents the OAuth device-code flow as the
  alternative.
- **`CONTEXT7_API_KEY`** env var (optional) — lifts the
  unauthenticated rate limit on `context7`. Not required; the server
  works in unauthenticated mode with rate limits per upstream
  README.

## Out of scope (v1)

- **`mksglu/context-mode`** — under consideration per spec §8 but not
  in v1 unless it passes D7 on a future task. Tracks
  `DeusData/codebase-memory-mcp` for the cross-module code-graph
  slot; users who need the context-mode behavior can run both.

## License

MIT — see [LICENSE](../../LICENSE).
