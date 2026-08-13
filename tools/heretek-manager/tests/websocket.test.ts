import { describe, it, expect, beforeAll, afterAll } from "vitest";
import WebSocket from "ws";
import { createServer } from "../src/server.js";

let server: ReturnType<typeof createServer>["http"];
let port: number;

beforeAll(async () => {
  ({ http: server } = createServer());
  await new Promise<void>((resolve) => server.listen(0, resolve));
  port = (server.address() as { port: number }).port;
});

afterAll(() => server.close());

describe("WebSocket", () => {
  it("connects and receives welcome", async () => {
    const ws = new WebSocket(`ws://localhost:${port}`);
    const msg = await new Promise<string>((resolve) => {
      ws.on("message", (data) => resolve(data.toString()));
    });
    ws.close();
    const parsed = JSON.parse(msg);
    expect(parsed.type).toBe("connected");
  });
});
