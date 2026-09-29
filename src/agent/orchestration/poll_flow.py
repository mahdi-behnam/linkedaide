"""Option B zero-external-infra polling trigger adapter for Telegram approvals and operator C2."""

from __future__ import annotations

import asyncio
import logging
import sys
from pathlib import Path
from typing import Any

import httpx

from agent.config import Settings, load_settings
from agent.models.schemas import CallbackDataPayload
from agent.orchestration.execute_flow import run_execute_flow
from agent.state import get_state_store
from agent.telegram.client import TelegramClient
from agent.telegram.command_handler import CommandHandler
from agent.telegram.draft_editor import handle_draft_edit, handle_edit_callback

logger = logging.getLogger("agent.orchestration.poll_flow")


async def run_poll_flow(
    settings: Settings | None = None,
    repo_root: Path | None = None,
    timeout_seconds: int = 20,
    telegram_client: TelegramClient | None = None,
) -> list[dict[str, Any]]:
    """Poll Telegram getUpdates for approvals, draft edits, and operator commands.

    Args:
        settings: Optional pre-loaded Settings.
        repo_root: Optional repository root path.
        timeout_seconds: Long polling timeout in seconds.
        telegram_client: Optional pre-constructed TelegramClient instance.

    Returns:
        list[dict[str, Any]]: Execution outcomes and handled action records.
    """
    cfg = settings or load_settings()
    root = repo_root or Path.cwd()
    state_store = get_state_store(settings=cfg, repo_root=root)

    bot_token = (
        cfg.telegram_bot_token.get_secret_value()
        if hasattr(cfg.telegram_bot_token, "get_secret_value")
        else str(cfg.telegram_bot_token)
    )
    url = f"https://api.telegram.org/bot{bot_token}/getUpdates"

    results: list[dict[str, Any]] = []

    async with httpx.AsyncClient(timeout=timeout_seconds + 5) as client:
        try:
            resp = await client.get(
                url,
                params={
                    "timeout": timeout_seconds,
                    "allowed_updates": ["callback_query", "message"],
                },
            )
            resp.raise_for_status()
            data = resp.json()
        except Exception as err:
            logger.error("Failed to poll Telegram updates: %s", err)
            return results

    tg = telegram_client or TelegramClient(cfg)
    cmd_handler = CommandHandler(settings=cfg, state_store=state_store, telegram=tg, repo_root=root)

    try:
        updates = data.get("result", [])
        for update in updates:
            # 1. Process incoming messages (operator commands or draft editing replies)
            msg = update.get("message")
            if msg:
                sender_id = msg.get("from", {}).get("id")
                if not TelegramClient.is_authorized(sender_id, cfg):
                    logger.warning(
                        "Unauthorized message received in poll flow from %s. Ignoring.",
                        sender_id,
                    )
                    continue

                text = (msg.get("text") or "").strip()
                if text.startswith("/"):
                    handled = await cmd_handler.handle_message(msg)
                    if handled:
                        cmd_token = text.split()[0].lstrip("/").split("@")[0].lower()
                        results.append({"status": "command_handled", "command": cmd_token})
                    continue

                if msg.get("reply_to_message"):
                    edited = await handle_draft_edit(
                        message=msg,
                        settings=cfg,
                        state_store=state_store,
                        telegram=tg,
                    )
                    if edited:
                        results.append(
                            {"status": "draft_edited", "message_id": msg.get("message_id")}
                        )
                    continue

            # 2. Process callback queries (approvals, rejections, inline edit buttons)
            cb = update.get("callback_query")
            if not cb:
                continue

            sender_id = cb.get("from", {}).get("id")
            if not TelegramClient.is_authorized(sender_id, cfg):
                logger.warning(
                    "Unauthorized callback_query received in poll flow from %s. Ignoring.",
                    sender_id,
                )
                continue

            cb_data = cb.get("data", "")
            try:
                parsed = CallbackDataPayload.from_callback_data(cb_data)
            except Exception:
                logger.warning("Failed to parse callback data in poll flow: %s", cb_data)
                continue

            if parsed.is_edit:
                await handle_edit_callback(
                    callback_query=cb,
                    settings=cfg,
                    state_store=state_store,
                    telegram=tg,
                )
                results.append({"status": "edit_prompted", "item_id": parsed.item_id})
                continue

            if parsed.is_regenerate:
                await cmd_handler.handle_callback_query(cb)
                results.append({"status": "regenerate_prompted", "item_id": parsed.item_id})
                continue

            action_name = "approve" if parsed.is_approval else "reject"
            msg_id = cb.get("message", {}).get("message_id")

            outcome = await run_execute_flow(
                action=action_name,
                item_id=parsed.item_id,
                telegram_chat_id=sender_id,
                telegram_message_id=msg_id,
                telegram_callback_query_id=cb.get("id"),
                settings=cfg,
                repo_root=root,
            )
            results.append(outcome)
    finally:
        if telegram_client is None:
            await tg.aclose()

    return results


def main() -> None:
    """CLI runner."""
    try:
        results = asyncio.run(run_poll_flow())
        print(f"Processed {len(results)} poll updates")
        sys.exit(0)
    except Exception as err:
        print(f"Fatal Poll error: {err}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
