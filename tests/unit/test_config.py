"""Unit tests for configuration loading and validation in agent.config."""

from pathlib import Path
from typing import Any

import pytest
from pydantic import SecretStr
from pydantic.fields import FieldInfo

from agent.config import ComplexValueDecoderMixin, Settings, load_settings
from agent.errors import ConfigError


class TestSettings:
    """Test suite for Settings model and loader."""

    def test_valid_settings_explicit(self) -> None:
        settings = Settings(
            nvidia_nim_api_key="nvapi-test-key",
            nim_model_primary="meta/llama-3.3-70b-instruct",
            nim_model_fallback="meta/llama-3.1-8b-instruct",
            nim_model_triage=None,
            nim_temperature=0.3,
            nim_timeout_seconds=45.0,
            nim_max_tokens=2048,
            telegram_bot_token="123456:ABC-DEF",
            telegram_authorized_chat_id=987654321,
            session_encryption_key="test-key-base64=",
            user_focus_areas=["AI Agents", "Distributed Systems"],
            user_persona="Senior AI Engineer",
            max_comments_per_day=4,
            max_posts_per_day=2,
            max_suggestions_per_run=2,
            pending_action_ttl_hours=8,
            agent_paused=False,
            dry_run=True,
            log_level="DEBUG",
            state_dir=Path("state"),
        )

        assert isinstance(settings.nvidia_nim_api_key, SecretStr)
        assert settings.nvidia_nim_api_key.get_secret_value() == "nvapi-test-key"
        assert settings.effective_triage_model == "meta/llama-3.3-70b-instruct"
        assert settings.telegram_authorized_chat_id == 987654321
        assert settings.dry_run is True
        assert len(settings.user_focus_areas) == 2

    def test_effective_triage_model_override(self) -> None:
        settings = Settings(
            nvidia_nim_api_key="nvapi-test-key",
            nim_model_primary="meta/llama-3.3-70b-instruct",
            nim_model_triage="meta/llama-3.1-8b-instruct",
            telegram_bot_token="123456:ABC",
            telegram_authorized_chat_id=123,
        )
        assert settings.effective_triage_model == "meta/llama-3.1-8b-instruct"

    def test_user_focus_areas_comma_separated(self) -> None:
        settings = Settings(
            nvidia_nim_api_key="nvapi-test-key",
            telegram_bot_token="123:ABC",
            telegram_authorized_chat_id=123,
            user_focus_areas="AI Agents,  Python,   Distributed Systems ,",  # type: ignore[arg-type]
        )
        assert settings.user_focus_areas == ["AI Agents", "Python", "Distributed Systems"]

    def test_user_focus_areas_json_string(self) -> None:
        settings = Settings(
            nvidia_nim_api_key="nvapi-test-key",
            telegram_bot_token="123:ABC",
            telegram_authorized_chat_id=123,
            user_focus_areas='["AI Agents", "Python", "Cloud Architecture"]',  # type: ignore[arg-type]
        )
        assert settings.user_focus_areas == ["AI Agents", "Python", "Cloud Architecture"]

    def test_user_focus_areas_empty_string(self) -> None:
        settings = Settings(
            nvidia_nim_api_key="nvapi-test-key",
            telegram_bot_token="123:ABC",
            telegram_authorized_chat_id=123,
            user_focus_areas="  ",  # type: ignore[arg-type]
        )
        assert settings.user_focus_areas == []

    def test_user_focus_areas_malformed_json_fallback(self) -> None:
        settings = Settings(
            nvidia_nim_api_key="nvapi-test-key",
            telegram_bot_token="123:ABC",
            telegram_authorized_chat_id=123,
            user_focus_areas="[invalid json, but valid comma, list]",  # type: ignore[arg-type]
        )
        assert "[invalid json" in settings.user_focus_areas[0]
        assert len(settings.user_focus_areas) == 3

    def test_user_focus_areas_invalid_type(self) -> None:
        settings = Settings(
            nvidia_nim_api_key="nvapi-test-key",
            telegram_bot_token="123:ABC",
            telegram_authorized_chat_id=123,
            user_focus_areas=12345,  # type: ignore[arg-type]
        )
        assert settings.user_focus_areas == []

    def test_load_settings_from_env(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("NVIDIA_NIM_API_KEY", "nvapi-env-key")
        monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "999:TOKEN")
        monkeypatch.setenv("TELEGRAM_AUTHORIZED_CHAT_ID", "555123")
        monkeypatch.setenv("DRY_RUN", "true")
        monkeypatch.setenv("MAX_COMMENTS_PER_DAY", "10")
        monkeypatch.setenv("USER_FOCUS_AREAS", "Python, LangGraph")

        settings = load_settings()
        assert isinstance(settings.nvidia_nim_api_key, SecretStr)
        assert settings.nvidia_nim_api_key.get_secret_value() == "nvapi-env-key"
        assert isinstance(settings.telegram_bot_token, SecretStr)
        assert settings.telegram_bot_token.get_secret_value() == "999:TOKEN"
        assert settings.telegram_authorized_chat_id == 555123
        assert settings.dry_run is True
        assert settings.max_comments_per_day == 10
        assert settings.user_focus_areas == ["Python", "LangGraph"]

    def test_load_settings_from_env_json_list(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("NVIDIA_NIM_API_KEY", "nvapi-env-key")
        monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "999:TOKEN")
        monkeypatch.setenv("TELEGRAM_AUTHORIZED_CHAT_ID", "555123")
        monkeypatch.setenv("USER_FOCUS_AREAS", '["Python", "Distributed Systems"]')

        settings = load_settings()
        assert settings.user_focus_areas == ["Python", "Distributed Systems"]

    def test_load_settings_from_env_empty_focus_areas(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("NVIDIA_NIM_API_KEY", "nvapi-env-key")
        monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "999:TOKEN")
        monkeypatch.setenv("TELEGRAM_AUTHORIZED_CHAT_ID", "555123")
        monkeypatch.setenv("USER_FOCUS_AREAS", "   ")

        settings = load_settings()
        assert settings.user_focus_areas == []

    def test_complex_decoder_mixin_direct(self) -> None:
        class DummyBase:
            def decode_complex_value(self, field_name: str, field_info: Any, value: Any) -> Any:
                return value

        class TestDecoder(ComplexValueDecoderMixin, DummyBase):
            pass

        decoder = TestDecoder()
        field_info = FieldInfo()
        assert decoder.decode_complex_value("other_field", field_info, "raw_value") == "raw_value"
        assert decoder.decode_complex_value("user_focus_areas", field_info, "a, b, c") == [
            "a",
            "b",
            "c",
        ]
        assert decoder.decode_complex_value("user_focus_areas", field_info, "  ") == []
        assert decoder.decode_complex_value("user_focus_areas", field_info, '["x", "y"]') == [
            "x",
            "y",
        ]
        assert decoder.decode_complex_value("user_focus_areas", field_info, "[bad json") == [
            "[bad json"
        ]

    def test_load_settings_missing_required_raises_config_error(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.delenv("NVIDIA_NIM_API_KEY", raising=False)
        monkeypatch.delenv("TELEGRAM_BOT_TOKEN", raising=False)
        monkeypatch.delenv("TELEGRAM_AUTHORIZED_CHAT_ID", raising=False)

        with pytest.raises(ConfigError) as exc_info:
            load_settings(_env_file=None)

        assert "Configuration validation failed" in str(exc_info.value)
        assert "errors" in exc_info.value.details

    def test_load_settings_invalid_range_raises_config_error(self) -> None:
        with pytest.raises(ConfigError) as exc_info:
            load_settings(
                nvidia_nim_api_key="key",
                telegram_bot_token="tok",
                telegram_authorized_chat_id=123,
                nim_temperature=3.5,  # Valid range: 0.0 .. 2.0
            )
        assert "nim_temperature" in str(exc_info.value)

    def test_reaction_settings_defaults_and_explicit(self) -> None:
        settings_default = Settings(
            nvidia_nim_api_key="key",
            telegram_bot_token="tok",
            telegram_authorized_chat_id=123,
        )
        assert settings_default.enable_pre_comment_reaction is False
        assert settings_default.default_reaction_type == "like"

        settings_custom = Settings(
            nvidia_nim_api_key="key",
            telegram_bot_token="tok",
            telegram_authorized_chat_id=123,
            enable_pre_comment_reaction=True,
            default_reaction_type="insightful",
        )
        assert settings_custom.enable_pre_comment_reaction is True
        assert settings_custom.default_reaction_type == "insightful"

    def test_load_reaction_settings_from_env(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("NVIDIA_NIM_API_KEY", "key")
        monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "tok")
        monkeypatch.setenv("TELEGRAM_AUTHORIZED_CHAT_ID", "123")
        monkeypatch.setenv("ENABLE_PRE_COMMENT_REACTION", "true")
        monkeypatch.setenv("DEFAULT_REACTION_TYPE", "celebrate")

        settings = load_settings()
        assert settings.enable_pre_comment_reaction is True
        assert settings.default_reaction_type == "celebrate"
