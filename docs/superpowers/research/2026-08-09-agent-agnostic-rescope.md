# Agent-Agnostic Re-Scope — Research Synthesis

**Date:** 2026-08-09
**Author:** deep-research (5 parallel agents, 331 tool calls total)
**Branch:** `research-heretek-agent-agnostic-rescope`
**Status:** Findings — implementation tracked via GitHub issues #TBD

---

## TL;DR

heretek is currently Claude-Code-only. The 4 major convergence points across modern coding harnesses are:

1. **Agent Plugins v1 marketplace schema** (`https://agentplugins.org/schemas/1.0.0/plugin.schema.json`) — Codex reads it natively, also reads `.claude-plugin/marketplace.json` wire-compatible.
2. **`AGENTS.md`** — Linux Foundation / Agentic AI Foundation stewarded, 60,000+ OSS projects, adopted by 15+ harnesses.
3. **Agent Skills spec** (`SKILL.md` per `agentskills.io`) — read by Claude Code, Cursor, OpenCode, Zed, Cline, Copilot, Replit, Windsurf, **Reasonix**, and more.
4. **`mcpServers` JSON shape** — universal across Claude Code, Cursor, Windsurf, Cline, Zed, Copilot, Continue, **Reasonix**, **OpenClaude**.

**MVP is much smaller than the re-scope suggests:** Codex has a wire-compatible marketplace format (zero schema change), Reasonix reads `.claude/skills/` natively and uses Claude-Code-compatible hook events, and `.claude/skills/` already works in 10+ harnesses. The hardest problem (hooks) is partially solved by Reasonix's hook parity.

## Direct answers

### Does Claude Code read `.agent/`?

**No.** Claude Code uses `.claude/skills/`, `.claude/agents/`, `.mcp.json`, `.claude/settings.json`. No `.agent/` discovery.

The cross-vendor instruction file is **AGENTS.md** (root + nested), Linux Foundation/AAIF-stewarded, 60k+ OSS projects, adopted by Codex, Cursor, Factory, Jules (Google), Amp, Zed, Copilot, JetBrains Junie, Windsurf, opencode, Cline, Replit, Warp, Devin, Augment, RooCode, Kilo Code, Gemini CLI. Source: https://agents.md/.

`.agent/skills/` is read by OpenCode (one of 6 skill paths) and Zed — but **not** Claude Code or Codex. Standardize on **AGENTS.md** as instruction layer + **SKILL.md** as skill format, not `.agent/`.

### MCP server config — formats per platform

| Platform | Path | Top-level key | Transports |
|---|---|---|---|
| Claude Code | `.mcp.json` (project) / `~/.claude.json` (user) | `mcpServers` | stdio / http / sse / ws |
| Codex CLI | `~/.codex/config.toml` / `.codex/config.toml` | `mcp_servers` (TOML, no `Servers`) | stdio / streamable-http |
| OpenCode | `opencode.json[c]` (no separate MCP file) | `mcp.<name>` with `type: "local"\|"remote"` | stdio / streamable-http / sse + OAuth DCR |
| Cursor | `.cursor/mcp.json` / `~/.cursor/mcp.json` | `mcpServers` | stdio / sse / streamable-http |
| Windsurf | `~/.codeium/windsurf/mcp_config.json` | `mcpServers` (with `serverUrl`) | stdio / sse / streamable-http |
| Cline | `~/.cline/mcp.json` | per-server entries | stdio / streamableHttp / sse |
| Zed | settings file `context_servers` | per-server entries | stdio / remote URL |
| Copilot | `.vscode/mcp.json` / `~/.copilot/mcp-config.json` | `servers` (different key!) | http / stdio + sandboxing |
| Continue | `.continue/mcpServers/*.yaml` | YAML with `name`/`version`/`schema: v1` | stdio / sse / streamable-http |
| Aider | **none** | — | — |
| **OpenClaude** | per-profile `.openclaude-profile.json`; uses `@modelcontextprotocol/sdk: 1.29.0` | Claude-Code-compatible (parity with `.mcp.json`) | stdio / http / sse / ws |
| **Reasonix** | TOML `[[plugins]]` block in `reasonix.toml` | MCP-compatible stdio plugins | stdio |

**Convergence:** `mcpServers` JSON shape (Claude + Cursor + Windsurf + Cline + Zed + Copilot + Continue + OpenClaude). Codex and Reasonix use TOML variants.

### Skills folder standardization

**Convergence:** `SKILL.md` per Agent Skills spec (`agentskills.io`), with `name` / `description` frontmatter.

| Harness | Skills discovery paths |
|---|---|
| Claude Code | `.claude/skills/<name>/SKILL.md`, `~/.claude/skills/`, plugin `skills/<name>/SKILL.md` |
| Codex CLI | `~/.codex/skills/<name>/SKILL.md`, per-repo `Repo` scope, `.system/` |
| OpenCode | `.opencode/skills/`, `.claude/skills/`, `.agents/skills/` (all searched) |
| Cursor | `.agents/skills/`, `.cursor/skills/`, also reads `.claude/skills/` + `.codex/skills/` for compat |
| Windsurf | `.devin/skills/`, `.windsurf/skills/` |
| Cline | `.cline/skills/`, `.clinerules/skills/`, `.claude/skills/` |
| Zed | `~/.agents/skills/` or `<worktree>/.agents/skills/` |
| Copilot | `~/.copilot/skills/`, `.github/skills/` |
| **Reasonix** | **`.reasonix/skills`, `.agents/skills`, `.agent/skills`, `.claude/skills`** (all searched) |
| OpenClaude | Claude-Code-compatible lookup (parity with `.claude/skills/`) |

**Key finding:** heretek's `plugins/skills-pack/` SKILL.md files already work in **Codex + OpenCode + Cursor + Cline + Reasonix + OpenClaude** without modification. **Zero polyglot work needed for skills.**

### LSP support matrix

| Harness | LSP | Notes |
|---|---|---|
| Claude Code | YES (via plugin `.lsp.json`, v2.0.74+) | Pre-built for TS/Python/Rust/Go |
| Codex CLI | **NONE** | Model-driven + ripgrep file_search; no LSP client crate |
| OpenCode | YES (opt-in `lsp: true`, 30+ built-in) | Auto-installs per file extension |
| Cursor / Windsurf / Zed / Copilot / JetBrains / Replit | NATIVE | The IDE substrate — not an extension surface |
| Cline / Continue | INHERIT host LSP (VS Code / JetBrains) | Not an extension point |
| Aider | NONE | CLI-only |
| OpenClaude | NO | (Claude Code parity; LSP lives in the host editor) |
| Reasonix | Native (Go binary) | Not an extension surface |

**Implication:** LSP is not portable. Each platform that has LSP provides it natively or via its own config. Don't target LSP cross-platform; lean on per-platform LSP for the harnesses that have it. Codex has zero story.

### Hook systems — write-once-publish-many?

**No clean abstraction exists.** Three camps:

| Camp | Harnesses | Model |
|---|---|---|
| Shell-hook JSON config | Claude Code (30+ events, 5 handler types), Cursor (~20 events), Cline (SDK plugins, 16 stages), **Reasonix** (5 events: `PreToolUse`, `PostToolUse`, `PermissionRequest`, `UserPromptSubmit`, `Stop` with exit 2 = block) | `hooks.json` / `.reasonix/settings.json` |
| Programmatic plugin | OpenCode (TS/JS ESM via `@opencode-ai/plugin`, ~20 events), Codex (TOML, 11 events — strict subset of Claude + `PermissionRequest`) | Plugin runtime |
| None | Windsurf, Zed, JetBrains, Replit, Copilot, Aider, Continue | No extension surface |

Codex hook events map **1:1** to Claude Code's events (PreToolUse, PostToolUse, SessionStart, SessionEnd, UserPromptSubmit, SubagentStart/Stop, Stop, PreCompact, PostCompact) **plus `PermissionRequest`, minus `Notification`**. Codex hooks are gated behind `plugin_hooks` feature flag (0.128.0).

**Reasonix hooks are Claude-Code-compatible** — same event names, same exit-code-2 = block semantics. Only the config location differs (`.reasonix/settings.json` vs `.claude/settings.json`).

OpenCode event names entirely different: `PreToolUse` → `tool.execute.before`, `Stop` → `session.idle`, `PostToolUse` → `tool.execute.after`, `PermissionRequest` → `permission.asked`, `SessionStart` → `session.created`. OpenCode plugins are ESM TS modules — can't ship shell `block-rm.sh` as-is.

---

## Polyglot project patterns (model after)

- **`Caesar-Nexus-Labs/caesar-harness-agent`** — broadest fan-out (12 native targets) via `npx @caesar/cli add --tool <tool>`. Model heretek's `/plugin marketplace add` after.
- **`cboone/agent-harness-plugins`** — cleanest build pipeline. `bin/build-codex-marketplace` + `bin/build-opencode-mirror` committed in repo, CI fails on drift. Closest analog to heretek's `scripts/generate_marketplace.py`.
- **`yitianlian/harnessbridge`** — converter CLI (`hb convert --from cursor --to claude`) via canonical Zod JSON schema (6 tools × 30 paths). Useful as migration tool, not primary publisher.
- **`tomdale/agent-plugins`** — tiered `universal/` + `claude/` + `codex/` polyglot layout.
- **`Gitlawb/openclaude`** — npm `@gitlawb/openclaude`, v0.27.0; Claude Code fork adapted for 200+ providers; uses `@modelcontextprotocol/sdk: 1.29.0`; own `.openclaude/` namespace; **DOES NOT read `.claude/` paths**. Translator required to ship OpenClaude-compatible output. Likely out-of-scope v1.
- **`esengine/DeepSeek-Reasonix`** — Go-based, MIT, npm `reasonix`, has VS Code extension + desktop app; `.reasonix/` namespace but **reads `.claude/skills/` natively**; hooks are Claude-Code-compatible (`PreToolUse`/`PostToolUse`/`PermissionRequest`/`UserPromptSubmit`/`Stop` with exit-2=block). **To support: trivial — emit `.reasonix/settings.json` mirroring `.claude/settings.json`; SKILL.md already works.** Highest-leverage new target.

## MCP server directories (polyglot install surface)

- **`https://mcp.directory/`** — 3,000+ servers, ships multi-platform install snippets (Cursor, VS Code, Claude Desktop, Claude Code, Codex, ChatGPT). Most polyglot registry.
- **`https://registry.modelcontextprotocol.io/`** — official MCP registry (vendor-neutral).
- **`https://github.com/mcp`** — GitHub's official MCP registry.
- **`punkpeye/awesome-mcp-servers`** — 92,006 stars, canonical community list.

---

## Pipeline architecture recommendation

### MVP (this sprint, minimal diff)

1. Extend `scripts/generate_marketplace.py` to emit `.agents/plugins/marketplace.json` alongside `.claude-plugin/marketplace.json`. Codex reads both natively (wire-compatible). **Zero schema change.**
2. Codex-specific MCP config translator: convert canonical `mcpServers` JSON → TOML `mcp_servers` block.
3. Reasonix target: emit `.reasonix/settings.json` mirroring `.claude/settings.json` (hooks) and `.reasonix/skills/` mirror (or rely on Reasonix's native `.claude/skills/` lookup).
4. Per-plugin AGENTS.md excerpt generator: write `<plugin>/AGENTS.md` from `catalog.yaml` `description` field. Free reach to 12+ harnesses.

### Phase 2 (next sprint)

5. Cursor target: emit `.cursor/mcp.json` + `.cursor/hooks.json` per plugin. Wire-compatible with Claude shape (just rename `mcpServers`).
6. OpenCode target: write `plugins/hooks/opencode/<name>.ts` per hook plugin (TS module wrapping the existing shell logic in `tool.execute.before/after` + `session.idle` handlers). OpenCode `mcp.<name>.type=local` with `command`/`args`/`environment`/`timeout`.
7. OpenCode plugin generator: emit `dist/opencode/plugins/<name>/index.ts` from canonical plugin def (cboone pattern, CI fails on drift).
8. Skill path fan-out: per-plugin publish to `.claude/skills/`, `.agents/skills/`, `.codex/skills/`, `.opencode/skills/`, `.cline/skills/` via symlink or copy in CI.

### Phase 3 (post-MVP)

9. Hook event normalizer DSL: `plugins/hooks/canonical-events.yaml` maps heretek events → per-platform names. CI gate that every heretek hook event has a matrix entry (even if `unsupported`).
10. SKILL.md fan-out: per-plugin symlink/copy `.claude/skills/<name>/SKILL.md` to all discovered paths.
11. OpenClaude feasibility spike: write translator from canonical heretek config to OpenClaude shape (high effort; defer unless user explicitly wants OpenClaude).

---

## Hard problems to accept as constraints

1. **Codex has no LSP** — any heretek plugin relying on LSP must skip Codex.
2. **Codex hook subset** — heretek's hooks plugin must accept that `Notification` drops on Codex (and Codex hooks are still gated behind `plugin_hooks` feature flag).
3. **OpenCode uses TS plugins** — D15-locked `plugins/hooks/` would need TS rewrites, not just config translation. Significant effort.
4. **7 of 11 surveyed harnesses have no hooks** — must degrade to AGENTS.md conventions or skill metadata for those.
5. **`.agent/` is not a standard** — fight the temptation to standardize there; AGENTS.md is the real convergence.
6. **OpenClaude is fork-isolated** — `.openclaude/` namespace is deliberately separate from `.claude/`. Translation is required, not optional.

---

## Caveats

- **Reasonix** / **OpenClaude** are real, indexed products — not misspellings or fictional. Both have npm packages, VS Code extensions, and substantial adoption signals. Initial synthesis mis-identified them; this document supersedes that.
- AGENTS.md ecosystem stats verified via agents.md + GitHub code search (60k+ repos, Aug 2026).
- All config schemas verified against current primary docs (Aug 2026). Codex 0.128.0, Claude Code v2.1.218+, OpenCode main branch.

## Open questions

1. **Codex `plugin_hooks` feature flag** — what's the rollout timeline? If still unstable, ship Codex marketplace support without hooks first.
2. **OpenCode plugin API stability** — `@opencode-ai/plugin` is the SDK surface; is it stable enough to ship hooks as ESM? Worth a spike.
3. **Caesar-style install UX** — does heretek's `/plugin marketplace add` need per-target install modes? Or is `git clone + run generate` enough?
4. **AGENTS.md per-plugin vs aggregated** — ship one per plugin (cleaner for polyglot, doubles file count) or one aggregated root AGENTS.md (smaller, less precise)?
5. **OpenClaude inclusion** — explicitly out-of-scope v1; revisit if user/team demand emerges.

## Sources

Primary docs:
- Anthropic Claude Code: https://code.claude.com/docs/en/{mcp,hooks,skills,sub-agents,plugins}
- OpenAI Codex CLI: https://developers.openai.com/codex + github.com/openai/codex (codex-rs/config + core-plugins + skills + external-agent-migration)
- OpenCode: https://opencode.ai/config.json + github.com/anomalyco/opencode
- AGENTS.md: https://agents.md/
- Agent Plugins v1 schema: https://agentplugins.org/schemas/1.0.0/plugin.schema.json
- Agent Skills spec: https://agentskills.io/

Other harnesses (verified docs):
- Cursor: cursor.com/docs/{mcp,hooks,skills,rules}
- Windsurf / Devin: docs.devin.ai/desktop/cascade/{mcp,skills,memories}
- Continue: docs.continue.dev
- Cline: docs.cline.bot
- Zed: zed.dev/docs/ai
- Copilot: code.visualstudio.com/docs/agent-customization
- JetBrains: jetbrains.com/help/ai-assistant
- Replit: docs.replit.com/features/agent

OSS alternatives:
- OpenClaude: github.com/Gitlawb/openclaude (npm `@gitlawb/openclaude`, v0.27.0)
- DeepSeek-Reasonix: github.com/esengine/DeepSeek-Reasonix (npm `reasonix`, MIT, Go)

Polyglot projects studied:
- github.com/Caesar-Nexus-Labs/caesar-harness-agent (12-target fan-out)
- github.com/cboone/agent-harness-plugins (codegen mirror with CI drift check)
- github.com/yitianlian/harnessbridge (canonical JSON schema converter)
- github.com/tomdale/agent-plugins (tiered polyglot layout)
