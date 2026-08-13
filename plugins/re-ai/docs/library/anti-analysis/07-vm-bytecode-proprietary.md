---
title: "Encrypted-VM Bytecode Interpreter (Proprietary-Engine Target)"
category: "anti-analysis"
platforms: ["windows"]
difficulty: "advanced"
tags: ["vm-protection", "obfuscation", "proprietary-engine", "static-analysis", "protection"]
summary: "The proprietary-engine variant of the encrypted-VM bytecode interpreter — a different section set (no W^X giant code-bearing section), a branchless cmova/cmo-based dispatcher instead of the IL2CPP table-walk, an anomalous .sbss entropy signal (BSS that is encrypted VM context), and a 'shielding' PDB suffix pattern that points to a code-integrity module."
updated: "2026-06-06"
related: ["anti-analysis/02-vm-bytecode-interpreter", "anti-analysis/05-launcher-activation-fingerprinting", "anti-analysis/01-anti-debug", "native/02-pe-section-layout", "tools/01-ghidra"]
---

## Summary

The proprietary-engine variant of the encrypted-VM bytecode interpreter has a different observable composition than the Unity-IL2CPP variant in [02-vm-bytecode-interpreter](../02-vm-bytecode-interpreter.md). Where the IL2CPP variant hides the bytecode in a giant W^X `.idata` and uses a 2-instruction lazy-decrypt entry stub, the proprietary variant keeps the bytecode in a custom section set (`.arch`/`.xcode`/`.xtext`/`.sbss`/`.link`) and dispatches it via a *branchless* `cmova r8, rbx` (or `cmo` family) instead of the IL2CPP table-walk. The "encrypted VM context" lives in a section that pretends to be BSS — its entropy of 7.3-7.5 is the unique tell. The same binary can also be hosting a launcher activation library ([05](../05-launcher-activation-fingerprinting.md)); the two layers coexist.

## Why this matters

The IL2CPP variant's giant `.idata` is a *visually obvious* signal. The proprietary variant is harder to spot because the section names look like a custom (but plausible) section layout — `.arch`/`.xcode`/`.xtext`/`.sbss` aren't in any widely-shared packer / protector section-name list. A naive search for "the 7 IL2CPP section names" will miss this category entirely. The three diagnostic signals that *do* fire are:

- The branchless dispatcher at the entry point (not a table-walk).
- The `.sbss` (or "uninitialized data") section with entropy > 7.0 — BSS in a normal binary has entropy < 0.5 (zero-init memory).
- A PDB reference whose suffix is `shielding.pdb` (or similar — a code-integrity module name).

When these three fire together, the category is the proprietary-engine variant of the encrypted-VM bytecode interpreter.

## Mechanics

The 3-observable composition, in **triage order**:

### 1. The branchless `cmova` / `cmo` dispatcher at the entry point

A function at offset 0x15025c6ca (a typical entry) with a single `cmova r8, rbx` followed by a `jmp` into the dispatch table. The `cmova` selects between two VM handler pointers based on a flag — the *register state* of a recent call, not a data-driven conditional branch. The disassembly is something like:

```asm
; Pseudo-disassembly of a typical proprietary-engine entry0
push   rbp
mov    rbp, rsp
sub    rsp, 0x60
mov    rax, [rel ctx_state]
cmova  r8, rbx               ; <-- branchless dispatcher
mov    rax, [r8 + rax*8 + 0x40]
jmp    rax                    ; indirect jump into the bytecode handler
```

The shape — a single `cmova` (or `cmo*` family) followed by an indirect `jmp` — is the signature. There's no "table-walk" here: the dispatch is one indirect branch, branchless on the flag state. Static disassembly that tries to follow the indirect jump will land in the encrypted bytecode region.

### 2. The anomalous `.sbss` entropy signal

The proprietary engine's "encrypted VM context" lives in a section that *looks* like BSS (`.bss`, `.sbss`, or a custom section the linker was told was BSS-style). BSS in a normal binary has entropy < 0.5 — the loader zero-fills it at load time, so the on-disk bytes are all-zero.

The proprietary variant's "BSS" section has entropy **7.0 to 7.9** — the same range as code or compressed data. This is a *load-bearing* tell: it's the only signal that requires no parsing, just `re-lief.get_sections` + an entropy read per section.

```python
# Quick triage — entropy per section
import lief
binary = lief.parse("target.exe")
for s in binary.sections:
    h = s.entropy  # Shannon entropy of the section's on-disk bytes
    if s.name in {".bss", ".sbss"} and h > 4.0:
        print(f"  {s.name}: entropy {h:.2f}  ← BSS-shaped but high-entropy")
```

The 7.0+ entropy is the canonical Pattern C signal. (Note: `.sbss` is a C++-specific BSS variant — short for "section BSS". Some toolchains name this `.bss.sbss` or merge it into `.bss`. The signal is the same: a BSS-shaped section with high entropy.)

### 3. A "shielding" PDB reference

The PE debug directory references a PDB filename whose **suffix** is `shielding.pdb` (or similar — a code-integrity module name). The literal string in the COFF debug directory is the easy signal. Vendor-neutral translation: any non-matching tag that suggests a *code-integrity* module (the suffix contains "shield", "guard", "integrity", "code", "verify", "tamper", "license" — these are the publisher-internal naming patterns). The exact product name is the user's call to make, not the corpus's.

```python
# Quick triage — PDB suffix
import re
import lief
binary = lief.parse("target.exe")
for dbg in binary.debug_entries:
    if dbg.type == lief.PE.DebugEntry.Type.CODEVIEW:
        pdb_path = dbg.path  # e.g. "C:\\builds\\WindowsLauncher_shielding.pdb"
        suffix = pdb_path.rsplit("\\", 1)[-1]
        if re.search(r"(shield|guard|integrity|code.?verify|tamper|license)", suffix, re.I):
            print(f"  {pdb_path}  ← code-integrity PDB suffix")
```

The PDB reference itself is a literal string in the binary, so this check is one `grep` away.

## Approach

The triage workflow, in order of escalation:

1. **Section list + entropy** — `re-lief.get_sections` (per-section entropy). Identify the `.bss` / `.sbss` / custom-BSS-shaped section with entropy > 7.0. One signal: the proprietary variant is present.
2. **Entry-point disassembly** — `re-rizin.disassemble_function` (or `re-lief.disasm_capstone`) on the function at offset 0x1000 (or wherever the entry point is). Look for a `cmova`/`cmo*` + indirect `jmp` pair. Two signals: confirm.
3. **PDB reference grep** — search the COFF debug directory for a PDB whose suffix is `shielding.pdb` (or any of the code-integrity naming patterns above). Three signals: confirm.
4. **Do not decompile the encrypted VM context region** — the `.sbss`-shaped section is opaque by construction; the *dispatcher surface* (the one branchless `cmova` + indirect `jmp` per function entry) is the analyzable artifact. Lifting the dispatcher is enough to understand the VM's control flow; lifting the bytecode region is wasted effort.
5. **The encrypted-VM bytecode interpreter and the launcher activation library can coexist.** A 1-3 MB sibling DLL with ordinal-only exports + WinHTTP + OpenSSL + a high HWID-vector import set is the [launcher activation library](../05-launcher-activation-fingerprinting.md). It's a separate layer; treat it as such.

## Common pitfalls

- **Mistaking the proprietary variant for a normal binary with a custom section layout.** Custom section names are normal in C++ projects that use `__declspec(allocate)` or `-fdata-sections`. The signal is the *combination* of (a) `.bss`-shaped section with entropy > 7.0, (b) a branchless dispatcher, (c) a code-integrity PDB suffix — any one alone is suggestive, all three together is conclusive.
- **Assuming a low `.bss` entropy is a "small" binary.** BSS entropy is always low in a normal binary (zero-init memory). A high `.bss` entropy is the *diagnostic* signal, not a "this binary is compressed" signal.
- **Decompiling the `.sbss` region.** The disassembled instructions are the encrypted VM context — opaque by construction. The *dispatcher* (one `cmova` + `jmp` per entry) is what you analyze. Decompile a few hundred functions, not the whole region.
- **Treating the PDB reference as a comment.** The literal PDB string in the COFF debug directory is a high-signal string; don't ignore it. A `shielding.pdb` / `guard.pdb` / `integrity.pdb` suffix is the single most diagnostic 30-byte string in the binary.
- **The IL2CPP and proprietary variants share some surface.** Both are encrypted-VM bytecode interpreters. Both have a dispatcher at the entry point. Both have high entropy in their bytecode region. The differences are *which* section set, *which* dispatcher style, and *what* PDB suffix. Don't conflate the two.

## Tooling pointers

- [`native/02-pe-section-layout`](../native/02-pe-section-layout.md) — primer on the PE section table and the entropy signal that this entry depends on.
- [`anti-analysis/02-vm-bytecode-interpreter`](../02-vm-bytecode-interpreter.md) — the Unity-IL2CPP variant. The proprietary variant complements it; together they cover the two observable compositions in the wild.
- [`anti-analysis/05-launcher-activation-fingerprinting`](../05-launcher-activation-fingerprinting.md) — the launcher activation library that often sits alongside the encrypted-VM bytecode interpreter in the same install. Different layer; different observable composition.
- [`anti-analysis/01-anti-debug`](../01-anti-debug.md) — the anti-debug surface (split between the activation library and the game DLL).
- [`ghidra`](../tools/01-ghidra.md) — for static analysis; decompile the dispatcher, not the bytecode region.
- `re-lief.get_sections` (via [RE-AI](https://github.com/Heretek-AI/RE-AI)) — per-section entropy read.
- `re-rizin.disassemble_function` (via [RE-AI](https://github.com/Heretek-AI/RE-AI)) — for the entry-point disassembly.
- `re-rizin.search_bytes` (via [RE-AI](https://github.com/Heretek-AI/RE-AI)) — to grep for the PDB-suffix string `shielding.pdb` (or your preferred code-integrity naming pattern).

## References

- [RE-AI: ANTI-TAMPER-TAXONOMY.md](https://github.com/Heretek-AI/RE-AI/blob/main/ANTI-TAMPER-TAXONOMY.md) — "Recognizing the patterns in arbitrary binaries" section, the Pattern C (proprietary-engine variant) fire rule.
- [RE-AI: data/drm-indicators.yaml](https://github.com/Heretek-AI/RE-AI/blob/main/data/drm-indicators.yaml) — the catalog; this entry is the prose form of the `section_indicators` rules for the proprietary variant.
- [Microsoft PE/COFF specification](https://learn.microsoft.com/en-us/windows/win32/debug/pe-format) — for the section characteristics and the debug directory.
- [Shannon entropy on bytes](https://en.wikipedia.org/wiki/Entropy_(information_theory)) — for the entropy signal in section 2.
