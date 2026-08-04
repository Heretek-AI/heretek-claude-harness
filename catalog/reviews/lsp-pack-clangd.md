---
slug: lsp-pack-clangd
date: 2026-08-04
status: approved
---

# clangd/clangd

## What

`clangd` is the official C/C++/Objective-C language server, maintained
by the LLVM project and the `clangd` org on GitHub. It is built on
Clang's own frontend and implements the Language Server Protocol (LSP)
to provide go-to-definition, find-all-references, refactorings
(`clang-rename`), code completion, inline diagnostics (via `clang`
itself, including `-Wall -Wextra` and `clang-tidy` integration when
configured via `.clangd` or `compile_commands.json`), and `clang-format`
formatting integration. At time of review: 2,261 stars, Apache-2.0
license, HEAD `0d73b70db36385313702175b480183eb80ca6a16`, `pushed_at`
2026-07-13, zero GitHub Security Advisories. Install: distro package
(`apt install clangd`, `brew install clangd`, `dnf install clangd`) or
`git clone https://github.com/clangd/clangd && ninja install` for
source builds.

## Why

Any C/C++-aware Claude Code plugin needs an LSP — without one, the
model has no ground truth about what types or symbols resolve where,
and every "fix this error" request turns into a re-derive-from-scratch
guess. `clangd` is the canonical choice: it is the LSP every editor
(VS Code via `clangd` extension, Neovim, Emacs, Zed, Helix, CLion)
ships out of the box, and it ships under the same permissive
Apache-2.0 license as the rest of the LLVM toolchain. This ADR is the
`lsp-pack` (generic) entry so users who install only `lsp-pack` get
C/C++ coverage without installing a per-language `cpp` plugin (which
is not yet a first-party heretek plugin). When or if a `cpp` plugin is
added later, both entries can coexist — Claude Code merges LSP servers
across installed plugins.

## Alternatives

- **cquery** — community C/C++ LSP. Lower activity; superseded by
  clangd. Rejected.
- **ccls** — community C/C++ LSP forked from cquery. Active but
  smaller audience; not vendored by editors. Rejected.
- **vscode-cpptools (Microsoft C/C++ extension)** — VS Code only; not
  a separate LSP binary. Rejected (not portable across editors).
- **clangd/clangd** — chosen. Official LLVM project; the LSP every
  C/C++ developer already has from their editor; same binary across
  every install method.

## Verdict

- [x] Approved
- [ ] Rejected

Reason: official LLVM project; Apache-2.0 (OSI-approved); 2,261 stars
(above the D7 500-star floor); last commit 2026-07-13 (within the 12-
month freshness window); zero advisories. The `clangd` binary is a
single self-contained Clang-based C++ binary; it shells out to
`clang-tidy` for additional diagnostics when configured (documented
LSP behaviour) and reads `compile_commands.json` for project
configuration. No network fetches at runtime, no out-of-workspace
writes. Passes every D7 criterion.

## Target plugin

`lsp-pack` (no per-language `cpp` plugin exists yet; this entry
provides the LSP slot that a future `cpp` plugin would mirror).

## Vetting checklist (D7)

- [x] stars ≥ 500 — **PASS** 2,261 stars at time of review.
- [x] last commit ≤ 12 months — **PASS** `pushed_at` 2026-07-13 (HEAD
      `0d73b70db36385313702175b480183eb80ca6a16`). Note: clangd's
      release cadence is slower than e.g. rust-analyzer's because it
      tracks LLVM's 6-month release cycle; this is expected and not a
      staleness signal.
- [x] OSI-approved license — **PASS** Apache-2.0 (`LICENSE.TXT` in
      repo root; `clangd` is part of the LLVM project; OSI-approved).
- [x] source-audit pass — **PASS** `clangd` is a single Clang-based
      binary. It shells out to `clang-tidy` for additional diagnostics
      when configured (documented in `.clangd` config); no network
      fetches at runtime, no out-of-workspace writes. Maintained by the
      official LLVM project.
- [x] no critical CVEs in 24 months — **PASS** GitHub Security
      Advisories endpoint returned zero advisories for `clangd/clangd`
      at time of review.
