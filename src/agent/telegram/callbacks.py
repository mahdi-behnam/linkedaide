"""Telegram inline keyboard callback query handlers.

Architecture Invariants:
- Human approval invariant: callback actions inspect or revise pending state, never trigger writes directly.
- Strict authorization: unauthorized senders receive zero state mutation and no response.
- Safety & Reliability: safe fallback to tone guidance if LLM draft regeneration fails.
"""

from __future__ import annotations

import html
import logging
from typing import Any

from agent.config import Settings
from agent.models import (
    CallbackDataPayload,
    EngagementStyle,
)
from agent.state.base import BaseStateStore
from agent.telegram.client import TelegramClient
from agent.telegram.keyboards import (
    build_suggestion_keyboard,
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


async def execute_regenerate_callback(
    state_store: BaseStateStore,
    telegram: TelegramClient,
    item_id: str,
    callback_query_id: str | None = None,
    chat_id: int | None = None,
    message_id: int | None = None,
    llm_service: Any | None = None,
) -> bool:
    """Handle reg:<item_id> callback query by drafting alternative or sending tone guidance.

    Args:
        state_store: Durable state store instance.
        telegram: Telegram client instance.
        item_id: ID of the pending item to regenerate.
        callback_query_id: Telegram callback query ID to answer.
        chat_id: Optional Telegram chat ID.
        message_id: Optional message ID of the suggestion.
        llm_service: Optional LLM service for draft regeneration.

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

    if llm_service is not None and hasattr(llm_service, "draft_comment") and pending.post_excerpt:
        try:
            if isinstance(pending.engagement_style, EngagementStyle):
                current_style = pending.engagement_style.value
            elif pending.engagement_style is not None:
                current_style = str(pending.engagement_style)
            else:
                current_style = ""
            alt_style = (
                EngagementStyle.CONTRARIAN_PERSPECTIVE
                if current_style == EngagementStyle.TECHNICAL_DEEP_DIVE.value
                else EngagementStyle.TECHNICAL_DEEP_DIVE
            )
            draft_res = await llm_service.draft_comment(
                post_text=pending.post_excerpt,
                author_name=pending.author_name or "LinkedIn Creator",
                engagement_style=alt_style,
            )
            draft_text = (
                draft_res.draft_comment
                if hasattr(draft_res, "draft_comment")
                else getattr(draft_res, "comment_text", None)
            )
            if draft_text:
                updated = state_store.update_pending_draft(pending.item_id, draft_text)
                if updated is not None:
                    updated.engagement_style = alt_style
                    state_store.write_pending(updated)
                    target_msg_id = message_id or updated.telegram_message_id
                    if chat_id is not None and target_msg_id is not None:
                        card_text = format_suggestion_card(updated)
                        kb = build_suggestion_keyboard(updated.item_id, updated.action_type)
                        await telegram.edit_message_text(
                            chat_id=chat_id,
                            message_id=target_msg_id,
                            text=card_text,
                            reply_markup=kb,
                        )
                    if callback_query_id:
                        await telegram.answer_callback_query(
                            callback_query_id,
                            text="🔄 Regenerated draft with alternative style!",
                            show_alert=False,
                        )
                    return True
        except Exception as gen_err:
            logger.warning(
                "Failed to regenerate draft via LLM: %s. Falling back to guidance.",
                gen_err,
            )

    if callback_query_id:
        await telegram.answer_callback_query(
            callback_query_id,
            text="🔄 Reply to this suggestion with your preferred tone or new draft.",
            show_alert=False,
        )

    if chat_id is not None:
        guidance_msg = (
            "🔄 <b>Draft Regeneration & Tone Guidance</b>\n\n"
            "To adjust the tone or regenerate this draft, reply directly to the suggestion message with:\n"
            "• <b>Custom Text:</b> Your complete revised draft\n"
            "• <b>Tone Options:</b>\n"
            "  - <i>Technical Deep-Dive:</i> In-depth architectural/systems perspective\n"
            "  - <i>Inquisitive Question:</i> Thoughtful inquiry sparking conversation\n"
            "  - <i>Contrarian Perspective:</i> Constructive alternative viewpoint\n"
            "  - <i>Supportive Synthesis:</i> Summary highlighting key takeaways\n\n"
            f"<i>Suggestion ID: <code>{html.escape(item_id)}</code></i>"
        )
        await telegram.send_message(
            chat_id=chat_id,
            text=guidance_msg,
            reply_to_message_id=message_id,
        )

    return True


async def execute_callback_query(
    settings: Settings,
    state_store: BaseStateStore,
    telegram: TelegramClient,
    callback_query: dict[str, Any],
    llm_service: Any | None = None,
) -> bool:
    """Process an incoming Telegram callback query (e.g. edit or regenerate).

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

    if payload.is_edit:
        return await execute_edit_callback(
            state_store=state_store,
            telegram=telegram,
            item_id=payload.item_id,
            callback_query_id=callback_query_id,
            chat_id=chat_id,
            message_id=message_id,
        )
    elif payload.is_regenerate:
        return await execute_regenerate_callback(
            state_store=state_store,
            telegram=telegram,
            item_id=payload.item_id,
            callback_query_id=callback_query_id,
            chat_id=chat_id,
            message_id=message_id,
            llm_service=llm_service,
        )

    return False
