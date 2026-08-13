# re-kaitai

MCP server exposing kaitai-struct for custom binary format reverse engineering.

Version: 0.1.0 | License: MIT

## Structure

```
re-kaitai/
  pyproject.toml                    # build config (setuptools, mcp[cli] + deps)
  src/re_kaitai/
    __init__.py
    __main__.py                     # entry: from server import main; main()
    server.py                       # FastMCP app with @mcp.tool() functions
  README.md
  LICENSE
  SECURITY.md


```

## Build

```bash
pip install -e .                    # install with deps
re-kaitai                         # start MCP server on stdio
```



## Tools

This server exposes these MCP tools: `check_compiler,list_known_formats,download_format,compile_format,parse_with_format,visualize,parse_unityfs,diff_parses`

## Usage (standalone)

Register this server in your `.mcp.json`:

```json
{
  "mcpServers": {
    "re-kaitai": {
      "command": "uv",
      "args": ["--directory", "/path/to/re-kaitai", "run", "re-kaitai"]
    }
  }
}
```

Or use via the [RE-AI agent-space](https://github.com/Heretek-RE/RE-AI): `./install.sh` clones all servers at pinned versions.
