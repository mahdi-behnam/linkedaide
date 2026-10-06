"""Telegram operator Command & Control (C2) handler.

Architecture Invariants:
- Human approval invariant: commands inspect or configure agent operation, never trigger writes.
- Strict authorization: only messages from TELEGRAM_AUTHORIZED_CHAT_ID are processed; unauthorized
  requests produce zero state mutations and zero response.
- Safety & Circuit Breaker: provides operational transparency and safe breaker reset controls.
- Deterministic formatting: outputs clean, parse_mode="HTML" compatible reports.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from agent.config import Settings
from agent.state.base import BaseStateStore
from agent.telegram.callbacks import (
    execute_callback_query,
    execute_edit_callback,
    execute_regenerate_callback,
)
from agent.telegram.client import TelegramClient
from agent.telegram.commands import (
    execute_clear_incident_command,
    execute_help_command,
    execute_pause_command,
    execute_pending_command,
    execute_resume_command,
    execute_stats_command,
    execute_status_command,
    execute_unknown_command,
)
from agent.telegram.draft_editor import handle_draft_edit
from agent.telegram.reply_keyboards import DOCK_BUTTON_COMMAND_MAP

logger = logging.getLogger(__name__)


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

        if (
            raw_text.startswith("/")
            or raw_text in DOCK_BUTTON_COMMAND_MAP
            or raw_text.startswith("⏸️ Pause")
            or raw_text.startswith("▶️ Resume")
        ):
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

        stripped = text.strip()
        if stripped in DOCK_BUTTON_COMMAND_MAP:
            command_name = DOCK_BUTTON_COMMAND_MAP[stripped]
        elif stripped.startswith("⏸️ Pause"):
            command_name = "pause"
        elif stripped.startswith("▶️ Resume"):
            command_name = "resume"
        else:
            parts = stripped.split()
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
        """Handle /status command: operational state, breaker, daily counters, and pending count."""
        return await execute_status_command(
            settings=self.settings,
            state_store=self.state_store,
            telegram=self.telegram,
            repo_root=self.repo_root,
            chat_id=chat_id,
            message_id=message_id,
        )

    async def handle_stats(self, chat_id: int, message_id: int | None = None) -> str:
        """Handle /stats command: trailing metrics from state/history.jsonl."""
        return await execute_stats_command(
            state_store=self.state_store,
            telegram=self.telegram,
            chat_id=chat_id,
            message_id=message_id,
        )

    async def handle_pending(self, chat_id: int, message_id: int | None = None) -> str:
        """Handle /pending command: lists all pending actions with target links and status."""
        return await execute_pending_command(
            state_store=self.state_store,
            telegram=self.telegram,
            chat_id=chat_id,
            message_id=message_id,
        )

    async def handle_pause(self, chat_id: int, message_id: int | None = None) -> str:
        """Handle /pause command: remotely suspend automated agent operations."""
        return await execute_pause_command(
            settings=self.settings,
            state_store=self.state_store,
            telegram=self.telegram,
            chat_id=chat_id,
            message_id=message_id,
        )

    async def handle_resume(self, chat_id: int, message_id: int | None = None) -> str:
        """Handle /resume command: remotely activate automated agent operations."""
        return await execute_resume_command(
            settings=self.settings,
            state_store=self.state_store,
            telegram=self.telegram,
            chat_id=chat_id,
            message_id=message_id,
        )

    async def handle_clear_incident(self, chat_id: int, message_id: int | None = None) -> str:
        """Handle /clear_incident command: safely resets the circuit breaker."""
        return await execute_clear_incident_command(
            state_store=self.state_store,
            telegram=self.telegram,
            chat_id=chat_id,
            message_id=message_id,
        )

    async def handle_help(self, chat_id: int, message_id: int | None = None) -> str:
        """Handle /help or /start command: display operator command manual."""
        return await execute_help_command(
            telegram=self.telegram,
            chat_id=chat_id,
            message_id=message_id,
        )

    async def handle_unknown(
        self, chat_id: int, command: str, message_id: int | None = None
    ) -> str:
        """Handle unrecognized commands with a helpful notice."""
        return await execute_unknown_command(
            telegram=self.telegram,
            chat_id=chat_id,
            command=command,
            message_id=message_id,
        )

    async def handle_reply_edit(self, message: dict[str, Any]) -> bool:
        """Handle inline draft editing when operator replies to a suggestion message."""
        return await handle_draft_edit(
            message=message,
            settings=self.settings,
            state_store=self.state_store,
            telegram=self.telegram,
        )

    async def handle_callback_query(self, callback_query: dict[str, Any]) -> bool:
        """Process an incoming Telegram callback query (e.g. edit or regenerate).

        Args:
            callback_query: Raw Telegram callback_query dictionary.

        Returns:
            bool: True if callback query was handled, False otherwise.
        """
        return await execute_callback_query(
            settings=self.settings,
            state_store=self.state_store,
            telegram=self.telegram,
            callback_query=callback_query,
            llm_service=self.llm_service,
        )

    async def handle_edit_callback(
        self,
        item_id: str,
        callback_query_id: str | None = None,
        chat_id: int | None = None,
        message_id: int | None = None,
    ) -> bool:
        """Handle edit:<item_id> callback query by prompting the operator to reply."""
        return await execute_edit_callback(
            state_store=self.state_store,
            telegram=self.telegram,
            item_id=item_id,
            callback_query_id=callback_query_id,
            chat_id=chat_id,
            message_id=message_id,
        )

    async def handle_regenerate_callback(
        self,
        item_id: str,
        callback_query_id: str | None = None,
        chat_id: int | None = None,
        message_id: int | None = None,
    ) -> bool:
        """Handle reg:<item_id> callback query by drafting alternative or sending tone guidance."""
        return await execute_regenerate_callback(
            state_store=self.state_store,
            telegram=self.telegram,
            item_id=item_id,
            callback_query_id=callback_query_id,
            chat_id=chat_id,
            message_id=message_id,
            llm_service=self.llm_service,
        )
