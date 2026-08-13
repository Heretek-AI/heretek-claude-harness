---
name: re-symbolic-exec
description: Symbolic execution and constraint solving with Triton. Use when the user says "find an input that reaches branch X", "solve for the magic bytes", "what inputs trigger Y", "is this branch reachable", "smash this check". Supports constraint solving, taint analysis, magic-byte search.
---

# Symbolic Execution with Triton

## When to use

Use this skill when you need to find an input that reaches a specific branch, or solve for a value that satisfies a constraint. Common prompts:

- "Find an input that bypasses this check"
- "What key/password triggers the success branch?"
- "Solve for the magic bytes that activate this code path"
- "Is this branch actually reachable?"
- "Where does this user-controlled data flow to?"

## When symbolic exec beats dynamic

Symbolic execution is the right tool when:

- You have many possible inputs and brute-force is infeasible
- The binary has a check you need to bypass
- You want to know *why* a branch is unreachable (constraint analysis)
- The check is on a function pointer, magic bytes, or a complex condition

Dynamic analysis (GDB) is the right tool when:

- You have a specific input and want to see what happens
- The behavior is timing-dependent or environmental
- The binary does syscalls / file I/O / network (Triton doesn't model these well)

## Workflow

**Step 1 — Extract the code**

Symbolic execution operates on raw machine code, not files. You need to extract the relevant bytes.

1. `re-rizin.analyze_function(path, level=2)` to find the function.
2. `re-rizin.disassemble_function(path, function, max_insns=2000)` to get the disassembly.
3. (Optional) `re-lief.parse_binary(path)` to find the function's offset in the file.
4. Use a small Python helper to read the bytes from the file at that offset.

**Step 2 — Run symbolic execution**

1. `re-triton.check_triton()` to confirm Triton is available.
2. `re-triton.symbolic_explore(code_b64=<base64 of bytes>, arch="X86_64", symbolic_args=["rdi", "rsi"], max_paths=16, timeout_s=30)`.
3. Inspect the returned `branches` list. Each entry is `(address, constraint)`.

**Step 3 — Solve a constraint**

1. For a branch you want to reach, take the constraint expression.
2. `re-triton.solve_constraint(constraint_expr="(sym_rdi + 1) == 42", vars=["sym_rdi"])`.
3. The model is a satisfying assignment — that's the input that reaches the branch.

**Step 4 — Validate**

Run the binary with the discovered input. If it crashes or behaves as expected, the solution is correct. If not, the constraint model is wrong — re-iterate.

## Worked example (crackme-style)

Suppose you have a function that checks `input[0] == 0x41 && input[1] == 0x42 && input[2] == 0x43`:

1. Disassemble the function. Find the conditional jump.
2. Mark `rdi` (or whichever register holds the input pointer) as symbolic.
3. Run `symbolic_explore` with `max_paths=4`.
4. The branch that takes the success path has constraint: `sym_rdi_0 == 65 && sym_rdi_1 == 66 && sym_rdi_2 == 67` (decimal ASCII for ABC).
5. `solve_constraint` returns `{sym_rdi_0: 65, sym_rdi_1: 66, sym_rdi_2: 67}`.
6. Provide that input to the binary.

## Taint analysis for data flow

When you want to know "where does this user input end up?":

1. `re-triton.taint_analysis(code_b64=<bytes>, taint_sources=["rdi"], steps=1000)`.
2. The result lists every `(address, register, value)` where tainted data was observed.
3. Cross-reference with `re-rizin.disassemble_function` to understand the path.

## Anti-symbolic-exec detection

Some binaries detect Triton/angr by checking for slow execution, low entropy, or unusual timing. The skill does NOT bypass these — for now, if symbolic exec doesn't converge, the binary may be using one of these tricks. Document the observation and escalate to dynamic analysis.

## Output

Produce:

1. The function analyzed (name, address)
2. The symbolic execution setup (which inputs are symbolic, max paths, timeout)
3. The branches discovered, with constraints
4. The model found (if a constraint was solved)
5. The validation result (did the input actually work?)
6. Recommendations for next steps

## Limitations

- Triton doesn't model syscalls, file I/O, network, or threading. Pure-computation functions only.
- For binary-only analysis, Triton handles x86/x64/AArch64/ARM/RISC-V. For more complex architectures, escalate to `re-angr` (v2).
- Path explosion: don't set `max_paths` above ~100 on real binaries.
- The `find_magic_bytes` tool is a high-level API — for real cracking workflows, use `symbolic_explore` + `solve_constraint` directly.
