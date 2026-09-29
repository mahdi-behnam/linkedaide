"""Ideation workflow process entrypoint and dependency wiring."""

from __future__ import annotations

import argparse
import asyncio
import logging
import sys
from pathlib import Path
from typing import Any, cast

from agent.config import Settings, load_settings
from agent.graphs.ideation_graph import build_ideation_graph
from agent.graphs.state import GraphContext, IdeationState
from agent.llm.service import LLMService
from agent.logging import setup_logging
from agent.safety.circuit_breaker import is_halted
from agent.safety.rate_limiter import DailyCapEnforcer
from agent.state import get_state_store
from agent.telegram.client import TelegramClient

logger = logging.getLogger("agent.orchestration.ideation_flow")


async def run_ideation_flow(
    settings: Settings | None = None,
    repo_root: Path | None = None,
) -> dict[str, Any]:
    """Execute the Ideation workflow from CLI or GitHub Actions cron trigger.

    Args:
        settings: Optional pre-loaded Settings instance.
        repo_root: Optional repository root path.

    Returns:
        dict[str, Any]: Final Ideation graph state.
    """
    cfg = settings or load_settings()
    root = repo_root or Path.cwd()

    setup_logging(cfg.log_level)
    logger.info("Initializing LinkedIn Ideation flow (dry_run=%s)", cfg.dry_run)

    # 1. Guard check
    halted, reason = is_halted(root, cfg)
    if halted:
        logger.warning("Ideation flow skipped: %s", reason)
        return {"status": "halted", "halted_reason": reason}

    # 2. Construct services
    state_store = get_state_store(settings=cfg, repo_root=root)
    telegram = TelegramClient(cfg)
    llm = LLMService(cfg)
    enforcer = DailyCapEnforcer(cfg)

    # 3. Construct GraphContext
    graph_context = GraphContext(
        settings=cfg,
        llm=llm,
        state_store=state_store,
        telegram=telegram,
        enforcer=enforcer,
    )

    # 4. Build and execute graph
    graph = build_ideation_graph()
    initial_state: IdeationState = {}
    result = await graph.ainvoke(initial_state, config={"configurable": {"context": graph_context}})

    logger.info(
        "Ideation flow finished with status: %s (suggestions: %d, errors: %d)",
        result.get("status"),
        len(result.get("pending_items", [])),
        len(result.get("errors", [])),
    )
    return cast(dict[str, Any], result)


def main() -> None:
    """CLI script runner."""
    parser = argparse.ArgumentParser(description="Run LinkedIn Ideation flow")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Execute in dry-run mode (prevents Telegram suggestion delivery)",
    )
    args = parser.parse_args()

    cfg = load_settings()
    if args.dry_run:
        cfg = cfg.model_copy(update={"dry_run": True})

    try:
        result = asyncio.run(run_ideation_flow(settings=cfg))
        if result.get("status") in ("failed", "llm_unavailable"):
            sys.exit(1)
        sys.exit(0)
    except Exception as err:
        print(f"Fatal Ideation error: {err}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
