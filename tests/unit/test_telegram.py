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
from agent.telegram.callbacks import (
    execute_back_callback,
    execute_callback_query,
    execute_cancel_edit_callback,
    execute_close_callback,
    execute_feedback_callback,
    execute_home_callback,
    execute_noop_callback,
    execute_refresh_callback,
    execute_reject_cancel_callback,
    execute_reject_confirm_callback,
    execute_reject_prompt_callback,
    execute_reset_circuit_breaker_callback,
    execute_review_callback,
    execute_tone_menu_callback,
    execute_tone_select_callback,
)
from agent.telegram.client import TelegramClient
from agent.telegram.draft_editor import handle_draft_edit, handle_edit_callback
from agent.telegram.keyboards import (
    build_editing_keyboard,
    build_help_keyboard,
    build_home_keyboard,
    build_outcome_message,
    build_pending_list_keyboard,
    build_regenerating_keyboard,
    build_reject_confirm_keyboard,
    build_rejection_feedback_keyboard,
    build_stats_keyboard,
    build_status_keyboard,
    build_suggestion_keyboard,
    build_suggestion_message,
    build_tone_keyboard,
    format_home_hub,
    format_rejection_card,
    format_suggestion_card,
    _format_safe_excerpt,
)
from agent.telegram.reply_keyboards import build_docked_reply_keyboard


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
        assert buttons[1]["callback_data"] == "ask_rej:item_abc"

    def test_build_suggestion_keyboard_post(self) -> None:
        keyboard = build_suggestion_keyboard("post_123", "approve_post")
        buttons = keyboard["inline_keyboard"][0]
        assert buttons[0]["callback_data"] == "ap:post_123"
        assert buttons[1]["callback_data"] == "ask_rej:post_123"

    def test_build_suggestion_keyboard_reply(self) -> None:
        keyboard = build_suggestion_keyboard("reply_123", "approve_reply")
        buttons = keyboard["inline_keyboard"][0]
        assert buttons[0]["callback_data"] == "ar:reply_123"
        assert buttons[1]["callback_data"] == "ask_rej:reply_123"

    def test_build_suggestion_keyboard_connection(self) -> None:
        keyboard = build_suggestion_keyboard("conn_123", "approve_connection")
        buttons = keyboard["inline_keyboard"][0]
        assert buttons[0]["callback_data"] == "acon:conn_123"
        assert buttons[1]["callback_data"] == "ask_rej:conn_123"

    def test_build_suggestion_keyboard_reaction(self) -> None:
        keyboard = build_suggestion_keyboard("rx_123", "approve_reaction")
        rows = keyboard["inline_keyboard"]
        assert len(rows) == 2  # Approve/Reject, Home Menu (no regenerate/edit)
        assert rows[0][0]["text"] == "✅ Approve"
        assert rows[0][0]["callback_data"] == "areact:rx_123"
        assert rows[0][1]["text"] == "❌ Reject"
        assert rows[0][1]["callback_data"] == "ask_rej:rx_123"
        assert rows[1][0]["text"] == "🏠 Home Menu"

    def test_build_suggestion_keyboard_includes_edit_button(self) -> None:
        keyboard = build_suggestion_keyboard("item_edit_test", "approve_comment")
        assert len(keyboard["inline_keyboard"]) == 3
        row1 = keyboard["inline_keyboard"][0]
        row2 = keyboard["inline_keyboard"][1]
        row3 = keyboard["inline_keyboard"][2]
        assert len(row1) == 2
        assert row1[0]["text"] == "✅ Approve"
        assert row1[0]["callback_data"] == "ac:item_edit_test"
        assert row1[1]["text"] == "❌ Reject"
        assert row1[1]["callback_data"] == "ask_rej:item_edit_test"
        assert len(row2) == 2
        assert row2[0]["text"] == "🔄 Regenerate"
        assert row2[0]["callback_data"] == "reg:item_edit_test"
        assert row2[1]["text"] == "✏️ Edit"
        assert row2[1]["callback_data"] == "ed:item_edit_test"
        assert row3[0]["text"] == "🏠 Home Menu"
        assert row3[0]["callback_data"] == "home:menu"
        assert len(b"reg:item_edit_test") < 64
        assert len(b"ed:item_edit_test") < 64

    def test_build_suggestion_keyboard_with_post_url(self) -> None:
        keyboard = build_suggestion_keyboard(
            "item_url_test", "approve_comment", post_url="https://linkedin.com/feed/update/urn:li:activity:123"
        )
        assert len(keyboard["inline_keyboard"]) == 4
        # First row is LinkedIn URL button
        assert keyboard["inline_keyboard"][0][0]["text"] == "🔗 View Post on LinkedIn"
        assert keyboard["inline_keyboard"][0][0]["url"] == "https://linkedin.com/feed/update/urn:li:activity:123"
        # Second row is Approve / Reject
        assert keyboard["inline_keyboard"][1][0]["text"] == "✅ Approve"
        assert keyboard["inline_keyboard"][1][1]["text"] == "❌ Reject"
        # Third row is Regenerate / Edit
        assert keyboard["inline_keyboard"][2][0]["text"] == "🔄 Regenerate"
        assert keyboard["inline_keyboard"][2][1]["text"] == "✏️ Edit"
        # Fourth row is Home Menu
        assert keyboard["inline_keyboard"][3][0]["text"] == "🏠 Home Menu"

    def test_build_editing_keyboard(self) -> None:
        kb = build_editing_keyboard("item_edit_123")
        assert len(kb["inline_keyboard"]) == 1
        btn = kb["inline_keyboard"][0][0]
        assert btn["text"] == "❌ Cancel Edit"
        assert btn["callback_data"] == "cx_ed:item_edit_123"
        assert len(b"cx_ed:item_edit_123") < 64

    def test_build_regenerating_keyboard(self) -> None:
        kb = build_regenerating_keyboard("item_regen_123")
        assert len(kb["inline_keyboard"]) == 1
        btn = kb["inline_keyboard"][0][0]
        assert "Generating with AI" in btn["text"]
        assert btn["callback_data"] == "noop:item_regen_123"
        assert len(b"noop:item_regen_123") < 64

    def test_build_pending_list_keyboard(self) -> None:
        items = [
            PendingAction(
                item_id="item_01",
                action_type="approve_comment",
                post_url="",
                draft_text="test draft 1",
            ),
            PendingAction(
                item_id="item_02",
                action_type="approve_post",
                post_url="",
                draft_text="test draft 2",
            ),
        ]
        kb = build_pending_list_keyboard(items)
        assert len(kb["inline_keyboard"]) == 3
        assert "Review #1" in kb["inline_keyboard"][0][0]["text"]
        assert kb["inline_keyboard"][0][0]["callback_data"] == "rev:item_01"
        assert "Review #2" in kb["inline_keyboard"][1][0]["text"]
        assert kb["inline_keyboard"][1][0]["callback_data"] == "rev:item_02"
        assert kb["inline_keyboard"][2][0]["text"] == "🔄 Refresh Queue"
        assert kb["inline_keyboard"][2][1]["text"] == "🏠 Home Menu"

    def test_build_status_keyboard(self) -> None:
        kb_tripped = build_status_keyboard(is_tripped=True, pending_count=3)
        assert len(kb_tripped["inline_keyboard"]) == 3
        assert kb_tripped["inline_keyboard"][0][0]["text"] == "🔄 Reset Circuit Breaker"
        assert kb_tripped["inline_keyboard"][0][0]["callback_data"] == "reset_cb:global"
        assert "Review Pending (3)" in kb_tripped["inline_keyboard"][1][0]["text"]
        assert kb_tripped["inline_keyboard"][2][0]["text"] == "🔄 Refresh Status"
        assert kb_tripped["inline_keyboard"][2][1]["text"] == "🏠 Home Menu"

        kb_normal = build_status_keyboard(is_tripped=False, pending_count=0)
        assert len(kb_normal["inline_keyboard"]) == 1
        assert kb_normal["inline_keyboard"][0][0]["text"] == "🔄 Refresh Status"
        assert kb_normal["inline_keyboard"][0][1]["text"] == "🏠 Home Menu"

    def test_build_docked_reply_keyboard_placeholder(self) -> None:
        markup = build_docked_reply_keyboard(is_paused=False, input_placeholder="Custom hint...")
        assert markup["input_field_placeholder"] == "Custom hint..."
        assert markup["resize_keyboard"] is True
        assert markup["is_persistent"] is True

    def test_format_rejection_card(self) -> None:
        item = PendingAction(
            item_id="rej_123",
            action_type="approve_comment",
            post_url="https://linkedin.com/post/123",
            author_name="Alice Smith",
            draft_text="Insightful thought!",
        )
        card_prompt = format_rejection_card(item)
        assert "❌ Suggestion Rejected by Operator" in card_prompt
        assert "rej_123" in card_prompt
        assert "Alice Smith" in card_prompt
        assert "Insightful thought!" in card_prompt
        assert "Why was this suggestion rejected?" in card_prompt

        card_feedback = format_rejection_card(item, reason="Too Generic")
        assert "Too Generic" in card_feedback
        assert "Feedback:" in card_feedback

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

        # Clean excerpt blockquote with expandable attribute
        assert (
            "<b>Post Excerpt:</b>\n<blockquote expandable>Exploring scalable microservices with Rust &amp; Go.</blockquote>"
            in card
        )
        # Draft blockquote with expandable attribute
        assert (
            "<b>Drafted Content:</b>\n<blockquote expandable>Fascinating architecture! How do you handle distributed transaction rollback in this setup?</blockquote>"
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

    def test_format_suggestion_card_full_length_excerpt(self) -> None:
        full_text = (
            "Building scalable microservices requires addressing distributed transaction consistency, "
            "network partitioning, and consensus latency. When designing services in Rust and Go, "
            "we often rely on asynchronous messaging brokers like Kafka or NATS to decouple components. "
            "However, handling idempotency and dual-write anomalies remains a primary challenge. "
            "In this post, we explore the Outbox pattern combined with change-data-capture (CDC) "
            "to guarantee at-least-once delivery without distributed locks."
        )
        assert len(full_text) > 400
        item = PendingAction(
            item_id="item_full_post_01",
            action_type="approve_comment",
            post_urn="urn:li:activity:777888",
            post_url="https://linkedin.com/feed/update/urn:li:activity:777888",
            author_name="Alice Architect",
            post_excerpt=full_text,
            draft_text="Great overview! The CDC Outbox pattern is crucial for reliable microservices.",
            confidence=0.92,
            reasoning="Directly covers distributed systems and messaging patterns.",
        )
        card = format_suggestion_card(item)

        # Verify the entire post text is preserved without the old 200 char truncation
        assert full_text in card
        assert f"<blockquote expandable>{full_text}</blockquote>" in card
        assert len(card) <= 3800

    def test_format_suggestion_card_dynamic_budget_truncation(self) -> None:
        # Create a massive post of 5000 characters
        huge_post = "Distributed systems require careful consensus design. " * 100
        assert len(huge_post) > 5000

        item = PendingAction(
            item_id="item_huge_post_01",
            action_type="approve_comment",
            post_urn="urn:li:activity:999111",
            post_url="https://linkedin.com/feed/update/urn:li:activity:999111",
            author_name="Bob Consensus",
            post_excerpt=huge_post,
            draft_text="Raft consensus and leader lease patterns are fundamental.",
            confidence=0.95,
            reasoning="Core consensus topic.",
        )
        card = format_suggestion_card(item, max_card_length=3800)

        # Verify that total length is bounded by max_card_length
        assert len(card) <= 3800
        # Verify truncation indicator is present
        assert "… [truncated for length]" in card
        # Verify expandable blockquote is cleanly closed
        assert "<blockquote expandable>" in card
        assert "</blockquote>" in card
        # Verify card contains vital metadata despite truncation
        assert "Bob Consensus" in card
        assert "<i>ID: item_huge_post_01</i>" in card

    def test_format_safe_excerpt_edge_cases(self) -> None:
        # Empty excerpt returns empty
        assert _format_safe_excerpt("", "Post Excerpt", 1000) == ""
        assert _format_safe_excerpt("   ", "Post Excerpt", 1000) == ""

        # Tiny budget returns empty
        assert _format_safe_excerpt("Some post text", "Post Excerpt", 40) == ""

        # HTML entity escaping
        raw_with_html = "Testing <script>alert('xss')</script> & 'quotes' > < symbols"
        res = _format_safe_excerpt(raw_with_html, "Post Excerpt", 1000)
        assert "<script>" not in res
        assert "&lt;script&gt;" in res
        assert "&amp;" in res

    def test_build_suggestion_keyboard_exceeds_64_bytes(self) -> None:
        long_id = "x" * 63
        with pytest.raises(ValueError, match="exceeds 64 bytes limit"):
            build_suggestion_keyboard(long_id)

    def test_build_reject_confirm_keyboard(self) -> None:
        kb = build_reject_confirm_keyboard("item_999", "approve_comment")
        assert len(kb["inline_keyboard"]) == 2
        row0 = kb["inline_keyboard"][0]
        assert len(row0) == 2
        assert row0[0]["text"] == "❌ Yes, Reject"
        assert row0[0]["callback_data"] == "cf_rej:item_999"
        assert row0[1]["text"] == "🔙 Cancel / Keep"
        assert row0[1]["callback_data"] == "cx_rej:item_999"
        row1 = kb["inline_keyboard"][1]
        assert row1[0]["text"] == "🏠 Home Menu"
        assert row1[0]["callback_data"] == "home:menu"
        assert len(b"cf_rej:item_999") < 64
        assert len(b"cx_rej:item_999") < 64

    def test_build_rejection_feedback_keyboard(self) -> None:
        kb = build_rejection_feedback_keyboard("item_999")
        assert len(kb["inline_keyboard"]) == 3
        row1 = kb["inline_keyboard"][0]
        row2 = kb["inline_keyboard"][1]
        row3 = kb["inline_keyboard"][2]
        assert row1[0]["callback_data"] == "fb:generic:item_999"
        assert row1[1]["callback_data"] == "fb:boring:item_999"
        assert row2[0]["callback_data"] == "fb:risky:item_999"
        assert row2[1]["callback_data"] == "fb:offtopic:item_999"
        assert row3[0]["callback_data"] == "fb:skip:item_999"
        assert row3[1]["callback_data"] == "home:menu"
        for row in kb["inline_keyboard"]:
            for btn in row:
                assert len(btn["callback_data"].encode("utf-8")) < 64

    def test_build_tone_keyboard_comment(self) -> None:
        kb = build_tone_keyboard("item_999", "approve_comment")
        assert len(kb["inline_keyboard"]) == 3
        row1 = kb["inline_keyboard"][0]
        row2 = kb["inline_keyboard"][1]
        row3 = kb["inline_keyboard"][2]
        assert row1[0]["callback_data"] == "tone:technical:item_999"
        assert row1[1]["callback_data"] == "tone:inquisitive:item_999"
        assert row2[0]["callback_data"] == "tone:contrarian:item_999"
        assert row2[1]["callback_data"] == "tone:shorter:item_999"
        assert row3[0]["callback_data"] == "back:item_999"
        assert row3[1]["callback_data"] == "home:menu"
        for row in kb["inline_keyboard"]:
            for btn in row:
                assert len(btn["callback_data"].encode("utf-8")) < 64

    def test_build_tone_keyboard_connection(self) -> None:
        kb = build_tone_keyboard("conn_999", "approve_connection")
        assert len(kb["inline_keyboard"]) == 3
        row1 = kb["inline_keyboard"][0]
        row2 = kb["inline_keyboard"][1]
        row3 = kb["inline_keyboard"][2]
        assert row1[0]["callback_data"] == "tone:casual:conn_999"
        assert row1[1]["callback_data"] == "tone:technical:conn_999"
        assert row2[0]["callback_data"] == "tone:concise:conn_999"
        assert row3[0]["callback_data"] == "back:conn_999"
        assert row3[1]["callback_data"] == "home:menu"
        for row in kb["inline_keyboard"]:
            for btn in row:
                assert len(btn["callback_data"].encode("utf-8")) < 64

    def test_build_docked_reply_keyboard(self) -> None:
        kb_active = build_docked_reply_keyboard(is_paused=False)
        assert kb_active["resize_keyboard"] is True
        assert kb_active["is_persistent"] is True
        rows = kb_active["keyboard"]
        assert rows[0][0]["text"] == "📊 Status"
        assert rows[0][1]["text"] == "📋 Pending Queue"
        assert rows[1][0]["text"] == "⏸️ Pause"
        assert rows[1][1]["text"] == "📈 Stats"
        assert rows[2][0]["text"] == "🏠 Home Menu"
        assert rows[2][1]["text"] == "❓ Help"

        kb_paused = build_docked_reply_keyboard(is_paused=True)
        rows_paused = kb_paused["keyboard"]
        assert rows_paused[1][0]["text"] == "▶️ Resume"

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

    def test_build_suggestion_message_reaction_type(self) -> None:
        rx_item = PendingAction(
            item_id="rx_999",
            action_type="approve_reaction",
            reaction_type="insightful",
            draft_text="Reaction: Insightful",
            confidence=0.85,
            reasoning="Insightful technical perspective.",
        )
        msg = build_suggestion_message(rx_item)
        assert "👍 Reaction (Insightful)" in msg
        assert "<b>Proposed Reaction:</b> Insightful" in msg
        assert "Metrics:" not in msg
        assert "rx_999" in msg

    def test_build_outcome_messages(self, sample_pending_action: PendingAction) -> None:
        # Success
        success_msg = build_outcome_message(sample_pending_action, "executed_success")
        assert "✅ Successfully Commented on LinkedIn!" in success_msg
        assert "item_test_12345" in success_msg

        # Reaction Success
        rx_item = PendingAction(
            item_id="rx_888",
            action_type="approve_reaction",
            reaction_type="celebrate",
            draft_text="Reaction: Celebrate",
            confidence=0.9,
        )
        rx_success_msg = build_outcome_message(rx_item, "executed_success")
        assert "✅ Successfully Reacted (Celebrate) on LinkedIn!" in rx_success_msg
        assert "rx_888" in rx_success_msg

        # Success with verification link
        proof_msg = build_outcome_message(
            sample_pending_action,
            "executed_success",
            verification_url="https://linkedin.com/feed/update/123/?commentUrn=456",
        )
        assert "View Your Comment on LinkedIn ↗" in proof_msg
        assert "commentUrn=456" in proof_msg

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

    def test_build_home_keyboard(self) -> None:
        kb_normal = build_home_keyboard(is_tripped=False, pending_count=2, is_paused=False)
        assert len(kb_normal["inline_keyboard"]) == 3
        # Row 1: Pending & Status
        assert "Pending (2)" in kb_normal["inline_keyboard"][0][0]["text"]
        assert kb_normal["inline_keyboard"][0][0]["callback_data"] == "rev:list"
        assert kb_normal["inline_keyboard"][0][1]["text"] == "📊 Status"
        assert kb_normal["inline_keyboard"][0][1]["callback_data"] == "refresh:status"
        # Row 2: Stats & Pause
        assert kb_normal["inline_keyboard"][1][0]["text"] == "📈 Stats"
        assert kb_normal["inline_keyboard"][1][1]["text"] == "⏸️ Pause Agent"
        assert kb_normal["inline_keyboard"][1][1]["callback_data"] == "home:pause"
        # Row 3: Refresh & Close
        assert kb_normal["inline_keyboard"][2][0]["text"] == "🔄 Refresh Hub"
        assert kb_normal["inline_keyboard"][2][1]["text"] == "❌ Close Menu"

        # Tripped case
        kb_tripped = build_home_keyboard(is_tripped=True, pending_count=0, is_paused=True)
        assert len(kb_tripped["inline_keyboard"]) == 4
        assert kb_tripped["inline_keyboard"][0][0]["text"] == "🔄 Reset Circuit Breaker"
        assert kb_tripped["inline_keyboard"][2][1]["text"] == "▶️ Resume Agent"
        assert kb_tripped["inline_keyboard"][2][1]["callback_data"] == "home:resume"

    def test_build_stats_keyboard(self) -> None:
        kb = build_stats_keyboard()
        assert len(kb["inline_keyboard"]) == 1
        assert kb["inline_keyboard"][0][0]["text"] == "🔄 Refresh Stats"
        assert kb["inline_keyboard"][0][0]["callback_data"] == "refresh:stats"
        assert kb["inline_keyboard"][0][1]["text"] == "🏠 Home Menu"
        assert kb["inline_keyboard"][0][1]["callback_data"] == "home:menu"

    def test_build_help_keyboard(self) -> None:
        kb = build_help_keyboard()
        assert len(kb["inline_keyboard"]) == 1
        assert kb["inline_keyboard"][0][0]["text"] == "🏠 Home Menu"
        assert kb["inline_keyboard"][0][0]["callback_data"] == "home:menu"
        assert kb["inline_keyboard"][0][1]["text"] == "📊 Status Report"
        assert kb["inline_keyboard"][0][1]["callback_data"] == "refresh:status"

    def test_format_home_hub(self, mock_settings: Settings) -> None:
        from agent.models import DailyCounters

        counters = DailyCounters(date="2026-10-07", comments_executed=3, posts_executed=1, suggestions_sent=5)
        text = format_home_hub(
            system_state="🟢 <b>Operational</b>",
            cb_status="🟢 <b>Normal</b>",
            pending_count=4,
            counters=counters,
            settings=mock_settings,
        )
        assert "Command & Control Hub" in text
        assert "Operational" in text
        assert "4</b> action(s) awaiting review" in text
        assert "3 / 5" in text
        assert "1 / 1" in text

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
    async def test_set_my_commands_success(self, mock_settings: Settings) -> None:
        captured_payload: dict[str, Any] = {}

        def handler(request: httpx.Request) -> httpx.Response:
            nonlocal captured_payload
            assert request.url.path.endswith("/setMyCommands")
            captured_payload = json.loads(request.content.decode("utf-8"))
            return httpx.Response(200, json={"ok": True, "result": True})

        transport = httpx.MockTransport(handler)
        async with httpx.AsyncClient(transport=transport) as http_client:
            client = TelegramClient(mock_settings, http_client=http_client)
            res = await client.set_my_commands()
            assert res is True
            assert "commands" in captured_payload
            cmd_names = [c["command"] for c in captured_payload["commands"]]
            assert "status" in cmd_names
            assert "pending" in cmd_names
            assert "pause" in cmd_names
            assert "resume" in cmd_names
            assert "post" in cmd_names

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


class TestTelegramCallbacks:
    """Test suite for interactive Telegram callback handlers and router."""

    @pytest.mark.asyncio
    async def test_execute_reject_prompt_callback(
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
            handled = await execute_reject_prompt_callback(
                state_store=test_state_store,
                telegram=telegram,
                item_id=sample_pending_action.item_id,
                callback_query_id="query_rej_prompt",
                chat_id=987654321,
                message_id=42,
            )

            assert handled is True
            # Pending item must still exist in state store
            assert test_state_store.read_pending(sample_pending_action.item_id) is not None

            # Must have answered query and edited reply markup
            assert len(recorded_requests) == 2
            answer_req = next(r for r in recorded_requests if "answerCallbackQuery" in r["path"])
            assert answer_req["payload"]["callback_query_id"] == "query_rej_prompt"
            assert "Confirm rejection" in answer_req["payload"]["text"]

            edit_req = next(r for r in recorded_requests if "editMessageReplyMarkup" in r["path"])
            assert edit_req["payload"]["chat_id"] == 987654321
            assert edit_req["payload"]["message_id"] == 42
            buttons = edit_req["payload"]["reply_markup"]["inline_keyboard"][0]
            assert buttons[0]["callback_data"] == f"cf_rej:{sample_pending_action.item_id}"
            assert buttons[1]["callback_data"] == f"cx_rej:{sample_pending_action.item_id}"

    @pytest.mark.asyncio
    async def test_execute_reject_cancel_callback(
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
            handled = await execute_reject_cancel_callback(
                state_store=test_state_store,
                telegram=telegram,
                item_id=sample_pending_action.item_id,
                callback_query_id="query_rej_cx",
                chat_id=987654321,
                message_id=42,
            )

            assert handled is True
            # Pending item must remain intact
            assert test_state_store.read_pending(sample_pending_action.item_id) is not None

            assert len(recorded_requests) == 2
            answer_req = next(r for r in recorded_requests if "answerCallbackQuery" in r["path"])
            assert "Rejection cancelled" in answer_req["payload"]["text"]

            edit_req = next(r for r in recorded_requests if "editMessageReplyMarkup" in r["path"])
            assert edit_req["payload"]["chat_id"] == 987654321
            row1 = edit_req["payload"]["reply_markup"]["inline_keyboard"][0]
            assert row1[0]["callback_data"] == f"ac:{sample_pending_action.item_id}"
            assert row1[1]["callback_data"] == f"ask_rej:{sample_pending_action.item_id}"

    @pytest.mark.asyncio
    async def test_execute_reject_confirm_callback(
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
            handled = await execute_reject_confirm_callback(
                state_store=test_state_store,
                telegram=telegram,
                item_id=sample_pending_action.item_id,
                callback_query_id="query_rej_cf",
                chat_id=987654321,
                message_id=42,
            )

            assert handled is True
            # Pending item must be deleted
            assert test_state_store.read_pending(sample_pending_action.item_id) is None

            # History entry must be appended with final_status="rejected"
            history = test_state_store.read_history()
            assert any(
                h.item_id == sample_pending_action.item_id and h.final_status == "rejected"
                for h in history
            )

            assert len(recorded_requests) == 2
            answer_req = next(r for r in recorded_requests if "answerCallbackQuery" in r["path"])
            assert "rejected" in answer_req["payload"]["text"].lower()

            edit_req = next(r for r in recorded_requests if "editMessageText" in r["path"])
            assert edit_req["payload"]["chat_id"] == 987654321
            assert edit_req["payload"]["message_id"] == 42
            assert "Optional feedback" in edit_req["payload"]["text"]
            # Feedback keyboard buttons present
            kb = edit_req["payload"]["reply_markup"]["inline_keyboard"]
            assert kb[0][0]["callback_data"] == f"fb:generic:{sample_pending_action.item_id}"

    @pytest.mark.asyncio
    async def test_execute_feedback_callback_with_reason(
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
            handled = await execute_feedback_callback(
                state_store=test_state_store,
                telegram=telegram,
                item_id="item_fb_01",
                reason="boring",
                callback_query_id="query_fb_01",
                chat_id=987654321,
                message_id=42,
            )

            assert handled is True
            feedbacks = test_state_store.load_rejection_feedbacks()
            assert any(f.get("item_id") == "item_fb_01" and f.get("reason") == "boring" for f in feedbacks)

            assert len(recorded_requests) == 2
            answer_req = next(r for r in recorded_requests if "answerCallbackQuery" in r["path"])
            assert "Feedback saved" in answer_req["payload"]["text"]

            edit_req = next(r for r in recorded_requests if "editMessageText" in r["path"])
            assert "Suggestion rejected by operator" in edit_req["payload"]["text"]
            assert "Feedback: boring" in edit_req["payload"]["text"]
            assert edit_req["payload"]["reply_markup"]["inline_keyboard"] == []

    @pytest.mark.asyncio
    async def test_execute_feedback_callback_skip(
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
            handled = await execute_feedback_callback(
                state_store=test_state_store,
                telegram=telegram,
                item_id="item_fb_skip",
                reason="skip",
                callback_query_id="query_fb_skip",
                chat_id=987654321,
                message_id=42,
            )

            assert handled is True
            feedbacks = test_state_store.load_rejection_feedbacks()
            assert not any(f.get("item_id") == "item_fb_skip" for f in feedbacks)

            assert len(recorded_requests) == 2
            answer_req = next(r for r in recorded_requests if "answerCallbackQuery" in r["path"])
            assert "dismissed" in answer_req["payload"]["text"].lower()

            edit_req = next(r for r in recorded_requests if "editMessageText" in r["path"])
            assert "Suggestion rejected by operator" in edit_req["payload"]["text"]
            assert "Feedback:" not in edit_req["payload"]["text"]
            assert edit_req["payload"]["reply_markup"]["inline_keyboard"] == []

    @pytest.mark.asyncio
    async def test_execute_tone_menu_and_back_callbacks(
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

            # 1. Tap tone menu (reg)
            handled_menu = await execute_tone_menu_callback(
                state_store=test_state_store,
                telegram=telegram,
                item_id=sample_pending_action.item_id,
                callback_query_id="query_menu",
                chat_id=987654321,
                message_id=42,
            )
            assert handled_menu is True
            edit_req = next(r for r in recorded_requests if "editMessageReplyMarkup" in r["path"])
            kb = edit_req["payload"]["reply_markup"]["inline_keyboard"]
            assert kb[0][0]["callback_data"] == f"tone:technical:{sample_pending_action.item_id}"
            assert kb[2][0]["callback_data"] == f"back:{sample_pending_action.item_id}"

            recorded_requests.clear()

            # 2. Tap back to review
            handled_back = await execute_back_callback(
                state_store=test_state_store,
                telegram=telegram,
                item_id=sample_pending_action.item_id,
                callback_query_id="query_back",
                chat_id=987654321,
                message_id=42,
            )
            assert handled_back is True
            edit_req2 = next(r for r in recorded_requests if "editMessageReplyMarkup" in r["path"])
            kb2 = edit_req2["payload"]["reply_markup"]["inline_keyboard"]
            assert kb2[0][0]["callback_data"] == f"ac:{sample_pending_action.item_id}"
            assert kb2[0][1]["callback_data"] == f"ask_rej:{sample_pending_action.item_id}"

    @pytest.mark.asyncio
    async def test_execute_tone_select_callback(
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

        class MockLLMService:
            async def rewrite_draft(self, draft_text: str, tone: str, post_excerpt: str = "") -> str:
                return f"Rewritten in {tone} style: {draft_text[:30]}"

        transport = httpx.MockTransport(handler)
        async with httpx.AsyncClient(transport=transport) as http_client:
            telegram = TelegramClient(mock_settings, http_client=http_client)
            handled = await execute_tone_select_callback(
                state_store=test_state_store,
                telegram=telegram,
                item_id=sample_pending_action.item_id,
                tone="contrarian",
                callback_query_id="query_tone_sel",
                chat_id=987654321,
                message_id=42,
                llm_service=MockLLMService(),
            )

            assert handled is True
            # Check draft was updated in state store
            updated = test_state_store.read_pending(sample_pending_action.item_id)
            assert updated is not None
            assert updated.draft_text.startswith("Rewritten in contrarian style:")

            # Check message was edited
            edit_req = next(r for r in recorded_requests if "editMessageText" in r["path"])
            assert "Rewritten in contrarian style:" in edit_req["payload"]["text"]
            # Review buttons restored (with LinkedIn URL button on top)
            kb = edit_req["payload"]["reply_markup"]["inline_keyboard"]
            assert kb[0][0]["url"] == sample_pending_action.post_url
            assert kb[1][0]["callback_data"] == f"ac:{sample_pending_action.item_id}"

    @pytest.mark.asyncio
    async def test_execute_callback_query_router(
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

            # Unauthorized sender -> dropped
            unauth_cb = {
                "id": "q_unauth",
                "from": {"id": 111222333},
                "data": f"ask_rej:{sample_pending_action.item_id}",
                "message": {"chat": {"id": 111222333}, "message_id": 10},
            }
            res_unauth = await execute_callback_query(
                settings=mock_settings,
                state_store=test_state_store,
                telegram=telegram,
                callback_query=unauth_cb,
            )
            assert res_unauth is False
            assert len(recorded_requests) == 0

            # Valid sender routes ask_rej
            valid_cb = {
                "id": "q_auth",
                "from": {"id": 987654321},
                "data": f"ask_rej:{sample_pending_action.item_id}",
                "message": {"chat": {"id": 987654321}, "message_id": 10},
            }
            res_valid = await execute_callback_query(
                settings=mock_settings,
                state_store=test_state_store,
                telegram=telegram,
                callback_query=valid_cb,
            )
            assert res_valid is True
            assert len(recorded_requests) == 2

    @pytest.mark.asyncio
    async def test_execute_cancel_edit_callback(
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
            handled = await execute_cancel_edit_callback(
                state_store=test_state_store,
                telegram=telegram,
                item_id=sample_pending_action.item_id,
                callback_query_id="q_cx_ed",
                chat_id=987654321,
                message_id=42,
            )
            assert handled is True
            assert len(recorded_requests) == 2
            answer_req = next(r for r in recorded_requests if "answerCallbackQuery" in r["path"])
            assert "cancelled" in answer_req["payload"]["text"].lower()
            edit_req = next(r for r in recorded_requests if "editMessageReplyMarkup" in r["path"])
            kb = edit_req["payload"]["reply_markup"]["inline_keyboard"]
            assert kb[0][0]["url"] == sample_pending_action.post_url
            assert kb[1][0]["callback_data"] == f"ac:{sample_pending_action.item_id}"

    @pytest.mark.asyncio
    async def test_execute_review_callback(
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
            return httpx.Response(200, json={"ok": True, "result": {"message_id": 555}})

        transport = httpx.MockTransport(handler)
        async with httpx.AsyncClient(transport=transport) as http_client:
            telegram = TelegramClient(mock_settings, http_client=http_client)
            handled = await execute_review_callback(
                state_store=test_state_store,
                telegram=telegram,
                item_id=sample_pending_action.item_id,
                callback_query_id="q_rev",
                chat_id=987654321,
            )
            assert handled is True
            # Answers callback and delivers suggestion card
            assert any("answerCallbackQuery" in r["path"] for r in recorded_requests)
            assert any("sendMessage" in r["path"] for r in recorded_requests)

    @pytest.mark.asyncio
    async def test_execute_reset_circuit_breaker_callback(
        self,
        mock_settings: Settings,
        test_state_store: GitStateStore,
    ) -> None:
        test_state_store.save_incident({"reason": "Test trip", "tripped_at": "2026-10-07T00:00:00Z"})
        recorded_requests: list[dict[str, Any]] = []

        def handler(request: httpx.Request) -> httpx.Response:
            data = json.loads(request.content.decode("utf-8"))
            recorded_requests.append({"path": request.url.path, "payload": data})
            return httpx.Response(200, json={"ok": True, "result": True})

        transport = httpx.MockTransport(handler)
        async with httpx.AsyncClient(transport=transport) as http_client:
            telegram = TelegramClient(mock_settings, http_client=http_client)
            handled = await execute_reset_circuit_breaker_callback(
                state_store=test_state_store,
                telegram=telegram,
                callback_query_id="q_reset_cb",
                chat_id=987654321,
                message_id=42,
            )
            assert handled is True
            assert test_state_store.read_incident() is None
            assert len(recorded_requests) == 2
            answer_req = next(r for r in recorded_requests if "answerCallbackQuery" in r["path"])
            assert "Circuit breaker reset" in answer_req["payload"]["text"]

    @pytest.mark.asyncio
    async def test_execute_noop_callback(
        self,
        mock_settings: Settings,
    ) -> None:
        recorded_requests: list[dict[str, Any]] = []

        def handler(request: httpx.Request) -> httpx.Response:
            data = json.loads(request.content.decode("utf-8"))
            recorded_requests.append({"path": request.url.path, "payload": data})
            return httpx.Response(200, json={"ok": True, "result": True})

        transport = httpx.MockTransport(handler)
        async with httpx.AsyncClient(transport=transport) as http_client:
            telegram = TelegramClient(mock_settings, http_client=http_client)
            handled = await execute_noop_callback(
                telegram=telegram,
                callback_query_id="q_noop",
            )
            assert handled is True
            assert len(recorded_requests) == 1
            assert "AI draft generation" in recorded_requests[0]["payload"]["text"]

    @pytest.mark.asyncio
    async def test_execute_home_callback(
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
            handled = await execute_home_callback(
                state_store=test_state_store,
                telegram=telegram,
                settings=mock_settings,
                chat_id=987654321,
                message_id=42,
                callback_query_id="q_home",
                action_arg="menu",
            )
            assert handled is True
            assert any("answerCallbackQuery" in r["path"] for r in recorded_requests)
            edit_req = next(r for r in recorded_requests if "editMessageText" in r["path"])
            assert "Command & Control Hub" in edit_req["payload"]["text"]

            # Test pause action_arg
            handled_pause = await execute_home_callback(
                state_store=test_state_store,
                telegram=telegram,
                settings=mock_settings,
                chat_id=987654321,
                message_id=42,
                callback_query_id="q_pause",
                action_arg="pause",
            )
            assert handled_pause is True
            assert test_state_store.is_paused() is True

    @pytest.mark.asyncio
    async def test_execute_close_callback(
        self,
        mock_settings: Settings,
    ) -> None:
        recorded_requests: list[dict[str, Any]] = []

        def handler(request: httpx.Request) -> httpx.Response:
            data = json.loads(request.content.decode("utf-8"))
            recorded_requests.append({"path": request.url.path, "payload": data})
            return httpx.Response(200, json={"ok": True, "result": True})

        transport = httpx.MockTransport(handler)
        async with httpx.AsyncClient(transport=transport) as http_client:
            telegram = TelegramClient(mock_settings, http_client=http_client)
            handled = await execute_close_callback(
                telegram=telegram,
                chat_id=987654321,
                message_id=42,
                callback_query_id="q_close",
            )
            assert handled is True
            assert any("answerCallbackQuery" in r["path"] for r in recorded_requests)
            assert any("deleteMessage" in r["path"] for r in recorded_requests)

    @pytest.mark.asyncio
    async def test_execute_refresh_callback(
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
            handled = await execute_refresh_callback(
                view="status",
                settings=mock_settings,
                state_store=test_state_store,
                telegram=telegram,
                chat_id=987654321,
                message_id=42,
                callback_query_id="q_ref_stat",
            )
            assert handled is True
            assert any("answerCallbackQuery" in r["path"] for r in recorded_requests)
            edit_req = next(r for r in recorded_requests if "editMessageText" in r["path"])
            assert "Agent Status Report" in edit_req["payload"]["text"]


class TestTelegramPhotoSuggestions:
    """Tests for post media photo previews and fallback behavior."""

    @pytest.mark.asyncio
    async def test_send_photo_success(self, mock_settings: Settings) -> None:
        sent_requests: list[dict[str, Any]] = []

        def handler(request: httpx.Request) -> httpx.Response:
            data = json.loads(request.content.decode("utf-8"))
            sent_requests.append({"path": request.url.path, "payload": data})
            return httpx.Response(200, json={"ok": True, "result": {"message_id": 9991}})

        transport = httpx.MockTransport(handler)
        async with httpx.AsyncClient(transport=transport) as http_client:
            client = TelegramClient(mock_settings, http_client=http_client)
            msg_id = await client.send_photo(
                chat_id=987654321,
                photo_url="https://media.licdn.com/image.jpg",
                caption="<b>Photo caption</b>",
            )
            assert msg_id == 9991
            assert len(sent_requests) == 1
            assert "sendPhoto" in sent_requests[0]["path"]
            assert sent_requests[0]["payload"]["photo"] == "https://media.licdn.com/image.jpg"
            assert sent_requests[0]["payload"]["caption"] == "<b>Photo caption</b>"

    @pytest.mark.asyncio
    async def test_send_suggestion_with_post_image_calls_send_photo(
        self, mock_settings: Settings, sample_pending_action: PendingAction
    ) -> None:
        action_with_image = sample_pending_action.model_copy(
            update={"post_image_url": "https://media.licdn.com/infographic.png"}
        )
        sent_requests: list[dict[str, Any]] = []

        def handler(request: httpx.Request) -> httpx.Response:
            data = json.loads(request.content.decode("utf-8"))
            sent_requests.append({"path": request.url.path, "payload": data})
            return httpx.Response(200, json={"ok": True, "result": {"message_id": 9992}})

        transport = httpx.MockTransport(handler)
        async with httpx.AsyncClient(transport=transport) as http_client:
            client = TelegramClient(mock_settings, http_client=http_client)
            msg_id = await client.send_suggestion(action_with_image)
            assert msg_id == 9992
            assert len(sent_requests) == 1
            assert "sendPhoto" in sent_requests[0]["path"]
            assert (
                sent_requests[0]["payload"]["photo"]
                == "https://media.licdn.com/infographic.png"
            )

    @pytest.mark.asyncio
    async def test_send_suggestion_with_post_image_fallback_to_send_message(
        self, mock_settings: Settings, sample_pending_action: PendingAction
    ) -> None:
        action_with_image = sample_pending_action.model_copy(
            update={"post_image_url": "https://media.licdn.com/broken.png"}
        )
        sent_requests: list[dict[str, Any]] = []

        def handler(request: httpx.Request) -> httpx.Response:
            data = json.loads(request.content.decode("utf-8"))
            sent_requests.append({"path": request.url.path, "payload": data})
            if "sendPhoto" in request.url.path:
                return httpx.Response(400, json={"ok": False, "description": "PHOTO_INVALID"})
            return httpx.Response(200, json={"ok": True, "result": {"message_id": 9993}})

        transport = httpx.MockTransport(handler)
        async with httpx.AsyncClient(transport=transport) as http_client:
            client = TelegramClient(mock_settings, http_client=http_client)
            msg_id = await client.send_suggestion(action_with_image)
            assert msg_id == 9993
            assert len(sent_requests) == 2
            assert "sendPhoto" in sent_requests[0]["path"]
            assert "sendMessage" in sent_requests[1]["path"]

