"""Unified CLI tool for the LinkedIn HITL agent.

Provides diagnostic 'doctor', interactive 'setup' wizard,
and flow execution commands (scout, execute, health).
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import os
import sys
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

import httpx
from cryptography.fernet import Fernet, InvalidToken
from pydantic import SecretStr

from agent.config import SUPPORTED_LLM_PROVIDERS, Settings, load_settings
from agent.errors import ConfigError

logger = logging.getLogger("agent.cli")

CheckStatus = Literal["PASS", "WARN", "FAIL"]

# Module-level reference to support testing/mocking
sync_playwright: Any = None
try:
    from playwright.sync_api import sync_playwright as _sync_playwright

    sync_playwright = _sync_playwright
except ImportError:
    pass


@dataclass
class CheckResult:
    """Diagnostic check result."""

    name: str
    status: CheckStatus
    message: str
    details: str | None = None


def format_check_result(result: CheckResult) -> str:
    """Format check result with rich status symbol."""
    symbol = {
        "PASS": "🟢 Pass",
        "WARN": "🟡 Warning",
        "FAIL": "🔴 Fail",
    }[result.status]
    output = f"  [{symbol}] {result.name}: {result.message}"
    if result.details:
        output += f"\n         {result.details}"
    return output


# -----------------------------------------------------------------------------
# Diagnostic Checks for 'doctor'
# -----------------------------------------------------------------------------


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
    if sync_playwright is None:
        try:
            from playwright.sync_api import sync_playwright as sp

            sync_playwright = sp
        except ImportError:
            return CheckResult(
                name="Playwright Chromium",
                status="FAIL",
                message="Playwright package is not installed",
                details="Run: uv add playwright && uv run playwright install chromium",
            )

    try:
        # If unpatched in Python 3.14+, use async_playwright for clean connection lifecycle
        if sync_playwright is _sync_playwright:
            from playwright.async_api import async_playwright

            async def _get_path() -> str:
                async with async_playwright() as ap:
                    return str(ap.chromium.executable_path)

            exec_path_str = asyncio.run(_get_path())
        else:
            with sync_playwright() as p:
                exec_path_str = getattr(p.chromium, "executable_path", None)

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


def check_llm_provider(settings: Settings | None) -> CheckResult:
    """Verify LLM provider configuration and test chat model instantiation."""
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
        from agent.llm.models import build_chat_model

        model = build_chat_model(settings)
        model_name = settings.effective_primary_model
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
            f"/storage/kv/namespaces/{namespace_id}/keys?limit=1"
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
    key_str = (
        enc_key.get_secret_value() if isinstance(enc_key, SecretStr) else str(enc_key or "")
    )

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


def run_doctor(
    args: argparse.Namespace | None = None,
    settings: Settings | None = None,
    repo_root: Path | None = None,
    telegram_client: httpx.Client | None = None,
    kv_client: httpx.Client | None = None,
) -> int:
    """Run full diagnostic test suite and print rich status checklist.

    Returns:
        int: 0 if all checks pass or only warnings; 1 if any check fails.
    """
    root = repo_root or (Path(args.repo_root) if args and getattr(args, "repo_root", None) else None)

    print("\n=== LinkedIn HITL Agent Doctor Diagnostics ===\n")

    results: list[CheckResult] = []

    # 1. Python runtime
    results.append(check_python_runtime())

    # 2. Playwright Chromium
    results.append(check_playwright_chromium())

    # 3. Configuration validation
    cfg_result, resolved_settings = check_configuration(settings)
    results.append(cfg_result)

    # 4. LLM provider check
    results.append(check_llm_provider(resolved_settings))

    # 5. Telegram bot check
    results.append(check_telegram_bot(resolved_settings, client=telegram_client))

    # 6. State backend check
    results.append(check_state_backend(resolved_settings, repo_root=root, client=kv_client))

    # 7. LinkedIn session check
    results.append(check_linkedin_session(resolved_settings))

    # Display checklist
    for res in results:
        print(format_check_result(res))

    passed_count = sum(1 for r in results if r.status == "PASS")
    warn_count = sum(1 for r in results if r.status == "WARN")
    fail_count = sum(1 for r in results if r.status == "FAIL")

    print(
        f"\nResult: {passed_count} passed, {warn_count} warning(s), {fail_count} failed."
    )

    if fail_count > 0:
        print("🔴 Diagnostics failed. Please resolve the errors highlighted above.\n")
        return 1
    if warn_count > 0:
        print("🟡 Diagnostics completed with warnings. System is operational with caveats.\n")
        return 0
    print("🟢 All systems operational!\n")
    return 0


# -----------------------------------------------------------------------------
# Interactive Setup Wizard
# -----------------------------------------------------------------------------


def parse_dotenv_lines(content: str) -> list[tuple[str | None, str]]:
    """Parse .env lines preserving empty lines and comments.

    Returns a list of tuples (key, line). For comment or empty lines, key is None.
    """
    entries: list[tuple[str | None, str]] = []
    for line in content.splitlines(keepends=True):
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            entries.append((None, line))
            continue
        line_to_parse = stripped
        if line_to_parse.startswith("export "):
            line_to_parse = line_to_parse[7:].strip()
        if "=" in line_to_parse:
            key = line_to_parse.split("=", 1)[0].strip()
            entries.append((key, line))
        else:
            entries.append((None, line))
    return entries


def read_dotenv_vars(env_path: Path) -> dict[str, str]:
    """Read existing environment variables from .env file into a dictionary."""
    if not env_path.exists():
        return {}
    vars_dict: dict[str, str] = {}
    content = env_path.read_text(encoding="utf-8")
    for line in content.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if stripped.startswith("export "):
            stripped = stripped[7:].strip()
        if "=" in stripped:
            k, v = stripped.split("=", 1)
            k = k.strip()
            v = v.strip()
            if (v.startswith('"') and v.endswith('"')) or (v.startswith("'") and v.endswith("'")):
                v = v[1:-1]
            vars_dict[k] = v
    return vars_dict


def update_dotenv_file(env_path: Path, new_vars: dict[str, str]) -> None:
    """Update or append variables in .env without overwriting unrelated variables or comments."""
    if env_path.exists():
        content = env_path.read_text(encoding="utf-8")
        parsed = parse_dotenv_lines(content)
        updated_lines: list[str] = []
        handled_keys: set[str] = set()

        for key, raw_line in parsed:
            if key is not None and key in new_vars:
                val = new_vars[key]
                updated_lines.append(f"{key}={val}\n")
                handled_keys.add(key)
            else:
                updated_lines.append(raw_line)

        if updated_lines and not updated_lines[-1].endswith("\n"):
            updated_lines[-1] += "\n"

        for key, val in new_vars.items():
            if key not in handled_keys:
                updated_lines.append(f"{key}={val}\n")

        new_content = "".join(updated_lines)
    else:
        new_content = "".join(f"{k}={v}\n" for k, v in new_vars.items())

    env_path.parent.mkdir(parents=True, exist_ok=True)
    env_path.write_text(new_content, encoding="utf-8")
    if os.name != "nt":
        try:
            os.chmod(env_path, 0o600)
        except OSError:
            pass


def run_setup(
    env_path: Path = Path(".env"),
    input_func: Callable[[str], str] = input,
    print_func: Callable[..., None] = print,
) -> dict[str, str]:
    """Run interactive setup wizard to configure .env safely.

    Args:
        env_path: Path to the .env file.
        input_func: Function to obtain user input (defaults to built-in input).
        print_func: Function to display messages (defaults to built-in print).

    Returns:
        dict[str, str]: Updated dictionary of environment variables written to .env.
    """
    print_func("==================================================")
    print_func("   LinkedIn HITL Agent - Interactive Setup Wizard ")
    print_func("==================================================")

    existing = read_dotenv_vars(env_path)
    new_vars: dict[str, str] = {}

    # 1. LLM Provider
    print_func("\n--- 1. LLM Provider Configuration ---")
    provider_map = {
        "1": "nvidia",
        "2": "openai",
        "3": "anthropic",
        "4": "gemini",
        "5": "groq",
        "6": "ollama",
    }
    print_func("Available providers:")
    for num, name in provider_map.items():
        print_func(f"  [{num}] {name}")

    current_provider = existing.get("LLM_PROVIDER", "nvidia")
    provider_choice = input_func(
        f"Select LLM Provider (1-6 or name) [{current_provider}]: "
    ).strip().lower()
    selected_provider = provider_map.get(provider_choice, provider_choice if provider_choice else current_provider)
    if selected_provider not in SUPPORTED_LLM_PROVIDERS:
        print_func(f"Note: '{selected_provider}' is not in standard provider list, proceeding anyway.")
    new_vars["LLM_PROVIDER"] = selected_provider

    if selected_provider == "nvidia":
        curr_k = existing.get("NVIDIA_NIM_API_KEY", "")
        k = input_func(f"Enter NVIDIA NIM API Key (starts with nvapi-) [{curr_k}]: ").strip()
        new_vars["NVIDIA_NIM_API_KEY"] = k if k else curr_k
    elif selected_provider == "openai":
        curr_k = existing.get("OPENAI_API_KEY", "")
        k = input_func(f"Enter OpenAI API Key [{curr_k}]: ").strip()
        new_vars["OPENAI_API_KEY"] = k if k else curr_k
    elif selected_provider == "anthropic":
        curr_k = existing.get("ANTHROPIC_API_KEY", "")
        k = input_func(f"Enter Anthropic API Key [{curr_k}]: ").strip()
        new_vars["ANTHROPIC_API_KEY"] = k if k else curr_k
    elif selected_provider == "gemini":
        curr_k = existing.get("GEMINI_API_KEY", "")
        k = input_func(f"Enter Google Gemini API Key [{curr_k}]: ").strip()
        new_vars["GEMINI_API_KEY"] = k if k else curr_k
    elif selected_provider == "groq":
        curr_k = existing.get("GROQ_API_KEY", "")
        k = input_func(f"Enter Groq API Key [{curr_k}]: ").strip()
        new_vars["GROQ_API_KEY"] = k if k else curr_k
    elif selected_provider == "ollama":
        curr_u = existing.get("OLLAMA_BASE_URL", "http://localhost:11434")
        u = input_func(f"Enter Ollama Base URL [{curr_u}]: ").strip()
        new_vars["OLLAMA_BASE_URL"] = u if u else curr_u

    # 2. Telegram Bot Configuration
    print_func("\n--- 2. Telegram Bot Configuration ---")
    curr_tok = existing.get("TELEGRAM_BOT_TOKEN", "")
    t_tok = input_func(f"Enter Telegram Bot Token (from @BotFather) [{curr_tok}]: ").strip()
    new_vars["TELEGRAM_BOT_TOKEN"] = t_tok if t_tok else curr_tok

    curr_cid = existing.get("TELEGRAM_AUTHORIZED_CHAT_ID", "")
    t_cid = input_func(f"Enter Authorized Telegram Chat/User ID [{curr_cid}]: ").strip()
    new_vars["TELEGRAM_AUTHORIZED_CHAT_ID"] = t_cid if t_cid else curr_cid

    # 3. State Persistence Backend
    print_func("\n--- 3. State Persistence Backend ---")
    curr_backend = existing.get("STATE_BACKEND", "git")
    backend_choice = input_func(
        f"Select State Backend ('kv' for Cloudflare KV, 'git' for Local/Git) [{curr_backend}]: "
    ).strip().lower()
    backend = backend_choice if backend_choice else curr_backend
    new_vars["STATE_BACKEND"] = backend

    if backend == "kv":
        curr_acc = existing.get("CLOUDFLARE_ACCOUNT_ID", "")
        acc = input_func(f"Enter Cloudflare Account ID [{curr_acc}]: ").strip()
        new_vars["CLOUDFLARE_ACCOUNT_ID"] = acc if acc else curr_acc

        curr_ns = existing.get("CLOUDFLARE_KV_NAMESPACE_ID", "")
        ns = input_func(f"Enter Cloudflare KV Namespace ID [{curr_ns}]: ").strip()
        new_vars["CLOUDFLARE_KV_NAMESPACE_ID"] = ns if ns else curr_ns

        curr_tk = existing.get("CLOUDFLARE_API_TOKEN", "")
        tk = input_func(f"Enter Cloudflare API Token [{curr_tk}]: ").strip()
        new_vars["CLOUDFLARE_API_TOKEN"] = tk if tk else curr_tk

    # 4. Session Encryption Key
    print_func("\n--- 4. Session Encryption Key ---")
    curr_key = existing.get("SESSION_ENCRYPTION_KEY", "")
    if not curr_key:
        generated_key = Fernet.generate_key().decode("utf-8")
        print_func(f"Generated new Fernet 32-byte encryption key: {generated_key}")
        new_vars["SESSION_ENCRYPTION_KEY"] = generated_key
    else:
        print_func("Existing SESSION_ENCRYPTION_KEY preserved.")
        new_vars["SESSION_ENCRYPTION_KEY"] = curr_key

    # Write updates
    update_dotenv_file(env_path, new_vars)
    print_func(f"\nConfiguration successfully saved to {env_path.resolve()}")
    print_func("\nNext Steps:")
    print_func("  1. Verify diagnostics:  uv run agent doctor")
    print_func("  2. Extract session:     uv run python scripts/extract_linkedin_session.py")
    print_func("  3. Run dry scout test:  uv run agent scout --dry-run\n")

    return new_vars


# -----------------------------------------------------------------------------
# Orchestration Dispatchers
# -----------------------------------------------------------------------------


def run_scout(args: argparse.Namespace) -> int:
    """Execute LinkedIn scout workflow."""
    from agent.orchestration.scout_flow import run_scout_flow

    cfg = load_settings()
    if getattr(args, "dry_run", False):
        cfg = cfg.model_copy(update={"dry_run": True})

    headless = not getattr(args, "headed", False)
    try:
        result = asyncio.run(run_scout_flow(settings=cfg, headless=headless))
        if result.get("status") in ("halted_bot_detection", "scrape_error"):
            return 1
        return 0
    except Exception as err:
        print(f"Fatal Scout error: {err}", file=sys.stderr)
        return 1


def run_execute(args: argparse.Namespace) -> int:
    """Execute approval or rejection dispatch flow."""
    from agent.orchestration.execute_flow import run_execute_flow

    try:
        result = asyncio.run(
            run_execute_flow(
                action=getattr(args, "action", None),
                item_id=getattr(args, "item_id", None),
                telegram_chat_id=getattr(args, "chat_id", None),
                telegram_message_id=getattr(args, "message_id", None),
                telegram_callback_query_id=getattr(args, "callback_query_id", None),
            )
        )
        if result.get("status") in ("failed", "halted_challenge", "session_error"):
            return 1
        return 0
    except Exception as err:
        print(f"Fatal Execute error: {err}", file=sys.stderr)
        return 1


def run_health(args: argparse.Namespace) -> int:
    """Execute LinkedIn session health check canary."""
    from agent.orchestration.health_check_flow import run_health_check_flow

    repo_root = Path(args.repo_root) if getattr(args, "repo_root", None) else None
    try:
        result = asyncio.run(run_health_check_flow(repo_root=repo_root))
        if not result.get("is_healthy", False):
            return 1
        return 0
    except Exception as err:
        print(f"Fatal Health Check error: {err}", file=sys.stderr)
        return 1


# -----------------------------------------------------------------------------
# Parser Construction and Entrypoint
# -----------------------------------------------------------------------------


def build_parser() -> argparse.ArgumentParser:
    """Build the top-level CLI parser."""
    parser = argparse.ArgumentParser(
        prog="agent",
        description="Unified CLI for the LinkedIn Human-in-the-Loop Agent",
    )
    subparsers = parser.add_subparsers(dest="command", help="Available subcommands")

    # doctor
    doctor_parser = subparsers.add_parser(
        "doctor", help="Run comprehensive diagnostic suite and environment checks"
    )
    doctor_parser.add_argument(
        "--repo-root", default=None, help="Root repository path"
    )

    # setup
    setup_parser = subparsers.add_parser(
        "setup", help="Interactive onboarding setup wizard"
    )
    setup_parser.add_argument(
        "--env-file", default=".env", help="Path to .env file to update (default: .env)"
    )

    # scout
    scout_parser = subparsers.add_parser(
        "scout", help="Run the LinkedIn feed scout workflow"
    )
    scout_parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Execute in dry-run mode (prevents live LinkedIn writes)",
    )
    scout_parser.add_argument(
        "--headed",
        action="store_true",
        help="Launch visible Chromium browser window for local inspection",
    )

    # execute
    execute_parser = subparsers.add_parser(
        "execute", help="Run the execute workflow for approved or rejected actions"
    )
    execute_parser.add_argument(
        "--action", choices=["approve", "reject"], default=None, help="Action to execute"
    )
    execute_parser.add_argument(
        "--item-id", default=None, help="Unique item ID for pending action"
    )
    execute_parser.add_argument(
        "--chat-id", type=int, default=None, help="Telegram chat ID"
    )
    execute_parser.add_argument(
        "--message-id", type=int, default=None, help="Telegram message ID"
    )
    execute_parser.add_argument(
        "--callback-query-id", default=None, help="Telegram callback query ID"
    )

    # health
    health_parser = subparsers.add_parser(
        "health", help="Run read-only session health check canary"
    )
    health_parser.add_argument(
        "--repo-root", default=None, help="Repository root path"
    )

    return parser


def main(argv: list[str] | None = None) -> None:
    """CLI main entrypoint."""
    parser = build_parser()
    args = parser.parse_args(argv)

    if not args.command:
        parser.print_help()
        sys.exit(0)

    exit_code = 0
    if args.command == "doctor":
        exit_code = run_doctor(args)
    elif args.command == "setup":
        run_setup(env_path=Path(getattr(args, "env_file", ".env")))
        exit_code = 0
    elif args.command == "scout":
        exit_code = run_scout(args)
    elif args.command == "execute":
        exit_code = run_execute(args)
    elif args.command == "health":
        exit_code = run_health(args)
    else:
        parser.print_help()
        exit_code = 1

    sys.exit(exit_code)


if __name__ == "__main__":
    main()
