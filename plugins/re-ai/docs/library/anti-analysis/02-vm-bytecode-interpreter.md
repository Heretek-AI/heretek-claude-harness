---
title: "Encrypted-VM Bytecode Interpreter (Unity IL2CPP target)"
category: "anti-analysis"
platforms: ["windows"]
difficulty: "advanced"
tags: ["vm-protection", "obfuscation", "unity", "il2cpp", "static-analysis", "protection"]
summary: "The observable composition of a register-based bytecode VM that has replaced the binary's real x86 code — section names, W^X .idata, lazy-decrypt entry stub, late-bound export tail, and HWID-vector imports — and the order to triage them in."
updated: "2026-06-06"
related: ["anti-analysis/01-anti-debug", "anti-analysis/07-vm-bytecode-proprietary", "native/02-pe-section-layout", "tools/01-ghidra"]
---

## Summary

An encrypted-VM bytecode interpreter replaces the binary's real x86 code with a register-based virtual machine. A dispatcher fetches handlers from a table; the original code never executes as x86. The recognition signal is not a single feature but a 7-observable composition that fires together — section-name regexes, a W^X (write+execute) giant code-bearing section, a packed-shape `.text`, a tiny entry stub at the PE entry point, a vendor-tagged PDB reference, a late-bound export tail, and an unusually large HWID-vector import set.

## Why this matters

When this composition fires, every static analysis technique that targets the binary's *code* gives the wrong answer: the disassembled function prologues are not the game's code, they are the VM runtime's stub. Decompilation produces noise. Function-boundary recovery produces noise. String extraction over the bytecode sections wastes hours and gigabytes of memory on a payload that is opaque by design.

Three common analyst traps:

- **Spending an hour on a function that turns out to be a handler.** The handler calls a 97-byte trampoline; the trampoline is in a section named `.ecode`; everything above it is the encrypted bytecode.
- **Running `strings` on a 470 MB `.idata` and OOMing.** The bytecode region is dense random-looking data, and a naive strings pass will try to allocate it all at once.
- **Assuming a "no symbols" Unity game is just stripped.** An encrypted-VM bytecode interpreter has the *symbols of the VM runtime*, not the game's. Both look like a stripped binary from the outside; the section shape is what disambiguates.

## Mechanics

The 7-observable composition, in **triage order** (cheapest to most expensive). When 4+ of these fire together, the category is the encrypted-VM bytecode interpreter.

### 1. Section names matching the encrypted-VM family

The PE's section table contains at least four of the seven section-name regexes:

```
\.xtls
\.didata
\.ecode
\.xdata
\.xpdata
\.udata
\.00cfg
```

These are well-known section names that this category uses as containers. The full set is diagnostic; fewer than four is suggestive but not conclusive. The section *names* in the binary are easy to grep for, so this is the cheapest first-pass check.

### 2. W^X on a giant code-bearing section

The largest code-bearing section has R + W + X permissions simultaneously. In PE characteristics:

- `MEM_READ` = 0x40000000
- `MEM_WRITE` = 0x80000000
- `MEM_EXECUTE` = 0x20000000

A 100+ MB `.idata` with all three of those bits set (plus `CNT_CODE`) is the canonical example. The "writable + executable" combination on a section that holds the bulk of the binary's content is the headline signal.

### 3. `.text` with `virtual_size >> raw_size`

The canonical `.text` section has `virtual_size` (in-memory size) much larger than `raw_size` (on-disk size) — 2.2 MB virtual vs 512 raw is a common shape. The loader zero-fills the gap at load time. This is the "large section with tiny text" packed-shape rule, and it indicates the on-disk bytes are stubs that the runtime expands.

### 4. A tiny `.ecode` entry stub

A small (under 200 bytes) section named `.ecode` sits at the PE entry point. It contains a lazy-decrypt routine — typically a 2-instruction page-stride loop that fills a key/material block on first call, gated by a one-byte "done" flag. Disassembling the entry point shows the stub; everything after the first `jmp` out of the stub is the encrypted bytecode.

The stub pattern:

```
; Pseudo-disassembly of a typical .ecode stub
push rax; push rcx; push rdx
cmp byte [done_flag], 0
jne .skip_decrypt
.loop:
    mov rdx, [page_ptr]
    ; ... transform rdx ...
    add page_ptr, 0x1000
    cmp page_ptr, end_ptr
    jl .loop
mov byte [done_flag], 1
.skip_decrypt:
pop rdx; pop rcx; pop rax
jmp vm_entry                ; jumps to the real interpreter entry
```

The exact instructions vary, but the shape — three pushes, a flag check, a page-stride loop, a flag set, the inverse teardown, a `jmp` out — is stable.

### 5. Vendor-tagged PDB reference

The PE debug directory references a PDB filename that embeds a name fragment not matching the binary's own basename. The literal string in the COFF debug directory is the easy signal. Vendor-neutral translation: *any* non-matching tag in the PDB reference is the indicator. (The exact product name is the user's call to make, not the corpus's.)

### 6. Late-bound export tail

The exports table ends with a single late-bound entry — a stub the game calls *after* the encrypted-VM bytecode interpreter is initialized. The name typically suggests "wait" or "activation" (e.g. an `WaitForActivation` export). The interpreter is "armed but inert" until this export returns. If your dynamic instrumentation skips the call, the binary may not exhibit the protected behaviour you expect.

### 7. 8+ of the 12 HWID-vector APIs imported

The import table shows 8 or more of the 12 high-signal HWID APIs:

```
CryptAcquireContextW, CryptGenRandom, GetUserNameW, GetComputerNameW,
GetVolumeInformationW, GetAdaptersInfo, GetAdaptersAddresses,
NtQuerySystemInformation, NtQuerySystemInformationEx,
NtQueryInformationProcess, ...
```

The fingerprint-vector set is unusual for a non-protected Unity IL2CPP game. Eight or more of the twelve is the static threshold.

## Approach

1. **Section list first** (cheapest; identifies the category-shape). If 4+ of the 7 section names fire, you are looking at this category.
2. **Imports check** — `re-lief.get_imports_exports` (or `re-rizin.list_imports_exports`). The 8+ HWID APIs confirm. `re-lief.categorize_strings` is the keyword-bucketed equivalent; the `obfuscation` and `hwid` buckets fire on the same data.
3. **Entry-point disassembly** of `.ecode` — `re-lief.disasm_capstone` or `re-rizin.disassemble_function`. The 2-instruction lazy-decrypt stub is the signature.
4. **String search for VM-dispatch markers** — the `obfuscation` bucket from `categorize_strings` should have hits on `dispatch`, `handler`, `vm_entry`, `lookup`.
5. **Do not decompile the entire bytecode section.** The `skip_sections` parameter on `re-lief.categorize_strings` keeps the memory footprint bounded. The encrypted bytecode is opaque by construction; the *control-flow surface* (the table-driven dispatcher) is the analyzable artifact.

## Variants

The Unity-IL2CPP variant described above is the most widely shipped. A second, distinct variant exists in proprietary engines (often AAA cross-platform titles) — the same conceptual category (encrypted-VM bytecode interpreter) with a different observable composition. The proprietary variant is documented in [`07-vm-bytecode-proprietary`](../07-vm-bytecode-proprietary.md) and complements this entry; the table below summarises the differences so a reader scanning both can spot which variant they're looking at.

| Signal | Unity-IL2CPP (this entry) | Proprietary-engine ([`07`](../07-vm-bytecode-proprietary.md)) |
|---|---|---|
| Section set (encrypted-VM containers) | `.xtls` `.didata` `.ecode` `.xdata` `.xpdata` `.udata` `.00cfg` | `.arch` `.xcode` `.xtext` `.sbss` `.link` |
| W^X giant code-bearing section | Yes — `.idata` is often 100+ MB with R+W+X | **No** — bytecode lives in custom sections, not the canonical `.idata` |
| `.text` with `virtual_size >> raw_size` | Yes — the lazy-decrypt stub at the entry point | No — `.text` is normal; the entry is a real CRT prologue + a branchless dispatcher |
| Entry-stub shape | 2-instruction page-stride loop in `.ecode` (3 pushes, flag check, page loop, flag set, 3 pops, `jmp`) | A single `cmova r8, rbx` (or `cmo*` family) followed by an indirect `jmp` into the dispatch table — no lazy-decrypt loop |
| Encrypted VM context location | The `.idata` / `.xtls` / etc. code-bearing section | A `.bss`-shaped section with entropy > 7.0 (BSS that isn't BSS) |
| PDB reference suffix | Typically matches the binary's own basename | A code-integrity module name (`shielding.pdb`, `guard.pdb`, `integrity.pdb`) |
| Launcher activation library | Often co-located, separate layer | Often co-located, separate layer |

The two variants can coexist in the same binary (an IL2CPP-style entry that dispatches into a proprietary-engine VM context). Treat the entries as *complementary*, not competing.

## Common pitfalls

- **Assuming "no symbols" means "stripped".** An encrypted-VM bytecode interpreter has the symbols of the VM runtime, not the game's. Both look like a stripped binary from the outside; the section shape is the disambiguator.
- **Decompiling the bytecode section end-to-end.** The disassembled instructions are encrypted handlers, not game logic. Decompile the *dispatcher* and a small sample of *handlers*, not the whole section.
- **Treating the late-bound entry-point stub as decorative.** It is the handshake with the license server. The interpreter is "armed but inert" until that export returns; if your dynamic instrumentation skips the call, the binary may not exhibit the protected behaviour you expect.
- **Memory blow-up on `strings`.** The `re-lief.categorize_strings` `skip_sections` parameter exists for this case; use it.

## Tooling pointers

- [`ghidra`](../tools/01-ghidra.md) — static analysis; decompile the dispatcher and a small sample of handlers.
- [`re-lief.get_sections`](https://github.com/Heretek-AI/RE-AI) — canonical accessor for the section table.
- [`re-lief.categorize_strings`](https://github.com/Heretek-AI/RE-AI) — keyword-bucketed strings dump; pass `skip_sections=[".idata", ".xtls", ".xpdata", ".udata", ".xdata", ".didata", ".ecode", ".00cfg"]` to skip the encrypted-VM bytecode regions on a 500+ MB binary.
- [`re-rizin.list_imports_exports`](https://github.com/Heretek-AI/RE-AI) — for the 8+ HWID API confirmation.
- [`re-rizin.disassemble_function`](https://github.com/Heretek-AI/RE-AI) — for the entry-stub disassembly.
- [`native/02-pe-section-layout`](../native/02-pe-section-layout.md) — primer on the PE section table that this entry depends on.

## References

- [RE-AI: ANTI-TAMPER-TAXONOMY.md](https://github.com/Heretek-AI/RE-AI/blob/main/ANTI-TAMPER-TAXONOMY.md) — "Recognizing the patterns in arbitrary binaries" section.
- [Microsoft PE/COFF specification](https://learn.microsoft.com/en-us/windows/win32/debug/pe-format) — for the section characteristics bits and the debug directory.
- [Wine PE documentation](https://wiki.winehq.org/PE_Format) — a readable summary of the same format.
