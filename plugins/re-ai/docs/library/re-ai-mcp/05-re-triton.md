---
title: "re-triton (RE-AI MCP server)"
category: "re-ai-mcp"
platforms: ["linux", "windows", "macos"]
difficulty: "advanced"
tags: ["triton", "symbolic-execution", "concolic", "taint-analysis", "coverage-map", "constraint-solving"]
summary: "MCP server wrapping the Triton library (the concolic / symbolic-execution engine). 7 tools covering concrete emulation, symbolic exploration, taint analysis, magic-byte solving, constraint solving, and coverage maps. The canonical solver for \"what input reaches branch X\" + the input to fuzz-style replay corpora. Pairs with re-rizin (the disasm input) and re-gdb (the runtime verification)."
updated: "2026-06-07"
related: ["re-ai-mcp/01-re-ai-plugin", "re-ai-mcp/02-re-rizin", "re-ai-mcp/06-re-winedbg", "anti-analysis/02-vm-bytecode-interpreter"]
---

## Summary

`re-triton` is the RE-AI MCP server that wraps
[Triton](https://triton-library.github.io/) — the
concolic / symbolic-execution engine. The server
exposes 7 tools covering concrete emulation,
symbolic exploration, taint analysis, magic-byte
solving, constraint solving, and coverage maps.

## Why this matters

`re-triton` is the **canonical solver for "what
input reaches branch X"**. The RE-AI plugin uses
Triton for:

- **Magic-byte solving** —
  `re-triton.find_magic_bytes(code_b64=<bytes>,
  target_bytes_b64=<bytes>, ...)` solves for the
  input that produces a target output. Used in
  `re-symbolic-exec` ("find input that reaches
  branch X", "solve for magic bytes").
- **Coverage mapping** —
  `re-triton.coverage_map(code_b64=<bytes>,
  base_address=0x400000)` lifts machine code to
  a coverage map. The output is the input to
  `re-fuzz-replay` (the fuzzer's coverage
  feedback).
- **Taint analysis** —
  `re-triton.taint_analysis(code_b64=<bytes>,
  taint_sources=["rdi", "rsi"])` tracks which
  memory/registers are influenced by the
  taint sources. Used in `re-vm-reverse` to
  trace the dispatcher's per-handler-index
  routing.

## Mechanics

The server requires `triton` (`pip install triton`).
Triton is heavy (~100 MB install) but provides
full x86_64 + AArch64 + ARM32 + MIPS + RISC-V
symbolic execution. The `check_triton()` tool
reports the installed version + the supported
architectures.

The 7 tools:

| Tool | Purpose |
|---|---|
| `check_triton` | Health check |
| `emulate_function` | Concrete emulation of machine code for N steps |
| `symbolic_explore` | Run symbolic execution; return constraints at branch exits |
| `coverage_map` | Lift machine code to edges hit + blocks seen |
| `taint_analysis` | Track which memory/registers are influenced by taint sources |
| `find_magic_bytes` | Solve for the input that produces the target output bytes |
| `solve_constraint` | Feed a constraint expression to Z3 and return a model |

The `code_b64` parameter (machine code bytes,
base64-encoded) is the input to all the lifting
tools. The `arch` parameter selects the target
architecture.

## Approach

Typical workflow:

1. `re-rizin.disassemble_function(path,
   function=<rva>)` — lift the disasm to text.
2. Reassemble the bytes via
   `re-lief.disasm_capstone(path, section_name=
   ".text", offset=<rva>, size=<bytes>)` to get
   the machine code.
3. Base64-encode the bytes → `code_b64`.
4. `re-triton.find_magic_bytes(code_b64=...,
   target_bytes_b64=..., base_address=0x400000,
   arch="X86_64", length=8)` — solve for the
   input.
5. Verify with `re-gdb` (or `re-winedbg` for
   Windows .exe targets).

## Common pitfalls

- **Triton is heavy.** The library is a full
  symbolic-execution engine; install time +
  memory footprint are large. Use
  `emulate_function` (concrete) when symbolic
  isn't required.
- **The `code_b64` base64 is transport-friendly**
  but you must base64-encode the raw bytes,
  not the disassembly text.
- **The `length` parameter on `find_magic_bytes`**
  is the input length; tune it to the size of
  the input the function reads (typically 4-32
  bytes for a magic-byte check; up to 1 KB
  for a hash pre-image).

## Tooling pointers

- The `coverage_map` output is the input to
  `re-fuzz-replay.seed_replay` (the fuzzer's
  coverage feedback)
- The `solve_constraint` output is the
  primitive; the higher-level `find_magic_bytes`
  wraps it for the common "solve for input"
  use case
- The `emulate_function` (concrete) +
  `symbolic_explore` (symbolic) pair covers
  the full emulation spectrum

## References

- [Triton](https://triton-library.github.io/) —
  the upstream project
- [KLEE](https://klee.github.io/) — the
  alternative symbolic-execution engine
  (Triton is the RE-AI choice for its
  Python-first API)
- `re-ai-mcp/02-re-rizin.md` — the canonical
  disasm input source
- `re-ai-mcp/06-re-winedbg.md` — the canonical
  runtime verification (for Windows .exe
  targets)
- `Output/v2.9.0-stress-test/vm-unpack/
  per-target/p3r/stage5-handler-lift.md` — the
  per-handler lift (the Triton + LLM
  decompile canonical use case)
