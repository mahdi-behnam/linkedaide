"""Telegram inline keyboard callback query handlers.

Architecture Invariants:
- Human approval invariant: callback actions inspect or revise pending state, never trigger writes directly.
- Strict authorization: unauthorized senders receive zero state mutation and no response.
- Safety & Reliability: safe fallback to tone guidance if LLM draft regeneration fails.
"""

from __future__ import annotations

import html
import logging
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from agent.config import Settings
from agent.models import (
    CallbackDataPayload,
    EngagementStyle,
    HistoryEntry,
)
from agent.safety.circuit_breaker import is_halted
from agent.state.base import BaseStateStore
from agent.telegram.client import TelegramClient
from agent.telegram.keyboards import (
    build_editing_keyboard,
    build_home_keyboard,
    build_pending_list_keyboard,
    build_regenerating_keyboard,
    build_reject_confirm_keyboard,
    build_rejection_feedback_keyboard,
    build_stats_keyboard,
    build_status_keyboard,
    build_suggestion_keyboard,
    build_tone_keyboard,
    format_home_hub,
    format_rejection_card,
    format_suggestion_card,
)

logger = logging.getLogger(__name__)


async def execute_edit_callback(
    state_store: BaseStateStore,
    telegram: TelegramClient,
    item_id: str,
    callback_query_id: str | None = None,
    chat_id: int | None = None,
    message_id: int | None = None,
) -> bool:
    """Handle edit:<item_id> callback query by prompting the operator with ForceReply.

    Args:
        state_store: Durable state store instance.
        telegram: Telegram client instance.
        item_id: ID of the pending item to edit.
        callback_query_id: Telegram callback query ID to answer.
        chat_id: Optional Telegram chat ID.
        message_id: Optional message ID of the suggestion.

    Returns:
        bool: True if handled, False if item not found or dropped.
    """
    pending = state_store.read_pending(item_id)
    if pending is None:
        if callback_query_id:
            await telegram.answer_callback_query(
                callback_query_id,
                text="⚠️ Suggestion is no longer pending or has already been processed.",
                show_alert=True,
            )
        return False

    if callback_query_id:
        await telegram.answer_callback_query(
            callback_query_id,
            text="✏️ Reply to this suggestion with your revised draft text.",
            show_alert=False,
        )

    if chat_id is not None and message_id is not None:
        kb = build_editing_keyboard(item_id)
        await telegram.edit_message_reply_markup(
            chat_id=chat_id,
            message_id=message_id,
            reply_markup=kb,
        )
        prompt_markup = {
            "force_reply": True,
            "input_field_placeholder": "Enter revised draft text...",
        }
        await telegram.send_message(
            chat_id=chat_id,
            text=f"✏️ <b>Edit Draft ({item_id}):</b>\nPlease type or paste your revised text below.",
            reply_markup=prompt_markup,
            reply_to_message_id=message_id,
        )
    return True


async def execute_cancel_edit_callback(
    state_store: BaseStateStore,
    telegram: TelegramClient,
    item_id: str,
    callback_query_id: str | None = None,
    chat_id: int | None = None,
    message_id: int | None = None,
) -> bool:
    """Cancel active draft editing and restore normal suggestion keyboard."""
    pending = state_store.read_pending(item_id)
    action_type = pending.action_type if pending else "approve_comment"
    post_url = pending.post_url if pending else None

    if callback_query_id:
        await telegram.answer_callback_query(
            callback_query_id,
            text="Editing cancelled.",
            show_alert=False,
        )

    if chat_id is not None and message_id is not None:
        kb = build_suggestion_keyboard(item_id, action_type, post_url=post_url)
        await telegram.edit_message_reply_markup(
            chat_id=chat_id,
            message_id=message_id,
            reply_markup=kb,
        )

    return True


async def execute_review_callback(
    state_store: BaseStateStore,
    telegram: TelegramClient,
    item_id: str,
    callback_query_id: str | None = None,
    chat_id: int | None = None,
) -> bool:
    """Pull up and display an existing pending suggestion card."""
    pending = state_store.read_pending(item_id)
    if pending is None:
        if callback_query_id:
            await telegram.answer_callback_query(
                callback_query_id,
                text="⚠️ Suggestion is no longer pending or has already been processed.",
                show_alert=True,
            )
        return False

    if callback_query_id:
        await telegram.answer_callback_query(
            callback_query_id,
            text=f"Viewing suggestion {item_id}",
            show_alert=False,
        )

    if chat_id is not None:
        await telegram.send_suggestion(pending)
    return True


async def execute_reset_circuit_breaker_callback(
    state_store: BaseStateStore,
    telegram: TelegramClient,
    callback_query_id: str | None = None,
    chat_id: int | None = None,
    message_id: int | None = None,
) -> bool:
    """Reset circuit breaker directly from status inline keyboard."""
    cleared = state_store.clear_incident()
    toast = "Circuit breaker reset to normal." if cleared else "No active incident found."
    if callback_query_id:
        await telegram.answer_callback_query(
            callback_query_id,
            text=toast,
            show_alert=False,
        )
    if chat_id is not None and message_id is not None:
        await telegram.edit_message_text(
            chat_id=chat_id,
            message_id=message_id,
            text="✅ <b>Circuit Breaker Reset</b>\nIncident cleared. Operational state normal.",
            reply_markup={"inline_keyboard": []},
        )
    return True


async def execute_noop_callback(
    telegram: TelegramClient,
    callback_query_id: str | None = None,
) -> bool:
    """Handle click on temporary loading status button."""
    if callback_query_id:
        await telegram.answer_callback_query(
            callback_query_id,
            text="⏳ AI draft generation in progress...",
            show_alert=False,
        )
    return True


async def execute_reject_prompt_callback(
    state_store: BaseStateStore,
    telegram: TelegramClient,
    item_id: str,
    callback_query_id: str | None = None,
    chat_id: int | None = None,
    message_id: int | None = None,
) -> bool:
    """Prompt operator with inline confirmation before rejecting suggestion."""
    pending = state_store.read_pending(item_id)
    action_type = pending.action_type if pending else "approve_comment"

    if callback_query_id:
        await telegram.answer_callback_query(
            callback_query_id,
            text="⚠️ Confirm rejection",
            show_alert=False,
        )

    if chat_id is not None and message_id is not None:
        kb = build_reject_confirm_keyboard(item_id, action_type)
        await telegram.edit_message_reply_markup(
            chat_id=chat_id,
            message_id=message_id,
            reply_markup=kb,
        )

    return True


async def execute_reject_cancel_callback(
    state_store: BaseStateStore,
    telegram: TelegramClient,
    item_id: str,
    callback_query_id: str | None = None,
    chat_id: int | None = None,
    message_id: int | None = None,
) -> bool:
    """Cancel rejection confirmation and restore standard suggestion keyboard."""
    pending = state_store.read_pending(item_id)
    action_type = pending.action_type if pending else "approve_comment"

    if callback_query_id:
        await telegram.answer_callback_query(
            callback_query_id,
            text="Rejection cancelled. Suggestion kept.",
            show_alert=False,
        )

    if chat_id is not None and message_id is not None:
        kb = build_suggestion_keyboard(item_id, action_type)
        await telegram.edit_message_reply_markup(
            chat_id=chat_id,
            message_id=message_id,
            reply_markup=kb,
        )

    return True


async def execute_reject_confirm_callback(
    state_store: BaseStateStore,
    telegram: TelegramClient,
    item_id: str,
    callback_query_id: str | None = None,
    chat_id: int | None = None,
    message_id: int | None = None,
) -> bool:
    """Confirm operator rejection, update durable state, and present feedback tags."""
    pending = state_store.read_pending(item_id)
    action_type = pending.action_type if pending else "approve_comment"

    state_store.delete_pending(item_id)
    now = datetime.now(UTC)
    entry = HistoryEntry(
        item_id=item_id,
        action_type=action_type,
        final_status="rejected",
        decided_at=now,
        executed_at=now,
        error="Rejected by operator via Telegram",
    )
    state_store.append_history(entry)

    rejection_label = (
        "❌ Connection request rejected"
        if action_type == "approve_connection"
        else "❌ Suggestion rejected"
    )

    if callback_query_id:
        await telegram.answer_callback_query(
            callback_query_id,
            text=rejection_label,
            show_alert=False,
        )

    if chat_id is not None and message_id is not None:
        rejection_prompt_html = (
            format_rejection_card(pending)
            if pending
            else f"<b>{html.escape(rejection_label)}</b>\n\n<i>Why was this suggestion rejected? (Optional feedback):</i>"
        )
        await telegram.edit_message_text(
            chat_id=chat_id,
            message_id=message_id,
            text=rejection_prompt_html,
            reply_markup=build_rejection_feedback_keyboard(item_id),
        )

    return True


async def execute_feedback_callback(
    state_store: BaseStateStore,
    telegram: TelegramClient,
    item_id: str,
    reason: str,
    callback_query_id: str | None = None,
    chat_id: int | None = None,
    message_id: int | None = None,
) -> bool:
    """Record rejection feedback reason and clear inline keyboard."""
    if reason != "skip":
        state_store.append_rejection_feedback(item_id, reason)

    toast_msg = "Feedback dismissed." if reason == "skip" else f"Feedback saved ({reason}). Thank you!"

    if callback_query_id:
        await telegram.answer_callback_query(
            callback_query_id,
            text=toast_msg,
            show_alert=False,
        )

    if chat_id is not None and message_id is not None:
        pending = state_store.read_pending(item_id)
        if pending is not None:
            final_text = format_rejection_card(pending, reason=reason)
        else:
            final_text = (
                f"❌ <b>Suggestion rejected by operator</b> (<code>{html.escape(item_id)}</code>)\n<i>Feedback: {html.escape(reason)}</i>"
                if reason != "skip"
                else f"❌ <b>Suggestion rejected by operator</b> (<code>{html.escape(item_id)}</code>)"
            )
        await telegram.edit_message_text(
            chat_id=chat_id,
            message_id=message_id,
            text=final_text,
            reply_markup={"inline_keyboard": []},
        )

    return True


async def execute_tone_menu_callback(
    state_store: BaseStateStore,
    telegram: TelegramClient,
    item_id: str,
    callback_query_id: str | None = None,
    chat_id: int | None = None,
    message_id: int | None = None,
) -> bool:
    """Display tone options sub-menu when operator taps Regenerate."""
    pending = state_store.read_pending(item_id)
    action_type = pending.action_type if pending else "approve_comment"

    if callback_query_id:
        await telegram.answer_callback_query(
            callback_query_id,
            text="Choose draft tone style:",
            show_alert=False,
        )

    if chat_id is not None and message_id is not None:
        kb = build_tone_keyboard(item_id, action_type)
        await telegram.edit_message_reply_markup(
            chat_id=chat_id,
            message_id=message_id,
            reply_markup=kb,
        )

    return True


async def execute_back_callback(
    state_store: BaseStateStore,
    telegram: TelegramClient,
    item_id: str,
    callback_query_id: str | None = None,
    chat_id: int | None = None,
    message_id: int | None = None,
) -> bool:
    """Return to standard suggestion review keyboard from tone picker."""
    pending = state_store.read_pending(item_id)
    action_type = pending.action_type if pending else "approve_comment"

    if callback_query_id:
        await telegram.answer_callback_query(
            callback_query_id,
            text="Back to suggestion review",
            show_alert=False,
        )

    if chat_id is not None and message_id is not None:
        kb = build_suggestion_keyboard(item_id, action_type)
        await telegram.edit_message_reply_markup(
            chat_id=chat_id,
            message_id=message_id,
            reply_markup=kb,
        )

    return True


async def execute_tone_select_callback(
    state_store: BaseStateStore,
    telegram: TelegramClient,
    item_id: str,
    tone: str,
    callback_query_id: str | None = None,
    chat_id: int | None = None,
    message_id: int | None = None,
    llm_service: Any | None = None,
) -> bool:
    """Handle tone selection: rewrite draft via LLM, update pending state, and re-render card."""
    pending = state_store.read_pending(item_id)
    if pending is None:
        if callback_query_id:
            await telegram.answer_callback_query(
                callback_query_id,
                text="⚠️ Suggestion is no longer pending or has already been processed.",
                show_alert=True,
            )
        return False

    if callback_query_id:
        await telegram.answer_callback_query(
            callback_query_id,
            text=f"🔄 Regenerating ({tone})...",
            show_alert=False,
        )

    target_msg_id = message_id or pending.telegram_message_id
    if chat_id is not None and target_msg_id is not None:
        try:
            loading_kb = build_regenerating_keyboard(pending.item_id)
            await telegram.edit_message_reply_markup(
                chat_id=chat_id,
                message_id=target_msg_id,
                reply_markup=loading_kb,
            )
        except Exception as kb_err:
            logger.debug("Failed to set loading keyboard during rewrite: %s", kb_err)

    new_draft: str | None = None
    if llm_service is not None:
        try:
            if hasattr(llm_service, "rewrite_draft"):
                res = await llm_service.rewrite_draft(
                    draft_text=pending.draft_text or "",
                    tone=tone,
                    post_excerpt=pending.post_excerpt or "",
                )
                if isinstance(res, str) and res.strip():
                    new_draft = res.strip()

            if not new_draft and hasattr(llm_service, "draft_comment") and pending.post_excerpt:
                tone_style_map = {
                    "technical": EngagementStyle.TECHNICAL_DEEP_DIVE,
                    "inquisitive": EngagementStyle.INQUISITIVE_QUESTION,
                    "contrarian": EngagementStyle.CONTRARIAN_PERSPECTIVE,
                    "shorter": EngagementStyle.SUPPORTIVE_SYNTHESIS,
                    "casual": EngagementStyle.SUPPORTIVE_SYNTHESIS,
                    "concise": EngagementStyle.SUPPORTIVE_SYNTHESIS,
                }
                style = tone_style_map.get(tone.lower(), EngagementStyle.TECHNICAL_DEEP_DIVE)
                draft_res = await llm_service.draft_comment(
                    post_text=pending.post_excerpt,
                    author_name=pending.author_name or "LinkedIn Creator",
                    engagement_style=style,
                )
                candidate = (
                    draft_res.draft_comment
                    if hasattr(draft_res, "draft_comment")
                    else getattr(draft_res, "comment_text", None)
                )
                if isinstance(candidate, str) and candidate.strip():
                    new_draft = candidate.strip()
        except Exception as err:
            logger.warning("Failed to regenerate draft via LLM for tone %s: %s", tone, err)
            if callback_query_id:
                try:
                    await telegram.answer_callback_query(
                        callback_query_id,
                        text=f"⚠️ Rewrite failed: {err}",
                        show_alert=True,
                    )
                except Exception:
                    pass

    if new_draft and isinstance(new_draft, str):
        updated = state_store.update_pending_draft(pending.item_id, new_draft)
        if updated is not None:
            pending = updated

    if chat_id is not None and target_msg_id is not None:
        card_text = format_suggestion_card(pending)
        kb = build_suggestion_keyboard(
            pending.item_id, pending.action_type, post_url=pending.post_url
        )
        await telegram.edit_message_text(
            chat_id=chat_id,
            message_id=target_msg_id,
            text=card_text,
            reply_markup=kb,
        )

    return True


async def execute_regenerate_callback(
    state_store: BaseStateStore,
    telegram: TelegramClient,
    item_id: str,
    callback_query_id: str | None = None,
    chat_id: int | None = None,
    message_id: int | None = None,
    llm_service: Any | None = None,
) -> bool:
    """Handle reg:<item_id> callback query by showing tone sub-menu."""
    return await execute_tone_menu_callback(
        state_store=state_store,
        telegram=telegram,
        item_id=item_id,
        callback_query_id=callback_query_id,
        chat_id=chat_id,
        message_id=message_id,
    )


async def execute_home_callback(
    state_store: BaseStateStore,
    telegram: TelegramClient,
    settings: Settings,
    chat_id: int | None,
    message_id: int | None,
    callback_query_id: str | None = None,
    action_arg: str | None = None,
) -> bool:
    """Handle home:<arg> callback by rendering or toggling Home Menu hub."""
    if callback_query_id:
        if action_arg == "pause":
            settings.agent_paused = True
            state_store.set_paused(True)
            alert_text = "⏸️ Agent paused."
        elif action_arg == "resume":
            settings.agent_paused = False
            state_store.set_paused(False)
            alert_text = "▶️ Agent resumed."
        else:
            alert_text = "🏠 Command & Control Hub"
        await telegram.answer_callback_query(callback_query_id, text=alert_text, show_alert=False)

    if chat_id is not None and message_id is not None:
        repo_root = getattr(state_store, "repo_root", Path.cwd())
        halted, _ = is_halted(repo_root, settings, state_store=state_store)
        incident = state_store.read_incident()

        if incident is not None:
            sys_status = "🚨 <b>Halted (Circuit Breaker Tripped)</b>"
            reason = incident.get("reason", "Incident detected")
            cb_status = f"🔴 <b>Tripped:</b> {html.escape(str(reason), quote=True)}"
        elif halted or settings.agent_paused or state_store.is_paused():
            sys_status = "⏸️ <b>Paused</b>"
            cb_status = "🟢 <b>Normal</b> (No active incident)"
        else:
            sys_status = "🟢 <b>Operational</b>"
            cb_status = "🟢 <b>Normal</b> (No active incident)"

        counters = state_store.load_daily_counters()
        pending_items = state_store.list_pending()
        pending_count = len(pending_items)
        is_paused_now = bool(halted or settings.agent_paused or state_store.is_paused())

        report = format_home_hub(
            system_state=sys_status,
            cb_status=cb_status,
            pending_count=pending_count,
            counters=counters,
            settings=settings,
        )
        reply_kb = build_home_keyboard(
            is_tripped=(incident is not None),
            pending_count=pending_count,
            is_paused=is_paused_now,
        )

        await telegram.edit_message_text(
            chat_id=chat_id,
            message_id=message_id,
            text=report,
            reply_markup=reply_kb,
        )
    return True


async def execute_close_callback(
    telegram: TelegramClient,
    chat_id: int | None,
    message_id: int | None,
    callback_query_id: str | None = None,
) -> bool:
    """Handle close:menu callback by removing or collapsing the interactive menu."""
    if callback_query_id:
        await telegram.answer_callback_query(
            callback_query_id, text="Closed.", show_alert=False
        )

    if chat_id is not None and message_id is not None:
        try:
            await telegram.delete_message(chat_id=chat_id, message_id=message_id)
        except Exception:
            await telegram.edit_message_reply_markup(
                chat_id=chat_id, message_id=message_id, reply_markup=None
            )
    return True


async def execute_refresh_callback(
    view: str,
    settings: Settings,
    state_store: BaseStateStore,
    telegram: TelegramClient,
    chat_id: int | None,
    message_id: int | None,
    callback_query_id: str | None = None,
) -> bool:
    """Handle refresh:<view> callback by refreshing the specified view in-place."""
    if callback_query_id:
        await telegram.answer_callback_query(
            callback_query_id, text="🔄 Refreshed", show_alert=False
        )

    if chat_id is None or message_id is None:
        return True

    repo_root = getattr(state_store, "repo_root", Path.cwd())

    if view == "home":
        return await execute_home_callback(
            state_store=state_store,
            telegram=telegram,
            settings=settings,
            chat_id=chat_id,
            message_id=message_id,
        )
    elif view == "pending":
        pending_items = state_store.list_pending()
        if not pending_items:
            text = "📋 <b>Pending Actions</b>\n\nNo actions currently awaiting approval."
            kb = build_pending_list_keyboard([], include_nav=True)
        else:
            lines = [f"📋 <b>Pending Actions ({len(pending_items)})</b>\n"]
            for idx, item in enumerate(pending_items, start=1):
                action_label = "Comment" if "comment" in item.action_type.lower() else "Post"
                author_esc = html.escape(item.author_name or "Unknown", quote=True)
                url = (item.post_url or "").strip()
                target_link = f'<a href="{html.escape(url, quote=True)}">LinkedIn Post</a>' if url else "<i>No URL</i>"
                draft_snippet = item.draft_text[:100] + ("..." if len(item.draft_text) > 100 else "")
                conf_str = f"{int(item.confidence * 100)}%" if item.confidence is not None else "N/A"
                lines.append(
                    f"{idx}. <b>{action_label}</b> (<code>{item.item_id}</code>)\n"
                    f"   • <b>Target:</b> {target_link}\n"
                    f"   • <b>Author:</b> {author_esc} (Confidence: {conf_str})\n"
                    f'   • <b>Draft:</b> <i>"{html.escape(draft_snippet, quote=True)}"</i>'
                )
            text = "\n\n".join(lines)
            kb = build_pending_list_keyboard(pending_items, include_nav=True)
        await telegram.edit_message_text(
            chat_id=chat_id, message_id=message_id, text=text, reply_markup=kb
        )
    elif view == "status":
        halted, _ = is_halted(repo_root, settings, state_store=state_store)
        incident = state_store.read_incident()
        if incident is not None:
            sys_status = "🚨 <b>Halted (Circuit Breaker Tripped)</b>"
            reason_esc = html.escape(str(incident.get("reason", "Incident detected")), quote=True)
            cb_status = f"🔴 <b>Tripped:</b> {reason_esc}"
        elif halted or settings.agent_paused or state_store.is_paused():
            sys_status = "⏸️ <b>Paused</b>"
            cb_status = "🟢 <b>Normal</b> (No active incident)"
        else:
            sys_status = "🟢 <b>Operational</b>"
            cb_status = "🟢 <b>Normal</b> (No active incident)"

        counters = state_store.load_daily_counters()
        pending_items = state_store.list_pending()
        pending_count = len(pending_items)
        focus_areas_str = ", ".join(settings.user_focus_areas) if settings.user_focus_areas else "General"
        focus_areas_esc = html.escape(focus_areas_str, quote=True)

        report = (
            "🎛️ <b>Agent Status Report</b>\n\n"
            f"• <b>System State:</b> {sys_status}\n"
            f"• <b>Circuit Breaker:</b> {cb_status}\n"
            f"• <b>Pending Approvals:</b> <b>{pending_count}</b> action(s) awaiting review\n\n"
            f"📊 <b>Daily Counters ({counters.date})</b>\n"
            f"• <b>Comments Executed:</b> {counters.comments_executed} / {settings.max_comments_per_day}\n"
            f"• <b>Posts Executed:</b> {counters.posts_executed} / {settings.max_posts_per_day}\n"
            f"• <b>Suggestions Sent:</b> {counters.suggestions_sent} (run limit: {settings.max_suggestions_per_run})\n\n"
            "⚙️ <b>Configuration</b>\n"
            f"• <b>Dry Run:</b> {settings.dry_run}\n"
            f"• <b>Focus Areas:</b> {focus_areas_esc}"
        )
        reply_kb = build_status_keyboard(
            is_tripped=(incident is not None),
            pending_count=pending_count,
            include_nav=True,
        )
        await telegram.edit_message_text(
            chat_id=chat_id, message_id=message_id, text=report, reply_markup=reply_kb
        )
    elif view == "stats":
        history_entries = state_store.read_history()
        total_actions = len(history_entries)
        approved_count = sum(1 for e in history_entries if e.final_status in ("approved", "executed_success"))
        rejected_count = sum(1 for e in history_entries if e.final_status == "rejected")
        expired_count = sum(1 for e in history_entries if e.final_status == "expired")
        failed_count = sum(
            1 for e in history_entries
            if e.final_status in ("failed", "error", "executed_failed", "halted")
            or (e.error and e.final_status not in ("expired", "rejected"))
        )
        comments_posted = sum(
            1 for e in history_entries
            if "comment" in e.action_type.lower() and e.final_status in ("approved", "executed_success")
        )
        posts_published = sum(
            1 for e in history_entries
            if "post" in e.action_type.lower() and e.final_status in ("approved", "executed_success")
        )
        counters = state_store.load_daily_counters()
        history_summary = (
            "<i>No historical actions recorded yet.</i>\n"
            if total_actions == 0
            else (
                f"• <b>Total Actions Logged:</b> {total_actions}\n"
                f"• <b>Approved:</b> {approved_count}\n"
                f"• <b>Rejected:</b> {rejected_count}\n"
                f"• <b>Expired:</b> {expired_count}\n"
                f"• <b>Comments Posted:</b> {comments_posted}\n"
                f"• <b>Posts Published:</b> {posts_published}\n"
                f"• <b>Failures:</b> {failed_count}\n"
            )
        )
        report = (
            "📈 <b>Agent Activity Statistics</b>\n\n"
            f"{history_summary}\n"
            f"📅 <b>Today's Activity ({counters.date})</b>\n"
            f"• <b>Comments Executed:</b> {counters.comments_executed}\n"
            f"• <b>Posts Executed:</b> {counters.posts_executed}\n"
            f"• <b>Suggestions Sent:</b> {counters.suggestions_sent}"
        )
        await telegram.edit_message_text(
            chat_id=chat_id, message_id=message_id, text=report, reply_markup=build_stats_keyboard()
        )
    return True


async def execute_callback_query(
    settings: Settings,
    state_store: BaseStateStore,
    telegram: TelegramClient,
    callback_query: dict[str, Any],
    llm_service: Any | None = None,
) -> bool:
    """Process an incoming Telegram callback query.

    Args:
        settings: Application runtime settings.
        state_store: Durable state store instance.
        telegram: Telegram client instance.
        callback_query: Raw Telegram callback_query dictionary.
        llm_service: Optional LLM service for draft regeneration.

    Returns:
        bool: True if callback query was handled, False otherwise.
    """
    callback_query_id = callback_query.get("id", "")
    sender_id = callback_query.get("from", {}).get("id")
    data = callback_query.get("data", "")
    msg = callback_query.get("message", {})
    chat_id = msg.get("chat", {}).get("id") or sender_id
    message_id = msg.get("message_id")

    if not TelegramClient.is_authorized(sender_id, settings):
        logger.warning(
            "Unauthorized callback query attempt from sender %s. Dropping.",
            sender_id,
        )
        return False

    if not data or ":" not in data:
        return False

    try:
        payload = CallbackDataPayload.from_callback_data(data)
    except Exception:
        logger.warning("Failed to parse callback data: '%s'", data)
        return False

    if payload.is_reject_prompt:
        return await execute_reject_prompt_callback(
            state_store=state_store,
            telegram=telegram,
            item_id=payload.item_id,
            callback_query_id=callback_query_id,
            chat_id=chat_id,
            message_id=message_id,
        )
    elif payload.is_reject_cancel:
        return await execute_reject_cancel_callback(
            state_store=state_store,
            telegram=telegram,
            item_id=payload.item_id,
            callback_query_id=callback_query_id,
            chat_id=chat_id,
            message_id=message_id,
        )
    elif payload.is_reject_confirm:
        return await execute_reject_confirm_callback(
            state_store=state_store,
            telegram=telegram,
            item_id=payload.item_id,
            callback_query_id=callback_query_id,
            chat_id=chat_id,
            message_id=message_id,
        )
    elif payload.is_feedback:
        return await execute_feedback_callback(
            state_store=state_store,
            telegram=telegram,
            item_id=payload.item_id,
            reason=payload.arg or "skip",
            callback_query_id=callback_query_id,
            chat_id=chat_id,
            message_id=message_id,
        )
    elif payload.is_regenerate:
        return await execute_tone_menu_callback(
            state_store=state_store,
            telegram=telegram,
            item_id=payload.item_id,
            callback_query_id=callback_query_id,
            chat_id=chat_id,
            message_id=message_id,
        )
    elif payload.is_back:
        return await execute_back_callback(
            state_store=state_store,
            telegram=telegram,
            item_id=payload.item_id,
            callback_query_id=callback_query_id,
            chat_id=chat_id,
            message_id=message_id,
        )
    elif payload.is_tone_select:
        return await execute_tone_select_callback(
            state_store=state_store,
            telegram=telegram,
            item_id=payload.item_id,
            tone=payload.arg or "technical",
            callback_query_id=callback_query_id,
            chat_id=chat_id,
            message_id=message_id,
            llm_service=llm_service,
        )
    elif payload.is_edit:
        return await execute_edit_callback(
            state_store=state_store,
            telegram=telegram,
            item_id=payload.item_id,
            callback_query_id=callback_query_id,
            chat_id=chat_id,
            message_id=message_id,
        )
    elif payload.is_cancel_edit:
        return await execute_cancel_edit_callback(
            state_store=state_store,
            telegram=telegram,
            item_id=payload.item_id,
            callback_query_id=callback_query_id,
            chat_id=chat_id,
            message_id=message_id,
        )
    elif payload.is_review:
        return await execute_review_callback(
            state_store=state_store,
            telegram=telegram,
            item_id=payload.item_id,
            callback_query_id=callback_query_id,
            chat_id=chat_id,
        )
    elif payload.is_reset_cb:
        return await execute_reset_circuit_breaker_callback(
            state_store=state_store,
            telegram=telegram,
            callback_query_id=callback_query_id,
            chat_id=chat_id,
            message_id=message_id,
        )
    elif payload.is_noop:
        return await execute_noop_callback(
            telegram=telegram,
            callback_query_id=callback_query_id,
        )
    elif payload.is_home:
        return await execute_home_callback(
            state_store=state_store,
            telegram=telegram,
            settings=settings,
            chat_id=chat_id,
            message_id=message_id,
            callback_query_id=callback_query_id,
            action_arg=payload.arg or payload.item_id,
        )
    elif payload.is_close:
        return await execute_close_callback(
            telegram=telegram,
            chat_id=chat_id,
            message_id=message_id,
            callback_query_id=callback_query_id,
        )
    elif payload.is_refresh:
        return await execute_refresh_callback(
            view=payload.arg or payload.item_id,
            settings=settings,
            state_store=state_store,
            telegram=telegram,
            chat_id=chat_id,
            message_id=message_id,
            callback_query_id=callback_query_id,
        )

    return False
