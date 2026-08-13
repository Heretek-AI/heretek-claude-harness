# re-vtil

MCP server for [VTIL-Core](https://github.com/vtil-project/VTIL-Core) (Virtual-machine Translation Intermediate Language, MIT). The "lift, optimize, emit pseudo-C" trio for VM handler characterization.

## Why

The other RE-AI MCP servers handle **byte-level** binary analysis (`re-lief`, `re-rizin`, `re-triton`). They tell you *what* a handler does in machine code, but not *what it means* in a higher-level IL.

`re-vtil` fills that gap. You give it a function's machine code, it lifts to VTIL's IL, you run optimization passes, and you get a pseudo-C reading. The use case is the encrypted-VM handler characterization in `re-encrypted-vm-tamper` — once you know which bytes are a handler, `re-vtil` tells you what those bytes mean.

## Architecture

The Python MCP server is a thin wrapper around a C++ ``vtil-cli`` helper built by install.sh from the vendored VTIL-Core source tree:

```
Claude Code (MCP stdio)
  │
  ▼
re-vtil server (Python, this directory)
  │  subprocess.run(...)
  ▼
vtil-cli (C++ single binary, built from src/re_vtil/cpp/VtilCli/)
  │
  └─ VTIL-Core (vendored as a git submodule)
```

The subprocess boundary is intentional: VTIL is a heavy C++ library with no first-class Python bindings. Process isolation is robust; the Python server always loads in degraded mode if the C++ helper is missing.

## Tools

| Tool | What it does |
|---|---|
| `check_vtil` | Health check — return VTIL version + supported archs |
| `lift_handler` | Lift machine code (base64) at a given base address to VTIL IL |
| `optimize` | Run VTIL optimization passes (dead-store-elim, branch-folding, mem-dep) |
| `emit_pseudo_c` | Emit a C-like pseudocode reading of an IL tree |

## Install

`./install.sh` builds `vtil-cli` via `cmake --build` against the vendored VTIL-Core source tree, then copies the binary to `servers/re-vtil/bin/`.

To build standalone (requires VTIL-Core source + cmake):

```bash
cd servers/re-vtil/src/re_vtil/cpp/VtilCli
cmake -B build -S .
cmake --build build --config Release
cp build/vtil-cli ../../../../bin/
```

To run:

```bash
re-vtil                          # stdio transport (default for MCP)
python -m re_vtil                # equivalent
```

## Requirements

- VTIL-Core source tree (vendored as a submodule under `src/re_vtil/cpp/`)
- CMake ≥ 3.16
- A C++20 compiler (gcc-10+, clang-12+, MSVC 2019+)
- capstone + z3 (the C++ helper links against the same deps as `re-triton`)

## Degraded mode

If `vtil-cli` is not built, every tool returns `{"status": "WARN", "error": "vtil-cli not built; run install.sh", ...}`. The Python MCP server itself always loads so Claude Code can surface the install hint.

## Pairing with `re-triton`

`re-triton` handles **concrete** + **symbolic** execution (Triton lifts to its own AST, evaluates with a concrete or symbolic state). `re-vtil` handles **static IL** (VTIL lifts to its own IL, runs IR-level optimization, emits pseudo-C). The two are complementary:

- Use `re-triton.solve_constraint` for "what input reaches this branch?"
- Use `re-vtil.lift_handler + optimize + emit_pseudo_c` for "what does this handler do in the abstract?"

For the encrypted-VM bytecode family: `re-triton.emulate_function` runs the encrypted handler under concrete inputs (decryption stub triggers, handler dispatches); `re-vtil.lift_handler` lifts the decrypted handler body to VTIL IL for the static read.
