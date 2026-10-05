"""Ideation workflow graph: discover context, draft original post ideas, persist, and notify."""

from __future__ import annotations

import hashlib
import logging
from datetime import UTC, datetime
from typing import Any

from langchain_core.runnables import RunnableConfig
from langgraph.graph import END, START, StateGraph

from agent.graphs.state import IdeationState, get_graph_context
from agent.models import PendingAction, PostIdea, PostIdeationContext
from agent.safety.circuit_breaker import is_halted

logger = logging.getLogger(__name__)


async def check_halted(state: IdeationState, config: RunnableConfig) -> dict[str, Any]:
    """Verify circuit breaker and pause switch before proceeding."""
    context = get_graph_context(config)
    halted, reason = is_halted(
        context.settings.state_dir.parent,
        context.settings,
        state_store=context.state_store,
    )
    if halted:
        logger.warning("Ideation graph check_halted: halted (%s)", reason)
        return {"halted_reason": reason, "status": "halted"}
    return {"halted_reason": None, "status": "active"}


async def load_context(state: IdeationState, config: RunnableConfig) -> dict[str, Any]:
    """Load focus areas, recent post history, and pending suggestions to ensure freshness."""
    context = get_graph_context(config)
    user_focus_areas = list(context.settings.user_focus_areas)
    recent_topics: list[str] = []

    if context.state_store:
        try:
            pending_items = context.state_store.list_pending()
            for pending in pending_items:
                if pending.post_excerpt and pending.post_excerpt.strip():
                    topic = pending.post_excerpt.strip()
                    if topic not in recent_topics:
                        recent_topics.append(topic)
                elif pending.draft_text and pending.draft_text.strip():
                    first_line = pending.draft_text.strip().split("\n")[0].strip()
                    if first_line and first_line not in recent_topics:
                        recent_topics.append(first_line)
        except Exception as err:
            logger.warning("Failed reading pending actions for ideation context: %s", err)

        try:
            history_entries = context.state_store.read_history(limit=50)
            for entry in history_entries:
                if entry.item_id and entry.item_id not in recent_topics:
                    recent_topics.append(entry.item_id)
        except Exception as err:
            logger.warning("Failed reading history entries for ideation context: %s", err)

    logger.info(
        "Loaded ideation context: %d focus areas, %d recent topics",
        len(user_focus_areas),
        len(recent_topics),
    )
    return {
        "user_focus_areas": user_focus_areas,
        "recent_topics": recent_topics,
        "status": "context_loaded",
    }


async def generate_ideas(state: IdeationState, config: RunnableConfig) -> dict[str, Any]:
    """Call LLM service with resilience to draft original post candidates."""
    context = get_graph_context(config)
    if not context.llm:
        logger.error("No LLM service available in GraphContext")
        return {
            "candidate_ideas": [],
            "errors": ["No LLM service provided in GraphContext"],
            "status": "llm_unavailable",
        }

    focus_areas = state.get("user_focus_areas") or list(context.settings.user_focus_areas)
    recent_topics = list(state.get("recent_topics") or [])
    candidates: list[PostIdea] = []
    errors: list[str] = list(state.get("errors") or [])

    try:
        post_context = PostIdeationContext(
            user_focus_areas=focus_areas,
            recent_topics=recent_topics,
        )
        idea = await context.llm.draft_post_idea(post_context)
        if idea is not None:
            candidates.append(idea)
        else:
            errors.append("LLM returned no idea")
    except Exception as err:
        logger.error("Failed drafting post idea: %s", err)
        errors.append(str(err))

    return {
        "candidate_ideas": candidates,
        "errors": errors,
        "status": "ideas_generated" if candidates else "no_ideas_generated",
    }


async def filter_and_rank(state: IdeationState, config: RunnableConfig) -> dict[str, Any]:
    """Deduplicate against recent topics, filter valid ideas, and construct PendingActions."""
    context = get_graph_context(config)
    candidates = state.get("candidate_ideas", [])
    recent_topics = [t.lower().strip() for t in (state.get("recent_topics") or [])]

    filtered: list[PostIdea] = []
    for idea in candidates:
        if not idea.should_post:
            continue
        if not idea.draft_post_text or not idea.draft_post_text.strip():
            continue

        headline_clean = idea.headline.lower().strip()
        if headline_clean and any(
            headline_clean == rt or (len(rt) > 5 and (headline_clean in rt or rt in headline_clean))
            for rt in recent_topics
        ):
            logger.info("Filtered duplicate idea headline: %s", idea.headline)
            continue

        filtered.append(idea)

    limit = max(1, context.settings.max_suggestions_per_run)
    ranked = filtered[:limit]

    pending_items: list[PendingAction] = []
    now = datetime.now(UTC)

    for idea in ranked:
        item_id = hashlib.sha256(f"post:{idea.headline}:{now.isoformat()}".encode()).hexdigest()[:8]

        parts: list[str] = []
        if idea.headline and idea.headline.strip():
            parts.append(idea.headline.strip())
        if idea.draft_post_text and idea.draft_post_text.strip():
            parts.append(idea.draft_post_text.strip())
        if idea.hashtags:
            tags_str = " ".join(
                tag if tag.startswith("#") else f"#{tag}" for tag in idea.hashtags if tag.strip()
            )
            if tags_str:
                parts.append(tags_str)

        draft_text = "\n\n".join(parts)

        pending = PendingAction(
            item_id=item_id,
            action_type="approve_post",
            created_at=now,
            post_urn="",
            post_url="",
            author_name="",
            post_excerpt=idea.headline,
            draft_text=draft_text,
            confidence=1.0,
            reasoning=idea.reasoning,
            telegram_chat_id=context.settings.telegram_authorized_chat_id,
            telegram_message_id=None,
        )
        pending_items.append(pending)

    return {
        "filtered_ideas": ranked,
        "pending_items": pending_items,
        "status": "filtered",
    }


async def persist_pending(state: IdeationState, config: RunnableConfig) -> dict[str, Any]:
    """Persist generated post suggestions to durable state as pending actions."""
    context = get_graph_context(config)
    pending_items = state.get("pending_items", [])

    if not context.state_store:
        logger.warning("No state_store in GraphContext: skipping persistence")
        return {
            "errors": list(state.get("errors") or []) + ["No state_store in GraphContext"],
            "status": "persist_skipped",
        }

    persisted_items: list[PendingAction] = []
    for item in pending_items:
        try:
            context.state_store.write_pending(item)
            persisted_items.append(item)
            logger.info("Persisted pending post idea: %s", item.item_id)
        except Exception as err:
            logger.error("Failed to write pending action %s: %s", item.item_id, err)

    return {
        "pending_items": persisted_items,
        "status": "persisted",
    }


async def send_suggestions(state: IdeationState, config: RunnableConfig) -> dict[str, Any]:
    """Deliver suggestion cards with approval keyboards to Telegram."""
    context = get_graph_context(config)
    pending_items = state.get("pending_items", [])

    if context.settings.dry_run:
        logger.info(
            "Dry-run enabled: skipping Telegram delivery for %d suggestion(s)", len(pending_items)
        )
        return {"pending_items": pending_items, "status": "completed_dry_run"}

    if not context.telegram:
        logger.warning("No Telegram client in GraphContext: skipping suggestion delivery")
        return {"pending_items": pending_items, "status": "completed_no_telegram"}

    updated_items: list[PendingAction] = []
    for item in pending_items:
        try:
            msg_id = await context.telegram.send_suggestion(item)
            item_with_msg = item.model_copy(update={"telegram_message_id": msg_id})
            if context.state_store:
                context.state_store.write_pending(item_with_msg)
            updated_items.append(item_with_msg)
            logger.info("Sent suggestion card for %s (message_id=%s)", item.item_id, msg_id)
        except Exception as err:
            logger.error("Failed delivering Telegram suggestion for %s: %s", item.item_id, err)

    if context.state_store and updated_items:
        try:
            context.state_store.increment_suggestion_count(count=len(updated_items))
        except Exception as err:
            logger.warning("Failed incrementing daily suggestion counter: %s", err)

    return {"pending_items": updated_items, "status": "completed"}


def route_after_halt_check(state: IdeationState) -> str:
    if state.get("halted_reason"):
        return END
    return "load_context"


def route_after_generate(state: IdeationState) -> str:
    candidates = state.get("candidate_ideas", [])
    if not candidates:
        return END
    return "filter_and_rank"


def route_after_filter(state: IdeationState) -> str:
    pending = state.get("pending_items", [])
    if not pending:
        return END
    return "persist_pending"


def build_ideation_graph() -> Any:
    """Build and compile the deterministic Ideation StateGraph."""
    graph = StateGraph(IdeationState)

    graph.add_node("check_halted", check_halted)
    graph.add_node("load_context", load_context)
    graph.add_node("generate_ideas", generate_ideas)
    graph.add_node("filter_and_rank", filter_and_rank)
    graph.add_node("persist_pending", persist_pending)
    graph.add_node("send_suggestions", send_suggestions)

    graph.add_edge(START, "check_halted")
    graph.add_conditional_edges("check_halted", route_after_halt_check, [END, "load_context"])
    graph.add_edge("load_context", "generate_ideas")
    graph.add_conditional_edges("generate_ideas", route_after_generate, [END, "filter_and_rank"])
    graph.add_conditional_edges("filter_and_rank", route_after_filter, [END, "persist_pending"])
    graph.add_edge("persist_pending", "send_suggestions")
    graph.add_edge("send_suggestions", END)

    return graph.compile()
