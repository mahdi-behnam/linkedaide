"""Unit tests for Cloudflare Worker realtime event notifier."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import httpx
import pytest
from pydantic import SecretStr

from agent.config.settings import Settings
from agent.orchestration.worker_notifier import notify_worker_event


@pytest.fixture
def base_settings() -> Settings:
    return Settings(
        telegram_bot_token="dummy:token",
        telegram_authorized_chat_id=123456,
        worker_url="https://relay-worker.test",
        desktop_api_secret=SecretStr("test-secret-key-123"),
    )


@pytest.mark.asyncio
async def test_notify_worker_event_skips_when_url_missing() -> None:
    settings = Settings(
        telegram_bot_token="dummy:token",
        telegram_authorized_chat_id=123456,
        worker_url=None,
        desktop_api_secret=SecretStr("secret"),
    )
    result = await notify_worker_event(settings, "action_executed")
    assert result is False


@pytest.mark.asyncio
async def test_notify_worker_event_skips_when_secret_missing() -> None:
    settings = Settings(
        telegram_bot_token="dummy:token",
        telegram_authorized_chat_id=123456,
        worker_url="https://relay-worker.test",
        desktop_api_secret=None,
    )
    result = await notify_worker_event(settings, "action_executed")
    assert result is False


@pytest.mark.asyncio
async def test_notify_worker_event_success(base_settings: Settings) -> None:
    mock_response = httpx.Response(status_code=200, json={"success": True, "broadcasted": True})

    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_post.return_value = mock_response

        success = await notify_worker_event(
            base_settings,
            "action_executed",
            {"item_id": "item-123", "action": "approve"},
        )

        assert success is True
        mock_post.assert_called_once()
        call_url = mock_post.call_args[0][0]
        call_json = mock_post.call_args[1]["json"]
        call_headers = mock_post.call_args[1]["headers"]

        assert call_url == "https://relay-worker.test/api/event"
        assert call_json == {
            "type": "action_executed",
            "item_id": "item-123",
            "action": "approve",
        }
        assert call_headers["Authorization"] == "Bearer test-secret-key-123"


@pytest.mark.asyncio
async def test_notify_worker_event_server_error(base_settings: Settings) -> None:
    mock_response = httpx.Response(status_code=500, text="Internal Server Error")

    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_post.return_value = mock_response

        success = await notify_worker_event(
            base_settings,
            "queue_updated",
            {"suggestions_count": 3},
        )

        assert success is False


@pytest.mark.asyncio
async def test_notify_worker_event_network_exception_fails_open(base_settings: Settings) -> None:
    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_post.side_effect = httpx.ConnectTimeout("Connection timed out")

        # Must not raise an exception, must fail open
        success = await notify_worker_event(
            base_settings,
            "action_executed",
        )

        assert success is False
