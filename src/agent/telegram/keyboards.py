"""Telegram inline keyboard builders and HTML message formatters.

Architecture Invariants:
- All inline keyboards stay strictly under Telegram's 64-byte callback_data limit.
- All dynamic strings are HTML-escaped to prevent injection or formatting breakages.
- Clear, structured suggestion and terminal outcome representations.
"""

import html
from typing import Any

from agent.models import (
    ACTION_CODE_APPROVE_COMMENT,
    ACTION_CODE_APPROVE_CONNECTION,
    ACTION_CODE_APPROVE_POST,
    ACTION_CODE_APPROVE_REACTION,
    ACTION_CODE_APPROVE_REPLY,
    ACTION_CODE_ASK_REJECT,
    ACTION_CODE_BACK,
    ACTION_CODE_CANCEL_EDIT,
    ACTION_CODE_CANCEL_REJECT,
    ACTION_CODE_CLOSE,
    ACTION_CODE_CONFIRM_REJECT,
    ACTION_CODE_EDIT,
    ACTION_CODE_FEEDBACK,
    ACTION_CODE_HOME,
    ACTION_CODE_NOOP,
    ACTION_CODE_REFRESH,
    ACTION_CODE_REGENERATE,
    ACTION_CODE_RESET_CB,
    ACTION_CODE_REVIEW,
    ACTION_CODE_TONE,
    PendingAction,
)


def build_suggestion_keyboard(
    item_id: str,
    action_type: str = "approve_comment",
    post_url: str | None = None,
    include_home: bool = True,
) -> dict[str, Any]:
    """Construct inline keyboard with Approve, Reject, Regenerate, Edit, and optional URL button.

    Args:
        item_id: Unique identifier for the pending action item.
        action_type: One of 'approve_comment', 'approve_post', 'approve_reply', or 'approve_connection'.
        post_url: Optional direct LinkedIn post URL for 1-tap verification.
        include_home: Whether to include the standard Home Menu navigation button.

    Returns:
        Telegram inline_keyboard reply_markup dictionary.

    Raises:
        ValueError: If callback_data exceeds Telegram's 64-byte limit.
    """
    clean_id = item_id.strip()
    is_reaction = action_type in ("approve_reaction", "reaction")
    if action_type in ("approve_post", "post"):
        approve_code = ACTION_CODE_APPROVE_POST
    elif action_type in ("approve_reply", "reply"):
        approve_code = ACTION_CODE_APPROVE_REPLY
    elif action_type in ("approve_connection", "connection"):
        approve_code = ACTION_CODE_APPROVE_CONNECTION
    elif is_reaction:
        approve_code = ACTION_CODE_APPROVE_REACTION
    else:
        approve_code = ACTION_CODE_APPROVE_COMMENT

    approve_cb = f"{approve_code}:{clean_id}"
    reject_cb = f"{ACTION_CODE_ASK_REJECT}:{clean_id}"
    reg_cb = f"{ACTION_CODE_REGENERATE}:{clean_id}"
    edit_cb = f"{ACTION_CODE_EDIT}:{clean_id}"
    home_cb = f"{ACTION_CODE_HOME}:menu"

    callbacks = [approve_cb, reject_cb, home_cb]
    if not is_reaction:
        callbacks.extend([reg_cb, edit_cb])

    for cb in callbacks:
        byte_len = len(cb.encode("utf-8"))
        if byte_len > 64:
            raise ValueError(
                f"Telegram callback_data exceeds 64 bytes limit ({byte_len} bytes): '{cb}'"
            )

    rows: list[list[dict[str, str]]] = []
    if post_url and post_url.strip().startswith("http"):
        rows.append([{"text": "🔗 View Post on LinkedIn", "url": post_url.strip()}])

    rows.append([
        {"text": "✅ Approve", "callback_data": approve_cb},
        {"text": "❌ Reject", "callback_data": reject_cb},
    ])
    if not is_reaction:
        rows.append([
            {"text": "🔄 Regenerate", "callback_data": reg_cb},
            {"text": "✏️ Edit", "callback_data": edit_cb},
        ])
    if include_home:
        rows.append([
            {"text": "🏠 Home Menu", "callback_data": home_cb},
        ])

    return {"inline_keyboard": rows}


def build_reject_confirm_keyboard(
    item_id: str, action_type: str = "approve_comment"
) -> dict[str, Any]:
    """Construct rejection confirmation inline keyboard with Confirm, Cancel, and Home buttons.

    Args:
        item_id: Unique identifier for the pending action item.
        action_type: Action type identifier.

    Returns:
        Telegram inline_keyboard reply_markup dictionary.

    Raises:
        ValueError: If callback_data exceeds Telegram's 64-byte limit.
    """
    clean_id = item_id.strip()
    confirm_cb = f"{ACTION_CODE_CONFIRM_REJECT}:{clean_id}"
    cancel_cb = f"{ACTION_CODE_CANCEL_REJECT}:{clean_id}"
    home_cb = f"{ACTION_CODE_HOME}:menu"

    for cb in (confirm_cb, cancel_cb, home_cb):
        byte_len = len(cb.encode("utf-8"))
        if byte_len > 64:
            raise ValueError(
                f"Telegram callback_data exceeds 64 bytes limit ({byte_len} bytes): '{cb}'"
            )

    return {
        "inline_keyboard": [
            [
                {"text": "❌ Yes, Reject", "callback_data": confirm_cb},
                {"text": "🔙 Cancel / Keep", "callback_data": cancel_cb},
            ],
            [
                {"text": "🏠 Home Menu", "callback_data": home_cb},
            ],
        ]
    }


def build_rejection_feedback_keyboard(item_id: str) -> dict[str, Any]:
    """Construct post-rejection feedback tags inline keyboard with Skip and Home navigation.

    Args:
        item_id: Unique identifier for the rejected action item.

    Returns:
        Telegram inline_keyboard reply_markup dictionary.

    Raises:
        ValueError: If callback_data exceeds Telegram's 64-byte limit.
    """
    clean_id = item_id.strip()
    callbacks = [
        f"{ACTION_CODE_FEEDBACK}:generic:{clean_id}",
        f"{ACTION_CODE_FEEDBACK}:boring:{clean_id}",
        f"{ACTION_CODE_FEEDBACK}:risky:{clean_id}",
        f"{ACTION_CODE_FEEDBACK}:offtopic:{clean_id}",
        f"{ACTION_CODE_FEEDBACK}:skip:{clean_id}",
        f"{ACTION_CODE_HOME}:menu",
    ]

    for cb in callbacks:
        byte_len = len(cb.encode("utf-8"))
        if byte_len > 64:
            raise ValueError(
                f"Telegram callback_data exceeds 64 bytes limit ({byte_len} bytes): '{cb}'"
            )

    return {
        "inline_keyboard": [
            [
                {"text": "🤖 Too Generic", "callback_data": callbacks[0]},
                {"text": "🥱 Boring", "callback_data": callbacks[1]},
            ],
            [
                {"text": "⚠️ Too Risky", "callback_data": callbacks[2]},
                {"text": "🚫 Off-Topic", "callback_data": callbacks[3]},
            ],
            [
                {"text": "⏩ Done / Skip", "callback_data": callbacks[4]},
                {"text": "🏠 Home Menu", "callback_data": callbacks[5]},
            ],
        ]
    }


def build_tone_keyboard(
    item_id: str, action_type: str = "approve_comment"
) -> dict[str, Any]:
    """Construct dynamic inline tone picker keyboard aligned with desktop app.

    Args:
        item_id: Unique identifier for the pending action item.
        action_type: Action type identifier ('approve_connection' vs other actions).

    Returns:
        Telegram inline_keyboard reply_markup dictionary.

    Raises:
        ValueError: If callback_data exceeds Telegram's 64-byte limit.
    """
    clean_id = item_id.strip()
    is_conn = action_type in ("approve_connection", "connection")
    back_cb = f"{ACTION_CODE_BACK}:{clean_id}"
    home_cb = f"{ACTION_CODE_HOME}:menu"

    if is_conn:
        buttons = [
            [
                {"text": "☕ Casual", "callback_data": f"{ACTION_CODE_TONE}:casual:{clean_id}"},
                {"text": "🔬 Technical", "callback_data": f"{ACTION_CODE_TONE}:technical:{clean_id}"},
            ],
            [
                {"text": "✂️ Concise", "callback_data": f"{ACTION_CODE_TONE}:concise:{clean_id}"},
            ],
            [
                {"text": "🔙 Back to Review", "callback_data": back_cb},
                {"text": "🏠 Home Menu", "callback_data": home_cb},
            ],
        ]
    else:
        buttons = [
            [
                {"text": "🔬 Technical", "callback_data": f"{ACTION_CODE_TONE}:technical:{clean_id}"},
                {"text": "❓ Inquisitive", "callback_data": f"{ACTION_CODE_TONE}:inquisitive:{clean_id}"},
            ],
            [
                {"text": "⚡ Contrarian", "callback_data": f"{ACTION_CODE_TONE}:contrarian:{clean_id}"},
                {"text": "✂️ Shorter", "callback_data": f"{ACTION_CODE_TONE}:shorter:{clean_id}"},
            ],
            [
                {"text": "🔙 Back to Review", "callback_data": back_cb},
                {"text": "🏠 Home Menu", "callback_data": home_cb},
            ],
        ]

    for row in buttons:
        for btn in row:
            cb = btn["callback_data"]
            byte_len = len(cb.encode("utf-8"))
            if byte_len > 64:
                raise ValueError(
                    f"Telegram callback_data exceeds 64 bytes limit ({byte_len} bytes): '{cb}'"
                )

    return {"inline_keyboard": buttons}


def build_editing_keyboard(item_id: str) -> dict[str, Any]:
    """Construct inline keyboard for active draft editing with Cancel Edit and Home buttons.

    Args:
        item_id: Unique identifier for the pending action item.

    Returns:
        Telegram inline_keyboard reply_markup dictionary.
    """
    clean_id = item_id.strip()
    cancel_cb = f"{ACTION_CODE_CANCEL_EDIT}:{clean_id}"
    home_cb = f"{ACTION_CODE_HOME}:menu"
    for cb in (cancel_cb, home_cb):
        byte_len = len(cb.encode("utf-8"))
        if byte_len > 64:
            raise ValueError(
                f"Telegram callback_data exceeds 64 bytes limit ({byte_len} bytes): '{cb}'"
            )
    return {
        "inline_keyboard": [
            [
                {"text": "❌ Cancel Edit", "callback_data": cancel_cb},
                {"text": "🏠 Home Menu", "callback_data": home_cb},
            ],
        ]
    }


def build_regenerating_keyboard(item_id: str) -> dict[str, Any]:
    """Construct inline keyboard displaying AI generation loading state.

    Args:
        item_id: Unique identifier for the pending action item.

    Returns:
        Telegram inline_keyboard reply_markup dictionary.
    """
    clean_id = item_id.strip()
    noop_cb = f"{ACTION_CODE_NOOP}:{clean_id}"
    return {
        "inline_keyboard": [
            [{"text": "⏳ Generating with AI...", "callback_data": noop_cb}],
        ]
    }


def build_pending_list_keyboard(
    items: list[PendingAction], max_items: int = 5, include_nav: bool = True
) -> dict[str, Any]:
    """Construct inline keyboard for /pending list with direct review buttons and nav footer.

    Args:
        items: List of PendingAction items awaiting operator review.
        max_items: Maximum items to attach direct buttons for.
        include_nav: Whether to append the standard Refresh / Home navigation row.

    Returns:
        Telegram inline_keyboard reply_markup dictionary.
    """
    rows: list[list[dict[str, str]]] = []
    for idx, item in enumerate(items[:max_items], start=1):
        clean_id = item.item_id.strip()
        cb = f"{ACTION_CODE_REVIEW}:{clean_id}"
        if len(cb.encode("utf-8")) <= 64:
            if "post" in item.action_type.lower():
                action_sym = "📝"
            elif "reaction" in item.action_type.lower():
                action_sym = "👍"
            elif "connection" in item.action_type.lower():
                action_sym = "🤝"
            else:
                action_sym = "💬"
            rows.append([
                {"text": f"{action_sym} Review #{idx} ({clean_id[:6]})", "callback_data": cb}
            ])
    if include_nav:
        rows.append([
            {"text": "🔄 Refresh Queue", "callback_data": f"{ACTION_CODE_REFRESH}:pending"},
            {"text": "🏠 Home Menu", "callback_data": f"{ACTION_CODE_HOME}:menu"},
        ])
    return {"inline_keyboard": rows}


def build_status_keyboard(
    is_tripped: bool = False, pending_count: int = 0, include_nav: bool = True
) -> dict[str, Any]:
    """Construct inline keyboard for /status report with quick action buttons and nav footer.

    Args:
        is_tripped: True if circuit breaker is tripped.
        pending_count: Number of actions currently pending approval.
        include_nav: Whether to append the standard Refresh / Home navigation row.

    Returns:
        Telegram inline_keyboard reply_markup dictionary.
    """
    rows: list[list[dict[str, str]]] = []
    if is_tripped:
        rows.append([
            {"text": "🔄 Reset Circuit Breaker", "callback_data": f"{ACTION_CODE_RESET_CB}:global"}
        ])
    if pending_count > 0:
        rows.append([
            {"text": f"📋 Review Pending ({pending_count})", "callback_data": f"{ACTION_CODE_REVIEW}:list"}
        ])
    if include_nav:
        rows.append([
            {"text": "🔄 Refresh Status", "callback_data": f"{ACTION_CODE_REFRESH}:status"},
            {"text": "🏠 Home Menu", "callback_data": f"{ACTION_CODE_HOME}:menu"},
        ])
    return {"inline_keyboard": rows}


def build_stats_keyboard() -> dict[str, Any]:
    """Construct inline keyboard for /stats report with Refresh and Home buttons.

    Returns:
        Telegram inline_keyboard reply_markup dictionary.
    """
    return {
        "inline_keyboard": [
            [
                {"text": "🔄 Refresh Stats", "callback_data": f"{ACTION_CODE_REFRESH}:stats"},
                {"text": "🏠 Home Menu", "callback_data": f"{ACTION_CODE_HOME}:menu"},
            ],
        ]
    }


def build_help_keyboard() -> dict[str, Any]:
    """Construct inline keyboard for /help manual with Home Menu and Status Report shortcuts.

    Returns:
        Telegram inline_keyboard reply_markup dictionary.
    """
    return {
        "inline_keyboard": [
            [
                {"text": "🏠 Home Menu", "callback_data": f"{ACTION_CODE_HOME}:menu"},
                {"text": "📊 Status Report", "callback_data": f"{ACTION_CODE_REFRESH}:status"},
            ],
        ]
    }


def build_home_keyboard(
    is_tripped: bool = False,
    pending_count: int = 0,
    is_paused: bool = False,
) -> dict[str, Any]:
    """Construct inline keyboard for /home Command & Control hub.

    Args:
        is_tripped: True if circuit breaker is tripped.
        pending_count: Number of actions currently pending approval.
        is_paused: True if agent operations are currently paused.

    Returns:
        Telegram inline_keyboard reply_markup dictionary.
    """
    rows: list[list[dict[str, str]]] = []
    if is_tripped:
        rows.append([
            {"text": "🔄 Reset Circuit Breaker", "callback_data": f"{ACTION_CODE_RESET_CB}:global"}
        ])

    review_cb = f"{ACTION_CODE_REVIEW}:list" if pending_count > 0 else f"{ACTION_CODE_REFRESH}:pending"
    pause_text = "▶️ Resume Agent" if is_paused else "⏸️ Pause Agent"
    pause_cb = f"{ACTION_CODE_HOME}:resume" if is_paused else f"{ACTION_CODE_HOME}:pause"

    rows.append([
        {"text": f"📋 Pending ({pending_count})", "callback_data": review_cb},
        {"text": "📊 Status", "callback_data": f"{ACTION_CODE_REFRESH}:status"},
    ])
    rows.append([
        {"text": "📈 Stats", "callback_data": f"{ACTION_CODE_REFRESH}:stats"},
        {"text": pause_text, "callback_data": pause_cb},
    ])
    rows.append([
        {"text": "🔄 Refresh Hub", "callback_data": f"{ACTION_CODE_REFRESH}:home"},
        {"text": "❌ Close Menu", "callback_data": f"{ACTION_CODE_CLOSE}:menu"},
    ])
    return {"inline_keyboard": rows}


def format_home_hub(
    system_state: str,
    cb_status: str,
    pending_count: int,
    counters: Any,
    settings: Any,
) -> str:
    """Format HTML message for Command & Control Home Hub.

    Args:
        system_state: Rendered system state HTML string.
        cb_status: Rendered circuit breaker status HTML string.
        pending_count: Number of items awaiting operator review.
        counters: DailyCounters instance or equivalent object.
        settings: Application Settings instance.

    Returns:
        HTML formatted home hub message string.
    """
    focus_str = ", ".join(settings.user_focus_areas) if settings.user_focus_areas else "General"
    date_str = getattr(counters, "date", "Today")
    comments_executed = getattr(counters, "comments_executed", 0)
    posts_executed = getattr(counters, "posts_executed", 0)
    suggestions_sent = getattr(counters, "suggestions_sent", 0)

    lines = [
        "<b>🏠 LinkedIn HITL Agent — Command & Control Hub</b>\n",
        f"• <b>System State:</b> {system_state}",
        f"• <b>Circuit Breaker:</b> {cb_status}",
        f"• <b>Pending Queue:</b> <b>{pending_count}</b> action(s) awaiting review\n",
        f"📊 <b>Today's Activity ({html.escape(str(date_str))})</b>",
        f"• <b>Comments:</b> {comments_executed} / {settings.max_comments_per_day}",
        f"• <b>Posts:</b> {posts_executed} / {settings.max_posts_per_day}",
        f"• <b>Suggestions Sent:</b> {suggestions_sent}\n",
        f"🎯 <b>Focus Areas:</b> <i>{html.escape(focus_str)}</i>\n",
        "<i>Select an option below or use docked buttons:</i>",
    ]
    return "\n".join(lines)


def format_suggestion_card(item: PendingAction) -> str:
    """Format an action suggestion card with rich HTML styling and metrics.

    Includes target post author, headline, clean excerpt blockquotes,
    character/word count metrics, confidence, and reasoning.

    Args:
        item: PendingAction containing context, author, draft, and confidence.

    Returns:
        HTML formatted message card string.
    """
    is_post = item.action_type in ("approve_post", "post")
    is_reply = item.action_type in ("approve_reply", "reply")
    is_conn = item.action_type in ("approve_connection", "connection")
    is_reaction = item.action_type in ("approve_reaction", "reaction")

    if is_post:
        action_label = "📝 Original Post"
    elif is_reply:
        action_label = "💬 Thread Reply"
    elif is_conn:
        action_label = "🤝 Connection Request"
    elif is_reaction:
        rx_name = (getattr(item, "reaction_type", "") or "like").capitalize()
        action_label = f"👍 Reaction ({rx_name})"
    else:
        action_label = "💬 Feed Comment"

    lines: list[str] = [
        "<b>🚀 LinkedIn Action Suggestion</b>",
        f"<b>Type:</b> {action_label}",
    ]

    if item.engagement_style:
        style_raw = (
            item.engagement_style.value
            if hasattr(item.engagement_style, "value")
            else str(item.engagement_style)
        )
        style_label = " ".join(w.capitalize() for w in style_raw.replace("_", " ").split())
        lines.append(f"<b>Style:</b> {html.escape(style_label)}")

    author_name = (item.author_name or "").strip()
    author_headline = (getattr(item, "author_headline", "") or "").strip()
    if author_name and author_headline:
        lines.append(
            f"<b>Author:</b> {html.escape(author_name)} (<i>{html.escape(author_headline)}</i>)"
        )
    elif author_name:
        lines.append(f"<b>Author:</b> {html.escape(author_name)}")
    elif author_headline:
        lines.append(f"<b>Author Headline:</b> <i>{html.escape(author_headline)}</i>")

    if item.post_url:
        lines.append(
            f'<b>Post URL:</b> <a href="{html.escape(item.post_url)}">View on LinkedIn</a>'
        )

    if item.post_excerpt and not is_post:
        excerpt_label = "Parent Comment" if is_reply else "Post Excerpt"
        lines.append(
            f"<b>{excerpt_label}:</b>\n<blockquote expandable>{html.escape(item.post_excerpt)}</blockquote>"
        )

    if is_reaction:
        rx_name = (getattr(item, "reaction_type", "") or "like").capitalize()
        lines.append(f"<b>Proposed Reaction:</b> {html.escape(rx_name)}")
    else:
        content_label = "Drafted Note" if is_conn else "Drafted Content"
        lines.append(
            f"<b>{content_label}:</b>\n<blockquote expandable>{html.escape(item.draft_text)}</blockquote>"
        )
        char_count = len(item.draft_text)
        word_count = len(item.draft_text.split())
        lines.append(f"<b>Metrics:</b> {char_count} chars • {word_count} words")

    confidence_pct = int(item.confidence * 100)
    lines.append(f"<b>Confidence:</b> {confidence_pct}%")

    if item.reasoning:
        lines.append(f"<b>Reasoning:</b> {html.escape(item.reasoning)}")

    lines.append(f"<i>ID: {html.escape(item.item_id)}</i>")

    return "\n\n".join(lines)


def build_suggestion_message(item: PendingAction) -> str:
    """Format a readable HTML suggestion message for Telegram delivery.

    Backwards-compatible alias for format_suggestion_card.

    Args:
        item: PendingAction containing context, author, draft, and confidence.

    Returns:
        HTML formatted message string.
    """
    return format_suggestion_card(item)


def format_rejection_card(item: PendingAction, reason: str | None = None) -> str:
    """Format a rejection status card preserving post author, target link, and draft text.

    Args:
        item: PendingAction containing original suggestion context.
        reason: Optional rejection feedback reason (e.g. 'generic', 'skip').

    Returns:
        HTML formatted rejection summary string.
    """
    is_post = item.action_type in ("approve_post", "post")
    is_reply = item.action_type in ("approve_reply", "reply")
    is_conn = item.action_type in ("approve_connection", "connection")
    is_reaction = item.action_type in ("approve_reaction", "reaction")

    if is_post:
        action_label = "Original Post"
    elif is_reply:
        action_label = "Thread Reply"
    elif is_conn:
        action_label = "Connection Request"
    elif is_reaction:
        rx_name = (getattr(item, "reaction_type", "") or "like").capitalize()
        action_label = f"Reaction ({rx_name})"
    else:
        action_label = "Feed Comment"

    lines: list[str] = [
        "<b>❌ Suggestion Rejected by Operator</b>",
        f"<b>Item:</b> <code>{html.escape(item.item_id)}</code> ({action_label})",
    ]

    author_name = (item.author_name or "").strip()
    if author_name:
        lines.append(f"<b>Author:</b> {html.escape(author_name)}")

    if item.post_url:
        lines.append(f'<b>Target:</b> <a href="{html.escape(item.post_url)}">Original Post</a>')

    if item.draft_text and not is_reaction:
        draft_snippet = item.draft_text[:200] + ("..." if len(item.draft_text) > 200 else "")
        lines.append(f"<b>Draft Excerpt:</b>\n<blockquote expandable>{html.escape(draft_snippet)}</blockquote>")

    if reason and reason != "skip":
        lines.append(f"<b>Feedback:</b> <i>{html.escape(reason)}</i>")
    elif not reason:
        lines.append("<i>Why was this suggestion rejected? (Optional feedback):</i>")

    return "\n\n".join(lines)


def build_outcome_message(
    item: PendingAction | None,
    final_status: str,
    error: str | None = None,
    verification_url: str | None = None,
) -> str:
    """Format the final outcome status message replacing the interactive suggestion.

    Args:
        item: Optional PendingAction for context summary.
        final_status: Terminal status (executed_success, rejected, expired, executed_failed, halted).
        error: Optional error details if execution failed or halted.
        verification_url: Optional direct LinkedIn verification URL for the executed action.

    Returns:
        HTML formatted terminal outcome string.
    """
    status_lower = final_status.lower()

    if status_lower in ("executed_success", "success"):
        if item and item.action_type in ("approve_post", "post"):
            header = "<b>✅ Successfully Published to LinkedIn!</b>"
        elif item and item.action_type in ("approve_reply", "reply"):
            header = "<b>✅ Successfully Replied on LinkedIn!</b>"
        elif item and item.action_type in ("approve_connection", "connection"):
            header = f"<b>✅ Sent Connection Invitation to {html.escape(item.author_name or 'target')}!</b>"
        elif item and item.action_type in ("approve_reaction", "reaction"):
            rx_name = (getattr(item, "reaction_type", "") or "like").capitalize()
            header = f"<b>✅ Successfully Reacted ({html.escape(rx_name)}) on LinkedIn!</b>"
        else:
            header = "<b>✅ Successfully Commented on LinkedIn!</b>"
    elif status_lower in ("rejected", "reject"):
        header = "<b>❌ Suggestion Rejected</b>\nDeclined by operator."
    elif status_lower in ("expired", "expire"):
        header = "<b>⏱️ Suggestion Expired</b>\nApproval window timed out."
    elif status_lower in ("halted", "halt"):
        header = (
            "<b>🛑 System Halted (Circuit Breaker)</b>\nSafety limit or bot challenge triggered."
        )
    else:
        header = "<b>⚠️ Execution Failed</b>\nAction could not be completed."

    lines: list[str] = [header]

    if item:
        if item.action_type in ("approve_post", "post"):
            item_type = "Post"
        elif item.action_type in ("approve_reply", "reply"):
            item_type = "Thread Reply"
        elif item.action_type in ("approve_connection", "connection"):
            item_type = "Connection Request"
        elif item.action_type in ("approve_reaction", "reaction"):
            rx_name = (getattr(item, "reaction_type", "") or "like").capitalize()
            item_type = f"Reaction ({rx_name})"
        else:
            item_type = "Comment"
        lines.append(f"<b>Item:</b> <code>{html.escape(item.item_id)}</code> ({item_type})")
        if item.author_name and item.action_type not in ("approve_post", "post"):
            lines.append(f"<b>Author:</b> {html.escape(item.author_name)}")
        if item.post_url:
            lines.append(f'<b>Target:</b> <a href="{html.escape(item.post_url)}">Original Post</a>')
        if verification_url:
            if item.action_type in ("approve_connection", "connection"):
                lines.append(
                    f'<b>Proof:</b> <a href="{html.escape(verification_url)}">View Profile on LinkedIn ↗</a>'
                )
            elif item.action_type in ("approve_post", "post"):
                lines.append(
                    f'<b>Proof:</b> <a href="{html.escape(verification_url)}">View Your Post on LinkedIn ↗</a>'
                )
            elif item.action_type in ("approve_reaction", "reaction"):
                lines.append(
                    f'<b>Proof:</b> <a href="{html.escape(verification_url)}">View Post on LinkedIn ↗</a>'
                )
            else:
                lines.append(
                    f'<b>Proof:</b> <a href="{html.escape(verification_url)}">View Your Comment on LinkedIn ↗</a>'
                )
        elif item.draft_text and status_lower not in ("executed_success", "success") and item.action_type not in ("approve_reaction", "reaction"):
            lines.append(
                f"<b>Draft:</b> <blockquote expandable>{html.escape(item.draft_text[:200])}</blockquote>"
            )

    if error:
        lines.append(f"<b>Error Details:</b>\n<code>{html.escape(error)}</code>")

    return "\n\n".join(lines)
