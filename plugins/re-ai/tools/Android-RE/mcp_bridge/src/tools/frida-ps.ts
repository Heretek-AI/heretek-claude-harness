/**
 * frida-ps tool: list processes on a device via the adb shell.
 *
 * We intentionally do not wrap frida-tools in Node — the Python
 * android-re-mcp-dynamic server owns Frida session / script / RPC.
 * This tool is a thin "what's running" helper for parity.
 */

import { z } from "zod";
import type { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js";
import { adbClient } from "../adb/client.js";

export function register(server: McpServer): void {
  server.tool(
    "frida_list_processes",
    "List running processes on a device using `ps -A` via adb.",
    {
      serial: z.string().describe("Device serial"),
      filter: z.string().optional().describe("Substring filter on process name"),
    },
    async ({ serial, filter }) => {
      try {
        const { stdout } = await adbClient().shell(serial, "ps -A");
        const procs: { pid: number; name: string }[] = [];
        for (const line of stdout.split("\n").slice(1)) {
          const parts = line.trim().split(/\s+/);
          if (parts.length < 9) continue;
          const pid = parseInt(parts[1], 10);
          if (Number.isNaN(pid)) continue;
          const name = parts[parts.length - 1];
          if (filter && !name.includes(filter)) continue;
          procs.push({ pid, name });
        }
        return { content: [{ type: "text", text: JSON.stringify({ count: procs.length, processes: procs }) }] };
      } catch (e) {
        return { content: [{ type: "text", text: `error: ${(e as Error).message}` }], isError: true };
      }
    }
  );

  server.tool(
    "frida_ps",
    "Alias for frida_list_processes.",
    {
      serial: z.string().describe("Device serial"),
      filter: z.string().optional().describe("Substring filter on process name"),
    },
    async ({ serial, filter }) => {
      // Re-export the same handler
      try {
        const { stdout } = await adbClient().shell(serial, "ps -A");
        const procs: { pid: number; name: string }[] = [];
        for (const line of stdout.split("\n").slice(1)) {
          const parts = line.trim().split(/\s+/);
          if (parts.length < 9) continue;
          const pid = parseInt(parts[1], 10);
          if (Number.isNaN(pid)) continue;
          const name = parts[parts.length - 1];
          if (filter && !name.includes(filter)) continue;
          procs.push({ pid, name });
        }
        return { content: [{ type: "text", text: JSON.stringify({ count: procs.length, processes: procs }) }] };
      } catch (e) {
        return { content: [{ type: "text", text: `error: ${(e as Error).message}` }], isError: true };
      }
    }
  );
}
