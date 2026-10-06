/**
 * Utility helpers for formatting, response creation, and Telegram API interaction.
 */

import { Env } from "./types";

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
  replyToMessageId?: number | null,
  replyMarkup?: Record<string, unknown> | null
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
  if (replyMarkup) {
    payload.reply_markup = replyMarkup;
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

/** Formats updated pending card HTML for Telegram */
export function formatPendingCardHtml(item: Record<string, any>, editNote?: string): string {
  const isPost = item.action_type === "approve_post" || item.action_type === "post";
  const isReply = item.action_type === "approve_reply" || item.action_type === "reply";
  const isConn = item.action_type === "approve_connection" || item.action_type === "connection";

  let actionLabel = "💬 Feed Comment";
  if (isPost) actionLabel = "📝 Original Post";
  else if (isReply) actionLabel = "💬 Thread Reply";
  else if (isConn) actionLabel = "🤝 Connection Invitation";

  const lines: string[] = [
    "<b>🚀 LinkedIn Action Suggestion</b>",
    `<b>Type:</b> ${actionLabel}`,
  ];

  if (item.author_name) {
    const headline = item.author_headline ? ` (<i>${escapeHtml(item.author_headline)}</i>)` : "";
    lines.push(`<b>Author:</b> ${escapeHtml(item.author_name)}${headline}`);
  }

  if (item.post_url) {
    lines.push(`<b>Post URL:</b> <a href="${escapeHtml(item.post_url)}">View on LinkedIn</a>`);
  }

  if (item.post_excerpt && !isPost) {
    lines.push(`<b>Context:</b>\n<blockquote expandable>${escapeHtml(item.post_excerpt)}</blockquote>`);
  }

  const content = item.draft_text || item.note || item.text || "";
  lines.push(`<b>Drafted Content:</b>\n<blockquote expandable>${escapeHtml(content)}</blockquote>`);

  const charCount = content.length;
  const wordCount = content.trim() ? content.trim().split(/\s+/).length : 0;
  lines.push(`<b>Metrics:</b> ${charCount} chars • ${wordCount} words`);

  if (editNote) {
    lines.push(`<i>✏️ Note: ${escapeHtml(editNote)}</i>`);
  }

  lines.push(`<i>ID: ${escapeHtml(item.item_id || item.id || "")}</i>`);
  return lines.join("\n\n");
}

/** Constructs suggestion inline keyboard markup */
export function getSuggestionKeyboard(itemId: string, actionType: string = "approve_comment") {
  const cleanId = itemId.trim();
  let approveCode = "ac";
  if (actionType === "approve_post" || actionType === "post") {
    approveCode = "ap";
  } else if (actionType === "approve_reply" || actionType === "reply") {
    approveCode = "ar";
  } else if (actionType === "approve_connection" || actionType === "connection") {
    approveCode = "acon";
  }

  return {
    inline_keyboard: [
      [
        { text: "✅ Approve", callback_data: `${approveCode}:${cleanId}` },
        { text: "❌ Reject", callback_data: `ask_rej:${cleanId}` },
      ],
      [
        { text: "🔄 Regenerate", callback_data: `reg:${cleanId}` },
        { text: "✏️ Edit", callback_data: `edit:${cleanId}` },
      ],
    ],
  };
}

/** Constructs rejection confirmation inline keyboard markup */
export function getRejectConfirmKeyboard(itemId: string, actionType: string = "approve_comment") {
  const cleanId = itemId.trim();
  return {
    inline_keyboard: [
      [
        { text: "❌ Yes, Reject", callback_data: `cf_rej:${cleanId}` },
        { text: "🔙 Cancel / Keep", callback_data: `cx_rej:${cleanId}` },
      ],
    ],
  };
}

/** Constructs post-rejection feedback tags inline keyboard markup */
export function getRejectionFeedbackKeyboard(itemId: string) {
  const cleanId = itemId.trim();
  return {
    inline_keyboard: [
      [
        { text: "🤖 Too Generic", callback_data: `fb:generic:${cleanId}` },
        { text: "🥱 Boring", callback_data: `fb:boring:${cleanId}` },
      ],
      [
        { text: "⚠️ Too Risky", callback_data: `fb:risky:${cleanId}` },
        { text: "🚫 Off-Topic", callback_data: `fb:offtopic:${cleanId}` },
      ],
      [
        { text: "⏩ Done / Skip", callback_data: `fb:skip:${cleanId}` },
      ],
    ],
  };
}

/** Constructs dynamic inline tone picker keyboard aligned with desktop app */
export function getTonePickerKeyboard(itemId: string, actionType: string = "approve_comment") {
  const cleanId = itemId.trim();
  const isConn = actionType === "approve_connection" || actionType === "connection";
  if (isConn) {
    return {
      inline_keyboard: [
        [
          { text: "☕ Casual", callback_data: `tone:casual:${cleanId}` },
          { text: "🔬 Technical", callback_data: `tone:technical:${cleanId}` },
        ],
        [
          { text: "✂️ Concise", callback_data: `tone:concise:${cleanId}` },
          { text: "🔙 Back to Review", callback_data: `back:${cleanId}` },
        ],
      ],
    };
  }

  return {
    inline_keyboard: [
      [
        { text: "🔬 Technical", callback_data: `tone:technical:${cleanId}` },
        { text: "❓ Inquisitive", callback_data: `tone:inquisitive:${cleanId}` },
      ],
      [
        { text: "⚡ Contrarian", callback_data: `tone:contrarian:${cleanId}` },
        { text: "✂️ Shorter", callback_data: `tone:shorter:${cleanId}` },
      ],
      [
        { text: "🔙 Back to Review", callback_data: `back:${cleanId}` },
      ],
    ],
  };
}

/** Constructs persistent 2x2 reply keyboard dock for mobile navigation */
export function getDockedReplyKeyboard(isPaused: boolean = false) {
  return {
    keyboard: [
      [{ text: "📊 Status" }, { text: "📋 Pending Queue" }],
      [{ text: isPaused ? "▶️ Resume" : "⏸️ Pause" }, { text: "📈 Stats" }],
    ],
    resize_keyboard: true,
    is_persistent: true,
  };
}
