import { WebSocketServer, WebSocket } from "ws";
import type { Server } from "http";

export interface WSEvent {
  type: string;
  [key: string]: unknown;
}

export class EventBroadcaster {
  private wss: WebSocketServer;
  private clients: Set<WebSocket> = new Set();

  constructor(server: Server) {
    this.wss = new WebSocketServer({ server });
    this.wss.on("connection", (ws) => {
      this.clients.add(ws);
      ws.send(JSON.stringify({ type: "connected" }));
      ws.on("close", () => this.clients.delete(ws));
    });
  }

  broadcast(event: WSEvent): void {
    const data = JSON.stringify(event);
    for (const client of this.clients) {
      if (client.readyState === WebSocket.OPEN) {
        client.send(data);
      }
    }
  }
}
