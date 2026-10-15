"""LinkedIn feed scraper for post discovery and candidate extraction."""

from __future__ import annotations

import asyncio
import logging
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

from agent.browser.feed_parser import CARD_SELECTORS, TEXT_SELECTORS, parse_feed_card
from agent.browser.media_extractor import extract_media_from_card
from agent.browser.stealth import (
    detect_challenge_page,
    humanized_scroll,
    is_authwall_or_login,
    wait_for_login_redirect,
)
from agent.browser.telemetry import capture_dom_telemetry
from agent.config import Settings
from agent.errors import (
    BotDetectionError,
    ScrapeError,
    SelectorDriftError,
    SessionExpiredError,
)
from agent.models import PostRecord

if TYPE_CHECKING:
    from playwright.async_api import Page

logger = logging.getLogger(__name__)


class FeedScraper:
    """Scrapes candidate posts from LinkedIn feed."""

    def __init__(self, page: Page, settings: Settings, debug_dir: Path | None = None) -> None:
        self.page = page
        self.settings = settings
        self.debug_dir = debug_dir or (Path("debug") / "screenshots")
        self.debug_dir.mkdir(parents=True, exist_ok=True)

    async def _capture_screenshot(self, name: str) -> str:
        """Capture debug screenshot to inspect what the browser saw."""
        timestamp = datetime.now(UTC).strftime("%Y%m%d_%H%M%S")
        filename = f"{name}_{timestamp}.png"
        path = self.debug_dir / filename
        try:
            await self.page.screenshot(path=str(path), full_page=False)
            return str(path)
        except Exception:
            return ""

    async def _capture_telemetry(
        self,
        trigger: str,
        target_selector: str | None = None,
        item_id: str | None = None,
    ) -> str | None:
        """Capture DOM telemetry defensively without disrupting error handling."""
        try:
            call_kwargs: dict[str, Any] = {"trigger": trigger}
            if target_selector is not None:
                call_kwargs["target_selector"] = target_selector
            if item_id is not None:
                call_kwargs["item_id"] = item_id
            return await capture_dom_telemetry(self.page, **call_kwargs)
        except Exception as err:
            logger.debug("Failed capturing DOM telemetry for %s: %s", trigger, err)
            return None

    async def extract_media_from_card(self, card: Any) -> tuple[str | None, str | None]:
        """Extract high-resolution media URL and detected media type from a post card locator."""
        return await extract_media_from_card(card)

    async def scrape_feed(
        self,
        *,
        max_posts: int,
        seen_hashes: set[str],
        target_url: str | None = None,
        screens: int = 2,
    ) -> list[PostRecord]:
        """Scrape new, unseen posts from the feed or a target URL.

        Args:
            max_posts: Maximum candidate posts to return.
            seen_hashes: Set of previously seen post content hashes.
            target_url: Optional specific LinkedIn feed or hashtag URL to navigate to.
            screens: Number of screen lengths to organically scroll (default: 2).

        Returns:
            list[PostRecord]: List of discovered new posts.

        Raises:
            BotDetectionError: If a security checkpoint / CAPTCHA is encountered.
            SessionExpiredError: If redirected to login page or authwall.
            SelectorDriftError: If feed root structure is missing from the DOM.
            ScrapeError: On unrecoverable scraping failure.
        """
        # Optional navigation to target feed
        if target_url:
            clean_target = target_url.strip()
            if clean_target:
                logger.info("Navigating scraper to target feed: %s", clean_target)
                try:
                    await self.page.goto(clean_target, wait_until="domcontentloaded", timeout=30000)
                except Exception as err:
                    logger.warning(
                        "Navigation to target URL '%s' completed with warning: %s",
                        clean_target,
                        err,
                    )

        # 1. Challenge check (True bot challenge / CAPTCHA)
        if detect_challenge_page(self.page):
            screenshot_path = await self._capture_screenshot("feed_challenge")
            await self._capture_telemetry("feed_challenge")
            raise BotDetectionError(
                f"Bot detection challenge encountered on feed page: {self.page.url} (screenshot: {screenshot_path})"
            )

        # 2. Check for login redirect / authwall (Session invalid/expired)
        if is_authwall_or_login(self.page):
            is_authenticated = await wait_for_login_redirect(self.page, timeout=15.0)
            if not is_authenticated:
                screenshot_path = await self._capture_screenshot("feed_session_expired")
                raise SessionExpiredError(
                    f"LinkedIn session expired or unauthenticated (redirected to: {self.page.url})"
                )

        # 3. Verify feed container
        feed_container = self.page.locator(
            "main, div.scaffold-finite-scroll, div.feed-shared-update-v2, div.scaffold-layout__main"
        )
        try:
            container_count = await feed_container.count()
            if container_count == 0:
                if is_authwall_or_login(self.page):
                    is_authenticated = await wait_for_login_redirect(self.page, timeout=15.0)
                    if not is_authenticated:
                        raise SessionExpiredError("Scraper redirected to login / authwall")
                screenshot_path = await self._capture_screenshot("feed_selector_drift")
                await self._capture_telemetry(
                    trigger="feed_container_drift",
                    target_selector="main, div.scaffold-finite-scroll, div.feed-shared-update-v2, div.scaffold-layout__main",
                )
                raise SelectorDriftError(
                    f"Feed root container not found in DOM (screenshot: {screenshot_path})"
                )
        except (BotDetectionError, SessionExpiredError, SelectorDriftError, ScrapeError):
            raise
        except Exception as err:
            raise ScrapeError(f"Failed to locate feed container: {err}") from err

        # Wait briefly for dynamic feed cards to hydrate
        try:
            await self.page.wait_for_selector(
                "div[id^='expanded'][id$='MAIN_FEED_RELEVANCE'], div[id^='expanded'][id*='FEED'], div.feed-shared-update-v2, div[data-urn], div[data-id], div.scaffold-finite-scroll__content",
                timeout=8000,
            )
        except Exception:
            pass

        # 4. Organic scroll to load more dynamic content
        try:
            await humanized_scroll(self.page, screens=max(1, screens))
        except Exception:
            pass

        # Settle dynamic DOM updates
        await asyncio.sleep(1.5)

        if detect_challenge_page(self.page):
            screenshot_path = await self._capture_screenshot("feed_challenge_after_scroll")
            await self._capture_telemetry("feed_challenge")
            raise BotDetectionError(f"Bot challenge triggered during feed scroll: {self.page.url}")

        # Capture diagnostic screenshot of the feed
        screenshot_path = await self._capture_screenshot("feed_view")
        logger.info("Captured feed snapshot at: %s", screenshot_path)

        # 5. Multi-tier card selector resolution
        post_locators = None
        card_count = 0
        for selector in CARD_SELECTORS:
            loc = self.page.locator(selector)
            try:
                count = await loc.count()
                if count > 0:
                    post_locators = loc
                    card_count = count
                    logger.info("Matched %d feed card(s) using selector: '%s'", count, selector)
                    break
            except Exception:
                continue

        if post_locators is None or card_count == 0:
            post_locators = self.page.locator(
                "div[id^='expanded'][id$='MAIN_FEED_RELEVANCE'], div[id^='expanded'][id*='FEED'], div.feed-shared-update-v2, div[data-urn], div.scaffold-finite-scroll__content > div"
            )
            card_count = await post_locators.count()
            logger.info("Fallback card locator found %d card(s)", card_count)

        if card_count == 0:
            await self._capture_telemetry(
                trigger="feed_cards_drift",
                target_selector=", ".join(CARD_SELECTORS),
            )

        candidates: list[PostRecord] = []
        now = datetime.now(UTC)
        parsed_card_count = 0

        for i in range(card_count):
            if len(candidates) >= max_posts:
                break

            card = post_locators.nth(i)
            try:
                record, reason = await parse_feed_card(card, i, now, seen_hashes)
                if record is not None:
                    parsed_card_count += 1
                    candidates.append(record)
                    seen_hashes.add(record.content_hash)
                    logger.info(
                        "Discovered post by '%s' (%d chars): %s...",
                        record.author_name,
                        len(record.post_text),
                        record.post_text[:100].replace("\n", " "),
                    )
                elif reason and reason.startswith("already_seen"):
                    parsed_card_count += 1
                    logger.debug("Skipping already seen post: %s", reason)
            except Exception as parse_err:
                logger.debug("Failed to parse card %d: %s", i, parse_err)
                continue

        if card_count > 0 and parsed_card_count == 0:
            logger.warning(
                "Feed card layout drift: %d card(s) detected but text extraction failed on all of them",
                card_count,
            )
            await self._capture_telemetry(
                trigger="feed_card_layout_drift",
                target_selector=", ".join(TEXT_SELECTORS),
            )

        logger.info(
            "Scraped %d new candidate post(s) from %d DOM cards", len(candidates), card_count
        )
        return candidates


__all__ = ["FeedScraper"]
