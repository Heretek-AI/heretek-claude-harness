/**
 * android-re mcp-bridge entry point.
 *
 * Wires the FastMCP-equivalent Server (using @modelcontextprotocol/sdk)
 * to stdio and registers every tool. Destructive tools (install,
 * uninstall, push, etc.) require an explicit `confirm: true` flag.
 */

import { StdioServerTransport } from "@modelcontextprotocol/sdk/server/stdio.js";
import { createServer } from "./server.js";
import { logger } from "./util/logger.js";

async function main(): Promise<void> {
  const server = await createServer();
  const transport = new StdioServerTransport();
  await server.connect(transport);
  logger.info("android-re-mcp-bridge started on stdio");
}

main().catch((err: unknown) => {
  logger.error(`fatal: ${err instanceof Error ? err.message : String(err)}`);
  process.exit(1);
});
