# re-apktool

MCP server for **Android APK** triage. Two backends are supported
on the same MCP surface:

- **apktool** (Java) — the canonical APK disassembler. Produces
  a Smali representation of every DEX class plus a decoded
  `AndroidManifest.xml`. Install: `apt-get install apktool` or
  download the jar from
  <https://github.com/iBotPeaches/Apktool/releases>.
- **androguard** (Python) — pure-Python APK / DEX / manifest
  parser. Always installed (the server's hard dep). Faster to
  import, easier to script; less Smali-friendly than apktool.

The MCP wrappers call whichever backend is available; the
`check_apktool` tool reports the active backend so the analyst
knows which one fired.

## Tools

| Tool | What it does |
|---|---|
| `check_apktool` | Health check — return apktool / androguard / java availability |
| `parse_apk` | Open the APK, return header info (package, version, min/target SDK, per-file entry list, signature block presence) |
| `list_dex_classes` | Enumerate classes across every `classes*.dex` in the APK |
| `decode_manifest` | Return the decoded `AndroidManifest.xml` (text) plus the parsed activity / service / receiver / provider / permission lists |

## Why both backends?

`apktool` is the gold standard for Smali and manifest
decoding, but it's a Java tool the user has to install. The
`parse_apk` + `list_dex_classes` + `decode_manifest` surface
area is small enough that `androguard` covers ~90% of the
analyst's needs (header + classes + manifest) without requiring
a JRE. The MCP layer prefers `apktool` when present and falls
back to `androguard` cleanly.

## Install

```bash
pip install -e ./servers/re-apktool        # androguard (required)
apt-get install apktool                    # apktool (optional, java)
```

## Run

```bash
re-apktool                                 # stdio transport (default for MCP)
python -m re_apktool                       # equivalent
```

## Deferred to a future run

The original Explore findings called for an APK parser; this
scaffolding lands it so the future Android target run has the
toolchain. The Live Fire Windows-target run uses
`re-leak-scan` + `re-winedbg` for the three named products;
`re-apktool` becomes the workhorse when an Android binary is in
the input.
