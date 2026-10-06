"""CLI command for managing LinkedIn connection outreach candidates.

Supports listing, reviewing, approving, and rejecting queued connection requests
under human-in-the-loop governance.
"""

from __future__ import annotations

import argparse
import asyncio
import logging
from collections.abc import Callable
from pathlib import Path
from typing import Any

from agent.config import Settings, load_settings
from agent.models.actions import ConnectionRequestAction
from agent.orchestration.execute_flow import run_execute_flow
from agent.state import BaseStateStore, get_state_store

logger = logging.getLogger("agent.cli.outreach")

PrintFn = Callable[..., Any]
InputFn = Callable[[str], str]


def format_candidate_card(candidate: ConnectionRequestAction) -> str:
    """Format a single connection candidate as a clean terminal card."""
    status_icons = {
        "pending": "⏳",
        "approved": "✅",
        "rejected": "❌",
        "sent": "🚀",
        "failed": "⚠️",
    }
    icon = status_icons.get(candidate.status, "ℹ️")
    created = candidate.created_at.strftime("%Y-%m-%d %H:%M UTC")

    lines = [
        f"┌── [{icon} {candidate.status.upper()}] Candidate ID: {candidate.id}",
        f"│   Name:     {candidate.target_name}",
        f"│   Headline: {candidate.target_headline or '(none)'}",
        f"│   Profile:  {candidate.profile_url}",
        f"│   Created:  {created}",
    ]
    if candidate.mutual_context:
        lines.append(f"│   Context:  {candidate.mutual_context}")
    if candidate.note_text:
        lines.append(f'│   Note:     "{candidate.note_text}"')
    lines.append("└──" + "─" * 60)
    return "\n".join(lines)


def list_outreach_candidates(
    queue: list[ConnectionRequestAction],
    status_filter: str | None = None,
    print_fn: PrintFn = print,
) -> None:
    """List connection candidates filtered by status."""
    norm_filter = status_filter.lower().strip() if status_filter else "all"
    if norm_filter != "all":
        filtered = [c for c in queue if c.status.lower() == norm_filter]
    else:
        filtered = queue

    if not filtered:
        print_fn(f"No connection outreach candidates found (filter: {norm_filter}).")
        return

    print_fn(f"\nFound {len(filtered)} connection candidates (filter: {norm_filter}):\n")
    for candidate in filtered:
        print_fn(format_candidate_card(candidate))

    # Summary counts
    counts: dict[str, int] = {}
    for c in queue:
        counts[c.status] = counts.get(c.status, 0) + 1
    summary_parts = [f"{k}: {v}" for k, v in sorted(counts.items())]
    print_fn(f"Total: {len(queue)} across all statuses ({', '.join(summary_parts)})\n")


def review_outreach_candidates(
    queue: list[ConnectionRequestAction],
    settings: Settings,
    repo_root: Path | None = None,
    input_fn: InputFn = input,
    print_fn: PrintFn = print,
) -> int:
    """Interactively review pending connection candidates."""
    pending = [c for c in queue if c.status == "pending"]
    if not pending:
        print_fn("No pending connection candidates to review.")
        return 0

    print_fn(f"\n--- Reviewing {len(pending)} Pending Connection Candidates ---")
    for idx, candidate in enumerate(pending, 1):
        print_fn(f"\n[{idx}/{len(pending)}]")
        print_fn(format_candidate_card(candidate))

        prompt = "Decision: [a]pprove / [r]eject / [s]kip / [q]uit: "
        try:
            choice = input_fn(prompt).strip().lower()
        except (EOFError, KeyboardInterrupt):
            print_fn("\nReview aborted by operator.")
            return 0

        if choice == "a":
            print_fn(f"Approving candidate {candidate.id}...")
            result = asyncio.run(
                run_execute_flow(
                    action="approve",
                    item_id=candidate.id,
                    settings=settings,
                    repo_root=repo_root,
                )
            )
            status = result.get("status")
            if status in ("success", "dry_run"):
                print_fn(f"✅ Successfully executed approval for {candidate.target_name}.")
            else:
                err = result.get("error", "Execution failed")
                print_fn(f"❌ Failed to approve {candidate.id}: {err}")
        elif choice == "r":
            print_fn(f"Rejecting candidate {candidate.id}...")
            result = asyncio.run(
                run_execute_flow(
                    action="reject",
                    item_id=candidate.id,
                    settings=settings,
                    repo_root=repo_root,
                )
            )
            print_fn(f"❌ Rejected candidate {candidate.target_name}.")
        elif choice == "s":
            print_fn("Skipped.")
            continue
        elif choice == "q":
            print_fn("Exiting review.")
            break
        else:
            print_fn(f"Unknown option '{choice}', skipping.")

    return 0


def run_outreach(
    args: argparse.Namespace,
    settings: Settings | None = None,
    store: BaseStateStore | None = None,
    repo_root: Path | None = None,
    input_fn: InputFn = input,
    print_fn: PrintFn = print,
) -> int:
    """Execute connection outreach CLI subcommand."""
    cfg = settings or load_settings()
    if getattr(args, "dry_run", False):
        cfg = cfg.model_copy(update={"dry_run": True})

    root = repo_root or (Path(args.repo_root) if getattr(args, "repo_root", None) else Path.cwd())
    state_store = store or get_state_store(cfg, repo_root=root)
    queue = state_store.load_connection_queue()

    # 1. Direct approve
    if getattr(args, "approve", None):
        target_id = args.approve
        candidate = state_store.read_connection_candidate(target_id)
        if not candidate:
            print_fn(f"Error: Connection candidate '{target_id}' not found.")
            return 1
        print_fn(f"Approving connection request for '{candidate.target_name}' ({target_id})...")
        result: dict[str, Any] = asyncio.run(
            run_execute_flow(
                action="approve",
                item_id=target_id,
                settings=cfg,
                repo_root=root,
            )
        )
        if result.get("status") in ("failed", "halted_challenge", "session_error"):
            print_fn(f"Failed to execute approval: {result.get('error')}")
            return 1
        print_fn(f"✅ Connection request for '{candidate.target_name}' successfully processed.")
        return 0

    # 2. Direct reject
    if getattr(args, "reject", None):
        target_id = args.reject
        candidate = state_store.read_connection_candidate(target_id)
        if not candidate:
            print_fn(f"Error: Connection candidate '{target_id}' not found.")
            return 1
        print_fn(f"Rejecting connection request for '{candidate.target_name}' ({target_id})...")
        result = asyncio.run(
            run_execute_flow(
                action="reject",
                item_id=target_id,
                settings=cfg,
                repo_root=root,
            )
        )
        print_fn(f"❌ Connection candidate '{target_id}' marked as rejected.")
        return 0

    # 3. Interactive review
    if getattr(args, "review", False):
        return review_outreach_candidates(
            queue=queue,
            settings=cfg,
            repo_root=root,
            input_fn=input_fn,
            print_fn=print_fn,
        )

    # 4. Scout targeted connection candidates
    if (
        getattr(args, "scout", False)
        or getattr(args, "role", None)
        or getattr(args, "profile", None)
    ):
        from agent.orchestration.connection_scout_flow import run_connection_scout_flow

        res = asyncio.run(
            run_connection_scout_flow(
                role=getattr(args, "role", None),
                keyword=getattr(args, "keyword", None),
                profile_url=getattr(args, "profile", None),
                target_name=getattr(args, "name", None),
                custom_note=getattr(args, "note", None),
                limit=getattr(args, "limit", 5),
                dry_run=getattr(args, "dry_run", False),
                settings=cfg,
                repo_root=root,
                store=state_store,
            )
        )
        count = res.get("count", 0)
        print_fn(
            f"Connection scout completed: {count} new candidate(s) ingested into queue "
            f"(status: {res.get('status')})."
        )
        return 0

    # 5. Default: List candidates
    status_filter = getattr(args, "status", None)
    list_outreach_candidates(queue=queue, status_filter=status_filter, print_fn=print_fn)
    return 0
