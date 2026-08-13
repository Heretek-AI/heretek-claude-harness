# re-report-write

MCP server for writing analyst reports: free-text Markdown to a file, structured table to a file. Pure-Python, no system dependencies.

Version: 0.1.0 | License: MIT

## Structure

```
re-report-write/
  pyproject.toml                    # build config (setuptools, mcp[cli] + deps)
  src/re_report_write/
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
re-report-write                         # start MCP server on stdio
```



## Tools

This server exposes these MCP tools: `check_report_write,write_report,write_table`

## Usage (standalone)

Register this server in your `.mcp.json`:

```json
{
  "mcpServers": {
    "re-report-write": {
      "command": "uv",
      "args": ["--directory", "/path/to/re-report-write", "run", "re-report-write"]
    }
  }
}
```

Or use via the [RE-AI agent-space](https://github.com/Heretek-RE/RE-AI): `./install.sh` clones all servers at pinned versions.
