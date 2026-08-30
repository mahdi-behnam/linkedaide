"""Option B zero-external-infra polling trigger adapter for Telegram approvals."""

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

logger = logging.getLogger("agent.orchestration.poll_flow")


async def run_poll_flow(
    settings: Settings | None = None,
    repo_root: Path | None = None,
    timeout_seconds: int = 20,
) -> list[dict[str, Any]]:
    """Poll Telegram getUpdates for approved/rejected callback queries and invoke execute flow.

    Args:
        settings: Optional pre-loaded Settings.
        repo_root: Optional repository root path.
        timeout_seconds: Long polling timeout in seconds.

    Returns:
        list[dict[str, Any]]: Execution outcomes for processed callbacks.
    """
    cfg = settings or load_settings()
    root = repo_root or Path.cwd()

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
                url, params={"timeout": timeout_seconds, "allowed_updates": ["callback_query"]}
            )
            resp.raise_for_status()
            data = resp.json()
        except Exception as err:
            logger.error("Failed to poll Telegram updates: %s", err)
            return results

    updates = data.get("result", [])
    for update in updates:
        cb = update.get("callback_query")
        if not cb:
            continue

        sender_id = cb.get("from", {}).get("id")
        if sender_id != cfg.telegram_authorized_chat_id:
            continue

        cb_data = cb.get("data", "")
        try:
            parsed = CallbackDataPayload.from_callback_data(cb_data)
        except Exception:
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
