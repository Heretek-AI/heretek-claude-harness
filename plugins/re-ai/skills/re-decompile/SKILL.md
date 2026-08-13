---
name: re-decompile
description: Decompile a function to C-like pseudocode. Use when the user says "decompile this function", "what does X::Y do", "show me the source for main". Prefers re-llm-decompile (AI), falls back to re-rizin's pdc, falls back to re-lief disasm. Handles multiple architectures.
---

# Decompile a Function

## When to use

Use this skill when the user wants to understand what a specific function does at a C-like level of abstraction. Common prompts:

- "What does `main` do in `/bin/ls`?"
- "Decompile `sub_1400010a0` from this PE"
- "Show me the source of the function at `0x401000`"

## Workflow (resolution ladder)

The skill uses a 3-tier resolution ladder — try the highest-fidelity tool first, fall back gracefully.

**Tier 1 — LLM decompiler (highest fidelity, when available)**
1. `re-rizin.analyze_function(path)` to get the function list
2. Locate the requested function (by name, address, or symbol)
3. `re-rizin.disassemble_function(path, function, max_insns=2000)` to get the disassembly
4. `re-llm-decompile.decompile_function(disasm=..., arch=..., calling_conv=..., context=...)` to get C pseudocode
5. Optionally `re-llm-decompile.rename_variables(decompiled=...)` to improve names

**Tier 1.5 — agent-inline decompilation (v2.8.0, when the LLM tier is WARN/ERROR)**

If `re-llm-decompile.check_endpoint()` returns `status: WARN` (e.g. the resolved model is cloud-backed and likely to return HTTP 403 on programmatic calls — confirmed in r03-stress Phase 5), OR if a `decompile_function` call raises `LLMCallError` with `is_cloud_model: True`, fall through to this tier: do the decompile reasoning **yourself** with the disassembly as context. The agent host's already-loaded model produces the C pseudocode without needing a separate LLM endpoint.

1. Same step 1-3 as Tier 1 (analyze + locate + disassemble)
2. **Cap the disasm slice at 200 instructions per call** to keep the prompt budget tight. For longer functions, chain across multiple Tier 1.5 calls and stitch the results
3. Read the disasm yourself; produce the C pseudocode in the same shape that `decompile_function` would have returned (with `arch`, `calling_conv`, `context` in mind)
4. Record the output with a `tier: 1.5` marker in the per-binary JSON so a future re-run sees the provenance

Zero infra, zero auth, zero billing ambiguity. Use this when Tier 1 is structurally unavailable, not just transiently slow.

**Tier 2 — rizin pdc (medium fidelity, no LLM endpoint)**
1. Same step 1-2 as above
2. `re-rizin.decompile_function(path, function)` — direct pseudo-C from rizin

**Tier 3 — annotated disassembly (always works)**
1. `re-rizin.disassemble_function(path, function, max_insns=2000)`
2. Wrap the disassembly in a Markdown table with address, bytes, instruction
3. Add a paragraph at the top describing what the disassembly pattern suggests (loop, call, branch, etc.)

## Choosing the tier

Before starting, check `re-llm-decompile.check_endpoint()`. If `status: OK`, use Tier 1. Otherwise fall back to Tier 2 (rizin pdc), and only if pdc is unavailable fall back to Tier 3.

## Prompt-shaping for the LLM

When using Tier 1, include these fields in the call to `re-llm-decompile.decompile_function`:

- `disasm`: the disassembly text (one instruction per line is ideal)
- `arch`: e.g. "x86_64", "aarch64", "arm" — match the binary's architecture
- `calling_conv`: "SystemV" (Linux x86_64), "MS_x64" (Windows), "AAPCS" (ARM), "cdecl" (x86), etc.
- `context`: any caller-provided context — "this is the HTTP request handler for POST /login", "this is the entry point", etc. The LLM uses this to choose argument names and types.

If the function calls other functions whose names are visible in the disassembly (e.g. `call printf`), include those in `context` so the LLM can use them as type hints.

## Lifting to LLVM-IR (optional)

For complex functions, `re-llm-decompile.summarize_binary` can produce a one-paragraph summary. For per-function decompilation, prefer the LLM tier.

## Output

Always return:

1. The decompiled C code in a fenced ```c block
2. A 2-3 sentence explanation of what the function does
3. A list of "things to look at next" — interesting calls, suspicious patterns, IOCs

## Common pitfalls

- **Packed binaries** — the entry stub decodes the real code. After decompiling the stub, you need to find the OEP (original entry point) and decompile that. Use `re-rizin.search_bytes` for known packer signatures, or `re-triton.emulate_function` to step through the unpacker.
- **PLT/GOT** — calls to `@plt` are unresolved at static time. Tell the LLM the binary is dynamically linked and the names will resolve at runtime.
- **Vtables / dispatch tables** — decompiled output for C++ often shows vtable calls as `arg1->vtable[0x18](arg2)`. Note this in the explanation.
- **Optimizer output** — `-O2`/`-O3` binaries have functions that don't look like the source. `re-llm-decompile.explain_function` is often a better first read than `decompile_function` for these.

## What this skill does NOT do

- It does not run the binary. For dynamic analysis, use `re-dynamic-analysis`.
- It does not solve for input values. For constraint solving, use `re-symbolic-exec`.
- It does not produce a security audit. For vuln hunting, use `re-vuln-research`.
