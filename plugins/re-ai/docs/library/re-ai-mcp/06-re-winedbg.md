---
title: "re-winedbg (RE-AI MCP server)"
category: "re-ai-mcp"
platforms: ["linux", "macos"]
difficulty: "advanced"
tags: ["wine", "winedbg", "gdbserver", "windows", "ge", "gef", "dynamic-analysis", "memory-wall"]
summary: "MCP server wrapping Wine + winedbg + gdb (headless Windows .exe debugging from Linux/macOS). 30 tools covering the Wine launch + gdbserver + GDB + GEF surface. The canonical runtime-debugging surface for Windows .exe targets. v2.8.0 closed the Wine 11+ stdio-gdbserver incompatibility (A1) + the gdb Mi prompt-sentinel trailing space (A2) + added the `end_session` MCP tool (A3)."
updated: "2026-06-07"
related: ["re-ai-mcp/01-re-ai-plugin", "re-ai-mcp/05-re-triton", "re-ai-mcp/07-re-dotnet", "anti-analysis/02-vm-bytecode-interpreter"]
---

## Summary

`re-winedbg` is the RE-AI MCP server that wraps
[Wine](https://www.winehq.org/) + winedbg + gdb
+ GEF (the headless Windows .exe debugging surface
from Linux/macOS). The server exposes 30 tools
covering the Wine launch + gdbserver + gdb
client + GEF command set. The canonical
runtime-debugging surface for Windows .exe
targets from a non-Windows host.

## Why this matters

`re-winedbg` is the **canonical runtime surface**
for the Windows .exe targets in the RE-AI plugin's
stress test. The P3R + CD + LIR + HKIA + FM26 +
TWW3 + 007FL per-target walks all rely on
`re-winedbg.start_winedbg_gdbserver` →
`attach_winedbg_gdbserver` → `set_breakpoint` →
`gef_trace_breakpoint` for the runtime analysis
of the entitlement call sites + the encrypted-VM
dispatchers.

The v2.8.0 cycle closed the Wine 11+ stdio-gdbserver
incompatibility (A1: the v2.8.0 added
`WinedbgStdioClient` class in
`servers/re-winedbg/src/re_winedbg/winedbg.py`
with the stdio subprocess + `_read_until_prompt`
loop). The v2.8.0 cycle also fixed the gdb Mi
prompt-sentinel trailing space (A2:
`servers/re-gdb/src/re_gdb/gdb_mi.py:127` drops
the trailing space) and added the `end_session`
MCP tool (A3).

## Mechanics

The server requires `wine` + `winedbg` + `gdb`
on PATH (Linux/macOS hosts only; Windows hosts
use `re-gdb` directly). The `check_winedbg()`
tool reports the installed versions of all three
+ the GEF configuration status.

The 30 tools fall into 4 categories:

| Category | Tools |
|---|---|
| **Server lifecycle** | `start_winedbg_gdbserver`, `attach_winedbg_gdbserver`, `end_session`, `launch_under_wine` |
| **Breakpoints** | `set_breakpoint`, `remove_breakpoint`, `run_to_breakpoint` |
| **Execution control** | `continue_execution`, `step_into`, `step_over`, `step_out`, `step_count` |
| **Inspection** | `read_memory`, `write_memory`, `read_registers`, `write_register`, `info_modules`, `info_threads`, `backtrace` |
| **GEF commands** | `gef_trace_breakpoint`, `gef_canary`, `gef_heap`, `gef_nearpc`, `gef_pattern_create`, `gef_pattern_offset`, `gef_registers`, `gef_vmmap` |

The `gef_trace_breakpoint(session, target,
register, format, max_hits)` tool is the
v2.4-of-the-server fast-path for handler-
frequency profiling. The v2.4 `max_hits=1000`
cap is the constraint that drove the
`handler_frequency_analyzer.py` helper in
`skills/re-vm-reverse/references/` (the
10×1000 batching pattern).

## Approach

Typical Windows .exe runtime walk:

1. `start_winedbg_gdbserver(exe, port=0,
   session="vm")` — start the winedbg gdbserver
   (the .exe is paused at its entry point).
2. `attach_winedbg_gdbserver(session="vm",
   host="127.0.0.1", port=<port>, exe=exe)` —
   connect the gdb client.
3. `info_modules(session="vm")` — populate the
   per-module base-address cache (for RVA-based
   breakpoint resolution).
4. `set_breakpoint(session="vm",
   target="*<dispatcher_addr>")` — set a
   breakpoint at the dispatcher entry.
5. `continue_execution(session="vm")` — let the
   .exe run until the breakpoint.
6. `gef_trace_breakpoint(session="vm",
   target="*<dispatcher_addr>", register="$rcx",
   format="idx=%d\\n", max_hits=1000)` — drive
   the trace server-side; the tool returns a
   structured `{hits: [{n, regs}], truncated:
   bool}` table.
7. For the 10×1000 batching pattern: drive the
   MCP call N times and feed each batch JSON
   to `references/handler_frequency_analyzer.py`
   in `skills/re-vm-reverse/`.
8. `end_session(session="vm")` — tear down the
   gdb client + the winedbg gdbserver + the
   Wine process tree.

## Common pitfalls

- **The Wine 11+ stdio-gdbserver incompatibility
  (A1).** Closed in v2.8.0 with the
  `WinedbgStdioClient` class; pre-v2.8.0 the
  server hangs after `start_winedbg_gdbserver`.
  The v2.9.0 stress test verified the closure
  on LIR + P3R + CD.
- **The Wine process tree cleanup.** `end_session`
  runs `wineserver -k` on the per-session
  WINEPREFIX (refuses to kill the global
  `~/.wine`). Forgetting `end_session` leaks
  Wine processes + the WINEPREFIX disk usage.
- **The Wine 11+ stdio regression on new targets.**
  If the per-target probe fails with a
  stdio-related error, re-run with
  `wine --version`; if Wine < 10, the cell is
  WARN (not FAIL — the host is the issue, not
  the server).

## Tooling pointers

- The `gef_trace_breakpoint` output is the
  input to `references/handler_frequency_analyzer.py`
  (the v2.9.0 helper)
- The `info_modules` output is the per-module
  base-address cache that powers RVA-based
  breakpoint resolution
- The `end_session` tool is the canonical
  teardown; calling it on a stale session is
  a no-op (idempotent)

## References

- [Wine](https://www.winehq.org/) — the
  upstream Windows compatibility layer
- [GEF](https://huggingface.co/docs/transformers/main_classes/quantizer) — the
  GDB Enhanced Features (the gdb extensions
  the server uses)
- [winedbg](https://wiki.winehq.org/Winedbg) —
  the Wine debugger
- `re-ai-mcp/05-re-triton.md` — the
  symbolic-execution bridge (the Triton +
  winedbg pair is the canonical
  dynamic + symbolic analysis combo)
- `re-ai-mcp/07-re-dotnet.md` — the .NET
  counterpart (uses the v2.8.1 C8
  `re-dotnet-patch` backend for IL patching)
- `Output/v2.9.0-stress-test/vm-unpack/
  per-target/p3r/stage4-trace.md` — the
  P3R per-target trace
