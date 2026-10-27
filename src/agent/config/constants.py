"""Provider constants and complex field registries for configuration."""

from __future__ import annotations

COMPLEX_LIST_FIELDS: frozenset[str] = frozenset(
    {"user_focus_areas", "scout_target_urls", "target_hashtags"}
)

SUPPORTED_LLM_PROVIDERS: frozenset[str] = frozenset(
    {"nvidia", "openai", "anthropic", "gemini", "groq", "ollama", "openai-compatible"}
)
