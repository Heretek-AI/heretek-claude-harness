# Epic Online Services (EOS)

**Provider:** Epic Games
**Surface:** `EOSSDK-Win64-Shipping.dll` is the canonical sibling artifact

## Headline

A custom-engine game is the canonical EOS-bypass target (the `re-eos-bypass` skill handles the per-binary EOS side-file drop). The `clockwork_crossplatform_eos.dll` + `EOSSDK-Win64-Shipping.dll` pair is the EOS sibling-stub-drop pattern.

## Per-game evidence

| Game | EOS sibling | Notes |
|---|---|---|
| Custom-engine target | `clockwork_crossplatform_eos.dll` + `EOSSDK-Win64-Shipping.dll` (~19MB) | Custom EOS shim |

## Cross-references

- RE-AI `skills/re-eos-bypass/SKILL.md` (5-step EOS stub walk)
- RE-AI See the RE-AI output directory. (v2.9.0 per-target walks)
- RE-UNLEASHED `publishers/creative-assembly/total-war-warhammer-3/`
