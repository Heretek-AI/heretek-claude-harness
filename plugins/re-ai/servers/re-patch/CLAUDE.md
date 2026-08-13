# re-patch

MCP server for on-disk patching of binary artifacts: SHA-256 manifest, byte-level patch application, manifest-driven restore. Pure-Python, no system dependencies.

Version: 0.1.0 | License: MIT

## Structure

```
re-patch/
  pyproject.toml                    # build config (setuptools, mcp[cli] + deps)
  src/re_patch/
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
re-patch                         # start MCP server on stdio
```



## Tools

This server exposes these MCP tools: `check_patch,sha,apply_patch,restore_original`

## Usage (standalone)

Register this server in your `.mcp.json`:

```json
{
  "mcpServers": {
    "re-patch": {
      "command": "uv",
      "args": ["--directory", "/path/to/re-patch", "run", "re-patch"]
    }
  }
}
```

Or use via the [RE-AI agent-space](https://github.com/Heretek-RE/RE-AI): `./install.sh` clones all servers at pinned versions.
