# Architecture

## Layered view

```
┌─────────────────────────────────────────────────────────────┐
│  Claude Code (or any MCP client)                            │
│  ┌──────────────────────────────────────────────────────┐   │
│  │ Skills (markdown workflow recipes)                    │   │
│  │ - triage-orchestrator, static-triage, dynamic-hook…   │   │
│  └────────────────────┬─────────────────────────────────┘   │
└───────────────────────┼─────────────────────────────────────┘
                        │ MCP (stdio)
       ┌────────────────┼────────────────┐
       │                │                │
       ▼                ▼                ▼
 ┌───────────┐  ┌────────────┐  ┌────────────────┐
 │ static    │  │ native     │  │ dynamic        │
 │ (Python)  │  │ (Python)   │  │ (Python)       │
 │ androguard│  │ LIEF       │  │ frida + adbkit │
 │ + apktool │  │            │  │                │
 │ + jadx    │  │            │  │                │
 └─────┬─────┘  └─────┬──────┘  └────────┬───────┘
       │              │                  │
       └──────────────┴──────────────────┘
                      │ imports
                      ▼
             ┌────────────────────┐
             │ android_re_core    │  shared Python library
             │ (Project model,    │  - androguard 4.1.4
             │  apk/dex/manifest/ │  - LIEF 0.17.6
             │  frida/device)     │  - subprocess runners
             └────────────────────┘
                      │
                      ▼
             ┌────────────────────┐
             │ mcp_bridge (TS)    │  ADB / SCREENCAP / LOGCAT
             │ @modelcontextproto │  FRIDA-PS
             └────────────────────┘
```

## Process model

Every MCP server runs as its own process and communicates over **stdio** with
the MCP client. There is no shared memory between them. When the
`android-re-triage` orchestrator needs a static result, it either:

- **Recomputes** the result itself by importing `android_re_core` directly
  (preferred), or
- **Asks the user** to invoke the static MCP server first, then passes the
  result through as a context argument.

This keeps the architecture simple and avoids IPC. The downside is that an
end-to-end triage session may need to coordinate two or three MCP servers;
that's what the `android-re-triage-orchestrator` skill handles.

## State model

Three kinds of state:

1. **Project state** — per-APK in-memory objects keyed by `project_id`,
   managed by `android_re_core.project.ProjectStore`. Lost on server
   restart unless explicitly serialized to disk.
2. **Triage state** — long-running, multi-step analysis runs persisted
   to SQLite in `~/.android-re/triage.db`. Allows checkpointing,
   resumption, and correlation across the static / native / dynamic
   results. The per-triage *workdir* (on disk) now lives under
   `Output/<apk>-<sha>/<triage_id>/` — the legacy `./.triage/` at the
   repo root has been retired.
3. **File outputs** — every file-producing MCP tool (decompile, gradle
   rebuild, secrets scan, MASVS coverage, SARIF, native report,
   session report, screenshots, etc.) accepts an `output_path` /
   `output_dir` parameter. The default is derived from
   [`android_re_core.paths.output_dir_for(apk_path)`](../android_re_core/src/android_re_core/paths.py)
   and resolves to
   `Output/<apk-basename>-<short-sha>/<subdir>/<file>`. Override the
   base with the `ANDROID_RE_OUTPUT_DIR` env var (read once at import
   time). See [`output-convention.md`](output-convention.md) for the full convention.

## Tools vs. skills

| Dimension        | MCP tool                          | Claude skill                       |
|------------------|-----------------------------------|------------------------------------|
| **Interface**    | Function call with typed schema   | Markdown recipe with frontmatter   |
| **Best for**     | A single, well-defined operation  | Multi-step workflows, judgment     |
| **Examples**     | `decompile_method`                | `android-re-decompile`             |
| **Composes**     | Other tools (or external CLIs)    | Other skills + MCP tools           |
| **State**        | Stateless or per-`project_id`     | Can be long-running, checkpointed  |

A skill is the right place for **judgment and orchestration** (decide which
MASVS controls to check, correlate findings, write a report). A tool is the
right place for **typed primitives** (decompile, parse, query).

## Security model

See [Security Model](security-model.md). Summary:

- All destructive tools require `confirm: bool`.
- Skills declare their effect envelope (read-only / write-device / network)
  in frontmatter.
- `android_re_core.apk` enforces a 500 MB max APK size and 100:1
  decompression ratio.
- No `eval()` of APK content; all decompilation is text extraction.
- The on-device `frida-server` is bundled under the wxWindows licence with a
  personal-use restriction. See `LICENSE-3rdparty.md`.
