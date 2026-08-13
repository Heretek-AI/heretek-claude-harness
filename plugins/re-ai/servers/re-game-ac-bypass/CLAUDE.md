# re-game-ac-bypass

MCP server for game anti-cheat runtime analysis: kernel-callback enumeration, anti-cheat primitive mapping, telemetry-beacon tracing. Wraps re-frida + re-winedbg + re-static-triage. Vendor-neutral: talks about observable anti-cheat primitives, not specific products.

Version: 0.1.0 | License: MIT

## Structure

```
re-game-ac-bypass/
  pyproject.toml                    # build config (setuptools, mcp[cli] + deps)
  src/re_game_ac_bypass/
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
re-game-ac-bypass                         # start MCP server on stdio
```



## Tools

This server exposes these MCP tools: `check_game_ac_bypass,enumerate_kernel_callbacks,map_anti_cheat_primitives,trace_telemetry_beacon,classify_anti_cheat_runtime`

## Usage (standalone)

Register this server in your `.mcp.json`:

```json
{
  "mcpServers": {
    "re-game-ac-bypass": {
      "command": "uv",
      "args": ["--directory", "/path/to/re-game-ac-bypass", "run", "re-game-ac-bypass"]
    }
  }
}
```

Or use via the [RE-AI agent-space](https://github.com/Heretek-RE/RE-AI): `./install.sh` clones all servers at pinned versions.
