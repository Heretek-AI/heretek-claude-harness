# re-angr

MCP server for angr (UC Santa Barbara) — symbolic execution + CFG + reaching-definitions. Cross-validates re-triton for MBA-obfuscated arithmetic. Vendor-neutral.

Version: 0.1.0 | License: MIT

## Structure

```
re-angr/
  pyproject.toml                    # build config (setuptools, mcp[cli] + deps)
  src/re_angr/
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
re-angr                         # start MCP server on stdio
```



## Tools

This server exposes these MCP tools: `check_angr,build_cfg,symbolic_exec,reaching_definitions`

## Usage (standalone)

Register this server in your `.mcp.json`:

```json
{
  "mcpServers": {
    "re-angr": {
      "command": "uv",
      "args": ["--directory", "/path/to/re-angr", "run", "re-angr"]
    }
  }
}
```

Or use via the [RE-AI agent-space](https://github.com/Heretek-RE/RE-AI): `./install.sh` clones all servers at pinned versions.
