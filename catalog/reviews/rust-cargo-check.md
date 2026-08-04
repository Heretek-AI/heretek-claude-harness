---
slug: rust-cargo-check
date: 2026-08-04
status: approved
---

# rust-lang/cargo (cargo-check workflow)

## What

`cargo check` is the upstream `cargo` subcommand that type-checks a Rust
crate without producing a binary. It is part of `rust-lang/cargo` (the
official package manager / build tool, installed by `rustup` itself) and
is the canonical "did this compile?" command every Rust developer runs
before running tests or building.

## Why

The `rust` plugin's flagship workflow is "edit a `.rs` file → surface
type errors fast". `rust-analyzer` gives in-editor diagnostics, but the
agent loop needs a way to do a project-wide check without spawning a
debug build (which can take minutes on large crates). `cargo check` is the
exact tool for that — it runs `rustc`'s type-check phase, prints
`file:line:col` diagnostics, and exits in seconds.

The first-party skill (`skills/cargo-check/SKILL.md`) wraps this command
so Claude Code can invoke it without the user writing the invocation
every time.

## Alternatives

- **`cargo build`** — type-checks *and* links a binary. 5-10x slower than
  `cargo check` on real projects. Wastes CI/agent-loop time for a workflow
  whose only goal is "are there type errors?".
- **`cargo clippy`** — useful (and shipped separately as a Clippy skill in
  Task 3), but runs lints on top of `cargo check`. Mixing the two
  confuses "is this a type error or a style nit?" for the model.
- **`cargo check`** — chosen. The minimal, fastest way to answer "does
  this compile?". Already on every Rust developer's machine via `rustup`.

## Verdict

- [x] Approved
- [ ] Rejected

Reason: `cargo check` is a built-in subcommand of the official
`rust-lang/cargo` tool, which is shipped to every Rust user via `rustup`
itself (no extra install step). It is not a third-party plugin — it is
the canonical, upstream-blessed workflow. The `skills/cargo-check/SKILL.md`
skill is first-party heretek code (we wrote the frontmatter) wrapping the
official upstream command. The skill itself needs no ADR — first-party
skills ARE first-party. This ADR documents *why we recommend the
underlying upstream tool* so the decision is auditable.

## Target plugin

`rust`

## Vetting checklist (D7)

- [x] stars ≥ 500 — **PASS** `rust-lang/cargo` has 13,000+ stars; well over
      threshold. (`cargo check` is a subcommand of `cargo`, not a separate
      repo — the stars count applies to the parent tool.)
- [x] last commit ≤ 12 months — **PASS** `rust-lang/cargo` is under active
      Rust Foundation maintenance; HEAD updated within days.
- [x] OSI-approved license — **PASS** `rust-lang/cargo` is dual
      `MIT OR Apache-2.0` (same as every Rust Foundation tool).
- [x] source-audit pass — **PASS** `cargo check` is a built-in subcommand
      of `cargo`, not a third-party wrapper. It invokes `rustc` directly
      with the same compiler the user already trusts. No external
      subprocess beyond `rustc` itself.
- [x] no critical CVEs in 24 months — **PASS** zero GitHub Security
      Advisories of critical severity for `rust-lang/cargo` at time of
      review.

## Implementation note

The skill frontmatter lives at `plugins/rust/skills/cargo-check/SKILL.md`
and invokes `cargo check --message-format=short --color=never`. No ADR
required for the skill file itself — it is first-party heretek code, not
an upstream item.
