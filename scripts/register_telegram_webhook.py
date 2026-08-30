"""CLI utility to register or remove Telegram webhook for the Cloudflare Relay Worker.

Usage:
    uv run python scripts/register_telegram_webhook.py --worker-url https://... --secret-token ...
    uv run python scripts/register_telegram_webhook.py --delete
"""

from __future__ import annotations

import argparse
import os
import sys

import httpx


def register_webhook(
    worker_url: str,
    secret_token: str,
    bot_token: str | None = None,
) -> bool:
    """Register Telegram webhook with X-Telegram-Bot-Api-Secret-Token."""
    token = bot_token or os.environ.get("TELEGRAM_BOT_TOKEN")
    if not token:
        raise ValueError("TELEGRAM_BOT_TOKEN is required.")

    api_url = f"https://api.telegram.org/bot{token}/setWebhook"
    payload = {
        "url": worker_url,
        "secret_token": secret_token,
        "allowed_updates": ["callback_query"],
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
    token = bot_token or os.environ.get("TELEGRAM_BOT_TOKEN")
    if not token:
        raise ValueError("TELEGRAM_BOT_TOKEN is required.")

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


def main() -> None:
    parser = argparse.ArgumentParser(description="Manage Telegram webhook for Relay Worker")
    parser.add_argument("--worker-url", type=str, help="Cloudflare Worker HTTPS URL")
    parser.add_argument("--secret-token", type=str, help="Telegram Webhook secret token")
    parser.add_argument(
        "--bot-token", type=str, default=None, help="Telegram bot token (or via env)"
    )
    parser.add_argument("--delete", action="store_true", help="Delete existing webhook")
    args = parser.parse_args()

    try:
        if args.delete:
            success = delete_webhook(args.bot_token)
        else:
            if not args.worker_url or not args.secret_token:
                print(
                    "Error: --worker-url and --secret-token are required to register webhook.",
                    file=sys.stderr,
                )
                sys.exit(1)
            success = register_webhook(args.worker_url, args.secret_token, args.bot_token)

        sys.exit(0 if success else 1)
    except Exception as err:
        print(f"Error: {err}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
