"""Asynchronous Telegram Bot API client for human-in-the-loop approvals.

Architecture Invariants:
- High-risk operations require explicit human authorization via Telegram.
- Outbound approval requests attach inline keyboard with compact callback_data.
- Outcome transitions strip the inline keyboard as a UI-level idempotency guard.
- Strict authorization check validates sender against TELEGRAM_AUTHORIZED_CHAT_ID.
"""

from __future__ import annotations

import logging
from typing import Any

import httpx
from pydantic import SecretStr

from agent.config import Settings
from agent.errors import TelegramAPIError
from agent.models import PendingAction
from agent.telegram.keyboards import (
    build_suggestion_keyboard,
    build_suggestion_message,
    format_suggestion_card,
)

logger = logging.getLogger(__name__)


class TelegramClient:
    """Asynchronous HTTP client for Telegram Bot API interactions."""

    def __init__(
        self,
        settings: Settings,
        http_client: httpx.AsyncClient | None = None,
    ) -> None:
        self._settings = settings
        self._custom_client = http_client is not None
        self._http_client = http_client or httpx.AsyncClient(timeout=15.0)

        token_str = (
            settings.telegram_bot_token.get_secret_value()
            if isinstance(settings.telegram_bot_token, SecretStr)
            else str(settings.telegram_bot_token)
        )
        self._base_url = f"https://api.telegram.org/bot{token_str}"

    async def __aenter__(self) -> TelegramClient:
        return self

    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        await self.aclose()

    async def aclose(self) -> None:
        """Close the underlying HTTP client if internally managed."""
        if not self._custom_client and not self._http_client.is_closed:
            await self._http_client.aclose()

    @staticmethod
    def is_authorized(chat_id: int | None, settings: Settings) -> bool:
        """Validate whether a chat/user ID matches the authorized Telegram identity.

        Args:
            chat_id: Telegram chat or user ID from callback/message.
            settings: Runtime configuration containing TELEGRAM_AUTHORIZED_CHAT_ID.

        Returns:
            True if authorized, False otherwise.
        """
        if chat_id is None or chat_id <= 0:
            return False
        return chat_id == settings.telegram_authorized_chat_id

    @staticmethod
    def format_suggestion_card(item: PendingAction) -> str:
        """Format an action suggestion card with rich HTML styling."""
        return format_suggestion_card(item)

    async def send_photo(
        self,
        chat_id: int,
        photo_url: str,
        caption: str = "",
        reply_markup: dict[str, Any] | None = None,
    ) -> int:
        """Send a photo with caption and optional reply markup to Telegram.

        Args:
            chat_id: Target Telegram chat ID.
            photo_url: HTTPS URL or file_id of the photo.
            caption: HTML formatted caption (max 1024 characters).
            reply_markup: Optional inline or reply keyboard markup.

        Returns:
            Telegram message_id of the sent photo message.

        Raises:
            TelegramAPIError: If the API call fails or returns an error.
        """
        payload: dict[str, Any] = {
            "chat_id": chat_id,
            "photo": photo_url,
            "caption": caption[:1024],
            "parse_mode": "HTML",
        }
        if reply_markup is not None:
            payload["reply_markup"] = reply_markup

        data = await self._post("sendPhoto", payload)
        result = data.get("result")
        message_id = result.get("message_id") if isinstance(result, dict) else None
        if not message_id or not isinstance(message_id, int):
            raise TelegramAPIError(
                f"Telegram sendPhoto response missing integer message_id: {data}"
            )
        return message_id

    async def send_suggestion(self, item: PendingAction) -> int:
        """Send an action approval suggestion to the authorized Telegram chat.

        If the item includes a post image and the formatted card fits Telegram's
        1024-character caption limit, delivers as a photo preview with automatic
        HTML fallback.

        Args:
            item: PendingAction record with context, draft text, and item ID.

        Returns:
            Telegram message_id of the sent suggestion message.

        Raises:
            TelegramAPIError: If the API call fails or returns an error.
        """
        message_text = build_suggestion_message(item)
        keyboard = build_suggestion_keyboard(item.item_id, item.action_type)

        image_url = getattr(item, "post_image_url", None)
        if not image_url and item.media_attachments:
            for m in item.media_attachments:
                if m.media_type == "image" and m.file_url and m.file_url.startswith("http"):
                    image_url = m.file_url
                    break

        if image_url and image_url.startswith("http") and len(message_text) <= 1024:
            try:
                msg_id = await self.send_photo(
                    chat_id=self._settings.telegram_authorized_chat_id,
                    photo_url=image_url,
                    caption=message_text,
                    reply_markup=keyboard,
                )
                logger.info(
                    f"Sent Telegram photo suggestion for item '{item.item_id}' (message_id={msg_id})"
                )
                return msg_id
            except Exception as err:
                logger.warning(
                    f"sendPhoto failed for item '{item.item_id}', falling back to sendMessage: {err}"
                )

        payload: dict[str, Any] = {
            "chat_id": self._settings.telegram_authorized_chat_id,
            "text": message_text,
            "parse_mode": "HTML",
            "link_preview_options": {"is_disabled": True},
            "reply_markup": keyboard,
        }

        data = await self._post("sendMessage", payload)
        result = data.get("result")
        message_id = result.get("message_id") if isinstance(result, dict) else None
        if not message_id or not isinstance(message_id, int):
            raise TelegramAPIError(
                f"Telegram sendMessage response missing integer message_id: {data}"
            )

        logger.info(f"Sent Telegram suggestion for item '{item.item_id}' (message_id={message_id})")
        return message_id

    async def edit_to_outcome(
        self,
        chat_id: int,
        message_id: int,
        outcome_text: str,
    ) -> None:
        """Edit a suggestion message to terminal outcome and strip its inline keyboard.

        This removes the inline buttons to prevent duplicate operator clicks.

        Args:
            chat_id: Target Telegram chat ID.
            message_id: ID of the message to edit.
            outcome_text: Formatted terminal outcome text.

        Raises:
            TelegramAPIError: If editing fails (except for harmless 'message is not modified').
        """
        payload: dict[str, Any] = {
            "chat_id": chat_id,
            "message_id": message_id,
            "text": outcome_text,
            "parse_mode": "HTML",
            "link_preview_options": {"is_disabled": True},
            "reply_markup": {"inline_keyboard": []},
        }

        try:
            await self._post("editMessageText", payload)
            logger.info(f"Updated Telegram message {message_id} in chat {chat_id} to outcome.")
        except TelegramAPIError as e:
            err_msg = str(e).lower()
            if "message is not modified" in err_msg:
                logger.debug(
                    f"Telegram message {message_id} already contains outcome text. Ignoring."
                )
                return
            raise

    async def send_notification(self, text: str) -> int:
        """Send an operational or emergency alert message to the authorized chat.

        Args:
            text: Notification text (supports HTML formatting).

        Returns:
            Telegram message_id.

        Raises:
            TelegramAPIError: If delivery fails.
        """
        payload: dict[str, Any] = {
            "chat_id": self._settings.telegram_authorized_chat_id,
            "text": text,
            "parse_mode": "HTML",
            "link_preview_options": {"is_disabled": True},
        }

        data = await self._post("sendMessage", payload)
        result = data.get("result")
        message_id = result.get("message_id") if isinstance(result, dict) else None
        if not message_id or not isinstance(message_id, int):
            raise TelegramAPIError(f"Telegram sendMessage notification missing message_id: {data}")
        return message_id

    async def edit_message_text(
        self,
        chat_id: int,
        message_id: int,
        text: str,
        reply_markup: dict[str, Any] | None = None,
    ) -> None:
        """Edit message text and optionally update or refresh its inline keyboard.

        Args:
            chat_id: Target Telegram chat ID.
            message_id: ID of the message to edit.
            text: Updated message text (supports HTML formatting).
            reply_markup: Optional inline keyboard markup.

        Raises:
            TelegramAPIError: If editing fails (except for harmless 'message is not modified').
        """
        payload: dict[str, Any] = {
            "chat_id": chat_id,
            "message_id": message_id,
            "text": text,
            "parse_mode": "HTML",
            "link_preview_options": {"is_disabled": True},
        }
        if reply_markup is not None:
            payload["reply_markup"] = reply_markup

        try:
            await self._post("editMessageText", payload)
            logger.info(f"Edited Telegram message {message_id} in chat {chat_id}.")
        except TelegramAPIError as e:
            err_msg = str(e).lower()
            if "message is not modified" in err_msg:
                logger.debug(
                    f"Telegram message {message_id} was not modified. Treating as graceful no-op."
                )
                return
            raise

    async def edit_message_reply_markup(
        self,
        chat_id: int,
        message_id: int,
        reply_markup: dict[str, Any] | None = None,
    ) -> None:
        """Edit only the inline reply markup of an existing message.

        Args:
            chat_id: Target Telegram chat ID.
            message_id: ID of the message to edit.
            reply_markup: Optional inline keyboard markup.

        Raises:
            TelegramAPIError: If editing fails (except for harmless 'message is not modified').
        """
        payload: dict[str, Any] = {
            "chat_id": chat_id,
            "message_id": message_id,
        }
        if reply_markup is not None:
            payload["reply_markup"] = reply_markup
        else:
            payload["reply_markup"] = {"inline_keyboard": []}

        try:
            await self._post("editMessageReplyMarkup", payload)
            logger.info("Edited Telegram message %s reply markup in chat %s.", message_id, chat_id)
        except TelegramAPIError as e:
            err_msg = str(e).lower()
            if "message is not modified" in err_msg:
                logger.debug(
                    "Telegram message %s markup was not modified. Treating as graceful no-op.",
                    message_id,
                )
                return
            raise

    async def answer_callback_query(
        self,
        callback_query_id: str,
        text: str | None = None,
        show_alert: bool = False,
    ) -> None:
        """Acknowledge a Telegram callback query with optional notification or alert.

        Args:
            callback_query_id: Unique identifier for the query to be answered.
            text: Optional notification text to display to the user.
            show_alert: If True, show an alert instead of a toast notification.

        Raises:
            TelegramAPIError: If the API call fails.
        """
        payload: dict[str, Any] = {
            "callback_query_id": callback_query_id,
        }
        if text is not None:
            payload["text"] = text
        if show_alert:
            payload["show_alert"] = True

        await self._post("answerCallbackQuery", payload)
        logger.debug(f"Answered Telegram callback query {callback_query_id}")

    async def send_message(
        self,
        chat_id: int,
        text: str,
        reply_markup: dict[str, Any] | None = None,
        reply_to_message_id: int | None = None,
    ) -> int:
        """Send a formatted message to a Telegram chat with optional keyboard and reply threading.

        Args:
            chat_id: Target Telegram chat ID.
            text: Message text (supports HTML formatting).
            reply_markup: Optional reply markup (e.g. inline keyboard).
            reply_to_message_id: Optional message ID to reply to.

        Returns:
            Telegram message_id of the sent message.

        Raises:
            TelegramAPIError: If delivery fails.
        """
        payload: dict[str, Any] = {
            "chat_id": chat_id,
            "text": text,
            "parse_mode": "HTML",
            "link_preview_options": {"is_disabled": True},
        }
        if reply_markup is not None:
            payload["reply_markup"] = reply_markup
        if reply_to_message_id is not None:
            payload["reply_to_message_id"] = reply_to_message_id

        data = await self._post("sendMessage", payload)
        result = data.get("result")
        message_id = result.get("message_id") if isinstance(result, dict) else None
        if not message_id or not isinstance(message_id, int):
            raise TelegramAPIError(
                f"Telegram sendMessage response missing integer message_id: {data}"
            )
        return message_id

    async def set_my_commands(
        self,
        commands: list[dict[str, str]] | None = None,
    ) -> bool:
        """Register Telegram Bot command menu descriptions via setMyCommands.

        Args:
            commands: Optional list of command dicts with 'command' and 'description'.

        Returns:
            bool: True if registration was successful.

        Raises:
            TelegramAPIError: If the API call fails.
        """
        bot_commands = commands or [
            {"command": "status", "description": "Check system health, breaker, and daily counters"},
            {"command": "pending", "description": "List all actions awaiting operator approval"},
            {"command": "stats", "description": "Performance metrics, counters, and approval rate"},
            {"command": "pause", "description": "Suspend automated scouting and execution workflows"},
            {"command": "resume", "description": "Resume automated agent operations"},
            {"command": "clear_incident", "description": "Safely reset tripped circuit breaker"},
            {"command": "post", "description": "Draft an original LinkedIn post from a quick note"},
            {"command": "scout", "description": "Triage and draft a comment for a specific LinkedIn URL"},
            {"command": "help", "description": "View operator command manual and usage guide"},
        ]
        data = await self._post("setMyCommands", {"commands": bot_commands})
        return bool(data.get("ok", False))

    async def _post(self, method: str, payload: dict[str, Any]) -> dict[str, Any]:
        """Execute a POST request against the Telegram Bot API."""
        url = f"{self._base_url}/{method}"
        try:
            response = await self._http_client.post(url, json=payload)
        except Exception as net_err:
            raise TelegramAPIError(
                f"Telegram Bot API network request failed ({method}): {net_err}"
            ) from net_err

        try:
            data = response.json()
        except Exception:
            data = {"raw_body": response.text}

        if response.status_code >= 400 or not data.get("ok", False):
            description = data.get("description", response.text)
            status_code = response.status_code
            raise TelegramAPIError(
                f"Telegram API error {status_code} on {method}: {description}",
                details={"status_code": status_code, "response": data},
            )

        return data  # type: ignore[no-any-return]
