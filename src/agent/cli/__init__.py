"""Unified CLI tool and entrypoints for the LinkedIn HITL agent.

Provides diagnostic 'doctor', interactive 'setup' wizard,
and flow execution commands (scout, execute, health).
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import sys
from pathlib import Path

from agent.cli.setup import run_setup
from agent.config import load_settings
from agent.doctor import run_doctor

logger = logging.getLogger("agent.cli")


def run_scout(args: argparse.Namespace) -> int:
    """Execute LinkedIn scout workflow."""
    from agent.orchestration.scout_flow import run_scout_flow

    cfg = load_settings()
    if getattr(args, "dry_run", False):
        cfg = cfg.model_copy(update={"dry_run": True})

    headless = not getattr(args, "headed", False)
    try:
        result = asyncio.run(run_scout_flow(settings=cfg, headless=headless))
        if result.get("status") in ("halted_bot_detection", "scrape_error"):
            return 1
        return 0
    except Exception as err:
        print(f"Fatal Scout error: {err}", file=sys.stderr)
        return 1


def run_execute(args: argparse.Namespace) -> int:
    """Execute approval or rejection dispatch flow."""
    from agent.orchestration.execute_flow import run_execute_flow

    try:
        result = asyncio.run(
            run_execute_flow(
                action=getattr(args, "action", None),
                item_id=getattr(args, "item_id", None),
                telegram_chat_id=getattr(args, "chat_id", None),
                telegram_message_id=getattr(args, "message_id", None),
                telegram_callback_query_id=getattr(args, "callback_query_id", None),
            )
        )
        if result.get("status") in ("failed", "halted_challenge", "session_error"):
            return 1
        return 0
    except Exception as err:
        print(f"Fatal Execute error: {err}", file=sys.stderr)
        return 1


def run_health(args: argparse.Namespace) -> int:
    """Execute LinkedIn session health check canary."""
    from agent.orchestration.health_check_flow import run_health_check_flow

    repo_root = Path(args.repo_root) if getattr(args, "repo_root", None) else None
    try:
        result = asyncio.run(run_health_check_flow(repo_root=repo_root))
        if not result.get("is_healthy", False):
            return 1
        return 0
    except Exception as err:
        print(f"Fatal Health Check error: {err}", file=sys.stderr)
        return 1


def build_parser() -> argparse.ArgumentParser:
    """Build the top-level CLI parser."""
    parser = argparse.ArgumentParser(
        prog="agent",
        description="Unified CLI for the LinkedIn Human-in-the-Loop Agent",
    )
    subparsers = parser.add_subparsers(dest="command", help="Available subcommands")

    # doctor
    doctor_parser = subparsers.add_parser(
        "doctor", help="Run comprehensive diagnostic suite and environment checks"
    )
    doctor_parser.add_argument("--repo-root", default=None, help="Root repository path")

    # setup
    setup_parser = subparsers.add_parser("setup", help="Interactive onboarding setup wizard")
    setup_parser.add_argument(
        "--env-file", default=".env", help="Path to .env file to update (default: .env)"
    )

    # scout
    scout_parser = subparsers.add_parser("scout", help="Run the LinkedIn feed scout workflow")
    scout_parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Execute in dry-run mode (prevents live LinkedIn writes)",
    )
    scout_parser.add_argument(
        "--headed",
        action="store_true",
        help="Launch visible Chromium browser window for local inspection",
    )

    # execute
    execute_parser = subparsers.add_parser(
        "execute", help="Run the execute workflow for approved or rejected actions"
    )
    execute_parser.add_argument(
        "--action", choices=["approve", "reject"], default=None, help="Action to execute"
    )
    execute_parser.add_argument("--item-id", default=None, help="Unique item ID for pending action")
    execute_parser.add_argument("--chat-id", type=int, default=None, help="Telegram chat ID")
    execute_parser.add_argument("--message-id", type=int, default=None, help="Telegram message ID")
    execute_parser.add_argument(
        "--callback-query-id", default=None, help="Telegram callback query ID"
    )

    # health
    health_parser = subparsers.add_parser(
        "health", help="Run read-only session health check canary"
    )
    health_parser.add_argument("--repo-root", default=None, help="Repository root path")

    return parser


def main(argv: list[str] | None = None) -> None:
    """CLI main entrypoint."""
    parser = build_parser()
    args = parser.parse_args(argv)

    if not args.command:
        parser.print_help()
        sys.exit(0)

    exit_code = 0
    if args.command == "doctor":
        exit_code = run_doctor(args)
    elif args.command == "setup":
        run_setup(env_path=Path(getattr(args, "env_file", ".env")))
        exit_code = 0
    elif args.command == "scout":
        exit_code = run_scout(args)
    elif args.command == "execute":
        exit_code = run_execute(args)
    elif args.command == "health":
        exit_code = run_health(args)
    else:
        parser.print_help()
        exit_code = 1

    sys.exit(exit_code)


__all__ = [
    "build_parser",
    "main",
    "run_doctor",
    "run_execute",
    "run_health",
    "run_scout",
    "run_setup",
]
