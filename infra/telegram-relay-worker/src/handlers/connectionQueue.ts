/**
 * Handlers for Outreach Connection Queue in Cloudflare Worker.
 */

import { Env } from "../types";
import { jsonResponse } from "../utils";
import { broadcastEvent } from "./ws";

export async function handleConnectionQueue(
  request: Request,
  env: Env
): Promise<Response> {
  if (!env.LINKEDIN_AGENT_KV) {
    return jsonResponse({ error: "KV namespace not configured" }, 500);
  }

  const method = request.method;

  // GET /api/connection-queue
  if (method === "GET") {
    try {
      const rawQueue = await env.LINKEDIN_AGENT_KV.get("connection_queue");
      let queue: unknown[] = [];
      if (rawQueue) {
        try {
          const parsed = JSON.parse(rawQueue);
          if (Array.isArray(parsed)) {
            queue = parsed;
          }
        } catch {
          queue = [];
        }
      }

      return jsonResponse({
        success: true,
        queue,
        candidates: queue,
      });
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : String(err);
      return jsonResponse({ error: "Failed to list connection queue", details: msg }, 500);
    }
  }

  // POST /api/connection-queue
  if (method === "POST") {
    let body: any;
    try {
      body = await request.json();
    } catch {
      return jsonResponse({ error: "Invalid JSON body" }, 400);
    }

    try {
      const rawQueue = await env.LINKEDIN_AGENT_KV.get("connection_queue");
      let queue: any[] = [];
      if (rawQueue) {
        try {
          queue = JSON.parse(rawQueue) || [];
        } catch {
          queue = [];
        }
      }

      // Check if it's an update status request: { id, status, note_text? }
      if (body.id && body.status && !body.profile_url && !body.candidate) {
        const idx = queue.findIndex((c: any) => c.id === body.id);
        if (idx >= 0) {
          queue[idx].status = body.status;
          if (body.note_text !== undefined) {
            queue[idx].note_text = body.note_text;
          }
          if (body.status === "approved") {
            queue[idx].approved_at = new Date().toISOString();
          }
        }
      } else {
        // Upsert candidate
        const candidate = body.candidate || body;
        if (!candidate || !candidate.id) {
          return jsonResponse({ error: "Candidate payload requires an 'id'" }, 400);
        }
        const idx = queue.findIndex((c: any) => c.id === candidate.id);
        if (idx >= 0) {
          queue[idx] = { ...queue[idx], ...candidate };
        } else {
          queue.push({
            status: "pending",
            created_at: new Date().toISOString(),
            ...candidate,
          });
        }
      }

      await env.LINKEDIN_AGENT_KV.put("connection_queue", JSON.stringify(queue));

      broadcastEvent({
        type: "connection_queue_updated",
      });

      return jsonResponse({
        success: true,
        queue,
      });
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : String(err);
      return jsonResponse({ error: "Failed to update connection queue", details: msg }, 500);
    }
  }

  return jsonResponse({ error: "Method Not Allowed" }, 405);
}
