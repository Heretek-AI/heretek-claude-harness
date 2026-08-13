# EA App / Origin

**Provider:** Electronic Arts
**Surface:** `OriginSDK.dll` is the canonical sibling artifact; the `.ooa` section in the launcher is the side-file

## Headline

A representative IL2CPP game is the canonical EA App/Origin target. The representative launcher carries an `.ooa` section (2048 bytes, entropy 3.02) — the Origin/EA App side-file. The `OriginSDK.dll` is in the IL2CPP metadata (191 types in the OriginSDK image). The `re-origin-stub-drop` skill (v2.9.0 WS-25) handles the per-binary Origin side-file drop.

## Per-game evidence

| Game | Origin/EA App signal | Notes |
|---|---|---|
| Representative IL2CPP target | `.ooa` section in launcher; `OriginSDK.dll` in IL2CPP metadata | IL2CPP game with EA App integration |

## Cross-references

- RE-AI `skills/re-origin-stub-drop/SKILL.md` (5-step Origin stub walk)
- RE-AI See the RE-AI output directory. (v2.9.0 walk)
- RE-UNLEASHED `publishers/ea-originals/lost-in-random/`
