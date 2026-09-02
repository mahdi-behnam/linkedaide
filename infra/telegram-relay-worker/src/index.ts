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

    return new Response(JSON.stringify({ status: "dispatched", action, item_id: itemId }), {
      status: 200,
      headers: { "Content-Type": "application/json" },
    });
  },
};
