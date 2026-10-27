"""Unit tests for LLM health monitoring, multi-channel alerting, and debouncing."""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from pydantic import SecretStr

from agent.config import Settings
from agent.doctor.checks import check_llm_provider
from agent.llm.service import LLMService
from agent.models.actions import PendingAction
from agent.models.llm import CommentDraft
from agent.orchestration.llm_alert import (
    HEALTH_RECORD_KEY,
    check_and_notify_llm_health,
    is_alert_debounced,
)
from agent.telegram.client import TelegramClient
from agent.telegram.keyboards import format_suggestion_card


@pytest.fixture
def test_settings() -> Settings:
    return Settings(
        nvidia_nim_api_key="nvapi-test-key",
        nim_model_primary="nvidia/nemotron-3-ultra-550b-a55b",
        nim_model_fallback="openai/gpt-oss-20b",
        telegram_bot_token="123456:MOCK_TOKEN",
        telegram_authorized_chat_id=123456789,
        worker_url="https://test.relay.workers.dev",
        desktop_api_secret=SecretStr("test-desktop-secret-1234567890"),
    )


class TestAlertDebounce:
    """Test debounce cooldown logic."""

    def test_no_previous_alert(self) -> None:
        assert is_alert_debounced(None, cooldown_hours=12.0) is False
        assert is_alert_debounced("", cooldown_hours=12.0) is False

    def test_within_cooldown_window(self) -> None:
        now = datetime.now(UTC)
        two_hours_ago = (now - timedelta(hours=2)).isoformat()
        assert is_alert_debounced(two_hours_ago, cooldown_hours=12.0, current_time=now) is True

    def test_outside_cooldown_window(self) -> None:
        now = datetime.now(UTC)
        thirteen_hours_ago = (now - timedelta(hours=13)).isoformat()
        assert (
            is_alert_debounced(thirteen_hours_ago, cooldown_hours=12.0, current_time=now) is False
        )

    def test_malformed_timestamp_fails_open(self) -> None:
        assert is_alert_debounced("invalid-iso-date", cooldown_hours=12.0) is False


class TestCommentDraftNormalization:
    """Test schema hardening against open-source model variations."""

    def test_standard_draft_comment(self) -> None:
        draft = CommentDraft.model_validate(
            {"draft_comment": "Excellent distributed systems post!"}
        )
        assert draft.draft_comment == "Excellent distributed systems post!"

    def test_content_synonym_normalized(self) -> None:
        # Some open-source models return {"content": ...}
        draft = CommentDraft.model_validate({"content": "A thoughtful technical comment."})
        assert draft.draft_comment == "A thoughtful technical comment."

    def test_comment_synonym_normalized(self) -> None:
        draft = CommentDraft.model_validate({"comment": "Another valuable insight on consensus."})
        assert draft.draft_comment == "Another valuable insight on consensus."

    def test_extra_fields_ignored_without_error(self) -> None:
        # Models returning extra metadata (like author_id, post_id) should not fail validation
        draft = CommentDraft.model_validate(
            {
                "content": "Valid comment text",
                "author_id": 999,
                "post_id": 12345,
                "unknown_meta": True,
            }
        )
        assert draft.draft_comment == "Valid comment text"


@pytest.mark.asyncio
class TestLLMAlertNotifications:
    """Test multi-channel notification and state persistence."""

    async def test_healthy_runner_clears_previous_degradation(
        self, test_settings: Settings
    ) -> None:
        mock_llm = MagicMock(spec=LLMService)
        mock_llm.get_health_report.return_value = {
            "status": "healthy",
            "primary_model": test_settings.effective_primary_model,
            "fallback_model": test_settings.effective_fallback_model,
            "primary_failure_count": 0,
            "fallback_invocations": 0,
        }

        mock_store = MagicMock()
        # Simulate previously degraded state in store
        mock_store.get_key.return_value = json.dumps({"status": "degraded"})

        with patch(
            "agent.orchestration.llm_alert.notify_worker_event", new_callable=AsyncMock
        ) as mock_worker:
            report = await check_and_notify_llm_health(test_settings, mock_llm, mock_store)

            assert report["status"] == "healthy"
            # Verify status updated to healthy in store
            mock_store.put_key.assert_called_once()
            args = mock_store.put_key.call_args[0]
            assert args[0] == HEALTH_RECORD_KEY
            assert json.loads(args[1])["status"] == "healthy"

            # Verify recovery event dispatched
            mock_worker.assert_called_once_with(
                test_settings,
                "system_recovered",
                {"code": "LLM_HEALTHY", "model": test_settings.effective_primary_model},
            )

    async def test_degraded_runner_triggers_telegram_and_worker(
        self, test_settings: Settings
    ) -> None:
        mock_llm = MagicMock(spec=LLMService)
        mock_llm.get_health_report.return_value = {
            "status": "degraded",
            "primary_model": test_settings.effective_primary_model,
            "fallback_model": test_settings.effective_fallback_model,
            "primary_failure_count": 2,
            "fallback_invocations": 2,
            "has_primary_404": True,
            "last_primary_error": "[404] Not Found Function: test-uuid",
        }

        mock_store = MagicMock()
        mock_store.get_key.return_value = None  # No previous alert timestamp (not debounced)

        mock_telegram = AsyncMock(spec=TelegramClient)

        with patch(
            "agent.orchestration.llm_alert.notify_worker_event", new_callable=AsyncMock
        ) as mock_worker:
            report = await check_and_notify_llm_health(
                test_settings, mock_llm, mock_store, telegram=mock_telegram
            )

            assert report["status"] == "degraded"

            # 1. Check store saved degraded health
            mock_store.put_key.assert_any_call(
                HEALTH_RECORD_KEY,
                json.dumps(report),
            )

            # 2. Check worker event dispatched with dynamic model names
            mock_worker.assert_called_once_with(
                test_settings,
                "system_warning",
                {
                    "code": "LLM_PRIMARY_DEGRADED",
                    "model": test_settings.effective_primary_model,
                    "fallback": test_settings.effective_fallback_model,
                    "error": "[404] Not Found Function: test-uuid",
                    "failure_count": 2,
                },
            )

            # 3. Check Telegram alert sent
            mock_telegram.send_notification.assert_called_once()
            sent_msg = mock_telegram.send_notification.call_args[0][0]
            assert test_settings.effective_primary_model in sent_msg
            assert test_settings.effective_fallback_model in sent_msg
            assert "404" in sent_msg

    async def test_degraded_runner_debounces_telegram(self, test_settings: Settings) -> None:
        mock_llm = MagicMock(spec=LLMService)
        mock_llm.get_health_report.return_value = {
            "status": "degraded",
            "primary_model": test_settings.effective_primary_model,
            "fallback_model": test_settings.effective_fallback_model,
            "primary_failure_count": 1,
            "fallback_invocations": 1,
            "last_primary_error": "Connection timed out",
        }

        mock_store = MagicMock()
        # Return timestamp from 1 hour ago (within 12h debounce window)
        one_hour_ago = (datetime.now(UTC) - timedelta(hours=1)).isoformat()
        mock_store.get_key.return_value = one_hour_ago

        mock_telegram = AsyncMock(spec=TelegramClient)

        with patch("agent.orchestration.llm_alert.notify_worker_event", new_callable=AsyncMock):
            await check_and_notify_llm_health(
                test_settings, mock_llm, mock_store, telegram=mock_telegram
            )

            # Telegram notification should be suppressed
            mock_telegram.send_notification.assert_not_called()


class TestSuggestionCardFormatting:
    """Test dynamic fallback tag display on Telegram suggestion cards."""

    def test_card_includes_dynamic_fallback_tag(self) -> None:
        action = PendingAction(
            item_id="test1234",
            action_type="approve_comment",
            draft_text="Great insights on caching topologies.",
            confidence=0.9,
            author_name="Alice Engineer",
            fallback_used=True,
            model_used="openai/gpt-oss-20b",
        )
        card = format_suggestion_card(action)
        assert "Drafted using fallback model (openai/gpt-oss-20b)" in card

    def test_card_omits_fallback_tag_when_healthy(self) -> None:
        action = PendingAction(
            item_id="test5678",
            action_type="approve_comment",
            draft_text="Insightful discussion on consensus.",
            confidence=0.95,
            author_name="Bob Developer",
            fallback_used=False,
            model_used="nvidia/nemotron-3-ultra-550b-a55b",
        )
        card = format_suggestion_card(action)
        assert "Drafted using fallback model" not in card


class TestDoctorProbe:
    """Test active doctor probe for LLM provider."""

    def test_doctor_probe_passes_when_model_responds(self, test_settings: Settings) -> None:
        with patch("agent.llm.models.build_chat_model") as mock_build:
            mock_model = MagicMock()
            mock_build.return_value = mock_model
            res = check_llm_provider(test_settings, probe_connectivity=True)
            assert res.status == "PASS"
            assert "configured with model" in res.message
            mock_model.invoke.assert_called_once()

    def test_doctor_probe_fails_on_404(self, test_settings: Settings) -> None:
        with patch("agent.llm.models.build_chat_model") as mock_build:
            mock_model = MagicMock()
            mock_model.invoke.side_effect = Exception(
                "[404] Not Found Function 'xyz': Not found for account"
            )
            mock_build.return_value = mock_model
            res = check_llm_provider(test_settings, probe_connectivity=True)
            assert res.status == "FAIL"
            assert "404" in res.message
            assert test_settings.effective_primary_model in res.message
