"""Unit tests for automated rolling cookie keepalive and session persistence."""

from __future__ import annotations

import json
import time
from unittest.mock import AsyncMock, MagicMock

import pytest
from cryptography.fernet import Fernet
from pydantic import SecretStr

from agent.browser.session import generate_encryption_key
from agent.browser.session_keeper import refresh_and_persist_session
from agent.errors import SessionError


@pytest.fixture
def enc_key() -> str:
    return generate_encryption_key()


@pytest.fixture
def mock_context() -> MagicMock:
    ctx = MagicMock()
    now_epoch = time.time()
    ctx.cookies = AsyncMock(
        return_value=[
            {
                "name": "li_at",
                "value": "AQEDATestCookieValue123",
                "expires": now_epoch + 86400 * 30,  # 30 days remaining
                "domain": ".www.linkedin.com",
                "path": "/",
            },
            {
                "name": "JSESSIONID",
                "value": "ajax:987654321",
                "expires": now_epoch + 86400 * 30,
                "domain": ".www.linkedin.com",
                "path": "/",
            },
        ]
    )
    ctx.storage_state = AsyncMock(
        return_value={
            "cookies": [{"name": "li_at", "value": "AQEDATestCookieValue123"}],
            "origins": [],
        }
    )
    return ctx


@pytest.fixture
def mock_state_store() -> MagicMock:
    store = MagicMock()
    store.put_key = MagicMock()
    return store


@pytest.mark.asyncio
async def test_refresh_and_persist_session_success(
    mock_context: MagicMock, mock_state_store: MagicMock, enc_key: str
) -> None:
    result = await refresh_and_persist_session(
        context=mock_context,
        session_encryption_key=enc_key,
        state_store=mock_state_store,
    )

    assert result["refreshed"] is True
    assert 29.0 <= result["remaining_days"] <= 31.0

    # Verify state store interaction
    mock_state_store.put_key.assert_called_once()
    key_arg, token_arg = mock_state_store.put_key.call_args[0]
    assert key_arg == "linkedin_session_state_enc"
    assert isinstance(token_arg, str)

    # Verify that the token can be decrypted and matches original storage state
    f = Fernet(enc_key.encode("utf-8"))
    decrypted_bytes = f.decrypt(token_arg.encode("utf-8"))
    decrypted_state = json.loads(decrypted_bytes.decode("utf-8"))
    assert decrypted_state["cookies"][0]["name"] == "li_at"
    assert decrypted_state["cookies"][0]["value"] == "AQEDATestCookieValue123"


@pytest.mark.asyncio
async def test_refresh_and_persist_session_with_secret_str(
    mock_context: MagicMock, mock_state_store: MagicMock, enc_key: str
) -> None:
    secret_key = SecretStr(enc_key)
    result = await refresh_and_persist_session(
        context=mock_context,
        session_encryption_key=secret_key,
        state_store=mock_state_store,
    )

    assert result["refreshed"] is True
    mock_state_store.put_key.assert_called_once()


@pytest.mark.asyncio
async def test_refresh_and_persist_session_missing_encryption_key_raises(
    mock_context: MagicMock, mock_state_store: MagicMock
) -> None:
    with pytest.raises(SessionError, match="session_encryption_key is missing"):
        await refresh_and_persist_session(
            context=mock_context,
            session_encryption_key="",
            state_store=mock_state_store,
        )


@pytest.mark.asyncio
async def test_refresh_and_persist_session_without_li_at_defaults_zero_days(
    mock_context: MagicMock, mock_state_store: MagicMock, enc_key: str
) -> None:
    mock_context.cookies = AsyncMock(
        return_value=[{"name": "other_cookie", "value": "123", "expires": -1}]
    )

    result = await refresh_and_persist_session(
        context=mock_context,
        session_encryption_key=enc_key,
        state_store=mock_state_store,
    )

    assert result["refreshed"] is True
    assert result["remaining_days"] == 0.0
    mock_state_store.put_key.assert_called_once()


@pytest.mark.asyncio
async def test_refresh_and_persist_session_cookies_failure_raises(
    mock_context: MagicMock, mock_state_store: MagicMock, enc_key: str
) -> None:
    mock_context.cookies = AsyncMock(side_effect=RuntimeError("Browser process disconnected"))

    with pytest.raises(SessionError, match="Failed to extract cookies"):
        await refresh_and_persist_session(
            context=mock_context,
            session_encryption_key=enc_key,
            state_store=mock_state_store,
        )


@pytest.mark.asyncio
async def test_refresh_and_persist_session_storage_state_failure_raises(
    mock_context: MagicMock, mock_state_store: MagicMock, enc_key: str
) -> None:
    mock_context.storage_state = AsyncMock(side_effect=RuntimeError("Storage state access denied"))

    with pytest.raises(SessionError, match="Failed to dump browser storage state"):
        await refresh_and_persist_session(
            context=mock_context,
            session_encryption_key=enc_key,
            state_store=mock_state_store,
        )


@pytest.mark.asyncio
async def test_refresh_and_persist_session_state_store_failure_raises(
    mock_context: MagicMock, mock_state_store: MagicMock, enc_key: str
) -> None:
    mock_state_store.put_key = MagicMock(side_effect=RuntimeError("KV write timeout"))

    with pytest.raises(SessionError, match="Failed to persist refreshed session"):
        await refresh_and_persist_session(
            context=mock_context,
            session_encryption_key=enc_key,
            state_store=mock_state_store,
        )


@pytest.mark.asyncio
async def test_action_executor_triggers_session_refresh(
    mock_context: MagicMock, mock_state_store: MagicMock, enc_key: str
) -> None:
    from agent.browser.executor import ActionExecutor
    from agent.config import Settings

    settings = Settings(
        nvidia_nim_api_key=SecretStr("nvapi-test"),
        nim_model_primary="primary-model",
        nim_model_fallback="fallback-model",
        telegram_bot_token=SecretStr("123:token"),
        telegram_authorized_chat_id=12345,
        user_focus_areas=["AI"],
        session_encryption_key=SecretStr(enc_key),
        dry_run=False,
    )

    page = MagicMock()
    page.context = mock_context
    page.url = "https://www.linkedin.com/feed/update/urn:li:activity:100/"
    page.screenshot = AsyncMock()

    executor = ActionExecutor(page, settings, state_store=mock_state_store)
    result = await executor.refresh_session()

    assert result is not None
    assert result["refreshed"] is True
    mock_state_store.put_key.assert_called_once()
