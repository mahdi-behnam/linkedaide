"""Comment thread monitor orchestration flow: inspect active threads, triage replies, and queue drafts."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from playwright.async_api import async_playwright

from agent.browser.executor import ActionExecutor
from agent.browser.session import ensure_session_file
from agent.browser.stealth import new_stealth_context, wait_for_login_redirect
from agent.config import Settings, load_settings
from agent.llm.service import LLMService
from agent.logging import setup_logging
from agent.orchestration.thread_monitor import find_thread_replies
from agent.safety.circuit_breaker import is_halted
from agent.state import get_state_store
from agent.telegram.client import TelegramClient

logger = logging.getLogger("agent.orchestration.thread_monitor_flow")


async def run_thread_monitor_flow(
    settings: Settings | None = None,
    repo_root: Path | None = None,
    headless: bool = True,
) -> dict[str, Any]:
    """Execute the comment thread reply monitoring flow.

    Args:
        settings: Optional pre-loaded Settings instance.
        repo_root: Optional repository root path.
        headless: Whether to launch Playwright in headless mode.

    Returns:
        dict[str, Any]: Outcome metadata and newly queued actions.
    """
    cfg = settings or load_settings()
    root = repo_root or Path.cwd()

    setup_logging(cfg.log_level)
    logger.info("Initializing Thread Monitor flow (headless=%s)", headless)

    # 1. Guard check
    halted, reason = is_halted(root, cfg)
    if halted:
        logger.warning("Thread monitor flow skipped: %s", reason)
        return {"status": "halted", "halted_reason": reason, "queued_count": 0}

    # 2. State store check
    state_store = get_state_store(cfg, root)
    active_threads = state_store.list_active_threads()
    active_threads = [t for t in active_threads if t.status == "active"]
    if not active_threads:
        logger.info("No active threads to monitor.")
        return {"status": "no_active_threads", "queued_count": 0, "queued_actions": []}

    # 3. Services
    llm = LLMService(cfg)
    telegram = TelegramClient(cfg) if cfg.telegram_bot_token else None

    # 4. Browser session
    session_path = ensure_session_file(cfg, root)
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(
            headless=headless,
            args=[
                "--disable-blink-features=AutomationControlled",
                "--no-sandbox",
                "--disable-dev-shm-usage",
            ],
        )
        context = await new_stealth_context(browser, storage_state_path=session_path)
        page = await context.new_page()

        try:
            await page.goto("https://www.linkedin.com/feed/", wait_until="domcontentloaded")
            await wait_for_login_redirect(page)

            executor = ActionExecutor(page, cfg, state_store)
            queued = await find_thread_replies(
                executor=executor,
                llm=llm,
                state_store=state_store,
                settings=cfg,
                telegram=telegram,
            )
            return {
                "status": "completed",
                "queued_count": len(queued),
                "queued_actions": [action.item_id for action in queued],
            }
        finally:
            await context.close()
            await browser.close()
