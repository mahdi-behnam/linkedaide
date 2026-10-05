"""Scout workflow graph: discover, triage, draft, persist, and notify."""

from __future__ import annotations

import asyncio
import hashlib
import logging
import re
from datetime import UTC, datetime
from typing import Any

from langchain_core.runnables import RunnableConfig
from langgraph.graph import END, START, StateGraph

from agent.browser.stealth import humanized_dwell
from agent.browser.url_utils import hashtag_to_feed_url
from agent.config import Settings
from agent.errors import BotDetectionError, ScrapeError, SessionExpiredError
from agent.graphs.state import ScoutState, get_graph_context
from agent.models import (
    CommentDraft,
    ConnectionRequestAction,
    PendingAction,
    PostRecord,
    TriageResult,
)
from agent.safety.circuit_breaker import is_halted, trip_breaker

logger = logging.getLogger(__name__)


def get_scout_target_sources(settings: Settings) -> list[str | None]:
    """Resolve configured target sources (URLs and hashtags) for feed scraping.

    Combines explicit target URLs from scout_target_urls and resolved hashtag search
    URLs from target_hashtags. Preserves encounter order and deduplicates URLs.
    If no targets are configured, falls back to [None] (default feed).
    """
    sources: list[str | None] = []

    if settings.scout_target_urls:
        for url in settings.scout_target_urls:
            clean_url = url.strip()
            if clean_url and clean_url not in sources:
                sources.append(clean_url)

    if settings.target_hashtags:
        for tag in settings.target_hashtags:
            clean_tag = tag.strip()
            if clean_tag:
                try:
                    hashtag_url = hashtag_to_feed_url(clean_tag)
                    if hashtag_url and hashtag_url not in sources:
                        sources.append(hashtag_url)
                except ValueError as err:
                    logger.warning("Skipping invalid target hashtag %r: %s", clean_tag, err)

    if not sources:
        sources.append(None)

    return sources


async def check_halted(state: ScoutState, config: RunnableConfig) -> dict[str, Any]:
    """Verify circuit breaker and pause switch before proceeding."""
    context = get_graph_context(config)
    halted, reason = is_halted(context.settings.state_dir.parent, context.settings)
    if halted:
        logger.warning("Scout graph check_halted: halted (%s)", reason)
        return {"halted_reason": reason, "status": "halted"}
    return {"halted_reason": None, "status": "active"}


async def prune_expired(state: ScoutState, config: RunnableConfig) -> dict[str, Any]:
    """Prune expired pending actions from durable state and update Telegram messages."""
    context = get_graph_context(config)
    if not context.state_store:
        return {"pruned_items": []}

    ttl_hours = context.settings.pending_action_ttl_hours
    pruned = context.state_store.prune_expired_pending(ttl_hours=ttl_hours)
    logger.info("Pruned %d expired pending action(s) (TTL=%dh)", len(pruned), ttl_hours)

    if context.telegram and pruned:
        for item in pruned:
            chat_id = item.telegram_chat_id or context.settings.telegram_authorized_chat_id
            msg_id = item.telegram_message_id
            if msg_id and msg_id > 0:
                try:
                    await context.telegram.edit_to_outcome(
                        chat_id=chat_id,
                        message_id=msg_id,
                        outcome_text="⏱️ Suggestion expired (exceeded approval TTL)",
                    )
                except Exception as err:
                    logger.warning(
                        "Failed to update Telegram outcome for expired item %s (msg_id=%s): %s",
                        item.item_id,
                        msg_id,
                        err,
                    )

    return {"pruned_items": pruned}


async def load_seen(state: ScoutState, config: RunnableConfig) -> dict[str, Any]:
    """Load previously seen post hashes from durable state."""
    context = get_graph_context(config)
    seen_hashes: set[str] = set()
    if context.state_store:
        seen_hashes = context.state_store.load_seen_hashes(ttl_days=30)
    logger.info("Loaded %d previously seen post hashes", len(seen_hashes))
    return {"seen_hashes": seen_hashes}


async def scrape_feed(state: ScoutState, config: RunnableConfig) -> dict[str, Any]:
    """Scrape candidate posts across configured LinkedIn feed sources."""
    context = get_graph_context(config)
    if not context.scraper:
        return {"posts": [], "status": "no_scraper"}

    seen_hashes = set(state.get("seen_hashes", []))
    target_sources = get_scout_target_sources(context.settings)
    max_total_posts = context.settings.max_suggestions_per_run * 3

    all_posts: list[PostRecord] = []
    errors: list[str] = list(state.get("errors", []))

    for idx, target_url in enumerate(target_sources):
        if len(all_posts) >= max_total_posts:
            logger.info(
                "Reached candidate post limit (%d/%d), skipping remaining %d target source(s)",
                len(all_posts),
                max_total_posts,
                len(target_sources) - idx,
            )
            break

        if idx > 0:
            logger.info(
                "Dwelling between scout target navigations (%d/%d)...",
                idx + 1,
                len(target_sources),
            )
            await humanized_dwell(min_seconds=1.5, max_seconds=3.5)

        remaining = max_total_posts - len(all_posts)
        try:
            posts = await context.scraper.scrape_feed(
                max_posts=remaining,
                seen_hashes=seen_hashes,
                target_url=target_url,
            )
            all_posts.extend(posts)
            for p in posts:
                seen_hashes.add(p.content_hash)
            logger.info(
                "Target source '%s' yielded %d post(s) (total candidates: %d/%d)",
                target_url or "default_feed",
                len(posts),
                len(all_posts),
                max_total_posts,
            )
        except BotDetectionError as err:
            logger.error("Bot challenge encountered during feed scrape: %s", err)
            if context.state_store:
                trip_breaker(context.settings.state_dir.parent, reason=str(err))
            if context.telegram:
                await context.telegram.send_notification(f"⚠️ Circuit breaker tripped: {err}")
            return {"halted_reason": str(err), "status": "halted_bot_detection", "posts": []}
        except SessionExpiredError as err:
            logger.warning(
                "LinkedIn session expired or unauthenticated on target '%s': %s",
                target_url or "default_feed",
                err,
            )
            if context.telegram:
                await context.telegram.send_notification(
                    f"🔑 LinkedIn session expired or unauthenticated: {err}. Please re-authenticate using scripts/extract_linkedin_session.py"
                )
            return {"errors": [str(err)], "posts": [], "status": "session_expired"}
        except ScrapeError as err:
            logger.warning(
                "Scrape error encountered for target '%s': %s",
                target_url or "default_feed",
                err,
            )
            errors.append(f"Target '{target_url or 'default_feed'}': {err}")
            continue

    if not all_posts and errors:
        return {"errors": errors, "posts": [], "status": "scrape_error"}

    return {"posts": all_posts, "seen_hashes": seen_hashes, "status": "scraped", "errors": errors}


async def triage_batch(state: ScoutState, config: RunnableConfig) -> dict[str, Any]:
    """Evaluate scraped posts with LLM triage chain."""
    context = get_graph_context(config)
    if not context.llm:
        return {"triage_results": []}

    posts = state.get("posts", [])
    results: list[tuple[PostRecord, TriageResult]] = []
    errors: list[str] = list(state.get("errors", []))

    async def _evaluate_one(post: PostRecord) -> tuple[PostRecord, TriageResult] | None:
        assert context.llm is not None
        try:
            triage = await context.llm.evaluate_post(post)
            return (post, triage)
        except Exception as err:
            errors.append(f"Triage failed for {post.post_urn}: {err}")
            return None

    tasks = [_evaluate_one(p) for p in posts]
    evaluated = await asyncio.gather(*tasks)

    for item in evaluated:
        if item is not None:
            post, triage = item
            logger.info(
                "Triage [%s] by '%s' -> %s (conf: %.2f) - Reason: %s",
                post.post_urn,
                post.author_name,
                triage.recommendation.upper(),
                triage.confidence,
                triage.reasoning,
            )
            results.append(item)

    qualifying_count = sum(1 for _, t in results if t.recommendation == "comment")
    logger.info(
        "Triage complete: %d/%d post(s) qualified for comment drafting",
        qualifying_count,
        len(results),
    )

    return {"triage_results": results, "errors": errors}


async def draft_batch(state: ScoutState, config: RunnableConfig) -> dict[str, Any]:
    """Generate comment drafts for posts that passed triage."""
    context = get_graph_context(config)
    if not context.llm:
        return {"drafts": []}

    triage_results = state.get("triage_results", [])
    qualifying = [(p, t) for p, t in triage_results if t.recommendation == "comment"]

    drafts: list[tuple[PostRecord, TriageResult, CommentDraft]] = []
    errors: list[str] = list(state.get("errors", []))

    async def _draft_one(
        post: PostRecord, triage: TriageResult
    ) -> tuple[PostRecord, TriageResult, CommentDraft] | None:
        assert context.llm is not None
        try:
            draft = await context.llm.draft_comment(post, triage)
            return (post, triage, draft)
        except Exception as err:
            errors.append(f"Drafting failed for {post.post_urn}: {err}")
            return None

    tasks = [_draft_one(p, t) for p, t in qualifying]
    generated = await asyncio.gather(*tasks)

    for item in generated:
        if item is not None:
            drafts.append(item)

    logger.info("Successfully generated %d comment draft(s)", len(drafts))
    return {"drafts": drafts, "errors": errors}


async def rank_and_build_pending(state: ScoutState, config: RunnableConfig) -> dict[str, Any]:
    """Rank draft candidates by confidence and create PendingAction models."""
    context = get_graph_context(config)
    drafts = state.get("drafts", [])
    sorted_drafts = sorted(drafts, key=lambda x: x[1].confidence, reverse=True)

    max_suggestions = context.settings.max_suggestions_per_run
    top_candidates = sorted_drafts[:max_suggestions]

    now = datetime.now(UTC)
    pending_items: list[PendingAction] = []
    connection_candidates: list[ConnectionRequestAction] = []

    for post, triage, draft in top_candidates:
        item_id = hashlib.sha256(f"{post.post_urn}:{now.isoformat()}".encode()).hexdigest()[:8]
        pending = PendingAction(
            item_id=item_id,
            action_type="approve_comment",
            created_at=now,
            post_urn=post.post_urn,
            post_url=post.post_url,
            author_name=post.author_name,
            post_excerpt=post.post_text[:200],
            draft_text=draft.draft_comment,
            confidence=triage.confidence,
            reasoning=triage.reasoning,
            engagement_style=draft.engagement_style or triage.engagement_style,
            telegram_chat_id=context.settings.telegram_authorized_chat_id,
            telegram_message_id=0,
        )
        pending_items.append(pending)

        # Connection outreach candidate discovery
        if post.author_name and post.author_name != "LinkedIn Member" and triage.confidence >= 0.7:
            profile_url = getattr(post, "author_profile_url", None) or ""
            if not profile_url:
                slug = re.sub(r"[^a-zA-Z0-9-]", "", post.author_name.lower().replace(" ", "-"))
                profile_url = f"https://www.linkedin.com/in/{slug}/"
            conn_id = f"conn-{hashlib.sha256(profile_url.encode()).hexdigest()[:8]}"
            first_name = post.author_name.split()[0]
            candidate = ConnectionRequestAction(
                id=conn_id,
                profile_url=profile_url,
                target_name=post.author_name,
                mutual_context=f"Interacted with {post.author_name}'s post on LinkedIn",
                note_text=f"Hi {first_name}, I enjoyed your recent post on LinkedIn and would value connecting!",
                status="pending",
                created_at=now,
            )
            connection_candidates.append(candidate)

    return {"pending_items": pending_items, "connection_candidates": connection_candidates}


async def persist_state(state: ScoutState, config: RunnableConfig) -> dict[str, Any]:
    """Persist new pending items, connection candidates, and update seen hashes in durable state."""
    context = get_graph_context(config)
    if not context.state_store:
        return {}

    pending_items = state.get("pending_items", [])
    connection_candidates = state.get("connection_candidates", [])
    posts = state.get("posts", [])

    for item in pending_items:
        context.state_store.write_pending(item)

    for candidate in connection_candidates:
        context.state_store.add_connection_candidate(candidate)

    if posts:
        context.state_store.record_seen_posts(posts)

    return {}


async def send_telegram_suggestions(state: ScoutState, config: RunnableConfig) -> dict[str, Any]:
    """Deliver suggestion messages with inline Approve/Reject keyboards to Telegram."""
    context = get_graph_context(config)
    if not context.telegram or not context.state_store:
        return {"status": "completed_no_telegram"}

    pending_items = state.get("pending_items", [])
    updated_items: list[PendingAction] = []
    errors: list[str] = list(state.get("errors", []))

    for item in pending_items:
        try:
            msg_id = await context.telegram.send_suggestion(item)
            item_with_msg = item.model_copy(update={"telegram_message_id": msg_id})
            context.state_store.write_pending(item_with_msg)
            updated_items.append(item_with_msg)
        except Exception as err:
            logger.error(
                "Failed to send Telegram suggestion for pending item %s: %s",
                item.item_id,
                err,
            )
            errors.append(f"Telegram delivery failed for {item.item_id}: {err}")

    if context.state_store and updated_items:
        context.state_store.increment_suggestion_count(count=len(updated_items))

    return {"pending_items": updated_items, "status": "completed", "errors": errors}


# Conditional Route Functions
def route_after_halt_check(state: ScoutState) -> str:
    if state.get("halted_reason"):
        return END
    return "prune_expired"


def route_after_scrape(state: ScoutState) -> str:
    if state.get("halted_reason") or not state.get("posts"):
        return END
    return "triage_batch"


def route_after_triage(state: ScoutState) -> str:
    triage_results = state.get("triage_results", [])
    has_qualifying = any(t.recommendation == "comment" for _, t in triage_results)
    if not has_qualifying:
        return END
    return "draft_batch"


def build_scout_graph() -> Any:
    """Build and compile the deterministic Scout StateGraph."""
    graph = StateGraph(ScoutState)

    graph.add_node("check_halted", check_halted)
    graph.add_node("prune_expired", prune_expired)
    graph.add_node("load_seen", load_seen)
    graph.add_node("scrape_feed", scrape_feed)
    graph.add_node("triage_batch", triage_batch)
    graph.add_node("draft_batch", draft_batch)
    graph.add_node("rank_and_build_pending", rank_and_build_pending)
    graph.add_node("persist_state", persist_state)
    graph.add_node("send_telegram_suggestions", send_telegram_suggestions)

    graph.add_edge(START, "check_halted")
    graph.add_conditional_edges("check_halted", route_after_halt_check, [END, "prune_expired"])
    graph.add_edge("prune_expired", "load_seen")
    graph.add_edge("load_seen", "scrape_feed")
    graph.add_conditional_edges("scrape_feed", route_after_scrape, [END, "triage_batch"])
    graph.add_conditional_edges("triage_batch", route_after_triage, [END, "draft_batch"])
    graph.add_edge("draft_batch", "rank_and_build_pending")
    graph.add_edge("rank_and_build_pending", "persist_state")
    graph.add_edge("persist_state", "send_telegram_suggestions")
    graph.add_edge("send_telegram_suggestions", END)

    return graph.compile()
