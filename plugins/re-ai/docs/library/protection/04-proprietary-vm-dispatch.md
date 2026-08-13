# Pattern C — proprietary-engine encrypted VM

**Status:** Stable in `ANTI-TAMPER-TAXONOMY.md` since v2.7.0. Vendor-named mirror entry here.

## Architecture

The proprietary-engine category: a game studio's own engine ships its own encrypted-VM protection (no third-party ATD wrapping). Examples:
- Proprietary engine with dispatcher-table architecture (refined to Pattern A-VMT in the taxonomy)
- Proprietary engine with encrypted-VM-style section layout
- Custom game engine with light encrypted-VM variant

The Pattern C section set is a superset of the encrypted-VM family but lacks the specific ATD signals (POGO entry, .trace).

## Empirical cases

- Representative target — proprietary engine (refined to Pattern A-VMT)
- Representative target — proprietary engine (encrypted-VM-style sections)
- Representative target — custom game engine (light variant)

## Cross-references

- RE-AI `ANTI-TAMPER-TAXONOMY.md` Pattern C
- See the RE-AI output directory for per-binary triage data.
- RE-UNLEASHED `engines/`
