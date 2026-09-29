"""Runtime configuration loader and settings model.

Architecture Invariants:
- All runtime configuration flows through Settings.
- Validated via pydantic-settings.
- Missing or invalid configuration raises ConfigError.
"""

import json
from pathlib import Path
from typing import Any

from pydantic import AliasChoices, Field, SecretStr, ValidationError, field_validator
from pydantic.fields import FieldInfo
from pydantic_settings import (
    BaseSettings,
    DotEnvSettingsSource,
    EnvSettingsSource,
    PydanticBaseSettingsSource,
    SettingsConfigDict,
)

from agent.errors import ConfigError

COMPLEX_LIST_FIELDS: frozenset[str] = frozenset(
    {"user_focus_areas", "scout_target_urls", "target_hashtags"}
)


def _parse_raw_string_list(value: str) -> list[str]:
    """Parse a comma-separated or JSON list string into a list of non-empty stripped strings."""
    v_str = value.strip()
    if not v_str:
        return []
    if v_str.startswith("[") and v_str.endswith("]"):
        try:
            parsed = json.loads(v_str)
            if isinstance(parsed, list):
                return [
                    str(item).strip() for item in parsed if item is not None and str(item).strip()
                ]
        except json.JSONDecodeError:
            pass
    return [part.strip() for part in v_str.split(",") if part.strip()]


class ComplexValueDecoderMixin:
    """Mixin supporting comma-separated and JSON list parsing for complex settings fields."""

    def decode_complex_value(self, field_name: str, field_info: FieldInfo, value: Any) -> Any:
        if field_name.lower() in COMPLEX_LIST_FIELDS and isinstance(value, str):
            return _parse_raw_string_list(value)
        return super().decode_complex_value(field_name, field_info, value)  # type: ignore[misc]


class FlexibleEnvSettingsSource(ComplexValueDecoderMixin, EnvSettingsSource):
    """Env source supporting flexible list formats."""


class FlexibleDotEnvSettingsSource(ComplexValueDecoderMixin, DotEnvSettingsSource):
    """DotEnv source supporting flexible list formats."""


class Settings(BaseSettings):
    """Central configuration settings for the LinkedIn HITL Agent."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # NVIDIA NIM LLM Configuration
    nvidia_nim_api_key: SecretStr | str = Field(
        description="API key for NVIDIA NIM endpoints",
        validation_alias=AliasChoices("NVIDIA_NIM_API_KEY", "nvidia_nim_api_key"),
    )
    nim_model_primary: str = Field(
        default="nvidia/nemotron-3-super-120b-a12b",
        description="Primary model for comment and post drafting",
        validation_alias=AliasChoices("NIM_MODEL_PRIMARY", "nim_model_primary"),
    )
    nim_model_fallback: str = Field(
        default="openai/gpt-oss-20b",
        description="Fallback model if primary encounters rate limit or failure",
        validation_alias=AliasChoices("NIM_MODEL_FALLBACK", "nim_model_fallback"),
    )
    nim_model_triage: str | None = Field(
        default=None,
        description="Optional lightweight model dedicated to post triage",
        validation_alias=AliasChoices("NIM_MODEL_TRIAGE", "nim_model_triage"),
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

    @field_validator("nvidia_nim_api_key", "telegram_bot_token", mode="after")
    @classmethod
    def ensure_secret_str(cls, v: SecretStr | str) -> SecretStr:
        """Ensure secret fields are wrapped in SecretStr."""
        if isinstance(v, str):
            return SecretStr(v)
        return v

    @field_validator(
        "session_encryption_key",
        "linkedin_session_state_enc",
        "cloudflare_api_token",
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
        normalized: list[str] = []
        for tag in v:
            clean = tag.strip()
            while clean.startswith("#") or clean.startswith(" "):
                clean = clean.lstrip("#").strip()
            if clean and not set(clean).issubset({"#", " "}) and clean not in normalized:
                normalized.append(clean)
        return normalized

    @field_validator("scout_target_urls", mode="after")
    @classmethod
    def normalize_scout_target_urls(cls, v: list[str]) -> list[str]:
        """Normalize scout URLs: strip whitespace, filter empty entries, and deduplicate."""
        normalized: list[str] = []
        for url in v:
            clean = url.strip()
            if clean and clean not in normalized:
                normalized.append(clean)
        return normalized

    @property
    def effective_triage_model(self) -> str:
        """Return the effective model to use for triage."""
        return self.nim_model_triage or self.nim_model_primary


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
