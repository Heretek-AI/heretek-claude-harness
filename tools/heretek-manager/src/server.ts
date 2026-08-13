import express from "express";
import type { Server as HttpServer } from "http";
import http from "http";
import { statusRouter } from "./api/status.js";
import { createProvidersRouter } from "./api/providers.js";
import { createModelsRouter } from "./api/models.js";
import type { AIProvider } from "./providers/types.js";
import { EventBroadcaster } from "./ws/events.js";

export interface ServerResult {
  http: HttpServer;
  broadcaster: EventBroadcaster;
}

export function createServer(
  providers?: Map<string, AIProvider>
): ServerResult {
  const app = express();
  app.use(express.json());

  const registry = providers || new Map();

  app.use("/api/status", statusRouter);
  app.use("/api/providers", createProvidersRouter(registry));
  app.use("/api/models", createModelsRouter(registry));

  const srv = http.createServer(app);
  const broadcaster = new EventBroadcaster(srv);
  return { http: srv, broadcaster };
}
