/**
 * REST API route handlers for Desktop Control Panel integration.
 */

import { Env } from "../types";
import { inferContentType, jsonResponse, getTelegramCredentials } from "../utils";
import { broadcastEvent, handleWebSocketUpgrade } from "./ws";
import { handleScheduledPosts } from "./scheduled";
import { handleConnectionQueue } from "./connectionQueue";
import { handleScoutSchedule, defaultScoutWindows } from "./scoutSchedule";
import { rewriteDraftWithLlm, VALID_TONES } from "./llm";

// In-memory edge cache for GET /api/state to protect KV limits against burst reads
let cachedKvRef: unknown = null;
let cachedStatePayload: Record<string, unknown> | null = null;
let cachedStateTimestamp = 0;
const STATE_CACHE_TTL_MS = 30_000; // 30 seconds edge cache

export function invalidateStateCache(): void {
  cachedKvRef = null;
  cachedStatePayload = null;
  cachedStateTimestamp = 0;
}

export async function handleGetState(request: Request, env: Env): Promise<Response> {
  if (request.method !== "GET") {
    return jsonResponse({ error: "Method Not Allowed" }, 405);
  }
  if (!env.LINKEDIN_AGENT_KV) {
    return jsonResponse({ error: "KV namespace not configured" }, 500);
  }

  // Return cached state if available and within TTL to conserve KV reads/lists
  if (
    cachedKvRef === env.LINKEDIN_AGENT_KV &&
    cachedStatePayload &&
    Date.now() - cachedStateTimestamp < STATE_CACHE_TTL_MS
  ) {
    return jsonResponse({
      success: true,
      state: cachedStatePayload,
    });
  }

  // 1. Lists and gets all pending:* records
  const pending: unknown[] = [];
  let cursor: string | undefined = undefined;
  do {
    const listResult: { keys: Array<{ name: string }>; list_complete: boolean; cursor?: string } =
      await env.LINKEDIN_AGENT_KV.list({ prefix: "pending:", cursor });
    for (const key of listResult.keys) {
      const rawVal = await env.LINKEDIN_AGENT_KV.get(key.name);
      if (rawVal) {
        try {
          pending.push(JSON.parse(rawVal));
        } catch {
          pending.push(rawVal);
        }
      }
    }
    cursor = listResult.list_complete ? undefined : listResult.cursor;
  } while (cursor);

  pending.sort((a: any, b: any) => {
    const aTime = a && typeof a === "object" && a.created_at ? new Date(a.created_at).getTime() : 0;
    const bTime = b && typeof b === "object" && b.created_at ? new Date(b.created_at).getTime() : 0;
    return aTime - bTime;
  });

  // 2. daily_counters
  const rawCounters = await env.LINKEDIN_AGENT_KV.get("daily_counters");
  let dailyCounters: unknown = null;
  if (rawCounters) {
    try {
      dailyCounters = JSON.parse(rawCounters);
    } catch {
      dailyCounters = null;
    }
  }

  // 3. history
  const rawHistory = await env.LINKEDIN_AGENT_KV.get("history");
  let history: unknown[] = [];
  if (rawHistory) {
    try {
      const parsed = JSON.parse(rawHistory);
      if (Array.isArray(parsed)) {
        history = parsed;
      }
    } catch {
      history = [];
    }
  }

  // 4. incident
  const rawIncident = await env.LINKEDIN_AGENT_KV.get("incident");
  let incident: unknown = null;
  if (rawIncident) {
    try {
      incident = JSON.parse(rawIncident);
    } catch {
      incident = rawIncident;
    }
  }

  // 5. paused
  const rawPaused = await env.LINKEDIN_AGENT_KV.get("paused");
  const paused: boolean = rawPaused !== null;

  // 6. connection_queue (optional)
  const rawConnectionQueue = await env.LINKEDIN_AGENT_KV.get("connection_queue");
  let connectionQueue: unknown = null;
  if (rawConnectionQueue) {
    try {
      connectionQueue = JSON.parse(rawConnectionQueue);
    } catch {
      connectionQueue = null;
    }
  }

  // 7. scheduled_posts (optional)
  const rawScheduledPosts = await env.LINKEDIN_AGENT_KV.get("scheduled_posts");
  let scheduledPosts: unknown = null;
  if (rawScheduledPosts) {
    try {
      scheduledPosts = JSON.parse(rawScheduledPosts);
    } catch {
      scheduledPosts = null;
    }
  }

  // 8. active_threads (optional)
  const rawActiveThreads = await env.LINKEDIN_AGENT_KV.get("active_threads");
  let activeThreads: unknown = null;
  if (rawActiveThreads) {
    try {
      activeThreads = JSON.parse(rawActiveThreads);
    } catch {
      activeThreads = null;
    }
  }

  // 9. scout_schedule (optional)
  const rawScoutSchedule = await env.LINKEDIN_AGENT_KV.get("scout_schedule");
  let scoutSchedule: unknown = null;
  if (rawScoutSchedule) {
    try {
      scoutSchedule = JSON.parse(rawScoutSchedule);
    } catch {
      scoutSchedule = null;
    }
  }

  const statePayload: Record<string, unknown> = {
    pending,
    daily_counters: dailyCounters,
    history,
    incident,
    paused,
  };
  if (connectionQueue !== null) {
    statePayload.connection_queue = connectionQueue;
  }
  if (scheduledPosts !== null) {
    statePayload.scheduled_posts = scheduledPosts;
  }
  if (activeThreads !== null) {
    statePayload.active_threads = activeThreads;
  }
  if (scoutSchedule !== null) {
    statePayload.scout_schedule = scoutSchedule;
  }

  cachedKvRef = env.LINKEDIN_AGENT_KV;
  cachedStatePayload = statePayload;
  cachedStateTimestamp = Date.now();

  return jsonResponse({
    success: true,
    state: statePayload,
  });
}

export async function handlePostAction(
  request: Request,
  env: Env,
  ctx: ExecutionContext
): Promise<Response> {
  if (request.method !== "POST") {
    return jsonResponse({ error: "Method Not Allowed" }, 405);
  }

  let body: { action?: string; item_id?: string };
  try {
    body = (await request.json()) as { action?: string; item_id?: string };
  } catch {
    return jsonResponse({ error: "Invalid JSON body" }, 400);
  }

  const { action, item_id: itemId } = body || {};
  if (!action || !itemId || (action !== "approve" && action !== "reject")) {
    return jsonResponse(
      { error: "Invalid payload: action must be 'approve' or 'reject', and item_id must be provided" },
      400
    );
  }

  if (action === "reject") {
    if (!env.LINKEDIN_AGENT_KV) {
      return jsonResponse({ error: "KV namespace not configured" }, 500);
    }

    let actionType = "approve_comment";
    let telegramMessageId: number | null = null;
    let telegramChatId: number | null = null;

    try {
      const rawPending = await env.LINKEDIN_AGENT_KV.get(`pending:${itemId}`);
      if (rawPending) {
        const pending = JSON.parse(rawPending);
        actionType = pending.action_type || actionType;
        if (typeof pending.telegram_message_id === "number") {
          telegramMessageId = pending.telegram_message_id;
        }
        if (typeof pending.telegram_chat_id === "number") {
          telegramChatId = pending.telegram_chat_id;
        }
      }
    } catch {
      // Continue
    }

    // Delete pending item and secondary message index from KV
    try {
      await env.LINKEDIN_AGENT_KV.delete(`pending:${itemId}`);
      if (telegramMessageId && telegramMessageId > 0) {
        await env.LINKEDIN_AGENT_KV.delete(`msg_id:${telegramMessageId}`);
      }
    } catch {
      // Continue
    }

    // Append rejection history entry
    try {
      const rawHistory = await env.LINKEDIN_AGENT_KV.get("history");
      let history: Array<Record<string, unknown>> = [];
      if (rawHistory) {
        try {
          const parsed = JSON.parse(rawHistory);
          if (Array.isArray(parsed)) {
            history = parsed;
          }
        } catch {
          history = [];
        }
      }
      const nowIso = new Date().toISOString();
      history.push({
        item_id: itemId,
        action_type: actionType,
        final_status: "rejected",
        decided_at: nowIso,
        executed_at: nowIso,
        screenshot_path: null,
        error: "Rejected by operator via API",
      });
      await env.LINKEDIN_AGENT_KV.put("history", JSON.stringify(history));
    } catch {
      // Continue
    }

    // Also update connection_queue status if candidate exists
    try {
      const rawQueue = await env.LINKEDIN_AGENT_KV.get("connection_queue");
      if (rawQueue) {
        const queue = JSON.parse(rawQueue);
        if (Array.isArray(queue)) {
          const idx = queue.findIndex((c: any) => c.id === itemId);
          if (idx >= 0) {
            queue[idx].status = "rejected";
            await env.LINKEDIN_AGENT_KV.put("connection_queue", JSON.stringify(queue));
          }
        }
      }
    } catch {
      // Continue
    }

    // Edit linked Telegram message if known
    const targetChatId =
      telegramChatId ??
      (env.TELEGRAM_AUTHORIZED_CHAT_ID ? parseInt(env.TELEGRAM_AUTHORIZED_CHAT_ID, 10) : null);

    if (env.TELEGRAM_BOT_TOKEN && targetChatId && telegramMessageId) {
      ctx.waitUntil(
        fetch(`https://api.telegram.org/bot${env.TELEGRAM_BOT_TOKEN}/editMessageText`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            chat_id: targetChatId,
            message_id: telegramMessageId,
            text: "❌ Suggestion rejected",
            reply_markup: { inline_keyboard: [] },
          }),
        }).catch(() => {})
      );
    }

    invalidateStateCache();
    broadcastEvent({
      type: "action_executed",
      item_id: itemId,
      action: "reject",
    });

    return jsonResponse({
      success: true,
      status: "rejected",
      item_id: itemId,
    });
  }

  // action === "approve"
  let telegramMessageId: number | null = null;
  let telegramChatId: number | null = env.TELEGRAM_AUTHORIZED_CHAT_ID
    ? parseInt(env.TELEGRAM_AUTHORIZED_CHAT_ID, 10)
    : null;

  if (env.LINKEDIN_AGENT_KV) {
    try {
      const rawPending = await env.LINKEDIN_AGENT_KV.get(`pending:${itemId}`);
      if (rawPending) {
        const pending = JSON.parse(rawPending);
        if (typeof pending.telegram_message_id === "number") {
          telegramMessageId = pending.telegram_message_id;
        }
        if (typeof pending.telegram_chat_id === "number") {
          telegramChatId = pending.telegram_chat_id;
        }
        const draftText = (body as any).draft_text || (body as any).draftText;
        if (draftText && typeof draftText === "string") {
          pending.draft_text = draftText;
          await env.LINKEDIN_AGENT_KV.put(`pending:${itemId}`, JSON.stringify(pending));
        }
      }
    } catch {
      // Continue with defaults
    }

    const noteText = (body as any).note || (body as any).note_text;
    if (noteText) {
      try {
        const rawQueue = await env.LINKEDIN_AGENT_KV.get("connection_queue");
        if (rawQueue) {
          const queue = JSON.parse(rawQueue);
          if (Array.isArray(queue)) {
            const idx = queue.findIndex((c: any) => c.id === itemId);
            if (idx >= 0) {
              queue[idx].note_text = noteText;
              queue[idx].status = "approved";
              queue[idx].approved_at = new Date().toISOString();
              await env.LINKEDIN_AGENT_KV.put("connection_queue", JSON.stringify(queue));
            }
          }
        }
      } catch {
        // Continue
      }
    }
  }

  const repoOwner = (body as any).repo_owner || env.GITHUB_REPO_OWNER;
  const repoName = (body as any).repo_name || env.GITHUB_REPO_NAME;
  const pat = (body as any).github_pat || env.GITHUB_DISPATCH_PAT;

  if (!repoOwner || !repoName || !pat) {
    const missing = [
      !repoOwner && "GITHUB_REPO_OWNER",
      !repoName && "GITHUB_REPO_NAME",
      !pat && "GITHUB_DISPATCH_PAT",
    ].filter(Boolean);
    return jsonResponse(
      {
        error: "GitHub action dispatch failed: Missing configuration",
        details: `Missing required cloud dispatch settings: ${missing.join(", ")}. Please configure them in Desktop Settings or Cloudflare Worker environment.`,
        action: "approve",
        item_id: itemId,
      },
      400
    );
  }

  const dispatchUrl = `https://api.github.com/repos/${repoOwner}/${repoName}/dispatches`;
  const clientPayload = {
    action: "approve",
    item_id: itemId,
    telegram_chat_id: telegramChatId,
    telegram_message_id: telegramMessageId,
    source: "desktop_api",
  };

  let dispatchResponse: Response;
  try {
    dispatchResponse = await fetch(dispatchUrl, {
      method: "POST",
      headers: {
        Accept: "application/vnd.github+json",
        Authorization: `Bearer ${pat}`,
        "User-Agent": "Telegram-Relay-Worker",
        "X-GitHub-Api-Version": "2022-11-28",
      },
      body: JSON.stringify({
        event_type: "telegram-approval-action",
        client_payload: clientPayload,
      }),
    });
  } catch (networkError: unknown) {
    const errMsg =
      networkError instanceof Error ? networkError.message : "Network request failed";
    return jsonResponse(
      {
        error: "GitHub dispatch network failure",
        details: errMsg,
        action: "approve",
        item_id: itemId,
      },
      502
    );
  }

  if (!dispatchResponse.ok) {
    const errText = await dispatchResponse.text();
    let details = errText;
    if (
      dispatchResponse.status === 403 &&
      errText.includes("Resource not accessible by personal access token")
    ) {
      details = `${errText} -> Personal Access Token lacks workflow dispatch permission. For Classic PATs (ghp_...), check 'workflow' and 'repo' scopes. For Fine-grained PATs (github_pat_...), set Repository Permissions -> 'Actions' to 'Read and write'.`;
    }
    return jsonResponse(
      {
        error: "GitHub dispatch failed",
        status_code: dispatchResponse.status,
        status_text: dispatchResponse.statusText,
        details,
        action: "approve",
        item_id: itemId,
      },
      502
    );
  }

  if (env.TELEGRAM_BOT_TOKEN && telegramChatId && telegramMessageId) {
    ctx.waitUntil(
      fetch(`https://api.telegram.org/bot${env.TELEGRAM_BOT_TOKEN}/editMessageText`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          chat_id: telegramChatId,
          message_id: telegramMessageId,
          text: "⏳ Approval received via Desktop Panel, executing...",
          reply_markup: { inline_keyboard: [] },
        }),
      }).catch(() => {})
    );
  }

  invalidateStateCache();
  broadcastEvent({
    type: "action_executed",
    item_id: itemId,
    action: "approve",
  });

  return jsonResponse({
    success: true,
    status: "dispatched",
    action: "approve",
    item_id: itemId,
  });
}

export async function handlePostScout(request: Request, env: Env): Promise<Response> {
  if (request.method !== "POST") {
    return jsonResponse({ error: "Method Not Allowed" }, 405);
  }

  let body: {
    ref?: string;
    use_repository_dispatch?: boolean;
    repo_owner?: string;
    repo_name?: string;
    github_pat?: string;
  } = {};
  try {
    const text = await request.text();
    if (text) {
      body = JSON.parse(text);
    }
  } catch {
    // Optional body
  }

  const repoOwner = body.repo_owner || env.GITHUB_REPO_OWNER;
  const repoName = body.repo_name || env.GITHUB_REPO_NAME;
  const pat = body.github_pat || env.GITHUB_DISPATCH_PAT;

  if (!repoOwner || !repoName || !pat) {
    const missing = [
      !repoOwner && "GITHUB_REPO_OWNER",
      !repoName && "GITHUB_REPO_NAME",
      !pat && "GITHUB_DISPATCH_PAT",
    ].filter(Boolean);
    return jsonResponse(
      {
        error: "GitHub scout dispatch failed: Missing configuration",
        details: `Missing required cloud dispatch settings: ${missing.join(", ")}. Please configure them in Desktop Settings or Cloudflare Worker environment.`,
      },
      400
    );
  }

  let dispatchUrl: string;
  let dispatchBody: Record<string, unknown>;

  if (body.use_repository_dispatch) {
    dispatchUrl = `https://api.github.com/repos/${repoOwner}/${repoName}/dispatches`;
    dispatchBody = {
      event_type: "linkedin_agent_action",
      client_payload: { action: "scout" },
    };
  } else {
    dispatchUrl = `https://api.github.com/repos/${repoOwner}/${repoName}/actions/workflows/scout.yml/dispatches`;
    dispatchBody = {
      ref: body.ref || "main",
    };
  }

  let dispatchResponse: Response;
  try {
    dispatchResponse = await fetch(dispatchUrl, {
      method: "POST",
      headers: {
        Accept: "application/vnd.github+json",
        Authorization: `Bearer ${pat}`,
        "User-Agent": "Telegram-Relay-Worker",
        "X-GitHub-Api-Version": "2022-11-28",
      },
      body: JSON.stringify(dispatchBody),
    });
  } catch (networkError: unknown) {
    const errMsg =
      networkError instanceof Error ? networkError.message : "Network request failed";
    return jsonResponse(
      { error: "GitHub dispatch network failure", details: errMsg },
      502
    );
  }

  if (!dispatchResponse.ok) {
    const errText = await dispatchResponse.text();
    let details = errText;
    if (
      dispatchResponse.status === 403 &&
      errText.includes("Resource not accessible by personal access token")
    ) {
      details = `${errText} -> Personal Access Token lacks workflow dispatch permission. For Classic PATs (ghp_...), check 'workflow' and 'repo' scopes. For Fine-grained PATs (github_pat_...), set Repository Permissions -> 'Actions' to 'Read and write'.`;
    }
    return jsonResponse(
      {
        error: "GitHub scout dispatch failed",
        status_code: dispatchResponse.status,
        status_text: dispatchResponse.statusText,
        details,
      },
      502
    );
  }

  broadcastEvent({
    type: "queue_updated",
  });

  return jsonResponse({
    success: true,
    status: "scout_triggered",
  });
}

export async function handlePostIdeate(request: Request, env: Env): Promise<Response> {
  if (request.method !== "POST") {
    return jsonResponse({ error: "Method Not Allowed" }, 405);
  }

  let body: {
    ref?: string;
    use_repository_dispatch?: boolean;
    repo_owner?: string;
    repo_name?: string;
    github_pat?: string;
    dry_run?: boolean;
  } = {};
  try {
    const text = await request.text();
    if (text) {
      body = JSON.parse(text);
    }
  } catch {
    // Optional body
  }

  const repoOwner = body.repo_owner || env.GITHUB_REPO_OWNER;
  const repoName = body.repo_name || env.GITHUB_REPO_NAME;
  const pat = body.github_pat || env.GITHUB_DISPATCH_PAT;

  if (!repoOwner || !repoName || !pat) {
    const missing = [
      !repoOwner && "GITHUB_REPO_OWNER",
      !repoName && "GITHUB_REPO_NAME",
      !pat && "GITHUB_DISPATCH_PAT",
    ].filter(Boolean);
    return jsonResponse(
      {
        error: "GitHub ideation dispatch failed: Missing configuration",
        details: `Missing required cloud dispatch settings: ${missing.join(", ")}. Please configure them in Desktop Settings or Cloudflare Worker environment.`,
      },
      400
    );
  }

  let dispatchUrl: string;
  let dispatchBody: Record<string, unknown>;

  if (body.use_repository_dispatch) {
    dispatchUrl = `https://api.github.com/repos/${repoOwner}/${repoName}/dispatches`;
    dispatchBody = {
      event_type: "linkedin_agent_action",
      client_payload: { action: "ideate" },
    };
  } else {
    dispatchUrl = `https://api.github.com/repos/${repoOwner}/${repoName}/actions/workflows/ideation.yml/dispatches`;
    dispatchBody = {
      ref: body.ref || "main",
      inputs: {
        dry_run: body.dry_run ? "true" : "false",
      },
    };
  }

  let dispatchResponse: Response;
  try {
    dispatchResponse = await fetch(dispatchUrl, {
      method: "POST",
      headers: {
        Accept: "application/vnd.github+json",
        Authorization: `Bearer ${pat}`,
        "User-Agent": "Telegram-Relay-Worker",
        "X-GitHub-Api-Version": "2022-11-28",
      },
      body: JSON.stringify(dispatchBody),
    });
  } catch (networkError: unknown) {
    const errMsg =
      networkError instanceof Error ? networkError.message : "Network request failed";
    return jsonResponse(
      { error: "GitHub dispatch network failure", details: errMsg },
      502
    );
  }

  if (!dispatchResponse.ok) {
    const errText = await dispatchResponse.text();
    let details = errText;
    if (
      dispatchResponse.status === 403 &&
      errText.includes("Resource not accessible by personal access token")
    ) {
      details = `${errText} -> Personal Access Token lacks workflow dispatch permission. For Classic PATs (ghp_...), check 'workflow' and 'repo' scopes. For Fine-grained PATs (github_pat_...), set Repository Permissions -> 'Actions' to 'Read and write'.`;
    }
    return jsonResponse(
      {
        error: "GitHub ideation dispatch failed",
        status_code: dispatchResponse.status,
        status_text: dispatchResponse.statusText,
        details,
      },
      502
    );
  }

  broadcastEvent({
    type: "queue_updated",
  });

  return jsonResponse({
    success: true,
    status: "ideation_triggered",
  });
}

export async function handlePostPause(request: Request, env: Env): Promise<Response> {
  if (request.method !== "POST") {
    return jsonResponse({ error: "Method Not Allowed" }, 405);
  }
  if (!env.LINKEDIN_AGENT_KV) {
    return jsonResponse({ error: "KV namespace not configured" }, 500);
  }

  let body: { paused?: boolean };
  try {
    body = (await request.json()) as { paused?: boolean };
  } catch {
    return jsonResponse({ error: "Invalid JSON body" }, 400);
  }

  if (typeof body?.paused !== "boolean") {
    return jsonResponse({ error: "Field 'paused' must be a boolean" }, 400);
  }

  if (body.paused) {
    await env.LINKEDIN_AGENT_KV.put(
      "paused",
      JSON.stringify({ paused_at: new Date().toISOString() })
    );
  } else {
    await env.LINKEDIN_AGENT_KV.delete("paused");
  }

  invalidateStateCache();
  return jsonResponse({
    success: true,
    paused: body.paused,
  });
}

export async function handleClearIncident(request: Request, env: Env): Promise<Response> {
  if (request.method !== "POST") {
    return jsonResponse({ error: "Method Not Allowed" }, 405);
  }
  if (!env.LINKEDIN_AGENT_KV) {
    return jsonResponse({ error: "KV namespace not configured" }, 500);
  }

  await env.LINKEDIN_AGENT_KV.delete("incident");
  invalidateStateCache();

  return jsonResponse({
    success: true,
    cleared: true,
  });
}

export async function handlePostRewrite(request: Request, env: Env): Promise<Response> {
  if (request.method !== "POST") {
    return jsonResponse({ error: "Method Not Allowed" }, 405);
  }

  let body: { draft_text?: string; tone?: string; post_excerpt?: string };
  try {
    body = (await request.json()) as {
      draft_text?: string;
      tone?: string;
      post_excerpt?: string;
    };
  } catch {
    return jsonResponse({ error: "Invalid JSON body" }, 400);
  }

  const { draft_text: draftText, tone, post_excerpt: postExcerpt } = body || {};
  if (!draftText || typeof draftText !== "string" || !tone || typeof tone !== "string") {
    return jsonResponse({ error: "Fields 'draft_text' and 'tone' are required" }, 400);
  }

  if (!VALID_TONES.includes(tone as any)) {
    return jsonResponse(
      { error: `Invalid tone. Allowed tones: ${VALID_TONES.join(", ")}` },
      400
    );
  }

  if (!env.NVIDIA_NIM_API_KEY) {
    return jsonResponse({ error: "NVIDIA_NIM_API_KEY is not configured" }, 500);
  }

  let rewrittenText = "";
  try {
    rewrittenText = await rewriteDraftWithLlm(env, draftText, tone, postExcerpt);
  } catch (error: unknown) {
    const errMsg = error instanceof Error ? error.message : "LLM request failed";
    return jsonResponse({ error: "LLM rewrite request failed", details: errMsg }, 502);
  }

  return jsonResponse({
    success: true,
    rewritten_text: rewrittenText,
    rewrittenText: rewrittenText,
    draft: rewrittenText,
    tone,
  });
}

export async function handlePostSession(request: Request, env: Env): Promise<Response> {
  if (request.method !== "POST") {
    return jsonResponse({ error: "Method Not Allowed" }, 405);
  }
  if (!env.LINKEDIN_AGENT_KV) {
    return jsonResponse({ error: "KV namespace not configured" }, 500);
  }

  let body: { session_data?: string };
  try {
    body = (await request.json()) as { session_data?: string };
  } catch {
    return jsonResponse({ error: "Invalid JSON body" }, 400);
  }

  if (!body?.session_data || typeof body.session_data !== "string") {
    return jsonResponse({ error: "Field 'session_data' must be a non-empty string" }, 400);
  }

  await env.LINKEDIN_AGENT_KV.put("linkedin_session_state_enc", body.session_data);
  invalidateStateCache();

  return jsonResponse({
    success: true,
    stored: true,
  });
}

export async function handlePutMedia(
  request: Request,
  env: Env,
  url: URL
): Promise<Response> {
  const authHeader = request.headers.get("Authorization");
  if (!env.DESKTOP_API_SECRET || authHeader !== `Bearer ${env.DESKTOP_API_SECRET}`) {
    return jsonResponse({ error: "Unauthorized" }, 401);
  }

  if (!env.SCREENSHOTS_BUCKET) {
    return jsonResponse({ error: "R2 bucket not configured" }, 500);
  }

  const key = url.pathname.replace(/^\/api\/media\//, "");
  if (!key || key === "/api/media") {
    return jsonResponse({ error: "Media key is required" }, 400);
  }

  const body = await request.arrayBuffer();
  const contentType = inferContentType(key);

  await env.SCREENSHOTS_BUCKET.put(key, body, {
    httpMetadata: { contentType },
  });

  return jsonResponse({
    success: true,
    key,
    size: body.byteLength,
  });
}

export async function handleGetMedia(
  request: Request,
  env: Env,
  url: URL
): Promise<Response> {
  const authHeader = request.headers.get("Authorization");
  const queryToken = url.searchParams.get("token");
  const isAuthorized =
    Boolean(env.DESKTOP_API_SECRET) &&
    (authHeader === `Bearer ${env.DESKTOP_API_SECRET}` || queryToken === env.DESKTOP_API_SECRET);

  if (!isAuthorized) {
    return jsonResponse({ error: "Unauthorized" }, 401);
  }

  if (!env.SCREENSHOTS_BUCKET) {
    return jsonResponse({ error: "R2 bucket not configured" }, 500);
  }

  const key = url.pathname.replace(/^\/api\/media\//, "");
  if (!key || key === "/api/media") {
    return jsonResponse({ error: "Media key is required" }, 400);
  }

  const object = await env.SCREENSHOTS_BUCKET.get(key);
  if (!object) {
    return jsonResponse({ error: "Media object not found" }, 404);
  }

  const contentType = object.httpMetadata?.contentType || inferContentType(key);

  return new Response(object.body, {
    status: 200,
    headers: {
      "Content-Type": contentType,
      "Cache-Control": "public, max-age=86400",
    },
  });
}

export async function handlePostEvent(request: Request, _env: Env): Promise<Response> {
  if (request.method !== "POST") {
    return jsonResponse({ error: "Method Not Allowed" }, 405);
  }

  let body: { type?: string; [key: string]: unknown };
  try {
    body = (await request.json()) as { type?: string; [key: string]: unknown };
  } catch {
    return jsonResponse({ error: "Invalid JSON body" }, 400);
  }

  if (!body || typeof body.type !== "string" || !body.type.trim()) {
    return jsonResponse({ error: "Field 'type' is required and must be a non-empty string" }, 400);
  }

  invalidateStateCache();
  broadcastEvent(body as { type: string; [key: string]: any });

  return jsonResponse({
    success: true,
    broadcasted: true,
    event: body,
  });
}

async function handleConfig(request: Request, env: Env): Promise<Response> {
  if (!env.LINKEDIN_AGENT_KV) {
    return jsonResponse({ error: "LINKEDIN_AGENT_KV is not bound" }, 500);
  }

  if (request.method === "GET") {
    const raw = await env.LINKEDIN_AGENT_KV.get("config:runtime");
    let config = {};
    if (raw) {
      try {
        config = JSON.parse(raw);
      } catch {
        config = {};
      }
    }
    return jsonResponse({ config });
  }

  if (request.method === "PUT" || request.method === "POST") {
    try {
      const body = (await request.json()) as { config?: Record<string, unknown> };
      if (!body || typeof body !== "object") {
        return jsonResponse({ error: "Invalid JSON body" }, 400);
      }
      const incoming = (body.config || body) as Record<string, unknown>;
      const rawExisting = await env.LINKEDIN_AGENT_KV.get("config:runtime");
      let existing: Record<string, unknown> = {};
      if (rawExisting) {
        try {
          existing = JSON.parse(rawExisting);
        } catch {
          existing = {};
        }
      }
      const merged = { ...existing, ...incoming };
      await env.LINKEDIN_AGENT_KV.put("config:runtime", JSON.stringify(merged, null, 2));
      return jsonResponse({ success: true, config: merged });
    } catch (err) {
      const msg = err instanceof Error ? err.message : "Failed to update config";
      return jsonResponse({ error: msg }, 400);
    }
  }

  return jsonResponse({ error: "Method Not Allowed" }, 405);
}

async function handleVerifyTelegram(request: Request, env: Env): Promise<Response> {
  let token = "";
  if (request.method === "POST") {
    try {
      const body = (await request.json()) as { token?: string };
      token = body?.token?.trim() || "";
    } catch {
      // ignore
    }
  }

  if (!token && env.LINKEDIN_AGENT_KV) {
    try {
      const raw = await env.LINKEDIN_AGENT_KV.get("config:runtime");
      if (raw) {
        const parsed = JSON.parse(raw);
        if (parsed?.telegram_bot_token) {
          token = String(parsed.telegram_bot_token).trim();
        }
      }
    } catch {
      // ignore
    }
  }
  if (!token && env.TELEGRAM_BOT_TOKEN) {
    token = env.TELEGRAM_BOT_TOKEN.trim();
  }

  if (!token) {
    return jsonResponse({ success: false, error: "Telegram bot token is not configured" }, 400);
  }

  try {
    const res = await fetch(`https://api.telegram.org/bot${token}/getMe`);
    const data = (await res.json()) as {
      ok: boolean;
      result?: { username?: string; first_name?: string; id?: number };
      description?: string;
    };
    if (data.ok && data.result) {
      return jsonResponse({
        success: true,
        username: data.result.username,
        first_name: data.result.first_name,
        bot_id: data.result.id,
      });
    }
    return jsonResponse(
      {
        success: false,
        error: data.description || "Telegram API rejected the bot token",
      },
      400
    );
  } catch (err) {
    const msg = err instanceof Error ? err.message : "Failed to connect to Telegram API";
    return jsonResponse({ success: false, error: msg }, 502);
  }
}

export async function handleApiRequest(
  request: Request,
  env: Env,
  ctx: ExecutionContext,
  url: URL
): Promise<Response> {
  // Resolve dynamic Telegram credentials from Cloudflare KV (config:runtime) with env fallback
  const creds = await getTelegramCredentials(env);
  env = {
    ...env,
    TELEGRAM_BOT_TOKEN: creds.token || env.TELEGRAM_BOT_TOKEN,
    TELEGRAM_AUTHORIZED_CHAT_ID: creds.authorizedChatId || env.TELEGRAM_AUTHORIZED_CHAT_ID,
  };

  const pathname = url.pathname.replace(/\/+$/, "");

  // WebSocket push hub upgrade endpoint
  if (pathname === "/api/ws") {
    return handleWebSocketUpgrade(request, env, url);
  }

  // Cloudflare R2 Media Vault endpoint
  if (url.pathname === "/api/media" || url.pathname.startsWith("/api/media/")) {
    if (request.method === "PUT") {
      return handlePutMedia(request, env, url);
    }
    if (request.method === "GET") {
      return handleGetMedia(request, env, url);
    }
    return jsonResponse({ error: "Method Not Allowed" }, 405);
  }

  const authHeader = request.headers.get("Authorization");
  if (!env.DESKTOP_API_SECRET || authHeader !== `Bearer ${env.DESKTOP_API_SECRET}`) {
    return jsonResponse({ error: "Unauthorized" }, 401);
  }

  if (pathname === "/api/state") {
    return handleGetState(request, env);
  }
  if (pathname === "/api/event") {
    return handlePostEvent(request, env);
  }
  if (pathname === "/api/action") {
    return handlePostAction(request, env, ctx);
  }
  if (pathname === "/api/scout") {
    return handlePostScout(request, env);
  }
  if (pathname === "/api/ideate" || pathname === "/api/trigger-ideation") {
    return handlePostIdeate(request, env);
  }
  if (pathname === "/api/pause") {
    return handlePostPause(request, env);
  }
  if (pathname === "/api/incident/clear") {
    return handleClearIncident(request, env);
  }
  if (pathname === "/api/rewrite") {
    return handlePostRewrite(request, env);
  }
  if (pathname === "/api/session") {
    return handlePostSession(request, env);
  }
  if (pathname === "/api/scheduled-posts" || pathname.startsWith("/api/scheduled-posts/")) {
    return handleScheduledPosts(request, env, url);
  }
  if (pathname === "/api/connection-queue") {
    return handleConnectionQueue(request, env);
  }
  if (pathname === "/api/scout-schedule") {
    return handleScoutSchedule(request, env);
  }
  if (pathname === "/api/config") {
    return handleConfig(request, env);
  }
  if (pathname === "/api/telegram/verify") {
    return handleVerifyTelegram(request, env);
  }

  return jsonResponse({ error: "Not Found" }, 404);
}
