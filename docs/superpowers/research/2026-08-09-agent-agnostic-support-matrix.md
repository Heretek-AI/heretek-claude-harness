# Agent-Agnostic Support Matrix

**Date:** 2026-08-09
**Companion to:** `2026-08-09-agent-agnostic-rescope.md`
**Source data:** 5 parallel research agents, 331 tool calls, verified against primary docs

---

## Per-harness config surface

| Harness | MCP config | Hooks | Skills discovery | LSP | AGENTS.md | Marketplace format |
|---|---|---|---|---|---|---|
| **Claude Code** | `.mcp.json` (`mcpServers`), transports stdio/http/sse/ws | 30+ events, 5 handler types (command/http/mcp_tool/prompt/agent) | `.claude/skills/<name>/SKILL.md`, `~/.claude/skills/`, plugin `skills/<name>/SKILL.md` | First-class via plugin `.lsp.json` (v2.0.74+) | NO (uses `CLAUDE.md`) | `.claude-plugin/marketplace.json` (canonical) |
| **Codex CLI** | `~/.codex/config.toml` → `mcp_servers` block (TOML, no `Servers` suffix) | **11 events** (PreToolUse, PermissionRequest, PostToolUse, PreCompact, PostCompact, SessionStart, SessionEnd, UserPromptSubmit, SubagentStart, SubagentStop, Stop). Hooks gated by `plugin_hooks` feature flag (0.128.0). No Notification. | `~/.codex/skills/<name>/SKILL.md`, per-repo `Repo` scope, `.system/` | **NONE** | YES (primary) | `.agents/plugins/marketplace.json` (Agent Plugins v1) — **wire-compatible with `.claude-plugin/marketplace.json`** |
| **OpenCode (sst)** | `opencode.json[c]` → `mcp.<name>` with `type: "local"\|"remote"` discriminator, OAuth + DCR built-in | TS/JS ESM plugins via `@opencode-ai/plugin` (NOT shell). Events: `tool.execute.before/after`, `session.idle`, `permission.asked`, `file.edited`, etc. (~20) | `.opencode/skills/`, `.claude/skills/`, `.agents/skills/` (all searched) | First-class opt-in (`lsp: true`), 30+ built-in servers with auto-install | YES (with CLAUDE.md fallback) | Local plugins via glob `{plugin,plugins}/*.{ts,js}` + npm `plugin:` array |
| **Cursor** | `.cursor/mcp.json` (`mcpServers`), `.cursor/hooks.json` (~20 events) | YES — Claude-compatible shape | `.agents/skills/`, `.cursor/skills/`, also reads `.claude/skills/` + `.codex/skills/` | Native (VS Code fork) | YES (root + nested) | `.cursor-plugin/marketplace.json` (Codex-compatible) |
| **Windsurf** | `~/.codeium/windsurf/mcp_config.json` (`mcpServers` with `serverUrl`) | **NONE** | `.devin/skills/`, `.windsurf/skills/` | Native | YES | — |
| **Continue.dev** | `.continue/mcpServers/*.yaml` (or `mcpServers:` in `config.yaml`) | **NONE** | **NONE** (rules/prompts in config.yaml) | Inherits host LSP | Manual (provider) | — |
| **Cline** | `~/.cline/mcp.json` (UI) | SDK plugins, 16 lifecycle stages, `.cline/hooks/` | `.cline/skills/`, `.clinerules/skills/`, `.claude/skills/` | Inherits VS Code | YES | — |
| **Aider** | **NONE** | **NONE** | **NONE** (`read:` list only) | NO | Manual (`read: AGENTS.md`) | — |
| **Zed** | `context_servers` in settings file | **NONE** | `~/.agents/skills/` or `<worktree>/.agents/skills/` | Native | YES (primary) | — |
| **Copilot Coding Agent** | `.vscode/mcp.json`, `~/.copilot/mcp-config.json` (`servers`) | **NONE** | `~/.copilot/skills/`, `.github/skills/` | Native | YES | — |
| **JetBrains Junie** | IDE UI MCP settings | **NONE** | **NONE** | Native | YES | — |
| **Replit Agent** | per-project MCP / Connectors | **NONE** | `/.agents/skills/` | Native | YES | — |
| **OpenClaude** (`Gitlawb/openclaude`) | per-profile `.openclaude-profile.json`; `@modelcontextprotocol/sdk: 1.29.0` | YES (Claude-Code-compatible, see `docs/hook-chains.md`) | Claude-Code-compatible lookup | NO | YES (own AGENTS.md in repo) | — (own catalog, isolated) |
| **DeepSeek-Reasonix** (`esengine/DeepSeek-Reasonix`) | TOML `[[plugins]]` block in `reasonix.toml` (MCP-compatible stdio plugins); `.reasonix/` namespace | **YES — Claude-Code-compatible** (`PreToolUse`, `PostToolUse`, `PermissionRequest`, `UserPromptSubmit`, `Stop`; exit 2 = block); config in `.reasonix/settings.json` | **YES — reads `.claude/skills/`, `.agents/skills/`, `.agent/skills/`, `.reasonix/skills/`** (all searched); built-ins `explore/research/review/security-review/test` | Native (Go binary) | YES — `REASONIX.md`, `AGENTS.md`, `CLAUDE.md` **all loaded** (AGENTS.md is NOT merely a fallback) | — (no first-class marketplace; plugins via TOML) |

---

## Hook event name mapping (canonical → per-platform)

| Canonical | Claude Code | Codex | OpenCode | Cursor | Cline | Reasonix |
|---|---|---|---|---|---|---|
| pre_tool_use | `PreToolUse` | `PreToolUse` | `tool.execute.before` | `preToolUse` | `tool_call_before` | `PreToolUse` |
| post_tool_use | `PostToolUse` | `PostToolUse` | `tool.execute.after` | `postToolUse` | `tool_call_after` | `PostToolUse` |
| post_tool_use_failure | `PostToolUseFailure` | — | `tool.execute.after` | `postToolUseFailure` | `tool_call_after` | — |
| permission_request | `PermissionRequest` | `PermissionRequest` | `permission.asked` | (implicit) | `before_agent_start` | `PermissionRequest` |
| user_prompt_submit | `UserPromptSubmit` | `UserPromptSubmit` | (per-session) | `beforeSubmitPrompt` | `turn_start` | `UserPromptSubmit` |
| session_start | `SessionStart` | `SessionStart` | `session.created` | `sessionStart` | `session_start` | — |
| session_end | `SessionEnd` | `SessionEnd` | `session.deleted` | `sessionEnd` | `session_shutdown` | — |
| session_idle | `Stop` | `Stop` | `session.idle` | `stop` | `run_end` | `Stop` |
| session_error | (in `Stop`) | — | `session.error` | (in `stop`) | `stop_error` | — |
| subagent_start | `SubagentStart` | `SubagentStart` | (per-message) | `subagentStart` | — | — |
| subagent_stop | `SubagentStop` | `SubagentStop` | (per-message) | `subagentStop` | — | — |
| pre_compact | `PreCompact` | `PreCompact` | `experimental.session.compacting` | `preCompact` | — | — |
| post_compact | `PostCompact` | `PostCompact` | (post-compact) | (implicit) | — | — |
| notification | `Notification` | **—** (separate legacy `notify` field) | `tui.toast.show` | (implicit) | — | — |
| permission_denied | `PermissionDenied` | — | `permission.replied` | (implicit) | — | — |

**Coverage gaps:** Codex, Reasonix, Cline drop `Notification`. OpenCode has no `PermissionRequest` parity (`permission.asked` is closest but semantically different).

---

## MCP field compatibility (canonical `mcpServers` JSON)

| Field | Claude | Cursor | Windsurf | Cline | Zed | Copilot | Continue | Codex (TOML) | OpenCode (JSONC) | Reasonix (TOML) |
|---|---|---|---|---|---|---|---|---|---|---|
| `command` | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ (`command[]`) | ✓ |
| `args` | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| `env` | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | `environment{}` | ✓ |
| `url` | ✓ | ✓ | `serverUrl` | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ (with `type:"remote"`) | — |
| `headers` | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ (http_headers) | ✓ (remote) | — |
| `type` (transport) | ✓ (stdio/http/sse/ws) | ✓ | ✓ | ✓ | implicit | ✓ (`http`/`stdio`) | ✓ | implicit | REQUIRED (local/remote) | implicit |
| `bearer_token_env_var` | — | — | — | — | — | — | — | ✓ | — | — |
| `oauth` | — | — | — | — | — | — | — | ✓ | ✓ (built-in DCR) | — |
| `enabled_tools`/`disabled_tools` | — | — | — | — | — | — | — | ✓ | — | — |
| `scopes` | — | — | — | — | — | — | — | ✓ | — | — |
| `timeout` | ✓ (HTTP/WS) | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ (`startup_timeout_sec`/`tool_timeout_sec`) | ✓ (ms, default 5000) | ✓ |
| `cwd` | — | — | — | — | — | — | — | ✓ | ✓ | — |
| `required` | — | — | — | — | — | — | — | ✓ | — | — |

---

## Marketplace format compatibility

| Harness | Native marketplace | Wire-compat with heretek? |
|---|---|---|
| Claude Code | `.claude-plugin/marketplace.json` | **canonical** |
| Codex CLI | `.agents/plugins/marketplace.json` (Agent Plugins v1) + `.claude-plugin/marketplace.json` (legacy) | **YES** — reads both natively |
| OpenCode | local plugins via glob + npm `plugin:` | NO (different shape) |
| Cursor | `.cursor-plugin/marketplace.json` | PARTIAL (rename only) |
| OpenClaude | (own catalog) | NO (fork-isolated) |
| Reasonix | (no first-class marketplace; plugins via TOML) | PARTIAL via TOML `[[plugins]]` |

---

## Target priority for heretek re-scope

| Tier | Targets | Effort | Reason |
|---|---|---|---|
| **MVP** | Codex CLI + **Reasonix** | Minimal | Both read `.claude/skills/`; Codex wire-compatible marketplace; Reasonix hooks are JSON-shape-compatible |
| **MVP** | AGENTS.md + Skill fan-out | Minimal | 12+ harnesses read AGENTS.md; SKILL.md spec is universal |
| **Phase 2** | Cursor + OpenCode | Medium | Cursor uses hooks.json shape (Claude-compatible); OpenCode needs TS plugin mirror |
| **Phase 3** | Windsurf, Cline, Zed, Copilot, Replit, JetBrains | Low | AGENTS.md + SKILL.md fan-out covers these |
| **Skip v1** | Aider (no MCP), Continue (no hooks), JetBrains (closed model) | — | Limited extension surface |
| **Skip v1** | **OpenClaude** (fork-isolated) | — | Translation required, not optional |