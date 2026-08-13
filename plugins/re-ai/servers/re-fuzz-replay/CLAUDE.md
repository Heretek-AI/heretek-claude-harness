# re-fuzz-replay

MCP server for fuzz-style replay of an input corpus against a target function. Wraps re-triton + re-gdb. Pure-Python, vendor-neutral.

Version: 0.1.0 | License: MIT

## Structure

```
re-fuzz-replay/
  pyproject.toml                    # build config (setuptools, mcp[cli] + deps)
  src/re_fuzz_replay/
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
re-fuzz-replay                         # start MCP server on stdio
```



## Tools

This server exposes these MCP tools: `check_fuzz_replay,seed_replay,coverage_map,edge_diff,next_inputs`

## Usage (standalone)

Register this server in your `.mcp.json`:

```json
{
  "mcpServers": {
    "re-fuzz-replay": {
      "command": "uv",
      "args": ["--directory", "/path/to/re-fuzz-replay", "run", "re-fuzz-replay"]
    }
  }
}
```

Or use via the [RE-AI agent-space](https://github.com/Heretek-RE/RE-AI): `./install.sh` clones all servers at pinned versions.
