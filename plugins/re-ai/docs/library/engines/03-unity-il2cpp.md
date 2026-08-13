# Unity IL2CPP — cross-publisher view

**Publisher:** Various (Unity Technologies engine, used by many publishers)
**Characteristics:** IL2CPP-compiled games with encrypted-VM bytecode interpreters in GameAssembly.dll

## Headline

IL2CPP (Intermediate Language To C++) is Unity's ahead-of-time compilation pipeline. The original C# source is converted to C++ and compiled to native code; the metadata (`global-metadata.dat`) retains the type/method/field names for runtime reflection.

The v2.9.1+ re-il2cpp walker handles versions 24-31 (Unity 2019.4 LTS through Unity 6). For metadata-stripped or non-standard-location targets, see the Step 1a branch in `skills/re-il2cpp-static-triage/SKILL.md`.

## Per-game table

| Game | Metadata version | Source artifact | Notes |
|---|---|---|---|
| Representative IL2CPP target (IL2CPP metadata v27) | Fully supported; OriginSDK.dll in metadata |
| Representative IL2CPP target (IL2CPP metadata v31) | Unity 6; Gap 25 canonical |
| Representative IL2CPP target | (stripped metadata variant) | Per-binary triage | Metadata stripped; Gap pattern |

## Cross-references

- RE-AI `servers/re-il2cpp/src/re_il2cpp/_common.py` (`MAX_VERSION=31`, v2.9.1+)
- RE-AI `servers/re-il2cpp/src/re_il2cpp/version_table.py`
- RE-AI `skills/re-il2cpp-static-triage/SKILL.md`
- RE-AI `ANTI-TAMPER-TAXONOMY.md` Pattern A (encrypted-VM bytecode interpreter, Unity IL2CPP variant)
