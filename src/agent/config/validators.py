"""Field normalization and validation helper functions for configuration."""

from __future__ import annotations

from typing import Any

from agent.config.constants import SUPPORTED_LLM_PROVIDERS


def normalize_provider_name(v: Any) -> str:
    """Normalize and validate LLM provider name."""
    if isinstance(v, str):
        clean = v.strip().lower()
        if clean in SUPPORTED_LLM_PROVIDERS:
            return clean
        raise ValueError(
            f"Unsupported LLM provider '{v}'. Supported: {', '.join(sorted(SUPPORTED_LLM_PROVIDERS))}"
        )
    return "nvidia"


def normalize_target_hashtags_list(v: list[str]) -> list[str]:
    """Normalize hashtags: strip whitespace, strip leading '#', and filter empty entries."""
    normalized: list[str] = []
    for tag in v:
        clean = tag.strip()
        while clean.startswith("#") or clean.startswith(" "):
            clean = clean.lstrip("#").strip()
        if clean and not set(clean).issubset({"#", " "}) and clean not in normalized:
            normalized.append(clean)
    return normalized


def normalize_scout_target_urls_list(v: list[str]) -> list[str]:
    """Normalize scout URLs: strip whitespace, filter empty entries, and deduplicate."""
    normalized: list[str] = []
    for url in v:
        clean = url.strip()
        if clean and clean not in normalized:
            normalized.append(clean)
    return normalized
