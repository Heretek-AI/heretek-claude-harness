---
slug: js-ts-biome
date: 2026-08-04
status: approved
---

# biomejs/biome

## What

`biome` is a single-binary toolchain for JavaScript, TypeScript, JSX/TSX,
JSON, and CSS — written in Rust by the Biome Developers team. It combines
the three jobs that historically required three separate tools: a
formatter (`biome format`, an opinionated Prettier-compatible formatter),
a linter (`biome lint`, with ~280 rules covering correctness, style,
suspicious patterns, and performance), and a project-wide analyzer
(`biome check`, which runs lint + format + import-sort in one pass). It
also ships an LSP server entrypoint — `biome lsp-proxy` — that the LSP
plugin uses to give Claude Code inline diagnostics and formatting on
edits.

Latest release at time of review: **Biome CLI v2.5.7** (published
2026-08-04). HEAD commit `6556ca3c11659ba67c33e7be3605d12f33c8616b`,
pushed 2026-08-04. 25,496★ on GitHub.

## Why

The `js-ts` plugin needs an LSP that can give Claude Code inline lint,
format, and import-sort feedback as the model edits `.js`/`.ts`/`.jsx`/
`.tsx` files. The historical solution — `eslint` for lint + `prettier`
for format + `typescript-language-server` for TS type info — is three
packages, three config files (`.eslintrc.*`, `.prettierrc.*`,
`tsconfig.json`), and three diagnostic streams the model has to merge in
its head. Biome replaces all three with one Rust binary, one
`biome.json` config, and one process. That is the same "one tool, one
install" pragmatic argument that the plan makes for `ruff` in `python`
and that Task 3 accepted (spec §8).

A second reason: the LSP server biome ships (`biome lsp-proxy`) is
exactly what Claude Code's `.lsp.json` protocol expects — a stdio JSON-RPC
server with no daemon socket to manage from the plugin side. It also
handles `.js`, `.ts`, `.jsx`, `.tsx`, and `.json` out of the box, so a
single `extensionToLanguage` map covers every common JS/TS file the model
will touch.

A third reason: biome is meaningfully faster than the alternatives. Its
own benchmarks and the community's published numbers put it at 10-25x
`eslint` on cold lint and ~2x on warm runs. That matters for the agent
loop because the LSP runs on every save — a slow LSP stretches every
edit-and-feedback cycle.

## Alternatives

- **eslint + prettier + typescript-language-server** — the legacy
  stack. Three npm packages, three config files, three daemons
  (`eslint_d`, optional `prettierd`, `tsserver`). Each needs its own
  install + version pin. Rejected: violates the plan's "one tool per
  role" pragmatic note (spec §8) and triples the install footprint.
- **oxc** (`oxc-project/oxc`) — a newer Rust toolchain in the same
  niche, ~17k stars, also MIT/Apache-2.0, also fast. We considered it
  for the same reasons as biome. Rejected: biome is more mature (its
  LSP, formatter, and CI subcommand are all 1.0+, while oxc's LSP and
  formatter are still beta), and the broader community has converged
  on biome. We can revisit if oxc catches up.
- **deno_lint** — Deno's linter, not LSP-shaped by default (no
  standalone `deno_lsp` you can point Claude Code at without bundling
  Deno itself). Rejected.
- **biomejs/biome** — chosen. MIT OR Apache-2.0 (dual-licensed; the
  Cargo crate declares `license = "MIT OR Apache-2.0"` and the repo
  ships both `LICENSE-MIT` and `LICENSE-APACHE`), 25,496★, pushed
  today, single Rust binary, single `biome.json` config, official
  `biome lsp-proxy` LSP entrypoint.

## Verdict

- [x] Approved
- [ ] Rejected

Reason: MIT OR Apache-2.0 (both OSI-approved; SPDX `Apache-2.0` on the
GitHub API side, `MIT OR Apache-2.0` in the repo's own `package.json`),
25,496★, pushed 2026-08-04. The `biome lsp-proxy` subcommand is a
documented, stable public API in the official CLI reference at
`biomejs.dev/reference/cli/`. No known critical CVEs in the GitHub
Security Advisories database for `biomejs/biome` (zero entries at time
of review). Passes every D7 criterion.

## Target plugin

`js-ts`

## Vetting checklist (D7)

- [x] stars ≥ 500 — **PASS** 25,496 stars at time of review.
- [x] last commit ≤ 12 months — **PASS** `pushed_at` 2026-08-04
      (HEAD commit `6556ca3c11659ba67c33e7be3605d12f33c8616b`, latest
      release `@biomejs/biome@2.5.7` published 2026-08-04).
- [x] OSI-approved license — **PASS** dual `MIT OR Apache-2.0`
      (both OSI-approved). Repo ships both `LICENSE-MIT` and
      `LICENSE-APACHE`. `package.json` declares
      `"license": "MIT OR Apache-2.0"`. GitHub API reports SPDX
      `Apache-2.0` as the repo's primary license.
- [x] source-audit pass — **PASS** `biome` is a single static Rust
      binary. It does not shell out to other tools at runtime, does not
      fetch network resources during LSP/format/lint operations, and does
      not write outside the workspace. The `lsp-proxy` subcommand
      forwards LSP JSON-RPC between stdio and an optional local daemon
      (`start`/`stop`) — no external socket, no network listener.
- [x] no critical CVEs in 24 months — **PASS** GitHub Security
      Advisories endpoint returned zero advisories for `biomejs/biome`
      at time of review.

## Implementation note

The plugin ships a `.lsp.json` that invokes `biome lsp-proxy`. The
`biome` binary is user-installed (per D7 — the plugin does not ship it);
the README documents `npm install -g @biomejs/biome` as the install
path. The LSP serves the inline-diagnostics role; the typecheck skill
(`skills/typecheck/SKILL.md`) covers the project-wide type-check role
and uses the official `tsc` from the `typescript` npm package (see
`js-ts-typescript.md`).
