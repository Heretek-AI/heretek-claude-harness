# re-binary-diff

MCP server for binary diff and section fingerprinting: unified diff between two files, per-section fingerprint of one file. Dry-run only — never writes. Pure-Python, no system dependencies.

Version: 0.1.0 | License: MIT

## Structure

```
re-binary-diff/
  pyproject.toml                    # build config (setuptools, mcp[cli] + deps)
  src/re_binary_diff/
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
re-binary-diff                         # start MCP server on stdio
```



## Tools

This server exposes these MCP tools: `check_binary_diff,unified_diff,fingerprint_sections`

## Usage (standalone)

Register this server in your `.mcp.json`:

```json
{
  "mcpServers": {
    "re-binary-diff": {
      "command": "uv",
      "args": ["--directory", "/path/to/re-binary-diff", "run", "re-binary-diff"]
    }
  }
}
```

Or use via the [RE-AI agent-space](https://github.com/Heretek-RE/RE-AI): `./install.sh` clones all servers at pinned versions.
