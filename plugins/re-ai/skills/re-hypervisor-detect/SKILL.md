---
name: re-hypervisor-detect
description: Detect the hypervisor-detection primitive surface of a target binary. Use when the analyst suspects a target installs or defeats a hypervisor (anti-cheat, anti-RE, custom packer). Walks a category-by-category decision tree: CPUID-leaf probes, VMX/EPT detection, TSC skew checks, registry/file/mac/SMBIOS/ACPI probes. Each category is observed via re-lief.categorize_strings plus re-hypervisor-detect static primitives plus re-winedbg single-step on a controlled guest. Categories only — never names a specific commercial hypervisor or product.
---

# Hypervisor-Detection Primitive Scan

## When to use

Use this skill when the analyst suspects a target
binary installs or defeats a hypervisor. Common
triggers:

- The binary is an anti-cheat or anti-RE tool.
- The binary is a custom VM-pack that uses
  hypervisor-mode execution to hide its
  dispatcher.
- The user names the binary as "checking for
  VMs" or "hardened against sandbox".

The skill walks a category-by-category decision
tree and reports the posture. Categories only.

## What this skill returns

1. **CPUID-leaf probe count** — the number of
   ``0F A2`` opcodes in the .text section +
   the inferred leaf number for each.
2. **VMX / EPT probe count** — the number of
   ``0F C7`` (VMXON) / ``0F 01 C1`` (VMCALL) /
   ``0F 01 82`` (INVEPT) opcodes.
3. **TSC skew probe count** — the number of
   ``0F 31`` (RDTSC) opcodes.
4. **SMBIOS / ACPI keyword presence** — the
   string-table hits for the canonical probe
   strings.
5. **Registry-probe keyword presence** — the
   string-table hits for the canonical
   VM-detection registry keys.
6. **Hypervisor posture classification** —
   ``no-probes``, ``static-probes-only``,
   ``runtime-probes``, ``rich-runtime``,
   ``kernel-active``.

## What this skill does NOT do

- **Does not auto-bypass.** The skill reports
  the surface; the analyst decides what to
  bypass.
- **Does not name specific commercial
  hypervisor / VM-detection products.**
  Categories only.
- **Does not require a live hypervisor.** The
  static pass works against a dead binary.
  The runtime pass (RDTSC timing, CPUID
  measurement) is optional; the analyst runs
  it under re-winedbg when needed.

## Workflow

**Step 1 — CPUID leaf probe (parallel-safe)**

```
re-hypervisor-detect.cpu_id_leaf_probe(path=binary_path)
```

Returns the leaf list + per-leaf category.

**Step 2 — VMX / EPT probe (parallel-safe)**

```
re-hypervisor-detect.vmx_ept_probe(path=binary_path)
```

Returns the VMXON / VMCALL / INVEPT / INVVPID
hit list.

**Step 3 — TSC skew probe (parallel-safe)**

```
re-hypervisor-detect.tsc_skew_measure(path=binary_path)
```

Returns the RDTSC count.

**Step 4 — SMBIOS / ACPI probe (parallel-safe)**

```
re-hypervisor-detect.smbios_probe(path=binary_path)
```

Returns the keyword hit list.

**Step 5 — Registry probe (parallel-safe)**

```
re-hypervisor-detect.registry_probe(path=binary_path)
```

Returns the keyword hit list.

**Step 6 — Posture classification**

```
re-hypervisor-detect.classify_hypervisor_posture(path=binary_path)
```

Returns the posture label + the per-probe counts.

**Step 7 — Runtime confirmation (optional)**

For binaries with high leaf counts, the analyst
confirms at runtime under re-winedbg:

```
re-winedbg.run_to_breakpoint(session=wine_session, target="*<CPUID_addr>")
re-winedbg.read_registers(session=wine_session)
```

The register read after the CPUID confirms
ECX bit 31 (the hypervisor-present bit).

## Output report format

```markdown
# Hypervisor-Detection Primitive Scan — <path>

## CPUID leaves
- 1: hypervisor-present (4 hits)
- 0x40000000: hypervisor-vendor (2 hits)
- 0x40000100: misc (1 hit)

## VMX / EPT
- VMXON: 2 hits
- VMCALL: 1 hit
- INVEPT: 0 hits

## TSC skew
- RDTSC: 47 hits

## SMBIOS / ACPI
- SMBIOS keyword: 1 hit
- ACPI keyword: 2 hits

## Registry
- HKLM\SOFTWARE keyword: 1 hit
- MachineGuid: 1 hit

## Posture
runtime-probes (CPUID + RDTSC + ACPI; no VMXON)

## Runtime confirmation
- re-winedbg run on <binary>: ECX bit 31 = 0 (no hypervisor)
```

## Pairing with other skills

- `re-anti-analysis-scan` — the broader
  anti-analysis primitive surface. The
  hypervisor-detection scan is a subset.
- `re-encrypted-vm-tamper` — for binaries that
  have encrypted-VM bytecode protection. The
  hypervisor-detection scan is a *first-pass*
  signal; the encrypted-VM stack is the
  deeper analysis.
- `re-winedbg` — for the runtime confirmation
  under Wine.
- `re-static-triage` — for the broader binary
  triage. Pair with the import / section
  surface.
