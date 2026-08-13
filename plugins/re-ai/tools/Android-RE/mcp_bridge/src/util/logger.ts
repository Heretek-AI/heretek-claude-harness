/**
 * Tiny structured logger that writes to stderr (stdout is reserved
 * for the MCP JSON-RPC transport).
 */

type Level = "info" | "warn" | "error" | "debug";

function emit(level: Level, msg: string): void {
  const line = `${new Date().toISOString()} [${level.toUpperCase()}] ${msg}\n`;
  process.stderr.write(line);
}

export const logger = {
  info: (msg: string): void => emit("info", msg),
  warn: (msg: string): void => emit("warn", msg),
  error: (msg: string): void => emit("error", msg),
  debug: (msg: string): void => emit("debug", msg),
};
