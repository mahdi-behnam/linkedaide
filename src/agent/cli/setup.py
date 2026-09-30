"""Interactive onboarding setup wizard for generating or updating .env configuration."""

from __future__ import annotations

import os
from collections.abc import Callable
from pathlib import Path

from cryptography.fernet import Fernet

from agent.config import SUPPORTED_LLM_PROVIDERS


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
    provider_choice = (
        input_func(f"Select LLM Provider (1-6 or name) [{current_provider}]: ").strip().lower()
    )
    selected_provider = provider_map.get(
        provider_choice, provider_choice if provider_choice else current_provider
    )
    if selected_provider not in SUPPORTED_LLM_PROVIDERS:
        print_func(
            f"Note: '{selected_provider}' is not in standard provider list, proceeding anyway."
        )
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
    backend_choice = (
        input_func(
            f"Select State Backend ('kv' for Cloudflare KV, 'git' for Local/Git) [{curr_backend}]: "
        )
        .strip()
        .lower()
    )
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
