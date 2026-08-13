---
name: re-steam-stub-unwrap
description: Bypass the Steamworks stub launcher gate on a PE binary. Drops a steam_appid.txt side-file (the canonical Valve developer escape hatch) and, when needed, NOPs the SteamAPI_RestartAppIfNecessary call site. Use when the user says "remove the Steam requirement", "make this game launch without Steam", or "bypass the Steam stub". Formalizes the manual Write workaround from r03-stress.
---

# Bypass the Steam Stub Launcher Gate

## When to use

Use this skill when a PE binary refuses to launch without Steam — i.e., it
links Steamworks (`steam_api64.dll`) and calls `SteamAPI_RestartAppIfNecessary`
at startup, which spawns the Steam client and asks the user to launch
through Steam.

Common prompts:

- "Remove the Steam requirement from this `.exe`"
- "How do I run `game.exe` without Steam launching first?"
- "Bypass the Steam stub on this binary"
- "Drop the `steam_appid.txt` for this game"

**Does NOT** bypass anti-tamper wrappers (the encrypted-VM /
section-protected variety). Use
`re-drm-fingerprint` to identify those first; this skill only handles
the storefront-level gate.

## Workflow

### 1. Confirm the binary actually has a Steam stub

```
re-lief.parse_binary(path)                # confirm PE32+
re-lief.get_imports_exports(path)         # look for steam_api64.dll
re-rizin.search_bytes(path,
    pattern="5374 6561 6d 41 50 49 5f 52 65 73 74 61 72 74 41 70 70 49 66 4e 65 63 65 73 73 61 72 79")
                                          # "SteamAPI_RestartAppIfNecessary"
                                          # ASCII byte sequence
```

If `search_bytes` returns 0 hits, the binary doesn't link Steamworks
this way — abort and try a different storefront catalog entry.

### 2. Identify the Steam AppID

Look up the AppID on the public Steam store. The canonical URL is
`https://store.steampowered.com/app/<APPID>/<slug>/`. Either:

- `WebFetch` against `https://store.steampowered.com/search/?term=<game-name>`
- Read the bundled `references/steam_appid_dropper.py` which encodes
  the lookup pattern

The AppID is a positive integer (usually 6-7 digits).

### 3. Classify the stub version (optional but recommended)

```
mcp__re-rizin__list_imports_exports(path="<sibling steam_api64.dll>")
```

The exports list distinguishes Steamworks SDK versions:
- v1.51 (older): no `SteamAPI_InitSafe`, no `SteamAPI_InitAnonymousUser`
- v1.60+ (newer): both of the above present

See `references/steam_stub_classifier.py` for the structured detection.

### 4. Drop the side-file

This is the canonical Valve escape hatch — Steamworks reads
`steam_appid.txt` (alongside the executable, ASCII text + trailing
newline) and skips the relaunch check when present.

```
re-report-write.write_report(
    path="Output/<run-id>/patches/<target>/steam_appid.txt",
    content="<APPID>\n",
)
```

### 5. (Optional, advanced) NOP the call site

If the side-file alone is insufficient (the engine wraps the call in
a custom gate), find the actual call site:

```
re-rizin.search_bytes(path, pattern="<APPID hex string>")
                                          # often the AppID appears
                                          # in the literal as the
                                          # arg to RestartAppIfNecessary
re-rizin.get_xrefs(path, address="<addr-of-string>")
                                          # the xref is the call site
```

Then either:
- `re-patch.apply_patch` to NOP the `call` (`E8 ?? ?? ?? ??` → `90 ×5`)
- OR redirect the call to a `xor eax, eax; ret` stub (`31 C0 C3`)

Document the patch in `Output/<run-id>/patches/<target>/<binary>.candidate_patch.rationale.md`.

## Live-test (manual; outside the run scope)

```bash
cp Output/<run-id>/patches/<target>/steam_appid.txt \
   Input/.../<game>/<exe>.dir/steam_appid.txt
wine Input/.../<game>/<exe>
```

If the game launches without the Steam client window appearing — bypass
worked. If Steam still pops up, the engine wraps the call (try Step 5)
or the binary is also anti-tamper-protected (use `re-drm-fingerprint`).

## What this skill does NOT do

- It does NOT bypass anti-tamper. Combine with the relevant skill
  (`re-vm-reverse`, `re-encrypted-vm-tamper`) for the anti-tamper layer.
- It does NOT touch other storefront SDKs (EA / Epic / GOG). Each
  storefront has its own canonical bypass. See
  `data/drm-indicators.yaml::pattern_indicators.mappings` (descriptors
  `managed launcher store-gate`, `overlay-archive section in a
  launcher PE`) for the related entries.
  - **The managed-launcher ecosystem half is now in the
    `re-origin-stub-drop` skill** (shipped v2.9.0; uses the
    B3 catalog entry's `managed launcher store-gate`
    category label; the LIR per-target walk is in
    `See the RE-AI output directory.
    per-target/lir/`).
  - **The Epic Online Services half is in the
    `re-eos-bypass` skill** (shipped v2.9.0; the FM26
    per-target walk is in
    `See the RE-AI output directory.
    per-target/<sports-manager-target>/`).
- It does NOT distribute or vendor any third-party Steam emulator.
  See `docs/re-steam-unwrap.md` for the public-source citations and
  the cite-only policy.

## References

- `references/steam_appid_dropper.py` — verify the AppID via SteamDB
  and emit the canonical 8-byte payload
- `references/steam_stub_classifier.py` — v1.51 vs v1.60+ Steamworks
  detection from `steam_api64.dll` exports
- `docs/re-steam-unwrap.md` — public-source citation chain (added in
  WS-10)
- `data/drm-indicators.yaml::pattern_indicators.mappings` —
  `managed launcher store-gate` (B3) catalog entry
- **`re-origin-stub-drop`** (shipped v2.9.0) — the
  managed-launcher (C# / Mono) analogue; mirrors this
  skill's 5-step walk for the managed-launcher ecosystem
  entitlement on Mono launchers.
- **`re-eos-bypass`** (shipped v2.9.0) — the Epic
  Online Services analogue; the FM26 EOS overlay
  case.
