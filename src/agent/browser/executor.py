"""Playwright browser action executor for comments and posts."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import TYPE_CHECKING, Any

from agent.browser.actions.comment_mixin import CommentMixin
from agent.browser.actions.connection_mixin import ConnectionMixin
from agent.browser.actions.post_mixin import PostMixin
from agent.browser.actions.reaction_mixin import ReactionMixin
from agent.browser.actions.thread_mixin import ThreadMixin
from agent.browser.actions.verification_mixin import VerificationMixin
from agent.browser.biometrics import BiometricController
from agent.browser.session_keeper import refresh_and_persist_session
from agent.config import Settings

if TYPE_CHECKING:
    from playwright.async_api import Page

    from agent.state.base import BaseStateStore

logger = logging.getLogger(__name__)


class ActionExecutor(
    VerificationMixin,
    ReactionMixin,
    CommentMixin,
    PostMixin,
    ConnectionMixin,
    ThreadMixin,
):
    """Executes validated LinkedIn write and read actions via Playwright.

    Inherits specialized action behaviors from:
    - VerificationMixin: screenshot capture, DOM verification, error alerts, login/post checks
    - ReactionMixin: organic post reactions
    - CommentMixin: comment posting and submission verification
    - PostMixin: post creation and modal verification
    - ConnectionMixin: personalized connection requests and verification
    - ThreadMixin: comment thread inspection and follow-up reply posting
    """

    def __init__(
        self,
        page: Page,
        settings: Settings,
        debug_dir: Path | None = None,
        state_store: BaseStateStore | None = None,
        biometrics: BiometricController | None = None,
    ) -> None:
        self.page = page
        self.settings = settings
        self.debug_dir = debug_dir or (Path("debug") / "screenshots")
        self.debug_dir.mkdir(parents=True, exist_ok=True)
        self.state_store = state_store
        self.biometrics = biometrics or BiometricController(page)

    async def refresh_session(self) -> dict[str, Any] | None:
        """Refresh and persist authenticated session state."""
        return await self._refresh_and_persist_session()

    async def _refresh_and_persist_session(self) -> dict[str, Any] | None:
        """Refresh and persist authenticated session state after successful action execution."""
        enc_key = getattr(self.settings, "session_encryption_key", None)
        if not enc_key:
            return None

        ctx = getattr(self.page, "context", None)
        if not ctx:
            return None

        store = self.state_store
        if store is None:
            try:
                from agent.state import get_state_store

                store = get_state_store(self.settings, Path.cwd())
            except Exception:
                store = None

        if store is None:
            return None

        try:
            return await refresh_and_persist_session(
                context=ctx,
                session_encryption_key=enc_key,
                state_store=store,
            )
        except Exception as err:
            logger.warning("Rolling cookie keepalive refresh failed non-fatal: %s", err)
            return None


__all__ = ["ActionExecutor"]
