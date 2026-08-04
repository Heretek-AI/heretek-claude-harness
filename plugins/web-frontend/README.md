# web-frontend

> heretek marketplace — first-party plugin

## What

Web frontend task plugin: chrome-devtools MCP for browser introspection
(performance traces, network logs, screenshots, console messages,
remote debugging) plus the `lighthouse` skill for accessibility,
performance, best-practices, and SEO scoring. Together they give
Claude Code the same diagnostic surface Chrome DevTools gives a human
developer.

## Install

```bash
/plugin install web-frontend@heretek
```

## Components

- **MCP: `chrome-devtools`** — Google's `chrome-devtools-mcp` server,
  launched via `npx -y chrome-devtools-mcp@latest`. Exposes a live
  Chrome instance over MCP. Requires Node.js LTS and a current stable
  Chrome (or Chrome for Testing). See
  `catalog/reviews/web-frontend-chrome-devtools-mcp.md` for the
  vetting record.
- **Skill: `lighthouse`** — wrapper around `npx lighthouse <url>` that
  scores a page on the five Lighthouse categories and surfaces the
  top failing audits. See `skills/lighthouse/SKILL.md` and
  `catalog/reviews/web-frontend-lighthouse.md`.

## Requirements

- Node.js 22 LTS or later (`chrome-devtools-mcp` and `lighthouse` both
  fetch via `npx` on first use).
- A current stable Chrome or Chrome for Testing install on the host.

## Out of scope (v1)

- `storybook-mcp` — rejected on D7's `stars ≥ 500` gate
  (`storybookjs/mcp` reports 265★ at time of review). If your
  Storybook-driven workflow needs component introspection, use the
  `chrome-devtools` MCP against a running `npx storybook dev` server
  plus the `lighthouse` skill. See
  `catalog/reviews/web-frontend-storybook-mcp.md` for the full
  rationale and re-vet trigger.

## License

MIT — see [LICENSE](../../LICENSE).
