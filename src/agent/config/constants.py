"""Provider constants and complex field registries for configuration."""

from __future__ import annotations

COMPLEX_LIST_FIELDS: frozenset[str] = frozenset(
    {"user_focus_areas", "scout_target_urls", "target_hashtags"}
)

SUPPORTED_LLM_PROVIDERS: frozenset[str] = frozenset(
    {"nvidia", "openai", "anthropic", "gemini", "groq", "ollama", "openai-compatible"}
)

PROVIDER_DEFAULT_MODELS: dict[str, dict[str, str]] = {
    "nvidia": {
        "primary": "nvidia/nemotron-3-ultra-550b-a55b",
        "fallback": "openai/gpt-oss-20b",
        "triage": "openai/gpt-oss-20b",
    },
    "openai": {
        "primary": "gpt-4o",
        "fallback": "gpt-4o-mini",
        "triage": "gpt-4o-mini",
    },
    "anthropic": {
        "primary": "claude-3-5-sonnet-latest",
        "fallback": "claude-3-5-haiku-latest",
        "triage": "claude-3-5-haiku-latest",
    },
    "gemini": {
        "primary": "gemini-2.0-flash",
        "fallback": "gemini-1.5-flash",
        "triage": "gemini-1.5-flash",
    },
    "groq": {
        "primary": "llama-3.3-70b-versatile",
        "fallback": "llama-3.1-8b-instant",
        "triage": "llama-3.1-8b-instant",
    },
    "ollama": {
        "primary": "llama3.2",
        "fallback": "llama3.2",
        "triage": "llama3.2",
    },
    "openai-compatible": {
        "primary": "default",
        "fallback": "default",
        "triage": "default",
    },
}
