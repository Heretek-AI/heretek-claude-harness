---
slug: lsp-pack-rust-analyzer
date: 2026-08-04
status: approved
---

# rust-lang/rust-analyzer (lsp-pack entry)

## What

`rust-analyzer` is the official Rust language server, maintained by the
`rust-lang` project and installed via `rustup component add rust-analyzer`.
It implements the Language Server Protocol (LSP) and provides go-to-
definition, find-all-references, refactorings, code completion, inline
diagnostics (via `rustc` + `clippy`), and integrated `rustfmt` formatting.
At time of review: 16,724 stars, dual `MIT OR Apache-2.0` license,
HEAD `8e505372b769fcd787b44fd5391e60fa3ada7f22`, `pushed_at` 2026-08-04.

## Why

`rust-analyzer` is the canonical LSP for Rust — every editor (VS Code,
Neovim, Emacs, Zed, Helix) ships it out of the box, and the binary is one
`rustup component add` away for any Rust developer. This ADR adds the
*generic* `lsp-pack` entry (Task 8) so that users who install only the
cross-cutting `lsp-pack` (and not the language-specific `rust` plugin)
still get Rust LSP coverage. The entry mirrors the one already in the
`rust` plugin (`catalog/reviews/rust-analyzer.md`); Claude Code merges
LSP servers from all installed plugins, so duplicate entries do not
conflict at runtime.

## Alternatives

- **IntelliJ Rust** — closed-source backend; not LSP-shaped.
- **RLS** — superseded by rust-analyzer; read-only maintenance mode.
- **`rust-lang/rust-analyzer`** — chosen. Official, ubiquitous, LSP-native.

## Verdict

- [x] Approved
- [ ] Rejected

Reason: official Rust Foundation project; dual MIT/Apache-2.0 (both OSI-
approved); 16,724 stars (well above the D7 500-star floor); last commit
2026-08-04; zero open GitHub Security Advisories. The binary is a single
self-contained LSP server that does not shell out, fetch network
resources, or write outside the workspace. Passes every D7 criterion.

## Target plugin

`lsp-pack` (mirrors `rust` plugin entry — both are approved; see
`catalog/reviews/rust-analyzer.md` for the language-plugin ADR).

## Vetting checklist (D7)

- [x] stars ≥ 500 — **PASS** 16,724 stars at time of review.
- [x] last commit ≤ 12 months — **PASS** `pushed_at` 2026-08-04 (HEAD
      `8e505372b769fcd787b44fd5391e60fa3ada7f22`).
- [x] OSI-approved license — **PASS** dual `MIT OR Apache-2.0`
      (`LICENSE-MIT` + `LICENSE-APACHE` in repo root; `Cargo.toml`
      declares `license = "MIT OR Apache-2.0"`).
- [x] source-audit pass — **PASS** self-contained LSP server; no
      subprocess, network, or out-of-workspace writes. Rust Foundation
      stewardship + 16k+ star community makes this one of the lowest-
      risk items in the marketplace.
- [x] no critical CVEs in 24 months — **PASS** GitHub Security Advisories
      endpoint returned zero advisories for `rust-lang/rust-analyzer` at
      time of review.
