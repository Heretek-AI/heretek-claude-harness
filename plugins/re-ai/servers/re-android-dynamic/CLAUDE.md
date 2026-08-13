# re-android-dynamic

MCP server for runtime analysis of an Android APK via Frida + the device. Wraps re-frida + re-apktool. Vendor-neutral.

Version: 0.1.0 | License: MIT

## Structure

```
re-android-dynamic/
  pyproject.toml                    # build config (setuptools, mcp[cli] + deps)
  src/re_android_dynamic/
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
re-android-dynamic                         # start MCP server on stdio
```



## Tools

This server exposes these MCP tools: `check_android_dynamic,start_android_session,trace_method,dump_class_loader,check_root_bypass,check_ssl_pinning_bypass,install_objection,rpc_call`

## Usage (standalone)

Register this server in your `.mcp.json`:

```json
{
  "mcpServers": {
    "re-android-dynamic": {
      "command": "uv",
      "args": ["--directory", "/path/to/re-android-dynamic", "run", "re-android-dynamic"]
    }
  }
}
```

Or use via the [RE-AI agent-space](https://github.com/Heretek-RE/RE-AI): `./install.sh` clones all servers at pinned versions.
