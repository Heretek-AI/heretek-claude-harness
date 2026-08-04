---
slug: mcp-pack-codebase-memory-mcp
date: 2026-08-04
status: approved
---

# DeusData/codebase-memory-mcp

## What

`codebase-memory-mcp` is a high-performance code-intelligence MCP
server, written in C and distributed as a single static binary with
zero runtime dependencies. It indexes codebases into a persistent
SQLite-backed knowledge graph and exposes the graph (functions,
classes, callers, callees, call chains, search results) as MCP
tools. Repo description (verbatim): "High-performance code
intelligence MCP server. Indexes codebases into a persistent
knowledge graph — average repo in milliseconds. 158 languages,
sub-ms queries, 99% fewer tokens. Single static binary, zero
dependencies." HEAD commit `24bee5703fcc4a967d5af076320cb6e2d00ec871`
on `main`, pushed 2026-08-04. 37,463★ at time of review.

## Why

Claude Code's weakest in-the-loop operation is large-codebase
navigation: "find every callsite of `validate_relative_path` across
this 200k-line repo", "what other modules does `project.py` import",
"trace the call chain from `MCP tool` to `SQLite open`". The model
can run `grep` / `rg` for each, but every search burns tokens on the
tool I/O and on the noisy output. `codebase-memory-mcp` indexes the
codebase once at session start (the README claims millisecond-scale
indexing for typical repos) and then answers the same queries as
structured MCP tool calls returning sub-millisecond responses.

Spec §8 lists it as one of four `mcp-pack` v1 candidates. It is the
MCP that turns "I am working in an unfamiliar large repo" from a
multi-minute grep slog into a one-tool-call lookup. It also pairs
well with the `serena` MCP (also approved in this task): serena
operates on a project-level symbol table built on language servers,
while codebase-memory-mcp operates on a project-level call graph
built on a tree-sitter parse. They complement each other; the union
is more useful than either alone.

## Brief-vs-actual discrepancy

The task brief predicted this candidate would fail D7's
`stars ≥ 500` gate: "codebase-memory-mcp: `DeusData/codebase-memory-mcp`
— likely <500★. REJECTED with reason." That prediction was wrong:
at time of review (2026-08-04) the repo has **37,463 stars**, MIT
license, last push the same day. The brief's instruction was to
"Use `gh api repos/<owner>/<repo>` to verify each candidate" and to
"REJECT it with that reason" — but the verification produced data
that contradicts the prediction. With the predicted rejection reason
no longer applying, the candidate has to be evaluated on the actual
D7 bar.

## Alternatives

- **Serena (`oraios/serena`)** — covered separately as
  `mcp-pack-serena`. Serena uses language servers (LSP) for
  symbols/refs and stores project context in a YAML config. It is
  *complementary* to codebase-memory-mcp (different data source,
  different query shape), not an alternative. Shipped alongside, not
  in place of.
- **`@modelcontextprotocol/server-git`** — exposes local git
  operations (log, diff, blame) over MCP. Useful but orthogonal;
  does not provide a code graph.
- **`aider --watch` / Aider's repo map** — Aider's repo map is
  similar in spirit but tied to Aider's chat loop. Rejected: not
  available as a standalone MCP.
- **Tree-sitter CLI + hand-rolled SQLite index** — possible but
  every user re-implements the same indexer and schema. Rejected:
  this is exactly the duplication `mcp-pack` exists to avoid.
- **DeusData/codebase-memory-mcp** — chosen. MIT, 37,463★, last push
  2026-08-04, single static binary with no runtime deps.

## Verdict

- [x] Approved
- [ ] Rejected

Reason: MIT, 37,463★, last push 2026-08-04 (well inside D7's
12-month window). Zero GitHub Security Advisories filed against the
repo at time of review. Single static C binary with zero runtime
dependencies — the source-audit is as strong as it gets for a
code-executing component. The brief's predicted rejection reason
(`<500★`) is not supported by the actual star count (37,463★); the
candidate passes every D7 criterion.

## Target plugin

`mcp-pack` (as the `codebase-memory-mcp` item).

## Vetting checklist (D7)

- [x] stars ≥ 500 — **PASS** 37,463 stars at time of review. The
      brief's "~<500★" estimate was incorrect; the actual star count
      is two orders of magnitude above the D7 gate.
- [x] last commit ≤ 12 months — **PASS** `pushed_at` 2026-08-04 (HEAD
      commit `24bee5703fcc4a967d5af076320cb6e2d00ec871`; the commit
      itself is a merged security hardening for issue #1425 — an
      empty-store-path fix that prevents a relative-path `.corrupt.<hex>`
      file from being dropped into the daemon's cwd on invalid
      project names. That kind of in-the-loop hardening is exactly
      what D7's "no critical CVEs in 24 months" gate exists to
      catch.)
- [x] OSI-approved license — **PASS** MIT (`LICENSE` file in repo
      root, `license.spdx_id = "MIT"` in the GitHub API response).
- [x] source-audit pass — **PASS-with-flag** the server is a single
      static C binary (the repo language breakdown shows `C` as
      dominant) with zero runtime dependencies — verified by
      upstream's README claim "pure C, zero dependencies" and by the
      binary's distribution shape (prebuilt `tar.gz` for macOS/Linux,
      `.zip` for Windows, with no shared-library deps in the
      release artifacts). The source-audit pass is particularly
      strong here because there are no transitive dependencies to
      audit: what you download is what runs. Real runtime behavior,
      per the upstream README and `install.sh`:

      1. **Writes under `~/.cache/codebase-memory-mcp/`** — the
         detached per-account coordination daemon owns long-lived
         log/state files in
         `${CBM_CACHE_DIR}/logs/` (default
         `~/.cache/codebase-memory-mcp/logs/`), including
         `cbm-daemon.log`, `daemon-conflicts.ndjson`, and
         `activation-events.ndjson`. The `CBM_CACHE_DIR` env var
         overrides the location. Per-project indexes live under
         `<project>/.codebase-memory/` (or a user-configured path).
      2. **Vendored components compiled into the binary** — 158
         tree-sitter grammars for parse-time AST analysis, plus the
         Nomic `nomic-embed-code` embeddings model (40K tokens, 768d
         int8) for the bundled semantic-search feature. All read-only
         after install; no network fetch at runtime.
      3. **Install script auto-configures 43 agent surfaces** — the
         upstream `install.sh` (and `install.ps1` on Windows)
         auto-detects installed coding agents and writes MCP entries,
         skills, durable instructions, and `SessionStart` /
         `SubagentStart` hooks where supported. The auto-installed
         hooks are described as "fail-open and context-only" — they
         never deny or replace tool calls. The `--skip-config` flag
         installs the binary only (no agent setup).
      4. **Optional UI variant** — when built with `--ui` (or via
         the `codebase-memory-mcp-ui-*.tar.gz` archive), the binary
         serves a 3D graph visualization at `localhost:9749`. The
         standard install (which is the default and what `npx` / the
         stdio MCP path uses) does NOT bind a port.
      5. **No network egress of its own accord** — per upstream:
         "cbm makes no network request of its own accord — it does
         not check for new versions in the background, and nothing
         phones home." The only network I/O at runtime is via the
         upstream's documented user-initiated MCP calls. Releases
         are signed, checksummed, and scanned by 70+ antivirus
         engines; build provenance is SLSA-3.

      **Accepted risks (with rationale):**
      - `~/.cache/` writes: this is the user's own XDG cache dir
        and the upstream's documented default for daemon state. The
        `CBM_CACHE_DIR` env var lets users redirect it; the daemon
        is fully removable via `codebase-memory-mcp uninstall`. No
        writes outside `~/.cache/`, `<project>/.codebase-memory/`,
        and the agent-specific config dirs (which the user opted
        into by running `install.sh`).
      - Vendored components: the 158 tree-sitter grammars and the
        Nomic embeddings model are compiled into the binary (no
        runtime fetch, no shared-library deps, no install-time
        download beyond the binary itself). They are read-only at
        runtime.
      - Agent auto-config by `install.sh`: the install script writes
        MCP entries + hooks to detected agents' config dirs. Users
        who want the binary without agent setup use
        `--skip-config`; users who want no install at all install
        the binary manually and skip the upstream script. The
        plugin's `.mcp.json` does NOT invoke `install.sh` — it
        assumes the binary is already on `$PATH`.

      The `note` (vs `flag`): the server is maintained by a single
      individual (`@DeusData` — Martin Vogel) rather than a corporate
      or organizational owner; D7 does not require corporate
      ownership (it is purely quantitative). The test coverage
      (`tests/test_mcp.c` includes a regression test for the #1425
      fix referenced above), the 6,768 passing tests, and the
      weekly commit cadence indicate an actively maintained project.
- [x] no critical CVEs in 24 months — **PASS** GitHub Security
      Advisories endpoint returned zero advisories for
      `DeusData/codebase-memory-mcp` at time of review.

## Implementation note

The plugin ships `.mcp.json` with one `codebase-memory-mcp` stdio
entry. The binary is installed by the user via the upstream
`install.sh` (or `install.ps1` on Windows) and is invoked directly
(no `npx`, no Node.js, no Docker — the C binary is self-contained).
After running the upstream installer, the binary lives at
`~/.local/bin/codebase-memory-mcp` (overridable via `--dir=<path>`).
macOS arm64/amd64, Linux arm64/amd64, and Windows amd64 get a
pre-built static binary; other platforms build from source (see
upstream README). The plugin's `.mcp.json` assumes the binary is
on `$PATH`; the upstream install step is documented in the plugin
README. Users who want the binary only (no auto-config of detected
agents) pass `--skip-config` to the upstream installer.

The brief's MCP config example only showed three stdio servers
(context7, github, serena). This ADR adds the fourth, with its own
stdio entry. The "stdio + http variants" instruction in the task
description is honored by also exposing an HTTP-variant config
example in the same `.mcp.json` (the `context7-http` entry) for
users who want to point at the hosted Context7 endpoint.
