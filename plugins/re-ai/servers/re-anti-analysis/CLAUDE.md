# re-anti-analysis

MCP server for anti-analysis primitive scanning: cross-section correlation of anti-debug + anti-VM + anti-sandbox primitives in a binary. Wraps re-lief + re-rizin + the vendored data/anti-analysis-catalog.json. Pure-Python, vendor-neutral.

Version: 0.1.0 | License: MIT

## Structure

```
re-anti-analysis/
  pyproject.toml                    # build config (setuptools, mcp[cli] + deps)
  src/re_anti_analysis/
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
re-anti-analysis                         # start MCP server on stdio
```



## Tools

This server exposes these MCP tools: `check_anti_analysis,scan_anti_analysis_primitives,classify_native_protection,correlate_anti_patterns,suggest_runtime_trap`

## Usage (standalone)

Register this server in your `.mcp.json`:

```json
{
  "mcpServers": {
    "re-anti-analysis": {
      "command": "uv",
      "args": ["--directory", "/path/to/re-anti-analysis", "run", "re-anti-analysis"]
    }
  }
}
```

Or use via the [RE-AI agent-space](https://github.com/Heretek-RE/RE-AI): `./install.sh` clones all servers at pinned versions.
