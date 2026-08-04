# js-ts

> heretek marketplace — JavaScript/TypeScript task plugin.

## What

`biome` LSP + a `typecheck` skill. Biome is the de-facto JS/TS
toolchain in 2026 (single Rust binary that replaces `eslint`+`prettier`
+`typescript-language-server` for the inline-diagnostic role) and is
used here as the LSP. The `typecheck` skill wraps the official
`tsc --noEmit` for project-wide type checking — biome is intentionally
not a type checker, so we pair it with the reference TS compiler per
the plan's "pragmatic" note (spec §8).

## Install

```bash
/plugin install js-ts@heretek
```

## Install the LSP binary

```bash
npm install -g @biomejs/biome
```

The plugin's `.lsp.json` assumes `biome` is on `$PATH` (`biome --version`
should print something like `@biomejs/biome 2.5.7`). The plugin does NOT
ship the binary (per D7).

For type-checking you also need a TypeScript install (the `typecheck`
skill invokes `tsc`):

```bash
npm install -g typescript
```

## Use

Open any `.js`, `.ts`, `.jsx`, `.tsx`, or `.json` file. Claude Code
auto-attaches the biome LSP for inline lint, format, and import-sort
diagnostics. Biome's LSP is intentionally lint/format-only — for full
type checking pair it with the `typecheck` skill.

For a one-shot project-wide type-check pass, ask Claude Code to "run
tsc" or "typecheck the project" — the `typecheck` skill will surface
the errors.

## Components

- `.lsp.json` — biome LSP config (`biome lsp-proxy`)
- `skills/typecheck/SKILL.md` — `tsc --noEmit` workflow

## License

MIT — see [LICENSE](../../LICENSE).
