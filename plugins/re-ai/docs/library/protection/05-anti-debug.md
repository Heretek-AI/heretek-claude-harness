# Anti-debug

**Pattern:** Cross-cutting observation in the per-target analysis (the v2.9.0 stress test's per-binary anti_analysis JSON files all carry the same anti-analysis primitive counts).

## Status

**Placeholder.** VM-protected targets typically show:
- 200+ RDTSC matches (timing-trap)
- 200+ INT 2D / INT 3 matches (kernel debug exception + INT3)
- 200+ CPUID matches (VM detection)
- 200+ VMXON matches (hypervisor detection)
- 200+ INVD matches (emulator detection)
- 27-36 VMCALLs (hypervisor call)

IL2CPP launchers are typically clean at the launcher layer (the protection is in `GameAssembly.dll`, not the launcher).

## Detection

- `re-anti-analysis.scan_anti_analysis_primitives` returns per-primitive byte-hit counts
- `re-hypervisor-detect.classify_hypervisor_posture` returns "kernel-active" for the 4 VM targets
- `re-leak-scan` does not apply to anti-debug (no telemetry aspect)

## Cross-references

- RE-AI `ANTI-TAMPER-TAXONOMY.md` Pattern B
- See the RE-AI output directory for per-binary triage data. (the per-target anti-analysis data)
- RE-AI `servers/re-anti-analysis/` (the byte-sequence scanner)
- RE-AI `servers/re-hypervisor-detect/` (the posture classifier)
