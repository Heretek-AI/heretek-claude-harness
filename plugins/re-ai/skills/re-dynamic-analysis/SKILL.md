---
name: re-dynamic-analysis
description: Dynamic analysis with GDB + GEF. Use when the user says "run this in a debugger", "set a breakpoint", "what does this do when I call X", "find the offset that triggers Y", "step through this", "I have a crash dump". Manages GDB sessions, GEF commands for heap, canary, registers, vmmap, patterns.
---

# Dynamic Analysis with GDB + GEF

## When to use

Use this skill when you need to run code, set breakpoints, examine memory, or find the offset that triggers a crash. The skill drives GDB via the GDB/MI protocol through `re-gdb` MCP server.

**Safety: never run unsigned/untrusted binaries on a host you care about.** Use a sandbox, a VM, or a Docker container. The plugin assumes you've already isolated the environment.

Common prompts:

- "Step through this in a debugger"
- "Set a breakpoint at `main` and run to it"
- "Why is this crashing? Find the offset that triggers it"
- "I have a crash dump, where did it die?"

## Workflow

**Step 1 — Set up a session**

1. `re-gdb.check_gdb()` to confirm gdb + GEF are installed.
2. `re-gdb.start_session(path="/path/to/binary", session="analyze")` to open a session.
3. Capture the returned `pid` and `gdb_args` for later steps.

**Step 2 — Run to a breakpoint**

1. `re-gdb.run_to_breakpoint(session="analyze", target="main")` to start execution and stop at `main`.
2. If the binary takes input, you may need to provide it via stdin — `re-gdb` doesn't yet have a "send stdin" tool; pre-stage input by piping it to gdb at start, or use a debugger with TTY support (GDB attach from another terminal).

**Step 3 — Inspect and step**

1. `re-gdb.step_count(session="analyze", count=1)` to single-step.
2. `re-gdb.gef_registers(session="analyze")` to see register state.
3. `re-gdb.read_memory(session="analyze", addr="0x7fffffffe000", count=32, fmt="hex")` to dump memory.
4. `re-gdb.gef_nearpc(session="analyze", n=10)` to see the next 10 instructions.

**Step 4 — GEF-specific commands**

- `re-gdb.gef_heap(session)` — `heap chunks` (glibc malloc bins)
- `re-gdb.gef_canary(session)` — `canary` (stack canary value)
- `re-gdb.gef_vmmap(session)` — `vmmap` (mapped regions with perms)
- `re-gdb.gef_registers(session)` — `registers` (extended view)

**Step 5 — End the session**

1. `re-gdb.end_session(session="analyze")` to tear down the GDB subprocess.

## Offset-finding pattern (for crash analysis)

The standard "find the offset that triggers a crash" workflow:

1. `re-gdb.gef_pattern_create(length=2000)` to generate a cyclic pattern.
2. Send the pattern as input to the binary (e.g. via stdin or argv).
3. Run the binary; it crashes at some address. Get the return address from the crash.
4. Take the bytes of the pattern that were loaded into the return address (last 4-8 bytes).
5. `re-gdb.gef_pattern_offset(value=<those bytes>)` to find the offset.
6. The result tells you exactly which input offset overwrites the return address — that's the vulnerability.

## When to use what

- **Breakpoints + step**: understanding a function's control flow
- **Watchpoints + memory dumps**: finding what writes to a specific address
- **Heap commands**: use-after-free, double-free, heap overflow
- **vmmap**: confirming NX/PIE/RELRO settings
- **nearpc + registers**: "what just happened" after a step
- **pattern_create + pattern_offset**: crash analysis

## Anti-debug detection

Some binaries detect debuggers via `ptrace`, `IsDebuggerPresent`, timing checks, etc. The skill does NOT bypass anti-debug — that's a separate v2 skill (`re-anti-debug-bypass`). For now, document what you observe and let the user decide.

If GDB fails to attach or the binary exits immediately:

1. `re-gdb.gef_registers` immediately after start — if EIP/RIP is past the entry point, the binary already self-terminated.
2. Check the binary with `re-capa.detect_capabilities` for anti-analysis rules.
3. Suggest `re-symbolic-exec` (Triton) as an alternative — it doesn't run the binary.

## Output

For each dynamic analysis run, produce:

1. The command sequence (which GDB commands you sent, in order)
2. The key observations (register state, memory dumps, GEF output)
3. A conclusion (what the binary does, what causes the crash, etc.)
4. Recommended next steps

## Windows .exe on Linux (via Wine + winedbg)

The `re-winedbg` MCP server drives the winedbg gdbserver (a
debugger shim that ships with Wine) so you can attach to a Windows
`.exe` from a Linux or macOS box. Same primitives as the
native-`re-gdb` flow, plus a launch step.

**Step 1 — Confirm Wine is available**

1. `re-winedbg.check_winedbg()` to confirm `wine` + `winedbg` + a
   compatible `gdb` are installed. If `status` is `WARN`, follow
   the install hint or set `RE_AI_SKIP_WINE=1` and use a real
   Windows host or VM instead.

**Step 2 — Launch the .exe under Wine (debugger attached)**

1. `re-winedbg.start_winedbg_gdbserver(exe="/path/to/Foo.exe",
   args=["--headless"], env={"FOO_VAR": "1"}, port=0,
   session="analyze")` — returns `{session, port, command_line}`.
   The winedbg gdbserver binds a TCP port; the .exe is paused at
   its entry point. A fresh `WINEPREFIX` is created under
   `~/.cache/re-ai-wine/<session>/` — your global `~/.wine` is
   never touched.
2. `re-winedbg.attach_winedbg_gdbserver(session="analyze",
   host="127.0.0.1", port=<port>, exe="/path/to/Foo.exe")` — opens
   a gdb-client subprocess connected to the gdbserver. On attach
   the server issues `info sharedlibrary` and populates the
   per-module base-address cache.

**Step 3 — Set a breakpoint**

- By RVA in a known DLL:
  `re-winedbg.set_breakpoint(session="analyze", target="GameAssembly.dll+0x1234")`.
  The server resolves the RVA to an absolute address via the
  per-module base-address cache populated in step 2. Module
  name match is case-insensitive and tolerates a missing `.dll`
  suffix.
- By absolute address:
  `re-winedbg.set_breakpoint(session="analyze", target="*0x180001234")`.
- By symbol:
  `re-winedbg.set_breakpoint(session="analyze", target="Foo")`
  (works for exported symbols; for IL2CPP / non-exported
  functions, prefer RVA).

**Step 4 — Continue, step, inspect**

Same tools as `re-gdb` (operating on the same `session` string):

- `re-winedbg.continue_execution(session="analyze", timeout_s=5)`
- `re-winedbg.step_into` / `step_over` / `step_out`
- `re-winedbg.read_registers` / `read_memory` / `info_modules` /
  `info_threads` / `backtrace`

`info_modules` re-runs `info sharedlibrary` and merges the result
into the cache — call it after the .exe has loaded more DLLs
(e.g. after a `continue_execution` past the initial breakpoint)
to make new modules addressable by RVA.

**Step 5 — Trace a hot handler (server-side `commands N; silent;
printf ...; continue; end`)**

`re-winedbg.gef_trace_breakpoint(session="analyze",
target="*<dispatcher_addr>", register="$rcx", format="idx=%d\\n",
max_hits=1000)` runs a server-side silent-printf command list
and returns a structured `{hits: [{n, regs}], truncated: bool}`
table. This replaces the manual GDB-command workaround used in
`re-vm-reverse` Stage 4 — the agent no longer needs to know the
`commands 1; silent; printf ...; continue; end` incantation.

**Step 6 — Patch in-memory (optional)**

`re-winedbg.write_memory(session="analyze", addr="0x...<NOP_target>",
bytes_b64="<base64-of-0x909090909090>")` writes bytes to the
debugged process. The patch is local to the debuggee; the
on-disk binary is not touched. Use this for runtime NOP-out,
hook install, or in-memory decryption-stub replacement.

**Step 7 — Tear down**

1. `re-winedbg.end_session(session="analyze")` — closes the
   gdb-client, stops the winedbg gdbserver, runs `wineserver -k`
   on the per-session prefix (refuses to kill the global
   `~/.wine`), and kills the wine process tree.

**Notes**

- `launch_under_wine` is for when you don't want a debugger
  attached — just want the .exe to run so a future
  `re-gdb.attach_pid` (or our `start_winedbg_gdbserver`) can pick
  it up.
- The winedbg gdbserver is a best-effort user-mode debugger. It
  does not implement kernel-mode debugging or hardware
  watchpoints on all architectures.

## Limitations

- `re-gdb` runs GDB in a subprocess. The MCP server is on the same host as GDB — no remote debugging yet.
- `re-winedbg` adds remote-target capability for Windows .exe
  targets: a winedbg gdbserver bound on `127.0.0.1` plus a
  gdb-client attached via `target remote`. The two halves still
  run on the same host (no true cross-host remote debug).
- No TTY support — if the binary needs an interactive terminal, use `attach_pid` from another GDB session in a different terminal.
- No conditional breakpoints via `re-gdb` yet — use `re-rizin.search_bytes` to find offsets first, then `run_to_breakpoint` to a specific address. `re-winedbg.gef_trace_breakpoint` provides a structured trace helper for Windows targets.
