# re-gdb

MCP server wrapping GDB + GEF for dynamic analysis.

Version: 0.1.0 | License: MIT

## Structure

```
re-gdb/
  pyproject.toml                    # build config (setuptools, mcp[cli] + deps)
  src/re_gdb/
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
re-gdb                         # start MCP server on stdio
```



## Tools

This server exposes these MCP tools: `check_gdb,start_session,end_session,run_to_breakpoint,step_count,read_memory,gef_heap,gef_canary,gef_registers,gef_vmmap,gef_nearpc,gef_pattern_create,gef_pattern_offset,attach_pid`

## Usage (standalone)

Register this server in your `.mcp.json`:

```json
{
  "mcpServers": {
    "re-gdb": {
      "command": "uv",
      "args": ["--directory", "/path/to/re-gdb", "run", "re-gdb"]
    }
  }
}
```

Or use via the [RE-AI agent-space](https://github.com/Heretek-RE/RE-AI): `./install.sh` clones all servers at pinned versions.
