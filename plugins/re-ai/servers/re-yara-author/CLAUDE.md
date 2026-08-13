# re-yara-author

MCP server for authoring YARA rules from binary samples: distinctive feature extraction, candidate ranking, rule emission, validation against a positive/negative set. Wraps re-lief + re-yara. Pure-Python, vendor-neutral.

Version: 0.1.0 | License: MIT

## Structure

```
re-yara-author/
  pyproject.toml                    # build config (setuptools, mcp[cli] + deps)
  src/re_yara_author/
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
re-yara-author                         # start MCP server on stdio
```



## Tools

This server exposes these MCP tools: `check_yara_author,extract_distinctive_features,rank_candidates,emit_rule,validate_rule,iterate_on_false_positives`

## Usage (standalone)

Register this server in your `.mcp.json`:

```json
{
  "mcpServers": {
    "re-yara-author": {
      "command": "uv",
      "args": ["--directory", "/path/to/re-yara-author", "run", "re-yara-author"]
    }
  }
}
```

Or use via the [RE-AI agent-space](https://github.com/Heretek-RE/RE-AI): `./install.sh` clones all servers at pinned versions.
