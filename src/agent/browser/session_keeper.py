"""Automated rolling session keepalive and storage state persistence."""

from __future__ import annotations

import json
import logging
import time
from typing import TYPE_CHECKING, Any

from pydantic import SecretStr

from agent.browser.session import encrypt_storage_state
from agent.errors import SessionError

if TYPE_CHECKING:
    from playwright.async_api import BrowserContext

    from agent.state.base import BaseStateStore

logger = logging.getLogger(__name__)


async def refresh_and_persist_session(
    context: BrowserContext,
    session_encryption_key: SecretStr | str,
    state_store: BaseStateStore,
) -> dict[str, Any]:
    """Extract, refresh, re-encrypt, and persist authenticated browser session state.

    Args:
        context: Playwright BrowserContext containing active session cookies.
        session_encryption_key: Fernet encryption key (SecretStr or str).
        state_store: BaseStateStore instance to persist refreshed state token.

    Returns:
        dict[str, Any]: Execution status with remaining days until cookie expiry, e.g.
            {"refreshed": True, "remaining_days": 28.5}

    Raises:
        SessionError: If encryption key is missing or session extraction/encryption fails.
    """
    if not session_encryption_key:
        raise SessionError("Cannot refresh session: session_encryption_key is missing or empty")

    try:
        cookies = await context.cookies()
    except Exception as err:
        raise SessionError(f"Failed to extract cookies from browser context: {err}") from err

    li_at_cookie = next((c for c in cookies if c.get("name") == "li_at"), None)
    jsessionid_cookie = next((c for c in cookies if c.get("name") == "JSESSIONID"), None)

    if not li_at_cookie:
        logger.warning("li_at cookie missing from context cookies during session keepalive refresh")
    if not jsessionid_cookie:
        logger.warning(
            "JSESSIONID cookie missing from context cookies during session keepalive refresh"
        )

    remaining_days = 0.0
    now_epoch = time.time()
    if li_at_cookie:
        expires = li_at_cookie.get("expires", -1)
        if expires is not None and float(expires) > 0:
            remaining_seconds = float(expires) - now_epoch
            remaining_days = max(0.0, round(remaining_seconds / 86400.0, 1))

    try:
        storage_state_data: Any = await context.storage_state()
        if isinstance(storage_state_data, dict):
            raw_json = json.dumps(storage_state_data).encode("utf-8")
        elif isinstance(storage_state_data, str):
            raw_json = storage_state_data.encode("utf-8")
        else:
            raw_json = bytes(storage_state_data)
    except Exception as err:
        raise SessionError(f"Failed to dump browser storage state: {err}") from err

    encrypted_token = encrypt_storage_state(raw_json, session_encryption_key)

    try:
        state_store.put_key("linkedin_session_state_enc", encrypted_token)
    except Exception as err:
        raise SessionError(f"Failed to persist refreshed session to state store: {err}") from err

    logger.info(
        "Refreshed and persisted session keepalive (li_at=%s, JSESSIONID=%s, remaining_days=%.1f)",
        li_at_cookie is not None,
        jsessionid_cookie is not None,
        remaining_days,
    )

    return {"refreshed": True, "remaining_days": remaining_days}
