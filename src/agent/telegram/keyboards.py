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
    ACTION_CODE_APPROVE_REPLY,
    ACTION_CODE_REJECT_COMMENT,
    ACTION_CODE_REJECT_CONNECTION,
    ACTION_CODE_REJECT_POST,
    ACTION_CODE_REJECT_REPLY,
    PendingAction,
)


def build_suggestion_keyboard(item_id: str, action_type: str = "approve_comment") -> dict[str, Any]:
    """Construct inline keyboard with Approve, Reject, Regenerate, and Edit buttons.

    Args:
        item_id: Unique identifier for the pending action item.
        action_type: One of 'approve_comment', 'approve_post', 'approve_reply', or 'approve_connection'.

    Returns:
        Telegram inline_keyboard reply_markup dictionary.

    Raises:
        ValueError: If callback_data exceeds Telegram's 64-byte limit.
    """
    clean_id = item_id.strip()
    if action_type in ("approve_post", "post"):
        approve_code = ACTION_CODE_APPROVE_POST
        reject_code = ACTION_CODE_REJECT_POST
    elif action_type in ("approve_reply", "reply"):
        approve_code = ACTION_CODE_APPROVE_REPLY
        reject_code = ACTION_CODE_REJECT_REPLY
    elif action_type in ("approve_connection", "connection"):
        approve_code = ACTION_CODE_APPROVE_CONNECTION
        reject_code = ACTION_CODE_REJECT_CONNECTION
    else:
        approve_code = ACTION_CODE_APPROVE_COMMENT
        reject_code = ACTION_CODE_REJECT_COMMENT

    approve_cb = f"{approve_code}:{clean_id}"
    reject_cb = f"{reject_code}:{clean_id}"
    reg_cb = f"reg:{clean_id}"
    edit_cb = f"edit:{clean_id}"

    for cb in (approve_cb, reject_cb, reg_cb, edit_cb):
        byte_len = len(cb.encode("utf-8"))
        if byte_len > 64:
            raise ValueError(
                f"Telegram callback_data exceeds 64 bytes limit ({byte_len} bytes): '{cb}'"
            )

    return {
        "inline_keyboard": [
            [
                {"text": "✅ Approve", "callback_data": approve_cb},
                {"text": "❌ Reject", "callback_data": reject_cb},
            ],
            [
                {"text": "🔄 Regenerate", "callback_data": reg_cb},
                {"text": "✏️ Edit", "callback_data": edit_cb},
            ],
        ]
    }


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

    if is_post:
        action_label = "📝 Original Post"
    elif is_reply:
        action_label = "💬 Thread Reply"
    elif is_conn:
        action_label = "🤝 Connection Request"
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
            f"<b>{excerpt_label}:</b>\n<blockquote>{html.escape(item.post_excerpt)}</blockquote>"
        )

    content_label = "Drafted Note" if is_conn else "Drafted Content"
    lines.append(
        f"<b>{content_label}:</b>\n<blockquote>{html.escape(item.draft_text)}</blockquote>"
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


def build_outcome_message(
    item: PendingAction | None,
    final_status: str,
    error: str | None = None,
) -> str:
    """Format the final outcome status message replacing the interactive suggestion.

    Args:
        item: Optional PendingAction for context summary.
        final_status: Terminal status (executed_success, rejected, expired, executed_failed, halted).
        error: Optional error details if execution failed or halted.

    Returns:
        HTML formatted terminal outcome string.
    """
    status_lower = final_status.lower()

    if status_lower in ("executed_success", "success"):
        header = "<b>✅ Executed Successfully</b>\nAction published to LinkedIn."
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
        else:
            item_type = "Comment"
        lines.append(f"<b>Item:</b> {html.escape(item.item_id)} ({item_type})")
        if item.draft_text:
            lines.append(
                f"<b>Draft:</b> <blockquote>{html.escape(item.draft_text[:200])}</blockquote>"
            )

    if error:
        lines.append(f"<b>Error Details:</b>\n<code>{html.escape(error)}</code>")

    return "\n\n".join(lines)
