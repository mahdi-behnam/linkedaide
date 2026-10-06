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
from typing import Any

from agent.config import Settings
from agent.models import (
    CallbackDataPayload,
    EngagementStyle,
    HistoryEntry,
)
from agent.state.base import BaseStateStore
from agent.telegram.client import TelegramClient
from agent.telegram.keyboards import (
    build_reject_confirm_keyboard,
    build_rejection_feedback_keyboard,
    build_suggestion_keyboard,
    build_tone_keyboard,
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
    """Handle edit:<item_id> callback query by prompting the operator to reply.

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
            f"<b>{html.escape(rejection_label)}</b>\n\n"
            "<i>Why was this suggestion rejected? (Optional feedback):</i>"
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
        final_text = (
            f"❌ <b>Suggestion rejected by operator</b>\n<i>Feedback: {html.escape(reason)}</i>"
            if reason != "skip"
            else "❌ <b>Suggestion rejected by operator</b>"
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

    if new_draft and isinstance(new_draft, str):
        updated = state_store.update_pending_draft(pending.item_id, new_draft)
        if updated is not None:
            pending = updated

    target_msg_id = message_id or pending.telegram_message_id
    if chat_id is not None and target_msg_id is not None:
        card_text = format_suggestion_card(pending)
        kb = build_suggestion_keyboard(pending.item_id, pending.action_type)
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

    return False
