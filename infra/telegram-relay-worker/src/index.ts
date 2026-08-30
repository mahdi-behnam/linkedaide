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
}

export default {
  async fetch(request: Request, env: Env, ctx: ExecutionContext): Promise<Response> {
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
    const isApproval = actionCode === "ac" || actionCode === "ap" || actionCode === "apv";
    const isRejection = actionCode === "rc" || actionCode === "rp" || actionCode === "rej";

    if (!isApproval && !isRejection) {
      return new Response("Unknown action code", { status: 400 });
    }

    const action = isApproval ? "approve" : "reject";
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
      })
    );

    // 5. Dispatch GitHub Actions repository_dispatch event
    const dispatchUrl = `https://api.github.com/repos/${env.GITHUB_REPO_OWNER}/${env.GITHUB_REPO_NAME}/dispatches`;
    const clientPayload = {
      action: action,
      item_id: itemId,
      telegram_chat_id: cb.message?.chat.id ?? authorizedId,
      telegram_message_id: cb.message?.message_id ?? null,
      telegram_callback_query_id: cb.id,
    };

    const dispatchResponse = await fetch(dispatchUrl, {
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

    if (!dispatchResponse.ok) {
      const errText = await dispatchResponse.text();
      return new Response(`GitHub dispatch failed: ${errText}`, { status: 502 });
    }

    return new Response(JSON.stringify({ status: "dispatched", action, item_id: itemId }), {
      status: 200,
      headers: { "Content-Type": "application/json" },
    });
  },
};
