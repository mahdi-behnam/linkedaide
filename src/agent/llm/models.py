"""NVIDIA NIM Chat Model factory functions.

Architecture Invariants:
- Centralized model construction.
- No direct ChatNVIDIA instantiation scattered across the codebase.
- API keys are retrieved from SecretStr configuration.
"""

from typing import Any, Literal

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_nvidia_ai_endpoints import ChatNVIDIA
from pydantic import SecretStr

from agent.config import Settings


def build_chat_model(
    settings: Settings,
    *,
    role: Literal["triage", "generation", "fallback"] = "generation",
    model_name: str | None = None,
    **kwargs: Any,
) -> BaseChatModel:
    """Instantiate a ChatNVIDIA model configured for a specific operational role.

    Args:
        settings: Application runtime settings.
        role: Operational role determines default model selection.
        model_name: Explicit override for model name.
        **kwargs: Additional parameters forwarded to ChatNVIDIA (e.g. temperature override).

    Returns:
        Configured BaseChatModel instance.
    """
    if model_name:
        selected_model = model_name
    elif role == "triage":
        selected_model = settings.effective_triage_model
    elif role == "fallback":
        selected_model = settings.nim_model_fallback
    else:
        selected_model = settings.nim_model_primary

    temperature = kwargs.pop("temperature", settings.nim_temperature)
    max_tokens = kwargs.pop("max_tokens", settings.nim_max_tokens)
    timeout = kwargs.pop("timeout", settings.nim_timeout_seconds)
    top_p = kwargs.pop("top_p", settings.nim_top_p)

    api_key_str = (
        settings.nvidia_nim_api_key.get_secret_value()
        if isinstance(settings.nvidia_nim_api_key, SecretStr)
        else str(settings.nvidia_nim_api_key)
    )

    model_kwargs: dict[str, Any] = {
        "model": selected_model,
        "nvidia_api_key": api_key_str,
        "temperature": temperature,
        "max_completion_tokens": max_tokens,
        "timeout": timeout,
        **kwargs,
    }

    if settings.nim_base_url:
        model_kwargs["base_url"] = settings.nim_base_url

    if top_p is not None:
        model_kwargs["top_p"] = top_p

    return ChatNVIDIA(**model_kwargs)
