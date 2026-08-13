# re-ios

MCP server for iOS / Mach-O reverse engineering: IPA parse, ObjC class dump, Swift symbol demangle, Frida-on-iOS session. Wraps re-frida + re-lief. Vendor-neutral.

Version: 0.1.0 | License: MIT

## Structure

```
re-ios/
  pyproject.toml                    # build config (setuptools, mcp[cli] + deps)
  src/re_ios/
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
re-ios                         # start MCP server on stdio
```



## Tools

This server exposes these MCP tools: `check_ios,parse_ipa,dump_objc_classes,demangle_swift_symbols,enumerate_linked_frameworks,start_ios_session`

## Usage (standalone)

Register this server in your `.mcp.json`:

```json
{
  "mcpServers": {
    "re-ios": {
      "command": "uv",
      "args": ["--directory", "/path/to/re-ios", "run", "re-ios"]
    }
  }
}
```

Or use via the [RE-AI agent-space](https://github.com/Heretek-RE/RE-AI): `./install.sh` clones all servers at pinned versions.
