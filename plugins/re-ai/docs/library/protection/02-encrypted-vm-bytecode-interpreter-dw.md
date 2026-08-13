# Pattern A-DW — encrypted-VM bytecode interpreter (UE5 + third-party ATD)

**Status:** Stable in `ANTI-TAMPER-TAXONOMY.md` since v2.9.0 (the v2.9.0 WS-30 addition). Vendor-named mirror entry here.

## Architecture

The third-party-ATD-wrapped UE5 variant: a third-party anti-tamper layer (Denuvo ATD being the canonical case) wraps the UE5 binary with an encrypted-VM bytecode interpreter. Section set per the taxonomy doc:

- `.text / .rdata / .arch / .xcode / .xtext / .xtls / .trace`

The `-DW` suffix = A-DenuvoWrapped (project-internal mnemonic), not a vendor name. The differentiator from Pattern A is the section set: Pattern A has `.xtls / .didata / .ecode / .xdata / .xpdata / .udata / .00cfg`; Pattern A-DW has `.text / .rdata / .arch / .xcode / .xtext / .xtls / .trace`. The two sets are disjoint (no overlap except `.xtls` + `.xpdata`); the section table is the deciding signal.

## Detection

- `re-lief.classify_native_protection` returns `encrypted-vm-bytecode-interpreter` when the Pattern A-DW section set fires
- `re-lief.get_debug_directory` returns a POGO entry (kind: "POGO") — the third-party-ATD's trigger-arming metadata
- `re-rizin.search_bytes` for `denuvo` ASCII may confirm the specific ATD vendor

## Empirical cases

- Representative UE5 target — UE5 + third-party ATD confirmed
  - 3 `denuvo` string hits (see `publishers/atlus-sega/persona-3-reload/`)
  - Source data: `RE-AI/See the RE-AI output directory. (9-stage static ATD analysis)
- Representative UE5 target — Pattern A-DW-adjacent but NO third-party ATD string
  - See `publishers/io-interactive/007-first-light/`
  - Possibly a Denuvo-free IO build, OR Denuvo with the build-identifier stripped

## Cross-references

- RE-AI `ANTI-TAMPER-TAXONOMY.md` Pattern A-DW
- RE-AI See the RE-AI output directory.
- RE-AI `skills/re-drm-fingerprint/SKILL.md`
- RE-UNLEASHED `engines/unreal-engine-5/`
- RE-UNLEASHED `publishers/atlus-sega/persona-3-reload/`
