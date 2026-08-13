---
name: re-mba-deobfuscate
description: Mixed-Boolean-Arithmetic deobfuscation using Triton symbolic execution + Z3. Use when the user says "this is MBA-obfuscated", "deobfuscate this expression", "rewrite this back to normal arithmetic", "I see a + b written as (a & b) + (a | b)", "Zhou 2007", "SiMBA", "MBA-Blast". The skill uses a catalog of MBA identities and Z3 equivalence queries to simplify MBA-rewritten code.
---

# MBA Deobfuscation with Triton + Z3

## When to use

Use this skill when x86 (or AArch64 / RISC-V) code has been rewritten with **Mixed-Boolean-Arithmetic** identities — arithmetic operations expressed using a mix of bitwise and arithmetic operators to defeat pattern matching. The classic example:

```c
x + y     rewritten to    (x & y) + (x | y)     // same result
x | y     rewritten to    x + y + 1 + (~x | ~y)  // same result
x ^ y     rewritten to    (x | y) & ~(x & y)     // same result
```

Encrypted-VM bytecode schemes and academic obfuscators (SiMBA, MBA-Blast) use MBA rewriting to hide constants, control flow, and integer identities from a static reader. MBA rewriting is **semantically equivalent** to the original — it's just harder to read.

The skill uses **Triton** (already in the plugin via `re-triton`) to perform symbolic execution and **Z3** (Triton's underlying SMT solver) to prove equivalence. The plugin does the math; the LLM narrates the result.

## Companion data

Read `data/drm-indicators.yaml::mba_patterns` from the plugin root. It contains a starter catalog of MBA identities with their Z3-compatible expressions. Extend the catalog when you encounter a new pattern.

## What MBA looks like in disassembly

A normal `add eax, ebx` (5 bytes: `01 d8`) might appear as a 12-instruction sequence:

```asm
mov  ecx, eax
and  ecx, ebx
mov  edx, eax
or   edx, ebx
add  edx, ecx       ; result in edx, not eax
mov  eax, edx
```

That's the MBA form of `x + y = (x & y) + (x | y)`. The result is in `edx` not `eax`, which is a tell.

Other tells:

- The number of instructions is much higher than the obvious expression.
- A register is written, then a different register is used for the result.
- The same input is `mov`-ed into 2-3 different registers in sequence.
- The final sequence ends with a `mov` from a temporary register to the destination.

## Workflow

### Stage 1 — Locate MBA sequences (re-rizin)

1. `re-rizin.analyze_function(path, level=2)`. Find the function the user is asking about.
2. `re-rizin.disassemble_function(path, function, max_insns=2000)`.
3. Walk the disassembly looking for the tells above. Mark candidate sequences with their start address.
4. The skill does NOT auto-detect — the LLM does the visual scan, then the skill verifies with Triton.

### Stage 2 — Extract the MBA expression (the LLM does this)

For each candidate sequence, write a Python expression that captures what the disassembly computes, in terms of bit-vector arithmetic. Use the `re-triton.solve_constraint` format.

Example:

```python
# Disassembly computes edx = (eax & ebx) + (eax | ebx)
# In z3: BitVec('x') and BitVec('y')
# Expression: (x & y) + (x | y)
expr = "(x & y) + (x | y)"
vars_ = ["x", "y"]
```

The LLM should:

- Pick a bit-vector width (8, 16, 32, 64) matching the source. Most MBA is on 32-bit or 64-bit values.
- Translate each instruction into a Python expression.
- Identify the result register and use that as the LHS of the final constraint.

### Stage 3 — Verify with Z3 equivalence (re-triton)

For each candidate MBA expression, ask Z3 if it's equivalent to a simpler form. Start with the candidates in `drm-indicators.yaml::mba_patterns::identities`.

1. `re-triton.solve_constraint(constraint_expr="<mba_expr> == <original_expr>", vars=[<vars>])`.
2. If status is `sat`, the solver found a counterexample — the MBA and the original differ. The MBA is either broken (rare) or it's a different pattern than you thought.
3. If status is `unsat`, the solver proved equivalence — the MBA is correctly rewriting the original.
4. If the original expression is the simpler form, you've won. If you don't know the original, run a battery of `solve_constraint` calls against the patterns in the catalog; the first `unsat` response identifies the original.

### Stage 4 — Symbolic search for the original (re-triton, advanced)

If the catalog doesn't have a match, the LLM can ask Triton to symbolically search for a smaller equivalent expression. This is a small but powerful use of Z3's optimization capabilities.

```python
# Pseudocode for the LLM
# Given: f(x, y) = MBA expression
# Find: g(x, y) such that g is short and f == g for all (x, y)

# Approach: enumerate candidate templates of increasing length.
# For each template, ask Z3 if there's a binding of parameters that
# makes f == template for all inputs. The first binding wins.
```

This is the "what MBA-Blast does" workflow. It's a v2 feature for `re-triton`; for now, this stage is documented in the skill but not yet automated.

### Stage 5 — Patch the binary (re-lief, optional)

If the user wants the deobfuscated form in the binary:

1. Compute the bytes of the simpler expression (the deobfuscated sequence).
2. Read the original bytes at the MBA sequence's start address with `re-lief.disasm_capstone` (or `re-rizin.search_bytes`).
3. Overwrite the bytes with the simpler form. **Note:** this can break the binary if register usage is different. Always backup first and run in a sandbox.

For most analysis purposes, **don't patch the binary** — just document the equivalence in a comment.

### Stage 6 — Document (the LLM does this)

Produce a Markdown report:

```markdown
## MBA Deobfuscation: <filename> @ <address>

### MBA sequence
- Address: 0x401080–0x4010B4 (52 bytes, 12 instructions)
- Input registers: eax, ebx
- Output register: edx

### MBA form
`(x & y) + (x | y)`

### Z3 verification
- Constraint: `(x & y) + (x | y) == x + y`
- Result: `unsat` (no counterexample found)
- Equivalence proven: yes

### Source form
`x + y`

### Suggested replacement assembly
```asm
add edx, eax       ; 1 instruction, 2 bytes
```
(versus the original 12 instructions / 52 bytes — **96% size reduction**.)

### Risk of patching
- Register usage differs (edx vs eax in the source). If any downstream code assumes `eax` holds the result, patching will break it.
- The MBA version is wider in instruction footprint — a code-cache-warming defender might detect the size change.

### Recommendation
Do not patch; document. The Z3 proof is the deliverable.
```

## Limitations

- The skill requires the LLM to read disassembly and translate to Python expressions. This is a strong capability but not perfect — complex MBA sequences (chained identities, MBA-of-MBA) can confuse the translation.
- Z3 equivalence queries are slow for wide bit-vectors (64-bit). For best performance, narrow to 32-bit or 8-bit when the surrounding context allows.
- The skill does NOT handle MBA on floating-point values. Z3 has limited FP support and most MBA is on integers.
- The skill does NOT do MBA *generation* (rewriting normal code into MBA form) — only deobfuscation.

## What this skill does NOT do

- It does NOT bypass MBA-based anti-RE. It documents the equivalence.
- It does NOT handle MBA-of-MBA (recursive rewriting). v2 candidate.
- It does NOT auto-detect MBA in disassembly. The LLM points; the skill verifies.
- It does NOT produce patches. Document the equivalence; the user decides whether to patch.

## Worked example

Suppose the disassembly at 0x401050 is:

```asm
mov  ecx, eax
and  ecx, ebx
mov  edx, eax
or   edx, ebx
add  edx, ecx
mov  eax, edx
```

The LLM translates:

- After `mov ecx, eax; and ecx, ebx`: `ecx = x & y`
- After `mov edx, eax; or edx, ebx`: `edx = x | y`
- After `add edx, ecx`: `edx = (x & y) + (x | y)`
- After `mov eax, edx`: `eax = (x & y) + (x | y)`

The MBA form is `(x & y) + (x | y)`. The skill queries Z3:

```
constraint: (x & y) + (x | y) == x + y
result: unsat (proof of equivalence)
```

The original form is `x + y`, which compiles to `add eax, ebx` (2 bytes). The MBA form is 6 instructions (12 bytes). 83% smaller.

## When this skill is the wrong tool

- The disassembly has MBA-like patterns but is actually just normal code. Don't run Z3 on every `add` you see — only on sequences that match the tells.
- The MBA is on a value that has a known narrow range (e.g. a boolean). Z3 will prove equivalence, but the simpler form isn't interesting because the original was already trivial.
- The MBA is part of a *side-channel-free* constant generator (e.g. a constant derived from a long chain of bit-twiddles). In that case, the original form is "the constant." Z3 will just return `unsat` for any candidate other than the literal constant.
