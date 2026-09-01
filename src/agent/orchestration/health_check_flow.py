"""Weekly session health check canary entrypoint."""

from __future__ import annotations

import asyncio
import logging
import sys
from pathlib import Path
from typing import Any, cast

from playwright.async_api import async_playwright

from agent.browser.executor import ActionExecutor
from agent.browser.session import ensure_session_file
from agent.browser.stealth import new_stealth_context
from agent.config import Settings, load_settings
from agent.graphs.health_graph import build_health_graph
from agent.graphs.state import GraphContext, HealthCheckState
from agent.logging import setup_logging
from agent.safety.circuit_breaker import is_halted
from agent.state.store import GitStateStore
from agent.telegram.client import TelegramClient

logger = logging.getLogger("agent.orchestration.health_check_flow")


async def run_health_check_flow(
    settings: Settings | None = None, repo_root: Path | None = None
) -> dict[str, Any]:
    """Execute the read-only session health check canary.

    Args:
        settings: Optional pre-loaded Settings instance.
        repo_root: Optional repository root path.

    Returns:
        dict[str, Any]: Final HealthCheck graph state.
    """
    cfg = settings or load_settings()
    root = repo_root or Path.cwd()

    setup_logging(cfg.log_level)
    logger.info("Running LinkedIn session health check")

    halted, reason = is_halted(root, cfg)
    if halted:
        logger.warning("Health check skipped: %s", reason)
        return {"status": "halted", "halted_reason": reason, "is_healthy": False}

    state_store = GitStateStore(root)
    telegram = TelegramClient(cfg)
    storage_state_path = ensure_session_file(cfg)

    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(headless=True)
        try:
            context_pw = await new_stealth_context(
                browser, storage_state_path=storage_state_path
            )
            page = await context_pw.new_page()

            try:
                await page.goto(
                    "https://www.linkedin.com/feed/", wait_until="domcontentloaded", timeout=30000
                )
            except Exception as err:
                logger.warning("Feed navigation warning during health check: %s", err)

            executor = ActionExecutor(page, cfg)
            graph_context = GraphContext(
                settings=cfg,
                state_store=state_store,
                telegram=telegram,
                executor=executor,
            )

            graph = build_health_graph()
            initial_state: HealthCheckState = {}
            result = await graph.ainvoke(
                initial_state, config={"configurable": {"context": graph_context}}
            )

            logger.info("Health check completed: is_healthy=%s", result.get("is_healthy"))
            return cast(dict[str, Any], result)
        finally:
            await browser.close()


def main() -> None:
    """CLI runner."""
    try:
        result = asyncio.run(run_health_check_flow())
        if not result.get("is_healthy", False):
            sys.exit(1)
        sys.exit(0)
    except Exception as err:
        print(f"Fatal Health Check error: {err}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
