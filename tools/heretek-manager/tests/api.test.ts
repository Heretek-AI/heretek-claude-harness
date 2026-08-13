import { describe, it, expect, beforeAll, afterAll } from "vitest";
import type { Server } from "http";
import { createServer } from "../src/server.js";

let server: Server;
let baseUrl: string;

beforeAll(async () => {
  ({ http: server } = createServer());
  await new Promise<void>((resolve) => server.listen(0, resolve));
  const addr = server.address();
  baseUrl = `http://localhost:${(addr as { port: number }).port}`;
});

afterAll(() => server.close());

describe("GET /api/status", () => {
  it("returns ok", async () => {
    const res = await fetch(`${baseUrl}/api/status`);
    const body = await res.json();
    expect(res.status).toBe(200);
    expect(body.status).toBe("ok");
  });
});

describe("GET /api/providers", () => {
  it("returns provider list", async () => {
    const res = await fetch(`${baseUrl}/api/providers`);
    const body = await res.json();
    expect(res.status).toBe(200);
    expect(Array.isArray(body.providers)).toBe(true);
  });
});

describe("GET /api/models", () => {
  it("returns model list", async () => {
    const res = await fetch(`${baseUrl}/api/models`);
    const body = await res.json();
    expect(res.status).toBe(200);
    expect(Array.isArray(body.models)).toBe(true);
  });
});
