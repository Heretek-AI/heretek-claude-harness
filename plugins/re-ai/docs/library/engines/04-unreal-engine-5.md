# Unreal Engine 5 — cross-publisher view

**Publisher:** Epic Games (engine), various (games)
**Characteristics:** Encrypted-VM bytecode interpreters (protected Blueprint bytecode) + potential third-party ATD wrapping

## Headline

Unreal Engine 5 games compile to native C++ and do not have the IL2CPP metadata format. The C#/.NET reflection surface that IL2CPP depends on does not exist. The re-il2cpp walker is not applicable to UE5 binaries.

UE5 games can still carry encrypted-VM bytecode interpreters (the protected Blueprint bytecode format) and Denuvo ATD wrapping. A representative UE5 target showed the full Pattern A-DW section set with third-party ATD string hits.

## Per-game table

| Game | Pattern | Doc |
|---|---|---|
| Representative UE5 target | Pattern A-DW (third-party ATD-wrapped) | See the anti-tamper taxonomy doc |

## Cross-references

- RE-AI `ANTI-TAMPER-TAXONOMY.md` Pattern A-DW
- RE-AI See the RE-AI output directory. (9-stage static ATD analysis)
- RE-AI `skills/re-drm-fingerprint/SKILL.md`
- RE-AI `servers/re-lief/src/re_lief/parsers.py` `get_debug_directory` (Gap 22 fix — POGO check for Denuvo ATD detection)
