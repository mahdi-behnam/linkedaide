"""CLI utility to register or remove Telegram webhook for the Cloudflare Relay Worker.

Usage:
    uv run python scripts/register_telegram_webhook.py --worker-url https://... --secret-token ...
    uv run python scripts/register_telegram_webhook.py --delete
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path
from typing import Any

import httpx


def _get_bot_token(provided_token: str | None = None) -> str:
    """Retrieve bot token from arg, env, or project Settings."""
    if provided_token:
        return provided_token
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    if token:
        return token
    try:
        from pydantic import SecretStr

        from agent.config import load_settings

        repo_root = Path(__file__).resolve().parent.parent
        env_path = repo_root / ".env"
        s = load_settings(_env_file=env_path) if env_path.exists() else load_settings()
        if s.telegram_bot_token:
            raw_token = s.telegram_bot_token
            return (
                raw_token.get_secret_value() if isinstance(raw_token, SecretStr) else str(raw_token)
            )
    except Exception:
        pass
    raise ValueError("TELEGRAM_BOT_TOKEN is required.")


def register_webhook(
    worker_url: str,
    secret_token: str,
    bot_token: str | None = None,
) -> bool:
    """Register Telegram webhook with X-Telegram-Bot-Api-Secret-Token."""
    token = _get_bot_token(bot_token)

    api_url = f"https://api.telegram.org/bot{token}/setWebhook"
    payload = {
        "url": worker_url,
        "secret_token": secret_token,
        "allowed_updates": ["callback_query", "message"],
        "drop_pending_updates": False,
    }

    resp = httpx.post(api_url, json=payload, timeout=15.0)
    resp.raise_for_status()
    data = resp.json()

    if data.get("ok"):
        print(f"Webhook registered successfully to: {worker_url}")
        return True
    else:
        print(f"Webhook registration failed: {data.get('description')}")
        return False


def delete_webhook(bot_token: str | None = None) -> bool:
    """Remove configured Telegram webhook to enable long-polling mode."""
    token = _get_bot_token(bot_token)

    api_url = f"https://api.telegram.org/bot{token}/deleteWebhook"
    resp = httpx.post(api_url, params={"drop_pending_updates": False}, timeout=15.0)
    resp.raise_for_status()
    data = resp.json()

    if data.get("ok"):
        print("Webhook deleted successfully. Polling mode is now enabled.")
        return True
    else:
        print(f"Webhook deletion failed: {data.get('description')}")
        return False


DEFAULT_BOT_COMMANDS = [
    {"command": "status", "description": "Check system health, breaker, and daily counters"},
    {"command": "pending", "description": "List all actions awaiting operator approval"},
    {"command": "stats", "description": "Performance metrics, counters, and approval rate"},
    {"command": "pause", "description": "Suspend automated scouting and execution workflows"},
    {"command": "resume", "description": "Resume automated agent operations"},
    {"command": "clear_incident", "description": "Safely reset tripped circuit breaker"},
    {"command": "post", "description": "Draft an original LinkedIn post from a quick note"},
    {"command": "scout", "description": "Triage and draft a comment for a specific LinkedIn URL"},
    {"command": "help", "description": "View operator command manual and usage guide"},
]


def register_bot_commands(
    bot_token: str | None = None,
    commands: list[dict[str, str]] | None = None,
) -> bool:
    """Register official Telegram bot commands menu (setMyCommands)."""
    token = _get_bot_token(bot_token)

    api_url = f"https://api.telegram.org/bot{token}/setMyCommands"
    bot_commands = commands or DEFAULT_BOT_COMMANDS
    resp = httpx.post(api_url, json={"commands": bot_commands}, timeout=15.0)
    resp.raise_for_status()
    data = resp.json()

    if data.get("ok"):
        print("Bot commands registered successfully via setMyCommands.")
        return True
    else:
        print(f"Bot commands registration failed: {data.get('description')}")
        return False


def get_webhook_info(bot_token: str | None = None) -> dict[str, Any]:
    """Retrieve current Telegram webhook registration status."""
    token = _get_bot_token(bot_token)
    api_url = f"https://api.telegram.org/bot{token}/getWebhookInfo"
    resp = httpx.get(api_url, timeout=15.0)
    resp.raise_for_status()
    data = resp.json()
    res = data.get("result", {})
    return res if isinstance(res, dict) else {}


def main() -> None:
    parser = argparse.ArgumentParser(description="Manage Telegram webhook for Relay Worker")
    parser.add_argument("--worker-url", type=str, help="Cloudflare Worker HTTPS URL")
    parser.add_argument("--secret-token", type=str, help="Telegram Webhook secret token")
    parser.add_argument(
        "--bot-token", type=str, default=None, help="Telegram bot token (or via env)"
    )
    parser.add_argument("--delete", action="store_true", help="Delete existing webhook")
    parser.add_argument(
        "--set-commands", action="store_true", help="Register Telegram bot commands menu only"
    )
    parser.add_argument(
        "--info", action="store_true", help="Inspect current Telegram webhook status"
    )
    args = parser.parse_args()

    try:
        if args.info:
            info = get_webhook_info(args.bot_token)
            print("Telegram Webhook Status:")
            print(f"  URL: {info.get('url') or '(None - polling mode)'}")
            allowed = info.get("allowed_updates") or []
            print(f"  Allowed Updates: {allowed}")
            print(f"  Pending Updates: {info.get('pending_update_count', 0)}")
            if info.get("last_error_message"):
                print(f"  Last Error: {info['last_error_message']}")

            if info.get("url") and "message" not in allowed:
                print(
                    "\n⚠️ WARNING: 'message' is missing from allowed_updates!\n"
                    "Telegram will DROP all text messages (like /status, /start).\n"
                    "To fix, re-register your webhook with allowed_updates containing 'message':\n"
                    "  uv run python scripts/register_telegram_webhook.py --secret-token <YOUR_SECRET_TOKEN>"
                )
            success = True
        elif args.set_commands:
            success = register_bot_commands(args.bot_token)
        elif args.delete:
            success = delete_webhook(args.bot_token)
        else:
            worker_url = args.worker_url
            if not worker_url:
                info = get_webhook_info(args.bot_token)
                worker_url = info.get("url")
                if worker_url:
                    print(f"Re-using existing registered worker URL: {worker_url}")
                else:
                    print(
                        "Error: --worker-url is required (no existing webhook URL found in Telegram).",
                        file=sys.stderr,
                    )
                    sys.exit(1)

            secret_token = args.secret_token or os.environ.get("TELEGRAM_WEBHOOK_SECRET")
            if not secret_token:
                print(
                    "Error: --secret-token is required to register webhook.",
                    file=sys.stderr,
                )
                sys.exit(1)

            success = register_webhook(worker_url, secret_token, args.bot_token)
            if success:
                try:
                    register_bot_commands(args.bot_token)
                except Exception as cmd_err:
                    print(f"Warning: Failed to set bot commands: {cmd_err}")

        sys.exit(0 if success else 1)
    except Exception as err:
        print(f"Error: {err}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
