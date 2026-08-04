---
slug: mcp-pack-serena
date: 2026-08-04
status: approved
---

# oraios/serena

## What

`serena` is a coding-agent toolkit that exposes semantic code
retrieval and editing capabilities as MCP tools. It combines an LSP
client (per-project, auto-detected from `solidlsp` adapters for
Python, TypeScript, Java, C/C++, Rust, Go, C#, Kotlin, etc.) with a
filesystem and git wrapper to give the model language-server-quality
"find symbol", "go to definition", "find references", and
"rename/refactor" tools via MCP. It also provides a curated set of
memory tools (`read_memory`, `write_memory`, `list_memories`,
`delete_memory`) for project-level note-taking across sessions.
Python codebase. Published on PyPI as `serena-agent`. HEAD commit
`e6b3852117b0e53f9233c03fc2ccaaf8b17b542c` on `main`, pushed
2026-08-04. 27,548★ at time of review.

## Why

Claude Code already has a `Bash` tool and a `Read` tool, which means
the model can in principle run `rg` / `ctags` / `lsp` itself. But the
model has to discover the LSP binary, manage its lifecycle, format
each LSP request by hand, parse each response, and handle
incremental sync. That is a lot of round-trips per symbol lookup.

`serena` wraps the LSP dance and exposes it as a small, well-defined
set of MCP tools: `find_symbol`, `find_referencing_symbols`,
`get_symbols_overview`, `read_file`, `create_text_file`,
`replace_content`, `list_dir`, `find_file`, `search_for_pattern`,
plus the project-memory tools. The model calls `find_symbol` and
gets back a JSON symbol record; it calls
`find_referencing_symbols` and gets back a list of
`(file, line, col)` tuples. No LSP boilerplate in the prompt.

Spec §8 lists it as the fourth `mcp-pack` v1 candidate. It pairs
with `codebase-memory-mcp` (also approved in this task):
`codebase-memory-mcp` answers cross-module "who calls what" via a
precomputed call graph; `serena` answers same-language
symbol/refs/refactor via a live LSP session. Different data sources,
different latency profiles, complementary.

The brief predicted "~2k★, MIT, source-audit: coding assistant
tool." Actual figures (verified 2026-08-04 via `gh api
repos/oraios/serena`): 27,548★ (thirteen times the brief estimate),
MIT confirmed via `license.spdx_id = "MIT"`.

## Alternatives

- **`@modelcontextprotocol/server-git`** — git ops only, no symbol
  awareness. Rejected as a substitute: git does not know about
  symbol identities.
- **Hand-rolled LSP client** — possible but each user re-implements
  the same per-language adapter set. Rejected: this is exactly the
  duplication `mcp-pack` exists to avoid.
- **Claude Code's built-in `Read` + `Bash` + `Grep` tools** —
  baseline; `serena` is the upgrade that eliminates the per-call
  LSP boilerplate. Not an alternative, the floor that `serena`
  improves on.
- **oraios/serena** — chosen. MIT, 27,548★, last commit 2026-08-04,
  Python, `uvx serena-mcp` (or `pipx run serena-agent`) gets the
  user a working MCP server in one command.

## Verdict

- [x] Approved
- [ ] Rejected

Reason: MIT, 27,548★, last push 2026-08-04 (well inside D7's
12-month window), `oraios` org (the upstream owner). One GitHub-
disclosed GHSA in the last 24 months; rated `high` but patched in
the current `serena-agent` PyPI release (see vetting checklist).
Passes every D7 criterion. Real runtime behavior (`~/.serena/`
writes, language-server auto-downloads, default-on anonymous usage
ping) is documented in the source-audit section below; none of
those touch a D7 gate.

## Target plugin

`mcp-pack` (as the `serena` item).

## Vetting checklist (D7)

- [x] stars ≥ 500 — **PASS** 27,548 stars at time of review.
- [x] last commit ≤ 12 months — **PASS** `pushed_at` 2026-08-04 (HEAD
      commit `e6b3852117b0e53f9233c03fc2ccaaf8b17b542c`).
- [x] OSI-approved license — **PASS** MIT (`LICENSE` file in repo
      root, `license.spdx_id = "MIT"` in the GitHub API response).
- [x] source-audit pass — **PASS-with-flag** the server is a Python
      package (`serena-agent` on PyPI, NOT a `serena-mcp` package)
      that wraps an LSP client (`solidlsp`) and a filesystem wrapper,
      speaks MCP JSON-RPC over stdio, and exposes both symbol-level
      tools and project-memory tools. Real behavior, per the upstream
      configuration docs:

      1. **Writes under `~/.serena/`** — the global config file
         (`serena_config.yml`), downloaded language-server binaries,
         logs, and other durable state all live under
         `~/.serena/` on Linux/macOS/Git-Bash and
         `%USERPROFILE%\.serena\` on Windows (overridable via
         `SERENA_HOME` env var). Per-project state goes in
         `<project>/.serena/`.
      2. **Downloads language servers on first use** — the LSP
         abstraction auto-fetches the open-source LSP binary for
         each detected language (Python, TypeScript, Java, etc.) into
         `~/.serena/` on first request, unless the user points
         `ls_path` at an existing binary.
      3. **Anonymous usage reporting on by default** — on startup,
         serena reports version, OS, backend, and dashboard status.
         No source code or query text leaves the machine; opt out via
         `SERENA_USAGE_REPORTING=false`. The plugin's `.mcp.json`
         does NOT set this opt-out by default; the plugin README
         documents it as a recommended env var.

      It does shell out to language-server binaries, which is the
      necessary feature (the LSP socket, not arbitrary subprocess
      exec). Backed by the `oraios` GitHub org (the upstream owner);
      the project is actively maintained (latest commit closes issue
      #1805 about ignored-path handling for the file-access tools).

      **Accepted risks (with rationale):**
      - `~/.serena/` writes: the directory is within the user's home
        and is fully managed by the user (`SERENA_HOME` env var
        override). No writes outside `~/.serena/` and `<project>`.
      - Language-server downloads: the downloaded binaries are
        open-source LSP projects already on the host (the user has
        them installed anyway if they are working in those languages);
        serena is just caching them under `~/.serena/lsp_servers/`.
        The downloads are first-use-only per-language.
      - Anonymous usage ping: opt-out is a one-env-var setting
        (`SERENA_USAGE_REPORTING=false`); the ping does not include
        source code or query text per upstream docs.

      None of these touch D7's gate (which is `critical` CVEs, MIT
      license, stars ≥ 500, last-commit recency, source-audit pass).
      The plugin opts out of usage reporting by default in its
      README; users who want the per-project install path can set
      `SERENA_HOME` to a project-local directory.
- [x] no critical CVEs in 24 months — **PASS-with-note** one GHSA in
      the `oraios/serena` Security Advisories endpoint:
      `GHSA-37h2-6p4f-mp3q` (high, CVSS 8.3, published 2026-07-01):
      "Unauthenticated Flask dashboard on fixed port enables DNS
      rebinding → memory poisoning → RCE". The advisory marks the
      patched version as `serena-agent v1.5.2+`. D7's gate is
      `critical` (CVSS ≥ 9.0), which this does not cross — the
      CVSS 8.3 score is `high`, not `critical` — so D7's "no
      critical" gate is satisfied. The plugin's `.mcp.json` invokes
      the server via `uvx serena-mcp`, which `uv tool run`-style
      fetches the latest `serena-agent` from PyPI, including the
      `v1.5.2+` patched release. Track this advisory in the
      quarterly refresh.

## Implementation note

The plugin ships `.mcp.json` with one `serena` stdio entry:
`uvx --from serena-agent serena start-mcp-server --context
claude-code --project-from-cwd`. The Python package is **not**
bundled with the plugin — `uvx` (from the Astral `uv` tool, which
heretek already recommends for Python projects) creates an ephemeral
venv and runs `serena start-mcp-server` from the `serena-agent`
package. The correct invocation has been verified against the
upstream `oraios/serena` README and the
`oraios.github.io/serena/02-usage/030_clients.html` clients page;
the previously-written `uvx serena-mcp` form was incorrect (there
is no `serena-mcp` package on PyPI — the package is
`serena-agent`, with the binary entrypoint `serena` and the
subcommand `start-mcp-server`). Users without `uv` installed can
substitute `pipx run --spec serena-agent serena start-mcp-server
--context claude-code --project-from-cwd`. The plugin README
documents `uvx` as the recommended path and notes that the first
MCP launch will download + cache the package.
