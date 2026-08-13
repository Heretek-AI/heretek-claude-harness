# Pattern A — encrypted-VM bytecode interpreter (Unity IL2CPP target)

**Status:** Stable in `ANTI-TAMPER-TAXONOMY.md` since v2.7.0. Vendor-named mirror entry here for cross-publisher views.

## Architecture

The Unity IL2CPP target compiles C# to native C++ and ships a metadata file (`global-metadata.dat`) alongside the launcher. The encrypted-VM bytecode interpreter is a separate protection layer (commercial variant) that wraps the IL2CPP code in a VM. Pattern A's section set per the taxonomy doc:

- `.xtls` family (`.xtls / .didata / .ecode / .xdata / .xpdata / .udata / .00cfg`)

## Empirical cases

- Representative IL2CPP target — full IL2CPP + Steam/Origin SKUs
  - See `publishers/ea-originals/lost-in-random/`
- Representative IL2CPP target — Unity 6 (metadata v31)
  - See `publishers/sports-interactive/football-manager-26/`
- Representative IL2CPP target — metadata stripped
  - See `publishers/sunblink/hello-kitty-island-adventure/`

## Cross-references

- RE-AI `ANTI-TAMPER-TAXONOMY.md` Pattern A
- RE-AI `skills/re-il2cpp-static-triage/SKILL.md` (the workflow)
- RE-UNLEASHED `engines/unity-il2cpp/`
