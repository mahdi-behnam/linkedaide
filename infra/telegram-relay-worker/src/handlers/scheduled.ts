/**
 * Handlers for Scheduled Posts in Cloudflare Worker.
 */

import { Env } from "../types";
import { jsonResponse } from "../utils";
import { broadcastEvent } from "./ws";

export async function handleScheduledPosts(
  request: Request,
  env: Env,
  url: URL
): Promise<Response> {
  if (!env.LINKEDIN_AGENT_KV) {
    return jsonResponse({ error: "KV namespace not configured" }, 500);
  }

  const method = request.method;

  // GET /api/scheduled-posts
  if (method === "GET") {
    try {
      const rawPosts = await env.LINKEDIN_AGENT_KV.get("scheduled_posts");
      let posts: unknown[] = [];
      if (rawPosts) {
        try {
          const parsed = JSON.parse(rawPosts);
          if (Array.isArray(parsed)) {
            posts = parsed;
          }
        } catch {
          posts = [];
        }
      } else {
        // Fallback: list scheduled:* keys
        const listResult = await env.LINKEDIN_AGENT_KV.list({ prefix: "scheduled:" });
        for (const key of listResult.keys) {
          const raw = await env.LINKEDIN_AGENT_KV.get(key.name);
          if (raw) {
            try {
              posts.push(JSON.parse(raw));
            } catch {
              // ignore
            }
          }
        }
      }

      return jsonResponse({
        success: true,
        posts,
      });
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : String(err);
      return jsonResponse({ error: "Failed to list scheduled posts", details: msg }, 500);
    }
  }

  // POST /api/scheduled-posts
  if (method === "POST") {
    let body: any;
    try {
      body = await request.json();
    } catch {
      return jsonResponse({ error: "Invalid JSON body" }, 400);
    }

    const post = body?.post || body;
    if (!post || typeof post !== "object") {
      return jsonResponse({ error: "Missing post payload" }, 400);
    }

    const postId = post.id || `post_${Date.now()}_${Math.random().toString(36).substring(2, 7)}`;
    const fullPost = {
      ...post,
      id: postId,
      created_at: post.created_at || new Date().toISOString(),
    };

    try {
      // 1. Save single key
      await env.LINKEDIN_AGENT_KV.put(`scheduled:${postId}`, JSON.stringify(fullPost));

      // 2. Update list in scheduled_posts
      const rawList = await env.LINKEDIN_AGENT_KV.get("scheduled_posts");
      let list: any[] = [];
      if (rawList) {
        try {
          list = JSON.parse(rawList) || [];
        } catch {
          list = [];
        }
      }
      const existingIdx = list.findIndex((p: any) => p.id === postId);
      if (existingIdx >= 0) {
        list[existingIdx] = fullPost;
      } else {
        list.push(fullPost);
      }
      await env.LINKEDIN_AGENT_KV.put("scheduled_posts", JSON.stringify(list));

      broadcastEvent({
        type: "scheduled_posts_updated",
        post_id: postId,
        action: "save",
      });

      return jsonResponse({
        success: true,
        post: fullPost,
      });
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : String(err);
      return jsonResponse({ error: "Failed to save scheduled post", details: msg }, 500);
    }
  }

  // DELETE /api/scheduled-posts/:id or /api/scheduled-posts?id=:id
  if (method === "DELETE") {
    let postId = url.searchParams.get("id");
    const pathParts = url.pathname.replace(/\/+$/, "").split("/");
    if (pathParts.length > 3 && pathParts[2] === "scheduled-posts") {
      postId = pathParts[3];
    }

    if (!postId) {
      try {
        const body: any = await request.json();
        postId = body?.id || body?.post_id;
      } catch {
        // ignore
      }
    }

    if (!postId) {
      return jsonResponse({ error: "Post ID is required for deletion" }, 400);
    }

    try {
      // 1. Delete single key
      await env.LINKEDIN_AGENT_KV.delete(`scheduled:${postId}`);

      // 2. Remove from list in scheduled_posts
      const rawList = await env.LINKEDIN_AGENT_KV.get("scheduled_posts");
      if (rawList) {
        try {
          const list: any[] = JSON.parse(rawList) || [];
          const filtered = list.filter((p: any) => p.id !== postId);
          await env.LINKEDIN_AGENT_KV.put("scheduled_posts", JSON.stringify(filtered));
        } catch {
          // ignore
        }
      }

      broadcastEvent({
        type: "scheduled_posts_updated",
        post_id: postId,
        action: "delete",
      });

      return jsonResponse({
        success: true,
        id: postId,
      });
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : String(err);
      return jsonResponse({ error: "Failed to delete scheduled post", details: msg }, 500);
    }
  }

  return jsonResponse({ error: "Method Not Allowed" }, 405);
}
