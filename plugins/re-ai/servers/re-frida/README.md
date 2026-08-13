# re-frida

MCP server wrapping the **Frida** dynamic-instrumentation
toolkit. Frida injects a JavaScript engine (V8) into a target
process and lets the analyst hook arbitrary functions, walk the
type graph, and call into the target at runtime.

The MCP layer adds:

- a stable session identifier — multiple scripts and hooks can be
  installed under one session, sharing state.
- a strict allowlist of binary-operation shapes — Frida exposes
  the full V8 JS API to scripts but the MCP wrappers only call
  the canonical, well-understood primitives (attach, spawn,
  enumerate, hook, RPC).
- **soft-skip behaviour** — when the ``frida`` Python module or
  the native ``libfrida`` are missing, every tool returns ``WARN``
  with an install hint and the plugin keeps working.

## Tools

| Tool | What it does |
|---|---|
| `check_frida` | Health check — return frida version, native lib presence, USB device list |
| `start_session` | Spawn a new process under Frida (target: Android / iOS / native PID / remote endpoint) |
| `attach_pid` | Attach to a running process by host PID |
| `script_load` | Compile + load a Frida script (JavaScript) into a session |
| `script_call` | Call a method on a loaded script's exports (RPC) |
| `enumerate_modules` | List modules loaded into the session's process |
| `enumerate_exports` | List exports of a single module |
| `hook_method` | Install an Interceptor hook on a named method |
| `rpc_export` | Register a Python-side callable as an RPC export the JS side can call |
| `end_session` | Tear down a session, unload scripts, detach |

## Install

Frida is a heavy install (the Python module pulls in ``frida`` +
``frida-tools``; the underlying ``libfrida`` is a native shared
library shipped via PyPI wheels). To install standalone:

```bash
pip install -e ./servers/re-frida
```

On the **target device** (the phone or VM Frida is talking to),
the matching ``frida-server`` binary must be running. See
<https://frida.re/docs/>.

## Run

```bash
re-frida                            # stdio transport (default for MCP)
python -m re_frida                  # equivalent
```

## Deferred to a future run

The original Explore findings called for a Frida server; this
plugin-internal scaffolding lands it so the deep-dive agents can
pick it up. The Windows targets in the Live Fire stress test
still use `re-winedbg` as the primary dynamic tool; the Android
target future run is where `re-frida` becomes the workhorse.
