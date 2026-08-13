---
title: "PE Section Layout and W^X"
category: "native"
platforms: ["windows"]
difficulty: "intermediate"
tags: ["file-format", "pe", "static-analysis", "fundamentals", "protection"]
summary: "The PE section table — canonical section names (.text/.rdata/.data/.rsrc), the characteristics byte (R/W/X permissions, CNT_CODE, CNT_INITIALIZED_DATA), the virtual_size vs raw_size distinction, the entropy signal, and the W^X pattern that flags encrypted-VM bytecode containers and packers."
updated: "2026-06-06"
related: ["native/01-elf-format", "anti-analysis/02-vm-bytecode-interpreter", "anti-analysis/07-vm-bytecode-proprietary", "anti-analysis/05-launcher-activation-fingerprinting", "tools/01-ghidra"]
---

## Summary

The PE (Portable Executable) section table is a list of named, permissioned, sized memory regions the Windows loader maps into the process address space. Most binaries use canonical names and standard permissions; a small set of deviations from the canonical layout is the bulk of the static-detection signal for encrypted-VM bytecode interpreters, packers, and other anti-analysis wrappers. The two most informative deviations are **W^X** (a code-bearing section with read+write+execute simultaneously) and **`virtual_size >> raw_size`** (a packed-shape stub region the loader zero-fills at load time).

## Why this matters

Every static-analysis technique that works on a PE file (decompilation, function-boundary recovery, entropy visualization, W^X detection) is built on top of the section table. Misreading the section characteristics is a common analyst trap: an encrypted-VM bytecode interpreter's `.idata` can be 470 MB with R + W + X simultaneously, and a "just a large .idata" reading misses the category entirely.

The 5 minutes spent learning the section characteristics byte pays off across the rest of static analysis: every static-triage workflow on PE files starts with the section table.

## Mechanics

### Canonical section names and their roles

| Section | Typical permissions | What it holds |
|---|---|---|
| `.text` | RX | Compiled code |
| `.rdata` | R | Read-only data: string literals, vtables, const tables |
| `.data` | RW | Initialized read-write data |
| `.rsrc` | R | Resources (icons, manifests, version info) |
| `.pdata` | R | Exception tables (x64 unwind info) |
| `.reloc` | R | Base-relocation table |
| `.tls` / `.tls$` | RW | Thread-local storage (TLS callbacks live in `.tls$`) |
| `.debug` / `.debug$P` / `.debug$S` | R | Debug info (PDB data; large if PDB is embedded) |
| `.idata` | R | Import table (the "writable + executable" `.idata` is the encrypted-VM bytecode family; see below) |
| `.edata` | R | Export table |

The names are conventional but not mandatory. A compiler can use any name; tools key off the *characteristics byte*, not the name.

### Proprietary-engine encrypted-VM section set

In addition to the canonical names above, a *second* observable composition exists in some Windows binaries (typically AAA cross-platform titles using a proprietary engine) — the **proprietary-engine variant** of the encrypted-VM bytecode interpreter. The custom section set is:

| Section | Typical permissions | What it holds |
|---|---|---|
| `.arch` | R | Architecture / dispatch table (the encrypted-VM bytecode interpreter's handler table) |
| `.xcode` | RX | Encrypted bytecode + dispatch loop (the VM's code-bearing region) |
| `.xtext` | R | Encrypted strings / lookup tables (the "VM dictionary") |
| `.sbss` | RW (zero-fill expected) | **Encrypted VM context** — entropy 7.0+ (BSS that isn't BSS) |
| `.link` | R | Link table (the cross-handler jump graph) |

This is *not* a packer like UPX (which compresses the whole binary) — the proprietary engine replaces the game's code with its own VM, the same as the [Unity-IL2CPP encrypted-VM variant](../anti-analysis/02-vm-bytecode-interpreter.md), but with a different observable composition. The diagnostic signal is **the `.sbss` entropy**:

```python
# Quick triage — anomalous .bss entropy
import lief
b = lief.parse("target.exe")
for s in b.sections:
    if s.name in {".bss", ".sbss"} and s.entropy > 4.0:
        # BSS normally has entropy < 0.5 (zero-init memory).
        # 7.0+ means the section is the encrypted VM context, not BSS.
        print(f"  {s.name}: entropy {s.entropy:.2f}  ← BSS-shaped but high-entropy")
```

The proprietary variant is documented in detail in [`anti-analysis/07-vm-bytecode-proprietary`](../anti-analysis/07-vm-bytecode-proprietary.md); the Unity-IL2CPP variant is in [`anti-analysis/02-vm-bytecode-interpreter`](../anti-analysis/02-vm-bytecode-interpreter.md). Both entries share the same conceptual category (encrypted-VM bytecode interpreter) but have different observable compositions. Treat the entries as *complementary*.

### The characteristics byte

A 32-bit bitfield per section. The two most-significant groups of bits:

**Permission bits** (any combination of these three):

- `MEM_READ` = 0x40000000
- `MEM_WRITE` = 0x80000000
- `MEM_EXECUTE` = 0x20000000

**Content-class bits** (one or both):

- `CNT_CODE` = 0x00000020
- `CNT_INITIALIZED_DATA` = 0x00000040

Canonical combinations:

- `.text`: `CNT_CODE | MEM_READ | MEM_EXECUTE`
- `.rdata`: `CNT_INITIALIZED_DATA | MEM_READ`
- `.data`: `CNT_INITIALIZED_DATA | MEM_READ | MEM_WRITE`
- `.rsrc`: `CNT_INITIALIZED_DATA | MEM_READ`

The combination `MEM_READ | MEM_WRITE | MEM_EXECUTE` (W^X) on a code-bearing section (`CNT_CODE` also set) is the encrypted-VM bytecode container signal. The canonical W^X encrypted-VM shape is a 100+ MB `.idata` carrying all four bits. A 1-3 MB `.data` with `MEM_READ | MEM_WRITE` is normal and not the signal.

### `virtual_size` vs `raw_size`

Each section has two sizes:

- **`virtual_size`**: the in-memory size, the loader zero-fills the gap if `virtual_size > raw_size`.
- **`raw_size`**: the on-disk size, the number of bytes in the file.

For most sections these are equal or close. When `virtual_size >> raw_size` (e.g. 2.2 MB virtual, 512 raw), the loader zero-fills the gap at load time. This is the **"large section with tiny text"** packed-shape signal. The 512 raw bytes are a stub that the runtime expands.

A related shape: `raw_size == 0` with `virtual_size > 0`. The loader allocates memory but reads no bytes from the file. This is the empty-section pattern used by UPX (`UPX0` is raw-size 0, virtual-size > 0; it's the destination for the unpacked `.text`).

### Per-section entropy

Shannon entropy, 0.0 (all same byte) to 8.0 (random):

- Normal `.text`: 6.0-6.6 (compiled code with mixed instructions, jump tables, immediates)
- Normal `.rdata`: 4.5-5.5 (string literals, vtables)
- Normal `.data`: variable (depends on payload)
- High entropy (7.5+) on a code section: encrypted-TLS signal — the bytecode is dense, near-random-looking bytes

Per-section entropy is the cheapest static signal for "is this section encrypted or compressed?"

### Non-canonical section names by category

| Category | Section names |
|---|---|
| Encrypted-VM bytecode interpreter (Unity IL2CPP target) | `.xtls`, `.didata`, `.ecode`, `.xdata`, `.xpdata`, `.udata`, `.00cfg` |
| Encrypted-VM bytecode interpreter (alternative VM-pack family) | `.vmp0`, `.vmp1`, `.code` |
| Encrypted-VM bytecode interpreter (WinLicense-style family) | `.themida`, `.winlice` |
| Generic packer (UPX) | `.UPX0`, `.UPX1` |
| Manual / custom packing | single-character or empty section names |

The full regex list is in `data/drm-indicators.yaml::section_indicators.rules`.

### "Large section with tiny text" — the canonical packed shape

The classic packed-PE shape:

- `.text` has `virtual_size >> raw_size` (e.g. 2.2 MB virtual, 512 raw).
- A non-canonical section name holds the unpacker's code (`.UPX1`, `.vmp0`, etc.).
- The original `.text` content is gone — replaced with a stub.

This pattern alone is *strongly* suggestive of packing. Confirm with the entropy pattern (low entropy on `.text`, high entropy on the stub section) and the imports pattern (imports are often rebuilt at runtime by the unpacker).

## Approach

1. `re-lief.get_sections` returns the full table with permissions, entropy, and `virtual_size` / `raw_size` for each section.
2. Sort by entropy descending. Top-3 high-entropy sections are where you look first.
3. For any section with W^X, look up the section name against the section-name regex list. Hits confirm the category.
4. For any section with `virtual_size >> raw_size`, confirm the packed shape and skip the on-disk analysis (the loader will fill the gap).

## Common pitfalls

- **Confusing virtual size with raw size in entropy calculations.** Entropy is a per-byte statistic; use the *raw* bytes for entropy (which is what the LIEF / re-lief implementation does).
- **Trusting section names from a packed binary.** After packing, section names can be anything; rely on characteristics and entropy, not names.
- **Missing the W^X bit on a code-bearing section.** The combination of `CNT_CODE` + `MEM_EXECUTE` + `MEM_WRITE` is the headline signal for the encrypted-VM bytecode interpreter category.
- **Confusing `.rdata` entropy (which is normal at 4.5-5.5) with encrypted payload.** `.rdata` has lots of string literals; high-but-not-max entropy is normal. Only 7.5+ is the signal.
- **Ignoring the `.debug` and `.debug$P` sections.** A `.debug` section is 30+ MB in builds with full debug info. The size is a *signal* about how the binary was built (release with PDB symbols vs stripped release). The presence of `.debug$P` references a PDB file in the COFF debug directory; a non-matching tag in the PDB filename is the encrypted-VM vendor-tagged-PDB signal.
- **Treating "empty section" as a benign optimization.** Raw-size 0 with virtual-size > 0 is the unpacked-destination pattern; the binary expects the runtime to fill it.

## Tooling pointers

- [`re-lief.get_sections`](https://github.com/Heretek-AI/RE-AI) — canonical accessor for the section table.
- [`re-lief.categorize_strings`](https://github.com/Heretek-AI/RE-AI) — keyword-bucketed strings dump; pass `skip_sections=[".idata", ".xtls", ".xpdata", ".udata", ".xdata", ".didata", ".ecode", ".00cfg"]` to skip encrypted-VM bytecode regions on a 500+ MB binary.
- [`re-rizin.list_imports_exports`](https://github.com/Heretek-AI/RE-AI) — for the imports + exports surface.
- [`ghidra`](../tools/01-ghidra.md) — decompile after you've identified the category.
- [`anti-analysis/02-vm-bytecode-interpreter`](../anti-analysis/02-vm-bytecode-interpreter.md) and [`anti-analysis/05-launcher-activation-fingerprinting`](../anti-analysis/05-launcher-activation-fingerprinting.md) — for the protection-layer follow-up once the section shape is identified.

## References

- [Microsoft PE/COFF specification](https://learn.microsoft.com/en-us/windows/win32/debug/pe-format) — the canonical reference for the section table and characteristics byte.
- [Wine PE documentation](https://wiki.winehq.org/PE_Format) — a readable summary of the same format, useful for cross-checking the canonical names.
- [PE Format — section table (wiki.osdev.org)](https://wiki.osdev.org/PE) — an alternative walkthrough.
- [RE-AI: ANTI-TAMPER-TAXONOMY.md](https://github.com/Heretek-AI/RE-AI/blob/main/ANTI-TAMPER-TAXONOMY.md) — for the category vocabulary and the 7-observable composition.
