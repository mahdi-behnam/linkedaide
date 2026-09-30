"""Custom settings sources and complex value decoders for configuration."""

from __future__ import annotations

import json
from typing import Any

from pydantic.fields import FieldInfo
from pydantic_settings import DotEnvSettingsSource, EnvSettingsSource

from agent.config.constants import COMPLEX_LIST_FIELDS


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
