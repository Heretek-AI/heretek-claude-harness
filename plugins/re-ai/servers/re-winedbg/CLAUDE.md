# re-winedbg

MCP server wrapping winedbg + gdb for headless Windows-binary debugging on Linux/macOS.

Version: 0.1.0 | License: MIT

## Structure

```
re-winedbg/
  pyproject.toml                    # build config (setuptools, mcp[cli] + deps)
  src/re_winedbg/
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
re-winedbg                         # start MCP server on stdio
```



## Tools

This server exposes these MCP tools: `check_winedbg,launch_under_wine,start_winedbg_gdbserver,attach_winedbg_gdbserver,set_breakpoint,remove_breakpoint,gef_trace_breakpoint,continue_execution,step_into,step_over,step_out,read_registers,write_register,read_memory,write_memory,info_modules,info_threads,backtrace,end_session`

## Usage (standalone)

Register this server in your `.mcp.json`:

```json
{
  "mcpServers": {
    "re-winedbg": {
      "command": "uv",
      "args": ["--directory", "/path/to/re-winedbg", "run", "re-winedbg"]
    }
  }
}
```

Or use via the [RE-AI agent-space](https://github.com/Heretek-RE/RE-AI): `./install.sh` clones all servers at pinned versions.
