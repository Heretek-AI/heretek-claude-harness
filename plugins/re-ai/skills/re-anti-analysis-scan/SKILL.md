---
name: re-anti-analysis-scan
description: Detect the anti-analysis primitive surface of a target binary (anti-debug + anti-VM + anti-sandbox + memory-integrity + code-integrity + process-introspection). Use when the user asks "does this binary have anti-debug / anti-VM / anti-sandbox?", "what anti-RE primitives did the packer install?", or hands the analyst an unknown protected binary. Calls re-anti-analysis.scan_anti_analysis_primitives + re-anti-analysis.classify_native_protection + re-anti-analysis.correlate_anti_patterns, then walks the analyst through the matched primitives and offers an optional re-patch NOP-out for selected hits under the override-scope contract. Does not auto-bypass; the analyst reviews each hit.
---

# Anti-Analysis Primitive Scan

## When to use

Use this skill when the user asks "does this binary
have anti-debug / anti-VM / anti-sandbox?" or hands
the analyst an unknown protected binary. The skill
combines three passes:

1. **String-table pass** — `re-anti-analysis
   .scan_anti_analysis_primitives` (via
   `re-lief.protection_catalog`).
2. **Disasm pass** — RDTSC = `0F 31`, INT 2D = `CD 2D`,
   INT 3 = `CC`, CPUID = `0F A2`, VMXON = `0F C7`,
   VMCALL = `0F 01 C1`.
3. **Section-table pass** — `re-anti-analysis
   .classify_native_protection` (via
   `re-lief.protection_catalog`).

The output is a per-category primitive list +
a cross-section correlation score (categories that
fire in both string-table and disasm are stronger
signals than categories that fire in just one).

## What this skill returns

1. **String-table matches** — per-category, per-primitive
   hits with offset + section.
2. **Disasm matches** — per-primitive byte-sequence
   hits with address.
3. **Section-table classification** —
   ``plain-pe``, ``packer-stub-wrapped``,
   ``vm-bytecoded-pe``, ``encrypted-vm-bytecode-interpreter``,
   ``il2cpp-runtime``, ``anti-debug-wrapped``,
   ``unpacked-debug-pe``.
4. **Correlation score** — categories that fired
   in both passes.
5. **Optional runtime-trap recipe** — when the
   analyst wants to confirm a primitive at runtime,
   the skill surfaces the re-winedbg / re-frida
   recipe from `re-anti-analysis
   .suggest_runtime_trap`.

## What this skill does NOT do

- **Does not auto-bypass.** The skill offers the
  ``re-patch.apply_patch`` primitive (under the
  override-scope contract from `CLAUDE.md`) but
  the analyst applies the patch manually.
- **Does not name specific commercial
  anti-tamper / VM-pack products.** Categories
  only.
- **Does not crack encrypted-VM bytecode strings.**
  The string-table pass is a static read; the
  analyst uses a dynamic trace to recover
  runtime-decrypted strings, then re-runs the
  skill against the recovered strings.

## Workflow

**Step 1 — String-table pass (parallel-safe)**

```
re-anti-analysis.scan_anti_analysis_primitives(path=binary_path)
```

Returns the per-category matches.

**Step 2 — Section-table classification (parallel-safe)**

```
re-anti-analysis.classify_native_protection(path=binary_path)
```

Returns the protection_class label + the evidence.

**Step 3 — Cross-section correlation (parallel-safe)**

```
re-anti-analysis.correlate_anti_patterns(path=binary_path)
```

Returns the correlation_score (count of categories
that fired in both passes).

**Step 4 — Runtime confirmation (optional)**

For primitives the analyst wants to confirm at
runtime:

```
re-anti-analysis.suggest_runtime_trap(target_path=binary_path, primitive="RDTSC")
```

Returns the recipe (which re-winedbg / re-frida
tool, which breakpoint, which register to read).
The analyst applies the recipe manually.

**Step 5 — Optional NOP-out (override-scope)**

For primitives the analyst wants to neutralise,
the skill offers ``re-patch.apply_patch``. The
override-scope contract from `CLAUDE.md` is the
gatekeeper: the patch is written to
`Output/<run-id>/patches/`, never to the
on-disk binary.

## Output report format

```markdown
# Anti-Analysis Primitive Scan — <path>

## Protection class
encrypted-vm-bytecode-interpreter

## String-table matches
- anti_debug: 12 (IsDebuggerPresent, NtQueryInformationProcess, ...)
- process_introspection: 6 (NtQuerySystemInformation, EnumProcessModules, ...)
- anti_vm: 4 (CPUID, VBOX, VMware, ...)

## Disasm matches
- RDTSC: 47 hits
- INT 2D: 3 hits
- CPUID: 18 hits
- VMXON: 2 hits

## Correlation
anti_debug: fired in both string-table + disasm
process_introspection: fired in both
anti_vm: fired in both
correlation_score: 3

## Runtime confirmation (optional)
[analyst-applied recipes]

## NOP-out plan (optional)
[override-scope contract required]
```

## Pairing with other skills

- `re-static-triage` — for the broader binary
  triage. The triage's import list is a useful
  cross-reference for the anti-analysis scan.
- `re-encrypted-vm-tamper` — when the binary has
  encrypted-VM bytecode protection. The encrypted
  string regions are not visible to this scan.
- `re-vm-reverse` — for the deeper VM-pack
  analysis. The 6-stage lift feeds into this
  skill's `anti_debug` + `process_introspection`
  findings.
