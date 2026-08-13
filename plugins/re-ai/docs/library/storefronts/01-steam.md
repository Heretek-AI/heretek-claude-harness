# Steam

**Provider:** Valve Corporation
**Surface:** `steam_api64.dll` is the canonical sibling artifact; `steam_appid.txt` is the documented developer escape hatch

## Headline

The Steamworks SDK is publicly documented. Valve ships a `steam_appid.txt` convention that, when placed in the game's working directory, allows the game to run without an active Steam client. This is the documented developer escape hatch — not a bypass.

Representative stress-test targets carry `steam_api64.dll` siblings or have Steam-deployed SKUs. The `re-steam-stub-unwrap` skill handles the per-binary Steam stub-drop.

## Per-game evidence

| Game | Steam sibling | Notes |
|---|---|---|
| IL2CPP target (example A) | `steam_api64.dll` (~300KB) | Standard Steamworks |
| Football Manager 26 | (via Unity Steamworks plugin) | Unity Steamworks |
| IL2CPP target (example B) | (via Unity Steamworks plugin) | Unity Steamworks |
| Lost In Random | (via Unity Steamworks plugin) | Plus EA App/Origin |
| UE5 target (example A) | (via UE5 OnlineSubsystemSteam) | Standard Steamworks |
| UE5 target (example B) | (via UE5 OnlineSubsystemSteam) | Standard Steamworks |
| Custom-engine target | `clockwork_steam.dll` (~250KB) | Custom Steam shim |

## Cross-references

- RE-AI `skills/re-steam-stub-unwrap/SKILL.md` (5-step Steam stub walk)
- RE-AI `docs/re-steam-unwrap.md` (Steam-specific research notes)
- RE-AI See the RE-AI output directory. (v2.9.0 per-target walks)
