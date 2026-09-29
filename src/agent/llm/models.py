"""Chat Model factory functions for multi-provider LLM support.

Architecture Invariants:
- Centralized model construction.
- Dynamic construction of provider chat models (NVIDIA, OpenAI, Anthropic, Gemini, Groq, Ollama, OpenAI-compatible).
- Safe dynamic imports with actionable error messages when optional provider packages are missing.
- API keys are retrieved securely from SecretStr configuration.
"""

from typing import Any, Literal

from langchain_core.language_models.chat_models import BaseChatModel
from pydantic import SecretStr

from agent.config import SUPPORTED_LLM_PROVIDERS, Settings

# Module-level references to support direct test patching (e.g. patch("agent.llm.models.ChatNVIDIA"))
ChatNVIDIA: Any = None
ChatOpenAI: Any = None
ChatAnthropic: Any = None
ChatGoogleGenerativeAI: Any = None
ChatGroq: Any = None
ChatOllama: Any = None

try:
    from langchain_nvidia_ai_endpoints import ChatNVIDIA as _ChatNVIDIA

    ChatNVIDIA = _ChatNVIDIA
except ImportError:
    pass

try:
    from langchain_openai import ChatOpenAI as _ChatOpenAI

    ChatOpenAI = _ChatOpenAI
except ImportError:
    pass

try:
    from langchain_anthropic import ChatAnthropic as _ChatAnthropic

    ChatAnthropic = _ChatAnthropic
except ImportError:
    pass

try:
    from langchain_google_genai import ChatGoogleGenerativeAI as _ChatGoogleGenerativeAI

    ChatGoogleGenerativeAI = _ChatGoogleGenerativeAI
except ImportError:
    pass

try:
    from langchain_groq import ChatGroq as _ChatGroq

    ChatGroq = _ChatGroq
except ImportError:
    pass

try:
    from langchain_ollama import ChatOllama as _ChatOllama

    ChatOllama = _ChatOllama
except ImportError:
    pass


def _resolve_chat_nvidia() -> type:
    """Resolve and return ChatNVIDIA class or raise friendly ImportError."""
    if ChatNVIDIA is not None:
        return ChatNVIDIA  # type: ignore[no-any-return]
    try:
        from langchain_nvidia_ai_endpoints import ChatNVIDIA as cls

        return cls
    except ImportError as e:
        raise ImportError(
            "To use NVIDIA NIM, install langchain-nvidia-ai-endpoints: uv add langchain-nvidia-ai-endpoints"
        ) from e


def _resolve_chat_openai() -> type:
    """Resolve and return ChatOpenAI class or raise friendly ImportError."""
    if ChatOpenAI is not None:
        return ChatOpenAI  # type: ignore[no-any-return]
    try:
        from langchain_openai import ChatOpenAI as cls

        return cls
    except ImportError as e:
        raise ImportError(
            "To use OpenAI or OpenAI-compatible endpoints, install langchain-openai: uv add langchain-openai"
        ) from e


def _resolve_chat_anthropic() -> type:
    """Resolve and return ChatAnthropic class or raise friendly ImportError."""
    if ChatAnthropic is not None:
        return ChatAnthropic  # type: ignore[no-any-return]
    try:
        from langchain_anthropic import ChatAnthropic as cls

        return cls
    except ImportError as e:
        raise ImportError(
            "To use Anthropic, install langchain-anthropic: uv add langchain-anthropic"
        ) from e


def _resolve_chat_gemini() -> type:
    """Resolve and return ChatGoogleGenerativeAI class or raise friendly ImportError."""
    if ChatGoogleGenerativeAI is not None:
        return ChatGoogleGenerativeAI  # type: ignore[no-any-return]
    try:
        from langchain_google_genai import ChatGoogleGenerativeAI as cls

        return cls
    except ImportError as e:
        raise ImportError(
            "To use Google Gemini, install langchain-google-genai: uv add langchain-google-genai"
        ) from e


def _resolve_chat_groq() -> type:
    """Resolve and return ChatGroq class or raise friendly ImportError."""
    if ChatGroq is not None:
        return ChatGroq  # type: ignore[no-any-return]
    try:
        from langchain_groq import ChatGroq as cls

        return cls
    except ImportError as e:
        raise ImportError("To use Groq, install langchain-groq: uv add langchain-groq") from e


def _resolve_chat_ollama() -> type:
    """Resolve and return ChatOllama class or raise friendly ImportError."""
    if ChatOllama is not None:
        return ChatOllama  # type: ignore[no-any-return]
    try:
        from langchain_ollama import ChatOllama as cls

        return cls
    except ImportError as e:
        raise ImportError("To use Ollama, install langchain-ollama: uv add langchain-ollama") from e


def build_chat_model(
    settings: Settings,
    *,
    role: Literal["triage", "generation", "fallback"] = "generation",
    model_name: str | None = None,
    **kwargs: Any,
) -> BaseChatModel:
    """Instantiate a LangChain chat model configured for a specific operational role and provider.

    Args:
        settings: Application runtime settings.
        role: Operational role determines default model selection ('generation', 'triage', 'fallback').
        model_name: Explicit override for model name.
        **kwargs: Additional parameters forwarded to the model constructor (e.g. temperature override).

    Returns:
        Configured BaseChatModel instance.
    """
    provider = settings.llm_provider.lower().strip()
    selected_model = model_name or settings.get_model_for_role(role)

    temperature = kwargs.pop("temperature", settings.nim_temperature)
    max_tokens = kwargs.pop("max_tokens", settings.nim_max_tokens)
    timeout = kwargs.pop("timeout", settings.nim_timeout_seconds)
    top_p = kwargs.pop("top_p", settings.nim_top_p)

    if provider == "nvidia":
        cls = _resolve_chat_nvidia()
        api_key = settings.nvidia_nim_api_key
        api_key_str = (
            api_key.get_secret_value()
            if isinstance(api_key, SecretStr)
            else (str(api_key) if api_key else "")
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
        return cls(**model_kwargs)

    if provider in ("openai", "openai-compatible"):
        cls = _resolve_chat_openai()
        api_key = settings.openai_api_key or (
            settings.nvidia_nim_api_key if provider == "openai-compatible" else None
        )
        api_key_str = (
            api_key.get_secret_value()
            if isinstance(api_key, SecretStr)
            else (str(api_key) if api_key else None)
        )
        model_kwargs = {
            "model": selected_model,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "timeout": timeout,
            **kwargs,
        }
        if api_key_str:
            model_kwargs["api_key"] = api_key_str
        if settings.nim_base_url:
            model_kwargs["base_url"] = settings.nim_base_url
        if top_p is not None:
            model_kwargs["top_p"] = top_p
        return cls(**model_kwargs)

    if provider == "anthropic":
        cls = _resolve_chat_anthropic()
        api_key = settings.anthropic_api_key
        api_key_str = (
            api_key.get_secret_value()
            if isinstance(api_key, SecretStr)
            else (str(api_key) if api_key else None)
        )
        model_kwargs = {
            "model": selected_model,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "timeout": timeout,
            **kwargs,
        }
        if api_key_str:
            model_kwargs["api_key"] = api_key_str
        if top_p is not None:
            model_kwargs["top_p"] = top_p
        return cls(**model_kwargs)

    if provider == "gemini":
        cls = _resolve_chat_gemini()
        api_key = settings.gemini_api_key
        api_key_str = (
            api_key.get_secret_value()
            if isinstance(api_key, SecretStr)
            else (str(api_key) if api_key else None)
        )
        model_kwargs = {
            "model": selected_model,
            "temperature": temperature,
            "max_output_tokens": max_tokens,
            "timeout": timeout,
            **kwargs,
        }
        if api_key_str:
            model_kwargs["google_api_key"] = api_key_str
        if top_p is not None:
            model_kwargs["top_p"] = top_p
        return cls(**model_kwargs)

    if provider == "groq":
        cls = _resolve_chat_groq()
        api_key = settings.groq_api_key
        api_key_str = (
            api_key.get_secret_value()
            if isinstance(api_key, SecretStr)
            else (str(api_key) if api_key else None)
        )
        model_kwargs = {
            "model": selected_model,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "timeout": timeout,
            **kwargs,
        }
        if api_key_str:
            model_kwargs["groq_api_key"] = api_key_str
        if top_p is not None:
            model_kwargs["top_p"] = top_p
        return cls(**model_kwargs)

    if provider == "ollama":
        cls = _resolve_chat_ollama()
        model_kwargs = {
            "model": selected_model,
            "base_url": settings.ollama_base_url,
            "temperature": temperature,
            **kwargs,
        }
        if top_p is not None:
            model_kwargs["top_p"] = top_p
        return cls(**model_kwargs)

    raise ValueError(
        f"Unsupported LLM provider '{provider}'. Supported: {', '.join(sorted(SUPPORTED_LLM_PROVIDERS))}"
    )


__all__ = [
    "ChatAnthropic",
    "ChatGoogleGenerativeAI",
    "ChatGroq",
    "ChatNVIDIA",
    "ChatOllama",
    "ChatOpenAI",
    "build_chat_model",
]
