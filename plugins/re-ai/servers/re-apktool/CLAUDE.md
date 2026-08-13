# re-apktool

MCP server for Android APK triage: parse APK headers, list DEX classes, decode AndroidManifest.xml. Wraps apktool (Java) and androguard (Python) so the MCP caller can pick either backend.

Version: 0.1.0 | License: MIT

## Structure

```
re-apktool/
  pyproject.toml                    # build config (setuptools, mcp[cli] + deps)
  src/re_apktool/
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
re-apktool                         # start MCP server on stdio
```



## Tools

This server exposes these MCP tools: `check_apktool,parse_apk,list_dex_classes,decode_manifest,classify_apk_protection`

## Usage (standalone)

Register this server in your `.mcp.json`:

```json
{
  "mcpServers": {
    "re-apktool": {
      "command": "uv",
      "args": ["--directory", "/path/to/re-apktool", "run", "re-apktool"]
    }
  }
}
```

Or use via the [RE-AI agent-space](https://github.com/Heretek-RE/RE-AI): `./install.sh` clones all servers at pinned versions.
