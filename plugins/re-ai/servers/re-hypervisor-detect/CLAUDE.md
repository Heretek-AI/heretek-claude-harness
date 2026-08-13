# re-hypervisor-detect

MCP server for hypervisor-detection primitive scanning: CPUID leaves, VMX/EPT, TSC skew, SMBIOS/ACPI probes. Wraps re-winedbg + re-lief. Vendor-neutral.

Version: 0.1.0 | License: MIT

## Structure

```
re-hypervisor-detect/
  pyproject.toml                    # build config (setuptools, mcp[cli] + deps)
  src/re_hypervisor_detect/
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
re-hypervisor-detect                         # start MCP server on stdio
```



## Tools

This server exposes these MCP tools: `check_hypervisor_detect,cpu_id_leaf_probe,vmx_ept_probe,tsc_skew_measure,smbios_probe,registry_probe,classify_hypervisor_posture`

## Usage (standalone)

Register this server in your `.mcp.json`:

```json
{
  "mcpServers": {
    "re-hypervisor-detect": {
      "command": "uv",
      "args": ["--directory", "/path/to/re-hypervisor-detect", "run", "re-hypervisor-detect"]
    }
  }
}
```

Or use via the [RE-AI agent-space](https://github.com/Heretek-RE/RE-AI): `./install.sh` clones all servers at pinned versions.
