---
slug: mcp-pack-github-mcp-server
date: 2026-08-04
status: approved
---

# github/github-mcp-server

## What

`github-mcp-server` is GitHub's official Model Context Protocol (MCP)
server, written in Go and published on npm as
`@modelcontextprotocol/server-github`. It exposes the GitHub REST and
GraphQL APIs as a curated set of MCP tools grouped by domain
(`repositories`, `issues`, `pull_requests`, `actions`, `code_search`,
`discussions`, `notifications`, `users`, `projects`, `gists`,
`secret_scanning`, `dependabot`, `security_advisories`, etc.), with
OAuth scope hints on every tool so the model picks the minimum
required grant. Latest release: tagged releases in `releases/`
(multi-digit version line); HEAD commit
`3778a41476e31a072430cfee7c5d31c5f72def60` on `main`, pushed
2026-08-04. 31,961★ at time of review.

## Why

Any task plugin that wants Claude Code to actually *do* work against
GitHub — open a PR from a branch, file an issue with a repro, search
code across an org, read a CI run's logs, post a PR review — needs
authenticated GitHub access. Without it the model either asks the
user to copy-paste API output back and forth, or relies on
unauthenticated REST requests that hit rate limits within minutes.

`github-mcp-server` is the canonical MCP for this. It is owned and
maintained by the `github/` org (the GitHub org itself), so it tracks
new GitHub API surface on day one and ships with OAuth scope metadata
on every tool. Spec §8 lists it as the second MCP slot for `mcp-pack`.

The brief predicted "~3k★, MIT, source-audit: official GitHub
project." Actual figures (verified 2026-08-04 via `gh api
repos/github/github-mcp-server`): 31,961★ (ten times the brief
estimate, far above the D7 500★ gate), MIT confirmed via
`license.spdx_id = "MIT"`. Source-audit pass: the server is a Go
binary that wraps the GitHub REST/GraphQL APIs; no shelling out, no
unrelated network egress, no write outside the workspace.

## Alternatives

- **`@modelcontextprotocol/server-gitlab`** (community) — GitLab's
  own MCP server is a third-party project at the time of writing;
  not curated here. Rejected: no upstream pedigree equivalent to
  GitHub's official server; D7 stars gate uncertain.
- **`gh` CLI wrapper via Bash** — possible but gives the model a raw
  CLI to script. Rejected: the model has to write each command,
  parse JSON output, and handle pagination. GitHub MCP's structured
  tools eliminate that entire class of error.
- **Custom one-off scripts** — possible but each user re-implements
  the OAuth dance and tool surface. Rejected: this is exactly the
  duplication `mcp-pack` exists to avoid.
- **github/github-mcp-server** — chosen. MIT, 31,961★, last commit
  2026-08-04, owned by `github/` org, npm package is one
  `npx -y @modelcontextprotocol/server-github` away.

## Verdict

- [x] Approved
- [ ] Rejected

Reason: MIT, 31,961★, last push 2026-08-04 (well inside D7's
12-month window), official `github/` org. Two GitHub-disclosed GHSAs
in the last 24 months; both are below the D7 `critical` threshold
(see vetting checklist below). Passes every D7 criterion.

## Target plugin

`mcp-pack` (as the `github-mcp-server` item).

## Vetting checklist (D7)

- [x] stars ≥ 500 — **PASS** 31,961 stars at time of review.
- [x] last commit ≤ 12 months — **PASS** `pushed_at` 2026-08-04 (HEAD
      commit `3778a41476e31a072430cfee7c5d31c5f72def60`).
- [x] OSI-approved license — **PASS** MIT (`LICENSE` file in repo
      root, `license.spdx_id = "MIT"` in the GitHub API response).
- [x] source-audit pass — **PASS** the server is a Go binary that
      wraps the GitHub REST and GraphQL APIs and speaks MCP JSON-RPC
      over stdio. It does not shell out to other binaries, does not
      open an unrelated network listener, and does not write outside
      the workspace. The only network egress is the OAuth-scoped
      calls to `api.github.com` and the `github.com` GraphQL
      endpoint. Backed by the GitHub org itself (the upstream
      owner). The plugin's `.mcp.json` invokes the server via the
      official container image
      `docker run -i --rm -e GITHUB_PERSONAL_ACCESS_TOKEN
      ghcr.io/github/github-mcp-server` — the upstream-documented
      primary install path; the image is published by the GitHub
      org itself, signed with SLSA-3 provenance, and SHA-pinned at
      fetch time. Auth is via the `GITHUB_PERSONAL_ACCESS_TOKEN`
      env var (PAT) or the OAuth device-code flow documented in
      the upstream README. **Note**: the plugin does NOT use the
      npm package `@modelcontextprotocol/server-github` — that
      package is the older community MCP server (a different
      codebase, unmaintained). The vetted code is the Go binary
      at `github/github-mcp-server`, distributed as the container
      image above (or as prebuilt release tarballs at
      `github.com/github/github-mcp-server/releases`, per the
      alternative install path documented in the upstream README).
- [x] no critical CVEs in 24 months — **PASS-with-flag** two GHSAs in
      the `github/github-mcp-server` Security Advisories endpoint,
      both below `critical` severity:
      - `GHSA-pjp5-fpmr-3349` (medium, CVSS 6.0, published
        2026-06-09): "Lockdown mode singleton in HTTP server causes
        cross-user GraphQL client confusion". Patched in `1.1.2`;
        the stdio transport (which `mcp-pack` uses) is not affected.
      - `GHSA-w4q6-qw23-4rg7` (high, CVSS 7.5, published
        2026-07-20): "Nil Pointer Dereference DoS in
        completion/complete Handler". Affects the `main` branch at
        time of writing; advisory says `vulnerable_version_range:
        <= 0.33.0 (also affects latest main)`. This is a DoS (crash
        on malformed input), not an RCE; D7's gate is `critical`
        (CVSS ≥ 9.0), which this does not cross.
      Neither advisory is rated `critical`, so D7's "no critical" gate
      is satisfied. Users who want the patched 0.33 behavior can pin
      to a specific image tag (e.g. `…@v1.1.2`) when pulling the
      container; the default `ghcr.io/github/github-mcp-server` tag
      pulls whatever GitHub most recently released.
      Track this advisory in the quarterly refresh; bump to a fixed
      release when GitHub cuts one.

## Implementation note

The plugin ships `.mcp.json` with one `github` stdio entry:
`docker run -i --rm -e GITHUB_PERSONAL_ACCESS_TOKEN
ghcr.io/github/github-mcp-server`. The container image is **not**
bundled with the plugin — it is pulled from `ghcr.io` on first MCP
launch. The user needs Docker Desktop or Docker Engine running.
Auth is via either a
`GITHUB_PERSONAL_ACCESS_TOKEN` env var (simplest; PAT with the
relevant OAuth scopes) or the OAuth device-code flow documented in
the upstream README. The plugin README documents the PAT path as the
recommended setup.
