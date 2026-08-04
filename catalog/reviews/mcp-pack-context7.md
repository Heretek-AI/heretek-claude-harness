---
slug: mcp-pack-context7
date: 2026-08-04
status: approved
---

# upstash/context7

## What

`context7` is Upstash's official Model Context Protocol (MCP) server
that fetches up-to-date, version-pinned documentation for libraries
and frameworks directly into an LLM's prompt. The server exposes tools
that resolve a `libraryId` (e.g. `/vercel/next.js`, `/websites/uploadcare`,
`/llmstxt/<source>`, `/packages/<name>`) into the matching docs chunk
via the Context7 HTTP API at `https://context7.com/api/v2/context` and
returns them as tool results. The repo is TypeScript, published on npm
as `@upstash/context7-mcp`, and the canonical install path is
`npx -y @upstash/context7-mcp@latest` over stdio. HEAD commit
`594a73133e14631af8c915a1b4f2c8039c964fe1` on `master`, pushed
2026-08-04. 60,259★ at time of review.

## Why

The single highest-leverage failure mode for Claude Code (and any
coding LLM) is hallucinating API surface area that does not exist in
the user's pinned library version. Models trained on a snapshot of the
web confidently invent method signatures, option names, and import
paths from memory, and the user pays for the round-trip of writing
broken code, running it, and getting a runtime error.

`context7` is the canonical fix: every tool call pulls the current
docs page for the library the user names, scoped to the user's pinned
version when given. The model then reasons over real text instead of
over its own priors. Per spec §8 the `mcp-pack` plugin's first MCP
slot is `context7` — this is the most-bang-per-buck capability the
plugin can ship.

The brief predicted "~7k★, MIT, source-audit: Upstash project, used
widely." Actual figures (verified 2026-08-04 via `gh api
repos/upstash/context7`): 60,259★ (vastly exceeds the brief estimate
and dwarfs the D7 500★ gate by two orders of magnitude), MIT license
confirmed both via the GitHub API `license.spdx_id = "MIT"` and via
the `LICENSE` file content (`base64` decode matches the standard MIT
header "The MIT License (MIT)" with "Copyright (c) 2021 Upstash,
Inc."). Source-audit pass: Upstash is a well-funded, well-known
serverless-data company; the MCP server is a thin TypeScript wrapper
around Upstash's hosted Context7 REST API.

## Alternatives

- **Anthropic-built docs fetcher** — not available; Anthropic ships
  no equivalent MCP server. The Claude Code `WebFetch` tool fetches
  arbitrary URLs but does not know about version-pinning or library-ID
  resolution. Rejected: no upgrade path over raw `WebFetch` for the
  use case.
- **`@modelcontextprotocol/server-github`** (covered separately as
  `mcp-pack-github-mcp-server`) — orthogonal. GitHub MCP retrieves
  repo contents and PR data; it does not resolve library docs.
  Shipped alongside, not in place of, context7.
- **Local docs RAG (e.g. a custom Chroma/Milvus stack over scraped
  docs)** — possible but each user would re-implement and re-host the
  same scraper. Rejected: every user re-paying for the same indexing
  job is exactly the duplication `mcp-pack` exists to avoid.
- **upstash/context7** — chosen. MIT, 60,259★, last commit 2026-08-04,
  npm package is one `npx -y @upstash/context7-mcp@latest` away,
  backed by Upstash (the team behind Upstash Redis/Kafka/QStash).

## Verdict

- [x] Approved
- [ ] Rejected

Reason: MIT, 60,259★, last push 2026-08-04 (well inside D7's
12-month window), Upstash-owned. Zero GitHub Security Advisories
filed against the repo at time of review. Passes every D7 criterion.

## Target plugin

`mcp-pack` (as the `context7` item).

## Vetting checklist (D7)

- [x] stars ≥ 500 — **PASS** 60,259 stars at time of review (vastly
      exceeds the 500★ gate; well above even the ~7k estimate in the
      plan).
- [x] last commit ≤ 12 months — **PASS** `pushed_at` 2026-08-04 (HEAD
      commit `594a73133e14631af8c915a1b4f2c8039c964fe1`).
- [x] OSI-approved license — **PASS** MIT (`LICENSE` file in repo
      root, `license.spdx_id = "MIT"` in the GitHub API response,
      `license.key = "mit"`).
- [x] source-audit pass — **PASS** the published npm package
      `@upstash/context7-mcp` is a thin TypeScript wrapper that takes
      a `libraryId` + `query`, calls `https://context7.com/api/v2/context`
      over HTTPS, and returns the docs chunk. It does not shell out,
      does not write outside the workspace, and does not open a
      network listener. The only network egress is the authenticated
      call to `context7.com`. Backed by Upstash (the well-funded
      serverless-data company that ships Upstash Redis/Kafka/QStash
      and is the upstream owner of the repo). The plugin's `.mcp.json`
      invokes the server via `npx -y @upstash/context7-mcp@latest`
      over stdio; a Context7 API key can be passed via the
      `CONTEXT7_API_KEY` env var, but the server also works in
      unauthenticated mode with rate limits per upstream README.
- [x] no critical CVEs in 24 months — **PASS** GitHub Security
      Advisories endpoint returned zero advisories for
      `upstash/context7` at time of review.

## Implementation note

The plugin ships `.mcp.json` with one `context7` stdio entry:
`npx -y @upstash/context7-mcp@latest`. The npm package is **not**
bundled with the plugin — it is fetched on first MCP launch via `npx`.
The user needs Node.js LTS (the same requirement as `chrome-devtools-mcp`
in the `web-frontend` plugin). Users with a Context7 API key can set
`CONTEXT7_API_KEY` in their environment to lift the unauthenticated
rate limit; the plugin README documents this as an optional step.
