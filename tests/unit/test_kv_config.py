"""Unit tests for centralized Cloudflare KV configuration and secrets loader."""

from __future__ import annotations

import json
from collections.abc import Generator
from typing import Any
from unittest.mock import MagicMock, patch

import httpx
import pytest
from pydantic import SecretStr

from agent.browser.session import generate_encryption_key
from agent.cli.config import (
    run_config_init_from_env,
    run_config_set,
    run_config_set_secret,
    run_config_show,
)
from agent.config.kv_loader import (
    CONFIG_KV_KEY,
    SECRETS_KV_KEY,
    clear_kv_config_cache,
    decrypt_secrets_payload,
    encrypt_secrets_payload,
    fetch_kv_raw_value,
    load_central_kv_settings,
    put_kv_raw_value,
)
from agent.config.settings import Settings
from agent.errors import ConfigError


@pytest.fixture(autouse=True)
def _reset_kv_cache() -> Generator[None, None, None]:
    """Ensure in-memory KV cache is cleared before and after each test."""
    clear_kv_config_cache()
    yield
    clear_kv_config_cache()


def test_fernet_secrets_encryption_roundtrip() -> None:
    """Verify secrets dictionary encryption and decryption roundtrip."""
    key = generate_encryption_key()
    payload = {
        "nvidia_nim_api_key": "nvapi-test-key-12345",
        "telegram_bot_token": "987654321:ABCDEF",
    }

    encrypted = encrypt_secrets_payload(payload, key)
    assert isinstance(encrypted, str)
    assert encrypted != json.dumps(payload)

    decrypted = decrypt_secrets_payload(encrypted, key)
    assert decrypted == payload


def test_fernet_secrets_decryption_invalid_key_raises_config_error() -> None:
    """Verify decrypting with a wrong key raises ConfigError."""
    key1 = generate_encryption_key()
    key2 = generate_encryption_key()
    encrypted = encrypt_secrets_payload({"key": "val"}, key1)

    with pytest.raises(ConfigError, match="Invalid SESSION_ENCRYPTION_KEY"):
        decrypt_secrets_payload(encrypted, key2)


def test_fetch_and_put_kv_raw_value_mocked() -> None:
    """Test fetch_kv_raw_value and put_kv_raw_value with mocked httpx responses."""
    client = MagicMock(spec=httpx.Client)

    # 404 returns None
    resp_404 = MagicMock(spec=httpx.Response, status_code=404)
    client.get.return_value = resp_404
    val = fetch_kv_raw_value("acc", "ns", "tok", "nonexistent", client=client)
    assert val is None

    # 200 returns text
    resp_200 = MagicMock(spec=httpx.Response, status_code=200, text='{"foo": "bar"}')
    client.get.return_value = resp_200
    val = fetch_kv_raw_value("acc", "ns", "tok", "foo", client=client)
    assert val == '{"foo": "bar"}'

    # 500 raises ConfigError
    resp_500 = MagicMock(spec=httpx.Response, status_code=500, text="Internal Error")
    client.get.return_value = resp_500
    with pytest.raises(ConfigError, match="HTTP 500"):
        fetch_kv_raw_value("acc", "ns", "tok", "err", client=client)

    # Put 200 succeeds
    resp_put_200 = MagicMock(spec=httpx.Response, status_code=200)
    client.put.return_value = resp_put_200
    put_kv_raw_value("acc", "ns", "tok", "foo", "content", client=client)
    client.put.assert_called_once()


def test_load_central_kv_settings_offline_mode() -> None:
    """When Cloudflare credentials are missing, offline mode returns empty dict without error."""
    result = load_central_kv_settings(
        account_id=None,
        namespace_id=None,
        api_token=None,
        encryption_key=None,
        strict=False,
    )
    assert result == {}


def test_load_central_kv_settings_strict_missing_creds_raises() -> None:
    """In strict mode, missing credentials raise ConfigError."""
    with pytest.raises(ConfigError, match="Strict KV configuration requires"):
        load_central_kv_settings(
            account_id=None,
            namespace_id=None,
            api_token=None,
            encryption_key=None,
            strict=True,
        )


def test_load_central_kv_settings_strict_missing_config_raises() -> None:
    """In strict mode, if config:runtime does not exist in KV, fail fast."""
    client = MagicMock(spec=httpx.Client)
    client.get.return_value = MagicMock(spec=httpx.Response, status_code=404)

    with pytest.raises(ConfigError, match="Missing required Cloudflare KV key 'config:runtime'"):
        load_central_kv_settings(
            account_id="acc",
            namespace_id="ns",
            api_token="tok",
            encryption_key="key",
            strict=True,
            client=client,
        )


def test_load_central_kv_settings_strict_missing_required_model_raises() -> None:
    """In strict mode, if config:runtime lacks nim_model_primary, fail fast."""
    client = MagicMock(spec=httpx.Client)
    # config:runtime present but lacks nim_model_primary
    client.get.return_value = MagicMock(
        spec=httpx.Response,
        status_code=200,
        text=json.dumps({"max_suggestions_per_run": 5}),
    )

    with pytest.raises(ConfigError, match="Missing required setting 'nim_model_primary'"):
        load_central_kv_settings(
            account_id="acc",
            namespace_id="ns",
            api_token="tok",
            encryption_key="key",
            strict=True,
            client=client,
        )


def test_load_central_kv_settings_strict_success() -> None:
    """Verify successful loading and merging of operational config and decrypted secrets."""
    enc_key = generate_encryption_key()
    config_dict = {
        "nim_model_primary": "custom/llama-3.3-kv-test",
        "max_suggestions_per_run": 7,
    }
    secrets_dict = {
        "nvidia_nim_api_key": "nvapi-kv-secret-1234",
    }
    encrypted_secrets = encrypt_secrets_payload(secrets_dict, enc_key)

    client = MagicMock(spec=httpx.Client)

    def mock_get(url: str, **kwargs: Any) -> MagicMock:
        if CONFIG_KV_KEY in url:
            return MagicMock(spec=httpx.Response, status_code=200, text=json.dumps(config_dict))
        if SECRETS_KV_KEY in url:
            return MagicMock(spec=httpx.Response, status_code=200, text=encrypted_secrets)
        return MagicMock(spec=httpx.Response, status_code=404)

    client.get.side_effect = mock_get

    combined = load_central_kv_settings(
        account_id="acc",
        namespace_id="ns",
        api_token="tok",
        encryption_key=enc_key,
        strict=True,
        client=client,
    )

    assert combined["nim_model_primary"] == "custom/llama-3.3-kv-test"
    assert combined["max_suggestions_per_run"] == 7
    assert combined["nvidia_nim_api_key"] == "nvapi-kv-secret-1234"


def test_authoritative_kv_settings_integration(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify that Settings loads authoritative config from KV when STATE_BACKEND=kv."""
    enc_key = generate_encryption_key()
    config_data = {
        "nim_model_primary": "kv-authoritative-model",
        "max_suggestions_per_run": 9,
        "user_focus_areas": ["KV AI", "KV Python"],
    }
    secrets_data = {
        "nvidia_nim_api_key": "nvapi-authoritative-key",
        "telegram_bot_token": "123456:mock_token",
        "telegram_authorized_chat_id": 99999999,
    }

    monkeypatch.setenv("CLOUDFLARE_ACCOUNT_ID", "mock_acc")
    monkeypatch.setenv("CLOUDFLARE_KV_NAMESPACE_ID", "mock_ns")
    monkeypatch.setenv("CLOUDFLARE_API_TOKEN", "mock_tok")
    monkeypatch.setenv("SESSION_ENCRYPTION_KEY", enc_key)
    monkeypatch.setenv("STATE_BACKEND", "kv")

    with patch(
        "agent.config.sources.load_central_kv_settings",
        return_value={**config_data, **secrets_data},
    ):
        settings = Settings(
            telegram_bot_token="123456:mock_token",
            telegram_authorized_chat_id=99999999,
        )
        assert settings.nim_model_primary == "kv-authoritative-model"
        assert settings.max_suggestions_per_run == 9
        assert settings.user_focus_areas == ["KV AI", "KV Python"]
        assert settings.nvidia_nim_api_key is not None
        assert isinstance(settings.nvidia_nim_api_key, SecretStr)
        assert settings.nvidia_nim_api_key.get_secret_value() == "nvapi-authoritative-key"
        assert isinstance(settings.telegram_bot_token, SecretStr)
        assert settings.telegram_bot_token.get_secret_value() == "123456:mock_token"
        assert settings.telegram_authorized_chat_id == 99999999


def test_cli_config_commands(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """Test CLI commands: show, set, set-secret, and init-from-env."""
    enc_key = generate_encryption_key()
    monkeypatch.setenv("CLOUDFLARE_ACCOUNT_ID", "mock_acc")
    monkeypatch.setenv("CLOUDFLARE_KV_NAMESPACE_ID", "mock_ns")
    monkeypatch.setenv("CLOUDFLARE_API_TOKEN", "mock_tok")
    monkeypatch.setenv("SESSION_ENCRYPTION_KEY", enc_key)
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "123456:test_token")
    monkeypatch.setenv("TELEGRAM_AUTHORIZED_CHAT_ID", "123456789")
    monkeypatch.setenv("NVIDIA_NIM_API_KEY", "nvapi-1234567890")

    mock_kv = {
        CONFIG_KV_KEY: json.dumps({"nim_model_primary": "nvidia/nemotron-3-ultra-550b-a55b"}),
        SECRETS_KV_KEY: encrypt_secrets_payload(
            {"nvidia_nim_api_key": "nvapi-1234567890"}, enc_key
        ),
    }

    def fake_fetch(acc: str, ns: str, tok: str, key: str, **kwargs: Any) -> str | None:
        return mock_kv.get(key)

    def fake_put(acc: str, ns: str, tok: str, key: str, val: str, **kwargs: Any) -> None:
        mock_kv[key] = val

    with (
        patch("agent.cli.config.fetch_kv_raw_value", side_effect=fake_fetch),
        patch("agent.cli.config.put_kv_raw_value", side_effect=fake_put),
    ):
        # 1. show
        args = MagicMock()
        ret = run_config_show(args)
        assert ret == 0
        captured = capsys.readouterr().out
        assert "nim_model_primary" in captured
        assert "nvap...7890" in captured

        # 2. set
        set_args = MagicMock(key="nim_model_primary", value="custom/new-model")
        ret_set = run_config_set(set_args)
        assert ret_set == 0
        assert "custom/new-model" in mock_kv[CONFIG_KV_KEY]

        # 3. set-secret
        secret_args = MagicMock(key="openai_api_key", value="sk-new-secret")
        ret_sec = run_config_set_secret(secret_args)
        assert ret_sec == 0
        decrypted = decrypt_secrets_payload(mock_kv[SECRETS_KV_KEY], enc_key)
        assert decrypted["openai_api_key"] == "sk-new-secret"

        # 4. init-from-env
        init_args = MagicMock()
        ret_init = run_config_init_from_env(init_args)
        assert ret_init == 0
