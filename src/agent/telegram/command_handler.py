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
from pathlib import Path
from typing import Any

from agent.config import Settings
from agent.safety.circuit_breaker import is_halted
from agent.state.base import BaseStateStore
from agent.telegram.client import TelegramClient

logger = logging.getLogger(__name__)


class CommandHandler:
    """Operator Command and Control (C2) router for Telegram bot interactions."""

    def __init__(
        self,
        settings: Settings,
        state_store: BaseStateStore,
        telegram: TelegramClient,
        repo_root: Path | None = None,
    ) -> None:
        """Initialize operator command router.

        Args:
            settings: Runtime application configuration.
            state_store: Durable state store instance.
            telegram: Telegram client for message transmission.
            repo_root: Optional repository root path override.
        """
        self.settings = settings
        self.state_store = state_store
        self.telegram = telegram
        self.repo_root = (
            Path(repo_root).resolve()
            if repo_root
            else getattr(state_store, "repo_root", Path.cwd())
        )

    async def handle_message(self, message: dict[str, Any]) -> bool:
        """Process an incoming Telegram message for operator commands.

        Args:
            message: Raw Telegram message dictionary from getUpdates or webhook.

        Returns:
            bool: True if the message contained a handled operator command, False otherwise.
        """
        sender_id = message.get("from", {}).get("id")
        chat_id = message.get("chat", {}).get("id")
        message_id = message.get("message_id")
        raw_text = (message.get("text") or "").strip()

        if not raw_text.startswith("/"):
            return False

        return await self.handle_command(
            text=raw_text,
            chat_id=chat_id,
            sender_id=sender_id,
            message_id=message_id,
        )

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
