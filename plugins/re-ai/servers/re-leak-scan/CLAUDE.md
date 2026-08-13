# re-leak-scan

MCP server for detecting publisher telemetry pipeline leaks in binaries: Sentry DSNs, Logstash URLs, Confluence wiki links, Google Drive document URLs, Kafka topics. Pure-Python, vendor-neutral.

Version: 0.1.0 | License: MIT

## Structure

```
re-leak-scan/
  pyproject.toml                    # build config (setuptools, mcp[cli] + deps)
  src/re_leak_scan/
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
re-leak-scan                         # start MCP server on stdio
```



## Tools

This server exposes these MCP tools: `check_leak_scan,extract_strings,find_secrets,scan,verify_sentry_dsn,verify_confluence_url`

## Usage (standalone)

Register this server in your `.mcp.json`:

```json
{
  "mcpServers": {
    "re-leak-scan": {
      "command": "uv",
      "args": ["--directory", "/path/to/re-leak-scan", "run", "re-leak-scan"]
    }
  }
}
```

Or use via the [RE-AI agent-space](https://github.com/Heretek-RE/RE-AI): `./install.sh` clones all servers at pinned versions.
