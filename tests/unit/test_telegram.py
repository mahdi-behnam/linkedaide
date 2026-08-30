"""Unit tests for Telegram integration (client, keyboards, formatters, and authorization)."""

from datetime import UTC, datetime
from typing import Any

import httpx
import pytest

from agent.config import Settings
from agent.errors import TelegramAPIError
from agent.models.schemas import PendingAction
from agent.telegram.client import TelegramClient
from agent.telegram.keyboards import (
    build_outcome_message,
    build_suggestion_keyboard,
    build_suggestion_message,
)


@pytest.fixture
def mock_settings() -> Settings:
    """Create test settings fixture."""
    return Settings(
        nvidia_nim_api_key="nvapi-mock-key",
        telegram_bot_token="123456789:ABCdefGhIJKlmNoPQRsTUVwxyZ",
        telegram_authorized_chat_id=987654321,
    )


@pytest.fixture
def sample_pending_action() -> PendingAction:
    """Create sample PendingAction fixture."""
    return PendingAction(
        item_id="item_test_12345",
        action_type="approve_comment",
        post_urn="urn:li:activity:123456789",
        post_url="https://linkedin.com/feed/update/urn:li:activity:123456789",
        author_name="Jane Doe <Tech Lead & Architect>",
        post_excerpt="Discussing lock-free data structures in high-throughput engines.",
        draft_text="Lock-free approaches offer huge throughput gains, but ABA problems require hazard pointers.",
        confidence=0.95,
        reasoning="Directly matches systems architecture focus area.",
        created_at=datetime(2026, 8, 30, 12, 0, 0, tzinfo=UTC),
    )


class TestAuthorization:
    """Test suite for Telegram chat_id authorization guard."""

    def test_is_authorized_matching(self, mock_settings: Settings) -> None:
        assert TelegramClient.is_authorized(987654321, mock_settings) is True

    def test_is_authorized_mismatched(self, mock_settings: Settings) -> None:
        assert TelegramClient.is_authorized(111222333, mock_settings) is False

    def test_is_authorized_zero_and_negative(self, mock_settings: Settings) -> None:
        assert TelegramClient.is_authorized(0, mock_settings) is False
        assert TelegramClient.is_authorized(-123, mock_settings) is False

    def test_is_authorized_none(self, mock_settings: Settings) -> None:
        assert TelegramClient.is_authorized(None, mock_settings) is False


class TestKeyboardsAndMessages:
    """Test suite for keyboard construction and message formatting."""

    def test_build_suggestion_keyboard_comment(self) -> None:
        keyboard = build_suggestion_keyboard("item_abc", "approve_comment")
        buttons = keyboard["inline_keyboard"][0]
        assert len(buttons) == 2
        assert buttons[0]["text"] == "✅ Approve"
        assert buttons[0]["callback_data"] == "ac:item_abc"
        assert buttons[1]["text"] == "❌ Reject"
        assert buttons[1]["callback_data"] == "rc:item_abc"

    def test_build_suggestion_keyboard_post(self) -> None:
        keyboard = build_suggestion_keyboard("post_123", "approve_post")
        buttons = keyboard["inline_keyboard"][0]
        assert buttons[0]["callback_data"] == "ap:post_123"
        assert buttons[1]["callback_data"] == "rp:post_123"

    def test_build_suggestion_keyboard_exceeds_64_bytes(self) -> None:
        long_id = "x" * 63
        with pytest.raises(ValueError, match="exceeds 64 bytes limit"):
            build_suggestion_keyboard(long_id)

    def test_build_suggestion_message_escaping(self, sample_pending_action: PendingAction) -> None:
        msg = build_suggestion_message(sample_pending_action)
        # HTML special chars must be escaped
        assert "&lt;Tech Lead &amp; Architect&gt;" in msg
        assert "💬 Feed Comment" in msg
        assert "95%" in msg
        assert "View on LinkedIn" in msg
        assert "item_test_12345" in msg

    def test_build_suggestion_message_post_type(self) -> None:
        post_item = PendingAction(
            item_id="post_999",
            action_type="approve_post",
            draft_text="Original post thoughts on distributed consensus.",
            confidence=0.88,
            reasoning="Thought leadership post.",
        )
        msg = build_suggestion_message(post_item)
        assert "📝 Original Post" in msg
        assert "post_999" in msg

    def test_build_outcome_messages(self, sample_pending_action: PendingAction) -> None:
        # Success
        success_msg = build_outcome_message(sample_pending_action, "executed_success")
        assert "✅ Executed Successfully" in success_msg
        assert "item_test_12345" in success_msg

        # Rejected
        rejected_msg = build_outcome_message(sample_pending_action, "rejected")
        assert "❌ Suggestion Rejected" in rejected_msg

        # Expired
        expired_msg = build_outcome_message(sample_pending_action, "expired")
        assert "⏱️ Suggestion Expired" in expired_msg

        # Halted
        halted_msg = build_outcome_message(
            sample_pending_action, "halted", error="Bot challenge detected"
        )
        assert "🛑 System Halted" in halted_msg
        assert "Bot challenge detected" in halted_msg

        # Failed
        failed_msg = build_outcome_message(
            sample_pending_action, "executed_failed", error="Selector not found"
        )
        assert "⚠️ Execution Failed" in failed_msg
        assert "Selector not found" in failed_msg


class TestTelegramClient:
    """Test suite for TelegramClient HTTP operations and error translation."""

    @pytest.mark.asyncio
    async def test_send_suggestion_success(
        self, mock_settings: Settings, sample_pending_action: PendingAction
    ) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            assert request.url.path.endswith("/sendMessage")
            return httpx.Response(200, json={"ok": True, "result": {"message_id": 4201}})

        transport = httpx.MockTransport(handler)
        async with httpx.AsyncClient(transport=transport) as http_client:
            client = TelegramClient(mock_settings, http_client=http_client)
            message_id = await client.send_suggestion(sample_pending_action)
            assert message_id == 4201

    @pytest.mark.asyncio
    async def test_send_suggestion_api_error(
        self, mock_settings: Settings, sample_pending_action: PendingAction
    ) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(
                400, json={"ok": False, "description": "Bad Request: chat not found"}
            )

        transport = httpx.MockTransport(handler)
        async with httpx.AsyncClient(transport=transport) as http_client:
            client = TelegramClient(mock_settings, http_client=http_client)
            with pytest.raises(TelegramAPIError) as exc_info:
                await client.send_suggestion(sample_pending_action)
            assert "chat not found" in str(exc_info.value)
            assert exc_info.value.details.get("status_code") == 400

    @pytest.mark.asyncio
    async def test_send_suggestion_missing_message_id_raises(
        self, mock_settings: Settings, sample_pending_action: PendingAction
    ) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, json={"ok": True, "result": {}})

        transport = httpx.MockTransport(handler)
        async with httpx.AsyncClient(transport=transport) as http_client:
            client = TelegramClient(mock_settings, http_client=http_client)
            with pytest.raises(TelegramAPIError, match="missing integer message_id"):
                await client.send_suggestion(sample_pending_action)

    @pytest.mark.asyncio
    async def test_edit_to_outcome_strips_keyboard(self, mock_settings: Settings) -> None:
        captured_payload: dict[str, Any] = {}

        def handler(request: httpx.Request) -> httpx.Response:
            nonlocal captured_payload
            import json

            captured_payload = json.loads(request.content.decode("utf-8"))
            return httpx.Response(200, json={"ok": True, "result": {"message_id": 555}})

        transport = httpx.MockTransport(handler)
        async with httpx.AsyncClient(transport=transport) as http_client:
            client = TelegramClient(mock_settings, http_client=http_client)
            await client.edit_to_outcome(987654321, 555, "<b>✅ Done</b>")

            assert captured_payload["chat_id"] == 987654321
            assert captured_payload["message_id"] == 555
            assert captured_payload["reply_markup"] == {"inline_keyboard": []}

    @pytest.mark.asyncio
    async def test_edit_to_outcome_message_not_modified_ignored(
        self, mock_settings: Settings
    ) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(
                400,
                json={
                    "ok": False,
                    "description": "Bad Request: message is not modified: specified new message content and reply markup are exactly the same",
                },
            )

        transport = httpx.MockTransport(handler)
        async with httpx.AsyncClient(transport=transport) as http_client:
            client = TelegramClient(mock_settings, http_client=http_client)
            # Should NOT raise an exception
            await client.edit_to_outcome(987654321, 555, "<b>✅ Done</b>")

    @pytest.mark.asyncio
    async def test_edit_to_outcome_fatal_error_raises(self, mock_settings: Settings) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(
                403,
                json={"ok": False, "description": "Forbidden: bot was blocked by the user"},
            )

        transport = httpx.MockTransport(handler)
        async with httpx.AsyncClient(transport=transport) as http_client:
            client = TelegramClient(mock_settings, http_client=http_client)
            with pytest.raises(TelegramAPIError, match="bot was blocked"):
                await client.edit_to_outcome(987654321, 555, "<b>✅ Done</b>")

    @pytest.mark.asyncio
    async def test_send_notification_success_and_network_error(
        self, mock_settings: Settings
    ) -> None:
        # Success
        def handler_ok(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, json={"ok": True, "result": {"message_id": 9001}})

        transport_ok = httpx.MockTransport(handler_ok)
        async with httpx.AsyncClient(transport=transport_ok) as http_client:
            client = TelegramClient(mock_settings, http_client=http_client)
            msg_id = await client.send_notification("<b>Alert</b>: System started.")
            assert msg_id == 9001

        # Network error
        def handler_err(request: httpx.Request) -> httpx.Response:
            raise httpx.ConnectTimeout("Connection timed out")

        transport_err = httpx.MockTransport(handler_err)
        async with httpx.AsyncClient(transport=transport_err) as http_client:
            client = TelegramClient(mock_settings, http_client=http_client)
            with pytest.raises(TelegramAPIError, match="network request failed"):
                await client.send_notification("Alert")

    @pytest.mark.asyncio
    async def test_send_notification_missing_id_raises(self, mock_settings: Settings) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, json={"ok": True, "result": {}})

        transport = httpx.MockTransport(handler)
        async with httpx.AsyncClient(transport=transport) as http_client:
            client = TelegramClient(mock_settings, http_client=http_client)
            with pytest.raises(TelegramAPIError, match="notification missing message_id"):
                await client.send_notification("Alert")

    @pytest.mark.asyncio
    async def test_telegram_non_json_error_response(self, mock_settings: Settings) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(502, text="<html>502 Bad Gateway</html>")

        transport = httpx.MockTransport(handler)
        async with httpx.AsyncClient(transport=transport) as http_client:
            client = TelegramClient(mock_settings, http_client=http_client)
            with pytest.raises(TelegramAPIError, match="Telegram API error 502"):
                await client.send_notification("Alert")

    @pytest.mark.asyncio
    async def test_client_context_manager(self, mock_settings: Settings) -> None:
        async with TelegramClient(mock_settings) as client:
            assert client._http_client is not None
            assert not client._http_client.is_closed

        assert client._http_client.is_closed
