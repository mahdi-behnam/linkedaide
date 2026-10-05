"""Thread monitor workflow graph: inspect active threads, triage replies, draft follow-ups, and notify."""

from __future__ import annotations

import hashlib
import logging
from datetime import UTC, datetime
from typing import Any

from langchain_core.runnables import RunnableConfig
from langgraph.graph import END, START, StateGraph

from agent.graphs.state import ThreadMonitorState, get_graph_context
from agent.models import (
    ActiveThreadRecord,
    CommentDraft,
    PendingAction,
    ReplyTriageResult,
    ThreadReplyItem,
)
from agent.safety.circuit_breaker import is_halted

logger = logging.getLogger(__name__)


async def check_halted(state: ThreadMonitorState, config: RunnableConfig) -> dict[str, Any]:
    """Verify circuit breaker and pause switch before proceeding."""
    context = get_graph_context(config)
    halted, reason = is_halted(
        context.settings.state_dir.parent, context.settings, state_store=context.state_store
    )
    if halted:
        logger.warning("Thread monitor graph check_halted: halted (%s)", reason)
        return {"halted_reason": reason, "status": "halted"}
    return {"halted_reason": None, "status": "active"}


async def load_active_threads(state: ThreadMonitorState, config: RunnableConfig) -> dict[str, Any]:
    """Load active tracked comment threads from durable state."""
    context = get_graph_context(config)
    if not context.state_store:
        return {"active_threads": [], "status": "no_state_store"}

    active = context.state_store.list_active_threads()
    filtered = [t for t in active if t.status == "active"]
    logger.info("Loaded %d active comment thread(s) for reply monitoring", len(filtered))
    return {"active_threads": filtered, "status": "threads_loaded"}


async def inspect_threads(state: ThreadMonitorState, config: RunnableConfig) -> dict[str, Any]:
    """Inspect active comment threads in DOM for new unhandled replies."""
    context = get_graph_context(config)
    if not context.executor or not context.state_store:
        return {"discovered_replies": [], "status": "no_executor_or_store"}

    active_threads = state.get("active_threads", [])
    discovered_replies: list[tuple[ActiveThreadRecord, ThreadReplyItem]] = []
    errors: list[str] = list(state.get("errors", []))
    now = datetime.now(UTC)

    for thread in active_threads:
        logger.info("Inspecting replies on thread %s (%s)...", thread.id, thread.post_url)
        try:
            replies = await context.executor.inspect_comment_replies(
                post_url=thread.post_url,
                our_comment_text=thread.our_comment_text,
            )
        except Exception as err:
            logger.warning("Failed inspecting replies on thread %s: %s", thread.id, err)
            errors.append(f"Inspect failed for thread {thread.id}: {err}")
            continue

        context.state_store.save_active_thread(thread.model_copy(update={"last_checked_at": now}))

        for reply in replies:
            item_id = hashlib.sha256(
                f"{reply.reply_urn}:{reply.reply_text.strip()}".encode()
            ).hexdigest()[:8]
            existing_pending = context.state_store.read_pending(item_id)
            if existing_pending is not None:
                continue

            discovered_replies.append((thread, reply))

    logger.info("Discovered %d new unhandled thread replie(s)", len(discovered_replies))
    return {
        "discovered_replies": discovered_replies,
        "status": "inspected",
        "errors": errors,
    }


async def triage_replies(state: ThreadMonitorState, config: RunnableConfig) -> dict[str, Any]:
    """Evaluate discovered thread replies with LLM triage chain."""
    context = get_graph_context(config)
    if not context.llm:
        return {"triage_results": [], "status": "no_llm"}

    discovered = state.get("discovered_replies", [])
    results: list[tuple[ActiveThreadRecord, ThreadReplyItem, ReplyTriageResult]] = []
    errors: list[str] = list(state.get("errors", []))

    for thread, reply in discovered:
        try:
            triage = await context.llm.triage_thread_reply(
                reply=reply,
                our_comment=thread.our_comment_text,
                original_post=f"Post by {thread.post_author}: {thread.post_url}",
            )
            results.append((thread, reply, triage))
            logger.info(
                "Reply triage for %s: %s (confidence: %.2f)",
                reply.reply_urn,
                triage.recommendation.upper(),
                triage.confidence,
            )
        except Exception as err:
            logger.warning("Reply triage failed for %s: %s", reply.reply_urn, err)
            errors.append(f"Triage failed for {reply.reply_urn}: {err}")

    qualifying_count = sum(1 for _, _, t in results if t.recommendation == "reply")
    logger.info(
        "Reply triage complete: %d/%d qualified for response", qualifying_count, len(results)
    )
    return {"triage_results": results, "status": "triaged", "errors": errors}


async def draft_replies(state: ThreadMonitorState, config: RunnableConfig) -> dict[str, Any]:
    """Draft conversational follow-up comments for qualifying replies."""
    context = get_graph_context(config)
    if not context.llm:
        return {"drafts": [], "status": "no_llm"}

    triage_results = state.get("triage_results", [])
    qualifying = [(t, r, tr) for t, r, tr in triage_results if tr.recommendation == "reply"]
    drafts: list[tuple[ActiveThreadRecord, ThreadReplyItem, ReplyTriageResult, CommentDraft]] = []
    errors: list[str] = list(state.get("errors", []))

    for thread, reply, triage in qualifying:
        try:
            draft = await context.llm.draft_thread_reply(
                reply=reply,
                our_comment=thread.our_comment_text,
                original_post=f"Post by {thread.post_author}",
                triage=triage,
            )
            drafts.append((thread, reply, triage, draft))
            logger.info(
                "Generated reply draft for %s (%d chars)", reply.reply_urn, len(draft.draft_comment)
            )
        except Exception as err:
            logger.warning("Reply drafting failed for %s: %s", reply.reply_urn, err)
            errors.append(f"Drafting failed for {reply.reply_urn}: {err}")

    return {"drafts": drafts, "status": "drafted", "errors": errors}


async def persist_pending(state: ThreadMonitorState, config: RunnableConfig) -> dict[str, Any]:
    """Persist newly drafted follow-up actions to durable state store."""
    context = get_graph_context(config)
    if not context.state_store:
        return {"pending_items": [], "queued_count": 0}

    drafts = state.get("drafts", [])
    now = datetime.now(UTC)
    pending_items: list[PendingAction] = []

    for thread, reply, triage, draft in drafts:
        item_id = hashlib.sha256(
            f"{reply.reply_urn}:{reply.reply_text.strip()}".encode()
        ).hexdigest()[:8]

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
            telegram_chat_id=context.settings.telegram_authorized_chat_id,
            telegram_message_id=0,
        )

        context.state_store.write_pending(pending)
        pending_items.append(pending)
        logger.info("Persisted approve_reply action %s for reply by %s", item_id, reply.author_name)

    return {
        "pending_items": pending_items,
        "queued_count": len(pending_items),
        "status": "persisted",
    }


async def notify_telegram(state: ThreadMonitorState, config: RunnableConfig) -> dict[str, Any]:
    """Deliver suggestion cards with approve/reject keyboards to Telegram."""
    context = get_graph_context(config)
    pending_items = state.get("pending_items", [])
    if not context.telegram or not context.state_store:
        return {
            "pending_items": pending_items,
            "queued_count": len(pending_items),
            "status": "completed_no_telegram",
        }

    updated_items: list[PendingAction] = []
    errors: list[str] = list(state.get("errors", []))

    for item in pending_items:
        try:
            msg_id = await context.telegram.send_suggestion(item)
            item_with_msg = item.model_copy(update={"telegram_message_id": msg_id})
            context.state_store.write_pending(item_with_msg)
            updated_items.append(item_with_msg)
            logger.info(
                "Delivered Telegram suggestion card for %s (msg_id=%s)", item.item_id, msg_id
            )
        except Exception as err:
            logger.error("Failed sending Telegram suggestion for reply %s: %s", item.item_id, err)
            errors.append(f"Telegram delivery failed for {item.item_id}: {err}")
            updated_items.append(item)

    if context.state_store and updated_items:
        try:
            context.state_store.increment_suggestion_count(count=len(updated_items))
        except Exception as err:
            logger.warning("Failed incrementing suggestion count: %s", err)

    return {
        "pending_items": updated_items,
        "queued_count": len(updated_items),
        "status": "completed",
        "errors": errors,
    }


# Conditional routing functions
def route_after_halt_check(state: ThreadMonitorState) -> str:
    if state.get("halted_reason"):
        return END
    return "load_active_threads"


def route_after_load_threads(state: ThreadMonitorState) -> str:
    active = state.get("active_threads", [])
    if not active:
        return END
    return "inspect_threads"


def route_after_inspect(state: ThreadMonitorState) -> str:
    discovered = state.get("discovered_replies", [])
    if not discovered:
        return END
    return "triage_replies"


def route_after_triage(state: ThreadMonitorState) -> str:
    triage_results = state.get("triage_results", [])
    has_qualifying = any(tr.recommendation == "reply" for _, _, tr in triage_results)
    if not has_qualifying:
        return END
    return "draft_replies"


def route_after_draft(state: ThreadMonitorState) -> str:
    drafts = state.get("drafts", [])
    if not drafts:
        return END
    return "persist_pending"


def build_thread_monitor_graph() -> Any:
    """Build and compile the deterministic ThreadMonitor StateGraph."""
    graph = StateGraph(ThreadMonitorState)

    graph.add_node("check_halted", check_halted)
    graph.add_node("load_active_threads", load_active_threads)
    graph.add_node("inspect_threads", inspect_threads)
    graph.add_node("triage_replies", triage_replies)
    graph.add_node("draft_replies", draft_replies)
    graph.add_node("persist_pending", persist_pending)
    graph.add_node("notify_telegram", notify_telegram)

    graph.add_edge(START, "check_halted")
    graph.add_conditional_edges(
        "check_halted", route_after_halt_check, [END, "load_active_threads"]
    )
    graph.add_conditional_edges(
        "load_active_threads", route_after_load_threads, [END, "inspect_threads"]
    )
    graph.add_conditional_edges("inspect_threads", route_after_inspect, [END, "triage_replies"])
    graph.add_conditional_edges("triage_replies", route_after_triage, [END, "draft_replies"])
    graph.add_conditional_edges("draft_replies", route_after_draft, [END, "persist_pending"])
    graph.add_edge("persist_pending", "notify_telegram")
    graph.add_edge("notify_telegram", END)

    return graph.compile()
