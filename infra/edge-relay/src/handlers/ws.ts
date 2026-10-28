/**
 * WebSocket Push Hub for real-time desktop client synchronization.
 */

import { Env } from "../types";
import { jsonResponse } from "../utils";

/** Active WebSocket client connections connected to /api/ws */
export const activeClientSockets = new Set<WebSocket>();

/** Broadcasts a realtime JSON event to all connected WebSocket clients */
export function broadcastEvent(event: { type: string; payload?: any; [key: string]: any }): void {
  const message = JSON.stringify(event);
  for (const socket of activeClientSockets) {
    try {
      socket.send(message);
    } catch {
      activeClientSockets.delete(socket);
    }
  }
}

/**
 * Handles GET /api/ws WebSocket upgrade requests.
 * Authenticates via ?token=<secret> matching env.DESKTOP_API_SECRET.
 */
export function handleWebSocketUpgrade(
  request: Request,
  env: Env,
  url: URL
): Response {
  if (request.method !== "GET") {
    return jsonResponse({ error: "Method Not Allowed" }, 405);
  }

  const upgradeHeader = request.headers.get("Upgrade");
  if (upgradeHeader !== "websocket" && upgradeHeader?.toLowerCase() !== "websocket") {
    return new Response("Expected Upgrade: websocket", { status: 426 });
  }

  const token = url.searchParams.get("token");
  if (!env.DESKTOP_API_SECRET || !token || token !== env.DESKTOP_API_SECRET) {
    return jsonResponse({ error: "Unauthorized" }, 401);
  }

  const { 0: client, 1: server } = new WebSocketPair();

  server.accept();
  activeClientSockets.add(server);

  server.addEventListener("close", () => {
    activeClientSockets.delete(server);
  });

  server.addEventListener("error", () => {
    activeClientSockets.delete(server);
  });

  server.addEventListener("message", (event: MessageEvent) => {
    const data = typeof event.data === "string" ? event.data : event.data?.toString();
    if (data === "ping") {
      server.send("pong");
    }
  });

  try {
    return new Response(null, {
      status: 101,
      webSocket: client,
    } as ResponseInit);
  } catch {
    // Fallback for Node/test environments where Response constructor disallows status 101
    const res = new Response(null, { status: 200, statusText: "Switching Protocols" });
    Object.defineProperty(res, "status", { value: 101, writable: true, configurable: true });
    Object.defineProperty(res, "webSocket", { value: client, writable: true, configurable: true });
    return res;
  }
}
