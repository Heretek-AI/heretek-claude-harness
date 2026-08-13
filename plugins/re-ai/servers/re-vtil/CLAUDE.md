# re-vtil

MCP server for VTIL-Core (Virtual-machine Translation Intermediate Language) — lift, optimize, and emit pseudo-C for VM handler characterization. Vendor-neutral wrapper around the vtil-project/VTIL-Core C++ library.

Version: 0.1.0 | License: MIT

## Structure

```
re-vtil/
  pyproject.toml                    # build config (setuptools, mcp[cli] + deps)
  src/re_vtil/
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
re-vtil                         # start MCP server on stdio
```



## Tools

This server exposes these MCP tools: `check_vtil,lift_handler,optimize,emit_pseudo_c,simplify_lifted_il`

## Usage (standalone)

Register this server in your `.mcp.json`:

```json
{
  "mcpServers": {
    "re-vtil": {
      "command": "uv",
      "args": ["--directory", "/path/to/re-vtil", "run", "re-vtil"]
    }
  }
}
```

Or use via the [RE-AI agent-space](https://github.com/Heretek-RE/RE-AI): `./install.sh` clones all servers at pinned versions.
