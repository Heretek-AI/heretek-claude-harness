# re-speakeasy

MCP server for Speakeasy (Mandiant) Windows API emulation — runs Windows .exe in a Wine-like emulator and returns a structured per-API trace. Vendor-neutral.

Version: 0.1.0 | License: MIT

## Structure

```
re-speakeasy/
  pyproject.toml                    # build config (setuptools, mcp[cli] + deps)
  src/re_speakeasy/
    __init__.py
    __main__.py                     # entry: from server import main; main()
    server.py                       # FastMCP app with @mcp.tool() functions
  README.md
  LICENSE
  SECURITY.md

  bin/                              # CLI scripts
```

## Build

```bash
pip install -e .                    # install with deps
re-speakeasy                         # start MCP server on stdio
```



## Tools

This server exposes these MCP tools: `check_speakeasy,emulate_binary,list_emulated_apis`

## Usage (standalone)

Register this server in your `.mcp.json`:

```json
{
  "mcpServers": {
    "re-speakeasy": {
      "command": "uv",
      "args": ["--directory", "/path/to/re-speakeasy", "run", "re-speakeasy"]
    }
  }
}
```

Or use via the [RE-AI agent-space](https://github.com/Heretek-RE/RE-AI): `./install.sh` clones all servers at pinned versions.
