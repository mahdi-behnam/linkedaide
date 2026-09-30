"""Unit tests for residential proxy gateway configuration, sticky sessions, and stealth geo-alignment."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest
from pydantic import SecretStr

from agent.browser.session import build_proxy_config, create_browser_context
from agent.config import Settings


def _create_minimal_settings(**kwargs) -> Settings:
    """Helper creating a minimal Settings instance with defaults."""
    base_kwargs = {
        "telegram_bot_token": "123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11",
        "telegram_authorized_chat_id": 987654321,
        "nvidia_nim_api_key": "nvapi-test-key-12345",
    }
    base_kwargs.update(kwargs)
    return Settings(**base_kwargs)


def test_build_proxy_config_empty() -> None:
    """build_proxy_config returns None when residential_proxy_url is None or blank."""
    settings = _create_minimal_settings(residential_proxy_url=None)
    assert build_proxy_config(settings) is None

    settings_blank = _create_minimal_settings(residential_proxy_url="")
    assert build_proxy_config(settings_blank) is None


def test_build_proxy_config_simple_http() -> None:
    """build_proxy_config parses basic HTTP proxy without authentication."""
    settings = _create_minimal_settings(residential_proxy_url="http://residential.gateway.io:8080")
    config = build_proxy_config(settings)
    assert config is not None
    assert config == {"server": "http://residential.gateway.io:8080"}
    assert "username" not in config
    assert "password" not in config


def test_build_proxy_config_with_credentials() -> None:
    """build_proxy_config extracts username and password from authenticated proxy URL."""
    settings = _create_minimal_settings(
        residential_proxy_url="http://proxy_user:proxy_pass@res.proxy.net:9999"
    )
    config = build_proxy_config(settings)
    assert config is not None
    assert config["server"] == "http://res.proxy.net:9999"
    assert config["username"] == "proxy_user"
    assert config["password"] == "proxy_pass"


def test_build_proxy_config_socks5() -> None:
    """build_proxy_config supports SOCKS5 proxy protocol."""
    settings = _create_minimal_settings(
        residential_proxy_url="socks5://socks_user:socks_secret@127.0.0.1:1080"
    )
    config = build_proxy_config(settings)
    assert config is not None
    assert config["server"] == "socks5://127.0.0.1:1080"
    assert config["username"] == "socks_user"
    assert config["password"] == "socks_secret"


def test_build_proxy_config_sticky_session_injection() -> None:
    """Sticky session ID is formatted into username when credentials are present."""
    settings = _create_minimal_settings(
        residential_proxy_url="http://gate_user:gate_pass@gate.residence.net:8888",
        proxy_sticky_session_id="session_abc12345",
    )
    config = build_proxy_config(settings)
    assert config is not None
    assert config["server"] == "http://gate.residence.net:8888"
    assert config["username"] == "gate_user-session-session_abc12345"
    assert config["password"] == "gate_pass"


def test_build_proxy_config_sticky_session_without_credentials() -> None:
    """Sticky session ID is ignored when no credentials are in proxy URL."""
    settings = _create_minimal_settings(
        residential_proxy_url="http://open.proxy.org:8080",
        proxy_sticky_session_id="session_xyz",
    )
    config = build_proxy_config(settings)
    assert config is not None
    assert config["server"] == "http://open.proxy.org:8080"
    assert "username" not in config


@pytest.mark.asyncio
async def test_create_browser_context_proxy_and_geo_propagation() -> None:
    """create_browser_context propagates proxy, timezone_id, and locale to Playwright context."""
    settings = _create_minimal_settings(
        residential_proxy_url="http://agent_user:agent_pass@proxy.example.com:7000",
        proxy_sticky_session_id="sticky_node_9",
        proxy_egress_timezone="Europe/London",
        proxy_egress_locale="en-GB",
    )

    mock_browser = MagicMock()
    mock_context = MagicMock()
    mock_context.add_init_script = AsyncMock()
    mock_browser.new_context = AsyncMock(return_value=mock_context)

    context = await create_browser_context(mock_browser, settings)

    assert context == mock_context
    mock_browser.new_context.assert_awaited_once()
    called_kwargs = mock_browser.new_context.call_args[1]

    # Verify proxy configuration
    assert "proxy" in called_kwargs
    proxy = called_kwargs["proxy"]
    assert proxy["server"] == "http://proxy.example.com:7000"
    assert proxy["username"] == "agent_user-session-sticky_node_9"
    assert proxy["password"] == "agent_pass"

    # Verify timezone and locale alignment
    assert called_kwargs["timezone_id"] == "Europe/London"
    assert called_kwargs["locale"] == "en-GB"

    # Verify anti-detection script was added
    mock_context.add_init_script.assert_awaited_once()


@pytest.mark.asyncio
async def test_create_browser_context_without_proxy() -> None:
    """create_browser_context defaults when no proxy is configured."""
    settings = _create_minimal_settings(
        residential_proxy_url=None,
        proxy_egress_timezone=None,
        proxy_egress_locale=None,
    )

    mock_browser = MagicMock()
    mock_context = MagicMock()
    mock_context.add_init_script = AsyncMock()
    mock_browser.new_context = AsyncMock(return_value=mock_context)

    await create_browser_context(mock_browser, settings)

    called_kwargs = mock_browser.new_context.call_args[1]
    assert "proxy" not in called_kwargs
    assert called_kwargs["timezone_id"] == "America/New_York"
    assert called_kwargs["locale"] == "en-US"


def test_settings_secret_wrapping() -> None:
    """Ensure residential_proxy_url is safely wrapped in SecretStr."""
    settings = _create_minimal_settings(residential_proxy_url="http://user:secret@proxy.com:8080")
    assert isinstance(settings.residential_proxy_url, SecretStr)
    assert settings.residential_proxy_url.get_secret_value() == "http://user:secret@proxy.com:8080"
