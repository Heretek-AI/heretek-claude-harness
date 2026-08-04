---
name: lighthouse
description: Run Google Lighthouse against a local or remote URL and surface actionable accessibility / performance / SEO / best-practices findings.
---

# lighthouse

Thin wrapper around `npx lighthouse <url>` for the agent loop. Use this
skill after a frontend change when the user wants a real
accessibility / performance / SEO score against the page as Chrome
sees it, not just lint-and-typecheck output from the `js-ts` plugin.

## When to use

- The user asks to "audit", "score", "check accessibility", or "check
  performance" of a page.
- The user just shipped a frontend change and wants a measurable
  before/after.
- The user wants a reproducible set of axe-core-style a11y checks
  without configuring their own `axe-cli` setup.

## When NOT to use

- The user only wants static lint/format (use `js-ts` plugin's
  `biome-lsp`).
- The user wants the page run in their own browser (just point them at
  the URL).
- The user is benchmarking back-end latency — Lighthouse is a
  *frontend* rubric. For server-side profiling use a different tool.

## Workflow

1. **Confirm the URL.** Accept a full URL (`https://example.com/`) or
   `http://localhost:3000/` for a local dev server. If the user only
   says "the page" or "my app", ask before running — Lighthouse will
   spin up Chrome either way and you want to score the right page.
2. **Pick a headless browser flag set.** For CI / sandboxed runs use
   `--chrome-flags="--headless --no-sandbox"`. For interactive runs
   leave flags off and let Chrome pop up.
3. **Run the audit.**
   ```bash
   npx lighthouse <url> \
     --output=html \
     --output-path=./lighthouse.report.html \
     --chrome-flags="--headless --no-sandbox"
   ```
   The HTML report lands at `./lighthouse.report.html` in the cwd.
4. **Open the report and extract the scores.** Open the HTML report
   and read the top-level scores for `performance`, `accessibility`,
   `best-practices`, and `seo`. If any score is below the user's bar
   (default 90), surface the top three failing audits with their
   "Learn more" links.
5. **Hand back the verdict.** Tell the user the four scores, list the
   top failing audits with a one-line fix, and ask if they want a
   follow-up patch.

## Concrete example

User: "I just rewrote the homepage, can you check accessibility?"

```bash
npx lighthouse http://localhost:3000/ \
  --output=html \
  --output-path=./lighthouse.report.html \
  --chrome-flags="--headless --no-sandbox"
```

Then open `./lighthouse.report.html` and reply with the four scores
plus the top three failing audits.

## Requirements

- Node.js 22 LTS or later.
- A current Chrome or Chrome for Testing install on the host. Lighthouse
  will try to find Chrome automatically; if it fails, install via
  `npm install -g @puppeteer/browsers` or set `CHROME_PATH`.
- Outbound network to the URL being audited (Lighthouse fetches the
  page). For localhost URLs the agent must be on the same host as the
  dev server.

## Notes

- The first invocation downloads the `lighthouse` npm package via
  `npx`. Subsequent invocations are fast.
- Pass `--quiet` to suppress Lighthouse's progress output when the
  agent is running it inside a longer script.
- Pass `--only-categories=accessibility` (or any other category) to
  scope the audit. Useful when the user only cares about one axis.
- The full flag list is at <https://github.com/GoogleChrome/lighthouse#cli-options>.

## License

Apache-2.0 — inherited from upstream `GoogleChrome/lighthouse`.
