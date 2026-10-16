"""CLI utility to generate cryptographic secrets for LinkedAide.

Generates:
1. SESSION_ENCRYPTION_KEY (Fernet 32-byte URL-safe base64 key for encrypting browser session state)
2. TELEGRAM_WEBHOOK_SECRET (High-entropy URL-safe token for authenticating Telegram-to-Cloudflare webhook callbacks)
3. DESKTOP_API_SECRET (High-entropy URL-safe token for authenticating Desktop App and Worker API endpoints)

Usage:
    uv run python scripts/generate_secrets.py
    uv run python scripts/generate_secrets.py --type webhook
    uv run python scripts/generate_secrets.py --type session
    uv run python scripts/generate_secrets.py --type desktop
    uv run python scripts/generate_secrets.py --raw --type webhook
"""

from __future__ import annotations

import argparse
import secrets
import sys

from cryptography.fernet import Fernet


def generate_session_encryption_key() -> str:
    """Generate a 32-byte URL-safe base64-encoded Fernet key."""
    return Fernet.generate_key().decode("utf-8")


def generate_telegram_webhook_secret(nbytes: int = 32) -> str:
    """Generate a high-entropy URL-safe secret token for Telegram webhooks.

    Telegram Bot API secret_token requirement: 1-256 characters [A-Za-z0-9_-].
    """
    return secrets.token_urlsafe(nbytes)


def generate_desktop_api_secret(nbytes: int = 32) -> str:
    """Generate a high-entropy URL-safe secret token for Desktop App & Worker API authentication."""
    return secrets.token_urlsafe(nbytes)


def print_full_guide(session_key: str, webhook_secret: str, desktop_secret: str) -> None:
    """Print an operator-friendly guide with generated credentials."""
    banner = "=" * 70
    print(banner)
    print("  LINKEDAIDE - AUTOMATED SECRET GENERATOR")
    print(banner)
    print("\n[1] SESSION ENCRYPTION KEY (For LinkedIn Storage State Encryption)")
    print("    Used to symmetrically encrypt/decrypt authenticated Playwright session state.")
    print(f"    SESSION_ENCRYPTION_KEY={session_key}")
    print("\n[2] TELEGRAM WEBHOOK SECRET (For Cloudflare Relay Worker Security)")
    print("    Used by Telegram to sign webhook callbacks (X-Telegram-Bot-Api-Secret-Token)")
    print("    and verified by Cloudflare Worker before triggering GitHub Actions.")
    print(f"    TELEGRAM_WEBHOOK_SECRET={webhook_secret}")
    print("\n[3] DESKTOP API SECRET (For Desktop Control Panel & Worker Authentication)")
    print("    Used by the Desktop App and worker API to securely authenticate requests.")
    print(f"    DESKTOP_API_SECRET={desktop_secret}")
    print("\n" + banner)
    print("  WHERE TO CONFIGURE THESE SECRETS:")
    print(banner)

    print("\n--- A. Add to your local .env file ---")
    print(f"SESSION_ENCRYPTION_KEY={session_key}")
    print(f"DESKTOP_API_SECRET={desktop_secret}")
    print(f"# (Optional reference) TELEGRAM_WEBHOOK_SECRET={webhook_secret}")

    print("\n--- B. Configure Cloudflare Relay Worker (infra/telegram-relay-worker) ---")
    print("Run these commands in your terminal:")
    print("  npx wrangler secret put TELEGRAM_WEBHOOK_SECRET")
    print(f"  # When prompted, paste: {webhook_secret}")
    print("  npx wrangler secret put DESKTOP_API_SECRET")
    print(f"  # When prompted, paste: {desktop_secret}")

    print("\n--- C. Register Webhook with Telegram API ---")
    print("Run this command from the repository root:")
    print("  uv run python scripts/register_telegram_webhook.py \\")
    print("    --worker-url https://telegram-relay-worker.<your-subdomain>.workers.dev \\")
    print(f"    --secret-token {webhook_secret}")

    print(
        "\n--- D. Add to GitHub Repository Secrets (Settings -> Secrets & Variables -> Actions) ---"
    )
    print("  Name: SESSION_ENCRYPTION_KEY")
    print(f"  Value: {session_key}")
    print(banner + "\n")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Generate cryptographic secrets for LinkedAide setup."
    )
    parser.add_argument(
        "--type",
        choices=["all", "session", "webhook", "desktop"],
        default="all",
        help="Type of secret to generate: 'all' (default), 'session', 'webhook', or 'desktop'",
    )
    parser.add_argument(
        "--raw",
        action="store_true",
        help="Print only the raw secret value (useful for scripting/piping)",
    )
    args = parser.parse_args()

    session_key = generate_session_encryption_key()
    webhook_secret = generate_telegram_webhook_secret()
    desktop_secret = generate_desktop_api_secret()

    if args.raw:
        if args.type == "session":
            print(session_key)
        elif args.type == "webhook":
            print(webhook_secret)
        elif args.type == "desktop":
            print(desktop_secret)
        else:
            print(f"{session_key} {webhook_secret} {desktop_secret}")
        sys.exit(0)

    if args.type == "session":
        print(f"SESSION_ENCRYPTION_KEY={session_key}")
    elif args.type == "webhook":
        print(f"TELEGRAM_WEBHOOK_SECRET={webhook_secret}")
    elif args.type == "desktop":
        print(f"DESKTOP_API_SECRET={desktop_secret}")
    else:
        print_full_guide(session_key, webhook_secret, desktop_secret)


if __name__ == "__main__":
    main()
