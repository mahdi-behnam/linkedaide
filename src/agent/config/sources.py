"""Custom settings sources and complex value decoders for configuration."""

from __future__ import annotations

import json
from typing import Any

from pydantic.fields import FieldInfo
from pydantic_settings import (
    BaseSettings,
    DotEnvSettingsSource,
    EnvSettingsSource,
    PydanticBaseSettingsSource,
)

from agent.config.constants import COMPLEX_LIST_FIELDS
from agent.config.kv_loader import load_central_kv_settings


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


class AuthoritativeKVSettingsSource(ComplexValueDecoderMixin, PydanticBaseSettingsSource):
    """Authoritative settings source reading operational configuration and encrypted secrets from Cloudflare KV."""

    def __init__(self, settings_cls: type[BaseSettings]) -> None:
        super().__init__(settings_cls)
        self._data: dict[str, Any] | None = None

    def get_field_value(self, field: FieldInfo, field_name: str) -> tuple[Any, str, bool]:
        return None, field_name, False

    def __call__(self) -> dict[str, Any]:
        if self._data is not None:
            return self._data

        import os

        account_id = os.environ.get("CLOUDFLARE_ACCOUNT_ID") or os.environ.get(
            "cloudflare_account_id"
        )
        namespace_id = os.environ.get("CLOUDFLARE_KV_NAMESPACE_ID") or os.environ.get(
            "cloudflare_kv_namespace_id"
        )
        api_token = os.environ.get("CLOUDFLARE_API_TOKEN") or os.environ.get("cloudflare_api_token")
        encryption_key = os.environ.get("SESSION_ENCRYPTION_KEY") or os.environ.get(
            "session_encryption_key"
        )
        backend = (
            (os.environ.get("STATE_BACKEND") or os.environ.get("state_backend") or "")
            .lower()
            .strip()
        )

        # Strict KV mode: when explicitly configured to use KV backend
        is_strict = backend == "kv"

        raw_kv_data = load_central_kv_settings(
            account_id=account_id,
            namespace_id=namespace_id,
            api_token=api_token,
            encryption_key=encryption_key,
            strict=is_strict,
        )

        decoded: dict[str, Any] = {}
        for k, v in raw_kv_data.items():
            if isinstance(v, str) and k.lower() in COMPLEX_LIST_FIELDS:
                decoded[k] = _parse_raw_string_list(v)
            else:
                decoded[k] = v

        self._data = decoded
        return decoded
