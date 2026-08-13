# Pattern A-VMT — encrypted-VM handler-table dispatch (proprietary-engine variant)

**v2.9.1+ canonical entry.** This is the vendor-named companion to RE-AI's `ANTI-TAMPER-TAXONOMY.md` Pattern A-VMT. The empirical case is a handler-table-dispatch engine in a representative target binary.

## Architecture (canonical BlackSpace example)

The `.xcode` section has TWO sub-regimes (the diagnostic differentiator from Pattern A / A-DW):

- **Dispatch table** (192KB low-entropy 3.4-3.7): 36+ 16-byte big-endian entries
- **Encrypted metadata** (3.2MB high-entropy 6.3-7.2)

Handler targets point into `.link` where file bytes are zero (runtime-decrypted BSS). Handler implementations live in `.arch` (statically linked OpenSSL: AES-NI, SHA-512, Vector Permutation AES — 4012 crypto strings).

This is NOT a traditional bytecode interpreter. There is no per-instruction fetch+decode+dispatch loop in `.xcode`. Pattern A-VMT does not require a lifter to read the handlers; it requires a runtime trace to map handler IDs to call sites.

## Observable composition (6 items, any 4 = strong signal)

1. Section table contains `.arch` + `.link` + `.xcode` + `.xtext` + `.sbss` + `.rodata` (Pattern C's section set + a large `.rodata`).
2. The `.xcode` section has TWO sub-regimes: low-entropy head + high-entropy continuation at offset ~0x32000.
3. Dispatch-table handler IDs in range 0x01-0x55 with reserved-slot gaps; 16 < entry count < 256.
4. Handler targets point into `.link` where file bytes are zero (runtime-decrypted BSS).
5. The `.arch` section (50-100 MB) statically links a recognizable crypto library.
6. `mcp__re-lief__get_debug_directory` POGO check returns *no* POGO entry (distinguishing from Pattern A-DW).

## Differentiators

- vs Pattern A (Unity IL2CPP): no `GameAssembly.dll` sibling, no `.xtls` family
- vs Pattern A-DW (UE5 + Denuvo): no POGO entry, no `.trace` section
- vs Pattern C (proprietary-engine, encrypted body in `.rodata` only): Pattern A-VMT has the explicit dispatch table in `.xcode`

## Detection (RE-AI tools)

- `re-lief.classify_native_protection` returns `protection_class: "encrypted-vm-handler-table-dispatch"` when the section set + dual-entropy signature fires
- `re-lief.get_sections` shows the section set
- `re-anti-analysis.scan_anti_analysis_primitives` reports the kernel-active posture

## Empirical case

- Representative binary — handler-table-dispatch A-VMT case
  - See `publishers/pearl-abyss/crimson-desert/`
  - See `engines/blackspace-engine/`
  - Source data: `RE-AI/See the RE-AI output directory.

## v3 project input

Pattern A-VMT is one of TWO distinct VM architectures the v3 "restore original x86" project must handle. The other is Denuvo ATD (Pattern A-DW). See `RE-AI/ANTI-TAMPER-TAXONOMY.md` Pattern A-DW for the sibling.

## Cross-references

- RE-AI `ANTI-TAMPER-TAXONOMY.md` Pattern A-VMT
- See the RE-AI output directory for per-binary triage data. (canonical source)
- RE-AI `servers/re-lief/src/re_lief/protection_catalog.py` `_classify_avmt_signature` (the v2.9.1+ classifier)
- RE-UNLEASHED `publishers/pearl-abyss/crimson-desert/`
- RE-UNLEASHED `engines/blackspace-engine/`
