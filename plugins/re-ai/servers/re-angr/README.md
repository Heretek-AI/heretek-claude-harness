# re-angr

MCP server for [angr](https://github.com/angr/angr) (UC Santa Barbara, BSD) — symbolic execution + CFG + reaching-definitions. The "I have a heavy constraint problem and want a second opinion" tool.

## Why

The other RE-AI MCP servers handle most RE tasks well. But there are two cases where angr's approach is materially different from `re-triton`'s:

- **CFG construction.** angr's CFG is built statically (no execution, no emulation) and is one of the most accurate in the open-source world. `re-rizin.analyze_function` is faster but uses different heuristics; cross-validating with angr catches edge cases.
- **Reaching definitions.** angr's dataflow analysis is what makes `re-mba-deobfuscate` reliable. An MBA identity like `x + y == (x & y) + (x | y)` *looks* like real arithmetic, but the reaching-defs graph reveals that `(x & y)` and `(x | y)` were defined from the same source — the identity is a no-op substitution.

`re-angr` exposes both, and `re-triton` for the same constraint problem. The two together give the analyst a much stronger signal than either alone.

## Architecture

The Python MCP server is a thin wrapper around an `angr-cli` Python helper installed by install.sh:

```
Claude Code (MCP stdio)
  │
  ▼
re-angr server (Python, this directory)
  │  subprocess.run(...)
  ▼
angr-cli (small Python script, wraps the angr API)
  │
  └─ angr>=9.2 (pip-installed, the actual binary analysis platform)
```

The subprocess boundary is intentional: angr keeps long-lived `AngrProject` objects, which don't survive across JSON-RPC calls cleanly. The helper spawns a fresh Python process per call, which matches the per-tool-call model the MCP server uses.

## Tools

| Tool | What it does |
|---|---|
| `check_angr` | Health check — return angr + cle versions |
| `build_cfg` | Build a control-flow graph of a binary (or one function) |
| `symbolic_exec` | Run angr symbolic execution starting at an address |
| `reaching_definitions` | Compute the def-use graph for a function |

## Install

`./install.sh` installs `angr>=9.2` from PyPI.

To install standalone:

```bash
pip install 're-angr[core]'
```

## Requirements

- Python 3.11+
- angr>=9.2 (BSD, on PyPI)
- No system dependencies

## Degraded mode

If `angr-cli` is not installed, every tool returns `{"status": "WARN", "error": "angr-cli not installed; run install.sh", ...}`. The Python MCP server itself always loads so Claude Code can surface the install hint.

## Pairing with `re-triton`

`re-triton` is the fast first-call symbolic executor (Triton 1.0 with Quarkslab's bindings). `re-angr` is the cross-validation pass:

- Use `re-triton.solve_constraint` for "what input reaches this branch?" (fast, in-process).
- Use `re-angr.symbolic_exec` for "does another symbolic executor agree?" (slower, but independent).
- Use `re-angr.reaching_definitions` for "where was this variable defined?" (Triton doesn't compute this — it's a static dataflow analysis).

For MBA-obfuscated arithmetic: `re-triton.solve_constraint` solves the symbolic equation; `re-angr.reaching_definitions` shows the variable is a no-op substitution. Both together is a strong "this is a known identity" signal.

For CFG construction: `re-rizin.analyze_function` is the fast first call; `re-angr.build_cfg` is the cross-validation pass. Discrepancies (e.g. angr sees an indirect call that rizin doesn't) are worth investigating.
