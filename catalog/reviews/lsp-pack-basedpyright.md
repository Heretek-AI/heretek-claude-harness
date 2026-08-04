---
slug: lsp-pack-basedpyright
date: 2026-08-04
status: approved
---

# detachhead/basedpyright (lsp-pack entry)

## What

`basedpyright` is a stricter fork of Microsoft's `pyright` Python type
checker, maintained by Cameron Baertle and the `detachhead` organisation.
It adds checks beyond `pyright`'s default PEP 484 enforcement (including
some `# type: ignore` diagnostics, stricter `Optional` handling, more
aggressive `Any` warnings, no-implicit-`Any` failures) and ships the same
`basedpyright-langserver` LSP entry point used to drive inline diagnostics,
hover types, and go-to-definition in editors that speak LSP. At time of
review: 3,515 stars, MIT (`LICENSE.txt`), HEAD
`8de94d0d8e9989900ea0758abbda3fac97600dd9`, `pushed_at` 2026-08-04, zero
GitHub Security Advisories.

## Why

The `lsp-pack` is the "generic" home for users who want a single plugin
covering multiple languages without installing the per-language plugins.
For Python, the type-checking discipline heretek's D7 bar implies needs
something stricter than `ruff`'s lint-only LSP. Pyright itself is MIT and
is widely deployed, but `basedpyright` ships the same language server with
additional rules the heretek adoption story benefits from. The binary is
installed via `pip install basedpyright` (or `uv tool install
basedpyright` for a uv-managed user install) and is invoked as
`basedpyright-langserver --stdio`.

This entry mirrors the per-language `python` plugin's `ruff` LSP entry
(`catalog/reviews/python-ruff.md`); the two coexist intentionally because
`ruff` is fast lint+format and `basedpyright` is deeper type-check — they
are complementary, not duplicative. Users who want both install both
plugins; users who want only type-checking install just `lsp-pack`.

## Alternatives

- **microsoft/pyright** — upstream strict PEP 484 checker. Single-vendor
  governance; no extra discipline layer. Used as an upstream of
  basedpyright itself.
- **basedpyright** — chosen. Stricter than pyright on `# type: ignore`,
  `Optional`/`Any`, etc.; inherits pyright's MIT license (per
  `LICENSE.txt`); same LSP entry point as pyright.
- **mypy** — original Python type checker; no built-in LSP; would require
  `mypy-langserver` or `pylsp` plugin. Rejected as more moving parts.

## Verdict

- [x] Approved
- [ ] Rejected

Reason: MIT (verified by reading `LICENSE.txt` in repo root — GitHub
returns `NOASSERTION` for `license.spdx_id` because of a sibling
`.gitattributes` quirk, but the LICENSE.txt body is the canonical MIT
text); 3,515 stars (above the D7 500-star floor); last commit 2026-08-04;
zero advisories. The `basedpyright-langserver` binary is a self-contained
Node/TS process; it does not shell out to other tools, does not fetch
network resources at runtime, and does not write outside the workspace.

## Target plugin

`lsp-pack` (mirrors `python` plugin's `ruff` entry — both are approved
and ship complementary tools; see `catalog/reviews/python-ruff.md`).

## Vetting checklist (D7)

- [x] stars ≥ 500 — **PASS** 3,515 stars at time of review.
- [x] last commit ≤ 12 months — **PASS** `pushed_at` 2026-08-04 (HEAD
      `8de94d0d8e9989900ea0758abbda3fac97600dd9`).
- [x] OSI-approved license — **PASS** MIT (`LICENSE.txt` body in repo
      root is the canonical MIT License text verbatim; `LICENSE.txt`
      declares "MIT License" header).
- [x] source-audit pass — **PASS** `basedpyright-langserver` is a self-
      contained Node/TS process; no subprocess, no network IO at runtime,
      no out-of-workspace writes. The fork only adds extra checks; the
      runtime architecture is identical to upstream `pyright`.
- [x] no critical CVEs in 24 months — **PASS** GitHub Security Advisories
      endpoint returned zero advisories for `detachhead/basedpyright` at
      time of review.
