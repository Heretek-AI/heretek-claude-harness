---
slug: rust-clippy
date: 2026-08-04
status: approved
---

# rust-lang/rust-clippy

## What

`clippy` is the official Rust linter, maintained by the `rust-lang` project
and shipped as a `rustup component` (`rustup component add clippy`). It
ships over 800 lints across categories — `correctness` (deny), `suspicious`
(warn), `style`, `complexity`, `perf`, plus opt-in `pedantic`, `restriction`,
`nursery`, and `cargo`. `rust-analyzer` already invokes `clippy` for
inline diagnostics, but the agent loop benefits from a separate
"run clippy project-wide" workflow that surfaces all lint findings as a
single report.

## Why

`cargo check` answers "does it compile?". `cargo clippy` answers "does it
compile *and* does it follow Rust idioms?". The two are distinct signals
and the heretek `rust` plugin should ship both so the user (and Claude
Code) can choose. A `clippy`-aware workflow catches the 80% of "looks
fine but is subtly wrong or unidiomatic" patterns that `cargo check` is
not designed to flag.

The binary is shipped alongside `rust-analyzer` via `rustup`, so there is
no extra install step for the user — `rustup component add rust-analyzer`
already brings the toolchain that contains `clippy`.

## Alternatives

- **`cargo check` alone** — insufficient for idiom/lint coverage (see ADR
  `rust-cargo-check.md`).
- **Third-party linters** (`cargo-deny`, `cargo-machete`, `dylint`) —
  useful but orthogonal; they catch unused deps and custom rules, not
  idiomatic-Rust patterns. Out of scope for the first `rust` plugin.
- **`rust-lang/rust-clippy`** — chosen. Official, ubiquitous, no extra
  install beyond `rustup`.

## Verdict

- [x] Approved
- [ ] Rejected

Reason: official Rust Foundation project, dual MIT/Apache-2.0 license,
13,424 stars, last commit 2026-08-03. Source-audit: `clippy` is a set
of lints compiled into the same toolchain that ships `rustc`; it does
not shell out to anything outside the `rustup` toolchain. No known
critical CVEs in the GitHub Security Advisories database.

## Target plugin

`rust`

## Vetting checklist (D7)

- [x] stars ≥ 500 — **PASS** 13,424 stars at time of review.
- [x] last commit ≤ 12 months — **PASS** `pushed_at` 2026-08-03 (HEAD
      commit `8c34b94d986619698fd3b4c2c0eb287aeac97d79`).
- [x] OSI-approved license — **PASS** dual `MIT OR Apache-2.0` (README
      badge: "License: MIT OR Apache-2.0").
- [x] source-audit pass — **PASS** `clippy` runs as a `cargo` subcommand
      that invokes `rustc` with extra lint passes; no network calls, no
      external subprocess beyond the Rust toolchain. Rust Foundation
      stewardship and 13k+ stars make this one of the lowest-risk items
      in the marketplace.
- [x] no critical CVEs in 24 months — **PASS** GitHub Security Advisories
      endpoint returned zero advisories for `rust-lang/rust-clippy` at
      time of review.
