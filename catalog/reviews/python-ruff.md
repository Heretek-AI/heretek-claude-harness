---
slug: python-ruff
date: 2026-08-04
status: approved
---

# astral-sh/ruff

## What

`ruff` is Astral's all-in-one Python linter, formatter, and (since 0.4.x)
LSP server. Written in Rust, it implements the rule sets of `flake8`,
`isort`, `pyupgrade`, `pylint`, `flake8-bugbear`, `flake8-quotes`, and
many more — and runs them 10-100x faster than the Python tools it
replaces. The `ruff server` subcommand launches a Language Server Protocol
server; the `ruff check` and `ruff format` subcommands are the linter and
formatter entry points.

## Why

The `python` plugin needs both an LSP (so Claude Code can surface inline
type and lint errors while editing `.py` files) and a skill (so the agent
can run a project-wide lint pass on demand without spawning an editor).
Picking two separate tools — e.g. `pyright` for LSP and `flake8` for the
skill — means two installs, two config files, and two diagnostic streams
that the model has to mentally merge. Ruff is the de-facto Python linter
in 2026 (it has effectively replaced `flake8`/`isort`/`black`/`pyupgrade`
in most major Python projects) and it ships its own LSP. Choosing ruff
for both roles is the plan's "pragmatic" choice (spec §8) and gives
users a single `pip install ruff` (or `uv tool install ruff`) install
for the entire plugin.

## Alternatives

- **flake8 + isort + black + pyupgrade** (the pre-ruff stack) — multiple
  Python packages, each with its own config file (`.flake8`, `setup.cfg`,
  `pyproject.toml` for `isort` and `black`), 10-100x slower than ruff.
  Rejected for heretek use: too many moving parts, slow enough to hurt
  the agent loop.
- **pylint** — thorough but extremely slow and noisy; not LSP-shaped by
  default (you need `pylsp` plugins). Rejected.
- **microsoft/pyright** — see `python-pyright.md`. Rejected as LSP for
  this plugin because ruff already covers the LSP role and adding pyright
  on top would violate the plan's "one tool per plugin" pragmatic note.
- **astral-sh/ruff** — chosen. MIT, 49,068★, pushed 2026-08-04, single
  binary that does lint + format + LSP. The canonical 2026 Python tool.

## Verdict

- [x] Approved
- [ ] Rejected

Reason: MIT, 49,068★, last commit 2026-08-04 (same day). The `ruff`
binary is a single self-contained Rust executable that does not shell
out, does not fetch network resources, and does not write outside the
workspace. The `ruff server` LSP subcommand is documented as a stable
public API at `docs.astral.sh/ruff/editors`. No known critical CVEs in
the GitHub Security Advisories database for `astral-sh/ruff`. Passes
every D7 criterion.

## Target plugin

`python`

## Vetting checklist (D7)

- [x] stars ≥ 500 — **PASS** 49,068 stars at time of review.
- [x] last commit ≤ 12 months — **PASS** `pushed_at` 2026-08-04 (HEAD
      commit `e49143a56844560165df2b869a77da80858bca9f`, latest release
      `v0.16.1`).
- [x] OSI-approved license — **PASS** MIT (`LICENSE` in repo root, MIT
      header on every source file, Cargo workspace declares
      `license = "MIT"`).
- [x] source-audit pass — **PASS** `ruff` is a single static Rust
      binary; it does not shell out to other tools, does not fetch
      network resources at runtime, and does not write outside the
      workspace. The `ruff server` LSP process is the same binary in
      LSP-server mode. Backed by Astral (the team behind `uv` and
      `rye`) — a well-funded, well-known Python-tooling company.
- [x] no critical CVEs in 24 months — **PASS** GitHub Security
      Advisories endpoint returned zero advisories for `astral-sh/ruff`
      at time of review.

## Implementation note

Ruff serves two roles in this plugin:

1. **LSP** — `.lsp.json` invokes `ruff server` for inline diagnostics
   on `.py` and `.pyi` files. Note: ruff's LSP is intentionally
   lint/format-only; for navigation/completion it is meant to be paired
   with a Python type checker. For heretek's first-party plugin, the
   plan's "pragmatic" note accepts ruff-only and defers pyright-basedpyright
   type-checking to a future task if needed.
2. **Skill** — `skills/ruff-check/SKILL.md` runs `ruff check
   --output-format=concise --no-cache` from the project root and
   surfaces the first 50 lines of output.
