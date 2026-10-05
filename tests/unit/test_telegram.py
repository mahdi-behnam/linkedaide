import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx
import pytest

from agent.config import Settings
from agent.errors import TelegramAPIError
from agent.models import PendingAction
from agent.state.store import GitStateStore
from agent.telegram.client import TelegramClient
from agent.telegram.draft_editor import handle_draft_edit, handle_edit_callback
from agent.telegram.keyboards import (
    build_outcome_message,
    build_suggestion_keyboard,
    build_suggestion_message,
    format_suggestion_card,
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
def test_state_store(tmp_path: Path) -> GitStateStore:
    """Create a clean local GitStateStore fixture for testing draft editing."""
    return GitStateStore(tmp_path)


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

    def test_build_suggestion_keyboard_reply(self) -> None:
        keyboard = build_suggestion_keyboard("reply_123", "approve_reply")
        buttons = keyboard["inline_keyboard"][0]
        assert buttons[0]["callback_data"] == "ar:reply_123"
        assert buttons[1]["callback_data"] == "rr:reply_123"

    def test_build_suggestion_keyboard_connection(self) -> None:
        keyboard = build_suggestion_keyboard("conn_123", "approve_connection")
        buttons = keyboard["inline_keyboard"][0]
        assert buttons[0]["callback_data"] == "acon:conn_123"
        assert buttons[1]["callback_data"] == "rcon:conn_123"

    def test_build_suggestion_keyboard_includes_edit_button(self) -> None:
        keyboard = build_suggestion_keyboard("item_edit_test", "approve_comment")
        assert len(keyboard["inline_keyboard"]) == 2
        row1 = keyboard["inline_keyboard"][0]
        row2 = keyboard["inline_keyboard"][1]
        assert len(row1) == 2
        assert row1[0]["text"] == "✅ Approve"
        assert row1[0]["callback_data"] == "ac:item_edit_test"
        assert row1[1]["text"] == "❌ Reject"
        assert row1[1]["callback_data"] == "rc:item_edit_test"
        assert len(row2) == 2
        assert row2[0]["text"] == "🔄 Regenerate"
        assert row2[0]["callback_data"] == "reg:item_edit_test"
        assert row2[1]["text"] == "✏️ Edit"
        assert row2[1]["callback_data"] == "edit:item_edit_test"
        assert len(b"reg:item_edit_test") < 64
        assert len(b"edit:item_edit_test") < 64

    def test_format_suggestion_card_comprehensive(self) -> None:
        item = PendingAction(
            item_id="item_card_test_01",
            action_type="approve_comment",
            post_urn="urn:li:activity:999888",
            post_url="https://linkedin.com/feed/update/urn:li:activity:999888",
            author_name="Bob Builder <VP & CTO>",
            author_headline="VP of Engineering @ AI Corp",
            post_excerpt="Exploring scalable microservices with Rust & Go.",
            draft_text="Fascinating architecture! How do you handle distributed transaction rollback in this setup?",
            confidence=0.94,
            reasoning="Strong systems engineering topic matching core focus area.",
            created_at=datetime(2026, 9, 1, 10, 0, 0, tzinfo=UTC),
        )
        card = format_suggestion_card(item)

        # Target Post Author & Headline (with HTML escaping)
        assert "&lt;VP &amp; CTO&gt;" in card
        assert "VP of Engineering @ AI Corp" in card
        assert (
            "<b>Author:</b> Bob Builder &lt;VP &amp; CTO&gt; (<i>VP of Engineering @ AI Corp</i>)"
            in card
        )

        # Clean excerpt blockquote
        assert (
            "<b>Post Excerpt:</b>\n<blockquote>Exploring scalable microservices with Rust &amp; Go.</blockquote>"
            in card
        )
        # Draft blockquote
        assert (
            "<b>Drafted Content:</b>\n<blockquote>Fascinating architecture! How do you handle distributed transaction rollback in this setup?</blockquote>"
            in card
        )

        # Metrics: char and word count
        char_count = len(item.draft_text)
        word_count = len(item.draft_text.split())
        assert f"<b>Metrics:</b> {char_count} chars • {word_count} words" in card

        # Confidence and reasoning
        assert "<b>Confidence:</b> 94%" in card
        assert (
            "<b>Reasoning:</b> Strong systems engineering topic matching core focus area." in card
        )

        # ID footer
        assert "<i>ID: item_card_test_01</i>" in card

    def test_telegram_client_format_suggestion_card(
        self, sample_pending_action: PendingAction
    ) -> None:
        card1 = format_suggestion_card(sample_pending_action)
        card2 = TelegramClient.format_suggestion_card(sample_pending_action)
        assert card1 == card2

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

    def test_build_outcome_messages_for_reply_and_connection(self) -> None:
        reply_action = PendingAction(
            item_id="reply_out_1",
            action_type="approve_reply",
            post_urn="urn:li:comment:111",
            author_name="Dev Author",
            draft_text="Reply text here",
            confidence=0.9,
            created_at=datetime.now(UTC),
        )
        conn_action = PendingAction(
            item_id="conn_out_1",
            action_type="approve_connection",
            author_name="Profile Author",
            draft_text="Hi, let's connect!",
            confidence=0.85,
            created_at=datetime.now(UTC),
        )
        reply_msg = build_outcome_message(reply_action, "success")
        assert "Thread Reply" in reply_msg
        assert "reply_out_1" in reply_msg

        conn_msg = build_outcome_message(conn_action, "success")
        assert "Connection Request" in conn_msg
        assert "conn_out_1" in conn_msg

    def test_format_suggestion_card_reply_and_connection(self) -> None:
        reply_action = PendingAction(
            item_id="reply_card_1",
            action_type="approve_reply",
            post_urn="urn:li:comment:222",
            author_name="Thread Participant",
            post_excerpt="What are the best patterns for resilient workflows?",
            draft_text="Deterministic state checkpointing is key.",
            confidence=0.92,
            created_at=datetime.now(UTC),
        )
        conn_action = PendingAction(
            item_id="conn_card_1",
            action_type="approve_connection",
            author_name="Engineering Director",
            draft_text="Would love to connect regarding agent infrastructure.",
            confidence=0.88,
            created_at=datetime.now(UTC),
        )

        reply_card = format_suggestion_card(reply_action)
        assert "💬 Thread Reply" in reply_card
        assert "Parent Comment:" in reply_card

        conn_card = format_suggestion_card(conn_action)
        assert "🤝 Connection Request" in conn_card
        assert "Drafted Note:" in conn_card


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

    @pytest.mark.asyncio
    async def test_edit_message_text_success(self, mock_settings: Settings) -> None:
        captured_payload: dict[str, Any] = {}

        def handler(request: httpx.Request) -> httpx.Response:
            nonlocal captured_payload
            assert request.url.path.endswith("/editMessageText")
            captured_payload = json.loads(request.content.decode("utf-8"))
            return httpx.Response(200, json={"ok": True, "result": {"message_id": 777}})

        transport = httpx.MockTransport(handler)
        async with httpx.AsyncClient(transport=transport) as http_client:
            client = TelegramClient(mock_settings, http_client=http_client)
            keyboard = {"inline_keyboard": [[{"text": "Btn", "callback_data": "data"}]]}
            await client.edit_message_text(
                chat_id=987654321,
                message_id=777,
                text="<b>Updated Text</b>",
                reply_markup=keyboard,
            )

            assert captured_payload["chat_id"] == 987654321
            assert captured_payload["message_id"] == 777
            assert captured_payload["text"] == "<b>Updated Text</b>"
            assert captured_payload["parse_mode"] == "HTML"
            assert captured_payload["link_preview_options"] == {"is_disabled": True}
            assert captured_payload["reply_markup"] == keyboard

    @pytest.mark.asyncio
    async def test_edit_message_text_message_not_modified_ignored(
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
            # Should not raise exception
            await client.edit_message_text(
                chat_id=987654321,
                message_id=777,
                text="Same Text",
            )

    @pytest.mark.asyncio
    async def test_edit_message_text_fatal_error_raises(self, mock_settings: Settings) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(
                400,
                json={"ok": False, "description": "Bad Request: chat not found"},
            )

        transport = httpx.MockTransport(handler)
        async with httpx.AsyncClient(transport=transport) as http_client:
            client = TelegramClient(mock_settings, http_client=http_client)
            with pytest.raises(TelegramAPIError, match="chat not found"):
                await client.edit_message_text(
                    chat_id=987654321,
                    message_id=777,
                    text="New Text",
                )

    @pytest.mark.asyncio
    async def test_answer_callback_query_success(self, mock_settings: Settings) -> None:
        captured_payload: dict[str, Any] = {}

        def handler(request: httpx.Request) -> httpx.Response:
            nonlocal captured_payload
            assert request.url.path.endswith("/answerCallbackQuery")
            captured_payload = json.loads(request.content.decode("utf-8"))
            return httpx.Response(200, json={"ok": True, "result": True})

        transport = httpx.MockTransport(handler)
        async with httpx.AsyncClient(transport=transport) as http_client:
            client = TelegramClient(mock_settings, http_client=http_client)
            await client.answer_callback_query(
                callback_query_id="query_abc_123",
                text="Notice text",
                show_alert=True,
            )

            assert captured_payload["callback_query_id"] == "query_abc_123"
            assert captured_payload["text"] == "Notice text"
            assert captured_payload["show_alert"] is True

    @pytest.mark.asyncio
    async def test_answer_callback_query_defaults(self, mock_settings: Settings) -> None:
        captured_payload: dict[str, Any] = {}

        def handler(request: httpx.Request) -> httpx.Response:
            nonlocal captured_payload
            assert request.url.path.endswith("/answerCallbackQuery")
            captured_payload = json.loads(request.content.decode("utf-8"))
            return httpx.Response(200, json={"ok": True, "result": True})

        transport = httpx.MockTransport(handler)
        async with httpx.AsyncClient(transport=transport) as http_client:
            client = TelegramClient(mock_settings, http_client=http_client)
            await client.answer_callback_query(callback_query_id="query_minimal")

            assert captured_payload["callback_query_id"] == "query_minimal"
            assert "text" not in captured_payload
            assert "show_alert" not in captured_payload

    @pytest.mark.asyncio
    async def test_answer_callback_query_api_error_raises(self, mock_settings: Settings) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(
                400,
                json={"ok": False, "description": "Bad Request: query is too old"},
            )

        transport = httpx.MockTransport(handler)
        async with httpx.AsyncClient(transport=transport) as http_client:
            client = TelegramClient(mock_settings, http_client=http_client)
            with pytest.raises(TelegramAPIError, match="query is too old"):
                await client.answer_callback_query(callback_query_id="old_query")

    @pytest.mark.asyncio
    async def test_send_message_success(self, mock_settings: Settings) -> None:
        captured_payload: dict[str, Any] = {}

        def handler(request: httpx.Request) -> httpx.Response:
            nonlocal captured_payload
            assert request.url.path.endswith("/sendMessage")
            captured_payload = json.loads(request.content.decode("utf-8"))
            return httpx.Response(200, json={"ok": True, "result": {"message_id": 8801}})

        transport = httpx.MockTransport(handler)
        async with httpx.AsyncClient(transport=transport) as http_client:
            client = TelegramClient(mock_settings, http_client=http_client)
            keyboard: dict[str, Any] = {"inline_keyboard": []}
            msg_id = await client.send_message(
                chat_id=987654321,
                text="<b>Hello</b>",
                reply_markup=keyboard,
                reply_to_message_id=7701,
            )
            assert msg_id == 8801
            assert captured_payload["chat_id"] == 987654321
            assert captured_payload["text"] == "<b>Hello</b>"
            assert captured_payload["parse_mode"] == "HTML"
            assert captured_payload["link_preview_options"] == {"is_disabled": True}
            assert captured_payload["reply_markup"] == keyboard
            assert captured_payload["reply_to_message_id"] == 7701

    @pytest.mark.asyncio
    async def test_send_message_missing_message_id_raises(self, mock_settings: Settings) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, json={"ok": True, "result": {}})

        transport = httpx.MockTransport(handler)
        async with httpx.AsyncClient(transport=transport) as http_client:
            client = TelegramClient(mock_settings, http_client=http_client)
            with pytest.raises(TelegramAPIError, match="missing integer message_id"):
                await client.send_message(chat_id=987654321, text="Test")

    @pytest.mark.asyncio
    async def test_send_message_api_error_raises(self, mock_settings: Settings) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(
                400,
                json={"ok": False, "description": "Bad Request: message text is empty"},
            )

        transport = httpx.MockTransport(handler)
        async with httpx.AsyncClient(transport=transport) as http_client:
            client = TelegramClient(mock_settings, http_client=http_client)
            with pytest.raises(TelegramAPIError, match="message text is empty"):
                await client.send_message(chat_id=987654321, text="")


class TestHandleDraftEdit:
    """Test suite for handle_draft_edit interactive draft revisions."""

    @pytest.mark.asyncio
    async def test_handle_draft_edit_authorized_success(
        self,
        mock_settings: Settings,
        test_state_store: GitStateStore,
        sample_pending_action: PendingAction,
    ) -> None:
        action = sample_pending_action.model_copy(update={"telegram_message_id": 1001})
        test_state_store.write_pending(action)

        recorded_requests: list[dict[str, Any]] = []

        def handler(request: httpx.Request) -> httpx.Response:
            data = json.loads(request.content.decode("utf-8"))
            recorded_requests.append({"path": request.url.path, "payload": data})
            if request.url.path.endswith("/editMessageText"):
                return httpx.Response(200, json={"ok": True, "result": {"message_id": 1001}})
            if request.url.path.endswith("/sendMessage"):
                return httpx.Response(200, json={"ok": True, "result": {"message_id": 2002}})
            return httpx.Response(200, json={"ok": True})

        transport = httpx.MockTransport(handler)
        async with httpx.AsyncClient(transport=transport) as http_client:
            telegram = TelegramClient(mock_settings, http_client=http_client)
            message = {
                "message_id": 2001,
                "text": "Revised draft comment text with better explanation.",
                "from": {"id": 987654321},
                "chat": {"id": 987654321},
                "reply_to_message": {
                    "message_id": 1001,
                    "text": "Original suggestion message",
                },
            }

            result = await handle_draft_edit(
                message=message,
                settings=mock_settings,
                state_store=test_state_store,
                telegram=telegram,
            )

            assert result is True

            # Verify durable state updated
            updated_pending = test_state_store.read_pending(sample_pending_action.item_id)
            assert updated_pending is not None
            assert (
                updated_pending.draft_text == "Revised draft comment text with better explanation."
            )

            # Verify editMessageText called with re-rendered text and keyboard
            edit_reqs = [r for r in recorded_requests if r["path"].endswith("/editMessageText")]
            assert len(edit_reqs) == 1
            assert edit_reqs[0]["payload"]["chat_id"] == 987654321
            assert edit_reqs[0]["payload"]["message_id"] == 1001
            assert (
                "Revised draft comment text with better explanation."
                in edit_reqs[0]["payload"]["text"]
            )
            assert edit_reqs[0]["payload"]["reply_markup"] is not None

            # Verify confirmation sendMessage was dispatched
            send_reqs = [r for r in recorded_requests if r["path"].endswith("/sendMessage")]
            assert len(send_reqs) == 1
            assert send_reqs[0]["payload"]["chat_id"] == 987654321
            assert send_reqs[0]["payload"]["reply_to_message_id"] == 2001
            assert "Draft updated" in send_reqs[0]["payload"]["text"]

    @pytest.mark.asyncio
    async def test_handle_draft_edit_fallback_item_id_regex(
        self,
        mock_settings: Settings,
        test_state_store: GitStateStore,
        sample_pending_action: PendingAction,
    ) -> None:
        action = sample_pending_action.model_copy(update={"telegram_message_id": None})
        test_state_store.write_pending(action)

        recorded_requests: list[dict[str, Any]] = []

        def handler(request: httpx.Request) -> httpx.Response:
            data = json.loads(request.content.decode("utf-8"))
            recorded_requests.append({"path": request.url.path, "payload": data})
            return httpx.Response(200, json={"ok": True, "result": {"message_id": 3001}})

        transport = httpx.MockTransport(handler)
        async with httpx.AsyncClient(transport=transport) as http_client:
            telegram = TelegramClient(mock_settings, http_client=http_client)
            message = {
                "message_id": 2050,
                "text": "Regex fallback draft content.",
                "from": {"id": 987654321},
                "chat": {"id": 987654321},
                "reply_to_message": {
                    "message_id": 5555,
                    "text": f"Suggestion card\nID: {sample_pending_action.item_id}\nAuthor: Jane",
                },
            }

            result = await handle_draft_edit(
                message=message,
                settings=mock_settings,
                state_store=test_state_store,
                telegram=telegram,
            )

            assert result is True
            updated_pending = test_state_store.read_pending(sample_pending_action.item_id)
            assert updated_pending is not None
            assert updated_pending.draft_text == "Regex fallback draft content."

            edit_reqs = [r for r in recorded_requests if r["path"].endswith("/editMessageText")]
            assert len(edit_reqs) == 1
            assert edit_reqs[0]["payload"]["message_id"] == 5555

    @pytest.mark.asyncio
    async def test_handle_draft_edit_unauthorized_sender(
        self,
        mock_settings: Settings,
        test_state_store: GitStateStore,
        sample_pending_action: PendingAction,
    ) -> None:
        test_state_store.write_pending(sample_pending_action)
        recorded_requests: list[dict[str, Any]] = []

        def handler(request: httpx.Request) -> httpx.Response:
            data = json.loads(request.content.decode("utf-8"))
            recorded_requests.append({"path": request.url.path, "payload": data})
            return httpx.Response(200, json={"ok": True, "result": {"message_id": 1}})

        transport = httpx.MockTransport(handler)
        async with httpx.AsyncClient(transport=transport) as http_client:
            telegram = TelegramClient(mock_settings, http_client=http_client)
            message = {
                "message_id": 2001,
                "text": "Malicious override attempt.",
                "from": {"id": 111222333},
                "chat": {"id": 987654321},
                "reply_to_message": {"message_id": 1001, "text": "Original message"},
            }

            result = await handle_draft_edit(
                message=message,
                settings=mock_settings,
                state_store=test_state_store,
                telegram=telegram,
            )

            assert result is False
            # Zero state mutation
            item = test_state_store.read_pending(sample_pending_action.item_id)
            assert item is not None
            assert item.draft_text == sample_pending_action.draft_text
            # Zero API calls
            assert len(recorded_requests) == 0

    @pytest.mark.asyncio
    async def test_handle_draft_edit_missing_reply_to_message(
        self,
        mock_settings: Settings,
        test_state_store: GitStateStore,
        sample_pending_action: PendingAction,
    ) -> None:
        test_state_store.write_pending(sample_pending_action)
        recorded_requests: list[dict[str, Any]] = []

        def handler(request: httpx.Request) -> httpx.Response:
            recorded_requests.append({"path": request.url.path})
            return httpx.Response(200, json={"ok": True})

        transport = httpx.MockTransport(handler)
        async with httpx.AsyncClient(transport=transport) as http_client:
            telegram = TelegramClient(mock_settings, http_client=http_client)
            message = {
                "message_id": 2001,
                "text": "Not a reply to anything.",
                "from": {"id": 987654321},
                "chat": {"id": 987654321},
            }

            result = await handle_draft_edit(
                message=message,
                settings=mock_settings,
                state_store=test_state_store,
                telegram=telegram,
            )

            assert result is False
            assert len(recorded_requests) == 0

    @pytest.mark.asyncio
    async def test_handle_draft_edit_missing_or_expired_item(
        self,
        mock_settings: Settings,
        test_state_store: GitStateStore,
    ) -> None:
        recorded_requests: list[dict[str, Any]] = []

        def handler(request: httpx.Request) -> httpx.Response:
            data = json.loads(request.content.decode("utf-8"))
            recorded_requests.append({"path": request.url.path, "payload": data})
            return httpx.Response(200, json={"ok": True, "result": {"message_id": 9901}})

        transport = httpx.MockTransport(handler)
        async with httpx.AsyncClient(transport=transport) as http_client:
            telegram = TelegramClient(mock_settings, http_client=http_client)
            message = {
                "message_id": 2001,
                "text": "Revision for non-existent item.",
                "from": {"id": 987654321},
                "chat": {"id": 987654321},
                "reply_to_message": {
                    "message_id": 9999,
                    "text": "Some expired suggestion message without ID pattern",
                },
            }

            result = await handle_draft_edit(
                message=message,
                settings=mock_settings,
                state_store=test_state_store,
                telegram=telegram,
            )

            assert result is False
            assert len(test_state_store.list_pending()) == 0

            # Warning sent to operator
            send_reqs = [r for r in recorded_requests if r["path"].endswith("/sendMessage")]
            assert len(send_reqs) == 1
            assert (
                "no longer pending or has already been processed" in send_reqs[0]["payload"]["text"]
            )
            assert send_reqs[0]["payload"]["reply_to_message_id"] == 2001

    @pytest.mark.asyncio
    async def test_handle_draft_edit_empty_text_rejected(
        self,
        mock_settings: Settings,
        test_state_store: GitStateStore,
        sample_pending_action: PendingAction,
    ) -> None:
        action = sample_pending_action.model_copy(update={"telegram_message_id": 1001})
        test_state_store.write_pending(action)
        recorded_requests: list[dict[str, Any]] = []

        def handler(request: httpx.Request) -> httpx.Response:
            data = json.loads(request.content.decode("utf-8"))
            recorded_requests.append({"path": request.url.path, "payload": data})
            return httpx.Response(200, json={"ok": True, "result": {"message_id": 9902}})

        transport = httpx.MockTransport(handler)
        async with httpx.AsyncClient(transport=transport) as http_client:
            telegram = TelegramClient(mock_settings, http_client=http_client)
            message = {
                "message_id": 2001,
                "text": "   \n  ",
                "from": {"id": 987654321},
                "chat": {"id": 987654321},
                "reply_to_message": {"message_id": 1001, "text": "Original"},
            }

            result = await handle_draft_edit(
                message=message,
                settings=mock_settings,
                state_store=test_state_store,
                telegram=telegram,
            )

            assert result is False
            # Durable state unchanged
            item = test_state_store.read_pending(sample_pending_action.item_id)
            assert item is not None
            assert item.draft_text == sample_pending_action.draft_text

            # Error message sent
            send_reqs = [r for r in recorded_requests if r["path"].endswith("/sendMessage")]
            assert len(send_reqs) == 1
            assert "cannot be empty" in send_reqs[0]["payload"]["text"]

    @pytest.mark.asyncio
    async def test_handle_draft_edit_comment_length_limit(
        self,
        mock_settings: Settings,
        test_state_store: GitStateStore,
        sample_pending_action: PendingAction,
    ) -> None:
        action = sample_pending_action.model_copy(
            update={"action_type": "approve_comment", "telegram_message_id": 1001}
        )
        test_state_store.write_pending(action)
        recorded_requests: list[dict[str, Any]] = []

        def handler(request: httpx.Request) -> httpx.Response:
            data = json.loads(request.content.decode("utf-8"))
            recorded_requests.append({"path": request.url.path, "payload": data})
            return httpx.Response(200, json={"ok": True, "result": {"message_id": 9903}})

        transport = httpx.MockTransport(handler)
        async with httpx.AsyncClient(transport=transport) as http_client:
            telegram = TelegramClient(mock_settings, http_client=http_client)
            message = {
                "message_id": 2001,
                "text": "C" * 601,
                "from": {"id": 987654321},
                "chat": {"id": 987654321},
                "reply_to_message": {"message_id": 1001, "text": "Original"},
            }

            result = await handle_draft_edit(
                message=message,
                settings=mock_settings,
                state_store=test_state_store,
                telegram=telegram,
            )

            assert result is False
            # Draft unchanged
            item = test_state_store.read_pending(sample_pending_action.item_id)
            assert item is not None
            assert item.draft_text == sample_pending_action.draft_text

            send_reqs = [r for r in recorded_requests if r["path"].endswith("/sendMessage")]
            assert len(send_reqs) == 1
            assert "exceeds maximum length of 600 characters" in send_reqs[0]["payload"]["text"]

    @pytest.mark.asyncio
    async def test_handle_draft_edit_post_length_limit_and_success(
        self,
        mock_settings: Settings,
        test_state_store: GitStateStore,
        sample_pending_action: PendingAction,
    ) -> None:
        action = sample_pending_action.model_copy(
            update={"action_type": "approve_post", "telegram_message_id": 1002}
        )
        test_state_store.write_pending(action)
        recorded_requests: list[dict[str, Any]] = []

        def handler(request: httpx.Request) -> httpx.Response:
            data = json.loads(request.content.decode("utf-8"))
            recorded_requests.append({"path": request.url.path, "payload": data})
            return httpx.Response(200, json={"ok": True, "result": {"message_id": 9904}})

        transport = httpx.MockTransport(handler)
        async with httpx.AsyncClient(transport=transport) as http_client:
            telegram = TelegramClient(mock_settings, http_client=http_client)

            # 1. Exceeds 1200 characters for post
            too_long_message = {
                "message_id": 2001,
                "text": "P" * 1201,
                "from": {"id": 987654321},
                "chat": {"id": 987654321},
                "reply_to_message": {"message_id": 1002, "text": "Original"},
            }
            res_too_long = await handle_draft_edit(
                message=too_long_message,
                settings=mock_settings,
                state_store=test_state_store,
                telegram=telegram,
            )
            assert res_too_long is False
            send_reqs = [r for r in recorded_requests if r["path"].endswith("/sendMessage")]
            assert "exceeds maximum length of 1200 characters" in send_reqs[0]["payload"]["text"]

            # 2. Valid post length between 600 and 1200 (e.g. 850 chars)
            recorded_requests.clear()
            valid_post_text = "V" * 850
            valid_message = {
                "message_id": 2002,
                "text": valid_post_text,
                "from": {"id": 987654321},
                "chat": {"id": 987654321},
                "reply_to_message": {"message_id": 1002, "text": "Original"},
            }
            res_valid = await handle_draft_edit(
                message=valid_message,
                settings=mock_settings,
                state_store=test_state_store,
                telegram=telegram,
            )
            assert res_valid is True
            updated = test_state_store.read_pending(sample_pending_action.item_id)
            assert updated is not None
            assert updated.draft_text == valid_post_text

    @pytest.mark.asyncio
    async def test_handle_draft_edit_store_update_fails(
        self,
        mock_settings: Settings,
        test_state_store: GitStateStore,
        sample_pending_action: PendingAction,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        action = sample_pending_action.model_copy(update={"telegram_message_id": 1001})
        test_state_store.write_pending(action)
        recorded_requests: list[dict[str, Any]] = []

        def handler(request: httpx.Request) -> httpx.Response:
            data = json.loads(request.content.decode("utf-8"))
            recorded_requests.append({"path": request.url.path, "payload": data})
            return httpx.Response(200, json={"ok": True, "result": {"message_id": 9905}})

        monkeypatch.setattr(test_state_store, "update_pending_draft", lambda *args, **kwargs: None)

        transport = httpx.MockTransport(handler)
        async with httpx.AsyncClient(transport=transport) as http_client:
            telegram = TelegramClient(mock_settings, http_client=http_client)
            message = {
                "message_id": 2001,
                "text": "Valid text that fails update",
                "from": {"id": 987654321},
                "chat": {"id": 987654321},
                "reply_to_message": {"message_id": 1001, "text": "Original"},
            }

            result = await handle_draft_edit(
                message=message,
                settings=mock_settings,
                state_store=test_state_store,
                telegram=telegram,
            )
            assert result is False
            send_reqs = [r for r in recorded_requests if r["path"].endswith("/sendMessage")]
            assert len(send_reqs) == 1
            assert (
                "Failed to update draft: suggestion is no longer pending"
                in send_reqs[0]["payload"]["text"]
            )


class TestHandleEditCallback:
    """Test suite for handle_edit_callback inline [✏️ Edit] button clicks."""

    @pytest.mark.asyncio
    async def test_handle_edit_callback_authorized_success(
        self,
        mock_settings: Settings,
        test_state_store: GitStateStore,
        sample_pending_action: PendingAction,
    ) -> None:
        test_state_store.write_pending(sample_pending_action)
        recorded_requests: list[dict[str, Any]] = []

        def handler(request: httpx.Request) -> httpx.Response:
            data = json.loads(request.content.decode("utf-8"))
            recorded_requests.append({"path": request.url.path, "payload": data})
            return httpx.Response(200, json={"ok": True, "result": True})

        transport = httpx.MockTransport(handler)
        async with httpx.AsyncClient(transport=transport) as http_client:
            telegram = TelegramClient(mock_settings, http_client=http_client)
            callback_query = {
                "id": "query_edit_001",
                "from": {"id": 987654321},
                "data": f"ed:{sample_pending_action.item_id}",
            }

            result = await handle_edit_callback(
                callback_query=callback_query,
                settings=mock_settings,
                state_store=test_state_store,
                telegram=telegram,
            )

            assert result is True
            assert len(recorded_requests) == 1
            assert recorded_requests[0]["path"].endswith("/answerCallbackQuery")
            payload = recorded_requests[0]["payload"]
            assert payload["callback_query_id"] == "query_edit_001"
            assert "Reply to this suggestion with your revised draft text" in payload["text"]
            assert payload.get("show_alert", False) is False

    @pytest.mark.asyncio
    async def test_handle_edit_callback_unauthorized(
        self,
        mock_settings: Settings,
        test_state_store: GitStateStore,
        sample_pending_action: PendingAction,
    ) -> None:
        test_state_store.write_pending(sample_pending_action)
        recorded_requests: list[dict[str, Any]] = []

        def handler(request: httpx.Request) -> httpx.Response:
            recorded_requests.append({"path": request.url.path})
            return httpx.Response(200, json={"ok": True})

        transport = httpx.MockTransport(handler)
        async with httpx.AsyncClient(transport=transport) as http_client:
            telegram = TelegramClient(mock_settings, http_client=http_client)
            callback_query = {
                "id": "query_edit_unauth",
                "from": {"id": 111222333},
                "data": f"ed:{sample_pending_action.item_id}",
            }

            result = await handle_edit_callback(
                callback_query=callback_query,
                settings=mock_settings,
                state_store=test_state_store,
                telegram=telegram,
            )

            assert result is False
            assert len(recorded_requests) == 0

    @pytest.mark.asyncio
    async def test_handle_edit_callback_missing_or_expired_item(
        self,
        mock_settings: Settings,
        test_state_store: GitStateStore,
    ) -> None:
        recorded_requests: list[dict[str, Any]] = []

        def handler(request: httpx.Request) -> httpx.Response:
            data = json.loads(request.content.decode("utf-8"))
            recorded_requests.append({"path": request.url.path, "payload": data})
            return httpx.Response(200, json={"ok": True, "result": True})

        transport = httpx.MockTransport(handler)
        async with httpx.AsyncClient(transport=transport) as http_client:
            telegram = TelegramClient(mock_settings, http_client=http_client)
            callback_query = {
                "id": "query_edit_missing",
                "from": {"id": 987654321},
                "data": "ed:nonexistent_item_999",
            }

            result = await handle_edit_callback(
                callback_query=callback_query,
                settings=mock_settings,
                state_store=test_state_store,
                telegram=telegram,
            )

            assert result is False
            assert len(recorded_requests) == 1
            payload = recorded_requests[0]["payload"]
            assert payload["callback_query_id"] == "query_edit_missing"
            assert "no longer pending or has already been processed" in payload["text"]
            assert payload.get("show_alert") is True

    @pytest.mark.asyncio
    async def test_handle_edit_callback_malformed_data(
        self,
        mock_settings: Settings,
        test_state_store: GitStateStore,
    ) -> None:
        recorded_requests: list[dict[str, Any]] = []

        def handler(request: httpx.Request) -> httpx.Response:
            data = json.loads(request.content.decode("utf-8"))
            recorded_requests.append({"path": request.url.path, "payload": data})
            return httpx.Response(200, json={"ok": True, "result": True})

        transport = httpx.MockTransport(handler)
        async with httpx.AsyncClient(transport=transport) as http_client:
            telegram = TelegramClient(mock_settings, http_client=http_client)
            callback_query = {
                "id": "query_malformed",
                "from": {"id": 987654321},
                "data": "invalid_data_without_colon",
            }

            result = await handle_edit_callback(
                callback_query=callback_query,
                settings=mock_settings,
                state_store=test_state_store,
                telegram=telegram,
            )

            assert result is False
            assert len(recorded_requests) == 1
            assert recorded_requests[0]["payload"]["show_alert"] is True
