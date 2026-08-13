# re-yara

MCP server wrapping the YARA pattern-matching engine for binary triage: compile user-supplied rule directories and scan files / directories against them. Ships zero rules; the analyst provides them.

Version: 0.1.0 | License: MIT

## Structure

```
re-yara/
  pyproject.toml                    # build config (setuptools, mcp[cli] + deps)
  src/re_yara/
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
re-yara                         # start MCP server on stdio
```



## Tools

This server exposes these MCP tools: `check_yara,compile_rules,scan_binary,scan_directory`

## Usage (standalone)

Register this server in your `.mcp.json`:

```json
{
  "mcpServers": {
    "re-yara": {
      "command": "uv",
      "args": ["--directory", "/path/to/re-yara", "run", "re-yara"]
    }
  }
}
```

Or use via the [RE-AI agent-space](https://github.com/Heretek-RE/RE-AI): `./install.sh` clones all servers at pinned versions.
