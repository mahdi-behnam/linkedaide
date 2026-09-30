"""4-Tier Self-Healing Selector Engine and Fallback Pyramid Hierarchy.

Architecture Invariants:
- Tier 1: Canonical Data Attributes (e.g. data-control-name, data-test-*, div[data-view-name]).
- Tier 2: Accessibility Tree (AXTree / ARIA roles: button[name='...'], [role='textbox'], [aria-label='...']).
- Tier 3: Semantic Text Heuristics (text=..., :has-text(...), :text-matches(...)).
- Tier 4: Dynamic Overrides Cache (selector_overrides dict stored in StateStore / KV).
- Non-canonical candidate success triggers an in-memory and durable cache update.
- Complete candidate exhaustion raises SelectorDriftError.
"""

from __future__ import annotations

import json
import logging
from enum import IntEnum
from typing import TYPE_CHECKING

from agent.errors import SelectorDriftError

if TYPE_CHECKING:
    from playwright.async_api import Locator, Page

    from agent.state.base import BaseStateStore

logger = logging.getLogger(__name__)


class SelectorTier(IntEnum):
    """Fallback pyramid hierarchy tiers for self-healing selectors."""

    TIER_1_CANONICAL = 1
    TIER_2_AXTREE = 2
    TIER_3_SEMANTIC_TEXT = 3
    TIER_4_DYNAMIC_CACHE = 4


# Common canonical fallback configurations for LinkedIn UI elements
LINKEDIN_SELECTORS: dict[str, list[str]] = {
    "comment_box": [
        # Tier 1: Canonical Data Attributes
        "div.comments-comment-box__editor[data-control-name='comment_box']",
        "div[data-test-ql-editor='true']",
        "div[data-view-name='comment-editor']",
        # Tier 2: Accessibility Tree (AXTree / ARIA)
        "div[role='textbox'][aria-label*='comment' i]",
        "div.ql-editor[role='textbox']",
        # Tier 3: Semantic Text Heuristics
        "div.ql-editor:has-text('Add a comment')",
        "div.editor-content:has-text('comment')",
    ],
    "comment_submit": [
        # Tier 1: Canonical Data Attributes
        "button[data-control-name='comment_post']",
        "button.comments-comment-box__submit-button[data-test-comment-submit]",
        # Tier 2: Accessibility Tree (AXTree / ARIA)
        "button[role='button'][aria-label='Post comment']",
        "button.comments-comment-box__submit-button",
        # Tier 3: Semantic Text Heuristics
        "button:has-text('Comment')",
        "button:has-text('Post')",
    ],
    "post_input": [
        # Tier 1: Canonical Data Attributes
        "div.share-box-feed-entry__trigger[data-control-name='share.sharebox_btn']",
        "button[data-test-start-post-button]",
        # Tier 2: Accessibility Tree (AXTree / ARIA)
        "button[role='button'][aria-label*='Start a post' i]",
        "button.artdeco-button[aria-label*='Start a post' i]",
        # Tier 3: Semantic Text Heuristics
        "button:has-text('Start a post')",
    ],
    "post_editor": [
        # Tier 1: Canonical Data Attributes
        "div.share-creation-state__text-editor[data-control-name='post_editor']",
        "div[data-test-share-editor]",
        # Tier 2: Accessibility Tree (AXTree / ARIA)
        "div[role='textbox'][aria-label*='What do you want to talk about' i]",
        "div.tiptap.ProseMirror[role='textbox']",
        "div.ql-editor[role='textbox']",
        # Tier 3: Semantic Text Heuristics
        "div.tiptap.ProseMirror",
    ],
    "post_submit": [
        # Tier 1: Canonical Data Attributes
        "button[data-control-name='share.post_btn']",
        "button[data-test-post-submit-button]",
        # Tier 2: Accessibility Tree (AXTree / ARIA)
        "button[role='button'][aria-label='Post']",
        "button.share-actions__primary-action",
        # Tier 3: Semantic Text Heuristics
        "button:has-text('Post')",
    ],
}


class SelfHealingSelectorEngine:
    """4-tier self-healing selector engine with dynamic overrides caching and graceful fallbacks."""

    def __init__(self, state_store: BaseStateStore | None = None) -> None:
        self.state_store = state_store
        self._overrides: dict[str, str] = {}
        self._load_overrides()

    def _load_overrides(self) -> None:
        """Load persistent selector overrides from state store if available."""
        if self.state_store is None:
            return
        try:
            raw = self.state_store.get_key("selector_overrides")
            if raw:
                if isinstance(raw, dict):
                    self._overrides = {str(k): str(v) for k, v in raw.items()}
                elif isinstance(raw, str):
                    parsed = json.loads(raw)
                    if isinstance(parsed, dict):
                        self._overrides = {str(k): str(v) for k, v in parsed.items()}
        except Exception as err:
            logger.warning("Failed to load selector_overrides from state store: %s", err)

    @property
    def overrides(self) -> dict[str, str]:
        """Return a copy of the current in-memory selector overrides."""
        return dict(self._overrides)

    async def resolve_locator(
        self,
        page: Page,
        action_key: str,
        candidates: list[str],
        timeout_ms: int = 1500,
    ) -> tuple[Locator, str]:
        """Resolve an element locator with 4-tier self-healing fallbacks.

        1. Checks cached Tier 4 override first for action_key. If present and visible, returns it.
        2. Iterates through candidates in priority order (Tier 1 -> Tier 2 -> Tier 3).
        3. When a non-canonical candidate succeeds (index > 0):
           - Logs a warning.
           - Updates in-memory cache and persists override via state_store.put_key("selector_overrides", ...).
        4. If all candidates fail:
           - Raises SelectorDriftError.

        Args:
            page: Playwright Page instance.
            action_key: Canonical identifier for the element/action (e.g. 'comment_submit').
            candidates: Priority-ordered list of selector strings.
            timeout_ms: Per-candidate visibility check timeout in milliseconds.

        Returns:
            tuple[Locator, str]: Resolved Playwright Locator and selector string that matched.

        Raises:
            SelectorDriftError: If all candidates (and override) fail to locate a visible element.
        """
        # Tier 4: Check cached override first
        cached_selector = self._overrides.get(action_key)
        if cached_selector:
            try:
                locator = page.locator(cached_selector).first
                if await locator.is_visible(timeout=timeout_ms):
                    return locator, cached_selector
            except Exception:
                logger.debug(
                    "Cached selector override '%s' for action '%s' no longer resolves; checking candidates",
                    cached_selector,
                    action_key,
                )

        # Iterate candidates in priority order
        for idx, selector in enumerate(candidates):
            try:
                locator = page.locator(selector).first
                if await locator.is_visible(timeout=timeout_ms):
                    if idx > 0:
                        # Non-canonical candidate succeeded; heal and persist
                        logger.warning(
                            "Canonical selector for %s failed; self-healing healed to tier candidate %s",
                            action_key,
                            selector,
                        )
                        self._overrides[action_key] = selector
                        if self.state_store is not None:
                            try:
                                self.state_store.put_key(
                                    "selector_overrides", dict(self._overrides)
                                )
                            except Exception as err:
                                logger.warning(
                                    "Failed persisting selector_overrides to state store: %s",
                                    err,
                                )
                    return locator, selector
            except Exception:
                continue

        # Exhausted all candidates
        raise SelectorDriftError(f"All self-healing selector candidates failed for '{action_key}'")

    async def find_and_click(
        self,
        page: Page,
        action_key: str,
        candidates: list[str],
        timeout_ms: int = 1500,
    ) -> None:
        """Resolve element using self-healing candidates and click it.

        Args:
            page: Playwright Page instance.
            action_key: Canonical identifier for the action/element.
            candidates: Priority-ordered list of selector strings.
            timeout_ms: Per-candidate visibility check timeout in milliseconds.
        """
        locator, _ = await self.resolve_locator(
            page, action_key, candidates, timeout_ms=timeout_ms
        )
        await locator.click()
