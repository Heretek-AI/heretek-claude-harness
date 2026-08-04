---
slug: web-frontend-storybook-mcp
date: 2026-08-04
status: rejected
---

# storybookjs/mcp

## What

`storybookjs/mcp` is the Storybook org's monorepo for their
Model Context Protocol server. It bundles `@storybook/mcp` (standalone
MCP library for serving Storybook component knowledge),
`@storybook/addon-mcp` (Storybook dev-server MCP), `@storybook/claude-code-plugin`
and `@storybook/codex-plugin` (agent-marketplace plugins). The upstream
description is simply "🤖". Latest commit pushed 2026-08-04. 265★
on GitHub. SPDX `MIT`.

## Why

The `web-frontend` plugin spec §8 lists `storybook-mcp` as a candidate
component for design-system workflows — letting the agent introspect a
running Storybook dev server and read component props, stories, and
docs. It is a credible *function* (Storybook is the canonical
component workshop for React/Vue/Angular/Svelte), and the upstream is
the Storybook org itself, which is a D15 pedigree win.

It is rejected on D7.

## Alternatives

- **Storybook via the dev server + a skill** — the
  `skills-pack`/`web-frontend` plugin can ship a `storybook` skill that
  invokes `npx storybook dev` and uses `chrome-devtools-mcp` (already
  in the same plugin) to inspect the resulting pages. Same agent UX
  (read component story, capture screenshot, parse knobs table), zero
  extra MCP dependency, and `chrome-devtools-mcp` already passes D7
  comfortably. This is the path forward if Storybook introspection
  becomes a top user request later.
- **Storybook MCP via a maintained alternative** — none exist with
  ≥500★ at time of review.
- **storybookjs/mcp** — rejected (this ADR).

## Verdict

- [ ] Approved
- [x] Rejected

Reason: D7 stars gate **fails**. `storybookjs/mcp` reports 265★ at time
of review (2026-08-04). D7 requires `stars ≥ 500`. The threshold is
non-negotiable per the SP3 plan §D7; the upstream is otherwise a clean
MIT project with recent activity, but the stars gate is a hard cut.

Not included in `web-frontend` v1. The brief authorises a follow-up:
when (if) `storybookjs/mcp` crosses 500★, re-vet and re-add via a new
ADR; until then, prefer the `storybook` skill + `chrome-devtools-mcp`
combination.

## Target plugin

Would target `web-frontend` if approved. Not approved.

## Vetting checklist (D7)

- [ ] stars ≥ 500 — **FAIL** 265 stars at time of review. D7 requires
      ≥ 500. Hard gate.
- [x] last commit ≤ 12 months — **PASS** `pushed_at` 2026-08-04
      (HEAD commit on the default branch).
- [x] OSI-approved license — **PASS** MIT. Repo `LICENSE` file is the
      canonical MIT text. GitHub API reports SPDX `MIT`.
- [x] source-audit pass — **PASS** the server is a TypeScript MCP
      wrapper that talks to a local Storybook dev server; no network
      listener, no shell-out beyond Storybook's own dev-server boot.
- [ ] no critical CVEs in 24 months — **PASS-with-no-data** GitHub
      Security Advisories endpoint returned zero advisories for
      `storybookjs/mcp` at time of review. (Not strictly needed since
      the stars gate already fails.)
- [ ] **D7 stars gate (≥ 500)** — **FAIL** 265★. Disqualifying.
