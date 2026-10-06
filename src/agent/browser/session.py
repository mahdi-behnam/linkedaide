"""Playwright storage_state encryption and decryption at rest."""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path
from typing import TYPE_CHECKING, Any
from urllib.parse import unquote, urlsplit

from cryptography.fernet import Fernet, InvalidToken
from pydantic import SecretStr

from agent.browser.stealth import new_stealth_context
from agent.errors import SessionError

if TYPE_CHECKING:
    from playwright.async_api import Browser, BrowserContext

    from agent.config import Settings


def generate_encryption_key() -> str:
    """Generate a fresh URL-safe base64 32-byte Fernet key."""
    return Fernet.generate_key().decode("utf-8")


def encrypt_storage_state(raw_json: bytes, key: SecretStr | str) -> str:
    """Encrypt raw storage_state JSON bytes.

    Args:
        raw_json: Raw bytes of Playwright storage_state.json.
        key: Fernet key (SecretStr or string).

    Returns:
        str: Base64-encoded ciphertext string.
    """
    key_str = key.get_secret_value() if isinstance(key, SecretStr) else key
    try:
        f = Fernet(key_str.encode("utf-8") if isinstance(key_str, str) else key_str)
        token = f.encrypt(raw_json)
        return token.decode("utf-8")
    except Exception as err:
        raise SessionError(f"Failed to encrypt storage state: {err}") from err


def decrypt_storage_state(ciphertext_b64: str, key: SecretStr | str, out_path: Path) -> Path:
    """Decrypt base64 ciphertext and write to out_path with restricted permissions.

    Args:
        ciphertext_b64: Base64-encoded encrypted token string.
        key: Fernet key (SecretStr or string).
        out_path: Path where decrypted storage_state.json should be written.

    Returns:
        Path: The path to the decrypted file.

    Raises:
        SessionError: If decryption fails due to invalid key, corrupted token, or IO failure.
    """
    if not ciphertext_b64 or not ciphertext_b64.strip():
        raise SessionError("Empty or missing LinkedIn session ciphertext")

    key_str = key.get_secret_value() if isinstance(key, SecretStr) else key
    if not key_str or not key_str.strip():
        raise SessionError("Empty or missing session encryption key")

    try:
        f = Fernet(key_str.strip().encode("utf-8"))
        decrypted_bytes = f.decrypt(ciphertext_b64.strip().encode("utf-8"))
    except InvalidToken as err:
        raise SessionError(
            "Session decryption failed: Invalid encryption key or corrupted session data"
        ) from err
    except Exception as err:
        raise SessionError(f"Unexpected session decryption failure: {err}") from err

    try:
        out_path = Path(out_path).resolve()
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_bytes(decrypted_bytes)

        # Set restrictive permissions on POSIX runners
        if os.name != "nt":
            try:
                os.chmod(out_path, 0o600)
            except OSError:
                pass

        return out_path
    except Exception as err:
        raise SessionError(f"Failed to write decrypted session file to {out_path}: {err}") from err


def ensure_session_file(settings: Settings | Any) -> Path:
    """Ensure a valid decrypted storage_state.json exists on disk, auto-decrypting if needed.

    Args:
        settings: Settings instance containing storage state path and encryption keys.

    Returns:
        Path: Path to decrypted storage_state.json.

    Raises:
        SessionError: If no valid session file exists and credentials cannot decrypt one.
    """
    target_path = Path(settings.linkedin_storage_state_path).resolve()
    if target_path.exists() and target_path.stat().st_size > 0:
        return target_path

    # Attempt auto-decryption if ciphertext and key are present in settings
    enc_token = getattr(settings, "linkedin_session_state_enc", None)
    enc_key = getattr(settings, "session_encryption_key", None)

    if enc_token and enc_key:
        token_str = (
            enc_token.get_secret_value() if isinstance(enc_token, SecretStr) else str(enc_token)
        )
        key_str = enc_key.get_secret_value() if isinstance(enc_key, SecretStr) else str(enc_key)
        if token_str and key_str and token_str.strip() and key_str.strip():
            return decrypt_storage_state(token_str.strip(), key_str.strip(), target_path)

    raise SessionError(
        f"LinkedIn session state not found at '{settings.linkedin_storage_state_path}' and "
        "LINKEDIN_SESSION_STATE_ENC / SESSION_ENCRYPTION_KEY are not configured. "
        "Please run 'uv run python scripts/extract_linkedin_session.py' to extract and save your session."
    )


def check_session_expiry(
    storage_state_or_path: Path | str | dict[str, Any],
    warning_days: int = 3,
) -> dict[str, Any]:
    """Inspect Playwright storage state for LinkedIn authentication cookie expiry.

    Args:
        storage_state_or_path: Path to decrypted storage_state.json or parsed dictionary.
        warning_days: Days remaining threshold to flag as expiring soon.

    Returns:
        dict[str, Any]: {
            "has_cookie": bool,
            "expires_at": float | None,
            "days_remaining": float | None,
            "is_expiring_soon": bool,
        }
    """
    default_result: dict[str, Any] = {
        "has_cookie": False,
        "expires_at": None,
        "days_remaining": None,
        "is_expiring_soon": False,
    }

    data: dict[str, Any]
    if isinstance(storage_state_or_path, dict):
        data = storage_state_or_path
    else:
        path = Path(storage_state_or_path).resolve()
        if not path.exists():
            return default_result
        try:
            content = path.read_text(encoding="utf-8")
            data = json.loads(content)
        except Exception:
            return default_result

    cookies = data.get("cookies", [])
    if not isinstance(cookies, list):
        return default_result

    li_at_cookie = next(
        (c for c in cookies if isinstance(c, dict) and c.get("name") == "li_at"),
        None,
    )
    if not li_at_cookie:
        return default_result

    expires = li_at_cookie.get("expires")
    if expires is None:
        return {
            "has_cookie": True,
            "expires_at": None,
            "days_remaining": None,
            "is_expiring_soon": False,
        }

    try:
        exp_float = float(expires)
        if exp_float > 1e11:  # Milliseconds timestamp
            exp_float = exp_float / 1000.0
        now = time.time()
        seconds_left = exp_float - now
        days_remaining = max(0.0, seconds_left / 86400.0)
        is_expiring_soon = 0.0 < days_remaining <= float(warning_days)

        return {
            "has_cookie": True,
            "expires_at": exp_float,
            "days_remaining": round(days_remaining, 2),
            "is_expiring_soon": is_expiring_soon,
        }
    except (ValueError, TypeError):
        return {
            "has_cookie": True,
            "expires_at": None,
            "days_remaining": None,
            "is_expiring_soon": False,
        }


def build_proxy_config(settings: Settings | Any) -> dict[str, str] | None:
    """Parse residential proxy configuration into a Playwright proxy dictionary.

    Args:
        settings: Settings instance containing residential proxy attributes.

    Returns:
        dict[str, str] | None: Playwright-compatible proxy configuration dictionary, or None.
    """
    raw_proxy = getattr(settings, "residential_proxy_url", None)
    if not raw_proxy:
        return None

    url_str = (
        raw_proxy.get_secret_value() if isinstance(raw_proxy, SecretStr) else str(raw_proxy)
    ).strip()
    if not url_str:
        return None

    parsed = urlsplit(url_str)
    if not parsed.scheme or not parsed.hostname:
        return None

    server = f"{parsed.scheme}://{parsed.hostname}"
    if parsed.port:
        server = f"{server}:{parsed.port}"

    proxy_dict: dict[str, str] = {"server": server}

    username = unquote(parsed.username) if parsed.username else None
    password = unquote(parsed.password) if parsed.password else None

    sticky_id = getattr(settings, "proxy_sticky_session_id", None)
    if username is not None:
        if sticky_id:
            username = f"{username}-session-{sticky_id}"
        proxy_dict["username"] = username

    if password is not None:
        proxy_dict["password"] = password

    return proxy_dict


async def create_browser_context(
    browser: Browser,
    settings: Settings | Any,
    storage_state_path: Path | None = None,
    **kwargs: Any,
) -> BrowserContext:
    """Create a Playwright browser context with proxy routing, stealth defaults, and geo-alignment.

    Args:
        browser: Playwright Browser instance.
        settings: Agent Settings configuration.
        storage_state_path: Optional path to decrypted storage_state.json.
        **kwargs: Additional context options.

    Returns:
        BrowserContext: Configured browser context.
    """
    context_options: dict[str, Any] = dict(kwargs)

    # 1. Residential proxy gateway routing
    proxy_config = build_proxy_config(settings)
    if proxy_config and "proxy" not in context_options:
        context_options["proxy"] = proxy_config

    # 2. Timezone alignment (avoids timezone geo-mismatch detection)
    egress_tz = getattr(settings, "proxy_egress_timezone", None)
    if egress_tz and "timezone_id" not in context_options:
        context_options["timezone_id"] = egress_tz

    # 3. Locale alignment (avoids browser accept-language geo-mismatch detection)
    egress_locale = getattr(settings, "proxy_egress_locale", None)
    if egress_locale and "locale" not in context_options:
        context_options["locale"] = egress_locale

    return await new_stealth_context(
        browser=browser,
        storage_state_path=storage_state_path,
        **context_options,
    )


def main() -> None:
    """CLI entrypoint for decrypting session state in CI workflows."""
    parser = argparse.ArgumentParser(description="Decrypt LinkedIn Playwright storage state")
    subparsers = parser.add_subparsers(dest="command")

    decrypt_parser = subparsers.add_parser("decrypt", help="Decrypt session state")
    decrypt_parser.add_argument(
        "--out", required=True, help="Output path for decrypted storage_state.json"
    )

    args = parser.parse_args()

    if args.command == "decrypt":
        key = os.environ.get("SESSION_ENCRYPTION_KEY")
        ciphertext = os.environ.get("LINKEDIN_SESSION_STATE_ENC")

        if not key or not ciphertext:
            print(
                "Error: Missing SESSION_ENCRYPTION_KEY or LINKEDIN_SESSION_STATE_ENC env vars",
                file=sys.stderr,
            )
            sys.exit(1)

        try:
            out_file = decrypt_storage_state(ciphertext, key, Path(args.out))
            print(f"Decrypted session written to {out_file}")
        except Exception as err:
            print(f"Session decryption error: {err}", file=sys.stderr)
            sys.exit(1)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
