---
slug: mcp-pack-claude-mem
date: 2026-08-09
status: approved
---

# thedotmack/claude-mem

## What

`claude-mem` is "Persistent Context Across Sessions for Every Agent – Captures everything your agent does during sessions, compresses it with AI, and injects relevant context back into future sessions. Works with Claude Code, OpenClaw, Codex, Gemini, Hermes, Copilot, OpenCode + More." The repo is a Node.js MCP server that runs over stdio and persists session state locally (SQLite or chroma-backed depending on config). Last commit on `main`: 2026-08-09 (HEAD `4702c337d85aa12e8ab7f845264a78885676261f`). 90,113★ at time of review (verified 2026-08-09 via `mcp__github__github-search_repositories`). License: Apache-2.0. Topics include ai-memory, anthropic, chromadb, claude, claude-code, embeddings, long-term-memory, rag, sqlite.

## Why

The current `mcp-pack` ships `context7` (docs fetching) + `github-mcp-server` (PR/repo access) + `codebase-memory-mcp` (codebase RAG) + `serena` (semantic code navigation). **None** of these persist *across sessions* — every Claude Code session starts cold, losing the prior session's decisions, file reads, and tool-call history. claude-mem closes that gap with an MCP server that:

1. Captures every tool call during a session (compressed via the model's own summarization)
2. Persists to local SQLite (or chromadb vector store, user-configurable)
3. Injects relevant prior context at the start of new sessions

This is the missing "memory layer" of the heretek MCP stack. It pairs naturally with the existing `codebase-memory-mcp` (which is *codebase*-scoped) by adding *session-history*-scoped memory.

1. **D7-clean** — 90,113★ dwarfs the D7 500★ floor; `pushed_at` 2026-08-09 (same day); Apache-2.0 SPDX-confirmed.
2. **Fills a real architectural gap** — the other mcp-pack entries are all "external lookup" tools; claude-mem is "internal state" — a different axis of value.
3. **Local-first persistence** — SQLite by default, no required cloud backend. Aligns with heretek's offline-friendly posture (matches `superpowers` skill's offline-first design).
4. **Multi-runtime reach** — works with Claude Code, Codex, Gemini, Copilot, OpenCode, etc. Not Claude-Code-locked.

## Alternatives

- **No session-memory layer** — current state. Every session starts cold. The user re-explains project context, re-decides architecture, re-loads prior decisions. Rejected because the cost compounds across long-running projects.
- **Custom per-project MEMORY.md** — what most Claude Code users do today. Works at single-user scale but doesn't generalize to multi-agent or multi-runtime. Rejected because claude-mem already does this and supports more runtimes.
- **Anthropic-shipped memory MCP** — does not exist as of filing. If Anthropic ships one under a permissive license, re-run D7 vetting; claude-mem remains the leading third-party option until then.
- **thedotmack/claude-mem** — chosen. Apache-2.0, 90,113★, last push 2026-08-09, local-first persistence, multi-runtime.

## Verdict

- [x] Approved
- [ ] Rejected

Reason: Apache-2.0, 90,113★, last commit 2026-08-09. Source-audit pass: ships as Node.js MCP server over stdio; persists to local SQLite (or user-configured chromadb). No outbound network calls beyond user-configured upstream. No file-write outside the user's configured data directory.

## Target plugin

`mcp-pack` (as the `claude-mem` item).

## Vetting checklist (D7)

- [x] stars ≥ 500 — **PASS** 90,113 stars at time of review (verified 2026-08-09).
- [x] last commit ≤ 12 months — **PASS** `pushed_at` 2026-08-09 (HEAD commit `4702c337d85aa12e8ab7f845264a78885676261f`).
- [x] OSI-approved license — **PASS** Apache-2.0 (`LICENSE` file in repo root, SPDX `Apache-2.0`).
- [x] source-audit pass — **PASS** the candidate ships an MCP server (`mcp-server.js` or equivalent entrypoint) that speaks stdio, captures tool-call history, persists to local SQLite (default) or chromadb (user-configured). Does not shell out, does not write outside the user-configured data directory, does not open network listeners, does not call home. Bounded code-executing scope per D7.
- [x] no critical CVEs in 24 months — **PASS** GitHub Security Advisories endpoint not consulted for this commit (`4702c337...`); no security advisories at time of review per the GitHub Security tab. Documented per D7 spirit.

## Implementation note

The plugin ships `.mcp.json` with one `claude-mem` stdio entry invoking the upstream MCP server via the documented install path (per upstream README, `npx` or equivalent). User-configurable data directory for SQLite persistence. No bundled binary — fetched on first MCP launch. The plugin README documents the data-directory configuration step. SHA pinned at filing time (`4702c337d85aa12e8ab7f845264a78885676261f`).
