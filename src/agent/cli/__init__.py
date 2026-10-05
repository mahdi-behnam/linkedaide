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

from agent.cli.outreach import run_outreach
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


def run_poll(args: argparse.Namespace) -> int:
    """Execute local polling loop for Telegram approvals."""
    from agent.orchestration.poll_flow import run_poll_flow

    timeout = getattr(args, "timeout", 20)
    once = getattr(args, "once", False)
    repo_root = Path(args.repo_root) if getattr(args, "repo_root", None) else None

    try:
        if once:
            results = asyncio.run(run_poll_flow(repo_root=repo_root, timeout_seconds=timeout))
            print(f"Processed {len(results)} poll updates")
            return 0

        print("Starting Telegram polling listener (Ctrl+C to stop)...")
        while True:
            results = asyncio.run(run_poll_flow(repo_root=repo_root, timeout_seconds=timeout))
            if results:
                print(f"Processed {len(results)} poll updates")
    except KeyboardInterrupt:
        print("\nPolling stopped by operator.")
        return 0
    except Exception as err:
        print(f"Fatal Poll error: {err}", file=sys.stderr)
        return 1


def run_ideate(args: argparse.Namespace) -> int:
    """Execute LinkedIn standalone post ideation workflow."""
    from agent.orchestration.ideation_flow import run_ideation_flow

    cfg = load_settings()
    if getattr(args, "dry_run", False):
        cfg = cfg.model_copy(update={"dry_run": True})

    repo_root = Path(args.repo_root) if getattr(args, "repo_root", None) else None
    try:
        result = asyncio.run(run_ideation_flow(settings=cfg, repo_root=repo_root))
        if result.get("status") in ("failed", "llm_unavailable"):
            return 1
        return 0
    except Exception as err:
        print(f"Fatal Ideation error: {err}", file=sys.stderr)
        return 1


def run_thread_monitor(args: argparse.Namespace) -> int:
    """Execute LinkedIn active thread comment replies monitoring workflow."""
    from agent.orchestration.thread_monitor_flow import run_thread_monitor_flow

    cfg = load_settings()
    headless = not getattr(args, "headed", False)
    repo_root = Path(args.repo_root) if getattr(args, "repo_root", None) else None
    try:
        result = asyncio.run(
            run_thread_monitor_flow(settings=cfg, repo_root=repo_root, headless=headless)
        )
        if result.get("status") in ("failed", "session_error", "halted_challenge"):
            return 1
        print(f"Thread monitor finished. Queued {result.get('queued_count', 0)} reply actions.")
        return 0
    except Exception as err:
        print(f"Fatal Thread Monitor error: {err}", file=sys.stderr)
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

    # poll
    poll_parser = subparsers.add_parser(
        "poll", help="Run local Telegram polling loop for approvals and operator commands"
    )
    poll_parser.add_argument(
        "--timeout", type=int, default=20, help="Polling timeout in seconds (default: 20)"
    )
    poll_parser.add_argument(
        "--once", action="store_true", help="Run a single polling cycle and exit"
    )
    poll_parser.add_argument("--repo-root", default=None, help="Root repository path")

    # ideate
    ideate_parser = subparsers.add_parser(
        "ideate", help="Run the LinkedIn standalone post ideation workflow"
    )
    ideate_parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Execute in dry-run mode (prevents Telegram suggestion delivery)",
    )
    ideate_parser.add_argument("--repo-root", default=None, help="Root repository path")

    # thread-monitor
    thread_parser = subparsers.add_parser(
        "thread-monitor", help="Inspect active comment threads for new replies and draft follow-ups"
    )
    thread_parser.add_argument(
        "--headed",
        action="store_true",
        help="Launch visible Chromium browser window for local inspection",
    )
    thread_parser.add_argument("--repo-root", default=None, help="Root repository path")

    # outreach
    outreach_parser = subparsers.add_parser(
        "outreach", help="Manage LinkedIn connection outreach queue and review candidates"
    )
    outreach_parser.add_argument(
        "--list",
        action="store_true",
        help="List queued connection candidates (default behavior)",
    )
    outreach_parser.add_argument(
        "--review",
        action="store_true",
        help="Interactively review and triage pending connection candidates",
    )
    outreach_parser.add_argument(
        "--approve",
        metavar="ITEM_ID",
        default=None,
        help="Approve and execute a specific connection request candidate by ID",
    )
    outreach_parser.add_argument(
        "--reject",
        metavar="ITEM_ID",
        default=None,
        help="Reject a specific connection request candidate by ID",
    )
    outreach_parser.add_argument(
        "--status",
        choices=["pending", "approved", "rejected", "sent", "failed", "all"],
        default=None,
        help="Filter listed candidates by lifecycle status",
    )
    outreach_parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Execute approval in dry-run mode (prevents live LinkedIn writes)",
    )
    outreach_parser.add_argument("--repo-root", default=None, help="Root repository path")

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
    elif args.command == "poll":
        exit_code = run_poll(args)
    elif args.command == "ideate":
        exit_code = run_ideate(args)
    elif args.command == "thread-monitor":
        exit_code = run_thread_monitor(args)
    elif args.command == "outreach":
        exit_code = run_outreach(args)
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
    "run_ideate",
    "run_outreach",
    "run_poll",
    "run_scout",
    "run_setup",
    "run_thread_monitor",
]
