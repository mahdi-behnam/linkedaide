"""Comment thread monitoring subsystem: inspect active threads, triage replies, and queue drafts."""

from __future__ import annotations

import hashlib
import logging
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from agent.models import (
    ActiveThreadRecord,
    PendingAction,
    ThreadReplyItem,
)

if TYPE_CHECKING:
    from agent.browser.executor import ActionExecutor
    from agent.config import Settings
    from agent.llm.service import LLMService
    from agent.state.base import BaseStateStore
    from agent.telegram.client import TelegramClient

logger = logging.getLogger("agent.orchestration.thread_monitor")


async def find_thread_replies(
    executor: ActionExecutor,
    llm: LLMService,
    state_store: BaseStateStore,
    settings: Settings,
    telegram: TelegramClient | None = None,
) -> list[PendingAction]:
    """Inspect active comment threads for replies, triage them with LLM, and queue approve_reply actions.

    Args:
        executor: Browser ActionExecutor with ThreadMixin capability.
        llm: LLM service for reply triage and follow-up reply drafting.
        state_store: Durable state store tracking active threads and pending actions.
        settings: System settings.
        telegram: Optional Telegram client for operator notification.

    Returns:
        list[PendingAction]: Newly queued approve_reply actions.
    """
    active_threads = state_store.list_active_threads()
    if not active_threads:
        logger.info("No active threads to inspect for replies.")
        return []

    queued_actions: list[PendingAction] = []
    now = datetime.now(UTC)

    for thread in active_threads:
        if thread.status != "active":
            continue

        logger.info("Inspecting replies on thread %s (%s)...", thread.id, thread.post_url)
        try:
            replies = await executor.inspect_comment_replies(
                post_url=thread.post_url,
                our_comment_text=thread.our_comment_text,
            )
        except Exception as err:
            logger.warning("Failed inspecting replies on thread %s: %s", thread.id, err)
            continue

        state_store.save_active_thread(thread.model_copy(update={"last_checked_at": now}))

        for reply in replies:
            # Check if this reply was already queued or handled
            item_id = hashlib.sha256(
                f"{reply.reply_urn}:{reply.reply_text.strip()}".encode()
            ).hexdigest()[:8]
            existing_pending = state_store.read_pending(item_id)
            if existing_pending is not None:
                continue

            # Triage reply with LLM
            try:
                triage = await llm.triage_thread_reply(
                    reply=reply,
                    our_comment=thread.our_comment_text,
                    original_post=f"Post by {thread.post_author}: {thread.post_url}",
                )
            except Exception as err:
                logger.warning("Reply triage failed for %s: %s", reply.reply_urn, err)
                continue

            if triage.recommendation != "reply":
                logger.debug("Reply %s ignored by triage: %s", reply.reply_urn, triage.reasoning)
                continue

            # Draft reply follow-up
            try:
                draft = await llm.draft_thread_reply(
                    reply=reply,
                    our_comment=thread.our_comment_text,
                    original_post=f"Post by {thread.post_author}",
                    triage=triage,
                )
            except Exception as err:
                logger.warning("Reply drafting failed for %s: %s", reply.reply_urn, err)
                continue

            pending = PendingAction(
                item_id=item_id,
                action_type="approve_reply",
                created_at=now,
                post_urn=reply.parent_comment_urn or thread.post_urn,
                post_url=thread.post_url,
                author_name=reply.author_name,
                author_headline=reply.author_headline,
                post_excerpt=reply.reply_text[:200],
                draft_text=draft.draft_comment,
                confidence=triage.confidence,
                reasoning=triage.reasoning,
                engagement_style=draft.engagement_style or triage.engagement_style,
                telegram_chat_id=settings.telegram_authorized_chat_id,
                telegram_message_id=0,
            )

            state_store.write_pending(pending)

            if telegram:
                try:
                    msg_id = await telegram.send_suggestion(pending)
                    pending_with_msg = pending.model_copy(update={"telegram_message_id": msg_id})
                    state_store.write_pending(pending_with_msg)
                    pending = pending_with_msg
                except Exception as err:
                    logger.warning(
                        "Failed sending Telegram suggestion for reply %s: %s", item_id, err
                    )

            queued_actions.append(pending)
            logger.info(
                "Queued approve_reply action %s for reply by %s", item_id, reply.author_name
            )

    return queued_actions
