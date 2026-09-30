"""Runtime configuration loader and settings model.

Architecture Invariants:
- All runtime configuration flows through Settings.
- Validated via pydantic-settings.
- Missing or invalid configuration raises ConfigError.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from pydantic import (
    AliasChoices,
    Field,
    SecretStr,
    ValidationError,
    field_validator,
    model_validator,
)
from pydantic_settings import (
    BaseSettings,
    PydanticBaseSettingsSource,
    SettingsConfigDict,
)

from agent.config.constants import (
    PROVIDER_DEFAULT_MODELS,
)
from agent.config.sources import (
    FlexibleDotEnvSettingsSource,
    FlexibleEnvSettingsSource,
    _parse_raw_string_list,
)
from agent.config.validators import (
    normalize_provider_name,
    normalize_scout_target_urls_list,
    normalize_target_hashtags_list,
)
from agent.errors import ConfigError


class Settings(BaseSettings):
    """Central configuration settings for the LinkedIn HITL Agent."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # LLM Provider Configuration
    llm_provider: str = Field(
        default="nvidia",
        description="LLM provider: nvidia, openai, anthropic, gemini, groq, ollama, openai-compatible",
        validation_alias=AliasChoices("LLM_PROVIDER", "llm_provider"),
    )

    # Multi-provider API keys and endpoints
    openai_api_key: SecretStr | str | None = Field(
        default=None,
        description="API key for OpenAI",
        validation_alias=AliasChoices("OPENAI_API_KEY", "openai_api_key"),
    )
    anthropic_api_key: SecretStr | str | None = Field(
        default=None,
        description="API key for Anthropic",
        validation_alias=AliasChoices("ANTHROPIC_API_KEY", "anthropic_api_key"),
    )
    gemini_api_key: SecretStr | str | None = Field(
        default=None,
        description="API key for Google Gemini",
        validation_alias=AliasChoices(
            "GEMINI_API_KEY", "gemini_api_key", "GOOGLE_API_KEY", "google_api_key"
        ),
    )
    groq_api_key: SecretStr | str | None = Field(
        default=None,
        description="API key for Groq",
        validation_alias=AliasChoices("GROQ_API_KEY", "groq_api_key"),
    )
    ollama_base_url: str = Field(
        default="http://localhost:11434",
        description="Base URL for Ollama service",
        validation_alias=AliasChoices("OLLAMA_BASE_URL", "ollama_base_url"),
    )

    # NVIDIA NIM LLM Configuration
    nvidia_nim_api_key: SecretStr | str | None = Field(
        default=None,
        description="API key for NVIDIA NIM endpoints",
        validation_alias=AliasChoices("NVIDIA_NIM_API_KEY", "nvidia_nim_api_key"),
    )
    nim_model_primary: str = Field(
        default="nvidia/nemotron-3-super-120b-a12b",
        description="Primary model for comment and post drafting",
        validation_alias=AliasChoices(
            "LLM_MODEL_PRIMARY", "llm_model_primary", "NIM_MODEL_PRIMARY", "nim_model_primary"
        ),
    )
    nim_model_fallback: str = Field(
        default="openai/gpt-oss-20b",
        description="Fallback model if primary encounters rate limit or failure",
        validation_alias=AliasChoices(
            "LLM_MODEL_FALLBACK", "llm_model_fallback", "NIM_MODEL_FALLBACK", "nim_model_fallback"
        ),
    )
    nim_model_triage: str | None = Field(
        default=None,
        description="Optional lightweight model dedicated to post triage",
        validation_alias=AliasChoices(
            "LLM_MODEL_TRIAGE", "llm_model_triage", "NIM_MODEL_TRIAGE", "nim_model_triage"
        ),
    )
    nim_temperature: float = Field(
        default=0.2,
        ge=0.0,
        le=2.0,
        description="Temperature for LLM generation",
        validation_alias=AliasChoices("NIM_TEMPERATURE", "nim_temperature"),
    )
    nim_top_p: float | None = Field(
        default=None,
        ge=0.0,
        le=1.0,
        description="Top-p sampling probability",
        validation_alias=AliasChoices("NIM_TOP_P", "nim_top_p"),
    )
    nim_timeout_seconds: float = Field(
        default=60.0,
        ge=1.0,
        description="Request timeout for NVIDIA NIM API calls in seconds",
        validation_alias=AliasChoices("NIM_TIMEOUT_SECONDS", "nim_timeout_seconds"),
    )
    nim_max_tokens: int = Field(
        default=1024,
        ge=1,
        description="Maximum tokens generated per NIM response",
        validation_alias=AliasChoices("NIM_MAX_TOKENS", "nim_max_tokens"),
    )
    nim_base_url: str | None = Field(
        default=None,
        description="Custom base URL for NVIDIA NIM endpoint",
        validation_alias=AliasChoices("NIM_BASE_URL", "nim_base_url"),
    )
    nim_max_concurrency: int = Field(
        default=4,
        ge=1,
        description="Maximum concurrent requests to NVIDIA NIM",
        validation_alias=AliasChoices("NIM_MAX_CONCURRENCY", "nim_max_concurrency"),
    )

    # Telegram Configuration
    telegram_bot_token: SecretStr | str = Field(
        description="Telegram bot token obtained from @BotFather",
        validation_alias=AliasChoices("TELEGRAM_BOT_TOKEN", "telegram_bot_token"),
    )
    telegram_authorized_chat_id: int = Field(
        description="Authorized Telegram user/chat ID permitted to approve actions",
        validation_alias=AliasChoices("TELEGRAM_AUTHORIZED_CHAT_ID", "telegram_authorized_chat_id"),
    )

    # LinkedIn Session & Encryption
    session_encryption_key: SecretStr | str | None = Field(
        default=None,
        description="Fernet 32-byte url-safe base64 key for encrypting storage state",
        validation_alias=AliasChoices("SESSION_ENCRYPTION_KEY", "session_encryption_key"),
    )
    linkedin_session_state_enc: SecretStr | str | None = Field(
        default=None,
        description="Base64 encrypted LinkedIn Playwright storage state string",
        validation_alias=AliasChoices("LINKEDIN_SESSION_STATE_ENC", "linkedin_session_state_enc"),
    )
    linkedin_storage_state_path: Path = Field(
        default=Path("storage_state.json"),
        description="Path to decrypted Playwright storage_state.json",
        validation_alias=AliasChoices("LINKEDIN_STORAGE_STATE_PATH", "linkedin_storage_state_path"),
    )

    # Persona & Focus Areas
    user_focus_areas: list[str] = Field(
        default_factory=list,
        description="Domain areas of interest for filtering and comment focus",
        validation_alias=AliasChoices("USER_FOCUS_AREAS", "user_focus_areas"),
    )
    # Targeted Scouting Configuration
    scout_target_urls: list[str] = Field(
        default_factory=list,
        description="Explicit LinkedIn feed URLs to scout (e.g. hashtag feeds, creator activity pages)",
        validation_alias=AliasChoices("SCOUT_TARGET_URLS", "scout_target_urls"),
    )
    target_hashtags: list[str] = Field(
        default_factory=list,
        description="Target LinkedIn hashtags to scout (e.g. ['python', 'ai', '#agentic'])",
        validation_alias=AliasChoices("TARGET_HASHTAGS", "target_hashtags"),
    )
    user_persona: str = Field(
        default="",
        description="User persona and professional background guidance for LLM generation",
        validation_alias=AliasChoices("USER_PERSONA", "user_persona"),
    )
    max_comment_words: int = Field(
        default=80,
        ge=10,
        le=200,
        description="Target maximum word count for drafted comments",
        validation_alias=AliasChoices("MAX_COMMENT_WORDS", "max_comment_words"),
    )

    # Safety, Rate Limits, and Operational Controls
    max_comments_per_day: int = Field(
        default=5,
        ge=0,
        description="Daily maximum allowed LinkedIn comments",
        validation_alias=AliasChoices("MAX_COMMENTS_PER_DAY", "max_comments_per_day"),
    )
    max_posts_per_day: int = Field(
        default=1,
        ge=0,
        description="Daily maximum allowed original LinkedIn posts",
        validation_alias=AliasChoices("MAX_POSTS_PER_DAY", "max_posts_per_day"),
    )
    max_connections_per_day: int = Field(
        default=10,
        ge=0,
        description="Daily maximum allowed LinkedIn connection requests",
        validation_alias=AliasChoices("MAX_CONNECTIONS_PER_DAY", "max_connections_per_day"),
    )
    max_suggestions_per_run: int = Field(
        default=3,
        ge=1,
        description="Maximum suggestions delivered to Telegram per scout run",
        validation_alias=AliasChoices("MAX_SUGGESTIONS_PER_RUN", "max_suggestions_per_run"),
    )
    pending_action_ttl_hours: int = Field(
        default=12,
        ge=1,
        description="Time-to-live for pending approvals in hours before expiration",
        validation_alias=AliasChoices("PENDING_ACTION_TTL_HOURS", "pending_action_ttl_hours"),
    )
    agent_paused: bool = Field(
        default=False,
        description="Safety kill switch: when True, all workflows pause without action",
        validation_alias=AliasChoices("AGENT_PAUSED", "agent_paused"),
    )
    dry_run: bool = Field(
        default=False,
        description="When True, prevents all live LinkedIn writes and logs actions",
        validation_alias=AliasChoices("DRY_RUN", "dry_run"),
    )
    enable_pre_comment_reaction: bool = Field(
        default=False,
        description="Whether to perform an organic reaction before commenting",
        validation_alias=AliasChoices("ENABLE_PRE_COMMENT_REACTION", "enable_pre_comment_reaction"),
    )
    default_reaction_type: str = Field(
        default="like",
        description="Default reaction type (like, insightful, celebrate, support, love, funny)",
        validation_alias=AliasChoices("DEFAULT_REACTION_TYPE", "default_reaction_type"),
    )
    log_level: str = Field(
        default="INFO",
        description="Logging level",
        validation_alias=AliasChoices("LOG_LEVEL", "log_level"),
    )
    state_dir: Path = Field(
        default=Path("state"),
        description="Path to version-controlled durable state directory",
        validation_alias=AliasChoices("STATE_DIR", "state_dir"),
    )

    # State Persistence Backend Configuration
    state_backend: str = Field(
        default="git",
        description="State storage backend: git, kv, or local",
        validation_alias=AliasChoices("STATE_BACKEND", "state_backend"),
    )
    cloudflare_account_id: str | None = Field(
        default=None,
        description="Cloudflare Account ID for KV state persistence",
        validation_alias=AliasChoices("CLOUDFLARE_ACCOUNT_ID", "cloudflare_account_id"),
    )
    cloudflare_kv_namespace_id: str | None = Field(
        default=None,
        description="Cloudflare KV Namespace ID for state persistence",
        validation_alias=AliasChoices("CLOUDFLARE_KV_NAMESPACE_ID", "cloudflare_kv_namespace_id"),
    )
    cloudflare_api_token: SecretStr | str | None = Field(
        default=None,
        description="Cloudflare API Token with Workers KV permissions",
        validation_alias=AliasChoices("CLOUDFLARE_API_TOKEN", "cloudflare_api_token"),
    )
    worker_url: str | None = Field(
        default=None,
        description="Cloudflare Worker base URL for remote state and R2 media vault",
        validation_alias=AliasChoices("WORKER_URL", "worker_url"),
    )
    desktop_api_secret: SecretStr | None = Field(
        default=None,
        description="Shared secret for authenticating with Cloudflare Worker API",
        validation_alias=AliasChoices("DESKTOP_API_SECRET", "desktop_api_secret"),
    )

    # Residential Proxy Gateway Configuration
    residential_proxy_url: SecretStr | None = Field(
        default=None,
        description="Residential proxy gateway URL (e.g. http://user:pass@host:port or socks5://...)",
        validation_alias=AliasChoices("RESIDENTIAL_PROXY_URL", "residential_proxy_url"),
    )
    proxy_sticky_session_id: str | None = Field(
        default=None,
        description="Optional session ID for sticky IP residential proxy routing",
        validation_alias=AliasChoices("PROXY_STICKY_SESSION_ID", "proxy_sticky_session_id"),
    )
    proxy_egress_timezone: str | None = Field(
        default=None,
        description="Timezone matching residential proxy egress location (e.g. America/New_York)",
        validation_alias=AliasChoices("PROXY_EGRESS_TIMEZONE", "proxy_egress_timezone"),
    )
    proxy_egress_locale: str | None = Field(
        default=None,
        description="Browser locale matching residential proxy egress location (e.g. en-US)",
        validation_alias=AliasChoices("PROXY_EGRESS_LOCALE", "proxy_egress_locale"),
    )

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls: type[BaseSettings],
        init_settings: PydanticBaseSettingsSource,
        env_settings: PydanticBaseSettingsSource,
        dotenv_settings: PydanticBaseSettingsSource,
        file_secret_settings: PydanticBaseSettingsSource,
    ) -> tuple[PydanticBaseSettingsSource, ...]:
        env_file = getattr(dotenv_settings, "env_file", ".env")
        env_file_encoding = getattr(dotenv_settings, "env_file_encoding", "utf-8")
        return (
            init_settings,
            FlexibleEnvSettingsSource(settings_cls),
            FlexibleDotEnvSettingsSource(
                settings_cls,
                env_file=env_file,
                env_file_encoding=env_file_encoding,
            ),
            file_secret_settings,
        )

    @field_validator("llm_provider", mode="before")
    @classmethod
    def normalize_provider(cls, v: Any) -> str:
        """Normalize and validate LLM provider name."""
        return normalize_provider_name(v)

    @model_validator(mode="after")
    def validate_provider_keys(self) -> Settings:
        """Validate that the required API key for the selected provider is supplied."""
        if self.llm_provider == "nvidia" and not self.nvidia_nim_api_key:
            raise ValueError("nvidia_nim_api_key is required when llm_provider is 'nvidia'")
        return self

    @field_validator("telegram_bot_token", mode="after")
    @classmethod
    def ensure_secret_str(cls, v: SecretStr | str) -> SecretStr:
        """Ensure secret fields are wrapped in SecretStr."""
        if isinstance(v, str):
            return SecretStr(v)
        return v

    @field_validator(
        "nvidia_nim_api_key",
        "session_encryption_key",
        "linkedin_session_state_enc",
        "openai_api_key",
        "anthropic_api_key",
        "gemini_api_key",
        "groq_api_key",
        "cloudflare_api_token",
        "residential_proxy_url",
        mode="after",
    )
    @classmethod
    def ensure_optional_secret_str(cls, v: SecretStr | str | None) -> SecretStr | None:
        """Ensure optional secret fields are wrapped in SecretStr."""
        if isinstance(v, str):
            return SecretStr(v)
        return v

    @field_validator("user_focus_areas", "scout_target_urls", "target_hashtags", mode="before")
    @classmethod
    def parse_string_list(cls, v: Any) -> list[str]:
        """Parse comma-separated string, JSON list, or list of strings into list[str]."""
        if isinstance(v, list):
            return [str(item).strip() for item in v if item is not None and str(item).strip()]
        if isinstance(v, str):
            return _parse_raw_string_list(v)
        return []

    # Preserve backward-compatible alias if referenced dynamically
    parse_user_focus_areas = parse_string_list

    @field_validator("target_hashtags", mode="after")
    @classmethod
    def normalize_target_hashtags(cls, v: list[str]) -> list[str]:
        """Normalize hashtags: strip whitespace, strip leading '#', and filter empty entries."""
        return normalize_target_hashtags_list(v)

    @field_validator("scout_target_urls", mode="after")
    @classmethod
    def normalize_scout_target_urls(cls, v: list[str]) -> list[str]:
        """Normalize scout URLs: strip whitespace, filter empty entries, and deduplicate."""
        return normalize_scout_target_urls_list(v)

    def get_default_models_for_provider(self, provider: str | None = None) -> dict[str, str]:
        """Return default primary, fallback, and triage models for the specified or current provider."""
        p = (provider or self.llm_provider).lower().strip()
        return PROVIDER_DEFAULT_MODELS.get(p, PROVIDER_DEFAULT_MODELS["nvidia"])

    @property
    def default_primary_model(self) -> str:
        """Default primary model for the configured LLM provider."""
        return self.get_default_models_for_provider()["primary"]

    @property
    def default_fallback_model(self) -> str:
        """Default fallback model for the configured LLM provider."""
        return self.get_default_models_for_provider()["fallback"]

    @property
    def default_triage_model(self) -> str:
        """Default triage model for the configured LLM provider."""
        return self.get_default_models_for_provider()["triage"]

    @property
    def effective_primary_model(self) -> str:
        """Effective primary model for the configured provider."""
        if (
            self.llm_provider != "nvidia"
            and self.nim_model_primary == PROVIDER_DEFAULT_MODELS["nvidia"]["primary"]
        ):
            return self.default_primary_model
        return self.nim_model_primary

    @property
    def effective_fallback_model(self) -> str:
        """Effective fallback model for the configured provider."""
        if (
            self.llm_provider != "nvidia"
            and self.nim_model_fallback == PROVIDER_DEFAULT_MODELS["nvidia"]["fallback"]
        ):
            return self.default_fallback_model
        return self.nim_model_fallback

    @property
    def effective_triage_model(self) -> str:
        """Return the effective model to use for triage."""
        if self.nim_model_triage:
            return self.nim_model_triage
        if (
            self.llm_provider != "nvidia"
            and self.nim_model_primary == PROVIDER_DEFAULT_MODELS["nvidia"]["primary"]
        ):
            return self.default_triage_model
        return self.effective_primary_model

    def get_model_for_role(self, role: str = "generation") -> str:
        """Return effective model name for a specific role ('generation', 'fallback', 'triage')."""
        if role == "triage":
            return self.effective_triage_model
        if role == "fallback":
            return self.effective_fallback_model
        return self.effective_primary_model

    def get_api_key_for_provider(self, provider: str | None = None) -> SecretStr | str | None:
        """Return the configured API key for the specified or current provider."""
        p = (provider or self.llm_provider).lower().strip()
        if p == "nvidia":
            return self.nvidia_nim_api_key
        if p == "openai":
            return self.openai_api_key
        if p == "anthropic":
            return self.anthropic_api_key
        if p == "gemini":
            return self.gemini_api_key
        if p == "groq":
            return self.groq_api_key
        if p == "openai-compatible":
            return self.openai_api_key or self.nvidia_nim_api_key
        return None


def load_settings(**kwargs: Any) -> Settings:
    """Load and validate settings from environment variables, .env file, and/or kwargs.

    Raises:
        ConfigError: If required settings are missing or values fail validation.
    """
    try:
        return Settings(**kwargs)
    except ValidationError as e:
        field_errors = []
        for error in e.errors():
            loc = ".".join(str(elem) for elem in error["loc"])
            field_errors.append(f"{loc}: {error['msg']}")
        msg = f"Configuration validation failed: {'; '.join(field_errors)}"
        raise ConfigError(msg, details={"errors": e.errors()}) from e
