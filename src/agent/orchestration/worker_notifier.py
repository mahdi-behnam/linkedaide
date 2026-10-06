"""Realtime event notifier for Cloudflare Worker and Desktop Cockpit."""

from __future__ import annotations

import logging
from typing import Any

import httpx
from pydantic import SecretStr

from agent.config.settings import Settings

logger = logging.getLogger("agent.orchestration.worker_notifier")


async def notify_worker_event(
    settings: Settings,
    event_type: str,
    payload: dict[str, Any] | None = None,
    timeout: float = 5.0,
) -> bool:
    """Send an asynchronous event notification ping to Cloudflare Worker to broadcast to Desktop.

    Fails open (never raises exceptions) so runner workflow execution is never disrupted
    if the worker is unreachable, offline, or unconfigured.

    Returns:
        True if the event was accepted and broadcast by the worker, False otherwise.
    """
    if not settings.worker_url or not settings.desktop_api_secret:
        logger.debug("Worker URL or desktop API secret not configured; skipping event broadcast")
        return False

    secret_str = (
        settings.desktop_api_secret.get_secret_value()
        if isinstance(settings.desktop_api_secret, SecretStr)
        else str(settings.desktop_api_secret)
    )
    if not secret_str:
        return False

    endpoint = f"{settings.worker_url.rstrip('/')}/api/event"
    event_body: dict[str, Any] = {"type": event_type}
    if payload:
        event_body.update(payload)

    headers = {
        "Authorization": f"Bearer {secret_str}",
        "Content-Type": "application/json",
        "User-Agent": "LinkedIn-Agent-Runner/1.0",
    }

    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            resp = await client.post(endpoint, json=event_body, headers=headers)
            if resp.status_code == 200:
                logger.info("Realtime event '%s' dispatched to worker for desktop sync", event_type)
                return True
            logger.warning(
                "Worker event notify failed with HTTP %d: %s",
                resp.status_code,
                resp.text,
            )
            return False
    except Exception as err:
        logger.warning("Could not dispatch event '%s' to worker: %s", event_type, err)
        return False
