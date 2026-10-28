/**
 * Handlers for Scheduled Posts in Cloudflare Worker:
 * - REST API endpoints (GET, POST, DELETE)
 * - Cron trigger edge dispatcher (handleScheduledPostsCron)
 */

import { Env } from "../types";
import { jsonResponse } from "../utils";
import { broadcastEvent } from "./ws";

export interface ScheduledPostItem {
  id: string;
  headline?: string;
  post_text: string;
  scheduled_time?: string | null;
  status: "draft" | "scheduled" | "published" | "failed" | "rejected";
  media?: unknown[];
  dispatched_at?: string | null;
}

export interface ScheduledCronResult {
  checked: number;
  dispatched: number;
  errors: string[];
}

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

export async function handleScheduledPostsCron(
  env: Env,
  now: Date = new Date()
): Promise<ScheduledCronResult> {
  if (!env.LINKEDIN_AGENT_KV) {
    return { checked: 0, dispatched: 0, errors: ["No KV binding"] };
  }

  const rawPosts = await env.LINKEDIN_AGENT_KV.get("scheduled_posts");
  if (!rawPosts) {
    return { checked: 0, dispatched: 0, errors: [] };
  }

  let posts: ScheduledPostItem[];
  try {
    posts = JSON.parse(rawPosts);
  } catch (err: unknown) {
    return {
      checked: 0,
      dispatched: 0,
      errors: [`Failed to parse scheduled_posts: ${err instanceof Error ? err.message : String(err)}`],
    };
  }

  if (!Array.isArray(posts) || posts.length === 0) {
    return { checked: 0, dispatched: 0, errors: [] };
  }

  const duePosts: ScheduledPostItem[] = [];
  const updatedList: ScheduledPostItem[] = [];
  const errors: string[] = [];
  let dispatchedCount = 0;

  for (const post of posts) {
    if (post.status === "scheduled" && post.scheduled_time) {
      const scheduledDate = new Date(post.scheduled_time);
      if (!isNaN(scheduledDate.getTime()) && scheduledDate <= now) {
        // Prevent duplicate dispatches within 1 hour
        if (post.dispatched_at) {
          const lastDispatched = new Date(post.dispatched_at);
          if (
            !isNaN(lastDispatched.getTime()) &&
            now.getTime() - lastDispatched.getTime() < 3600000
          ) {
            updatedList.push(post);
            continue;
          }
        }
        duePosts.push(post);
        continue;
      }
    }
    updatedList.push(post);
  }

  for (const post of duePosts) {
    try {
      const dispatchUrl = `https://api.github.com/repos/${env.GITHUB_REPO_OWNER}/${env.GITHUB_REPO_NAME}/dispatches`;
      const clientPayload = {
        action: "approve",
        item_id: post.id,
      };

      const res = await fetch(dispatchUrl, {
        method: "POST",
        headers: {
          Accept: "application/vnd.github+json",
          Authorization: `Bearer ${env.GITHUB_DISPATCH_PAT}`,
          "User-Agent": "Edge-Relay",
          "X-GitHub-Api-Version": "2022-11-28",
        },
        body: JSON.stringify({
          event_type: "telegram-approval-action",
          client_payload: clientPayload,
        }),
      });

      if (!res.ok) {
        const text = await res.text();
        errors.push(`Failed dispatching ${post.id}: ${res.status} ${text}`);
        updatedList.push(post);
      } else {
        dispatchedCount++;
        const markedPost: ScheduledPostItem = {
          ...post,
          dispatched_at: now.toISOString(),
        };
        updatedList.push(markedPost);
        // Also update individual key
        await env.LINKEDIN_AGENT_KV.put(`scheduled:${post.id}`, JSON.stringify(markedPost));
      }
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : String(err);
      errors.push(`Error dispatching ${post.id}: ${msg}`);
      updatedList.push(post);
    }
  }

  // Update full list in KV if any post was dispatched
  if (dispatchedCount > 0) {
    await env.LINKEDIN_AGENT_KV.put("scheduled_posts", JSON.stringify(updatedList));
  }

  return {
    checked: posts.length,
    dispatched: dispatchedCount,
    errors,
  };
}
