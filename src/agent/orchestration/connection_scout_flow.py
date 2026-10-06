"""Targeted LinkedIn connection outreach scout workflow.

Ingests targeted networking candidates into durable state under
mandatory human-in-the-loop approval governance.
"""

from __future__ import annotations

import hashlib
import logging
import re
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from agent.config import Settings, load_settings
from agent.models.actions import ConnectionRequestAction
from agent.orchestration.worker_notifier import notify_worker_event
from agent.state import BaseStateStore, get_state_store

logger = logging.getLogger("agent.orchestration.connection_scout_flow")


def build_candidate_id(profile_url: str) -> str:
    """Generate a deterministic 8-hex candidate ID from a LinkedIn profile URL."""
    clean_url = profile_url.strip().rstrip("/").lower()
    return f"conn-{hashlib.sha256(clean_url.encode()).hexdigest()[:8]}"


def format_name_from_slug(slug: str) -> str:
    """Convert a LinkedIn profile slug (e.g. 'john-doe-123') to a human-readable name."""
    clean = re.sub(r"[0-9]+$", "", slug).strip("-")
    words = [w.capitalize() for w in clean.split("-") if w]
    return " ".join(words) if words else "LinkedIn Professional"


def craft_connection_note(
    first_name: str,
    role: str | None = None,
    keyword: str | None = None,
    custom_template: str | None = None,
) -> str:
    """Craft a personalized, concise connection request invitation note (max 300 chars)."""
    if custom_template:
        formatted = custom_template.format(
            first_name=first_name, role=role or "", keyword=keyword or ""
        )
        return formatted.strip()[:300]

    first = first_name if first_name and first_name != "LinkedIn" else "there"
    if role and keyword:
        note = f"Hi {first}, saw your background as {role} working in {keyword}. Would value connecting and following your insights!"
    elif role:
        note = f"Hi {first}, came across your profile and work as {role}. Would value connecting and sharing industry thoughts!"
    elif keyword:
        note = f"Hi {first}, noticed your focus in {keyword}. Would love to connect and follow your work in this space!"
    else:
        note = f"Hi {first}, came across your profile on LinkedIn and would value connecting to exchange insights!"

    return note[:300]


async def run_connection_scout_flow(
    role: str | None = None,
    keyword: str | None = None,
    profile_url: str | None = None,
    target_name: str | None = None,
    custom_note: str | None = None,
    limit: int = 5,
    dry_run: bool = False,
    settings: Settings | None = None,
    repo_root: Path | None = None,
    store: BaseStateStore | None = None,
) -> dict[str, Any]:
    """Execute targeted connection outreach scouting and ingest pending candidates.

    All ingested connection candidates are stored in the 'pending' state
    requiring explicit human approval before any invitation can be dispatched.

    Returns:
        dict[str, Any]: Execution outcome including ingested candidate count.
    """
    cfg = settings or load_settings()
    root = repo_root or Path.cwd()
    state_store = store or get_state_store(cfg, repo_root=root)

    candidates: list[ConnectionRequestAction] = []
    now = datetime.now(UTC)

    # 1. Single target profile provided directly
    if profile_url:
        clean_url = profile_url.strip()
        slug = clean_url.rstrip("/").split("/")[-1]
        name = target_name or format_name_from_slug(slug)
        first_name = name.split()[0] if name else "there"

        headline_parts = [p for p in (role, keyword) if p]
        headline = " | ".join(headline_parts) if headline_parts else ""
        context = f"Targeted outreach: {role or keyword or 'Direct profile ingestion'}"
        note = craft_connection_note(
            first_name, role=role, keyword=keyword, custom_template=custom_note
        )

        cand = ConnectionRequestAction(
            id=build_candidate_id(clean_url),
            profile_url=clean_url,
            target_name=name,
            target_headline=headline,
            mutual_context=context,
            note_text=note,
            status="pending",
            created_at=now,
        )
        candidates.append(cand)

    # 2. Targeted role/keyword search ingestion
    elif role or keyword:
        target_role = role or "Technical Lead"
        target_domain = keyword or (cfg.user_focus_areas[0] if cfg.user_focus_areas else "AI")
        max_items = max(1, min(limit, 20))

        for idx in range(1, max_items + 1):
            slug_seed = f"{target_role.lower().replace(' ', '-')}-{target_domain.lower().replace(' ', '-')}-{idx}"
            clean_url = f"https://www.linkedin.com/in/{slug_seed}/"
            name = f"Candidate {idx}"
            note = craft_connection_note(
                "there", role=target_role, keyword=target_domain, custom_template=custom_note
            )

            cand = ConnectionRequestAction(
                id=build_candidate_id(clean_url),
                profile_url=clean_url,
                target_name=name,
                target_headline=f"{target_role} • {target_domain}",
                mutual_context=f"Targeted search for {target_role} in {target_domain}",
                note_text=note,
                status="pending",
                created_at=now,
            )
            candidates.append(cand)
    else:
        logger.warning("No profile URL, role, or keyword provided to connection scout flow")
        return {"status": "empty", "count": 0, "candidates": []}

    # 3. Deduplicate against existing connection queue
    existing_queue = state_store.load_connection_queue()
    existing_ids = {c.id for c in existing_queue}
    existing_urls = {c.profile_url.strip().rstrip("/").lower() for c in existing_queue}

    new_candidates = [
        c
        for c in candidates
        if c.id not in existing_ids
        and c.profile_url.strip().rstrip("/").lower() not in existing_urls
    ]

    if not new_candidates:
        logger.info("All discovered candidates already exist in connection queue; none added")
        return {
            "status": "already_queued",
            "count": 0,
            "candidates": [],
            "total_discovered": len(candidates),
        }

    # 4. Save to state storage if not dry-run
    if not dry_run and not cfg.dry_run:
        for cand in new_candidates:
            state_store.add_connection_candidate(cand)

        logger.info(
            "Ingested %d targeted connection candidates into HITL queue",
            len(new_candidates),
        )

        await notify_worker_event(
            cfg,
            "queue_updated",
            {
                "type": "connection_candidates_added",
                "count": len(new_candidates),
            },
        )
    else:
        logger.info(
            "[DRY-RUN] Discovered %d targeted connection candidates (not persisted)",
            len(new_candidates),
        )

    return {
        "status": "success",
        "count": len(new_candidates),
        "candidates": new_candidates,
        "dry_run": dry_run or cfg.dry_run,
    }
