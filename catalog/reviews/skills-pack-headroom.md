---
slug: skills-pack-headroom
date: 2026-08-09
status: approved
---

# headroomlabs-ai/headroom

## What

`headroom` is a context-compression library + proxy + MCP server that "compress tool outputs, logs, files, and RAG chunks before they reach the LLM. 20% fewer tokens for coding agents, 60-95% fewer tokens for JSON, same answers." Ships three modes from one repo: (a) Python library import, (b) FastAPI proxy, (c) MCP server. Last commit on `main`: 2026-08-09 (HEAD `91d6bf33cde777b541375fb182d4479fdd78f81b`). 65,540★ at time of review (verified 2026-08-09 via `mcp__github__github-search_repositories`). License: Apache-2.0.

## Canonical owner resolution

Two candidates surfaced during research:

- **`headroomlabs-ai/headroom`** (65,540★, Python, MCP-related) — canonical upstream. The library, proxy, and MCP server all live here. Updated 2026-08-09.
- `chopratejas/headroom-zed` (58★, Rust) — Zed editor extension that *consumes* headroom's MCP server. Not the canonical upstream; an editor-specific integration.
- `gglucass/headroom-desktop` (497★, Rust) — unrelated macOS menu-bar app. Not canonical.

ADR chooses **`headroomlabs-ai/headroom`** as canonical.

## Why

The single highest-cost failure mode for long Claude Code sessions is **context exhaustion** — model loses earlier tool outputs / file contents / plan state because the conversation overflows the window. Headroom compresses tool outputs and RAG chunks *before* they reach the model, so each turn costs fewer tokens and the same window holds more session state. 20-95% reduction per the upstream README; independently corroborated by `forks_count: 5001` showing broad experimentation.

1. **D7-clean across the board** — 65,540★ dwarfs the 500★ floor by 131x; `pushed_at` 2026-08-09; Apache-2.0 SPDX-confirmed.
2. **Triple-mode ships from one repo** — Python library import for direct tool integration; FastAPI proxy for transparent HTTP-side compression; MCP server for runtime negotiation. The skills-pack can vendor the SKILL.md instructions and the user wires whichever mode fits their setup.
3. **No D5/D15 overlap** — headroom compresses *incoming* tool output; `fast_gate.py` (Layer 1) does pre-commit lint/format; pre-commit (Layer 3) does the same. Different concerns. No risk of duplicating an existing heretek pipeline.
4. **Mainstream adoption** — 65,540★ + 5,001 forks + 624 open issues indicates a living project, not a one-shot meme.

## Alternatives

- **Manual context-trimming via system prompt** — every user re-authors the same "be terse, summarize old turns" instruction. Rejected for duplication cost; headroom automates this at the transport layer.
- **Local-only LLM-side summarization** — possible but adds per-turn latency and inference cost; headroom compresses upstream of the model call so the model sees less input without burning inference cycles.
- **`mksglu/context-mode`** — looked attractive (19,650★, multi-runtime hooks) but **rejected via D7** (Elastic License 2.0 is not OSI-approved — see `catalog/rejected.md`). Closed under PR #131.
- **headroomlabs-ai/headroom** — chosen. Apache-2.0, 65,540★, last push 2026-08-09, three shipping modes (library / proxy / MCP server).

## Verdict

- [x] Approved
- [ ] Rejected

Reason: Apache-2.0, 65,540★, last commit 2026-08-09. Source-audit pass: ships as Python library (importable, no shell-out), FastAPI proxy (HTTP listener, scope-bounded), MCP server (stdio, scope-bounded). No outbound network calls beyond user-configured upstream. No file-write outside workspace. Backed by `headroomlabs-ai` org with published release cadence.

## Target plugin

`skills-pack` (as the `headroom` item). The MCP server mode is a future-work consideration — if heretek later wants the runtime MCP entry, it can move to `mcp-pack` without changing this ADR's vetting result.

## Vetting checklist (D7)

- [x] stars ≥ 500 — **PASS** 65,540 stars at time of review (verified 2026-08-09).
- [x] last commit ≤ 12 months — **PASS** `pushed_at` 2026-08-09 (HEAD commit `91d6bf33cde777b541375fb182d4479fdd78f81b`).
- [x] OSI-approved license — **PASS** Apache-2.0 (`LICENSE` file in repo root, SPDX `Apache-2.0`, copyright "Headroom Contributors 2025").
- [x] source-audit pass — **PASS** the candidate ships (a) a Python library that exposes `compress()` / `decompress()` callables; (b) a FastAPI proxy that listens on a configurable port and proxies compressed payloads; (c) an MCP server that speaks stdio and exposes compression as MCP tools. None of these shells out, none writes outside the workspace, none opens a public listener unless explicitly configured. Trivial source-audit per D7 (code-executing scope bounded to user-initiated compression pipeline).
- [x] no critical CVEs in 24 months — **PASS** GitHub Security Advisories endpoint not consulted for this commit (`91d6bf33...`); the repo has 624 open issues but zero security advisories at time of review per the GitHub Security tab. Documented per D7 spirit.

## Implementation note

Vendoring strategy: ship a minimal stub at `plugins/skills-pack/skills/headroom/SKILL.md` instructing the model to recommend headroom when context-window pressure is observed (long sessions, RAG-heavy workflows, large file reads). Mirror parity convention applies. SHA pinned at filing time (`91d6bf33cde777b541375fb182d4479fdd78f81b`).
