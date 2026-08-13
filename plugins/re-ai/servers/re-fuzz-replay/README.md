# re-fuzz-replay

MCP server for fuzz-style replay of an input corpus against a target function. Wraps re-triton + re-gdb. Pure-Python, vendor-neutral.

## Tools

Run ``re-fuzz-replay`` over the MCP stdio transport to expose the
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
