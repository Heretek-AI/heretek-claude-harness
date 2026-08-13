# re-frida

MCP server wrapping the Frida dynamic-instrumentation toolkit for Android, iOS, macOS, Linux, and Windows targets. Spawn, attach, load scripts, enumerate modules/exports, hook methods, and call RPC exports.

Version: 0.1.0 | License: MIT

## Structure

```
re-frida/
  pyproject.toml                    # build config (setuptools, mcp[cli] + deps)
  src/re_frida/
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
re-frida                         # start MCP server on stdio
```



## Tools

This server exposes these MCP tools: `check_frida,start_session,attach_pid,end_session,script_load,script_call,enumerate_modules,enumerate_exports,hook_method,rpc_export`

## Usage (standalone)

Register this server in your `.mcp.json`:

```json
{
  "mcpServers": {
    "re-frida": {
      "command": "uv",
      "args": ["--directory", "/path/to/re-frida", "run", "re-frida"]
    }
  }
}
```

Or use via the [RE-AI agent-space](https://github.com/Heretek-RE/RE-AI): `./install.sh` clones all servers at pinned versions.
