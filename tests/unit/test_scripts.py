"""Unit tests for local operator scripts."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

from scripts.register_telegram_webhook import delete_webhook, register_webhook


def test_register_webhook_success() -> None:
    with patch("httpx.post") as mock_post:
        mock_resp = AsyncMock()
        mock_resp.raise_for_status = lambda: None
        mock_resp.json = lambda: {"ok": True, "description": "Webhook was set"}
        mock_post.return_value = mock_resp

        success = register_webhook(
            worker_url="https://relay.workers.dev",
            secret_token="sec_token_123",
            bot_token="123:bot_token",
        )
        assert success is True


def test_delete_webhook_success() -> None:
    with patch("httpx.post") as mock_post:
        mock_resp = AsyncMock()
        mock_resp.raise_for_status = lambda: None
        mock_resp.json = lambda: {"ok": True, "description": "Webhook was deleted"}
        mock_post.return_value = mock_resp

        success = delete_webhook(bot_token="123:bot_token")
        assert success is True
