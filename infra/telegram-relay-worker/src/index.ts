/**
 * Cloudflare Worker: Telegram Webhook to GitHub repository_dispatch Relay & Desktop API.
 *
 * Modular architecture:
 * - types.ts: Core interfaces (Env, TelegramUpdate, etc.)
 * - utils.ts: HTML escaping, Telegram messaging, and response helpers
 * - handlers/ws.ts: WebSocket upgrade and realtime broadcast
 * - handlers/api.ts: REST API endpoints for Desktop Control Panel
 * - handlers/webhook.ts: Telegram webhook updates, commands, and callback queries
 */

import { Env } from "./types";
import { handleApiRequest } from "./handlers/api";
import { handleTelegramWebhook } from "./handlers/webhook";

// Re-export types
export * from "./types";

// Re-export utilities
export * from "./utils";

// Re-export WebSocket handlers and state
export * from "./handlers/ws";

// Re-export REST API handlers
export * from "./handlers/api";

// Re-export Webhook handlers
export * from "./handlers/webhook";

export default {
  async fetch(request: Request, env: Env, ctx: ExecutionContext): Promise<Response> {
    const url = new URL(request.url);

    // Authenticated REST API & WebSocket routes: /api/*
    if (url.pathname === "/api" || url.pathname.startsWith("/api/")) {
      return handleApiRequest(request, env, ctx, url);
    }

    // Telegram webhook handler
    return handleTelegramWebhook(request, env, ctx);
  },
};
