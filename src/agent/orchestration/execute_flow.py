"""Execute workflow process entrypoint for approval and rejection dispatches."""

from __future__ import annotations

import asyncio
import logging
import os
import sys
from pathlib import Path
from typing import Any, cast

from playwright.async_api import async_playwright

from agent.browser.executor import ActionExecutor
from agent.browser.session import ensure_session_file
from agent.browser.stealth import new_stealth_context
from agent.config import Settings, load_settings
from agent.graphs.execute_graph import build_execute_graph
from agent.graphs.state import ExecuteState, GraphContext
from agent.logging import setup_logging
from agent.safety.circuit_breaker import is_halted
from agent.safety.rate_limiter import DailyCapEnforcer
from agent.state.store import GitStateStore
from agent.telegram.client import TelegramClient

logger = logging.getLogger("agent.orchestration.execute_flow")


async def run_execute_flow(
    action: str | None = None,
    item_id: str | None = None,
    telegram_chat_id: int | None = None,
    telegram_message_id: int | None = None,
    telegram_callback_query_id: str | None = None,
    settings: Settings | None = None,
    repo_root: Path | None = None,
) -> dict[str, Any]:
    """Execute approval or rejection action triggered by repository_dispatch.

    Args:
        action: 'approve' or 'reject'.
        item_id: Unique 8-char item ID.
        telegram_chat_id: Telegram chat ID.
        telegram_message_id: Telegram message ID.
        telegram_callback_query_id: Telegram callback query ID.
        settings: Optional pre-loaded Settings instance.
        repo_root: Optional repository root path.

    Returns:
        dict[str, Any]: Final Execute graph state.
    """
    cfg = settings or load_settings()
    root = repo_root or Path.cwd()

    act = action or os.environ.get("ACTION", "approve")
    iid = item_id or os.environ.get("ITEM_ID", "")
    t_chat = telegram_chat_id or (
        int(os.environ["TELEGRAM_CHAT_ID"])
        if "TELEGRAM_CHAT_ID" in os.environ
        else cfg.telegram_authorized_chat_id
    )
    t_msg = telegram_message_id or (
        int(os.environ["TELEGRAM_MESSAGE_ID"]) if "TELEGRAM_MESSAGE_ID" in os.environ else None
    )
    t_cb = telegram_callback_query_id or os.environ.get("TELEGRAM_CALLBACK_QUERY_ID")

    setup_logging(cfg.log_level)
    logger.info("Executing action flow: %s for item: %s", act, iid)

    # 1. Guard check
    halted, reason = is_halted(root, cfg)
    if halted:
        logger.warning("Execute flow skipped: %s", reason)
        return {"status": "halted", "halted_reason": reason}

    # 2. Services
    state_store = GitStateStore(root)
    telegram = TelegramClient(cfg)
    enforcer = DailyCapEnforcer(cfg)

    initial_state: ExecuteState = {
        "action": act,
        "item_id": iid,
        "telegram_chat_id": t_chat,
        "telegram_message_id": t_msg,
        "telegram_callback_query_id": t_cb,
    }

    # If action is reject, browser launch is not required
    if act == "reject":
        graph_context = GraphContext(
            settings=cfg,
            state_store=state_store,
            telegram=telegram,
            enforcer=enforcer,
        )
        graph = build_execute_graph()
        result = await graph.ainvoke(
            initial_state, config={"configurable": {"context": graph_context}}
        )
        return cast(dict[str, Any], result)

    # Live or Dry-run browser execution
    storage_state_path = ensure_session_file(cfg)

    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(headless=True)
        try:
            context_pw = await new_stealth_context(browser, storage_state_path=storage_state_path)
            page = await context_pw.new_page()
            executor = ActionExecutor(page, cfg)

            graph_context = GraphContext(
                settings=cfg,
                state_store=state_store,
                telegram=telegram,
                executor=executor,
                enforcer=enforcer,
            )

            graph = build_execute_graph()
            result = await graph.ainvoke(
                initial_state, config={"configurable": {"context": graph_context}}
            )
            logger.info("Execute flow completed with status: %s", result.get("status"))
            return cast(dict[str, Any], result)
        finally:
            await browser.close()


def main() -> None:
    """CLI entrypoint."""
    try:
        result = asyncio.run(run_execute_flow())
        if result.get("status") in ("failed", "halted_challenge", "session_error"):
            sys.exit(1)
        sys.exit(0)
    except Exception as err:
        print(f"Fatal Execute error: {err}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
