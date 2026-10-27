"""Diagnostic check functions for doctor command."""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path
from typing import Any

import httpx
from cryptography.fernet import Fernet, InvalidToken
from pydantic import SecretStr

from agent.config import SUPPORTED_LLM_PROVIDERS, Settings, load_settings
from agent.doctor.runner import CheckResult
from agent.errors import ConfigError

# Module-level reference to support testing/mocking
sync_playwright: Any = None
_sync_playwright: Any = None
try:
    from playwright.sync_api import sync_playwright as _sp

    sync_playwright = _sp
    _sync_playwright = _sp
except ImportError:
    pass


def check_python_runtime() -> CheckResult:
    """Check Python version (requires >= 3.11)."""
    v = sys.version_info
    major = getattr(v, "major", v[0])
    minor = getattr(v, "minor", v[1])
    micro = getattr(v, "micro", v[2] if len(v) > 2 else 0)
    version_str = f"{major}.{minor}.{micro}"
    if (major, minor) < (3, 11):
        return CheckResult(
            name="Python Runtime",
            status="FAIL",
            message=f"Python {version_str} detected. Python >= 3.11 is required.",
        )
    return CheckResult(
        name="Python Runtime",
        status="PASS",
        message=f"Python {version_str} (>= 3.11 required)",
    )


def check_playwright_chromium() -> CheckResult:
    """Check Playwright package and Chromium browser installation."""
    global sync_playwright

    sp = sync_playwright
    if sp is None:
        try:
            from playwright.sync_api import sync_playwright as _sp

            sp = _sp
            sync_playwright = _sp
        except ImportError:
            return CheckResult(
                name="Playwright Chromium",
                status="FAIL",
                message="Playwright package is not installed",
                details="Run: uv add playwright && uv run playwright install chromium",
            )

    exec_path_str: str | None = None
    try:
        # If unpatched in Python 3.14+, use async_playwright for clean connection lifecycle
        if sp is _sync_playwright:
            from playwright.async_api import async_playwright

            async def _get_path() -> str:
                async with async_playwright() as ap:
                    return str(ap.chromium.executable_path)

            exec_path_str = asyncio.run(_get_path())
        else:
            with sp() as p:
                raw_path = getattr(p.chromium, "executable_path", None)
                exec_path_str = str(raw_path) if raw_path is not None else None

        if not exec_path_str:
            return CheckResult(
                name="Playwright Chromium",
                status="FAIL",
                message="Could not determine Chromium executable path",
                details="Run: uv run playwright install chromium",
            )
        exec_path = Path(exec_path_str)
        if exec_path.exists():
            return CheckResult(
                name="Playwright Chromium",
                status="PASS",
                message=f"Chromium executable found at {exec_path}",
            )
        return CheckResult(
            name="Playwright Chromium",
            status="FAIL",
            message=f"Chromium executable not found at {exec_path}",
            details="Run: uv run playwright install chromium",
        )
    except Exception as err:
        return CheckResult(
            name="Playwright Chromium",
            status="FAIL",
            message=f"Playwright check failed: {err}",
            details="Run: uv run playwright install chromium",
        )


def check_configuration(
    settings: Settings | None = None,
) -> tuple[CheckResult, Settings | None]:
    """Validate application configuration."""
    if settings is not None:
        return (
            CheckResult(
                name="Configuration",
                status="PASS",
                message="Configuration loaded and validated",
            ),
            settings,
        )

    try:
        loaded = load_settings()
        return (
            CheckResult(
                name="Configuration",
                status="PASS",
                message="Valid configuration loaded from environment/.env",
            ),
            loaded,
        )
    except ConfigError as err:
        return (
            CheckResult(
                name="Configuration",
                status="FAIL",
                message=f"Configuration validation failed: {err}",
                details="Run 'uv run agent setup' or inspect your .env file.",
            ),
            None,
        )
    except Exception as err:
        return (
            CheckResult(
                name="Configuration",
                status="FAIL",
                message=f"Unexpected error loading configuration: {err}",
                details="Run 'uv run agent setup' or inspect your .env file.",
            ),
            None,
        )


def check_llm_provider(settings: Settings | None, probe_connectivity: bool = True) -> CheckResult:
    """Verify LLM provider configuration and test chat model instantiation and connectivity."""
    if settings is None:
        return CheckResult(
            name="LLM Provider",
            status="FAIL",
            message="Skipped check: configuration is missing or invalid",
        )

    provider = settings.llm_provider.lower().strip()
    if provider not in SUPPORTED_LLM_PROVIDERS:
        return CheckResult(
            name="LLM Provider",
            status="FAIL",
            message=f"Unsupported LLM provider '{provider}'. Supported: {', '.join(sorted(SUPPORTED_LLM_PROVIDERS))}",
        )

    api_key = settings.get_api_key_for_provider()
    if provider != "ollama" and not api_key:
        return CheckResult(
            name="LLM Provider",
            status="FAIL",
            message=f"Missing API key for provider '{provider}'",
            details=f"Please configure {provider.upper()}_API_KEY or NVIDIA_NIM_API_KEY in .env",
        )

    try:
        from langchain_core.messages import HumanMessage

        from agent.llm.models import build_chat_model

        model = build_chat_model(settings)
        model_name = settings.effective_primary_model

        if probe_connectivity:
            try:
                # Active probe to verify model existence and endpoint credentials
                model.invoke([HumanMessage(content="ping")])
            except Exception as probe_err:
                err_str = str(probe_err)
                return CheckResult(
                    name="LLM Provider",
                    status="FAIL",
                    message=f"Model '{model_name}' failed probe on provider '{provider}': {err_str}",
                    details=f"The configured model returned an error ({err_str}). Please verify the model identifier and your API credentials in settings.",
                )

        return CheckResult(
            name="LLM Provider",
            status="PASS",
            message=f"Provider '{provider}' configured with model '{model_name}' ({type(model).__name__})",
        )
    except ImportError as err:
        return CheckResult(
            name="LLM Provider",
            status="FAIL",
            message=f"Missing dependency for provider '{provider}': {err}",
        )
    except Exception as err:
        return CheckResult(
            name="LLM Provider",
            status="FAIL",
            message=f"Failed to instantiate model for provider '{provider}': {err}",
        )


def check_telegram_bot(
    settings: Settings | None,
    client: httpx.Client | None = None,
) -> CheckResult:
    """Verify Telegram bot token by querying getMe endpoint."""
    if settings is None:
        return CheckResult(
            name="Telegram Bot",
            status="FAIL",
            message="Skipped check: configuration is missing or invalid",
        )

    raw_token = getattr(settings, "telegram_bot_token", None)
    token_str = (
        raw_token.get_secret_value() if isinstance(raw_token, SecretStr) else str(raw_token or "")
    )
    if not token_str or not token_str.strip():
        return CheckResult(
            name="Telegram Bot",
            status="FAIL",
            message="TELEGRAM_BOT_TOKEN is empty or not configured",
            details="Obtain a bot token from @BotFather on Telegram",
        )

    url = f"https://api.telegram.org/bot{token_str.strip()}/getMe"
    http_client = client or httpx.Client(timeout=10.0)
    try:
        resp = http_client.get(url)
        if resp.status_code == 200:
            data = resp.json()
            if data.get("ok"):
                result = data.get("result", {})
                username = result.get("username", "unknown")
                bot_name = result.get("first_name", "")
                name_str = f" ({bot_name})" if bot_name else ""
                return CheckResult(
                    name="Telegram Bot",
                    status="PASS",
                    message=f"Connected to @{username}{name_str}",
                )
            return CheckResult(
                name="Telegram Bot",
                status="FAIL",
                message=f"Telegram API response not ok: {data.get('description', 'Unknown error')}",
            )
        if resp.status_code in (401, 404):
            return CheckResult(
                name="Telegram Bot",
                status="FAIL",
                message=f"Invalid bot token (HTTP {resp.status_code})",
                details="Verify TELEGRAM_BOT_TOKEN obtained from @BotFather",
            )
        return CheckResult(
            name="Telegram Bot",
            status="FAIL",
            message=f"Telegram API returned HTTP {resp.status_code}",
            details=resp.text,
        )
    except Exception as err:
        return CheckResult(
            name="Telegram Bot",
            status="FAIL",
            message=f"Network error connecting to Telegram API: {err}",
        )
    finally:
        if client is None:
            http_client.close()


def check_state_backend(
    settings: Settings | None,
    repo_root: Path | None = None,
    client: httpx.Client | None = None,
) -> CheckResult:
    """Verify state persistence backend connectivity and write permissions."""
    if settings is None:
        return CheckResult(
            name="State Backend",
            status="FAIL",
            message="Skipped check: configuration is missing or invalid",
        )

    backend = settings.state_backend.lower().strip()
    has_kv_creds = bool(
        settings.cloudflare_account_id
        and settings.cloudflare_kv_namespace_id
        and settings.cloudflare_api_token
    )

    if backend == "kv" or has_kv_creds:
        account_id = settings.cloudflare_account_id
        namespace_id = settings.cloudflare_kv_namespace_id
        api_token = settings.cloudflare_api_token
        token_str = (
            api_token.get_secret_value()
            if isinstance(api_token, SecretStr)
            else str(api_token or "")
        )
        if not (account_id and namespace_id and token_str):
            return CheckResult(
                name="State Backend (Cloudflare KV)",
                status="FAIL",
                message="Cloudflare KV credentials incomplete (requires CLOUDFLARE_ACCOUNT_ID, CLOUDFLARE_KV_NAMESPACE_ID, and CLOUDFLARE_API_TOKEN)",
            )

        url = (
            f"https://api.cloudflare.com/client/v4/accounts/{account_id}"
            f"/storage/kv/namespaces/{namespace_id}/keys?limit=10"
        )
        headers = {
            "Authorization": f"Bearer {token_str}",
            "User-Agent": "LinkedIn-Agent-KV/1.0",
        }
        http_client = client or httpx.Client(timeout=10.0)
        try:
            resp = http_client.get(url, headers=headers)
            if resp.status_code == 200:
                data = resp.json()
                if data.get("success", False):
                    return CheckResult(
                        name="State Backend (Cloudflare KV)",
                        status="PASS",
                        message=f"Connected to Cloudflare KV namespace {namespace_id}",
                    )
                return CheckResult(
                    name="State Backend (Cloudflare KV)",
                    status="FAIL",
                    message=f"Cloudflare KV error: {data.get('errors')}",
                )
            return CheckResult(
                name="State Backend (Cloudflare KV)",
                status="FAIL",
                message=f"Cloudflare KV returned HTTP {resp.status_code}",
                details=resp.text,
            )
        except Exception as err:
            return CheckResult(
                name="State Backend (Cloudflare KV)",
                status="FAIL",
                message=f"Cloudflare KV connection error: {err}",
            )
        finally:
            if client is None:
                http_client.close()
    else:
        root = repo_root or Path.cwd()
        state_dir = (root / settings.state_dir).resolve()
        try:
            state_dir.mkdir(parents=True, exist_ok=True)
            test_file = state_dir / ".doctor_write_test"
            test_file.write_text("test", encoding="utf-8")
            test_file.unlink()
            return CheckResult(
                name="State Backend (Local/Git)",
                status="PASS",
                message=f"State directory writable at {state_dir}",
            )
        except Exception as err:
            return CheckResult(
                name="State Backend (Local/Git)",
                status="FAIL",
                message=f"Cannot write to state directory at {state_dir}: {err}",
            )


def check_linkedin_session(settings: Settings | None) -> CheckResult:
    """Verify presence and validity of LinkedIn session state or encrypted credentials."""
    if settings is None:
        return CheckResult(
            name="LinkedIn Session",
            status="FAIL",
            message="Skipped check: configuration is missing or invalid",
        )

    # 1. Plaintext storage_state.json check
    storage_path = Path(settings.linkedin_storage_state_path)
    if storage_path.exists() and storage_path.stat().st_size > 0:
        return CheckResult(
            name="LinkedIn Session",
            status="PASS",
            message=f"Decrypted session storage file found at {storage_path}",
        )

    # 2. Encrypted string and encryption key check
    enc_token = getattr(settings, "linkedin_session_state_enc", None)
    enc_key = getattr(settings, "session_encryption_key", None)
    token_str = (
        enc_token.get_secret_value() if isinstance(enc_token, SecretStr) else str(enc_token or "")
    )
    key_str = enc_key.get_secret_value() if isinstance(enc_key, SecretStr) else str(enc_key or "")

    if token_str.strip() and key_str.strip():
        try:
            f = Fernet(key_str.strip().encode("utf-8"))
            decrypted = f.decrypt(token_str.strip().encode("utf-8"))
            if decrypted:
                return CheckResult(
                    name="LinkedIn Session",
                    status="PASS",
                    message="Encrypted LinkedIn session verified and decryptable",
                )
        except InvalidToken:
            return CheckResult(
                name="LinkedIn Session",
                status="FAIL",
                message="Invalid SESSION_ENCRYPTION_KEY or corrupted LINKEDIN_SESSION_STATE_ENC",
                details="Re-extract session using: uv run python scripts/extract_linkedin_session.py",
            )
        except Exception as err:
            return CheckResult(
                name="LinkedIn Session",
                status="FAIL",
                message=f"Session decryption error: {err}",
            )

    return CheckResult(
        name="LinkedIn Session",
        status="WARN",
        message="LinkedIn session not configured (missing storage_state.json and LINKEDIN_SESSION_STATE_ENC)",
        details="Run 'uv run python scripts/extract_linkedin_session.py' to log in and save session.",
    )
