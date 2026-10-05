"""Reaction action mixin for ActionExecutor."""

from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING, Any

from agent.browser import stealth
from agent.browser.selectors import LINKEDIN_SELECTORS
from agent.errors import BotDetectionError, SelectorDriftError, SessionExpiredError

if TYPE_CHECKING:
    from playwright.async_api import Page

    from agent.browser.biometrics import BiometricController
    from agent.browser.selectors import SelfHealingSelectorEngine
    from agent.config import Settings

logger = logging.getLogger(__name__)


class ReactionMixin:
    """Mixin providing reaction interactions on LinkedIn posts."""

    page: Page
    settings: Settings
    biometrics: BiometricController
    selector_engine: SelfHealingSelectorEngine

    # Methods provided by VerificationMixin
    _capture_screenshot: Any

    async def react_to_post(
        self,
        reaction_type: str = "like",
        item_id: str = "item_action",
        dry_run: bool | None = None,
    ) -> bool:
        """React to a LinkedIn post with humanized dwell and graceful degradation."""
        is_dry_run = dry_run if dry_run is not None else self.settings.dry_run

        if stealth.detect_challenge_page(self.page):
            await self._capture_screenshot(f"challenge_react_{item_id}")
            raise BotDetectionError(f"Bot challenge during reaction check: {self.page.url}")

        if stealth.is_authwall_or_login(self.page):
            raise SessionExpiredError(
                f"LinkedIn session expired during reaction check; redirected to {self.page.url}"
            )

        if is_dry_run:
            logger.info("DRY_RUN: Simulated reaction '%s' on %s", reaction_type, self.page.url)
            return True

        try:
            like_selector = (
                "button[aria-label*='Reaction button state' i], button[aria-label*='React Like'], "
                "button[aria-label*='Like' i], button.react-button__trigger, button.reactions-react-button, "
                "button.feed-shared-social-action-bar__action-button:has-text('Like'), button:has-text('Like')"
            )
            try:
                react_btn, _ = await self.selector_engine.resolve_locator(
                    self.page,
                    "like_btn",
                    candidates=[like_selector, *LINKEDIN_SELECTORS.get("like_btn", [])],
                )
            except SelectorDriftError:
                logger.warning("Reaction button not found on %s", self.page.url)
                return False

            # Check if already reacted
            aria_pressed = (await react_btn.get_attribute("aria-pressed") or "").strip().lower()
            aria_label = (await react_btn.get_attribute("aria-label") or "").lower()
            is_already_reacted = (
                aria_pressed in ("true", "1")
                or "unreact" in aria_label
                or "unlike" in aria_label
                or ("reaction button state" in aria_label and "no reaction" not in aria_label)
            )
            if is_already_reacted:
                logger.info(
                    "Post %s already reacted (%s); skipping click", self.page.url, aria_label
                )
                return True

            norm_type = reaction_type.strip().lower()
            if norm_type in ("", "like"):
                await self.biometrics.click_element(react_btn)
                return True

            # Non-default reaction (e.g. insightful, celebrate, etc.)
            try:
                await react_btn.hover()
                await asyncio.sleep(0.4)
                canonical_reaction = (
                    f"button[data-test-reaction-type='{norm_type}'], "
                    f"button[aria-label*='{norm_type.capitalize()}' i], "
                    f"div.reactions-menu button:has-text('{norm_type.capitalize()}')"
                )
                reaction_menu_candidates = [
                    canonical_reaction,
                    f"button[data-test-reaction-type='{norm_type}']",
                    f"button[aria-label*='{norm_type.capitalize()}' i]",
                    f"div.reactions-menu button:has-text('{norm_type.capitalize()}')",
                ]
                try:
                    reaction_menu_item, _ = await self.selector_engine.resolve_locator(
                        self.page,
                        f"reaction_{norm_type}",
                        candidates=reaction_menu_candidates,
                    )
                    await self.biometrics.click_element(reaction_menu_item)
                    return True
                except SelectorDriftError:
                    logger.warning(
                        "Specific reaction button '%s' not found, falling back to Like", norm_type
                    )
                    await self.biometrics.click_element(react_btn)
                    return True
            except Exception as e:
                logger.warning(
                    "Failed to trigger specific reaction '%s' (%s), falling back to Like",
                    norm_type,
                    e,
                )
                await self.biometrics.click_element(react_btn)
                return True

        except (BotDetectionError, SessionExpiredError):
            raise
        except Exception as err:
            logger.warning("Non-fatal error during reaction attempt on %s: %s", self.page.url, err)
            return False
