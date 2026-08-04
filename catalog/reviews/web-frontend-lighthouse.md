---
slug: web-frontend-lighthouse
date: 2026-08-04
status: approved
---

# GoogleChrome/lighthouse

## What

`lighthouse` is Google's automated website auditing CLI. It runs a
headless Chrome against a URL, scores the page on five axes
(performance, accessibility, best-practices, SEO, and PWA), and writes
an HTML report with per-rule recommendations. The npm package is
`lighthouse`; the canonical invocation is `npx lighthouse <url>`, which
spins up Chrome, audits the page, and drops `<url>.lighthouse.report.html`
in the cwd. Latest release at time of review: **`lighthouse` v13.4.1**
on npm. HEAD commit `6908063802da4ad34e17db11384c14bd89b4a69c`, pushed
2026-08-02. 30,613★ on GitHub.

## Why

The `web-frontend` plugin needs a way for the agent to *measure* the
page it just built, not just lint and type-check it. `biome lsp-proxy`
catches style and type errors. `chrome-devtools-mcp` lets the agent
inspect a live browser. Neither gives the agent a known-good rubric to
score against. Lighthouse is the rubric — it is the same scoring
engine Chrome DevTools runs when a human opens the "Lighthouse" tab,
with the same audits and the same weights. The `lighthouse` skill
ships a thin wrapper around `npx lighthouse` that the agent invokes
after a frontend change so the user gets a concrete accessibility /
performance score alongside the source diff.

It is also a D15 canonical pick: the npm package is published by the
`@googlechrome` npm scope, the repo is under `GoogleChrome/`, and the
tool is the *only* widely-installed automated-accessibility auditor with
both the scale (30k★) and the credibility (Google Chrome team) to pass
D7's source-audit bar.

## Alternatives

- **`@axe-core/cli`** — axe-core's standalone CLI. MIT, ~6k★, more
  narrowly focused on accessibility (no performance, no SEO). Rejected
  for the first cut because Lighthouse ships axe-core as one of its
  audits anyway, so the agent gets axe-quality a11y checks via
  Lighthouse without a second install. If the plugin later needs a
  pure-a11y mode (e.g. CI gating on WCAG only), `axe-core/cli` is the
  follow-up.
- **PageSpeed Insights (`psi` npm)** — Google's hosted PSI API wrapper.
  Pros: faster (no local Chrome), official scoring. Cons: rate-limited,
  not the same as a local Lighthouse run (PSI uses field data blended
  with lab data), and adds a network dependency. Rejected for the first
  cut because the agent loop is offline-friendly by design and the
  plugin does not want a network round-trip in the quality gate.
- **`@unlighthouse/cli`** — community wrapper. ~600★, MIT. Rejected:
  thinner pedigree than upstream Lighthouse and offers no D7 audit
  advantage.
- **GoogleChrome/lighthouse** — chosen. Apache-2.0, 30,613★, pushed
  2026-08-02, Google-maintained, single npm install, stable CLI shape.

## Verdict

- [x] Approved
- [ ] Rejected

Reason: Apache-2.0 (OSI-approved), 30,613★, last push 2026-08-02 (well
within D7's 12-month window), `GoogleChrome/` upstream, zero GitHub
Security Advisories for the repo at time of review. Passes every D7
criterion.

## Target plugin

`web-frontend`

## Vetting checklist (D7)

- [x] stars ≥ 500 — **PASS** 30,613 stars at time of review.
- [x] last commit ≤ 12 months — **PASS** `pushed_at` 2026-08-02
      (HEAD commit `6908063802da4ad34e17db11384c14bd89b4a69c`, latest
      npm release `lighthouse@13.4.1` published 2026-08-02).
- [x] OSI-approved license — **PASS** Apache-2.0. Repo `LICENSE` file
      is the canonical Apache-2.0 text. GitHub API reports SPDX
      `Apache-2.0`. The npm package `lighthouse` declares
      `"license": "Apache-2.0"`.
- [x] source-audit pass — **PASS** `lighthouse` is a Node.js CLI that
      drives a bundled-or-system Chrome instance via the Chrome
      DevTools Protocol. It runs entirely on the user's local machine
      against the URL the agent passes on the command line; it does
      not open a network listener, does not shell out to other
      binaries, and does not write outside the cwd (the HTML report is
      written next to where the command was invoked). The audit
      payload is contained inside the CLI; no remote services are
      contacted unless `--throttling-method=simulate` is overridden to
      `devtools` and the agent explicitly opts into remote CrUX
      fetches, which the skill does not.
- [x] no critical CVEs in 24 months — **PASS** GitHub Security
      Advisories endpoint returned zero advisories for
      `GoogleChrome/lighthouse` at time of review.

## Implementation note

The plugin ships a `skills/lighthouse/SKILL.md` that wraps `npx
lighthouse <url>` for the agent loop. The `lighthouse` npm package is
**not** bundled with the plugin — it is fetched on first invocation via
`npx`. The user needs Node.js 22 LTS and a Chrome / Chrome for Testing
binary; both are documented in the upstream README and called out in
`plugins/web-frontend/README.md`.
