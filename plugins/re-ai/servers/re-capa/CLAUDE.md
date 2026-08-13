# re-capa

MCP server exposing capa (Mandiant) for capability detection with MITRE ATT&CK / MBC mappings.

Version: 0.1.0 | License: MIT

## Structure

```
re-capa/
  pyproject.toml                    # build config (setuptools, mcp[cli] + deps)
  src/re_capa/
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
re-capa                         # start MCP server on stdio
```



## Tools

This server exposes these MCP tools: `check_capa,detect_capabilities,extract_mbc,find_interesting`

## Usage (standalone)

Register this server in your `.mcp.json`:

```json
{
  "mcpServers": {
    "re-capa": {
      "command": "uv",
      "args": ["--directory", "/path/to/re-capa", "run", "re-capa"]
    }
  }
}
```

Or use via the [RE-AI agent-space](https://github.com/Heretek-RE/RE-AI): `./install.sh` clones all servers at pinned versions.
