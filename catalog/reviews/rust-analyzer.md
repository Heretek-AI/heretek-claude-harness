---
slug: rust-analyzer
date: 2026-08-04
status: approved
---

# rust-lang/rust-analyzer

## What

`rust-analyzer` is the official language server for Rust, maintained by the
`rust-lang` project and shipped as a `rustup component` (`rustup component
add rust-analyzer`). It implements the Language Server Protocol (LSP) and
provides go-to-definition, find-all-references, refactorings, code completion,
inline diagnostics (via `rustc` + `clippy`), and integrated `rustfmt`
formatting. The repo contains both the LSP binary and a reusable library
crateset (`ide`, `hir`, `syntax`, `parser`) that other Rust tooling builds on.

## Why

Any Rust-aware Claude Code plugin needs an LSP — without one, the model has no
ground truth about what types or symbols resolve where, and every "fix this
error" request turns into a re-derive-from-scratch guess. `rust-analyzer` is
the canonical choice: it is the LSP every editor (VS Code, Neovim, Emacs,
Zed, Helix) ships out of the box, and the binary is one `rustup component add`
away for any Rust developer. Heretek's `rust` plugin needs it.

## Alternatives

- **IntelliJ Rust** (`intellij-rust/intellij-rust`) — closed-source backend
  plus a partial open-source frontend. Does not implement LSP natively;
  requires the JetBrains IDE. Rejected for plugin use (not LSP-shaped).
- **RLS (Rust Language Server)** — the *previous* official LSP, now in
  maintenance mode and superseded by `rust-analyzer`. The `rust-lang`
  README explicitly recommends `rust-analyzer`. Rejected as obsolete.
- **`rust-lang/rust-analyzer`** — chosen. Official, LSP-native, ubiquitous,
  one `rustup` command away.

## Verdict

- [x] Approved
- [ ] Rejected

Reason: official Rust Foundation project, dual MIT/Apache-2.0 license,
16,724 stars, last commit 2026-08-04 (same day). Source-audit: README is
short and points at the published manual; the binary is invoked as an LSP
subprocess from any editor and does not shell out to anything else. No
known critical CVEs in the GitHub Security Advisories database for this
repo. Passes every D7 criterion.

## Target plugin

`rust`

## Vetting checklist (D7)

- [x] stars ≥ 500 — **PASS** 16,724 stars at time of review.
- [x] last commit ≤ 12 months — **PASS** `pushed_at` 2026-08-04 (HEAD commit
      `987d712f743ecf3651180735a8189b8cb398ec0a`).
- [x] OSI-approved license — **PASS** dual `MIT OR Apache-2.0` (both
      `LICENSE-MIT` and `LICENSE-APACHE` are present in the repo root;
      Cargo.toml declares `license = "MIT OR Apache-2.0"`). Both MIT and
      Apache-2.0 are OSI-approved.
- [x] source-audit pass — **PASS** the binary is a single self-contained
      LSP server; it does not shell out to other tools, does not fetch
      network resources, and does not write outside the workspace. The
      Rust Foundation stewardship and 16k+ star community use make this
      one of the lowest-risk items in the entire marketplace.
- [x] no critical CVEs in 24 months — **PASS** GitHub Security Advisories
      endpoint returned zero advisories for `rust-lang/rust-analyzer` at
      time of review.
