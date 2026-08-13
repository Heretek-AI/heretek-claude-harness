/**
 * Build the MCP server and register every tool.
 *
 * The server speaks stdio (default MCP transport). HTTP/SSE is left to
 * the standard @modelcontextprotocol/sdk transports; the user wires
 * those up in a separate entry point if needed.
 */

import { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js";

export async function createServer(): Promise<McpServer> {
  const server = new McpServer(
    {
      name: "android-re-bridge",
      version: "0.1.0",
    },
    {
      instructions:
        "Android device bridge (adbkit). Low-level adb primitives: shell, pull, push, install, logcat, screencap, screenrecord, dumpsys, input, frida-ps. Destructive tools require confirm=true. For Frida session / script / RPC operations, use the Python android-re-dynamic server.",
    }
  );

  // Eagerly register every tool module *before* the caller connects a
  // transport. The MCP SDK refuses to register capabilities after
  // connect(), so a lazy `void import(...).then(register)` would race
  // main()'s `await server.connect(transport)` and crash with
  // "Cannot register capabilities after connecting to transport".
  const [adb, fridaPs] = await Promise.all([
    import("./tools/adb.js"),
    import("./tools/frida-ps.js"),
  ]);
  adb.register(server);
  fridaPs.register(server);

  return server;
}
