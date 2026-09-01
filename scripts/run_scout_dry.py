"""Local dry-run script to execute Scout flow without sending real write actions.

Usage:
    uv run python scripts/run_scout_dry.py
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

from agent.config import load_settings
from agent.orchestration.scout_flow import run_scout_flow


def main() -> None:
    parser = argparse.ArgumentParser(description="LinkedIn Scout Flow — Local Dry Run")
    parser.add_argument(
        "--headed",
        action="store_true",
        help="Launch visible Chromium browser window to watch live scraping",
    )
    args = parser.parse_args()

    print("=" * 60)
    print("LINKEDIN SCOUT FLOW — LOCAL DRY RUN")
    print("=" * 60)

    cfg = load_settings()
    dry_cfg = cfg.model_copy(update={"dry_run": True})

    try:
        result = asyncio.run(
            run_scout_flow(settings=dry_cfg, repo_root=Path.cwd(), headless=not args.headed)
        )
        print("=" * 60)
        print(f"Scout Run Finished: {result.get('status')}")
        print(f"Posts evaluated: {len(result.get('posts', []))}")
        print(f"Suggestions generated: {len(result.get('pending_items', []))}")
        print("=" * 60)
        sys.exit(0)
    except Exception as err:
        print(f"Dry run failed: {err}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
