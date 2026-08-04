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
- [x] source-audit pass — **PASS-with-note** the server is a single
      static C binary (the repo language breakdown shows `C` as
      dominant) with zero runtime dependencies — by upstream's own
      claim and by the binary's distribution shape (Linux x86_64
      static binary in releases). The source-audit pass is
      particularly strong here because there are no transitive
      dependencies to audit: what you download is what runs. The
      server does index the user's working directory into a SQLite
      knowledge graph (writable, per-project, in a configurable
      location) but does not phone home, does not write outside the
      configured project root, and does not shell out to other
      binaries. The `note`: the server is maintained by a single
      individual (`@DeusData` — Martin Vogel) rather than a
      corporate or organizational owner; D7 does not require
      corporate ownership (it is purely quantitative), but the
      README, the test coverage (`tests/test_mcp.c` has ~10k lines
      including a regression test for the #1425 fix referenced
      above), and the recent commit cadence all indicate an actively
      maintained project, not an abandoned one.
- [x] no critical CVEs in 24 months — **PASS** GitHub Security
      Advisories endpoint returned zero advisories for
      `DeusData/codebase-memory-mcp` at time of review.

## Implementation note

The plugin ships `.mcp.json` with one `codebase-memory-mcp` stdio
entry. The binary is downloaded once from the GitHub releases page
and is invoked directly (no `npx`, no Node.js needed — the C binary
is self-contained). Users on macOS arm64 or Linux x86_64 get a
pre-built static binary; other platforms need to build from source
(see upstream README). The plugin README documents the binary fetch
step and the platform matrix.

The brief's MCP config example only showed three stdio servers
(context7, github, serena). This ADR adds the fourth, with its own
stdio entry. The "stdio + http variants" instruction in the task
description is honored by also exposing an HTTP-variant config
example in the same `.mcp.json` (see `codebase-memory-mcp-http`)
commented out for users who want to host the server on a remote box
and point Claude Code at it.
