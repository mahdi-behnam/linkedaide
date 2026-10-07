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
  formatHomeHub,
  formatPendingCardHtml,
  formatRejectionCard,
  formatTelegramErrorMessage,
  getDockedReplyKeyboard,
  getEditingKeyboard,
  getHelpKeyboard,
  getHomeKeyboard,
  getPendingListKeyboard,
  getRegeneratingKeyboard,
  getRejectConfirmKeyboard,
  getRejectionFeedbackKeyboard,
  getStatsKeyboard,
  getStatusKeyboard,
  getSuggestionKeyboard,
  getTonePickerKeyboard,
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
    const DOCK_MAP: Record<string, string> = {
      "📊 Status": "status",
      "📋 Pending Queue": "pending",
      "📈 Stats": "stats",
      "⏸️ Pause": "pause",
      "▶️ Resume": "resume",
      "⏸️ Pause / Resume": "pause",
      "🏠 Home Menu": "home",
      "❓ Help": "help",
    };
    const isDockButton = Boolean(DOCK_MAP[text]);
    const isVoice = Boolean(msg.voice);
    const isCommand = text.startsWith("/") || isDockButton;

    if (!isReply && !isCommand && !isVoice) {
      return new Response("Ignored non-callback update", { status: 200 });
    }

    const senderId = msg.from?.id;
    const authorizedId = parseInt(env.TELEGRAM_AUTHORIZED_CHAT_ID, 10);
    if (senderId !== authorizedId) {
      return new Response("Unauthorized Sender ID", { status: 403 });
    }

    const chatId = msg.chat?.id ?? authorizedId;
    const messageId = msg.message_id;

    if (isVoice) {
      await sendTelegramMessage(
        env,
        chatId,
        "🎙️ <b>Voice Note Received:</b>\nVoice-to-post transcription hook ready. Please type <code>/post &lt;idea&gt;</code> to draft an original post.",
        messageId
      );
      return new Response(JSON.stringify({ status: "voice_acknowledged" }), {
        headers: { "Content-Type": "application/json" },
      });
    }

    // Check if operator replied to an existing suggestion message
    const repliedMsg = msg.reply_to_message as { message_id: number; text?: string } | undefined;
    if (repliedMsg && env.LINKEDIN_AGENT_KV) {
      const repliedMessageId = repliedMsg.message_id;
      let matchedKey: string | null = null;
      let matchedPending: any = null;

      // Fast-path: O(1) direct lookup via secondary message index
      const directItemId = await env.LINKEDIN_AGENT_KV.get(`msg_id:${repliedMessageId}`);
      if (directItemId) {
        const raw = await env.LINKEDIN_AGENT_KV.get(`pending:${directItemId}`);
        if (raw) {
          try {
            matchedKey = `pending:${directItemId}`;
            matchedPending = JSON.parse(raw);
          } catch {}
        }
      }

      // Fallback: Scan pending items if not found via secondary index
      if (!matchedPending) {
        const listRes = await env.LINKEDIN_AGENT_KV.list({ prefix: "pending:" });
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
                matchedPending.action_type,
                matchedPending.post_url
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

    if (isCommand) {
      let isPaused = false;
      if (env.LINKEDIN_AGENT_KV) {
        try {
          isPaused = (await env.LINKEDIN_AGENT_KV.get("paused")) !== null;
        } catch {}
      }

      let parts: string[] = [];
      let cmdToken = "";
      if (DOCK_MAP[text]) {
        cmdToken = DOCK_MAP[text];
        parts = [cmdToken];
      } else {
        parts = text.split(" ");
        cmdToken = parts[0].substring(1).split("@")[0].toLowerCase();
      }

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
                  reply_markup: getSuggestionKeyboard(pending.item_id, pending.action_type, pending.post_url),
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
                    reply_markup: getSuggestionKeyboard(pending.item_id, pending.action_type, pending.post_url),
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

        const statusMarkup = hasIncident
          ? getStatusKeyboard(true, pendingCount)
          : getDockedReplyKeyboard(isPaused);

        await sendTelegramMessage(env, chatId, report, messageId, statusMarkup);
        return new Response(JSON.stringify({ status: "command_handled", command: "status" }), {
          headers: { "Content-Type": "application/json" },
        });
      } else if (cmdToken === "home") {
        let isPaused = false;
        let hasIncident = false;
        let incidentReason = "";
        let commentsCount = 0;
        let postsCount = 0;
        let pendingCount = 0;
        let counters: any = null;

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
              counters = JSON.parse(rawCounters);
              commentsCount = counters.comments_executed ?? 0;
              postsCount = counters.posts_executed ?? 0;
            } catch {}
          }
          const listRes = await env.LINKEDIN_AGENT_KV.list({ prefix: "pending:" });
          pendingCount = listRes.keys ? listRes.keys.length : 0;
        }

        let sysStatus = "🟢 <b>Operational</b>";
        let cbStatus = "🟢 <b>Normal</b> (No active incident)";
        if (hasIncident) {
          sysStatus = "🚨 <b>Halted (Circuit Breaker Tripped)</b>";
          cbStatus = `🔴 <b>Tripped</b> (${escapeHtml(incidentReason)})`;
        } else if (isPaused) {
          sysStatus = "⏸️ <b>Paused</b>";
        }

        const hubHtml = formatHomeHub(sysStatus, cbStatus, pendingCount, counters);
        const hubMarkup = getHomeKeyboard(hasIncident, pendingCount, isPaused);

        await sendTelegramMessage(env, chatId, hubHtml, messageId, hubMarkup);
        return new Response(JSON.stringify({ status: "command_handled", command: "home" }), {
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
        await sendTelegramMessage(env, chatId, reply, messageId, getDockedReplyKeyboard(true));
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
        await sendTelegramMessage(env, chatId, reply, messageId, getDockedReplyKeyboard(false));
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
        await sendTelegramMessage(env, chatId, reply, messageId, getDockedReplyKeyboard(isPaused));
        return new Response(
          JSON.stringify({ status: "command_handled", command: "clear_incident" }),
          { headers: { "Content-Type": "application/json" } }
        );
      } else if (cmdToken === "help" || cmdToken === "start") {
        const helpMsg =
          `🤖 <b>LinkedIn HITL Agent - Operator Commands</b>\n\n` +
          `<b>Control &amp; Monitoring:</b>\n` +
          `• <code>/status</code> — Current system health, circuit breaker &amp; daily counts\n` +
          `• <code>/pending</code> — Summary list of actions waiting for approval\n` +
          `• <code>/stats</code> — Daily activity &amp; all-time execution statistics\n` +
          `• <code>/pause</code> — Suspend scouting &amp; execution workflows\n` +
          `• <code>/resume</code> — Unpause and resume normal workflows\n` +
          `• <code>/clear_incident</code> — Reset tripped circuit breaker\n\n` +
          `<b>On-Demand Creation:</b>\n` +
          `• <code>/post &lt;idea&gt;</code> — Draft an original LinkedIn post from a concept note\n` +
          `• <code>/scout &lt;url&gt;</code> — Triage and draft a comment for a specific LinkedIn post\n\n` +
          `<b>Draft Editing &amp; Tone:</b>\n` +
          `• <code>/edit &lt;item_id&gt; &lt;text&gt;</code> — Replace draft text for an item\n` +
          `• <code>/tone &lt;item_id&gt; &lt;tone&gt;</code> — Rewrite draft with AI (${VALID_TONES.join(", ")})\n` +
          `• <i>Tip: You can also reply directly to any suggestion card with your revised draft or tone name!</i>`;

        await sendTelegramMessage(env, chatId, helpMsg, messageId, getHelpKeyboard());
        return new Response(JSON.stringify({ status: "command_handled", command: "help" }), {
          headers: { "Content-Type": "application/json" },
        });
      } else if (cmdToken === "stats") {
        let commentsExecuted = 0;
        let postsExecuted = 0;
        let connectionsSent = 0;
        let suggestionsSent = 0;
        let counterDate = "";
        let historyEntries: Array<Record<string, unknown>> = [];

        if (env.LINKEDIN_AGENT_KV) {
          const rawCounters = await env.LINKEDIN_AGENT_KV.get("daily_counters");
          if (rawCounters) {
            try {
              const c = JSON.parse(rawCounters);
              commentsExecuted = c.comments_executed ?? 0;
              postsExecuted = c.posts_executed ?? 0;
              connectionsSent = c.connections_sent ?? 0;
              suggestionsSent = c.suggestions_sent ?? 0;
              counterDate = c.date ?? "";
            } catch {}
          }
          const rawHistory = await env.LINKEDIN_AGENT_KV.get("history");
          if (rawHistory) {
            try {
              const h = JSON.parse(rawHistory);
              if (Array.isArray(h)) historyEntries = h;
            } catch {}
          }
        }

        let successCount = 0;
        let rejectedCount = 0;
        let failedCount = 0;

        for (const entry of historyEntries) {
          const status = entry.final_status;
          if (status === "executed_success") successCount++;
          else if (status === "rejected") rejectedCount++;
          else if (status === "expired" || status === "executed_failed" || status === "halted") {
            failedCount++;
          }
        }

        const totalDecided = successCount + rejectedCount;
        const approvalRate =
          totalDecided > 0 ? `${((successCount / totalDecided) * 100).toFixed(1)}%` : "N/A";

        const statsMsg =
          `📊 <b>Agent Performance &amp; Execution Stats</b>\n\n` +
          `📅 <b>Today's Counters${counterDate ? ` (${counterDate})` : ""}</b>\n` +
          `• <b>Suggestions Sent:</b> ${suggestionsSent}\n` +
          `• <b>Comments Published:</b> ${commentsExecuted}\n` +
          `• <b>Posts Published:</b> ${postsExecuted}\n` +
          `• <b>Connections Sent:</b> ${connectionsSent}\n\n` +
          `📈 <b>All-Time History (${historyEntries.length} records)</b>\n` +
          `• <b>Executed Actions:</b> ${successCount}\n` +
          `• <b>Operator Rejections:</b> ${rejectedCount}\n` +
          `• <b>Expired / Failed:</b> ${failedCount}\n` +
          `• <b>Approval Rate:</b> <b>${approvalRate}</b>`;

        await sendTelegramMessage(env, chatId, statsMsg, messageId, getStatsKeyboard());
        return new Response(JSON.stringify({ status: "command_handled", command: "stats" }), {
          headers: { "Content-Type": "application/json" },
        });
      } else if (cmdToken === "pending") {
        let keys: Array<{ name: string }> = [];
        if (env.LINKEDIN_AGENT_KV) {
          const listRes = await env.LINKEDIN_AGENT_KV.list({ prefix: "pending:" });
          keys = listRes.keys || [];
        }

        if (keys.length === 0) {
          await sendTelegramMessage(
            env,
            chatId,
            "📭 <b>No Pending Actions</b>\n\nThere are no actions currently awaiting review.",
            messageId,
            getDockedReplyKeyboard(isPaused)
          );
          return new Response(
            JSON.stringify({ status: "command_handled", command: "pending", count: 0 }),
            { headers: { "Content-Type": "application/json" } }
          );
        }

        const lines: string[] = [`📋 <b>Pending Approval Queue (${keys.length})</b>\n`];
        const displayKeys = keys.slice(0, 10);
        const pendingItems: Array<any> = [];
        for (let i = 0; i < displayKeys.length; i++) {
          if (!env.LINKEDIN_AGENT_KV) continue;
          const raw = await env.LINKEDIN_AGENT_KV.get(displayKeys[i].name);
          if (!raw) continue;
          try {
            const item = JSON.parse(raw);
            pendingItems.push(item);
            const actionType = item.action_type || "comment";
            let typeIcon = "💬 Comment";
            if (actionType === "post") typeIcon = "📝 Post";
            else if (actionType === "reply") typeIcon = "↩️ Reply";
            else if (actionType === "connect" || actionType === "connection") {
              typeIcon = "🤝 Connection";
            }

            const target = item.author || item.recipient_name || item.target_author || "";
            const draft = item.draft_text || item.note || item.text || "";
            const shortDraft = draft.length > 80 ? draft.substring(0, 77) + "..." : draft;

            lines.push(
              `${i + 1}. ${typeIcon} (<code>${escapeHtml(item.item_id)}</code>)` +
                (target ? `\n   • <i>Target:</i> ${escapeHtml(target)}` : "") +
                (shortDraft ? `\n   • <i>Draft:</i> "${escapeHtml(shortDraft)}"` : "")
            );
          } catch {}
        }
        if (keys.length > 10) {
          lines.push(`\n<i>...and ${keys.length - 10} more pending items.</i>`);
        }
        lines.push(`\n<i>Reply to any suggestion card or tap inline buttons to approve/reject.</i>`);

        const pendingMarkup = getPendingListKeyboard(pendingItems);
        await sendTelegramMessage(env, chatId, lines.join("\n"), messageId, pendingMarkup);
        return new Response(
          JSON.stringify({ status: "command_handled", command: "pending", count: keys.length }),
          { headers: { "Content-Type": "application/json" } }
        );
      } else if (cmdToken === "post") {
        const idea = parts.slice(1).join(" ").trim();
        if (!idea) {
          await sendTelegramMessage(
            env,
            chatId,
            `💡 <b>Draft an Original Post:</b>\n\nProvide an idea or topic after <code>/post</code>.\n\n<i>Example:</i> <code>/post 3 subtle pitfalls when building production agentic loops</code>`,
            messageId,
            getDockedReplyKeyboard(isPaused)
          );
          return new Response(JSON.stringify({ status: "command_handled", command: "post", prompt: true }), {
            headers: { "Content-Type": "application/json" },
          });
        }

        let draftText = idea;
        try {
          draftText = await rewriteDraftWithLlm(
            env,
            idea,
            "Create an insightful, high-value LinkedIn post based on this concept or note. Punchy opening hook, concise structured body, no generic buzzwords.",
            ""
          );
        } catch {}

        const itemId = `post_${Date.now().toString(36).slice(-6)}`;
        const pendingObj: any = {
          item_id: itemId,
          action_type: "approve_post",
          author_name: "You",
          draft_text: draftText,
          reasoning: `On-demand draft from note: ${idea.slice(0, 80)}`,
          created_at: new Date().toISOString(),
          telegram_chat_id: chatId,
        };

        if (env.LINKEDIN_AGENT_KV) {
          await env.LINKEDIN_AGENT_KV.put(`pending:${itemId}`, JSON.stringify(pendingObj));
        }

        const cardHtml = formatPendingCardHtml(pendingObj);
        const keyboard = getSuggestionKeyboard(itemId, "approve_post");
        const sentId = await sendTelegramMessage(env, chatId, cardHtml, undefined, keyboard);

        if (sentId && env.LINKEDIN_AGENT_KV) {
          pendingObj.telegram_message_id = sentId;
          await env.LINKEDIN_AGENT_KV.put(`pending:${itemId}`, JSON.stringify(pendingObj));
        }

        return new Response(
          JSON.stringify({ status: "command_handled", command: "post", item_id: itemId }),
          { headers: { "Content-Type": "application/json" } }
        );
      } else if (cmdToken === "scout") {
        const targetUrl = parts.slice(1).join(" ").trim();
        if (!targetUrl) {
          await sendTelegramMessage(
            env,
            chatId,
            `🧭 <b>On-Demand Target Scouting:</b>\n\nProvide a LinkedIn post URL after <code>/scout</code>.\n\n<i>Example:</i> <code>/scout https://www.linkedin.com/feed/update/urn:li:activity:123456789/</code>`,
            messageId,
            getDockedReplyKeyboard(isPaused)
          );
          return new Response(JSON.stringify({ status: "command_handled", command: "scout", prompt: true }), {
            headers: { "Content-Type": "application/json" },
          });
        }

        const confirmMsg =
          `🧭 <b>Target Received:</b>\n\n` +
          `Queued for on-demand scouting:\n<a href="${escapeHtml(targetUrl)}">${escapeHtml(targetUrl)}</a>\n\n` +
          `<i>The agent will evaluate this target against your focus areas and deliver a draft comment card for your review.</i>`;
        await sendTelegramMessage(env, chatId, confirmMsg, messageId, getDockedReplyKeyboard(isPaused));

        if (env.GITHUB_DISPATCH_PAT && env.GITHUB_REPO_OWNER && env.GITHUB_REPO_NAME) {
          try {
            const dispatchUrl = `https://api.github.com/repos/${env.GITHUB_REPO_OWNER}/${env.GITHUB_REPO_NAME}/dispatches`;
            ctx.waitUntil(
              fetch(dispatchUrl, {
                method: "POST",
                headers: {
                  Accept: "application/vnd.github+json",
                  Authorization: `Bearer ${env.GITHUB_DISPATCH_PAT}`,
                  "User-Agent": "Telegram-Relay-Worker",
                  "X-GitHub-Api-Version": "2022-11-28",
                },
                body: JSON.stringify({
                  event_type: "scout-target",
                  client_payload: { target_url: targetUrl, telegram_chat_id: chatId },
                }),
              }).catch(() => {})
            );
          } catch {}
        }

        return new Response(
          JSON.stringify({ status: "command_handled", command: "scout", target_url: targetUrl }),
          { headers: { "Content-Type": "application/json" } }
        );
      } else {
        const unknownMsg = `❓ <b>Unknown Command:</b> <code>/${escapeHtml(cmdToken)}</code>\n\nUse the buttons below or send <code>/help</code> for available commands.`;
        await sendTelegramMessage(env, chatId, unknownMsg, messageId, getDockedReplyKeyboard(isPaused));
        return new Response(JSON.stringify({ status: "command_handled", command: "unknown" }), {
          headers: { "Content-Type": "application/json" },
        });
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

  // 3. Parse compact callback data (e.g. "ac:1234abcd", "tone:technical:1234abcd")
  const parts = cb.data.split(":");
  if (parts.length < 2) {
    return new Response("Invalid callback_data format", { status: 400 });
  }

  const actionCode = parts[0];
  const itemId = parts.length === 2 ? parts[1] : parts[parts.length - 1];
  const targetChatId = cb.message?.chat.id ?? authorizedId;
  const targetMessageId = cb.message?.message_id ?? null;

  if (actionCode === "reg") {
    let actionType = "approve_comment";
    if (env.LINKEDIN_AGENT_KV) {
      try {
        const rawPending = await env.LINKEDIN_AGENT_KV.get(`pending:${itemId}`);
        if (rawPending) {
          const parsed = JSON.parse(rawPending);
          actionType = parsed.action_type || actionType;
        }
      } catch {}
    }

    ctx.waitUntil(
      fetch(`https://api.telegram.org/bot${env.TELEGRAM_BOT_TOKEN}/answerCallbackQuery`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          callback_query_id: cb.id,
          text: "Choose draft tone style:",
          show_alert: false,
        }),
      }).catch(() => {})
    );

    if (targetMessageId) {
      ctx.waitUntil(
        fetch(`https://api.telegram.org/bot${env.TELEGRAM_BOT_TOKEN}/editMessageReplyMarkup`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            chat_id: targetChatId,
            message_id: targetMessageId,
            reply_markup: getTonePickerKeyboard(itemId, actionType),
          }),
        }).catch(() => {})
      );
    }

    return new Response(
      JSON.stringify({ status: "tone_menu_displayed", item_id: itemId }),
      { status: 200, headers: { "Content-Type": "application/json" } }
    );
  }

  if (actionCode === "back") {
    let actionType = "approve_comment";
    let postUrl: string | undefined = undefined;
    if (env.LINKEDIN_AGENT_KV) {
      try {
        const rawPending = await env.LINKEDIN_AGENT_KV.get(`pending:${itemId}`);
        if (rawPending) {
          const parsed = JSON.parse(rawPending);
          actionType = parsed.action_type || actionType;
          postUrl = parsed.post_url;
        }
      } catch {}
    }

    ctx.waitUntil(
      fetch(`https://api.telegram.org/bot${env.TELEGRAM_BOT_TOKEN}/answerCallbackQuery`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          callback_query_id: cb.id,
          text: "Back to suggestion review",
          show_alert: false,
        }),
      }).catch(() => {})
    );

    if (targetMessageId) {
      ctx.waitUntil(
        fetch(`https://api.telegram.org/bot${env.TELEGRAM_BOT_TOKEN}/editMessageReplyMarkup`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            chat_id: targetChatId,
            message_id: targetMessageId,
            reply_markup: getSuggestionKeyboard(itemId, actionType, postUrl),
          }),
        }).catch(() => {})
      );
    }

    return new Response(
      JSON.stringify({ status: "back_to_review", item_id: itemId }),
      { status: 200, headers: { "Content-Type": "application/json" } }
    );
  }

  if (actionCode === "tone") {
    const toneSlug = parts[1];
    const targetItemId = parts[2];
    if (!toneSlug || !targetItemId || !VALID_TONES.includes(toneSlug as any)) {
      return new Response("Invalid tone parameters", { status: 400 });
    }

    if (!env.LINKEDIN_AGENT_KV) {
      return new Response("KV not configured", { status: 500 });
    }

    const raw = await env.LINKEDIN_AGENT_KV.get(`pending:${targetItemId}`);
    if (!raw) {
      ctx.waitUntil(
        fetch(`https://api.telegram.org/bot${env.TELEGRAM_BOT_TOKEN}/answerCallbackQuery`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            callback_query_id: cb.id,
            text: "⚠️ Suggestion is no longer pending or already processed.",
            show_alert: true,
          }),
        }).catch(() => {})
      );
      return new Response(JSON.stringify({ status: "item_not_found" }), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      });
    }

    const pending = JSON.parse(raw);

    // Show generating progress indicator on suggestion keyboard
    if (targetMessageId) {
      ctx.waitUntil(
        fetch(`https://api.telegram.org/bot${env.TELEGRAM_BOT_TOKEN}/editMessageReplyMarkup`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            chat_id: targetChatId,
            message_id: targetMessageId,
            reply_markup: getRegeneratingKeyboard(targetItemId),
          }),
        }).catch(() => {})
      );
    }

    try {
      const rewritten = await rewriteDraftWithLlm(
        env,
        pending.draft_text || pending.note || "",
        toneSlug,
        pending.post_excerpt || pending.target_post_content
      );
      pending.draft_text = rewritten;
      pending.updated_at = new Date().toISOString();
      await env.LINKEDIN_AGENT_KV.put(`pending:${targetItemId}`, JSON.stringify(pending));

      if (targetMessageId) {
        ctx.waitUntil(
          fetch(`https://api.telegram.org/bot${env.TELEGRAM_BOT_TOKEN}/editMessageText`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
              chat_id: targetChatId,
              message_id: targetMessageId,
              text: formatPendingCardHtml(pending, `Regenerated (${toneSlug})`),
              parse_mode: "HTML",
              link_preview_options: { is_disabled: true },
              reply_markup: getSuggestionKeyboard(pending.item_id, pending.action_type, pending.post_url),
            }),
          }).catch(() => {})
        );
      }

      ctx.waitUntil(
        fetch(`https://api.telegram.org/bot${env.TELEGRAM_BOT_TOKEN}/answerCallbackQuery`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            callback_query_id: cb.id,
            text: `🔄 Draft updated (${toneSlug})`,
            show_alert: false,
          }),
        }).catch(() => {})
      );

      broadcastEvent({ type: "queue_updated", item_id: targetItemId });
      return new Response(
        JSON.stringify({ status: "draft_updated", item_id: targetItemId, tone: toneSlug }),
        { status: 200, headers: { "Content-Type": "application/json" } }
      );
    } catch (err: any) {
      if (targetMessageId) {
        ctx.waitUntil(
          fetch(`https://api.telegram.org/bot${env.TELEGRAM_BOT_TOKEN}/editMessageReplyMarkup`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
              chat_id: targetChatId,
              message_id: targetMessageId,
              reply_markup: getSuggestionKeyboard(pending.item_id, pending.action_type, pending.post_url),
            }),
          }).catch(() => {})
        );
      }

      ctx.waitUntil(
        fetch(`https://api.telegram.org/bot${env.TELEGRAM_BOT_TOKEN}/answerCallbackQuery`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            callback_query_id: cb.id,
            text: `⚠️ Rewrite failed: ${err.message || "LLM error"}`,
            show_alert: true,
          }),
        }).catch(() => {})
      );
      return new Response(JSON.stringify({ status: "rewrite_failed", error: err.message }), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      });
    }
  }

  if (actionCode === "ed" || actionCode === "edit") {
    ctx.waitUntil(
      fetch(`https://api.telegram.org/bot${env.TELEGRAM_BOT_TOKEN}/answerCallbackQuery`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          callback_query_id: cb.id,
          text: "✏️ Enter your revised draft text below.",
          show_alert: false,
        }),
      }).catch(() => {})
    );

    if (targetMessageId) {
      ctx.waitUntil(
        fetch(`https://api.telegram.org/bot${env.TELEGRAM_BOT_TOKEN}/editMessageReplyMarkup`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            chat_id: targetChatId,
            message_id: targetMessageId,
            reply_markup: getEditingKeyboard(itemId),
          }),
        }).catch(() => {})
      );
    }

    ctx.waitUntil(
      fetch(`https://api.telegram.org/bot${env.TELEGRAM_BOT_TOKEN}/sendMessage`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          chat_id: targetChatId,
          text: `✏️ <b>Editing Draft</b> (<code>${escapeHtml(itemId)}</code>)\n\nType your revised text in the reply box below:`,
          parse_mode: "HTML",
          reply_parameters: targetMessageId ? { message_id: targetMessageId } : undefined,
          reply_markup: {
            force_reply: true,
            input_field_placeholder: "Enter revised draft text...",
          },
        }),
      }).catch(() => {})
    );

    return new Response(
      JSON.stringify({ status: "edit_prompted", item_id: itemId }),
      { status: 200, headers: { "Content-Type": "application/json" } }
    );
  }

  if (actionCode === "cx_ed") {
    let actionType = "approve_comment";
    let postUrl: string | undefined = undefined;
    if (env.LINKEDIN_AGENT_KV) {
      try {
        const rawPending = await env.LINKEDIN_AGENT_KV.get(`pending:${itemId}`);
        if (rawPending) {
          const parsed = JSON.parse(rawPending);
          actionType = parsed.action_type || actionType;
          postUrl = parsed.post_url;
        }
      } catch {}
    }

    ctx.waitUntil(
      fetch(`https://api.telegram.org/bot${env.TELEGRAM_BOT_TOKEN}/answerCallbackQuery`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          callback_query_id: cb.id,
          text: "Edit cancelled.",
          show_alert: false,
        }),
      }).catch(() => {})
    );

    if (targetMessageId) {
      ctx.waitUntil(
        fetch(`https://api.telegram.org/bot${env.TELEGRAM_BOT_TOKEN}/editMessageReplyMarkup`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            chat_id: targetChatId,
            message_id: targetMessageId,
            reply_markup: getSuggestionKeyboard(itemId, actionType, postUrl),
          }),
        }).catch(() => {})
      );
    }

    return new Response(
      JSON.stringify({ status: "edit_cancelled", item_id: itemId }),
      { status: 200, headers: { "Content-Type": "application/json" } }
    );
  }

  if (actionCode === "rev") {
    if (itemId === "list") {
      let keys: Array<{ name: string }> = [];
      if (env.LINKEDIN_AGENT_KV) {
        const listRes = await env.LINKEDIN_AGENT_KV.list({ prefix: "pending:" });
        keys = listRes.keys || [];
      }
      ctx.waitUntil(
        fetch(`https://api.telegram.org/bot${env.TELEGRAM_BOT_TOKEN}/answerCallbackQuery`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            callback_query_id: cb.id,
            text: `Queue has ${keys.length} pending action(s).`,
            show_alert: false,
          }),
        }).catch(() => {})
      );
      return new Response(
        JSON.stringify({ status: "pending_list_prompted", count: keys.length }),
        { status: 200, headers: { "Content-Type": "application/json" } }
      );
    }

    if (env.LINKEDIN_AGENT_KV) {
      const raw = await env.LINKEDIN_AGENT_KV.get(`pending:${itemId}`);
      if (raw) {
        try {
          const pending = JSON.parse(raw);
          const cardHtml = formatPendingCardHtml(pending);
          const keyboard = getSuggestionKeyboard(itemId, pending.action_type, pending.post_url);
          const sentId = await sendTelegramMessage(env, targetChatId, cardHtml, undefined, keyboard);
          if (sentId) {
            pending.telegram_message_id = sentId;
            await env.LINKEDIN_AGENT_KV.put(`pending:${itemId}`, JSON.stringify(pending));
          }

          ctx.waitUntil(
            fetch(`https://api.telegram.org/bot${env.TELEGRAM_BOT_TOKEN}/answerCallbackQuery`, {
              method: "POST",
              headers: { "Content-Type": "application/json" },
              body: JSON.stringify({
                callback_query_id: cb.id,
                text: `Opening #${itemId}...`,
                show_alert: false,
              }),
            }).catch(() => {})
          );

          return new Response(
            JSON.stringify({ status: "review_opened", item_id: itemId }),
            { status: 200, headers: { "Content-Type": "application/json" } }
          );
        } catch {}
      }
    }

    ctx.waitUntil(
      fetch(`https://api.telegram.org/bot${env.TELEGRAM_BOT_TOKEN}/answerCallbackQuery`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          callback_query_id: cb.id,
          text: "⚠️ Item no longer pending or already processed.",
          show_alert: true,
        }),
      }).catch(() => {})
    );

    return new Response(
      JSON.stringify({ status: "item_not_found", item_id: itemId }),
      { status: 200, headers: { "Content-Type": "application/json" } }
    );
  }

  if (actionCode === "reset_cb") {
    if (env.LINKEDIN_AGENT_KV) {
      await env.LINKEDIN_AGENT_KV.delete("incident");
    }
    ctx.waitUntil(
      fetch(`https://api.telegram.org/bot${env.TELEGRAM_BOT_TOKEN}/answerCallbackQuery`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          callback_query_id: cb.id,
          text: "✅ Circuit breaker reset.",
          show_alert: false,
        }),
      }).catch(() => {})
    );

    if (targetMessageId) {
      ctx.waitUntil(
        fetch(`https://api.telegram.org/bot${env.TELEGRAM_BOT_TOKEN}/editMessageText`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            chat_id: targetChatId,
            message_id: targetMessageId,
            text: "✅ <b>Circuit Breaker Reset</b>\n\nThe active incident record has been cleared and the circuit breaker reset to normal.",
            parse_mode: "HTML",
            reply_markup: { inline_keyboard: [] },
          }),
        }).catch(() => {})
      );
    }

    return new Response(
      JSON.stringify({ status: "circuit_breaker_reset" }),
      { status: 200, headers: { "Content-Type": "application/json" } }
    );
  }

  if (actionCode === "noop") {
    ctx.waitUntil(
      fetch(`https://api.telegram.org/bot${env.TELEGRAM_BOT_TOKEN}/answerCallbackQuery`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          callback_query_id: cb.id,
          text: "⏳ Generating draft with AI, please wait...",
          show_alert: false,
        }),
      }).catch(() => {})
    );
    return new Response(
      JSON.stringify({ status: "noop_acknowledged" }),
      { status: 200, headers: { "Content-Type": "application/json" } }
    );
  }

  if (actionCode === "ask_rej") {
    let actionType = "approve_comment";
    if (env.LINKEDIN_AGENT_KV) {
      try {
        const rawPending = await env.LINKEDIN_AGENT_KV.get(`pending:${itemId}`);
        if (rawPending) {
          const parsed = JSON.parse(rawPending);
          actionType = parsed.action_type || actionType;
        }
      } catch {}
    }

    ctx.waitUntil(
      fetch(`https://api.telegram.org/bot${env.TELEGRAM_BOT_TOKEN}/answerCallbackQuery`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          callback_query_id: cb.id,
          text: "⚠️ Confirm rejection",
          show_alert: false,
        }),
      }).catch(() => {})
    );

    if (targetMessageId) {
      ctx.waitUntil(
        fetch(`https://api.telegram.org/bot${env.TELEGRAM_BOT_TOKEN}/editMessageReplyMarkup`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            chat_id: targetChatId,
            message_id: targetMessageId,
            reply_markup: getRejectConfirmKeyboard(itemId, actionType),
          }),
        }).catch(() => {})
      );
    }

    return new Response(
      JSON.stringify({ status: "reject_confirmation_prompted", item_id: itemId }),
      { status: 200, headers: { "Content-Type": "application/json" } }
    );
  }

  if (actionCode === "cx_rej") {
    let actionType = "approve_comment";
    let postUrl: string | undefined = undefined;
    if (env.LINKEDIN_AGENT_KV) {
      try {
        const rawPending = await env.LINKEDIN_AGENT_KV.get(`pending:${itemId}`);
        if (rawPending) {
          const parsed = JSON.parse(rawPending);
          actionType = parsed.action_type || actionType;
          postUrl = parsed.post_url;
        }
      } catch {}
    }

    ctx.waitUntil(
      fetch(`https://api.telegram.org/bot${env.TELEGRAM_BOT_TOKEN}/answerCallbackQuery`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          callback_query_id: cb.id,
          text: "Rejection cancelled. Suggestion kept.",
          show_alert: false,
        }),
      }).catch(() => {})
    );

    if (targetMessageId) {
      ctx.waitUntil(
        fetch(`https://api.telegram.org/bot${env.TELEGRAM_BOT_TOKEN}/editMessageReplyMarkup`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            chat_id: targetChatId,
            message_id: targetMessageId,
            reply_markup: getSuggestionKeyboard(itemId, actionType, postUrl),
          }),
        }).catch(() => {})
      );
    }

    return new Response(
      JSON.stringify({ status: "reject_cancelled", item_id: itemId }),
      { status: 200, headers: { "Content-Type": "application/json" } }
    );
  }

  if (actionCode === "fb") {
    const feedbackReason = parts[1];
    const targetItemId = parts[2];

    if (feedbackReason !== "skip" && env.LINKEDIN_AGENT_KV) {
      try {
        const rawFb = await env.LINKEDIN_AGENT_KV.get("rejection_feedback");
        let fbList: Array<any> = [];
        if (rawFb) {
          try {
            fbList = JSON.parse(rawFb);
            if (!Array.isArray(fbList)) fbList = [];
          } catch {}
        }
        fbList.push({
          item_id: targetItemId,
          reason: feedbackReason,
          created_at: new Date().toISOString(),
        });
        if (fbList.length > 200) fbList = fbList.slice(-200);
        await env.LINKEDIN_AGENT_KV.put("rejection_feedback", JSON.stringify(fbList));
      } catch {}
    }

    const toastMsg =
      feedbackReason === "skip" ? "Feedback dismissed." : `Feedback saved (${feedbackReason}). Thank you!`;
    ctx.waitUntil(
      fetch(`https://api.telegram.org/bot${env.TELEGRAM_BOT_TOKEN}/answerCallbackQuery`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          callback_query_id: cb.id,
          text: toastMsg,
          show_alert: false,
        }),
      }).catch(() => {})
    );

    if (targetMessageId) {
      let pendingObj: any = undefined;
      if (env.LINKEDIN_AGENT_KV) {
        try {
          const raw = await env.LINKEDIN_AGENT_KV.get(`pending:${targetItemId}`);
          if (raw) pendingObj = JSON.parse(raw);
        } catch {}
      }
      const finalText = formatRejectionCard(pendingObj, feedbackReason);
      ctx.waitUntil(
        fetch(`https://api.telegram.org/bot${env.TELEGRAM_BOT_TOKEN}/editMessageText`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            chat_id: targetChatId,
            message_id: targetMessageId,
            text: finalText,
            parse_mode: "HTML",
            link_preview_options: { is_disabled: true },
            reply_markup: { inline_keyboard: [] },
          }),
        }).catch(() => {})
      );
    }

    return new Response(
      JSON.stringify({ status: "feedback_recorded", reason: feedbackReason, item_id: targetItemId }),
      { status: 200, headers: { "Content-Type": "application/json" } }
    );
  }

  if (actionCode === "home") {
    const subAction = parts[1] || "menu";
    let toast = "🏠 Control Hub";

    if (subAction === "pause") {
      if (env.LINKEDIN_AGENT_KV) {
        await env.LINKEDIN_AGENT_KV.put(
          "paused",
          JSON.stringify({ paused_at: new Date().toISOString() })
        );
      }
      toast = "⏸️ Agent paused";
      broadcastEvent({ type: "agent_paused" });
    } else if (subAction === "resume") {
      if (env.LINKEDIN_AGENT_KV) {
        await env.LINKEDIN_AGENT_KV.delete("paused");
      }
      toast = "▶️ Agent resumed";
      broadcastEvent({ type: "agent_resumed" });
    }

    ctx.waitUntil(
      fetch(`https://api.telegram.org/bot${env.TELEGRAM_BOT_TOKEN}/answerCallbackQuery`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          callback_query_id: cb.id,
          text: toast,
          show_alert: false,
        }),
      }).catch(() => {})
    );

    let isPaused = false;
    let hasIncident = false;
    let incidentReason = "";
    let commentsCount = 0;
    let postsCount = 0;
    let pendingCount = 0;
    let counters: any = null;

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
          counters = JSON.parse(rawCounters);
          commentsCount = counters.comments_executed ?? 0;
          postsCount = counters.posts_executed ?? 0;
        } catch {}
      }
      const listRes = await env.LINKEDIN_AGENT_KV.list({ prefix: "pending:" });
      pendingCount = listRes.keys ? listRes.keys.length : 0;
    }

    let sysStatus = "🟢 <b>Operational</b>";
    let cbStatus = "🟢 <b>Normal</b> (No active incident)";
    if (hasIncident) {
      sysStatus = "🚨 <b>Halted (Circuit Breaker Tripped)</b>";
      cbStatus = `🔴 <b>Tripped</b> (${escapeHtml(incidentReason)})`;
    } else if (isPaused) {
      sysStatus = "⏸️ <b>Paused</b>";
    }

    const hubHtml = formatHomeHub(sysStatus, cbStatus, pendingCount, counters);
    const hubMarkup = getHomeKeyboard(hasIncident, pendingCount, isPaused);

    if (targetMessageId) {
      ctx.waitUntil(
        fetch(`https://api.telegram.org/bot${env.TELEGRAM_BOT_TOKEN}/editMessageText`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            chat_id: targetChatId,
            message_id: targetMessageId,
            text: hubHtml,
            parse_mode: "HTML",
            link_preview_options: { is_disabled: true },
            reply_markup: hubMarkup,
          }),
        }).catch(() => {})
      );
    }

    return new Response(
      JSON.stringify({ status: "home_displayed", sub_action: subAction, paused: isPaused }),
      { status: 200, headers: { "Content-Type": "application/json" } }
    );
  }

  if (actionCode === "close") {
    ctx.waitUntil(
      fetch(`https://api.telegram.org/bot${env.TELEGRAM_BOT_TOKEN}/answerCallbackQuery`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          callback_query_id: cb.id,
          text: "Menu closed.",
          show_alert: false,
        }),
      }).catch(() => {})
    );

    if (targetMessageId) {
      ctx.waitUntil(
        fetch(`https://api.telegram.org/bot${env.TELEGRAM_BOT_TOKEN}/deleteMessage`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            chat_id: targetChatId,
            message_id: targetMessageId,
          }),
        }).then(async (res) => {
          if (!res.ok) {
            await fetch(`https://api.telegram.org/bot${env.TELEGRAM_BOT_TOKEN}/editMessageReplyMarkup`, {
              method: "POST",
              headers: { "Content-Type": "application/json" },
              body: JSON.stringify({
                chat_id: targetChatId,
                message_id: targetMessageId,
                reply_markup: { inline_keyboard: [] },
              }),
            });
          }
        }).catch(() => {})
      );
    }

    return new Response(
      JSON.stringify({ status: "menu_closed" }),
      { status: 200, headers: { "Content-Type": "application/json" } }
    );
  }

  if (actionCode === "refresh") {
    const subAction = parts[1] || "home";

    if (subAction === "status") {
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

      const statusMarkup = getStatusKeyboard(hasIncident, pendingCount, true);

      ctx.waitUntil(
        fetch(`https://api.telegram.org/bot${env.TELEGRAM_BOT_TOKEN}/answerCallbackQuery`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            callback_query_id: cb.id,
            text: "🔄 Status refreshed",
            show_alert: false,
          }),
        }).catch(() => {})
      );

      if (targetMessageId) {
        ctx.waitUntil(
          fetch(`https://api.telegram.org/bot${env.TELEGRAM_BOT_TOKEN}/editMessageText`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
              chat_id: targetChatId,
              message_id: targetMessageId,
              text: report,
              parse_mode: "HTML",
              link_preview_options: { is_disabled: true },
              reply_markup: statusMarkup,
            }),
          }).catch(() => {})
        );
      }

      return new Response(
        JSON.stringify({ status: "status_refreshed" }),
        { status: 200, headers: { "Content-Type": "application/json" } }
      );
    }

    if (subAction === "pending") {
      let keys: Array<{ name: string }> = [];
      if (env.LINKEDIN_AGENT_KV) {
        const listRes = await env.LINKEDIN_AGENT_KV.list({ prefix: "pending:" });
        keys = listRes.keys || [];
      }

      ctx.waitUntil(
        fetch(`https://api.telegram.org/bot${env.TELEGRAM_BOT_TOKEN}/answerCallbackQuery`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            callback_query_id: cb.id,
            text: `Queue refreshed (${keys.length} items)`,
            show_alert: false,
          }),
        }).catch(() => {})
      );

      let textContent = "";
      let pendingMarkup: any;

      if (keys.length === 0) {
        textContent = "📭 <b>No Pending Actions</b>\n\nThere are no actions currently awaiting review.";
        pendingMarkup = getPendingListKeyboard([], 5, true);
      } else {
        const lines: string[] = [`📋 <b>Pending Approval Queue (${keys.length})</b>\n`];
        const displayKeys = keys.slice(0, 10);
        const pendingItems: Array<any> = [];
        for (let i = 0; i < displayKeys.length; i++) {
          if (!env.LINKEDIN_AGENT_KV) continue;
          const raw = await env.LINKEDIN_AGENT_KV.get(displayKeys[i].name);
          if (!raw) continue;
          try {
            const item = JSON.parse(raw);
            pendingItems.push(item);
            const actionType = item.action_type || "comment";
            let typeIcon = "💬 Comment";
            if (actionType === "post") typeIcon = "📝 Post";
            else if (actionType === "reply") typeIcon = "↩️ Reply";
            else if (actionType === "connect" || actionType === "connection") {
              typeIcon = "🤝 Connection";
            }

            const target = item.author || item.recipient_name || item.target_author || "";
            const draft = item.draft_text || item.note || item.text || "";
            const shortDraft = draft.length > 80 ? draft.substring(0, 77) + "..." : draft;

            lines.push(
              `${i + 1}. ${typeIcon} (<code>${escapeHtml(item.item_id)}</code>)` +
                (target ? `\n   • <i>Target:</i> ${escapeHtml(target)}` : "") +
                (shortDraft ? `\n   • <i>Draft:</i> "${escapeHtml(shortDraft)}"` : "")
            );
          } catch {}
        }
        if (keys.length > 10) {
          lines.push(`\n<i>...and ${keys.length - 10} more pending items.</i>`);
        }
        lines.push(`\n<i>Reply to any suggestion card or tap inline buttons to approve/reject.</i>`);
        textContent = lines.join("\n");
        pendingMarkup = getPendingListKeyboard(pendingItems, 5, true);
      }

      if (targetMessageId) {
        ctx.waitUntil(
          fetch(`https://api.telegram.org/bot${env.TELEGRAM_BOT_TOKEN}/editMessageText`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
              chat_id: targetChatId,
              message_id: targetMessageId,
              text: textContent,
              parse_mode: "HTML",
              link_preview_options: { is_disabled: true },
              reply_markup: pendingMarkup,
            }),
          }).catch(() => {})
        );
      }

      return new Response(
        JSON.stringify({ status: "pending_refreshed", count: keys.length }),
        { status: 200, headers: { "Content-Type": "application/json" } }
      );
    }

    if (subAction === "stats") {
      let commentsExecuted = 0;
      let postsExecuted = 0;
      let connectionsSent = 0;
      let suggestionsSent = 0;
      let counterDate = "";
      let historyEntries: Array<Record<string, unknown>> = [];

      if (env.LINKEDIN_AGENT_KV) {
        const rawCounters = await env.LINKEDIN_AGENT_KV.get("daily_counters");
        if (rawCounters) {
          try {
            const c = JSON.parse(rawCounters);
            commentsExecuted = c.comments_executed ?? 0;
            postsExecuted = c.posts_executed ?? 0;
            connectionsSent = c.connections_sent ?? 0;
            suggestionsSent = c.suggestions_sent ?? 0;
            counterDate = c.date ?? "";
          } catch {}
        }
        const rawHistory = await env.LINKEDIN_AGENT_KV.get("history");
        if (rawHistory) {
          try {
            const h = JSON.parse(rawHistory);
            if (Array.isArray(h)) historyEntries = h;
          } catch {}
        }
      }

      let successCount = 0;
      let rejectedCount = 0;
      let failedCount = 0;

      for (const entry of historyEntries) {
        const status = entry.final_status;
        if (status === "executed_success") successCount++;
        else if (status === "rejected") rejectedCount++;
        else if (status === "expired" || status === "executed_failed" || status === "halted") {
          failedCount++;
        }
      }

      const totalDecided = successCount + rejectedCount;
      const approvalRate =
        totalDecided > 0 ? `${((successCount / totalDecided) * 100).toFixed(1)}%` : "N/A";

      const statsMsg =
        `📊 <b>Agent Performance &amp; Execution Stats</b>\n\n` +
        `📅 <b>Today's Counters${counterDate ? ` (${counterDate})` : ""}</b>\n` +
        `• <b>Suggestions Sent:</b> ${suggestionsSent}\n` +
        `• <b>Comments Published:</b> ${commentsExecuted}\n` +
        `• <b>Posts Published:</b> ${postsExecuted}\n` +
        `• <b>Connections Sent:</b> ${connectionsSent}\n\n` +
        `📈 <b>All-Time History (${historyEntries.length} records)</b>\n` +
        `• <b>Executed Actions:</b> ${successCount}\n` +
        `• <b>Operator Rejections:</b> ${rejectedCount}\n` +
        `• <b>Expired / Failed:</b> ${failedCount}\n` +
        `• <b>Approval Rate:</b> <b>${approvalRate}</b>`;

      ctx.waitUntil(
        fetch(`https://api.telegram.org/bot${env.TELEGRAM_BOT_TOKEN}/answerCallbackQuery`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            callback_query_id: cb.id,
            text: "🔄 Stats refreshed",
            show_alert: false,
          }),
        }).catch(() => {})
      );

      if (targetMessageId) {
        ctx.waitUntil(
          fetch(`https://api.telegram.org/bot${env.TELEGRAM_BOT_TOKEN}/editMessageText`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
              chat_id: targetChatId,
              message_id: targetMessageId,
              text: statsMsg,
              parse_mode: "HTML",
              link_preview_options: { is_disabled: true },
              reply_markup: getStatsKeyboard(),
            }),
          }).catch(() => {})
        );
      }

      return new Response(
        JSON.stringify({ status: "stats_refreshed" }),
        { status: 200, headers: { "Content-Type": "application/json" } }
      );
    }

    // Default: refresh home hub
    let isPaused = false;
    let hasIncident = false;
    let incidentReason = "";
    let commentsCount = 0;
    let postsCount = 0;
    let pendingCount = 0;
    let counters: any = null;

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
          counters = JSON.parse(rawCounters);
          commentsCount = counters.comments_executed ?? 0;
          postsCount = counters.posts_executed ?? 0;
        } catch {}
      }
      const listRes = await env.LINKEDIN_AGENT_KV.list({ prefix: "pending:" });
      pendingCount = listRes.keys ? listRes.keys.length : 0;
    }

    let sysStatus = "🟢 <b>Operational</b>";
    let cbStatus = "🟢 <b>Normal</b> (No active incident)";
    if (hasIncident) {
      sysStatus = "🚨 <b>Halted (Circuit Breaker Tripped)</b>";
      cbStatus = `🔴 <b>Tripped</b> (${escapeHtml(incidentReason)})`;
    } else if (isPaused) {
      sysStatus = "⏸️ <b>Paused</b>";
    }

    const hubHtml = formatHomeHub(sysStatus, cbStatus, pendingCount, counters);
    const hubMarkup = getHomeKeyboard(hasIncident, pendingCount, isPaused);

    ctx.waitUntil(
      fetch(`https://api.telegram.org/bot${env.TELEGRAM_BOT_TOKEN}/answerCallbackQuery`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          callback_query_id: cb.id,
          text: "🔄 Hub refreshed",
          show_alert: false,
        }),
      }).catch(() => {})
    );

    if (targetMessageId) {
      ctx.waitUntil(
        fetch(`https://api.telegram.org/bot${env.TELEGRAM_BOT_TOKEN}/editMessageText`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            chat_id: targetChatId,
            message_id: targetMessageId,
            text: hubHtml,
            parse_mode: "HTML",
            link_preview_options: { is_disabled: true },
            reply_markup: hubMarkup,
          }),
        }).catch(() => {})
      );
    }

    return new Response(
      JSON.stringify({ status: "home_refreshed" }),
      { status: 200, headers: { "Content-Type": "application/json" } }
    );
  }

  const isApproval =
    actionCode === "ac" ||
    actionCode === "ap" ||
    actionCode === "ar" ||
    actionCode === "apv" ||
    actionCode === "acon";
  const isRejection =
    actionCode === "cf_rej" ||
    actionCode === "rc" ||
    actionCode === "rp" ||
    actionCode === "rr" ||
    actionCode === "rej" ||
    actionCode === "rcon";

  if (!isApproval && !isRejection) {
    return new Response("Unknown action code", { status: 400 });
  }

  const action = isApproval ? "approve" : "reject";

  // Fast-path: Handle rejections directly inside Cloudflare Worker via KV without GitHub Actions
  if (isRejection && env.LINKEDIN_AGENT_KV) {
    // 1. Determine action_type from pending item if present
    let actionType = "approve_comment";
    if (actionCode === "rp") {
      actionType = "approve_post";
    } else if (actionCode === "rr") {
      actionType = "approve_reply";
    } else if (actionCode === "rcon") {
      actionType = "approve_connection";
    }
    let tgMsgId: number | null = null;
    let pendingObj: any = null;
    try {
      const rawPending = await env.LINKEDIN_AGENT_KV.get(`pending:${itemId}`);
      if (rawPending) {
        const pending = JSON.parse(rawPending);
        pendingObj = pending;
        actionType = pending.action_type || actionType;
        if (pending.telegram_message_id) {
          tgMsgId = Number(pending.telegram_message_id);
        }
      }
    } catch {
      // Fallback actionType already set
    }

    // 2. Delete pending item and secondary message index from KV
    try {
      await env.LINKEDIN_AGENT_KV.delete(`pending:${itemId}`);
      if (tgMsgId && tgMsgId > 0) {
        await env.LINKEDIN_AGENT_KV.delete(`msg_id:${tgMsgId}`);
      }
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

    // 6. Edit Telegram message to show rejection and offer optional feedback tags
    if (targetMessageId) {
      const rejectionPromptHtml = formatRejectionCard(pendingObj);

      ctx.waitUntil(
        fetch(`https://api.telegram.org/bot${env.TELEGRAM_BOT_TOKEN}/editMessageText`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            chat_id: targetChatId,
            message_id: targetMessageId,
            text: rejectionPromptHtml,
            parse_mode: "HTML",
            link_preview_options: { is_disabled: true },
            reply_markup: getRejectionFeedbackKeyboard(itemId),
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

  // Progressive lifecycle step 1/3: Update card text to Queued for Execution and strip keyboard
  if (isApproval && targetMessageId) {
    let queuedMsg = `⏳ <b>[1/3] Queued for Execution</b> (GitHub Actions / Runner)\n\n<b>Item:</b> <code>${escapeHtml(itemId)}</code>`;
    if (env.LINKEDIN_AGENT_KV) {
      try {
        const rawPending = await env.LINKEDIN_AGENT_KV.get(`pending:${itemId}`);
        if (rawPending) {
          const parsed = JSON.parse(rawPending);
          if (parsed.author_name) {
            queuedMsg += `\n<b>Author:</b> ${escapeHtml(parsed.author_name)}`;
          }
          if (parsed.draft_text) {
            const preview =
              parsed.draft_text.length > 120
                ? parsed.draft_text.slice(0, 120) + "..."
                : parsed.draft_text;
            queuedMsg += `\n<b>Draft:</b> <i>${escapeHtml(preview)}</i>`;
          }
        }
      } catch {}
    }

    ctx.waitUntil(
      fetch(`https://api.telegram.org/bot${env.TELEGRAM_BOT_TOKEN}/editMessageText`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          chat_id: targetChatId,
          message_id: targetMessageId,
          text: queuedMsg,
          parse_mode: "HTML",
          reply_markup: { inline_keyboard: [] },
        }),
      }).catch(() => {})
    );
  }

  // 5. Dispatch GitHub Actions repository_dispatch event
  const dispatchUrl = `https://api.github.com/repos/${env.GITHUB_REPO_OWNER}/${env.GITHUB_REPO_NAME}/dispatches`;

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
