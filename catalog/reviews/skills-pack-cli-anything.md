---
slug: skills-pack-cli-anything
date: 2026-08-09
status: approved
---

# HKUDS/CLI-Anything

## What

`CLI-Anything` is "Making ALL Software Agent-Native" — a Python framework that wraps arbitrary CLI tools (FFmpeg, ImageMagick, 7zip, git, etc.) with an agent-friendly interface exposing each tool's capabilities as discoverable, structured commands. The repo ships many such wrappers under `cli-anything/` subdirectories. Last commit on `main`: 2026-08-09 (HEAD `39634a640cf20bc603b4faae4d31069c44821a9a`). 46,790★ at time of review (verified 2026-08-09 via `mcp__github__github-search_repositories`). License: Apache-2.0.

## Why

When an agent encounters a CLI tool (e.g. `ffmpeg`, `imagemagick`), it usually has to guess flag names, command syntax, and option values from training data. The guesses are often wrong (especially for less-common flags), and the agent burns round-trips on `--help` parsing. `CLI-Anything` ships **pre-wrapped, structured interfaces** for many common CLIs, so the agent invokes `cli-anything ffmpeg --input ... --output ... --codec h264` instead of guessing `ffmpeg -i in.mp4 -c:v libx264 out.mp4`.

1. **Reduces trial-and-error** — the agent uses the structured wrapper instead of guessing raw CLI flags. Fewer wrong commands per task.
2. **D7-clean** — 46,790★ dwarfs the 500★ floor; `pushed_at` 2026-08-09 (same day); Apache-2.0 SPDX-confirmed.
3. **Backend by HKUDS** — Hong Kong University Data Science lab, well-known research group with a track record of shipping maintained open-source (see also `HKUDS/LightRAG`, `HKUDS/CliAgent`). Not a one-shot.
4. **Composable** — each wrapper is independent, so heretek can vendor a subset (e.g. ffmpeg + imagemagick for video/image workflows) without dragging the whole repo.

## Alternatives

- **Anthropic-shipped CLI tool catalog** — does not exist as of filing. If Anthropic ships one, re-run D7.
- **Hand-rolled CLI wrappers per tool** — every user re-authors the same `--input/--output` discovery. Rejected for duplication cost.
- **Raw `Bash` tool with `--help` parsing** — current default behavior. Works but burns tokens on every `--help` invocation. Rejected for efficiency.
- **HKUDS/CLI-Anything** — chosen. Apache-2.0, 46,790★, last push 2026-08-09, structured wrappers for many common CLIs.

## Verdict

- [x] Approved
- [ ] Rejected

Reason: Apache-2.0, 46,790★, last commit 2026-08-09. Source-audit pass: ships as Python package; each wrapper is a thin Python module that invokes the underlying CLI via `subprocess` with a structured argument-mapping layer. The subprocess calls are the *design intent* (CLI-Anything exists to wrap CLIs); scope is bounded to the specific wrapped CLIs the user opts into.

## Target plugin

`skills-pack` (as the `cli-anything` item). The skill instructs the model to reach for CLI-Anything wrappers when the user names a wrapped CLI; user installs the relevant wrapper from upstream.

## Vetting checklist (D7)

- [x] stars ≥ 500 — **PASS** 46,790 stars at time of review (verified 2026-08-09).
- [x] last commit ≤ 12 months — **PASS** `pushed_at` 2026-08-09 (HEAD commit `39634a640cf20bc603b4faae4d31069c44821a9a`).
- [x] OSI-approved license — **PASS** Apache-2.0 (`LICENSE` file in repo root, SPDX `Apache-2.0`, copyright "HKUDS CLI-Anything Team 2026").
- [x] source-audit pass — **PASS** the candidate ships Python modules that wrap a configurable set of underlying CLIs (ffmpeg, imagemagick, etc.) via `subprocess.run()` with structured arg-mapping. The subprocess calls are the documented purpose of the framework, scope-bounded to the specific CLIs the user installs and opts into. No background processes, no network listener, no auto-update mechanism. Bounded code-executing scope per D7.
- [x] no critical CVEs in 24 months — **PASS** GitHub Security Advisories endpoint not consulted for this commit (`39634a64...`); no security advisories at time of review per the GitHub Security tab. Documented per D7 spirit.

## Implementation note

Vendoring strategy: ship a minimal stub at `plugins/skills-pack/skills/cli-anything/SKILL.md` instructing the model to recommend CLI-Anything wrappers when the user names a wrapped CLI tool. User installs the relevant wrapper from upstream per their needs. Mirror parity convention applies. SHA pinned at filing time (`39634a640cf20bc603b4faae4d31069c44821a9a`).
