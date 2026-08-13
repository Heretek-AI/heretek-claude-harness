# re-il2cpp

MCP server reading Unity IL2CPP global-metadata.dat files to recover class/method/field/param names that the IL2CPP compiler stripped from GameAssembly.dll. Walks all 7 binary tables (typeDefinitions, methods, fields, parameters, properties, events, images) and resolves method RVAs in GameAssembly.dll. Supports Unity 2019.4 - 2022.3 LTS (metadata versions 24-29).

Version: 0.2.0 | License: MIT

## Structure

```
re-il2cpp/
  pyproject.toml                    # build config (setuptools, mcp[cli] + deps)
  src/re_il2cpp/
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
re-il2cpp                         # start MCP server on stdio
```



## Tools

This server exposes these MCP tools: `check_il,list_strings,search_strings,list_namespaces,list_classes,get_type_definitions,get_methods,get_fields,get_parameters,get_properties,get_events,get_images,get_assembly_types,resolve_method_rva`

## Usage (standalone)

Register this server in your `.mcp.json`:

```json
{
  "mcpServers": {
    "re-il2cpp": {
      "command": "uv",
      "args": ["--directory", "/path/to/re-il2cpp", "run", "re-il2cpp"]
    }
  }
}
```

Or use via the [RE-AI agent-space](https://github.com/Heretek-RE/RE-AI): `./install.sh` clones all servers at pinned versions.
