# re-dotnet

MCP server for .NET assembly analysis: enumerate types, methods, fields, strings, and decompile to C# (ILSpy backend). Vendor-neutral wrapper around AsmResolver + ICSharpCode.Decompiler.

Version: 0.1.0 | License: MIT

## Structure

```
re-dotnet/
  pyproject.toml                    # build config (setuptools, mcp[cli] + deps)
  src/re_dotnet/
    __init__.py
    __main__.py                     # entry: from server import main; main()
    server.py                       # FastMCP app with @mcp.tool() functions
  README.md
  LICENSE
  SECURITY.md

  bin/                              # CLI scripts
```

## Build

```bash
pip install -e .                    # install with deps
re-dotnet                         # start MCP server on stdio
```



## Tools

This server exposes these MCP tools: `check_dotnet,parse_assembly,decompile_type,decompile_method,list_strings,get_entry_point,get_methods,get_fields,classify_dotnet_protection,detect_managed_anti_debug,run_il_simplification`

## Usage (standalone)

Register this server in your `.mcp.json`:

```json
{
  "mcpServers": {
    "re-dotnet": {
      "command": "uv",
      "args": ["--directory", "/path/to/re-dotnet", "run", "re-dotnet"]
    }
  }
}
```

Or use via the [RE-AI agent-space](https://github.com/Heretek-RE/RE-AI): `./install.sh` clones all servers at pinned versions.
