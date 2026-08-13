# re-game-ac-bypass

MCP server for game anti-cheat runtime analysis: kernel-callback enumeration, anti-cheat primitive mapping, telemetry-beacon tracing. Wraps re-frida + re-winedbg + re-static-triage. Vendor-neutral: talks about observable anti-cheat primitives, not specific products.

## Tools

Run ``re-game-ac-bypass`` over the MCP stdio transport to expose the
tool surface. The server is a pure-Python wrapper; the actual
work delegates to the existing RE-AI servers (re-lief, re-rizin,
re-yara, re-frida, etc.).

## Installation

The server is installed by `./install.sh` from the plugin root
and is auto-registered in `.mcp.json`. No external system
dependencies.

## Vendor-neutrality

All output is vendor-neutral: category names only, no specific
commercial product / publisher / game title.
