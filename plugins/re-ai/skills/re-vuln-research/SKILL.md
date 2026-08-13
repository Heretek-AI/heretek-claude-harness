---
name: re-vuln-research
description: Vulnerability research methodology. Use when the user says "find a bug", "audit this code", "is there a CVE here", "is this exploitable", "audit this binary for vulns". Structured fuzzing + static slicing + sink/source analysis. Coordinates decompile + dynamic + symbolic.
---

# Vulnerability Research

## When to use

Use this skill when the user wants to find a security vulnerability in a binary or library. The skill combines static analysis (decompile, imports, strings), dynamic analysis (GDB + GEF), and symbolic execution (Triton) to triage and confirm findings.

Common prompts:

- "Audit this binary for vulns"
- "Is there a buffer overflow in `parse_input`?"
- "Find a memory corruption bug"
- "What input triggers the bug?"

## Workflow

**Step 1 — Surface the binary**

1. `re-static-triage` (or its tools) for file info, sections, imports, strings.
2. `re-capa.detect_capabilities` for capability inventory.
3. Identify the entry point and the function that handles user input.

**Step 2 — Reduce to the entry point of interest**

Don't audit the whole binary. Find the function the user is asking about:

1. `re-rizin.analyze_function(path, level=2)`.
2. `re-rizin.get_xrefs(path, target="<user_input_function>")` to find callers.
3. Pick the function the user is asking about. If unclear, ask.

**Step 3 — Static slicing (sink/source analysis)**

1. `re-decompile` (LLM tier) to get C pseudocode.
2. Identify sinks:
   - `memcpy`, `strcpy`, `strcat`, `sprintf`, `gets` → buffer overflow
   - `malloc(size)` where `size` is user-controlled → heap overflow / integer overflow
   - `printf(format)` where `format` is user-controlled → format string
   - `free(ptr)` followed by use → use-after-free
   - `system(cmd)`, `execve(cmd)` where `cmd` is user-controlled → command injection
3. Identify sources:
   - `argv[1]`, `argv[2]`, etc.
   - `read()`, `recv()`, `fgets()` from a file/socket
   - `GetCommandLineA()`, `GetCommandLineW()`
4. Trace from source to sink. If the path is direct, the function is likely vulnerable.

**Step 4 — Dynamic confirmation (GDB)**

1. `re-gdb.start_session(path)` and `re-gdb.run_to_breakpoint(target="<function>")`.
2. Send a large crafted input (cyclic pattern) via stdin.
3. `re-gdb.gef_registers` to see if RIP/RSP got corrupted.
4. `re-gdb.gef_pattern_offset` to find the exact offset that overwrites the return address.

**Step 5 — Symbolic confirmation (Triton, optional)**

1. `re-triton.symbolic_explore` on the bytes of the vulnerable function.
2. Find the constraint that triggers the bug.
3. `re-triton.solve_constraint` to compute the minimum input that triggers it.
4. Validate by running the binary with the computed input.

**Step 6 — Severity classification**

Use the standard vulnerability severity framework:

| Severity | Criteria | Examples |
|---|---|---|
| **Critical** | Remote, pre-auth, no user interaction | RCE in a network service |
| **High** | Local, user-interaction | LPE via setuid binary, sandbox escape |
| **Medium** | Requires specific config | Authenticated RCE in admin panel |
| **Low** | DoS / info disclosure | Crash on malformed input, memory leak |
| **Info** | Theoretical / non-exploitable | Out-of-bounds read past the end of a buffer that's never used |

## Sink/source cheat sheet

| Sink | Vulnerability | Severity cue |
|---|---|---|
| `memcpy(dst, src, n)` where `n` is user-controlled | Heap/stack buffer overflow | Critical/High |
| `strcpy(dst, src)` | Stack buffer overflow | Critical/High |
| `sprintf(buf, fmt, ...)` with no length check | Stack buffer overflow | High |
| `gets(buf)` | Stack buffer overflow | Critical |
| `malloc(n)` where `n` is user-controlled | Integer overflow leading to small alloc | High |
| `free(p); use(p)` | Use-after-free | High |
| `printf(user_input)` | Format string | High |
| `system(user_input)` | Command injection | Critical |
| `dlopen(user_input)`, `LoadLibrary(user_input)` | DLL hijacking | Medium |
| `memcpy(p, user, sizeof(struct))` where struct is wrong size | Type confusion | Medium |
| `int x = user * 0x10000` | Integer overflow | High |

## Output (the vulnerability report)

```
## Vulnerability: <filename> — <type>

### Affected function
- <function name>
- Address: 0x...
- Decompiled:
  ```c
  void parse_input(char *user_buf, size_t user_len) {
      char local_buf[64];
      memcpy(local_buf, user_buf, user_len);  // ← overflow
  }
  ```

### Vulnerability
- Type: Stack-based buffer overflow
- Severity: Critical (pre-auth, network-reachable, no mitigations)
- CWE-121

### Reproduction
1. Run: `<binary> <crafted_input>`
2. Crash at: RIP=0x4242424242424242
3. Offset: 72 (return address overwritten after 64 bytes of buffer + 8 bytes of saved RBP)

### Exploitation
- NX: enabled (no shellcode on stack)
- PIE: enabled (ASLR)
- Stack canary: enabled
- Requires an info-leak or non-ASLR target

### Recommendation
- Replace `memcpy` with bounded copy
- Or add a length check
- Refs: CVE-XXXX-XXXXX (if known)
```

## What this skill does NOT do

- It does not write exploits. It identifies vulnerabilities.
- It does not bypass mitigations (NX/PIE/ASLR/canary/CFG). That's a v2 skill.
- It does not generate a YARA rule (v2 candidate).

## Limitations

- The skill is best at memory-corruption bugs (overflow, UAF, format string). Logic bugs (race conditions, TOCTOU) are harder to find statically.
- Anti-analysis samples may require manual unpacking first.
- Fuzzing-driven discovery is a complement, not a replacement, for source/sink analysis. Recommend libFuzzer/AFL for long-running fuzzing; this skill is for the first-pass manual audit.
