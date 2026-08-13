# Contributing a Tool

## Where does my tool belong?

| Domain                | Server                | Module                                |
|-----------------------|-----------------------|----------------------------------------|
| APK manifest, classes, methods, signature, smali, jadx | `android-re-static` | `mcp_servers/static/src/.../tools/` |
| Native `.so`, OAT, VDEX, ART, ELF parsing             | `android-re-native` | `mcp_servers/native/src/.../tools/` |
| Device, Frida sessions, logcat, network, intents     | `android-re-dynamic` | `mcp_servers/dynamic/src/.../tools/` |
| Cross-server orchestration, MASVS report correlation  | `android-re-triage` | `mcp_servers/triage/src/.../tools/` |
| ADB, screencap, dumpsys, frida-ps (RE-specific only)  | `mcp_bridge` (TS)    | `mcp_bridge/src/tools/`              |

If a tool could belong to two servers, prefer the one that owns the
relevant state. For example, a tool that reads files from a device belongs
in `android-re-dynamic`, not `android-re-static`, even if the file is an
APK.

## Adding a Python tool

```python
# mcp_servers/static/src/android_re_mcp_static/tools/my_topic.py
from typing import Annotated
from pydantic import Field
from mcp.server.fastmcp import Context, FastMCP

def register(mcp: FastMCP) -> None:
    @mcp.tool(
        name="my_tool",
        description="Short, user-visible description shown to the LLM.",
    )
    def my_tool(
        project_id: Annotated[str, Field(description="Project ID returned by open_project")],
        some_arg: Annotated[int, Field(ge=0, le=100, default=10)],
    ) -> dict:
        """Long-form docstring shown in the tool's schema."""
        # ... do work using android_re_core ...
        return {"result": "..."}
```

Then register the topic module in `server.py`:

```python
from android_re_mcp_static.tools import my_topic  # noqa: F401
```

## Adding a TypeScript tool

```typescript
// mcp_bridge/src/tools/my_topic.ts
import { z } from "zod";
import type { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js";
import { adbClient } from "../adb/client.js";

export function registerMyTopicTools(server: McpServer): void {
  server.tool(
    "adb_my_tool",
    "Short, user-visible description shown to the LLM.",
    {
      serial: z.string().describe("Device serial from `adb devices`"),
      arg: z.number().int().min(0).max(100).default(10),
    },
    async ({ serial, arg }) => {
      const result = await adbClient(serial).shell(`...`);
      return { content: [{ type: "text", text: result.stdout }] };
    },
  );
}
```

Then register the topic in `src/server.ts`.

## Testing your tool

Every tool must have an in-memory `mcp.Client` test:

```python
# tests/test_mcp_static.py
import pytest
from mcp import Client
from android_re_mcp_static.server import build_server

@pytest.mark.asyncio
async def test_my_tool(crackme_apk):
    server = build_server()
    client = Client(server)
    await client.connect()

    tools = await client.list_tools()
    assert "my_tool" in {t.name for t in tools}

    # Open the project first
    open_result = await client.call_tool("open_project", {"apk_path": str(crackme_apk)})
    project_id = open_result["project_id"]

    # Now call your tool
    result = await client.call_tool("my_tool", {"project_id": project_id, "some_arg": 5})
    assert "result" in result
```

Run the test:

```bash
just test
# or
uv run pytest tests/test_mcp_static.py -k my_tool
```

## Documentation

Update `docs/mcp-tool-reference.md` with the new tool. The change should
include:

- Tool name and one-line description
- Input schema
- Example output
- Cross-references to related tools

## Pull request checklist

- [ ] Tool function implemented in the right module.
- [ ] Tool registered in `server.py` / `server.ts`.
- [ ] In-memory `mcp.Client` test added.
- [ ] Documentation updated.
- [ ] `just lint` and `just test` pass locally.
