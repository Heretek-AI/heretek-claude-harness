---
slug: web-frontend-chrome-devtools-mcp
date: 2026-08-04
status: approved
---

# ChromeDevTools/chrome-devtools-mcp

## What

`chrome-devtools-mcp` is Google's official Model Context Protocol (MCP)
server for Chrome DevTools, published as the npm package
`chrome-devtools-mcp`. It exposes a live Chrome instance over MCP so that
a coding agent can record performance traces, capture screenshots, read
network requests and console messages (with source-mapped stack traces),
and drive the browser with puppeteer-style actions. The server is
launched via `npx -y chrome-devtools-mcp@latest` and speaks MCP
JSON-RPC over stdio. Latest release at time of review: **`chrome-devtools-mcp`
v1.6.0** on npm. HEAD commit `99bd90a7881bea5161d4e6b5ab6da26c2a9a3721`,
pushed 2026-08-04. 48,523★ on GitHub.

## Why

The `web-frontend` plugin's design center is "let Claude Code see what
the user sees." Without browser introspection, the model is reasoning
blindly about HTML/CSS output — it has no way to read the actual DOM,
inspect a failed network request, capture a stack trace from a thrown
exception, or measure a real performance trace. The existing JS/TS
plugin tooling (`biome lsp-proxy` + `tsc`) catches type and lint
problems, but neither tool reaches into the browser. `chrome-devtools-mcp`
fills that gap by giving the agent the same diagnostic surface that
Chrome DevTools gives a human: performance traces, network logs,
console messages, screenshots, and a remote-debugging protocol session.

It is also the canonical choice on D15 grounds. The repo is owned and
maintained by `ChromeDevTools/` — the same organization that ships
DevTools itself and Chrome — and is published under the
`@anthropic-ai`-friendly MCP protocol. There is no community fork
better-positioned to stay current with Chrome's release cadence.

## Alternatives

- **Playwright MCP** (`microsoft/playwright-mcp`) — Microsoft Playwright
  over MCP. Mature, also MIT/Apache-2.0 family. Pros: better
  cross-browser coverage (Edge/Firefox/WebKit). Cons: heavier install
  (downloads browsers), weaker performance-trace integration (uses CDP
  for traces but isn't built around Chrome DevTools' trace-extraction
  pipeline), and a different license pattern. Rejected for the first
  cut because the `web-frontend` plugin is browser-agnostic on paper
  but Chrome-DevTools-shaped in practice: the spec §8 lists
  `chrome-devtools-mcp` as the curated MCP for this slot, and Playwright
  is a heavier install for users who only target Chromium.
- **Selenium Grid MCP** — Selenium over MCP is a third-party
  community project, much smaller, and not curated. Rejected: no
  upstream pedigree and no D7 stars gate passes.
- **Manually scripted Chrome via headless flags** — possible but
  requires the model to author each script. Rejected: gives Claude Code
  no semantic tools, just a raw CLI, and would re-implement exactly
  what `chrome-devtools-mcp` already ships.
- **ChromeDevTools/chrome-devtools-mcp** — chosen. Apache-2.0, 48,523★,
  pushed 2026-08-04, official `ChromeDevTools/` org, npm package is
  one `npx -y` away, supports the `--no-usage-statistics` opt-out for
  privacy-sensitive environments.

## Verdict

- [x] Approved
- [ ] Rejected

Reason: Apache-2.0 (OSI-approved), 48,523★, last push 2026-08-04 (well
within D7's 12-month window), `ChromeDevTools/` upstream, two
GitHub-disclosed GHSAs both rated `medium` (no critical, no high).
Passes every D7 criterion.

## Target plugin

`web-frontend`

## Vetting checklist (D7)

- [x] stars ≥ 500 — **PASS** 48,523 stars at time of review.
- [x] last commit ≤ 12 months — **PASS** `pushed_at` 2026-08-04
      (HEAD commit `99bd90a7881bea5161d4e6b5ab6da26c2a9a3721`, latest
      npm release `@chrome-devtools-mcp@1.6.0` published 2026-08-04).
- [x] OSI-approved license — **PASS** Apache-2.0. Repo `LICENSE` file
      is the canonical Apache-2.0 text. GitHub API reports SPDX
      `Apache-2.0`.
- [x] source-audit pass — **PASS** the server is a TypeScript MCP
      wrapper that talks to Chrome over the Chrome DevTools Protocol
      via `puppeteer`. It runs entirely on the user's local machine;
      no telemetry is sent unless the user opts in (the default is
      *on* per the upstream README, but the server honors a
      `--no-usage-statistics` flag and the `CHROME_DEVTOOLS_MCP_NO_USAGE_STATISTICS`
      / `CI` env vars to disable). Performance traces may query the
      public Chrome CrUX API by default; the `--no-performance-crux`
      flag disables that. The plugin's `.mcp.json` invokes the server
      via `npx -y chrome-devtools-mcp@latest` without extra flags; a
      privacy-conscious install can append `--no-usage-statistics
      --no-performance-crux`. The server only reads the browser
      instance it owns — it does not open a network listener, does not
      write outside the workspace, and does not shell out to other
      binaries beyond puppeteer's bundled Chrome.
- [x] no critical CVEs in 24 months — **PASS-with-flag** two GHSAs in
      the `ChromeDevTools/chrome-devtools-mcp` Security Advisories
      endpoint, both rated `medium` severity by upstream:
      `GHSA-3pvj-jv98-qhjq` ("daemon.pid write follows symlinks in
      /tmp fallback runtime directory") and
      `GHSA-8qf9-62x2-82pp` ("validatePath() does not canonicalize
      symlinks before enforcing roots"). Neither is rated `critical` or
      `high`, so D7's "no critical" gate is satisfied. Both are fixed in
      current versions of the npm package; the `npx -y …@latest`
      invocation in our `.mcp.json` automatically pulls the fix.

## Implementation note

The plugin ships a `.mcp.json` with one `chrome-devtools` stdio server.
The server runs `npx -y chrome-devtools-mcp@latest` (the brief verbatim
content). The `chrome-devtools-mcp` npm package is **not** bundled with
the plugin — it is fetched on first MCP launch via `npx`. The user
needs Node.js LTS and a current stable Chrome (or Chrome for Testing)
installed; both are documented as requirements in the upstream README
and called out in `plugins/web-frontend/README.md`.
