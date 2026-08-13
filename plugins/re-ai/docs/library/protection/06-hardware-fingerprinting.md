# Hardware fingerprinting

**Pattern:** Pattern B in `ANTI-TAMPER-TAXONOMY.md`

## Status

**Placeholder.** The stress test's per-target string categorization calls populated the `hwid` bucket for several VM-protected targets. A deep hardware-fingerprinting analysis is deferred to a follow-up cycle.

## Detection

- `re-lief.categorize_strings` populates the `hwid` bucket with calls to:
  - `GetAdaptersInfo` / `GetAdaptersAddresses` (network adapter MAC)
  - `GetUserName` / `GetComputerName` (host identity)
  - SMBIOS / WMI reads (hardware serial)
  - CPUID-based host fingerprinting
- `re-leak-scan.find_secrets` can correlate the binary with known HWID-collection patterns

## Cross-references

- RE-AI `ANTI-TAMPER-TAXONOMY.md` Pattern B
- See the RE-AI output directory for per-binary triage data. (A representative target has 7 hwid strings)
- RE-AI `skills/re-drm-fingerprint/SKILL.md`
