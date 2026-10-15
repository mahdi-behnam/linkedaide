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
            nim_model_primary="nvidia/nemotron-3-super-120b-a12b",
            nim_model_fallback="openai/gpt-oss-20b",
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
        assert settings.nim_model_primary == "nvidia/nemotron-3-super-120b-a12b"
        assert settings.nim_model_fallback == "openai/gpt-oss-20b"
        assert settings.effective_triage_model == "nvidia/nemotron-3-super-120b-a12b"
        assert settings.telegram_authorized_chat_id == 987654321
        assert settings.dry_run is True
        assert len(settings.user_focus_areas) == 2

    def test_settings_default_models(self) -> None:
        settings = Settings(
            _env_file=None,  # type: ignore[call-arg]
            nvidia_nim_api_key="nvapi-test-key",
            telegram_bot_token="123456:ABC",
            telegram_authorized_chat_id=123,
        )
        assert settings.nim_model_primary == "nvidia/nemotron-3-super-120b-a12b"
        assert settings.nim_model_fallback == "openai/gpt-oss-20b"
        assert settings.effective_triage_model == "nvidia/nemotron-3-super-120b-a12b"

    def test_effective_triage_model_override(self) -> None:
        settings = Settings(
            nvidia_nim_api_key="nvapi-test-key",
            nim_model_primary="nvidia/nemotron-3-super-120b-a12b",
            nim_model_triage="openai/gpt-oss-20b",
            telegram_bot_token="123456:ABC",
            telegram_authorized_chat_id=123,
        )
        assert settings.effective_triage_model == "openai/gpt-oss-20b"

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

    def test_scout_settings_defaults(self) -> None:
        settings = Settings(
            nvidia_nim_api_key="nvapi-test-key",
            telegram_bot_token="123:ABC",
            telegram_authorized_chat_id=123,
        )
        assert settings.scout_target_urls == []
        assert settings.target_hashtags == []

    def test_scout_target_urls_comma_separated(self) -> None:
        settings = Settings(
            nvidia_nim_api_key="nvapi-test-key",
            telegram_bot_token="123:ABC",
            telegram_authorized_chat_id=123,
            scout_target_urls="https://a.com,  https://b.com , https://a.com,",  # type: ignore[arg-type]
        )
        assert settings.scout_target_urls == ["https://a.com", "https://b.com"]

    def test_scout_target_urls_json_string(self) -> None:
        settings = Settings(
            nvidia_nim_api_key="nvapi-test-key",
            telegram_bot_token="123:ABC",
            telegram_authorized_chat_id=123,
            scout_target_urls='["https://a.com", "https://b.com", "https://a.com"]',  # type: ignore[arg-type]
        )
        assert settings.scout_target_urls == ["https://a.com", "https://b.com"]

    def test_scout_target_urls_empty_and_whitespace(self) -> None:
        settings = Settings(
            nvidia_nim_api_key="nvapi-test-key",
            telegram_bot_token="123:ABC",
            telegram_authorized_chat_id=123,
            scout_target_urls="   ",  # type: ignore[arg-type]
        )
        assert settings.scout_target_urls == []

        settings_list = Settings(
            nvidia_nim_api_key="nvapi-test-key",
            telegram_bot_token="123:ABC",
            telegram_authorized_chat_id=123,
            scout_target_urls=["", "   "],
        )
        assert settings_list.scout_target_urls == []

    def test_target_hashtags_comma_separated(self) -> None:
        settings = Settings(
            nvidia_nim_api_key="nvapi-test-key",
            telegram_bot_token="123:ABC",
            telegram_authorized_chat_id=123,
            target_hashtags="#python,  ai,   #DistributedSystems , #python",  # type: ignore[arg-type]
        )
        assert settings.target_hashtags == ["python", "ai", "DistributedSystems"]

    def test_target_hashtags_json_string(self) -> None:
        settings = Settings(
            nvidia_nim_api_key="nvapi-test-key",
            telegram_bot_token="123:ABC",
            telegram_authorized_chat_id=123,
            target_hashtags='["#python", "#AI", "cloud"]',  # type: ignore[arg-type]
        )
        assert settings.target_hashtags == ["python", "AI", "cloud"]

    def test_target_hashtags_stripping_and_empty(self) -> None:
        settings = Settings(
            nvidia_nim_api_key="nvapi-test-key",
            telegram_bot_token="123:ABC",
            telegram_authorized_chat_id=123,
            target_hashtags=["#", "##", "   ", "##tech", "#  python "],
        )
        assert settings.target_hashtags == ["tech", "python"]

    def test_target_hashtags_space_separated_hashes_discarded(self) -> None:
        """Tags consisting only of hashes and spaces are stripped to empty and discarded."""
        settings = Settings(
            nvidia_nim_api_key="nvapi-test-key",
            telegram_bot_token="123:ABC",
            telegram_authorized_chat_id=123,
            target_hashtags=["# #", "# # #", " # # ", "## #", "   #   #  ", "#valid"],
        )
        assert settings.target_hashtags == ["valid"]

    def test_parse_string_list_filters_none_entries(self) -> None:
        """parse_string_list filters out None items before string conversion."""
        settings = Settings(
            nvidia_nim_api_key="nvapi-test-key",
            telegram_bot_token="123:ABC",
            telegram_authorized_chat_id=123,
            scout_target_urls=[None, "https://example.com/feed", None],  # type: ignore[list-item]
            target_hashtags=[None, "#python", None],  # type: ignore[list-item]
            user_focus_areas=[None, "AI", None],  # type: ignore[list-item]
        )
        assert settings.scout_target_urls == ["https://example.com/feed"]
        assert settings.target_hashtags == ["python"]
        assert settings.user_focus_areas == ["AI"]

    def test_parse_string_list_json_filters_null_entries(self) -> None:
        """_parse_raw_string_list filters out JSON null items."""
        settings = Settings(
            nvidia_nim_api_key="nvapi-test-key",
            telegram_bot_token="123:ABC",
            telegram_authorized_chat_id=123,
            scout_target_urls='["https://example.com/feed", null]',  # type: ignore[arg-type]
            target_hashtags='[null, "#python"]',  # type: ignore[arg-type]
        )
        assert settings.scout_target_urls == ["https://example.com/feed"]
        assert settings.target_hashtags == ["python"]

    def test_load_scout_settings_from_env(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("NVIDIA_NIM_API_KEY", "nvapi-env-key")
        monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "999:TOKEN")
        monkeypatch.setenv("TELEGRAM_AUTHORIZED_CHAT_ID", "555123")
        monkeypatch.setenv(
            "SCOUT_TARGET_URLS",
            "https://linkedin.com/feed/1, https://linkedin.com/feed/2, https://linkedin.com/feed/1",
        )
        monkeypatch.setenv("TARGET_HASHTAGS", "#python, ai, #agentic, #python")

        settings = load_settings()
        assert settings.scout_target_urls == [
            "https://linkedin.com/feed/1",
            "https://linkedin.com/feed/2",
        ]
        assert settings.target_hashtags == ["python", "ai", "agentic"]

    def test_load_scout_settings_from_env_json(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("NVIDIA_NIM_API_KEY", "nvapi-env-key")
        monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "999:TOKEN")
        monkeypatch.setenv("TELEGRAM_AUTHORIZED_CHAT_ID", "555123")
        monkeypatch.setenv("SCOUT_TARGET_URLS", '["https://linkedin.com/feed/1"]')
        monkeypatch.setenv("TARGET_HASHTAGS", '["#python", "ai"]')

        settings = load_settings()
        assert settings.scout_target_urls == ["https://linkedin.com/feed/1"]
        assert settings.target_hashtags == ["python", "ai"]

    def test_complex_decoder_mixin_scout_fields(self) -> None:
        class DummyBase:
            def decode_complex_value(self, field_name: str, field_info: Any, value: Any) -> Any:
                return value

        class TestDecoder(ComplexValueDecoderMixin, DummyBase):
            pass

        decoder = TestDecoder()
        field_info = FieldInfo()
        assert decoder.decode_complex_value(
            "scout_target_urls", field_info, "https://a.com, https://b.com"
        ) == ["https://a.com", "https://b.com"]
        assert decoder.decode_complex_value("target_hashtags", field_info, "#python, ai") == [
            "#python",
            "ai",
        ]
        assert decoder.decode_complex_value("target_hashtags", field_info, '["#python", "ai"]') == [
            "#python",
            "ai",
        ]
        assert decoder.decode_complex_value("target_hashtags", field_info, "  ") == []

    def test_llm_provider_defaults_and_normalization(self) -> None:
        settings = Settings(
            nvidia_nim_api_key="nvapi-key",
            telegram_bot_token="123:ABC",
            telegram_authorized_chat_id=123,
        )
        assert settings.llm_provider == "nvidia"

        settings_openai = Settings(
            llm_provider="  OPENAI  ",
            openai_api_key="sk-test",
            telegram_bot_token="123:ABC",
            telegram_authorized_chat_id=123,
        )
        assert settings_openai.llm_provider == "openai"

    def test_llm_provider_unsupported_raises_config_error(self) -> None:
        with pytest.raises(ConfigError) as exc_info:
            load_settings(
                llm_provider="unsupported_backend",
                telegram_bot_token="123:ABC",
                telegram_authorized_chat_id=123,
            )
        assert "Unsupported LLM provider" in str(exc_info.value)

    def test_llm_provider_keys_and_endpoints(self) -> None:
        settings = Settings(
            llm_provider="openai",
            openai_api_key="sk-openai-123",
            anthropic_api_key="sk-ant-456",
            gemini_api_key="gm-789",
            groq_api_key="gsk-abc",
            ollama_base_url="http://custom-ollama:11434",
            telegram_bot_token="123:ABC",
            telegram_authorized_chat_id=123,
        )
        assert isinstance(settings.openai_api_key, SecretStr)
        assert settings.openai_api_key.get_secret_value() == "sk-openai-123"
        assert isinstance(settings.anthropic_api_key, SecretStr)
        assert settings.anthropic_api_key.get_secret_value() == "sk-ant-456"
        assert isinstance(settings.gemini_api_key, SecretStr)
        assert settings.gemini_api_key.get_secret_value() == "gm-789"
        assert isinstance(settings.groq_api_key, SecretStr)
        assert settings.groq_api_key.get_secret_value() == "gsk-abc"
        assert settings.ollama_base_url == "http://custom-ollama:11434"

    def test_provider_default_and_effective_models(self) -> None:
        providers_expected = {
            "openai": ("gpt-4o", "gpt-4o-mini", "gpt-4o-mini"),
            "anthropic": (
                "claude-3-5-sonnet-latest",
                "claude-3-5-haiku-latest",
                "claude-3-5-haiku-latest",
            ),
            "gemini": ("gemini-2.0-flash", "gemini-1.5-flash", "gemini-1.5-flash"),
            "groq": (
                "llama-3.3-70b-versatile",
                "llama-3.1-8b-instant",
                "llama-3.1-8b-instant",
            ),
            "ollama": ("llama3.2", "llama3.2", "llama3.2"),
        }

        for provider, (exp_primary, exp_fallback, exp_triage) in providers_expected.items():
            settings = Settings(
                llm_provider=provider,
                telegram_bot_token="123:ABC",
                telegram_authorized_chat_id=123,
            )
            assert settings.default_primary_model == exp_primary
            assert settings.default_fallback_model == exp_fallback
            assert settings.default_triage_model == exp_triage
            assert settings.effective_primary_model == exp_primary
            assert settings.effective_fallback_model == exp_fallback
            assert settings.effective_triage_model == exp_triage
            assert settings.get_model_for_role("generation") == exp_primary
            assert settings.get_model_for_role("fallback") == exp_fallback
            assert settings.get_model_for_role("triage") == exp_triage

    def test_provider_effective_models_override(self) -> None:
        settings = Settings(
            llm_provider="openai",
            nim_model_primary="gpt-4-turbo",
            nim_model_fallback="gpt-3.5-turbo",
            nim_model_triage="gpt-4o-mini",
            telegram_bot_token="123:ABC",
            telegram_authorized_chat_id=123,
        )
        assert settings.effective_primary_model == "gpt-4-turbo"
        assert settings.effective_fallback_model == "gpt-3.5-turbo"
        assert settings.effective_triage_model == "gpt-4o-mini"

    def test_get_api_key_for_provider(self) -> None:
        settings = Settings(
            llm_provider="anthropic",
            anthropic_api_key="sk-ant-test",
            openai_api_key="sk-open-test",
            telegram_bot_token="123:ABC",
            telegram_authorized_chat_id=123,
        )
        assert settings.get_api_key_for_provider() is not None
        assert (
            isinstance(settings.get_api_key_for_provider(), SecretStr)
            and settings.get_api_key_for_provider().get_secret_value() == "sk-ant-test"  # type: ignore[union-attr]
        )
        assert (
            isinstance(settings.get_api_key_for_provider("openai"), SecretStr)
            and settings.get_api_key_for_provider("openai").get_secret_value() == "sk-open-test"  # type: ignore[union-attr]
        )

    def test_load_multi_llm_settings_from_env(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("LLM_PROVIDER", "groq")
        monkeypatch.setenv("GROQ_API_KEY", "gsk-env-key")
        monkeypatch.setenv("LLM_MODEL_PRIMARY", "llama-3.3-70b-custom")
        monkeypatch.setenv("LLM_MODEL_FALLBACK", "llama-3.1-8b-custom")
        monkeypatch.setenv("LLM_MODEL_TRIAGE", "llama-3.1-8b-triage")
        monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "999:TOKEN")
        monkeypatch.setenv("TELEGRAM_AUTHORIZED_CHAT_ID", "555123")

        settings = load_settings()
        assert settings.llm_provider == "groq"
        assert isinstance(settings.groq_api_key, SecretStr)
        assert settings.groq_api_key.get_secret_value() == "gsk-env-key"
        assert settings.nim_model_primary == "llama-3.3-70b-custom"
        assert settings.nim_model_fallback == "llama-3.1-8b-custom"
        assert settings.nim_model_triage == "llama-3.1-8b-triage"
        assert settings.effective_primary_model == "llama-3.3-70b-custom"
        assert settings.effective_fallback_model == "llama-3.1-8b-custom"
        assert settings.effective_triage_model == "llama-3.1-8b-triage"

    def test_load_google_api_key_alias_from_env(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("LLM_PROVIDER", "gemini")
        monkeypatch.setenv("GOOGLE_API_KEY", "AIzaSyFakeGoogleKey")
        monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "999:TOKEN")
        monkeypatch.setenv("TELEGRAM_AUTHORIZED_CHAT_ID", "555123")

        settings = load_settings()
        assert settings.llm_provider == "gemini"
        assert isinstance(settings.gemini_api_key, SecretStr)
        assert settings.gemini_api_key.get_secret_value() == "AIzaSyFakeGoogleKey"

    def test_scout_engine_settings_defaults_and_env_overrides(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        defaults = Settings(
            nvidia_nim_api_key="nvapi-test-key",
            telegram_bot_token="123456:ABC",
            telegram_authorized_chat_id=123,
        )
        assert defaults.scout_scroll_screens == 2
        assert defaults.candidate_pool_multiplier == 3
        assert defaults.min_triage_confidence == 0.7

        monkeypatch.setenv("SCOUT_SCROLL_SCREENS", "4")
        monkeypatch.setenv("CANDIDATE_POOL_MULTIPLIER", "5")
        monkeypatch.setenv("MIN_TRIAGE_CONFIDENCE", "0.85")
        monkeypatch.setenv("NVIDIA_NIM_API_KEY", "nvapi-test-key")
        monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "123:TOKEN")
        monkeypatch.setenv("TELEGRAM_AUTHORIZED_CHAT_ID", "123")

        custom = load_settings()
        assert custom.scout_scroll_screens == 4
        assert custom.candidate_pool_multiplier == 5
        assert custom.min_triage_confidence == 0.85

