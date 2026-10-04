/**
 * Cloudflare Worker: Telegram Webhook to GitHub repository_dispatch Relay.
 *
 * Receives Telegram callback_query events, authenticates webhook secret and sender ID,
 * answers Telegram immediately with a toast notification, edits the message UI,
 * and triggers GitHub Actions repository_dispatch event with execution payload.
 */

export interface Env {
  TELEGRAM_WEBHOOK_SECRET: string;
  TELEGRAM_BOT_TOKEN: string;
  TELEGRAM_AUTHORIZED_CHAT_ID: string;
  GITHUB_DISPATCH_PAT: string;
  GITHUB_REPO_OWNER: string;
  GITHUB_REPO_NAME: string;
  LINKEDIN_AGENT_KV?: KVNamespace;
  SCREENSHOTS_BUCKET?: R2Bucket;
  DESKTOP_API_SECRET?: string;
  NVIDIA_NIM_API_KEY?: string;
  LLM_BASE_URL?: string;
}

export interface TelegramCallbackQuery {
  id: string;
  from: {
    id: number;
    is_bot: boolean;
    first_name: string;
    username?: string;
  };
  message?: {
    message_id: number;
    chat: {
      id: number;
    };
  };
  data?: string;
}

export interface TelegramUpdate {
  update_id: number;
  callback_query?: TelegramCallbackQuery;
  message?: {
    message_id: number;
    from?: {
      id: number;
      is_bot?: boolean;
      first_name?: string;
      username?: string;
    };
    chat?: {
      id: number;
    };
    text?: string;
    reply_to_message?: unknown;
  };
}

/** HTML entity escaping helper for Telegram HTML parse_mode */
export function escapeHtml(text: string): string {
  return text
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#039;");
}

/** Formats user-friendly error message for Telegram */
export function formatTelegramErrorMessage(
  action: string,
  itemId: string,
  errorSummary: string,
  errorDetails?: string
): string {
  const safeAction = escapeHtml(action);
  const safeItemId = escapeHtml(itemId);
  const safeSummary = escapeHtml(errorSummary);
  const safeDetails = errorDetails ? escapeHtml(errorDetails.slice(0, 500)) : "";

  let msg =
    `⚠️ <b>GitHub Dispatch Failed</b>\n\n` +
    `<b>Action:</b> ${safeAction}\n` +
    `<b>Item ID:</b> <code>${safeItemId}</code>\n` +
    `<b>Error:</b> <code>${safeSummary}</code>`;

  if (safeDetails) {
    msg += `\n<b>Details:</b> <code>${safeDetails}</code>`;
  }

  msg += `\n\n<i>Please check repository permissions, GitHub token, and runner status.</i>`;
  return msg;
}

/** Notifies Telegram of failure by editing message or sending alert */
export async function notifyTelegramFailure(
  env: Env,
  chatId: number,
  messageId: number | null,
  text: string
): Promise<void> {
  try {
    if (messageId) {
      await fetch(`https://api.telegram.org/bot${env.TELEGRAM_BOT_TOKEN}/editMessageText`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          chat_id: chatId,
          message_id: messageId,
          text,
          parse_mode: "HTML",
          link_preview_options: { is_disabled: true },
          reply_markup: { inline_keyboard: [] },
        }),
      });
    } else {
      await fetch(`https://api.telegram.org/bot${env.TELEGRAM_BOT_TOKEN}/sendMessage`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          chat_id: chatId,
          text,
          parse_mode: "HTML",
          link_preview_options: { is_disabled: true },
        }),
      });
    }
  } catch {
    // Silently continue if Telegram notification fails to preserve primary response
  }
}

export function jsonResponse(data: unknown, status = 200): Response {
  return new Response(JSON.stringify(data), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

/** Sends an HTML message to Telegram */
export async function sendTelegramMessage(
  env: Env,
  chatId: number,
  text: string,
  replyToMessageId?: number | null
): Promise<void> {
  const payload: Record<string, unknown> = {
    chat_id: chatId,
    text,
    parse_mode: "HTML",
    link_preview_options: { is_disabled: true },
  };
  if (typeof replyToMessageId === "number") {
    payload.reply_to_message_id = replyToMessageId;
  }
  try {
    await fetch(`https://api.telegram.org/bot${env.TELEGRAM_BOT_TOKEN}/sendMessage`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
  } catch {
    // Ignore notification errors
  }
}

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

export async function handleGetState(request: Request, env: Env): Promise<Response> {
  if (request.method !== "GET") {
    return jsonResponse({ error: "Method Not Allowed" }, 405);
  }
  if (!env.LINKEDIN_AGENT_KV) {
    return jsonResponse({ error: "KV namespace not configured" }, 500);
  }

  // 1. Lists and gets all pending:* records
  const pending: unknown[] = [];
  let cursor: string | undefined = undefined;
  do {
    const listResult: KVNamespaceListResult<unknown> =
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

  return jsonResponse({
    success: true,
    state: {
      pending,
      daily_counters: dailyCounters,
      history,
      incident,
      paused,
    },
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

    // Delete pending item from KV
    try {
      await env.LINKEDIN_AGENT_KV.delete(`pending:${itemId}`);
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
      }
    } catch {
      // Continue
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

  const validTones = [
    "technical",
    "inquisitive",
    "contrarian",
    "shorter",
    "regenerate",
    "casual",
    "concise",
  ];
  if (!validTones.includes(tone)) {
    return jsonResponse(
      { error: `Invalid tone. Allowed tones: ${validTones.join(", ")}` },
      400
    );
  }

  if (!env.NVIDIA_NIM_API_KEY) {
    return jsonResponse({ error: "NVIDIA_NIM_API_KEY is not configured" }, 500);
  }

  const baseUrl = (env.LLM_BASE_URL || "https://integrate.api.nvidia.com/v1").replace(/\/+$/, "");
  const llmUrl = `${baseUrl}/chat/completions`;

  const toneInstructions: Record<string, string> = {
    technical:
      "Rewrite with technical depth, precise industry terminology, analytical rigor, and concrete domain substance.",
    inquisitive:
      "Rewrite with an inquisitive angle, asking an engaging, open-ended question that prompts meaningful industry discussion.",
    contrarian:
      "Rewrite with a constructive contrarian perspective, politely challenging common industry assumptions with clear rationale.",
    shorter:
      "Rewrite to be concise, punchy, and direct, removing filler words while keeping the core insight.",
    regenerate:
      "Provide an alternative fresh draft with engaging domain insights, sharp perspective, and natural conversational flow.",
    casual:
      "Rewrite in a warm, approachable, conversational tone suitable for direct professional outreach.",
    concise:
      "Rewrite to be brief, clear, and high-impact within 300 characters.",
  };

  const toneModifier = toneInstructions[tone] || `Rewrite in a ${tone} tone.`;
  const systemPrompt =
    "You are an expert LinkedIn ghostwriter and editor. Your task is to rewrite a draft comment according to the specified tone instruction while preserving authenticity and professional voice. Return ONLY the rewritten text without greetings, explanations, or quotes.";

  const userPrompt = postExcerpt
    ? `Context Post:\n"${postExcerpt}"\n\nOriginal Draft:\n"${draftText}"\n\nTone Instruction:\n${toneModifier}\n\nRewritten Draft:`
    : `Original Draft:\n"${draftText}"\n\nTone Instruction:\n${toneModifier}\n\nRewritten Draft:`;

  let llmResp: Response;
  try {
    llmResp = await fetch(llmUrl, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${env.NVIDIA_NIM_API_KEY}`,
      },
      body: JSON.stringify({
        model: "nvidia/nemotron-3-super-120b-a12b",
        messages: [
          { role: "system", content: systemPrompt },
          { role: "user", content: userPrompt },
        ],
        temperature: 0.6,
        max_tokens: 500,
      }),
    });
  } catch (networkError: unknown) {
    const errMsg =
      networkError instanceof Error ? networkError.message : "LLM request failed";
    return jsonResponse({ error: "LLM network failure", details: errMsg }, 502);
  }

  if (!llmResp.ok) {
    const errText = await llmResp.text();
    return jsonResponse(
      {
        error: "LLM rewrite request failed",
        status_code: llmResp.status,
        details: errText,
      },
      502
    );
  }

  let rewrittenText = "";
  try {
    const data = (await llmResp.json()) as {
      choices?: Array<{ message?: { content?: string } }>;
    };
    rewrittenText = data.choices?.[0]?.message?.content?.trim() || "";
  } catch {
    return jsonResponse({ error: "Failed to parse LLM response JSON" }, 502);
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

  return jsonResponse({
    success: true,
    stored: true,
  });
}

export function inferContentType(key: string): string {
  const lower = key.toLowerCase();
  if (lower.endsWith(".png")) return "image/png";
  if (lower.endsWith(".jpg") || lower.endsWith(".jpeg")) return "image/jpeg";
  if (lower.endsWith(".pdf")) return "application/pdf";
  if (lower.endsWith(".webp")) return "image/webp";
  if (lower.endsWith(".gif")) return "image/gif";
  if (lower.endsWith(".svg")) return "image/svg+xml";
  return "application/octet-stream";
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

export async function handleApiRequest(
  request: Request,
  env: Env,
  ctx: ExecutionContext,
  url: URL
): Promise<Response> {
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
  if (pathname === "/api/action") {
    return handlePostAction(request, env, ctx);
  }
  if (pathname === "/api/scout") {
    return handlePostScout(request, env);
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

  return jsonResponse({ error: "Not Found" }, 404);
}

export default {
  async fetch(request: Request, env: Env, ctx: ExecutionContext): Promise<Response> {
    const url = new URL(request.url);

    // Authenticated REST API routes: /api/*
    if (url.pathname === "/api" || url.pathname.startsWith("/api/")) {
      return handleApiRequest(request, env, ctx, url);
    }

    if (request.method !== "POST") {
      return new Response("Method Not Allowed", { status: 405 });
    }

    // 1. Verify Telegram secret token header
    const secretHeader = request.headers.get("X-Telegram-Bot-Api-Secret-Token");
    if (!secretHeader || secretHeader !== env.TELEGRAM_WEBHOOK_SECRET) {
      return new Response("Unauthorized Webhook Secret", { status: 401 });
    }

    let update: TelegramUpdate;
    try {
      update = (await request.json()) as TelegramUpdate;
    } catch {
      return new Response("Invalid JSON Payload", { status: 400 });
    }

    if (update.message) {
      const msg = update.message;
      const text = (msg.text || "").trim();

      if (text.startsWith("/")) {
        const senderId = msg.from?.id;
        const authorizedId = parseInt(env.TELEGRAM_AUTHORIZED_CHAT_ID, 10);
        if (senderId !== authorizedId) {
          return new Response("Unauthorized Sender ID", { status: 403 });
        }

        const chatId = msg.chat?.id ?? authorizedId;
        const messageId = msg.message_id;
        const cmdToken = text.split(" ")[0].substring(1).split("@")[0].toLowerCase();

        if (cmdToken === "status") {
          let isPaused = false;
          let hasIncident = false;
          let incidentReason = "";
          let commentsCount = 0;
          let postsCount = 0;
          let pendingCount = 0;

          if (env.LINKEDIN_AGENT_KV) {
            const rawPaused = await env.LINKEDIN_AGENT_KV.get("paused");
            isPaused = rawPaused !== null;
            const rawIncident = await env.LINKEDIN_AGENT_KV.get("incident");
            if (rawIncident) {
              hasIncident = true;
              try {
                const inc = JSON.parse(rawIncident);
                incidentReason = inc.reason || "Incident detected";
              } catch {
                incidentReason = String(rawIncident);
              }
            }
            const rawCounters = await env.LINKEDIN_AGENT_KV.get("daily_counters");
            if (rawCounters) {
              try {
                const c = JSON.parse(rawCounters);
                commentsCount = c.comments_executed ?? 0;
                postsCount = c.posts_executed ?? 0;
              } catch {}
            }
            const listRes = await env.LINKEDIN_AGENT_KV.list({ prefix: "pending:" });
            pendingCount = listRes.keys ? listRes.keys.length : 0;
          }

          let sysStatus = "🟢 <b>Operational</b>";
          let cbStatus = "🟢 <b>Normal</b> (No active incident)";
          if (hasIncident) {
            sysStatus = "🚨 <b>Halted (Circuit Breaker Tripped)</b>";
            cbStatus = `🔴 <b>Tripped</b>\n  • <i>Reason:</i> ${escapeHtml(incidentReason)}`;
          } else if (isPaused) {
            sysStatus = "⏸️ <b>Paused</b>";
          }

          const report =
            `🎛️ <b>Agent Status Report</b>\n\n` +
            `• <b>System State:</b> ${sysStatus}\n` +
            `• <b>Circuit Breaker:</b> ${cbStatus}\n` +
            `• <b>Pending Approvals:</b> <b>${pendingCount}</b> action(s) awaiting review\n\n` +
            `📊 <b>Daily Counters</b>\n` +
            `• <b>Comments Executed:</b> ${commentsCount}\n` +
            `• <b>Posts Executed:</b> ${postsCount}`;

          await sendTelegramMessage(env, chatId, report, messageId);
          return new Response(JSON.stringify({ status: "command_handled", command: "status" }), {
            headers: { "Content-Type": "application/json" },
          });
        } else if (cmdToken === "pause") {
          if (env.LINKEDIN_AGENT_KV) {
            await env.LINKEDIN_AGENT_KV.put(
              "paused",
              JSON.stringify({ paused_at: new Date().toISOString() })
            );
          }
          const reply =
            "⏸️ <b>Agent Paused</b>\n\n" +
            "All automated scouting, triage, and execution workflows are now suspended.\n" +
            "Use /resume to restart operations.";
          await sendTelegramMessage(env, chatId, reply, messageId);
          return new Response(JSON.stringify({ status: "command_handled", command: "pause" }), {
            headers: { "Content-Type": "application/json" },
          });
        } else if (cmdToken === "resume") {
          if (env.LINKEDIN_AGENT_KV) {
            await env.LINKEDIN_AGENT_KV.delete("paused");
          }
          const reply =
            "▶️ <b>Agent Resumed</b>\n\n" +
            "Automated workflows are now active and ready to scout and execute according to schedule.";
          await sendTelegramMessage(env, chatId, reply, messageId);
          return new Response(JSON.stringify({ status: "command_handled", command: "resume" }), {
            headers: { "Content-Type": "application/json" },
          });
        } else if (cmdToken === "clear_incident") {
          if (env.LINKEDIN_AGENT_KV) {
            await env.LINKEDIN_AGENT_KV.delete("incident");
          }
          const reply =
            "✅ <b>Circuit Breaker Reset</b>\n\n" +
            "The active incident record has been cleared and the circuit breaker reset to normal.";
          await sendTelegramMessage(env, chatId, reply, messageId);
          return new Response(
            JSON.stringify({ status: "command_handled", command: "clear_incident" }),
            { headers: { "Content-Type": "application/json" } }
          );
        }
      }

      return new Response("Ignored non-callback update", { status: 200 });
    }

    const cb = update.callback_query;
    if (!cb || !cb.data) {
      return new Response("Ignored non-callback update", { status: 200 });
    }

    // 2. Validate authorized sender
    const senderId = cb.from.id;
    const authorizedId = parseInt(env.TELEGRAM_AUTHORIZED_CHAT_ID, 10);
    if (senderId !== authorizedId) {
      return new Response("Unauthorized Sender ID", { status: 403 });
    }

    // 3. Parse compact callback data (e.g. "ac:1234abcd", "rej:1234abcd")
    const parts = cb.data.split(":", 2);
    if (parts.length !== 2) {
      return new Response("Invalid callback_data format", { status: 400 });
    }

    const [actionCode, itemId] = parts;
    const isApproval = actionCode === "ac" || actionCode === "ap" || actionCode === "ar" || actionCode === "apv";
    const isRejection = actionCode === "rc" || actionCode === "rp" || actionCode === "rr" || actionCode === "rej";

    if (!isApproval && !isRejection) {
      return new Response("Unknown action code", { status: 400 });
    }

    const action = isApproval ? "approve" : "reject";

    // Fast-path: Handle rejections directly inside Cloudflare Worker via KV without GitHub Actions
    if (isRejection && env.LINKEDIN_AGENT_KV) {
      const targetChatId = cb.message?.chat.id ?? authorizedId;
      const targetMessageId = cb.message?.message_id ?? null;

      // 1. Determine action_type from pending item if present
      let actionType = "approve_comment";
      if (actionCode === "ap" || actionCode === "rp") {
        actionType = "approve_post";
      } else if (actionCode === "ar" || actionCode === "rr") {
        actionType = "approve_reply";
      }
      try {
        const rawPending = await env.LINKEDIN_AGENT_KV.get(`pending:${itemId}`);
        if (rawPending) {
          const pending = JSON.parse(rawPending);
          actionType = pending.action_type || actionType;
        }
      } catch {
        // Fallback actionType already set
      }

      // 2. Delete pending item from KV
      try {
        await env.LINKEDIN_AGENT_KV.delete(`pending:${itemId}`);
      } catch {
        // Continue
      }

      // 3. Read and append history in KV
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
          error: "Rejected by operator via Telegram",
        });
        await env.LINKEDIN_AGENT_KV.put("history", JSON.stringify(history));
      } catch {
        // Continue
      }

      // 4. Answer callback query
      ctx.waitUntil(
        fetch(`https://api.telegram.org/bot${env.TELEGRAM_BOT_TOKEN}/answerCallbackQuery`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            callback_query_id: cb.id,
            text: "❌ Suggestion rejected",
            show_alert: false,
          }),
        }).catch(() => {})
      );

      // 5. Edit Telegram message to "❌ Suggestion rejected" and remove inline keyboard
      if (targetMessageId) {
        ctx.waitUntil(
          fetch(`https://api.telegram.org/bot${env.TELEGRAM_BOT_TOKEN}/editMessageText`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
              chat_id: targetChatId,
              message_id: targetMessageId,
              text: "❌ Suggestion rejected",
              reply_markup: { inline_keyboard: [] },
            }),
          }).catch(() => {})
        );
      }

      broadcastEvent({
        type: "action_executed",
        item_id: itemId,
        action: "reject",
      });

      return new Response(
        JSON.stringify({ status: "rejected_via_kv", action: "reject", item_id: itemId }),
        {
          status: 200,
          headers: { "Content-Type": "application/json" },
        }
      );
    }

    const toastText = isApproval ? "⏳ Approval received, executing..." : "⏳ Rejection received, updating...";

    // 4. Acknowledge callback query to dismiss loading spinner in Telegram
    ctx.waitUntil(
      fetch(`https://api.telegram.org/bot${env.TELEGRAM_BOT_TOKEN}/answerCallbackQuery`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          callback_query_id: cb.id,
          text: toastText,
          show_alert: false,
        }),
      }).catch(() => {})
    );

    // 5. Dispatch GitHub Actions repository_dispatch event
    const dispatchUrl = `https://api.github.com/repos/${env.GITHUB_REPO_OWNER}/${env.GITHUB_REPO_NAME}/dispatches`;
    const targetChatId = cb.message?.chat.id ?? authorizedId;
    const targetMessageId = cb.message?.message_id ?? null;

    const clientPayload = {
      action,
      item_id: itemId,
      telegram_chat_id: targetChatId,
      telegram_message_id: targetMessageId,
      telegram_callback_query_id: cb.id,
    };

    let dispatchResponse: Response;
    try {
      dispatchResponse = await fetch(dispatchUrl, {
        method: "POST",
        headers: {
          Accept: "application/vnd.github+json",
          Authorization: `Bearer ${env.GITHUB_DISPATCH_PAT}`,
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
        networkError instanceof Error
          ? networkError.message
          : typeof networkError === "string"
            ? networkError
            : "Network request failed";
      const tgText = formatTelegramErrorMessage(action, itemId, "Network/Fetch Error", errMsg);
      ctx.waitUntil(notifyTelegramFailure(env, targetChatId, targetMessageId, tgText));

      return new Response(
        JSON.stringify({
          error: "GitHub dispatch network failure",
          details: errMsg,
          action,
          item_id: itemId,
        }),
        {
          status: 502,
          headers: { "Content-Type": "application/json" },
        }
      );
    }

    if (!dispatchResponse.ok) {
      const errText = await dispatchResponse.text();
      const statusSummary = `${dispatchResponse.status} ${dispatchResponse.statusText || ""}`.trim();
      const tgText = formatTelegramErrorMessage(action, itemId, statusSummary, errText);
      ctx.waitUntil(notifyTelegramFailure(env, targetChatId, targetMessageId, tgText));

      return new Response(
        JSON.stringify({
          error: "GitHub dispatch failed",
          status_code: dispatchResponse.status,
          status_text: dispatchResponse.statusText,
          details: errText,
          action,
          item_id: itemId,
        }),
        {
          status: 502,
          headers: { "Content-Type": "application/json" },
        }
      );
    }

    broadcastEvent({
      type: "action_executed",
      item_id: itemId,
      action,
    });

    return new Response(JSON.stringify({ status: "dispatched", action, item_id: itemId }), {
      status: 200,
      headers: { "Content-Type": "application/json" },
    });
  },
};
