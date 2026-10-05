"""Scout workflow process entrypoint and dependency wiring."""

from __future__ import annotations

import argparse
import asyncio
import logging
import sys
from pathlib import Path
from typing import Any, cast

from playwright.async_api import async_playwright

from agent.browser.scraper import FeedScraper
from agent.browser.session import ensure_session_file
from agent.browser.stealth import (
    is_authwall_or_login,
    new_stealth_context,
    wait_for_login_redirect,
)
from agent.config import Settings, load_settings
from agent.graphs.scout_graph import build_scout_graph
from agent.graphs.state import GraphContext, ScoutState
from agent.llm.service import LLMService
from agent.logging import setup_logging
from agent.safety.circuit_breaker import is_halted
from agent.safety.rate_limiter import DailyCapEnforcer
from agent.state import get_state_store
from agent.telegram.client import TelegramClient

logger = logging.getLogger("agent.orchestration.scout_flow")


async def run_scout_flow(
    settings: Settings | None = None,
    repo_root: Path | None = None,
    headless: bool = True,
) -> dict[str, Any]:
    """Execute the Scout workflow from CLI or GitHub Actions cron trigger.

    Args:
        settings: Optional pre-loaded Settings instance.
        repo_root: Optional repository root path.
        headless: Whether to launch Playwright in headless mode (default: True).

    Returns:
        dict[str, Any]: Final Scout graph state.
    """
    cfg = settings or load_settings()
    root = repo_root or Path.cwd()

    setup_logging(cfg.log_level)
    logger.info("Initializing LinkedIn Scout flow (dry_run=%s, headless=%s)", cfg.dry_run, headless)

    # 1. State Store
    state_store = get_state_store(settings=cfg, repo_root=root)

    # 2. Guard check
    halted, reason = is_halted(root, cfg, state_store=state_store)
    if halted:
        logger.warning("Scout flow skipped: %s", reason)
        return {"status": "halted", "halted_reason": reason}

    # 3. Construct services
    telegram = TelegramClient(cfg)
    llm = LLMService(cfg)
    enforcer = DailyCapEnforcer(cfg)

    # 3. Ensure valid decrypted session state file
    storage_state_path = ensure_session_file(cfg)

    # 4. Launch browser session
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(headless=headless)
        try:
            context_pw = await new_stealth_context(browser, storage_state_path=storage_state_path)
            page = await context_pw.new_page()

            # Navigate to LinkedIn feed
            try:
                await page.goto(
                    "https://www.linkedin.com/feed/", wait_until="domcontentloaded", timeout=30000
                )
            except Exception as err:
                logger.warning("Navigation to feed completed with warning: %s", err)

            # If redirected to login/handshake, wait up to 15s for auto-redirect to complete
            if is_authwall_or_login(page):
                logger.info(
                    "Detected login redirect/handshake; waiting up to 15s for auto-redirect..."
                )
                await wait_for_login_redirect(page, timeout=15.0)

            # If successfully on an authenticated page, persist refreshed session cookies
            if not is_authwall_or_login(page):
                try:
                    await context_pw.storage_state(path=str(storage_state_path))
                    logger.debug("Refreshed session storage state saved to %s", storage_state_path)
                except Exception as err:
                    logger.debug("Could not refresh session storage state: %s", err)

            scraper = FeedScraper(page, cfg)

            # 5. Construct GraphContext
            graph_context = GraphContext(
                settings=cfg,
                llm=llm,
                state_store=state_store,
                telegram=telegram,
                scraper=scraper,
                enforcer=enforcer,
            )

            # 6. Build and execute graph
            graph = build_scout_graph()
            initial_state: ScoutState = {}
            result = await graph.ainvoke(
                initial_state, config={"configurable": {"context": graph_context}}
            )

            # Persist updated session cookies after successful run
            if result.get("status") not in (
                "session_expired",
                "halted_bot_detection",
                "scrape_error",
            ):
                try:
                    await context_pw.storage_state(path=str(storage_state_path))
                except Exception:
                    pass

            logger.info(
                "Scout flow finished with status: %s (suggestions: %d, errors: %d)",
                result.get("status"),
                len(result.get("pending_items", [])),
                len(result.get("errors", [])),
            )
            return cast(dict[str, Any], result)
        finally:
            await browser.close()


def main() -> None:
    """CLI script runner."""
    parser = argparse.ArgumentParser(description="Run LinkedIn Scout flow")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Execute in dry-run mode (prevents live LinkedIn writes)",
    )
    parser.add_argument(
        "--headed",
        action="store_true",
        help="Launch visible Chromium browser window for local inspection",
    )
    args = parser.parse_args()

    cfg = load_settings()
    if args.dry_run:
        cfg = cfg.model_copy(update={"dry_run": True})

    try:
        result = asyncio.run(run_scout_flow(settings=cfg, headless=not args.headed))
        if result.get("status") in ("halted_bot_detection", "scrape_error"):
            sys.exit(1)
        sys.exit(0)
    except Exception as err:
        print(f"Fatal Scout error: {err}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
