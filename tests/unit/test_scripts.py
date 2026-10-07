"""Unit tests for local operator scripts."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

from cryptography.fernet import Fernet

from scripts.generate_secrets import (
    generate_desktop_api_secret,
    generate_session_encryption_key,
    generate_telegram_webhook_secret,
)
from scripts.register_telegram_webhook import (
    delete_webhook,
    get_webhook_info,
    register_bot_commands,
    register_webhook,
)


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
        sent_payload = mock_post.call_args[1]["json"]
        assert "message" in sent_payload["allowed_updates"]
        assert "callback_query" in sent_payload["allowed_updates"]


def test_delete_webhook_success() -> None:
    with patch("httpx.post") as mock_post:
        mock_resp = AsyncMock()
        mock_resp.raise_for_status = lambda: None
        mock_resp.json = lambda: {"ok": True, "description": "Webhook was deleted"}
        mock_post.return_value = mock_resp

        success = delete_webhook(bot_token="123:bot_token")
        assert success is True


def test_generate_secrets_functions() -> None:
    key = generate_session_encryption_key()
    assert isinstance(key, str)
    # Validate it is a valid Fernet key
    f = Fernet(key.encode("utf-8"))
    token = f.encrypt(b"test")
    assert f.decrypt(token) == b"test"

    webhook_sec = generate_telegram_webhook_secret()
    assert isinstance(webhook_sec, str)
    assert len(webhook_sec) >= 32
    # Telegram allows characters [A-Za-z0-9_-]
    for ch in webhook_sec:
        assert ch.isalnum() or ch in ("_", "-")

    desktop_sec = generate_desktop_api_secret()
    assert isinstance(desktop_sec, str)
    assert len(desktop_sec) >= 32
    for ch in desktop_sec:
        assert ch.isalnum() or ch in ("_", "-")


def test_get_webhook_info_success() -> None:
    with patch("httpx.get") as mock_get:
        mock_resp = AsyncMock()
        mock_resp.raise_for_status = lambda: None
        mock_resp.json = lambda: {
            "ok": True,
            "result": {
                "url": "https://relay.workers.dev",
                "allowed_updates": ["callback_query", "message"],
                "pending_update_count": 0,
            },
        }
        mock_get.return_value = mock_resp

        info = get_webhook_info(bot_token="123:bot_token")
        assert info["url"] == "https://relay.workers.dev"
        assert "message" in info["allowed_updates"]


def test_register_bot_commands_success() -> None:
    with patch("httpx.post") as mock_post:
        mock_resp = AsyncMock()
        mock_resp.raise_for_status = lambda: None
        mock_resp.json = lambda: {"ok": True, "result": True}
        mock_post.return_value = mock_resp

        success = register_bot_commands(bot_token="123:bot_token")
        assert success is True
        sent_payload = mock_post.call_args[1]["json"]
        assert len(sent_payload["commands"]) >= 5
