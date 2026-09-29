"""Telegram operator Command & Control (C2) handler.

Architecture Invariants:
- Human approval invariant: commands inspect or configure agent operation, never trigger writes.
- Strict authorization: only messages from TELEGRAM_AUTHORIZED_CHAT_ID are processed; unauthorized
  requests produce zero state mutations and zero response.
- Safety & Circuit Breaker: provides operational transparency and safe breaker reset controls.
- Deterministic formatting: outputs clean, parse_mode="HTML" compatible reports.
"""

from __future__ import annotations

import html
import logging
import re
from pathlib import Path
from typing import Any

from agent.config import Settings
from agent.models.schemas import (
    CallbackDataPayload,
    EngagementStyle,
    PendingAction,
)
from agent.safety.circuit_breaker import is_halted
from agent.state.base import BaseStateStore
from agent.telegram.client import TelegramClient
from agent.telegram.keyboards import (
    build_suggestion_keyboard,
    format_suggestion_card,
)

logger = logging.getLogger(__name__)

# Regex pattern for extracting item ID from Telegram message text (e.g. 'ID: item_12345')
ITEM_ID_REGEX = re.compile(r"ID:\s*([a-zA-Z0-9_\-]+)", re.IGNORECASE)

# Length constraints
MAX_COMMENT_DRAFT_LENGTH = 600
MAX_POST_DRAFT_LENGTH = 1200


class CommandHandler:
    """Operator Command and Control (C2) router for Telegram bot interactions."""

    def __init__(
        self,
        settings: Settings,
        state_store: BaseStateStore,
        telegram: TelegramClient,
        repo_root: Path | None = None,
        llm_service: Any | None = None,
    ) -> None:
        """Initialize operator command router.

        Args:
            settings: Runtime application configuration.
            state_store: Durable state store instance.
            telegram: Telegram client for message transmission.
            repo_root: Optional repository root path override.
            llm_service: Optional LLM service for draft regeneration.
        """
        self.settings = settings
        self.state_store = state_store
        self.telegram = telegram
        self.repo_root = (
            Path(repo_root).resolve()
            if repo_root
            else getattr(state_store, "repo_root", Path.cwd())
        )
        self.llm_service = llm_service

    async def handle_message(self, message: dict[str, Any]) -> bool:
        """Process an incoming Telegram message for operator commands or draft edits.

        Args:
            message: Raw Telegram message dictionary from getUpdates or webhook.

        Returns:
            bool: True if the message was handled, False otherwise.
        """
        sender_id = message.get("from", {}).get("id")
        chat_id = message.get("chat", {}).get("id")
        message_id = message.get("message_id")
        raw_text = (message.get("text") or "").strip()

        effective_sender = sender_id if sender_id is not None else chat_id
        if not TelegramClient.is_authorized(effective_sender, self.settings):
            logger.warning(
                "Unauthorized operator message attempt from sender %s. Dropping.",
                effective_sender,
            )
            return False

        if raw_text.startswith("/"):
            return await self.handle_command(
                text=raw_text,
                chat_id=chat_id,
                sender_id=sender_id,
                message_id=message_id,
            )

        if message.get("reply_to_message"):
            return await self.handle_reply_edit(message)

        return False

    async def handle_command(
        self,
        text: str,
        chat_id: int | None,
        sender_id: int | None = None,
        message_id: int | None = None,
    ) -> bool:
        """Route and execute an operator command string.

        Args:
            text: Raw command text (e.g. "/status", "/pause").
            chat_id: Telegram chat ID to reply to.
            sender_id: Telegram user ID sending the command.
            message_id: Optional Telegram message ID to thread the reply.

        Returns:
            bool: True if command was executed, False if unauthorized or dropped.
        """
        effective_sender = sender_id if sender_id is not None else chat_id
        if not TelegramClient.is_authorized(effective_sender, self.settings):
            logger.warning(
                "Unauthorized operator command attempt from sender %s. Dropping.",
                effective_sender,
            )
            return False

        if chat_id is None:
            logger.warning("Cannot route command without valid chat_id.")
            return False

        parts = text.strip().split()
        if not parts:
            return False

        cmd_token = parts[0].lower().lstrip("/")
        command_name = cmd_token.split("@")[0]

        if command_name == "status":
            await self.handle_status(chat_id=chat_id, message_id=message_id)
            return True
        elif command_name == "stats":
            await self.handle_stats(chat_id=chat_id, message_id=message_id)
            return True
        elif command_name == "pending":
            await self.handle_pending(chat_id=chat_id, message_id=message_id)
            return True
        elif command_name == "pause":
            await self.handle_pause(chat_id=chat_id, message_id=message_id)
            return True
        elif command_name == "resume":
            await self.handle_resume(chat_id=chat_id, message_id=message_id)
            return True
        elif command_name == "clear_incident":
            await self.handle_clear_incident(chat_id=chat_id, message_id=message_id)
            return True
        elif command_name in ("help", "start"):
            await self.handle_help(chat_id=chat_id, message_id=message_id)
            return True
        else:
            await self.handle_unknown(chat_id=chat_id, command=command_name, message_id=message_id)
            return True

    async def handle_status(self, chat_id: int, message_id: int | None = None) -> str:
        """Handle /status command: operational state, breaker, daily counters, and pending count.

        Args:
            chat_id: Target chat ID.
            message_id: Optional reply-to message ID.

        Returns:
            str: The rendered HTML status message sent to Telegram.
        """
        halted, halt_reason = is_halted(self.repo_root, self.settings)
        incident = self.state_store.read_incident()

        if incident is not None:
            sys_status = "🚨 <b>Halted (Circuit Breaker Tripped)</b>"
            reason_esc = html.escape(str(incident.get("reason", "Incident detected")), quote=True)
            tripped_at = str(incident.get("tripped_at", incident.get("created_at", "Unknown")))
            cb_status = (
                f"🔴 <b>Tripped</b>\n"
                f"  • <i>Reason:</i> {reason_esc}\n"
                f"  • <i>Tripped At:</i> <code>{html.escape(tripped_at, quote=True)}</code>"
            )
        elif halted or self.settings.agent_paused or self.state_store.is_paused():
            sys_status = "⏸️ <b>Paused</b>"
            cb_status = "🟢 <b>Normal</b> (No active incident)"
        else:
            sys_status = "🟢 <b>Operational</b>"
            cb_status = "🟢 <b>Normal</b> (No active incident)"

        counters = self.state_store.load_daily_counters()
        pending_items = self.state_store.list_pending()
        pending_count = len(pending_items)

        focus_areas_str = (
            ", ".join(self.settings.user_focus_areas)
            if self.settings.user_focus_areas
            else "General"
        )
        focus_areas_esc = html.escape(focus_areas_str, quote=True)

        report = (
            "🎛️ <b>Agent Status Report</b>\n\n"
            f"• <b>System State:</b> {sys_status}\n"
            f"• <b>Circuit Breaker:</b> {cb_status}\n"
            f"• <b>Pending Approvals:</b> <b>{pending_count}</b> action(s) awaiting review\n\n"
            f"📊 <b>Daily Counters ({counters.date})</b>\n"
            f"• <b>Comments Executed:</b> {counters.comments_executed} / {self.settings.max_comments_per_day}\n"
            f"• <b>Posts Executed:</b> {counters.posts_executed} / {self.settings.max_posts_per_day}\n"
            f"• <b>Suggestions Sent:</b> {counters.suggestions_sent} (run limit: {self.settings.max_suggestions_per_run})\n\n"
            "⚙️ <b>Configuration</b>\n"
            f"• <b>Dry Run:</b> {self.settings.dry_run}\n"
            f"• <b>Focus Areas:</b> {focus_areas_esc}"
        )

        await self.telegram.send_message(
            chat_id=chat_id,
            text=report,
            reply_to_message_id=message_id,
        )
        return report

    async def handle_stats(self, chat_id: int, message_id: int | None = None) -> str:
        """Handle /stats command: trailing metrics from state/history.jsonl.

        Args:
            chat_id: Target chat ID.
            message_id: Optional reply-to message ID.

        Returns:
            str: The rendered HTML stats message sent to Telegram.
        """
        history_entries = self.state_store.read_history()
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
            if "comment" in e.action_type.lower()
            and e.final_status in ("approved", "executed_success")
        )
        posts_published = sum(
            1
            for e in history_entries
            if "post" in e.action_type.lower()
            and e.final_status in ("approved", "executed_success")
        )

        counters = self.state_store.load_daily_counters()

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

        await self.telegram.send_message(
            chat_id=chat_id,
            text=report,
            reply_to_message_id=message_id,
        )
        return report

    async def handle_pending(self, chat_id: int, message_id: int | None = None) -> str:
        """Handle /pending command: lists all pending actions with target links and status.

        Args:
            chat_id: Target chat ID.
            message_id: Optional reply-to message ID.

        Returns:
            str: The rendered HTML pending list message sent to Telegram.
        """
        pending_items = self.state_store.list_pending()
        if not pending_items:
            empty_msg = "📋 <b>Pending Actions</b>\n\nNo actions currently awaiting approval."
            await self.telegram.send_message(
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
        await self.telegram.send_message(
            chat_id=chat_id,
            text=report,
            reply_to_message_id=message_id,
        )
        return report

    async def handle_pause(self, chat_id: int, message_id: int | None = None) -> str:
        """Handle /pause command: remotely suspend automated agent operations.

        Args:
            chat_id: Target chat ID.
            message_id: Optional reply-to message ID.

        Returns:
            str: The confirmation message sent to Telegram.
        """
        self.settings.agent_paused = True
        self.state_store.set_paused(True)

        msg = (
            "⏸️ <b>Agent Paused</b>\n\n"
            "All automated scouting, triage, and execution workflows are now suspended.\n"
            "Use /resume to restart operations."
        )
        await self.telegram.send_message(
            chat_id=chat_id,
            text=msg,
            reply_to_message_id=message_id,
        )
        return msg

    async def handle_resume(self, chat_id: int, message_id: int | None = None) -> str:
        """Handle /resume command: remotely activate automated agent operations.

        Args:
            chat_id: Target chat ID.
            message_id: Optional reply-to message ID.

        Returns:
            str: The confirmation message sent to Telegram.
        """
        self.settings.agent_paused = False
        self.state_store.set_paused(False)

        msg = (
            "▶️ <b>Agent Resumed</b>\n\n"
            "Automated workflows are now active and ready to scout and execute according to schedule."
        )
        await self.telegram.send_message(
            chat_id=chat_id,
            text=msg,
            reply_to_message_id=message_id,
        )
        return msg

    async def handle_clear_incident(self, chat_id: int, message_id: int | None = None) -> str:
        """Handle /clear_incident command: safely resets the circuit breaker.

        Args:
            chat_id: Target chat ID.
            message_id: Optional reply-to message ID.

        Returns:
            str: The result message sent to Telegram.
        """
        cleared = self.state_store.clear_incident()
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

        await self.telegram.send_message(
            chat_id=chat_id,
            text=msg,
            reply_to_message_id=message_id,
        )
        return msg

    async def handle_help(self, chat_id: int, message_id: int | None = None) -> str:
        """Handle /help or /start command: display operator command manual.

        Args:
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
            "• /help — Show this command reference"
        )
        await self.telegram.send_message(
            chat_id=chat_id,
            text=msg,
            reply_to_message_id=message_id,
        )
        return msg

    async def handle_unknown(
        self, chat_id: int, command: str, message_id: int | None = None
    ) -> str:
        """Handle unrecognized commands with a helpful notice.

        Args:
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
        await self.telegram.send_message(
            chat_id=chat_id,
            text=msg,
            reply_to_message_id=message_id,
        )
        return msg

    async def handle_reply_edit(self, message: dict[str, Any]) -> bool:
        """Handle inline draft editing when operator replies to a suggestion message.

        Args:
            message: Raw Telegram message dictionary containing reply_to_message.

        Returns:
            bool: True if draft was edited or handled with a reply, False if dropped.
        """
        sender_id = message.get("from", {}).get("id")
        chat_id = message.get("chat", {}).get("id")
        message_id = message.get("message_id")
        raw_text = (message.get("text") or "").strip()
        reply_to = message.get("reply_to_message") or {}

        effective_sender = sender_id if sender_id is not None else chat_id
        if not TelegramClient.is_authorized(effective_sender, self.settings):
            logger.warning(
                "Unauthorized reply edit attempt from sender %s. Dropping.",
                effective_sender,
            )
            return False

        reply_msg_id = reply_to.get("message_id")
        pending: PendingAction | None = None
        target_message_id: int | None = None

        if isinstance(reply_msg_id, int):
            pending = self.state_store.find_pending_by_message_id(reply_msg_id)
            if pending is not None:
                target_message_id = reply_msg_id

        if pending is None:
            reply_text = reply_to.get("text", "")
            match = ITEM_ID_REGEX.search(reply_text)
            if match:
                matched_id = match.group(1)
                pending = self.state_store.read_pending(matched_id)
                if pending is not None:
                    target_message_id = (
                        reply_msg_id if isinstance(reply_msg_id, int) else pending.telegram_message_id
                    )

        if pending is None:
            if chat_id is not None:
                await self.telegram.send_message(
                    chat_id=chat_id,
                    text="⚠️ The target suggestion is no longer pending or has already been processed.",
                    reply_to_message_id=message_id,
                )
            return False

        if not raw_text:
            if chat_id is not None:
                await self.telegram.send_message(
                    chat_id=chat_id,
                    text="❌ Draft text cannot be empty. Please reply with the revised text.",
                    reply_to_message_id=message_id,
                )
            return False

        is_post = pending.action_type in ("approve_post", "post")
        max_len = MAX_POST_DRAFT_LENGTH if is_post else MAX_COMMENT_DRAFT_LENGTH
        if len(raw_text) > max_len:
            if chat_id is not None:
                await self.telegram.send_message(
                    chat_id=chat_id,
                    text=(
                        f"❌ Draft exceeds maximum length of {max_len} characters "
                        f"({len(raw_text)}/{max_len}). Please shorten your draft."
                    ),
                    reply_to_message_id=message_id,
                )
            return False

        updated_item = self.state_store.update_pending_draft(pending.item_id, raw_text)
        if updated_item is None:
            if chat_id is not None:
                await self.telegram.send_message(
                    chat_id=chat_id,
                    text="⚠️ Failed to update draft: suggestion is no longer pending.",
                    reply_to_message_id=message_id,
                )
            return False

        if target_message_id is None:
            target_message_id = pending.telegram_message_id

        if chat_id is not None and target_message_id is not None:
            rendered_card = format_suggestion_card(updated_item)
            refreshed_keyboard = build_suggestion_keyboard(
                updated_item.item_id, updated_item.action_type
            )
            try:
                await self.telegram.edit_message_text(
                    chat_id=chat_id,
                    message_id=target_message_id,
                    text=rendered_card,
                    reply_markup=refreshed_keyboard,
                )
            except Exception as edit_err:
                logger.warning(
                    "Failed to edit Telegram suggestion message %s: %s",
                    target_message_id,
                    edit_err,
                )

        if chat_id is not None:
            await self.telegram.send_message(
                chat_id=chat_id,
                text="✏️ Draft updated successfully!",
                reply_to_message_id=message_id,
            )

        return True

    async def handle_callback_query(self, callback_query: dict[str, Any]) -> bool:
        """Process an incoming Telegram callback query (e.g. edit or regenerate).

        Args:
            callback_query: Raw Telegram callback_query dictionary.

        Returns:
            bool: True if callback query was handled, False otherwise.
        """
        callback_query_id = callback_query.get("id", "")
        sender_id = callback_query.get("from", {}).get("id")
        data = callback_query.get("data", "")
        msg = callback_query.get("message", {})
        chat_id = msg.get("chat", {}).get("id") or sender_id
        message_id = msg.get("message_id")

        if not TelegramClient.is_authorized(sender_id, self.settings):
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
            return await self.handle_edit_callback(
                item_id=payload.item_id,
                callback_query_id=callback_query_id,
                chat_id=chat_id,
                message_id=message_id,
            )
        elif payload.is_regenerate:
            return await self.handle_regenerate_callback(
                item_id=payload.item_id,
                callback_query_id=callback_query_id,
                chat_id=chat_id,
                message_id=message_id,
            )

        return False

    async def handle_edit_callback(
        self,
        item_id: str,
        callback_query_id: str | None = None,
        chat_id: int | None = None,
        message_id: int | None = None,
    ) -> bool:
        """Handle edit:<item_id> callback query by prompting the operator to reply.

        Args:
            item_id: ID of the pending item to edit.
            callback_query_id: Telegram callback query ID to answer.
            chat_id: Optional Telegram chat ID.
            message_id: Optional message ID of the suggestion.

        Returns:
            bool: True if handled, False if item not found or dropped.
        """
        pending = self.state_store.read_pending(item_id)
        if pending is None:
            if callback_query_id:
                await self.telegram.answer_callback_query(
                    callback_query_id,
                    text="⚠️ Suggestion is no longer pending or has already been processed.",
                    show_alert=True,
                )
            return False

        if callback_query_id:
            await self.telegram.answer_callback_query(
                callback_query_id,
                text="✏️ Reply to this suggestion with your revised draft text.",
                show_alert=False,
            )
        return True

    async def handle_regenerate_callback(
        self,
        item_id: str,
        callback_query_id: str | None = None,
        chat_id: int | None = None,
        message_id: int | None = None,
    ) -> bool:
        """Handle reg:<item_id> callback query by drafting alternative or sending tone guidance.

        Args:
            item_id: ID of the pending item to regenerate.
            callback_query_id: Telegram callback query ID to answer.
            chat_id: Optional Telegram chat ID.
            message_id: Optional message ID of the suggestion.

        Returns:
            bool: True if handled, False if item not found or dropped.
        """
        pending = self.state_store.read_pending(item_id)
        if pending is None:
            if callback_query_id:
                await self.telegram.answer_callback_query(
                    callback_query_id,
                    text="⚠️ Suggestion is no longer pending or has already been processed.",
                    show_alert=True,
                )
            return False

        if (
            self.llm_service is not None
            and hasattr(self.llm_service, "draft_comment")
            and pending.post_excerpt
        ):
            try:
                current_style = (
                    pending.engagement_style.value
                    if hasattr(pending.engagement_style, "value")
                    else str(pending.engagement_style or "")
                )
                alt_style = (
                    EngagementStyle.CONTRARIAN_PERSPECTIVE
                    if current_style == EngagementStyle.TECHNICAL_DEEP_DIVE.value
                    else EngagementStyle.TECHNICAL_DEEP_DIVE
                )
                draft_res = await self.llm_service.draft_comment(
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
                    updated = self.state_store.update_pending_draft(
                        pending.item_id, draft_text
                    )
                    if updated is not None:
                        updated.engagement_style = alt_style
                        self.state_store.write_pending(updated)
                        target_msg_id = message_id or updated.telegram_message_id
                        if chat_id is not None and target_msg_id is not None:
                            card_text = format_suggestion_card(updated)
                            kb = build_suggestion_keyboard(updated.item_id, updated.action_type)
                            await self.telegram.edit_message_text(
                                chat_id=chat_id,
                                message_id=target_msg_id,
                                text=card_text,
                                reply_markup=kb,
                            )
                        if callback_query_id:
                            await self.telegram.answer_callback_query(
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
            await self.telegram.answer_callback_query(
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
            await self.telegram.send_message(
                chat_id=chat_id,
                text=guidance_msg,
                reply_to_message_id=message_id,
            )

        return True
