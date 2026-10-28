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
): Promise<number | null> {
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
    const res = await fetch(`https://api.telegram.org/bot${env.TELEGRAM_BOT_TOKEN}/sendMessage`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    if (res.ok) {
      const data = (await res.json()) as any;
      return typeof data?.result?.message_id === "number" ? data.result.message_id : null;
    }
  } catch {
    // Ignore notification errors
  }
  return null;
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
  const isReaction = item.action_type === "approve_reaction" || item.action_type === "reaction";

  let actionLabel = "💬 Feed Comment";
  if (isPost) actionLabel = "📝 Original Post";
  else if (isReply) actionLabel = "💬 Thread Reply";
  else if (isConn) actionLabel = "🤝 Connection Invitation";
  else if (isReaction) {
    const rx = (item.reaction_type || "like").toUpperCase();
    actionLabel = `👍 Reaction (${rx})`;
  }

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

  if (isReaction) {
    const rx = (item.reaction_type || "like").toUpperCase();
    lines.push(`<b>Proposed Reaction:</b> ${escapeHtml(rx)}`);
  } else {
    const content = item.draft_text || item.note || item.text || "";
    lines.push(`<b>Drafted Content:</b>\n<blockquote expandable>${escapeHtml(content)}</blockquote>`);

    const charCount = content.length;
    const wordCount = content.trim() ? content.trim().split(/\s+/).length : 0;
    lines.push(`<b>Metrics:</b> ${charCount} chars • ${wordCount} words`);
  }

  if (editNote) {
    lines.push(`<i>✏️ Note: ${escapeHtml(editNote)}</i>`);
  }

  lines.push(`<i>ID: ${escapeHtml(item.item_id || item.id || "")}</i>`);
  return lines.join("\n\n");
}

/** Constructs suggestion inline keyboard markup */
export function getSuggestionKeyboard(
  itemId: string,
  actionType: string = "approve_comment",
  postUrl?: string,
  includeHome: boolean = true
) {
  const cleanId = itemId.trim();
  const isReaction = actionType === "approve_reaction" || actionType === "reaction";
  let approveCode = "ac";
  if (actionType === "approve_post" || actionType === "post") {
    approveCode = "ap";
  } else if (actionType === "approve_reply" || actionType === "reply") {
    approveCode = "ar";
  } else if (actionType === "approve_connection" || actionType === "connection") {
    approveCode = "acon";
  } else if (isReaction) {
    approveCode = "areact";
  }

  const rows: Array<Array<{ text: string; callback_data?: string; url?: string }>> = [];
  if (postUrl && postUrl.trim().startsWith("http")) {
    rows.push([{ text: "🔗 View Post on LinkedIn", url: postUrl.trim() }]);
  }

  rows.push([
    { text: "✅ Approve", callback_data: `${approveCode}:${cleanId}` },
    { text: "❌ Reject", callback_data: `ask_rej:${cleanId}` },
  ]);
  if (!isReaction) {
    rows.push([
      { text: "🔄 Regenerate", callback_data: `reg:${cleanId}` },
      { text: "✏️ Edit", callback_data: `edit:${cleanId}` },
    ]);
  }
  if (includeHome) {
    rows.push([{ text: "🏠 Home Menu", callback_data: "home:menu" }]);
  }

  return { inline_keyboard: rows };
}

/** Constructs active draft editing inline keyboard markup */
export function getEditingKeyboard(itemId: string) {
  const cleanId = itemId.trim();
  return {
    inline_keyboard: [
      [
        { text: "❌ Cancel Edit", callback_data: `cx_ed:${cleanId}` },
        { text: "🏠 Home Menu", callback_data: "home:menu" },
      ],
    ],
  };
}

/** Constructs loading AI draft generation inline keyboard markup */
export function getRegeneratingKeyboard(itemId: string) {
  const cleanId = itemId.trim();
  return {
    inline_keyboard: [
      [{ text: "⏳ Generating with AI...", callback_data: `noop:${cleanId}` }],
    ],
  };
}

/** Constructs interactive review buttons for /pending list */
export function getPendingListKeyboard(
  items: Array<{ id?: string; item_id?: string; action_type?: string }>,
  maxItems: number = 5,
  includeNav: boolean = true
) {
  const rows: Array<Array<{ text: string; callback_data: string }>> = [];
  for (let i = 0; i < Math.min(items.length, maxItems); i++) {
    const item = items[i];
    const cleanId = (item.item_id || item.id || "").trim();
    if (!cleanId) continue;
    const actionType = item.action_type || "";
    let sym = "💬";
    if (actionType.includes("post")) sym = "📝";
    else if (actionType.includes("reaction")) sym = "👍";
    else if (actionType.includes("connection")) sym = "🤝";
    rows.push([
      {
        text: `${sym} Review #${i + 1} (${cleanId.slice(0, 6)})`,
        callback_data: `rev:${cleanId}`,
      },
    ]);
  }
  if (includeNav) {
    rows.push([
      { text: "🔄 Refresh Queue", callback_data: "refresh:pending" },
      { text: "🏠 Home Menu", callback_data: "home:menu" },
    ]);
  }
  return { inline_keyboard: rows };
}

/** Constructs status quick-action inline keyboard */
export function getStatusKeyboard(
  isTripped: boolean = false,
  pendingCount: number = 0,
  includeNav: boolean = true
) {
  const rows: Array<Array<{ text: string; callback_data: string }>> = [];
  if (isTripped) {
    rows.push([{ text: "🔄 Reset Circuit Breaker", callback_data: "reset_cb:global" }]);
  }
  if (pendingCount > 0) {
    rows.push([{ text: `📋 Review Pending (${pendingCount})`, callback_data: "rev:list" }]);
  }
  if (includeNav) {
    rows.push([
      { text: "🔄 Refresh Status", callback_data: "refresh:status" },
      { text: "🏠 Home Menu", callback_data: "home:menu" },
    ]);
  }
  return { inline_keyboard: rows };
}

/** Formats rejection summary card preserving context */
export function formatRejectionCard(item?: any, reason?: string): string {
  const safeItem = item || {};
  const isPost = safeItem.action_type === "approve_post" || safeItem.action_type === "post";
  const isReply = safeItem.action_type === "approve_reply" || safeItem.action_type === "reply";
  const isConn = safeItem.action_type === "approve_connection" || safeItem.action_type === "connection";
  const isReaction = safeItem.action_type === "approve_reaction" || safeItem.action_type === "reaction";
  let actionLabel = "Feed Comment";
  if (isPost) actionLabel = "Original Post";
  else if (isReply) actionLabel = "Thread Reply";
  else if (isConn) actionLabel = "Connection Request";
  else if (isReaction) actionLabel = "Post Reaction";

  const lines = [
    "<b>❌ Suggestion rejected by operator</b>",
  ];
  if (safeItem.item_id || safeItem.id) {
    lines.push(`<b>Item:</b> <code>${escapeHtml(safeItem.item_id || safeItem.id || "")}</code> (${actionLabel})`);
  }
  if (safeItem.author_name) {
    lines.push(`<b>Author:</b> ${escapeHtml(safeItem.author_name)}`);
  }
  if (safeItem.post_url) {
    lines.push(`<b>Target:</b> <a href="${escapeHtml(safeItem.post_url)}">Original Post</a>`);
  }
  if (safeItem.draft_text) {
    const preview =
      safeItem.draft_text.length > 200 ? safeItem.draft_text.slice(0, 200) + "..." : safeItem.draft_text;
    lines.push(`<b>Draft Excerpt:</b>\n<blockquote expandable>${escapeHtml(preview)}</blockquote>`);
  }
  if (reason && reason !== "skip") {
    lines.push(`<b>Feedback:</b> <i>${escapeHtml(reason)}</i>`);
  } else if (!reason) {
    lines.push("<i>Why was this suggestion rejected? (Optional feedback):</i>");
  }
  return lines.join("\n\n");
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
      [
        { text: "🏠 Home Menu", callback_data: "home:menu" },
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
        { text: "🏠 Home Menu", callback_data: "home:menu" },
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
        ],
        [
          { text: "🔙 Back to Review", callback_data: `back:${cleanId}` },
          { text: "🏠 Home Menu", callback_data: "home:menu" },
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
        { text: "🏠 Home Menu", callback_data: "home:menu" },
      ],
    ],
  };
}

/** Constructs inline keyboard for /stats report */
export function getStatsKeyboard() {
  return {
    inline_keyboard: [
      [
        { text: "🔄 Refresh Stats", callback_data: "refresh:stats" },
        { text: "🏠 Home Menu", callback_data: "home:menu" },
      ],
    ],
  };
}

/** Constructs inline keyboard for /help command */
export function getHelpKeyboard() {
  return {
    inline_keyboard: [
      [
        { text: "🏠 Home Menu", callback_data: "home:menu" },
        { text: "📊 Status Report", callback_data: "refresh:status" },
      ],
    ],
  };
}

/** Constructs inline keyboard for /home Command & Control hub */
export function getHomeKeyboard(
  isTripped: boolean = false,
  pendingCount: number = 0,
  isPaused: boolean = false
) {
  const rows: Array<Array<{ text: string; callback_data: string }>> = [];
  if (isTripped) {
    rows.push([{ text: "🔄 Reset Circuit Breaker", callback_data: "reset_cb:global" }]);
  }

  const reviewCb = pendingCount > 0 ? "rev:list" : "refresh:pending";
  const pauseText = isPaused ? "▶️ Resume Agent" : "⏸️ Pause Agent";
  const pauseCb = isPaused ? "home:resume" : "home:pause";

  rows.push([
    { text: `📋 Pending (${pendingCount})`, callback_data: reviewCb },
    { text: "📊 Status", callback_data: "refresh:status" },
  ]);
  rows.push([
    { text: "📈 Stats", callback_data: "refresh:stats" },
    { text: pauseText, callback_data: pauseCb },
  ]);
  rows.push([
    { text: "🔄 Refresh Hub", callback_data: "refresh:home" },
    { text: "❌ Close Menu", callback_data: "close:menu" },
  ]);
  return { inline_keyboard: rows };
}

/** Formats HTML message for Command & Control Home Hub */
export function formatHomeHub(
  systemState: string,
  cbStatus: string,
  pendingCount: number,
  counters: any,
  focusAreas?: string[]
): string {
  const focusStr = focusAreas && focusAreas.length > 0 ? focusAreas.join(", ") : "General";
  const dateStr = counters?.date || "Today";
  const commentsExecuted = counters?.comments_executed || 0;
  const postsExecuted = counters?.posts_executed || 0;
  const suggestionsSent = counters?.suggestions_sent || 0;

  const lines = [
    "<b>🏠 LinkedAide — Command &amp; Control Hub</b>\n",
    `• <b>System State:</b> ${systemState}`,
    `• <b>Circuit Breaker:</b> ${cbStatus}`,
    `• <b>Pending Queue:</b> <b>${pendingCount}</b> action(s) awaiting review\n`,
    `📊 <b>Today's Activity (${escapeHtml(String(dateStr))})</b>`,
    `• <b>Comments:</b> ${commentsExecuted}`,
    `• <b>Posts:</b> ${postsExecuted}`,
    `• <b>Suggestions Sent:</b> ${suggestionsSent}\n`,
    `🎯 <b>Focus Areas:</b> <i>${escapeHtml(focusStr)}</i>\n`,
    "<i>Select an option below or use docked buttons:</i>",
  ];
  return lines.join("\n");
}

/** Constructs persistent reply keyboard dock for mobile navigation */
export function getDockedReplyKeyboard(
  isPaused: boolean = false,
  inputPlaceholder: string = "Tap a button or type /help..."
) {
  return {
    keyboard: [
      [{ text: "📊 Status" }, { text: "📋 Pending Queue" }],
      [{ text: isPaused ? "▶️ Resume" : "⏸️ Pause" }, { text: "📈 Stats" }],
      [{ text: "🏠 Home Menu" }, { text: "❓ Help" }],
    ],
    resize_keyboard: true,
    is_persistent: true,
    input_field_placeholder: inputPlaceholder.slice(0, 64),
  };
}

/**
 * Resolves Telegram Bot Token and Authorized Chat ID, preferring dynamic
 * Cloudflare KV config:runtime and falling back to env variables.
 */
export async function getTelegramCredentials(
  env: Env
): Promise<{ token: string; authorizedChatId: string }> {
  let token = env.TELEGRAM_BOT_TOKEN || "";
  let authorizedChatId = env.TELEGRAM_AUTHORIZED_CHAT_ID || "";

  if (env.LINKEDIN_AGENT_KV) {
    try {
      const raw = await env.LINKEDIN_AGENT_KV.get("config:runtime");
      if (raw) {
        const parsed = JSON.parse(raw);
        if (parsed && typeof parsed === "object") {
          if (parsed.telegram_bot_token) {
            token = String(parsed.telegram_bot_token).trim();
          }
          if (parsed.telegram_authorized_chat_id) {
            authorizedChatId = String(parsed.telegram_authorized_chat_id).trim();
          }
        }
      }
    } catch {
      // In case of error, fall back to environment variables
    }
  }

  return { token, authorizedChatId };
}
