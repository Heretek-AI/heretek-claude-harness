# re-ios

MCP server for iOS / Mach-O reverse engineering: IPA parse, ObjC class dump, Swift symbol demangle, Frida-on-iOS session. Wraps re-frida + re-lief. Vendor-neutral.

## Tools

Run ``re-ios`` over the MCP stdio transport to expose the
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
