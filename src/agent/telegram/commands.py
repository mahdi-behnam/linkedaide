"""Telegram operator Command & Control (C2) command executions.

Architecture Invariants:
- Human approval invariant: commands inspect or configure agent operation, never trigger writes.
- Strict authorization: only messages from TELEGRAM_AUTHORIZED_CHAT_ID are processed; unauthorized
  requests produce zero state mutations and zero response.
- Safety & Circuit Breaker: provides operational transparency and safe breaker reset controls.
- Deterministic formatting: outputs clean, parse_mode="HTML" compatible reports.
"""

from __future__ import annotations

import hashlib
import html
import logging
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from agent.config import Settings
from agent.models import PendingAction, PostIdeationContext
from agent.safety.circuit_breaker import is_halted
from agent.state.base import BaseStateStore
from agent.telegram.client import TelegramClient
from agent.telegram.reply_keyboards import build_docked_reply_keyboard

logger = logging.getLogger(__name__)


async def execute_status_command(
    settings: Settings,
    state_store: BaseStateStore,
    telegram: TelegramClient,
    repo_root: Path,
    chat_id: int,
    message_id: int | None = None,
) -> str:
    """Execute /status command: operational state, breaker, daily counters, and pending count.

    Args:
        settings: Application runtime settings.
        state_store: Durable state store instance.
        telegram: Telegram client for sending responses.
        repo_root: Path to repository root.
        chat_id: Target chat ID.
        message_id: Optional reply-to message ID.

    Returns:
        str: The rendered HTML status message sent to Telegram.
    """
    halted, halt_reason = is_halted(repo_root, settings, state_store=state_store)
    incident = state_store.read_incident()

    if incident is not None:
        sys_status = "🚨 <b>Halted (Circuit Breaker Tripped)</b>"
        reason_esc = html.escape(str(incident.get("reason", "Incident detected")), quote=True)
        tripped_at = str(incident.get("tripped_at", incident.get("created_at", "Unknown")))
        cb_status = (
            f"🔴 <b>Tripped</b>\n"
            f"  • <i>Reason:</i> {reason_esc}\n"
            f"  • <i>Tripped At:</i> <code>{html.escape(tripped_at, quote=True)}</code>"
        )
    elif halted or settings.agent_paused or state_store.is_paused():
        sys_status = "⏸️ <b>Paused</b>"
        cb_status = "🟢 <b>Normal</b> (No active incident)"
    else:
        sys_status = "🟢 <b>Operational</b>"
        cb_status = "🟢 <b>Normal</b> (No active incident)"

    counters = state_store.load_daily_counters()
    pending_items = state_store.list_pending()
    pending_count = len(pending_items)

    focus_areas_str = (
        ", ".join(settings.user_focus_areas) if settings.user_focus_areas else "General"
    )
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

    is_paused_now = bool(halted or settings.agent_paused or state_store.is_paused())
    await telegram.send_message(
        chat_id=chat_id,
        text=report,
        reply_markup=build_docked_reply_keyboard(is_paused=is_paused_now),
        reply_to_message_id=message_id,
    )
    return report


async def execute_stats_command(
    state_store: BaseStateStore,
    telegram: TelegramClient,
    chat_id: int,
    message_id: int | None = None,
) -> str:
    """Execute /stats command: trailing metrics from state/history.jsonl.

    Args:
        state_store: Durable state store instance.
        telegram: Telegram client for sending responses.
        chat_id: Target chat ID.
        message_id: Optional reply-to message ID.

    Returns:
        str: The rendered HTML stats message sent to Telegram.
    """
    history_entries = state_store.read_history()
    total_actions = len(history_entries)

    approved_count = sum(
        1 for e in history_entries if e.final_status in ("approved", "executed_success")
    )
    rejected_count = sum(1 for e in history_entries if e.final_status == "rejected")
    expired_count = sum(1 for e in history_entries if e.final_status == "expired")
    failed_count = sum(
        1
        for e in history_entries
        if e.final_status in ("failed", "error", "executed_failed", "halted")
        or (e.error and e.final_status not in ("expired", "rejected"))
    )

    comments_posted = sum(
        1
        for e in history_entries
        if "comment" in e.action_type.lower() and e.final_status in ("approved", "executed_success")
    )
    posts_published = sum(
        1
        for e in history_entries
        if "post" in e.action_type.lower() and e.final_status in ("approved", "executed_success")
    )

    counters = state_store.load_daily_counters()

    if total_actions == 0:
        history_summary = "<i>No historical actions recorded yet.</i>\n"
    else:
        history_summary = (
            f"• <b>Total Actions Logged:</b> {total_actions}\n"
            f"• <b>Approved:</b> {approved_count}\n"
            f"• <b>Rejected:</b> {rejected_count}\n"
            f"• <b>Expired:</b> {expired_count}\n"
            f"• <b>Comments Posted:</b> {comments_posted}\n"
            f"• <b>Posts Published:</b> {posts_published}\n"
            f"• <b>Failures:</b> {failed_count}\n"
        )

    report = (
        "📈 <b>Agent Activity Statistics</b>\n\n"
        f"{history_summary}\n"
        f"📅 <b>Today's Activity ({counters.date})</b>\n"
        f"• <b>Comments Executed:</b> {counters.comments_executed}\n"
        f"• <b>Posts Executed:</b> {counters.posts_executed}\n"
        f"• <b>Suggestions Sent:</b> {counters.suggestions_sent}"
    )

    await telegram.send_message(
        chat_id=chat_id,
        text=report,
        reply_to_message_id=message_id,
    )
    return report


async def execute_pending_command(
    state_store: BaseStateStore,
    telegram: TelegramClient,
    chat_id: int,
    message_id: int | None = None,
) -> str:
    """Execute /pending command: lists all pending actions with target links and status.

    Args:
        state_store: Durable state store instance.
        telegram: Telegram client for sending responses.
        chat_id: Target chat ID.
        message_id: Optional reply-to message ID.

    Returns:
        str: The rendered HTML pending list message sent to Telegram.
    """
    pending_items = state_store.list_pending()
    if not pending_items:
        empty_msg = "📋 <b>Pending Actions</b>\n\nNo actions currently awaiting approval."
        await telegram.send_message(
            chat_id=chat_id,
            text=empty_msg,
            reply_to_message_id=message_id,
        )
        return empty_msg

    lines = [f"📋 <b>Pending Actions ({len(pending_items)})</b>\n"]
    for idx, item in enumerate(pending_items, start=1):
        action_label = "Comment" if "comment" in item.action_type.lower() else "Post"
        author_esc = html.escape(item.author_name or "Unknown", quote=True)
        url = (item.post_url or "").strip()
        if url:
            target_link = f'<a href="{html.escape(url, quote=True)}">LinkedIn Post</a>'
        else:
            target_link = "<i>No URL</i>"

        if hasattr(item.created_at, "strftime"):
            created_str = item.created_at.strftime("%Y-%m-%d %H:%M UTC")
        else:
            created_str = str(item.created_at)

        draft_snippet = item.draft_text[:100] + ("..." if len(item.draft_text) > 100 else "")
        draft_esc = html.escape(draft_snippet, quote=True)
        conf_str = f"{int(item.confidence * 100)}%" if item.confidence is not None else "N/A"

        lines.append(
            f"{idx}. <b>{action_label}</b> (<code>{item.item_id}</code>)\n"
            f"   • <b>Target:</b> {target_link}\n"
            f"   • <b>Author:</b> {author_esc} (Confidence: {conf_str})\n"
            f"   • <b>Created:</b> <code>{html.escape(created_str, quote=True)}</code>\n"
            f'   • <b>Draft:</b> <i>"{draft_esc}"</i>'
        )

    report = "\n\n".join(lines)
    await telegram.send_message(
        chat_id=chat_id,
        text=report,
        reply_to_message_id=message_id,
    )
    return report


async def execute_pause_command(
    settings: Settings,
    state_store: BaseStateStore,
    telegram: TelegramClient,
    chat_id: int,
    message_id: int | None = None,
) -> str:
    """Execute /pause command: remotely suspend automated agent operations.

    Args:
        settings: Application runtime settings.
        state_store: Durable state store instance.
        telegram: Telegram client for sending responses.
        chat_id: Target chat ID.
        message_id: Optional reply-to message ID.

    Returns:
        str: The confirmation message sent to Telegram.
    """
    settings.agent_paused = True
    state_store.set_paused(True)

    msg = (
        "⏸️ <b>Agent Paused</b>\n\n"
        "All automated scouting, triage, and execution workflows are now suspended.\n"
        "Use /resume to restart operations."
    )
    await telegram.send_message(
        chat_id=chat_id,
        text=msg,
        reply_markup=build_docked_reply_keyboard(is_paused=True),
        reply_to_message_id=message_id,
    )
    return msg


async def execute_resume_command(
    settings: Settings,
    state_store: BaseStateStore,
    telegram: TelegramClient,
    chat_id: int,
    message_id: int | None = None,
) -> str:
    """Execute /resume command: remotely activate automated agent operations.

    Args:
        settings: Application runtime settings.
        state_store: Durable state store instance.
        telegram: Telegram client for sending responses.
        chat_id: Target chat ID.
        message_id: Optional reply-to message ID.

    Returns:
        str: The confirmation message sent to Telegram.
    """
    settings.agent_paused = False
    state_store.set_paused(False)

    msg = (
        "▶️ <b>Agent Resumed</b>\n\n"
        "Automated workflows are now active and ready to scout and execute according to schedule."
    )
    await telegram.send_message(
        chat_id=chat_id,
        text=msg,
        reply_markup=build_docked_reply_keyboard(is_paused=False),
        reply_to_message_id=message_id,
    )
    return msg


async def execute_clear_incident_command(
    state_store: BaseStateStore,
    telegram: TelegramClient,
    chat_id: int,
    message_id: int | None = None,
) -> str:
    """Execute /clear_incident command: safely resets the circuit breaker.

    Args:
        state_store: Durable state store instance.
        telegram: Telegram client for sending responses.
        chat_id: Target chat ID.
        message_id: Optional reply-to message ID.

    Returns:
        str: The result message sent to Telegram.
    """
    cleared = state_store.clear_incident()
    if cleared:
        msg = (
            "✅ <b>Circuit Breaker Reset</b>\n\n"
            "The incident state file (<code>state/incident.json</code>) was successfully cleared.\n"
            "The circuit breaker is now reset to normal operation."
        )
    else:
        msg = (
            "ℹ️ <b>Circuit Breaker Normal</b>\n\n"
            "No active incident was found. The circuit breaker is not currently tripped."
        )

    await telegram.send_message(
        chat_id=chat_id,
        text=msg,
        reply_to_message_id=message_id,
    )
    return msg


async def execute_help_command(
    telegram: TelegramClient,
    chat_id: int,
    message_id: int | None = None,
) -> str:
    """Execute /help or /start command: display operator command manual.

    Args:
        telegram: Telegram client for sending responses.
        chat_id: Target chat ID.
        message_id: Optional reply-to message ID.

    Returns:
        str: The help menu sent to Telegram.
    """
    msg = (
        "🤖 <b>Operator Command & Control</b>\n\n"
        "Available commands:\n"
        "• /status — Operational state, circuit breaker, and daily counters\n"
        "• /stats — Trailing engagement metrics and historical outcomes\n"
        "• /pending — List all actions currently awaiting operator approval\n"
        "• /pause — Remotely suspend all automated scouting and execution\n"
        "• /resume — Resume automated workflows\n"
        "• /clear_incident — Safely reset a tripped circuit breaker\n"
        "• /post &lt;idea&gt; — Draft an original LinkedIn post from a concept note\n"
        "• /scout &lt;url&gt; — Triage and draft a comment for a specific LinkedIn post\n"
        "• /help — Show this command reference"
    )
    await telegram.send_message(
        chat_id=chat_id,
        text=msg,
        reply_markup=build_docked_reply_keyboard(is_paused=False),
        reply_to_message_id=message_id,
    )
    return msg


async def execute_post_command(
    settings: Settings,
    state_store: BaseStateStore,
    telegram: TelegramClient,
    chat_id: int,
    idea_text: str,
    llm_service: Any | None = None,
    message_id: int | None = None,
) -> str:
    """Draft an original LinkedIn post from an on-demand idea prompt.

    Args:
        settings: Application runtime settings.
        state_store: Durable state store instance.
        telegram: Telegram client for sending cards.
        chat_id: Target chat ID.
        idea_text: User provided concept or topic.
        llm_service: Optional LLM service for post synthesis.
        message_id: Optional reply-to message ID.

    Returns:
        str: Response message text sent to operator.
    """
    clean_idea = idea_text.strip()
    if not clean_idea:
        prompt_msg = (
            "💡 <b>Draft an Original Post:</b>\n\n"
            "Provide an idea, concept, or topic note after <code>/post</code>.\n\n"
            "<i>Example:</i> <code>/post 3 subtle pitfalls when building production agentic loops</code>"
        )
        await telegram.send_message(
            chat_id=chat_id,
            text=prompt_msg,
            reply_to_message_id=message_id,
        )
        return prompt_msg

    now = datetime.now(UTC)
    draft_content = clean_idea
    reasoning = f"On-demand draft from operator note: {clean_idea[:100]}"

    if llm_service and hasattr(llm_service, "draft_post_idea"):
        try:
            ctx = PostIdeationContext(user_focus_areas=[clean_idea], recent_topics=[])
            idea_obj = await llm_service.draft_post_idea(ctx)
            if idea_obj and idea_obj.draft_post_text:
                draft_content = idea_obj.draft_post_text
                reasoning = getattr(idea_obj, "headline", "") or getattr(idea_obj, "reasoning", "") or reasoning
        except Exception as err:
            logger.warning("LLM drafting failed for /post, using raw note: %s", err)

    item_id = hashlib.sha256(f"post:{clean_idea}:{now.isoformat()}".encode()).hexdigest()[:8]
    pending = PendingAction(
        item_id=item_id,
        action_type="approve_post",
        created_at=now,
        post_url="",
        author_name="You",
        author_headline="Operator Draft",
        post_excerpt="",
        draft_text=draft_content,
        confidence=1.0,
        reasoning=reasoning,
        telegram_chat_id=chat_id,
        telegram_message_id=0,
    )
    state_store.write_pending(pending)
    sent_msg_id = await telegram.send_suggestion(pending)
    pending.telegram_message_id = sent_msg_id
    state_store.write_pending(pending)

    return f"Created post draft {item_id}"


async def execute_scout_command(
    settings: Settings,
    telegram: TelegramClient,
    chat_id: int,
    target_url: str,
    message_id: int | None = None,
) -> str:
    """Queue or evaluate a specific LinkedIn post target on demand.

    Args:
        settings: Application runtime settings.
        telegram: Telegram client for sending response.
        chat_id: Target chat ID.
        target_url: URL to LinkedIn post.
        message_id: Optional reply-to message ID.

    Returns:
        str: Response message text sent to operator.
    """
    clean_url = target_url.strip()
    if not clean_url:
        prompt_msg = (
            "🧭 <b>On-Demand Target Scouting:</b>\n\n"
            "Provide a target LinkedIn post URL after <code>/scout</code>.\n\n"
            "<i>Example:</i> <code>/scout https://www.linkedin.com/feed/update/urn:li:activity:123456789/</code>"
        )
        await telegram.send_message(
            chat_id=chat_id,
            text=prompt_msg,
            reply_to_message_id=message_id,
        )
        return prompt_msg

    url_esc = html.escape(clean_url, quote=True)
    confirm_msg = (
        "🧭 <b>Target Received:</b>\n\n"
        f"Queued for on-demand scouting:\n<a href=\"{url_esc}\">{url_esc}</a>\n\n"
        "<i>The agent will evaluate this target against your focus areas and deliver a draft comment card for your review.</i>"
    )
    await telegram.send_message(
        chat_id=chat_id,
        text=confirm_msg,
        reply_to_message_id=message_id,
    )
    return confirm_msg


async def execute_unknown_command(
    telegram: TelegramClient,
    chat_id: int,
    command: str,
    message_id: int | None = None,
) -> str:
    """Handle unrecognized commands with a helpful notice.

    Args:
        telegram: Telegram client for sending responses.
        chat_id: Target chat ID.
        command: The unrecognized command name.
        message_id: Optional reply-to message ID.

    Returns:
        str: The notice sent to Telegram.
    """
    cmd_esc = html.escape(command, quote=True)
    msg = (
        f"❓ <b>Unknown Command:</b> <code>/{cmd_esc}</code>\n\n"
        "Send /help to view the list of available operator commands."
    )
    await telegram.send_message(
        chat_id=chat_id,
        text=msg,
        reply_to_message_id=message_id,
    )
    return msg
