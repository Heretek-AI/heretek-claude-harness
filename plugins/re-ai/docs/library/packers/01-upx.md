---
title: "UPX Packing"
category: "packers"
platforms: ["linux", "windows", "macos"]
difficulty: "beginner"
tags: ["unpacking", "static-analysis", "tools"]
summary: "Detecting and unpacking the UPX packer — recognising the headers, the one-shot decompression, and how to recover the original entry point and import table without breaking the binary."
updated: "2026-06-04"
related: ["packers/05-custom", "native/02-pe-section-layout", "native/01-elf-format"]
---

## Summary

UPX (Ultimate Packer for eXecutables) is the most common packer you'll encounter. It supports PE, ELF, Mach-O, and a handful of other formats. It's free, open source, and trivially reversible with the same tool that packed it — but modified UPX builds and stripped UPX sections (used by some protectors as a thin obfuscation layer) require manual work.

## Why this matters

A packed binary is unreadable: `.text` is compressed bytes, the original imports are gone, the original entry point is in a small decompressor stub. The first thing almost every static analysis workflow does is unpack. UPX is the entry point for that workflow.

## Mechanics

### Detection

UPX leaves a few telltales:

- The ASCII strings `UPX!`, `UPX 0`, `UPX! Pro`, `UPX 3` somewhere in the binary (typically in a `UPX0` / `UPX1` section pair on PE, or in the `META` / `GNU_STACK` notes on ELF).
- A `UPX!` magic in the compressed payload header.
- The section names `UPX0` and `UPX1` (PE), or a custom `upx` PT_LOAD segment (ELF).
- The original `.text` / `.data` replaced with compressed bytes; `UPX0` is usually zero-sized (it'll be re-filled at runtime), `UPX1` is the compressed data plus the decompressor stub.

In practice, `Detect-It-Easy`, `exeinfo PE`, and `trid` all flag UPX correctly. `strings target | grep UPX` is the lazy-but-effective check.

### The structure of a UPX-packed PE

A packed PE looks like this in sections:

```
UPX0    empty (will be decompressed into here at runtime)
UPX1    compressed .text + .rdata + decompressor stub
.rsrc   often preserved
```

The entry point is at the start of the decompressor stub inside `UPX1`. The stub calls `VirtualProtect` to make `UPX0` writable+executable, then walks the compressed payload (its own length and location are stored in a small header at the end of `UPX1`), decompresses, fixes the import table, and jumps to the original entry point (OEP).

### The structure of a packed ELF

For ELF, UPX overwrites the `PT_LOAD` segments: there is usually one large `PT_LOAD` with the decompressor and a separate region that holds the compressed payload, plus a `PT_LOAD` for the unpacked base. The dynamic section (`PT_DYNAMIC`) is preserved so the loader can still process the file, but the `.text` and `.dynsym` are gone.

### The structure of a packed Mach-O

Mach-O is similar; the original `LC_SEGMENT_64` is replaced with a single segment containing the decompressor and the compressed payload. The `LC_LOAD_DYLIB` commands are preserved, so the loader handles the binary, but the executable code and data are in a blob.

## Approach

### 1. Try the easy path first

```bash
upx -d target.bin -o target.unpacked
```

This works in maybe 70% of cases. It fails when:
- The UPX magic was stripped or modified (some protectors do this).
- The binary has a non-standard UPX version that the installed `upx` doesn't recognise.
- The binary has been tampered with after packing (e.g. encrypted headers).

If `upx -d` works, you're done. Verify the unpacked binary still runs and that imports are resolved (e.g. with `Imports` of `die`, or `objdump -R` for ELF relocations).

### 2. For modified UPX: emulate the decompressor

Run the binary under unicorn, dump the decompressed image, fix the entry point, fix the imports, and write the result back. This is the "I want the original binary" path. Tools that automate this:

- [`unipacker`](https://github.com/unipacker/unipacker) — for several packers including UPX.
- [`flare-capa`](https://github.com/mandiant/capa) — for static analysis after unpacking.
- `Cuckoo Sandbox` — for dynamic unpacking (run, dump, recover).

### 3. For deeper analysis: dump at OEP

Run the binary under a debugger, set a breakpoint on the jump to OEP, and dump the process memory. The trick is finding the OEP:

- **Hardware breakpoint on the original entry address** — read the PE/ELF/Mach-O *before* packing, note the OEP, and HBP it post-load. With a packed sample this requires a known good header.
- **Break on `VirtualProtect` + `LoadLibraryA` / `GetProcAddress` import resolution** — after the stub has finished setting up and the import table has been resolved, the OEP is about to be called.
- **Trace `ret` instructions and look for an address that lands in a newly-executed region.** A common signature of the OEP jump is a `ret` whose return address is in the freshly-unpacked code.
- **Use a tool that detects OEP for you.** `Scylla` (Windows) is the canonical one; for ELF, [`syms2elf`](https://github.com/mstczuo/syms2elf) and `r2dec` plugins can recover symbols from a live process.

### 4. For a stripped UPX: reconstruct manually

This is the worst case. You'll see a custom decompressor, no `UPX!` strings, possibly with the section names renamed. Identify the loop that copies and decompresses bytes (look for tight loops with LZ-decompressor signatures: short match-length reads, dictionary lookups, big switch tables). Dump the output of that loop and you've got the unpacked `.text`.

## Common pitfalls

- **Assuming `upx -d` failed means it's not UPX.** Modified UPX is very common. Check the *behaviour* — a small entry point that calls `VirtualProtect` and then jumps far is the giveaway, not the magic.
- **Re-running the unpacked binary in a sandbox without re-fixing imports.** The `upx -d` output runs, but the import table is sometimes only resolved for specific Windows versions. Always verify with `dumpbin /imports` or `objdump -p`.
- **Forgetting that the original timestamps in the PE header are *packed-time*, not *build-time*.** A binary packed in 2020 may have a 1995 timestamp from the original. Use the unpacked binary's timestamp for any forensic timeline.
- **Confusing the OEP with the section's start address.** The OEP is an RVA, not a section boundary. Many tools report the wrong one.
- **Treating the decompressor stub as "just dead code".** It often contains anti-debug, anti-VM, and other checks that fire *before* unpacking. If your sandbox can't get past the stub, you'll never see the real binary.

## Tooling pointers

- `upx -d` — the official tool. `upx --version` to see what formats you have.
- [`ghidra`](../tools/01-ghidra.md) — for the manual reconstruction path; the decompiler can recognise the LZ77-style loops that UPX uses.
- [`binary-ninja`](../tools/03-binary-ninja.md) — same, with better scriptability for the analysis loop.
- `Detect-It-Easy` (DIE) — packer/compiler detection.
- `Scylla` (Windows) — OEP detection, import reconstruction, memory dumping.
- For Mach-O: `dsc_extractor` and `jtool` to verify the unpacked output.

## References

- [UPX source code and docs](https://github.com/upx/upx) — the canonical reference for the headers and format.
- [PE Format (Microsoft docs)](https://learn.microsoft.com/en-us/windows/win32/debug/pe-format) — for the import table reconstruction.
- [ELF Format (System V ABI)](https://refspecs.linuxfoundation.org/elf/gabi4+/contents.html) — for the PT_LOAD layout.
