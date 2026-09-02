"""Telegram inline keyboard builders and HTML message formatters.

Architecture Invariants:
- All inline keyboards stay strictly under Telegram's 64-byte callback_data limit.
- All dynamic strings are HTML-escaped to prevent injection or formatting breakages.
- Clear, structured suggestion and terminal outcome representations.
"""

import html
from typing import Any

from agent.models.schemas import (
    ACTION_CODE_APPROVE_COMMENT,
    ACTION_CODE_APPROVE_POST,
    ACTION_CODE_REJECT_COMMENT,
    ACTION_CODE_REJECT_POST,
    PendingAction,
)


def build_suggestion_keyboard(item_id: str, action_type: str = "approve_comment") -> dict[str, Any]:
    """Construct inline keyboard with Approve and Reject buttons for a pending action.

    Args:
        item_id: Unique identifier for the pending action item.
        action_type: Either 'approve_comment' or 'approve_post'.

    Returns:
        Telegram inline_keyboard reply_markup dictionary.

    Raises:
        ValueError: If callback_data exceeds Telegram's 64-byte limit.
    """
    if action_type in ("approve_post", "post"):
        approve_code = ACTION_CODE_APPROVE_POST
        reject_code = ACTION_CODE_REJECT_POST
    else:
        approve_code = ACTION_CODE_APPROVE_COMMENT
        reject_code = ACTION_CODE_REJECT_COMMENT

    approve_cb = f"{approve_code}:{item_id.strip()}"
    reject_cb = f"{reject_code}:{item_id.strip()}"

    for cb in (approve_cb, reject_cb):
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
            ]
        ]
    }


def build_suggestion_message(item: PendingAction) -> str:
    """Format a readable HTML suggestion message for Telegram delivery.

    Args:
        item: PendingAction containing context, author, draft, and confidence.

    Returns:
        HTML formatted message string.
    """
    is_post = item.action_type in ("approve_post", "post")
    action_label = "📝 Original Post" if is_post else "💬 Feed Comment"

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

    if item.author_name:
        lines.append(f"<b>Author:</b> {html.escape(item.author_name)}")

    if item.post_url:
        lines.append(
            f'<b>Post URL:</b> <a href="{html.escape(item.post_url)}">View on LinkedIn</a>'
        )

    if item.post_excerpt and not is_post:
        lines.append(
            f"<b>Post Excerpt:</b>\n<blockquote>{html.escape(item.post_excerpt)}</blockquote>"
        )

    lines.append(
        f"<b>Drafted Content:</b>\n<blockquote>{html.escape(item.draft_text)}</blockquote>"
    )

    confidence_pct = int(item.confidence * 100)
    lines.append(f"<b>Confidence:</b> {confidence_pct}%")

    if item.reasoning:
        lines.append(f"<b>Reasoning:</b> {html.escape(item.reasoning)}")

    lines.append(f"<i>ID: {html.escape(item.item_id)}</i>")

    return "\n\n".join(lines)


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
        item_type = "Post" if item.action_type in ("approve_post", "post") else "Comment"
        lines.append(f"<b>Item:</b> {html.escape(item.item_id)} ({item_type})")
        if item.draft_text:
            lines.append(
                f"<b>Draft:</b> <blockquote>{html.escape(item.draft_text[:200])}</blockquote>"
            )

    if error:
        lines.append(f"<b>Error Details:</b>\n<code>{html.escape(error)}</code>")

    return "\n\n".join(lines)
