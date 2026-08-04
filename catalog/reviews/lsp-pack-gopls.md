---
slug: lsp-pack-gopls
date: 2026-08-04
status: approved
---

# golang/tools (gopls)

## What

`gopls` is the official Go language server, maintained by the Go team at
Google as a subdirectory (`gopls/`) of `golang/tools`. It implements the
Language Server Protocol (LSP) and provides go-to-definition, find-all-
references, refactorings, code completion, inline diagnostics (delegating
to `go vet` / `gopls` itself's type-checker), and `gofmt`/`goimports`
formatting integration. The repo `golang/tools` also hosts other LSP-
adjacent utilities (`goimports`, `godoc`, `guru`) but `gopls` is the only
LSP-shaped subcommand. At time of review: 7,986 stars, BSD-3-Clause
license, HEAD `da22a7bb2f9a909d2663362e582cf97771eeefab`, `pushed_at`
2026-08-04, zero GitHub Security Advisories. Install: `go install
golang.org/x/tools/gopls@latest`.

## Why

Any Go-aware Claude Code plugin needs an LSP — without one, the model
has no ground truth about what types or symbols resolve where, and every
"fix this error" request turns into a re-derive-from-scratch guess.
`gopls` is the canonical choice and is the LSP every editor (VS Code
via `golang.go` extension, Neovim, Emacs, Zed, Helix) ships out of the
box. This ADR is the `lsp-pack` (generic) entry so users who install
only `lsp-pack` get Go coverage without installing a per-language
`go` plugin (which is not yet a first-party heretek plugin). When or if
a `go` plugin is added later, both entries can coexist — Claude Code
merges LSP servers across installed plugins.

## Alternatives

- **bombshell/wyliegopls** — community fork. Smaller audience, not
  vendored by editors. Rejected for the same reason the official Python
  fork ships instead of community forks.
- **sourcegraph/go-langserver** — archived; superseded by `gopls`.
- **golang/tools/gopls** — chosen. Official Google Go team; the LSP
  every editor ships; same install instruction everywhere.

## Verdict

- [x] Approved
- [ ] Rejected

Reason: official `golang.org/x/tools/gopls`; BSD-3-Clause (OSI-approved);
7,986 stars (well above the D7 500-star floor); last commit 2026-08-04
(same day; the Go team releases `gopls` continuously in lockstep with Go
releases); zero advisories. The `gopls` binary is a single self-
contained Go binary; it shells out only to `go` itself for type-
checking (which is documented and expected LSP behaviour) and does not
fetch network resources at runtime. Passes every D7 criterion.

## Target plugin

`lsp-pack` (no per-language `go` plugin exists yet; this entry provides
the LSP slot that a future `go` plugin would mirror).

## Vetting checklist (D7)

- [x] stars ≥ 500 — **PASS** 7,986 stars at time of review (the `golang/
      tools` repo, which is broader than just `gopls`).
- [x] last commit ≤ 12 months — **PASS** `pushed_at` 2026-08-04 (HEAD
      `da22a7bb2f9a909d2663362e582cf97771eeefab`; the Go team merges
      into `master` weekly).
- [x] OSI-approved license — **PASS** BSD-3-Clause (`LICENSE` file in
      repo root; `Go` source files carry the standard BSD-3-Clause
      header; OSI-approved).
- [x] source-audit pass — **PASS** `gopls` is a single Go binary. It
      shells out to `go` for type-checking (`go build`/`go vet`) — this
      is documented LSP behaviour for gopls and is the same pattern as
      rust-analyzer calling `rustc`. No network fetches at runtime, no
      out-of-workspace writes. Maintained by the official Google Go
      team.
- [x] no critical CVEs in 24 months — **PASS** GitHub Security
      Advisories endpoint returned zero advisories for `golang/tools`
      at time of review.
