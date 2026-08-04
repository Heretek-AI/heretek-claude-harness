---
slug: python-pyright
date: 2026-08-04
status: rejected
---

# microsoft/pyright

## What

`pyright` is Microsoft's static type checker for Python. It is a fast
type-checker written in TypeScript that implements the Python type system
described in PEP 484, and it can also act as an LSP server (`pyright-langserver`)
that surfaces inline diagnostics, hover types, and go-to-definition in any
editor that speaks LSP.

## Why

The `python` plugin needs an LSP — without one, the agent has no ground truth
about what resolves where, and every "fix this type error" request turns into
a re-derive-from-scratch guess. Pyright is the most widely used Python type
checker outside of `mypy` and is the canonical LSP choice in the Python
ecosystem.

## Alternatives

- **microsoft/pyright** — the canonical Python type checker; the binary is
  installed via `pip install pyright` or `npm install -g pyright`. 15,562 stars,
  MIT, pushed 2026-08-04.
- **detachhead/basedpyright** — a stricter fork with extra checks, 1.5k★
  Apache-2.0. More thorough but smaller community and slower release cadence.
- **mypy** — the original Python type checker, but it is not LSP-shaped (no
  built-in language server; you have to wrap it in `mypy-langserver` or use
  the pylsp plugin).
- **ruff** — Astral's all-in-one linter + formatter; ships its own LSP via
  `ruff server`. Picked *instead of* pyright for the python plugin: ruff is
  faster, MIT, 49k★, single tool that covers both lint (skill) and LSP.

## Verdict

- [ ] Approved
- [x] Rejected

Reason: **the `python` plugin ships `ruff` as both its skill and its LSP.**
Ruff is the de-facto Python linter in 2026 — it has effectively replaced
`flake8`, `isort`, `pyupgrade`, `black`, and parts of `pylint` in most
codebases. Adding `pyright` on top would mean two tools, two install steps,
two config files (`.ruff.toml` + `pyrightconfig.json`), and overlapping
diagnostics. The pragmatic choice for heretek's first-party python plugin
is one tool that does both jobs. This ADR is preserved so the decision is
auditable and so a future task can revisit pyright if the plugin grows a
need for dedicated type checking beyond ruff's lint scope.

## Target plugin

`python`

## Vetting checklist (D7)

- [x] stars ≥ 500 — **PASS** 15,562 stars at time of review.
- [x] last commit ≤ 12 months — **PASS** `pushed_at` 2026-08-04 (HEAD commit
      `de94b525d69e6b9554f39947d6c1eaefab5c41ab`).
- [x] OSI-approved license — **PASS** MIT (the GitHub API returns
      `NOASSERTION` for `microsoft/pyright` because the repo has no
      `license` sidebar metadata, but `LICENSE.txt` in the repo root is the
      canonical MIT License text verbatim; MIT is OSI-approved).
- [x] source-audit pass — **PASS** the `pyright` and `pyright-langserver`
      binaries are self-contained Node/TS processes; they do not shell out
      to other tools, do not fetch network resources at runtime, and do not
      write outside the workspace. Maintained by Microsoft under Eric Traut.
- [x] no critical CVEs in 24 months — **PASS** GitHub Security Advisories
      endpoint returned zero advisories for `microsoft/pyright` at time of
      review.

## Rejection rationale (D5/D15 alignment)

The plan's "pragmatic" note (spec §8) explicitly allows ruff to serve as
both LSP and skill to avoid tool-sprawl in the first-party python plugin.
Pyright's vetting passes D7 cleanly — this is not a quality rejection. It
is a scope rejection: shipping pyright on top of ruff would violate the
plan's "one tool per plugin" constraint and increase the install + config
surface for marginal benefit. If the plugin later needs strict PEP 484 type
checking that ruff's lint rules do not cover, pyright should be reconsidered.
