"""Telegram interactive draft editor handler for human-in-the-loop approvals.

Architecture Invariants:
- Human approval invariant: editing drafts alters only pending action state, never triggers execution.
- Strict authorization: unauthorized senders receive zero state mutation and no response.
- Deterministic safety: text length limits and pending state validation enforced deterministically.
- Atomicity: durable state in state/pending/{item_id}.json updated via atomic swap.
- UI synchronization: Telegram suggestion message re-rendered with refreshed buttons and blockquote.
"""

from __future__ import annotations

import logging
import re
from typing import Any

from agent.config import Settings
from agent.models.schemas import CallbackDataPayload, PendingAction
from agent.state.base import BaseStateStore
from agent.telegram.client import TelegramClient
from agent.telegram.keyboards import (
    build_suggestion_keyboard,
    build_suggestion_message,
)

logger = logging.getLogger(__name__)

# Regex pattern for extracting item ID from Telegram message text (e.g. 'ID: item_12345')
ITEM_ID_REGEX = re.compile(r"ID:\s*([a-zA-Z0-9_\-]+)", re.IGNORECASE)

# Length constraints
MAX_COMMENT_DRAFT_LENGTH = 600
MAX_POST_DRAFT_LENGTH = 1200


async def handle_edit_callback(
    callback_query: dict[str, Any] | None = None,
    settings: Settings | None = None,
    state_store: BaseStateStore | None = None,
    telegram: TelegramClient | None = None,
    *,
    callback_query_id: str | None = None,
    sender_id: int | None = None,
    data: str | None = None,
    item_id: str | None = None,
) -> bool:
    """Handle an inline [✏️ Edit] button callback query.

    Acknowledges the query and prompts the operator to reply to the suggestion with revised text.

    Args:
        callback_query: Raw Telegram callback_query dictionary.
        settings: Application runtime settings.
        state_store: Durable Git state store instance.
        telegram: Telegram client instance.
        callback_query_id: Optional explicit callback query ID.
        sender_id: Optional explicit sender user/chat ID.
        data: Optional explicit callback_data string.
        item_id: Optional explicit item ID.

    Returns:
        True if successfully handled, False if dropped or invalid.
    """
    if callback_query is not None:
        callback_query_id = callback_query_id or callback_query.get("id", "")
        sender_id = sender_id or callback_query.get("from", {}).get("id")
        data = data or callback_query.get("data", "")

    if settings is None or not TelegramClient.is_authorized(sender_id, settings):
        logger.warning(
            "Unauthorized edit callback query received from sender_id: %s. Dropping.", sender_id
        )
        return False

    if not item_id and data:
        try:
            payload = CallbackDataPayload.from_callback_data(data)
            item_id = payload.item_id
        except Exception:
            logger.warning("Failed to parse callback data for edit: '%s'", data)
            item_id = None

    pending: PendingAction | None = None
    if state_store is not None and item_id:
        pending = state_store.read_pending(item_id)

    if pending is None:
        if telegram is not None and callback_query_id:
            await telegram.answer_callback_query(
                callback_query_id,
                text="⚠️ Suggestion is no longer pending or has already been processed.",
                show_alert=True,
            )
        return False

    if telegram is not None and callback_query_id:
        await telegram.answer_callback_query(
            callback_query_id,
            text="✏️ Reply to this suggestion with your revised draft text.",
            show_alert=False,
        )

    return True


async def handle_draft_edit(
    message: dict[str, Any] | None = None,
    settings: Settings | None = None,
    state_store: BaseStateStore | None = None,
    telegram: TelegramClient | None = None,
    *,
    text: str | None = None,
    sender_id: int | None = None,
    chat_id: int | None = None,
    message_id: int | None = None,
    reply_to_message: dict[str, Any] | None = None,
) -> bool:
    """Handle an operator reply revising a pending draft's content.

    Validates sender authorization, resolves target pending action, validates revised text,
    atomically mutates durable state, re-renders the suggestion card, and sends confirmation.

    Args:
        message: Raw Telegram message dictionary.
        settings: Application runtime settings.
        state_store: Durable Git state store instance.
        telegram: Telegram client instance.
        text: Optional explicit revised text.
        sender_id: Optional explicit sender ID.
        chat_id: Optional explicit chat ID.
        message_id: Optional explicit operator reply message ID.
        reply_to_message: Optional explicit parent message being replied to.

    Returns:
        True if draft was successfully edited and updated, False otherwise.
    """
    if message is not None:
        sender_id = sender_id if sender_id is not None else message.get("from", {}).get("id")
        chat_id = chat_id if chat_id is not None else message.get("chat", {}).get("id")
        message_id = message_id if message_id is not None else message.get("message_id")
        text = text if text is not None else message.get("text", "")
        reply_to_message = (
            reply_to_message if reply_to_message is not None else message.get("reply_to_message")
        )

    # 1. Strict Authorization Guard
    if settings is None or not TelegramClient.is_authorized(sender_id, settings):
        logger.warning(
            "Unauthorized draft edit attempt from sender_id: %s. Zero state mutation.",
            sender_id,
        )
        return False

    if state_store is None or telegram is None:
        logger.error("Draft editor requires valid state_store and telegram client instances.")
        return False

    # 2. Match Target Pending Action
    if reply_to_message is None:
        logger.debug("Received message without reply_to_message; ignoring for draft edit.")
        return False

    pending: PendingAction | None = None
    target_message_id: int | None = None
    reply_msg_id = reply_to_message.get("message_id")
    if isinstance(reply_msg_id, int):
        pending = state_store.find_pending_by_message_id(reply_msg_id)
        if pending is not None:
            target_message_id = reply_msg_id

    # Fallback resolution via ID in reply message text
    if pending is None:
        reply_text = reply_to_message.get("text", "")
        match = ITEM_ID_REGEX.search(reply_text)
        if match:
            matched_id = match.group(1)
            pending = state_store.read_pending(matched_id)
            if pending is not None:
                target_message_id = (
                    reply_msg_id if isinstance(reply_msg_id, int) else pending.telegram_message_id
                )

    if pending is None:
        if chat_id is not None:
            await telegram.send_message(
                chat_id=chat_id,
                text="⚠️ The target suggestion is no longer pending or has already been processed.",
                reply_to_message_id=message_id,
            )
        return False

    # 3. Validate Revised Text
    revised_text = (text or "").strip()
    if not revised_text:
        if chat_id is not None:
            await telegram.send_message(
                chat_id=chat_id,
                text="❌ Draft text cannot be empty. Please reply with the revised text.",
                reply_to_message_id=message_id,
            )
        return False

    is_post = pending.action_type in ("approve_post", "post")
    max_len = MAX_POST_DRAFT_LENGTH if is_post else MAX_COMMENT_DRAFT_LENGTH
    if len(revised_text) > max_len:
        if chat_id is not None:
            await telegram.send_message(
                chat_id=chat_id,
                text=(
                    f"❌ Draft exceeds maximum length of {max_len} characters "
                    f"({len(revised_text)}/{max_len}). Please shorten your draft."
                ),
                reply_to_message_id=message_id,
            )
        return False

    # 4. Atomically Update Durable State
    updated_item = state_store.update_pending_draft(pending.item_id, revised_text)
    if updated_item is None:
        if chat_id is not None:
            await telegram.send_message(
                chat_id=chat_id,
                text="⚠️ Failed to update draft: suggestion is no longer pending.",
                reply_to_message_id=message_id,
            )
        return False

    # 5. Re-render Suggestion Message Card
    if target_message_id is None:
        target_message_id = pending.telegram_message_id

    if chat_id is not None and target_message_id is not None:
        rendered_text = build_suggestion_message(updated_item)
        refreshed_keyboard = build_suggestion_keyboard(
            updated_item.item_id, updated_item.action_type
        )
        try:
            await telegram.edit_message_text(
                chat_id=chat_id,
                message_id=target_message_id,
                text=rendered_text,
                reply_markup=refreshed_keyboard,
            )
        except Exception as edit_err:
            logger.warning(
                "Failed to edit Telegram suggestion message %s: %s",
                target_message_id,
                edit_err,
            )

    # 6. Send Confirmation Notice to Operator
    if chat_id is not None:
        await telegram.send_message(
            chat_id=chat_id,
            text="✅ Draft updated! Refreshed suggestion above with revised text.",
            reply_to_message_id=message_id,
        )

    return True
