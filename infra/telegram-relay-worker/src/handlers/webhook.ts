/**
 * Telegram Webhook Handler.
 *
 * Handles incoming webhook updates from Telegram Bot API:
 * 1. Verifies X-Telegram-Bot-Api-Secret-Token
 * 2. Processes operator chat commands (/status, /pause, /resume, /clear_incident)
 * 3. Processes inline keyboard callback queries (approve / reject)
 * 4. Fast-paths rejections directly in KV without CI runner invocation
 * 5. Triggers GitHub repository_dispatch for approved actions
 */

import { Env, TelegramUpdate } from "../types";
import {
  escapeHtml,
  formatPendingCardHtml,
  formatTelegramErrorMessage,
  getSuggestionKeyboard,
  notifyTelegramFailure,
  sendTelegramMessage,
} from "../utils";
import { rewriteDraftWithLlm, VALID_TONES } from "./llm";
import { broadcastEvent } from "./ws";

export async function handleTelegramWebhook(
  request: Request,
  env: Env,
  ctx: ExecutionContext
): Promise<Response> {
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
    const isReply = !!msg.reply_to_message;
    const isCommand = text.startsWith("/");

    if (!isReply && !isCommand) {
      return new Response("Ignored non-callback update", { status: 200 });
    }

    const senderId = msg.from?.id;
    const authorizedId = parseInt(env.TELEGRAM_AUTHORIZED_CHAT_ID, 10);
    if (senderId !== authorizedId) {
      return new Response("Unauthorized Sender ID", { status: 403 });
    }

    const chatId = msg.chat?.id ?? authorizedId;
    const messageId = msg.message_id;

    // Check if operator replied to an existing suggestion message
    const repliedMsg = msg.reply_to_message as { message_id: number; text?: string } | undefined;
    if (repliedMsg && env.LINKEDIN_AGENT_KV) {
      const repliedMessageId = repliedMsg.message_id;
      const listRes = await env.LINKEDIN_AGENT_KV.list({ prefix: "pending:" });
      let matchedKey: string | null = null;
      let matchedPending: any = null;

      for (const k of listRes.keys || []) {
        const raw = await env.LINKEDIN_AGENT_KV.get(k.name);
        if (raw) {
          try {
            const parsed = JSON.parse(raw);
            if (
              parsed.telegram_message_id === repliedMessageId ||
              parsed.message_id === repliedMessageId
            ) {
              matchedKey = k.name;
              matchedPending = parsed;
              break;
            }
          } catch {}
        }
      }

      if (matchedPending && matchedKey) {
        let requestedTone: string | null = null;
        const lowerText = text.toLowerCase().trim();
        if (lowerText.startsWith("/tone ") || lowerText.startsWith("/rewrite ")) {
          requestedTone = lowerText.split(" ")[1]?.trim() || null;
        } else if (lowerText === "/regenerate" || lowerText === "regenerate") {
          requestedTone = "regenerate";
        } else if (VALID_TONES.includes(lowerText as any)) {
          requestedTone = lowerText;
        }

        let updatedDraft = "";
        if (requestedTone) {
          try {
            updatedDraft = await rewriteDraftWithLlm(
              env,
              matchedPending.draft_text || matchedPending.note || "",
              requestedTone,
              matchedPending.post_excerpt || matchedPending.target_post_content
            );
          } catch (err: any) {
            await sendTelegramMessage(
              env,
              chatId,
              `⚠️ <b>Rewrite Failed:</b> ${escapeHtml(err.message || "LLM error")}`,
              messageId
            );
            return new Response(JSON.stringify({ status: "rewrite_failed", error: err.message }), {
              status: 200,
              headers: { "Content-Type": "application/json" },
            });
          }
        } else {
          updatedDraft = text;
        }

        matchedPending.draft_text = updatedDraft;
        matchedPending.updated_at = new Date().toISOString();
        await env.LINKEDIN_AGENT_KV.put(matchedKey, JSON.stringify(matchedPending));

        broadcastEvent({
          type: "queue_updated",
          item_id: matchedPending.item_id,
        });

        // Edit original suggestion message in Telegram
        ctx.waitUntil(
          fetch(`https://api.telegram.org/bot${env.TELEGRAM_BOT_TOKEN}/editMessageText`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
              chat_id: chatId,
              message_id: repliedMessageId,
              text: formatPendingCardHtml(
                matchedPending,
                requestedTone ? `Regenerated (${requestedTone})` : "Edited by operator"
              ),
              parse_mode: "HTML",
              link_preview_options: { is_disabled: true },
              reply_markup: getSuggestionKeyboard(
                matchedPending.item_id,
                matchedPending.action_type
              ),
            }),
          }).catch(() => {})
        );

        const replyConfirmation = requestedTone
          ? `🔄 <b>Draft Regenerated (${escapeHtml(requestedTone)})</b>\n\nUpdated card above. Tap <b>✅ Approve</b> when ready.`
          : `✏️ <b>Draft Updated</b>\n\nYour revised text has been saved to the pending card above. Tap <b>✅ Approve</b> when ready.`;

        await sendTelegramMessage(env, chatId, replyConfirmation, messageId);

        return new Response(
          JSON.stringify({
            status: "draft_updated",
            item_id: matchedPending.item_id,
            mode: requestedTone ? "regenerate" : "manual_edit",
            tone: requestedTone,
          }),
          { headers: { "Content-Type": "application/json" } }
        );
      }
    }

    if (text.startsWith("/")) {
      const parts = text.split(" ");
      const cmdToken = parts[0].substring(1).split("@")[0].toLowerCase();

      if (cmdToken === "edit") {
        const targetItemId = parts[1]?.trim();
        const newDraft = parts.slice(2).join(" ").trim();
        if (!targetItemId || !newDraft) {
          await sendTelegramMessage(
            env,
            chatId,
            "ℹ️ <b>Usage:</b> <code>/edit &lt;item_id&gt; &lt;new draft text&gt;</code> or reply directly to a suggestion card.",
            messageId
          );
          return new Response(JSON.stringify({ status: "command_handled", command: "edit" }), {
            headers: { "Content-Type": "application/json" },
          });
        }
        if (env.LINKEDIN_AGENT_KV) {
          const raw = await env.LINKEDIN_AGENT_KV.get(`pending:${targetItemId}`);
          if (!raw) {
            await sendTelegramMessage(
              env,
              chatId,
              `⚠️ Pending item <code>${escapeHtml(targetItemId)}</code> not found or already executed.`,
              messageId
            );
            return new Response(JSON.stringify({ status: "item_not_found" }), {
              headers: { "Content-Type": "application/json" },
            });
          }
          const pending = JSON.parse(raw);
          pending.draft_text = newDraft;
          pending.updated_at = new Date().toISOString();
          await env.LINKEDIN_AGENT_KV.put(`pending:${targetItemId}`, JSON.stringify(pending));

          if (pending.telegram_message_id) {
            ctx.waitUntil(
              fetch(`https://api.telegram.org/bot${env.TELEGRAM_BOT_TOKEN}/editMessageText`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                  chat_id: chatId,
                  message_id: pending.telegram_message_id,
                  text: formatPendingCardHtml(pending, "Edited by operator"),
                  parse_mode: "HTML",
                  link_preview_options: { is_disabled: true },
                  reply_markup: getSuggestionKeyboard(pending.item_id, pending.action_type),
                }),
              }).catch(() => {})
            );
          }

          broadcastEvent({ type: "queue_updated", item_id: targetItemId });
          await sendTelegramMessage(
            env,
            chatId,
            `✏️ <b>Draft Updated</b> for <code>${escapeHtml(targetItemId)}</code>.`,
            messageId
          );
          return new Response(JSON.stringify({ status: "draft_updated", item_id: targetItemId }), {
            headers: { "Content-Type": "application/json" },
          });
        }
      } else if (cmdToken === "tone" || cmdToken === "rewrite") {
        const targetItemId = parts[1]?.trim();
        const requestedTone = (parts[2] || "").trim().toLowerCase();
        if (!targetItemId || !requestedTone || !VALID_TONES.includes(requestedTone as any)) {
          await sendTelegramMessage(
            env,
            chatId,
            `ℹ️ <b>Usage:</b> <code>/tone &lt;item_id&gt; &lt;tone&gt;</code>\n\nAllowed tones: ${VALID_TONES.join(", ")}\nOr reply directly to any suggestion card with the tone name.`,
            messageId
          );
          return new Response(JSON.stringify({ status: "command_handled", command: "tone" }), {
            headers: { "Content-Type": "application/json" },
          });
        }
        if (env.LINKEDIN_AGENT_KV) {
          const raw = await env.LINKEDIN_AGENT_KV.get(`pending:${targetItemId}`);
          if (!raw) {
            await sendTelegramMessage(
              env,
              chatId,
              `⚠️ Pending item <code>${escapeHtml(targetItemId)}</code> not found or already executed.`,
              messageId
            );
            return new Response(JSON.stringify({ status: "item_not_found" }), {
              headers: { "Content-Type": "application/json" },
            });
          }
          const pending = JSON.parse(raw);
          try {
            const rewritten = await rewriteDraftWithLlm(
              env,
              pending.draft_text || "",
              requestedTone,
              pending.post_excerpt || pending.target_post_content
            );
            pending.draft_text = rewritten;
            pending.updated_at = new Date().toISOString();
            await env.LINKEDIN_AGENT_KV.put(`pending:${targetItemId}`, JSON.stringify(pending));

            if (pending.telegram_message_id) {
              ctx.waitUntil(
                fetch(`https://api.telegram.org/bot${env.TELEGRAM_BOT_TOKEN}/editMessageText`, {
                  method: "POST",
                  headers: { "Content-Type": "application/json" },
                  body: JSON.stringify({
                    chat_id: chatId,
                    message_id: pending.telegram_message_id,
                    text: formatPendingCardHtml(pending, `Regenerated (${requestedTone})`),
                    parse_mode: "HTML",
                    link_preview_options: { is_disabled: true },
                    reply_markup: getSuggestionKeyboard(pending.item_id, pending.action_type),
                  }),
                }).catch(() => {})
              );
            }

            broadcastEvent({ type: "queue_updated", item_id: targetItemId });
            await sendTelegramMessage(
              env,
              chatId,
              `🔄 <b>Draft Regenerated (${escapeHtml(requestedTone)})</b> for <code>${escapeHtml(targetItemId)}</code>.`,
              messageId
            );
            return new Response(
              JSON.stringify({ status: "draft_updated", item_id: targetItemId, tone: requestedTone }),
              { headers: { "Content-Type": "application/json" } }
            );
          } catch (err: any) {
            await sendTelegramMessage(
              env,
              chatId,
              `⚠️ <b>Rewrite Failed:</b> ${escapeHtml(err.message || "LLM error")}`,
              messageId
            );
            return new Response(JSON.stringify({ status: "rewrite_failed", error: err.message }), {
              headers: { "Content-Type": "application/json" },
            });
          }
        }
      } else if (cmdToken === "status") {
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
  const isApproval =
    actionCode === "ac" ||
    actionCode === "ap" ||
    actionCode === "ar" ||
    actionCode === "apv" ||
    actionCode === "acon";
  const isRejection =
    actionCode === "rc" ||
    actionCode === "rp" ||
    actionCode === "rr" ||
    actionCode === "rej" ||
    actionCode === "rcon";
  const isEdit = actionCode === "ed" || actionCode === "edit";
  const isRegenerate = actionCode === "reg";

  if (isEdit || isRegenerate) {
    const promptText = isEdit
      ? "✏️ Reply to this suggestion with your revised draft text."
      : "🔄 Reply to this suggestion with your preferred tone or new draft.";

    ctx.waitUntil(
      fetch(`https://api.telegram.org/bot${env.TELEGRAM_BOT_TOKEN}/answerCallbackQuery`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          callback_query_id: cb.id,
          text: promptText,
          show_alert: false,
        }),
      }).catch(() => {})
    );

    return new Response(
      JSON.stringify({
        status: isEdit ? "edit_prompted" : "regenerate_prompted",
        item_id: itemId,
      }),
      {
        status: 200,
        headers: { "Content-Type": "application/json" },
      }
    );
  }

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
    if (actionCode === "rp") {
      actionType = "approve_post";
    } else if (actionCode === "rr") {
      actionType = "approve_reply";
    } else if (actionCode === "rcon") {
      actionType = "approve_connection";
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

    // 4. Update connection_queue status if candidate exists
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

    const rejectionLabel =
      actionType === "approve_connection"
        ? "❌ Connection request rejected"
        : "❌ Suggestion rejected";

    // 5. Answer callback query
    ctx.waitUntil(
      fetch(`https://api.telegram.org/bot${env.TELEGRAM_BOT_TOKEN}/answerCallbackQuery`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          callback_query_id: cb.id,
          text: rejectionLabel,
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
            text: rejectionLabel,
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
}
