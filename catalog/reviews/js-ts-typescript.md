---
slug: js-ts-typescript
date: 2026-08-04
status: approved
---

# microsoft/TypeScript (tsc typecheck workflow)

## What

`tsc` is the official TypeScript compiler — the reference implementation
of the TypeScript language maintained by Microsoft (now in active
collaboration with the TypeScript-Go team). It is a single binary
shipped via the `typescript` npm package and is the canonical "does this
type-check?" command every TypeScript developer runs before `tsc --build`
or `ts-node`. The `tsc --noEmit` invocation is the standard
typecheck-only mode (it runs the type checker without writing `.js`
output, mirroring `cargo check` for Rust or `ruff check` for Python).

Latest release at time of review: **TypeScript 6.0.3** (published
2026-04-16). HEAD commit `b465fdbfe175304d9b977da137b2c178ae1091d3`,
pushed 2026-08-03. 110,057★ on GitHub.

## Why

The `js-ts` plugin needs a project-wide type-check workflow that Claude
Code can invoke on demand — something stronger than biome's
`biome lint` (which is intentionally a lint/format tool, not a type
checker) and that complements the in-editor LSP feedback. The
`typecheck` skill (`skills/typecheck/SKILL.md`) wraps the official
`tsc --noEmit` invocation so the agent loop has a deterministic,
fast, project-wide "are there type errors?" command.

The plan calls this out explicitly (spec §8): for `js-ts`, prefer
biome for the LSP (single tool, covers lint + format + import-sort
inline) and TypeScript for the type-check skill. Biome's linter is not
a type checker; it surfaces formatting and code-quality issues but
defers type-system questions to the TS compiler. `tsc` is the only tool
that can answer those, and it is the official one.

## Alternatives

- **`typescript-language-server` / `tsserver` as a separate LSP** —
  Microsoft's `tsserver` is the type-checker that powers VS Code's TS
  experience. Running it as a standalone LSP is possible (the
  `typescript-language-server` npm package wraps it), but it overlaps
  with biome's LSP for the files we care about (`.ts`/`.tsx`) and does
  not give us a *skill-shaped* project-wide command. The plan's
  pragmatic note (spec §8) explicitly picks biome for the LSP role and
  defers TS to the type-check skill — running both as LSPs violates
  that and doubles the per-edit diagnostic stream the model has to
  merge. Rejected for the LSP role.
- **deno check** — Deno's built-in type checker. Only works on Deno
  projects; not a general TS tool. Rejected.
- **swc / esbuild** — fast transpilers, neither runs a real type
  checker (`swc` and `esbuild` both strip types without checking them).
  Wrong tool for the job. Rejected.
- **microsoft/TypeScript** — chosen. Apache-2.0, 110,057★, pushed
  2026-08-03, the reference implementation of the TypeScript language.
  Every editor (VS Code, Vim/Neovim via `coc-tsserver`, Zed, etc.)
  shells out to it for type info already.

## Verdict

- [x] Approved
- [ ] Rejected

Reason: Apache-2.0 (OSI-approved; `LICENSE.txt` in repo root declares
`Apache License, Version 2.0`), 110,057★, pushed 2026-08-03. `tsc` is
the reference TS type checker — the same binary VS Code uses internally
via `tsserver`. No known critical CVEs in the GitHub Security Advisories
database for `microsoft/TypeScript` (zero entries at time of review).
Passes every D7 criterion.

## Target plugin

`js-ts`

## Vetting checklist (D7)

- [x] stars ≥ 500 — **PASS** 110,057 stars at time of review.
- [x] last commit ≤ 12 months — **PASS** `pushed_at` 2026-08-03
      (HEAD commit `b465fdbfe175304d9b977da137b2c178ae1091d3`, latest
      release `v6.0.3` published 2026-04-16).
- [x] OSI-approved license — **PASS** `Apache-2.0` (OSI-approved;
      `LICENSE.txt` declares `Apache License, Version 2.0`, GitHub API
      reports SPDX `Apache-2.0`).
- [x] source-audit pass — **PASS** `tsc` is a single static binary that
      reads `.ts` source files and either type-checks them in memory or
      emits `.js`. It does not shell out to other tools at runtime, does
      not fetch network resources during typecheck, and does not write
      outside the workspace unless explicitly invoked with `--outDir`.
      The `--noEmit` flag (used by the skill) skips output entirely.
      Backed by Microsoft — the canonical maintainer of the TypeScript
      language.
- [x] no critical CVEs in 24 months — **PASS** GitHub Security
      Advisories endpoint returned zero advisories for
      `microsoft/TypeScript` at time of review.

## Implementation note

The skill frontmatter lives at
`plugins/js-ts/skills/typecheck/SKILL.md` and invokes
`tsc --noEmit --pretty false`. No ADR is required for the skill file
itself — it is first-party heretek code (we wrote the frontmatter)
wrapping the official upstream `tsc` command. This ADR documents *why
we recommend the underlying upstream tool* so the decision is auditable.
The skill mirrors the `cargo-check` / `ruff-check` pattern from the
`rust` and `python` plugins: same shape, same D7 checklist, same
trailing-newline convention.
