"""Scout workflow process entrypoint and dependency wiring."""

from __future__ import annotations

import asyncio
import logging
import sys
from pathlib import Path
from typing import Any, cast

from playwright.async_api import async_playwright

from agent.browser.scraper import FeedScraper
from agent.browser.stealth import new_stealth_context
from agent.config import Settings, load_settings
from agent.graphs.scout_graph import build_scout_graph
from agent.graphs.state import GraphContext, ScoutState
from agent.llm.service import LLMService
from agent.safety.circuit_breaker import is_halted
from agent.safety.rate_limiter import DailyCapEnforcer
from agent.state.store import GitStateStore
from agent.telegram.client import TelegramClient

logger = logging.getLogger("agent.orchestration.scout_flow")


async def run_scout_flow(
    settings: Settings | None = None, repo_root: Path | None = None
) -> dict[str, Any]:
    """Execute the Scout workflow from CLI or GitHub Actions cron trigger.

    Args:
        settings: Optional pre-loaded Settings instance.
        repo_root: Optional repository root path.

    Returns:
        dict[str, Any]: Final Scout graph state.
    """
    cfg = settings or load_settings()
    root = repo_root or Path.cwd()

    logging.basicConfig(
        level=cfg.log_level, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
    )
    logger.info("Initializing LinkedIn Scout flow (dry_run=%s)", cfg.dry_run)

    # 1. Guard check
    halted, reason = is_halted(root, cfg)
    if halted:
        logger.warning("Scout flow skipped: %s", reason)
        return {"status": "halted", "halted_reason": reason}

    # 2. Construct services
    state_store = GitStateStore(root)
    telegram = TelegramClient(cfg)
    llm = LLMService(cfg)
    enforcer = DailyCapEnforcer(cfg)

    # 3. Launch browser session
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(headless=True)
        try:
            context_pw = await new_stealth_context(
                browser, storage_state_path=cfg.linkedin_storage_state_path
            )
            page = await context_pw.new_page()

            # Navigate to LinkedIn feed
            try:
                await page.goto(
                    "https://www.linkedin.com/feed/", wait_until="domcontentloaded", timeout=30000
                )
            except Exception as err:
                logger.warning("Navigation to feed completed with warning: %s", err)

            scraper = FeedScraper(page, cfg)

            # 4. Construct GraphContext
            graph_context = GraphContext(
                settings=cfg,
                llm=llm,
                state_store=state_store,
                telegram=telegram,
                scraper=scraper,
                enforcer=enforcer,
            )

            # 5. Build and execute graph
            graph = build_scout_graph()
            initial_state: ScoutState = {}
            result = await graph.ainvoke(
                initial_state, config={"configurable": {"context": graph_context}}
            )

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
    try:
        result = asyncio.run(run_scout_flow())
        if result.get("status") in ("halted_bot_detection", "scrape_error"):
            sys.exit(1)
        sys.exit(0)
    except Exception as err:
        print(f"Fatal Scout error: {err}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
