"""Unit tests for Connection Request HITL Outreach Queue, Schemas, and Safety Caps."""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from pydantic import SecretStr, ValidationError

from agent.browser.executor import ActionExecutor
from agent.config import Settings
from agent.errors import (
    BotDetectionError,
    ExecutionError,
    SubmissionVerificationError,
)
from agent.models import ConnectionRequestAction, DailyCounters, ExecutionResult
from agent.safety.rate_limiter import DailyCapEnforcer, can_send_connection


@pytest.fixture
def test_settings() -> Settings:
    return Settings(
        nvidia_nim_api_key=SecretStr("nvapi-test"),
        nim_model_primary="primary-model",
        nim_model_fallback="fallback-model",
        telegram_bot_token=SecretStr("123:token"),
        telegram_authorized_chat_id=12345,
        user_focus_areas=["AI", "Distributed Systems"],
        max_connections_per_day=10,
        dry_run=True,
    )


class TestConnectionRequestSchemas:
    """Tests for ConnectionRequestAction and DailyCounters schema validation."""

    def test_connection_request_action_defaults(self) -> None:
        action = ConnectionRequestAction(
            id="conn-123",
            profile_url="https://linkedin.com/in/test-profile",
            target_name="Jane Doe",
        )
        assert action.id == "conn-123"
        assert action.profile_url == "https://linkedin.com/in/test-profile"
        assert action.target_name == "Jane Doe"
        assert action.target_headline == ""
        assert action.mutual_context == ""
        assert action.note_text == ""
        assert action.status == "pending"
        assert isinstance(action.created_at, datetime)
        assert action.approved_at is None

    def test_connection_request_action_valid_300_char_note(self) -> None:
        note_300 = "X" * 300
        action = ConnectionRequestAction(
            id="conn-124",
            profile_url="https://linkedin.com/in/test-profile-2",
            target_name="John Smith",
            target_headline="Principal Architect",
            mutual_context="Commented on John's architecture post",
            note_text=note_300,
            status="approved",
            approved_at=datetime.now(UTC),
        )
        assert len(action.note_text) == 300
        assert action.status == "approved"
        assert action.approved_at is not None

    def test_connection_request_action_rejects_exceeding_300_chars(self) -> None:
        note_301 = "X" * 301
        with pytest.raises(ValidationError):
            ConnectionRequestAction(
                id="conn-125",
                profile_url="https://linkedin.com/in/test-profile-3",
                target_name="Alice",
                note_text=note_301,
            )

    def test_connection_request_action_invalid_status_raises(self) -> None:
        with pytest.raises(ValidationError):
            ConnectionRequestAction(
                id="conn-126",
                profile_url="https://linkedin.com/in/test-profile-4",
                target_name="Bob",
                status="invalid_status",  # type: ignore[arg-type]
            )

    def test_daily_counters_connections_sent(self) -> None:
        counters = DailyCounters(date="2026-09-30", connections_sent=5)
        assert counters.connections_sent == 5

        # ge=0 validation
        with pytest.raises(ValidationError):
            DailyCounters(date="2026-09-30", connections_sent=-1)


class TestConnectionSafetyAndRateLimits:
    """Tests for daily connection limits and enforcer."""

    def test_can_send_connection_function(self) -> None:
        counters = DailyCounters(date="2026-09-30", connections_sent=9)
        assert can_send_connection(counters, max_daily=10) is True

        counters_capped = DailyCounters(date="2026-09-30", connections_sent=10)
        assert can_send_connection(counters_capped, max_daily=10) is False

        counters_exceeded = DailyCounters(date="2026-09-30", connections_sent=12)
        assert can_send_connection(counters_exceeded, max_daily=10) is False

    def test_daily_cap_enforcer_connection(self, test_settings: Settings) -> None:
        enforcer = DailyCapEnforcer(test_settings)
        counters = DailyCounters(date="2026-09-30", connections_sent=4)

        allowed, reason = enforcer.can_execute_connection(counters)
        assert allowed is True
        assert reason is None

        # At cap
        counters_capped = DailyCounters(date="2026-09-30", connections_sent=10)
        allowed, reason = enforcer.can_execute_connection(counters_capped)
        assert allowed is False
        assert reason is not None
        assert "Daily connection cap reached (10/10)" in reason

    def test_settings_max_connections_config(self) -> None:
        custom_settings = Settings(
            nvidia_nim_api_key=SecretStr("nvapi-test"),
            telegram_bot_token=SecretStr("token"),
            telegram_authorized_chat_id=123,
            max_connections_per_day=25,
        )
        assert custom_settings.max_connections_per_day == 25


class TestActionExecutorConnectionInvitation:
    """Tests for ActionExecutor.send_connection_request browser automation."""

    @pytest.mark.asyncio
    async def test_send_connection_request_dry_run(self, test_settings: Settings) -> None:
        page = MagicMock()
        page.url = "https://www.linkedin.com/in/alice-dist/"
        page.screenshot = AsyncMock()

        executor = ActionExecutor(page, test_settings)
        result = await executor.send_connection_request(
            profile_url="https://www.linkedin.com/in/alice-dist/",
            note_text="Hi Alice, loved your distributed cache article!",
            item_id="conn_dry_01",
            dry_run=True,
        )

        assert isinstance(result, ExecutionResult)
        assert result.success is True
        assert result.action_type == "send_connection"
        assert result.item_id == "conn_dry_01"
        assert result.post_url == "https://www.linkedin.com/in/alice-dist/"
        assert result.comment_text == "Hi Alice, loved your distributed cache article!"

    @pytest.mark.asyncio
    async def test_send_connection_request_note_exceeding_300_raises(
        self, test_settings: Settings
    ) -> None:
        page = MagicMock()
        page.url = "https://www.linkedin.com/in/alice-dist/"

        executor = ActionExecutor(page, test_settings)
        with pytest.raises(ExecutionError, match="exceeds 300 characters"):
            await executor.send_connection_request(
                profile_url="https://www.linkedin.com/in/alice-dist/",
                note_text="Z" * 301,
            )

    @pytest.mark.asyncio
    async def test_send_connection_request_challenge_raises_bot_detection(
        self, test_settings: Settings
    ) -> None:
        page = MagicMock()
        page.url = "https://www.linkedin.com/checkpoint/challenge"

        executor = ActionExecutor(page, test_settings)
        with patch("agent.browser.stealth.detect_challenge_page", return_value=True):
            with pytest.raises(BotDetectionError):
                await executor.send_connection_request(
                    profile_url="https://www.linkedin.com/in/bob/",
                    dry_run=False,
                )

    @pytest.mark.asyncio
    async def test_send_connection_request_live_with_note(self, test_settings: Settings) -> None:
        page = MagicMock()
        page.url = "https://www.linkedin.com/in/marcus-ai/"
        page.screenshot = AsyncMock()
        page.goto = AsyncMock()

        # Connect button
        connect_btn = MagicMock()
        connect_btn.count = AsyncMock(return_value=1)
        connect_btn.is_visible = AsyncMock(return_value=True)
        connect_btn.first = connect_btn

        # Add a note button
        add_note_btn = MagicMock()
        add_note_btn.count = AsyncMock(return_value=1)
        add_note_btn.first = add_note_btn

        # Textarea
        textarea = MagicMock()
        textarea.count = AsyncMock(return_value=1)
        textarea.first = textarea

        # Send button
        send_btn = MagicMock()
        send_btn.count = AsyncMock(return_value=1)
        send_btn.first = send_btn

        def locator_side_effect(selector: str) -> MagicMock:
            loc = MagicMock()
            if "Connect" in selector:
                return connect_btn
            if "Add a note" in selector:
                return add_note_btn
            if "textarea" in selector or "message" in selector:
                return textarea
            if "Send" in selector:
                return send_btn
            if "Pending" in selector:
                loc.count = AsyncMock(return_value=1)
                loc.first = loc
                return loc
            loc.count = AsyncMock(return_value=0)
            loc.first = loc
            return loc

        page.locator = MagicMock(side_effect=locator_side_effect)

        executor = ActionExecutor(page, test_settings)
        executor.biometrics.click_element = AsyncMock()  # type: ignore[method-assign]
        executor.biometrics.type_text = AsyncMock()  # type: ignore[method-assign]
        executor._verify_connection_sent = AsyncMock(return_value=True)  # type: ignore[method-assign]
        executor._refresh_and_persist_session = AsyncMock()  # type: ignore[method-assign]

        result = await executor.send_connection_request(
            profile_url="https://www.linkedin.com/in/marcus-ai/",
            note_text="Hi Marcus, let's connect!",
            item_id="conn_live_01",
            dry_run=False,
        )

        assert result.success is True
        assert result.action_type == "send_connection"
        assert result.post_url == "https://www.linkedin.com/in/marcus-ai/"
        executor.biometrics.click_element.assert_any_call(connect_btn)
        executor.biometrics.type_text.assert_called_once_with(textarea, "Hi Marcus, let's connect!")
        executor.biometrics.click_element.assert_any_call(send_btn)

    @pytest.mark.asyncio
    async def test_send_connection_request_via_more_actions_dropdown(
        self, test_settings: Settings
    ) -> None:
        page = MagicMock()
        page.url = "https://www.linkedin.com/in/sarah-langchain/"
        page.screenshot = AsyncMock()
        page.goto = AsyncMock()

        # Direct connect button is missing
        direct_connect = MagicMock()
        direct_connect.count = AsyncMock(return_value=0)
        direct_connect.first = direct_connect

        # More actions button
        more_btn = MagicMock()
        more_btn.count = AsyncMock(return_value=1)
        more_btn.first = more_btn

        # Dropdown connect button
        dropdown_connect = MagicMock()
        dropdown_connect.count = AsyncMock(return_value=1)
        dropdown_connect.first = dropdown_connect

        # Send button
        send_btn = MagicMock()
        send_btn.count = AsyncMock(return_value=1)
        send_btn.first = send_btn

        def locator_side_effect(selector: str) -> MagicMock:
            loc = MagicMock()
            if "button:has-text('Connect')" in selector:
                return direct_connect
            if "More actions" in selector or "button:has-text('More')" in selector:
                return more_btn
            if "div[role='button']:has-text('Connect')" in selector:
                return dropdown_connect
            if "Send" in selector:
                return send_btn
            if "Pending" in selector:
                loc.count = AsyncMock(return_value=1)
                loc.first = loc
                return loc
            loc.count = AsyncMock(return_value=0)
            loc.first = loc
            return loc

        page.locator = MagicMock(side_effect=locator_side_effect)

        executor = ActionExecutor(page, test_settings)
        executor.biometrics.click_element = AsyncMock()  # type: ignore[method-assign]
        executor._verify_connection_sent = AsyncMock(return_value=True)  # type: ignore[method-assign]
        executor._refresh_and_persist_session = AsyncMock()  # type: ignore[method-assign]

        result = await executor.send_connection_request(
            profile_url="https://www.linkedin.com/in/sarah-langchain/",
            note_text=None,
            item_id="conn_more_01",
            dry_run=False,
        )

        assert result.success is True
        executor.biometrics.click_element.assert_any_call(more_btn)
        executor.biometrics.click_element.assert_any_call(dropdown_connect)
        executor.biometrics.click_element.assert_any_call(send_btn)

    async def test_verify_connection_sent_signal_pending_button(
        self, test_settings: Settings
    ) -> None:
        page = AsyncMock()
        empty_loc = AsyncMock()
        empty_loc.count = AsyncMock(return_value=0)
        pending_loc = AsyncMock()
        pending_loc.count = AsyncMock(return_value=1)

        def locator_se(sel: str) -> AsyncMock:
            if "Pending" in sel:
                return pending_loc
            return empty_loc

        page.locator = MagicMock(side_effect=locator_se)
        executor = ActionExecutor(page, test_settings)
        verified = await executor._verify_connection_sent(item_id="item1", timeout=0.5)
        assert verified is True

    async def test_verify_connection_sent_signal_toast(self, test_settings: Settings) -> None:
        page = AsyncMock()
        empty_loc = AsyncMock()
        empty_loc.count = AsyncMock(return_value=0)
        toast_loc = AsyncMock()
        toast_loc.count = AsyncMock(return_value=1)

        def locator_se(sel: str) -> AsyncMock:
            if "artdeco-toast-item--success" in sel:
                return toast_loc
            return empty_loc

        page.locator = MagicMock(side_effect=locator_se)
        executor = ActionExecutor(page, test_settings)
        verified = await executor._verify_connection_sent(item_id="item1", timeout=0.5)
        assert verified is True

    async def test_verify_connection_sent_timeout_raises(self, test_settings: Settings) -> None:
        page = AsyncMock()
        empty_loc = AsyncMock()
        empty_loc.count = AsyncMock(return_value=0)
        page.locator = MagicMock(return_value=empty_loc)
        executor = ActionExecutor(page, test_settings)
        executor._capture_screenshot = AsyncMock(return_value="/tmp/screenshot.png")  # type: ignore[method-assign]
        executor._capture_telemetry = AsyncMock()  # type: ignore[method-assign]

        with pytest.raises(SubmissionVerificationError) as exc_info:
            await executor._verify_connection_sent(
                item_id="item1", timeout=0.05, poll_interval=0.01
            )
        assert "could not be verified" in str(exc_info.value)
