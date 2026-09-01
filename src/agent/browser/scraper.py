"""LinkedIn feed scraper for post discovery and candidate extraction."""

from __future__ import annotations

import asyncio
import hashlib
import logging
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING

from agent.browser.stealth import (
    detect_challenge_page,
    humanized_scroll,
    is_authwall_or_login,
)
from agent.config import Settings
from agent.errors import (
    BotDetectionError,
    ScrapeError,
    SelectorDriftError,
    SessionExpiredError,
)
from agent.models.schemas import PostRecord

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

    async def scrape_feed(self, *, max_posts: int, seen_hashes: set[str]) -> list[PostRecord]:
        """Scrape new, unseen posts from the feed.

        Args:
            max_posts: Maximum candidate posts to return.
            seen_hashes: Set of previously seen post content hashes.

        Returns:
            list[PostRecord]: List of discovered new posts.

        Raises:
            BotDetectionError: If a security checkpoint / CAPTCHA is encountered.
            SessionExpiredError: If redirected to login page or authwall.
            SelectorDriftError: If feed root structure is missing from the DOM.
            ScrapeError: On unrecoverable scraping failure.
        """
        # 1. Challenge check (True bot challenge / CAPTCHA)
        if detect_challenge_page(self.page):
            screenshot_path = await self._capture_screenshot("feed_challenge")
            raise BotDetectionError(
                f"Bot detection challenge encountered on feed page: {self.page.url} (screenshot: {screenshot_path})"
            )

        # 2. Check for login redirect / authwall (Session invalid/expired)
        if is_authwall_or_login(self.page):
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
                    raise SessionExpiredError("Scraper redirected to login / authwall")
                screenshot_path = await self._capture_screenshot("feed_selector_drift")
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
                "div.feed-shared-update-v2, div[data-urn], div[data-id], div.scaffold-finite-scroll__content",
                timeout=8000,
            )
        except Exception:
            pass

        # 4. Organic scroll to load more dynamic content
        try:
            await humanized_scroll(self.page, screens=2)
        except Exception:
            pass

        # Settle dynamic DOM updates
        await asyncio.sleep(1.5)

        if detect_challenge_page(self.page):
            screenshot_path = await self._capture_screenshot("feed_challenge_after_scroll")
            raise BotDetectionError(f"Bot challenge triggered during feed scroll: {self.page.url}")

        # Capture diagnostic screenshot of the feed
        screenshot_path = await self._capture_screenshot("feed_view")
        logger.info("Captured feed snapshot at: %s", screenshot_path)

        # 5. Multi-tier card selector resolution
        card_selectors = [
            "div.feed-shared-update-v2",
            "div[data-urn*='urn:li:activity']",
            "div[data-activity-urn]",
            "div[data-id*='urn:li:activity']",
            "div[data-view-name='feed-full-update']",
            "div[data-view-name*='update']",
            "div[class*='feed-shared-update']",
            "div[componentkey]",
            "div.scaffold-finite-scroll__content > div:has(.update-components-actor)",
            "div.scaffold-finite-scroll__content > div:has([class*='actor'])",
            "div:has(div.update-components-actor)",
            "div:has([class*='feed-shared-actor'])",
            "div.scaffold-finite-scroll__content > div",
        ]

        post_locators = None
        card_count = 0
        for selector in card_selectors:
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
                "div.feed-shared-update-v2, div[data-urn], div[componentkey], div.scaffold-finite-scroll__content > div"
            )
            card_count = await post_locators.count()
            logger.info("Fallback card locator found %d card(s)", card_count)

        candidates: list[PostRecord] = []
        now = datetime.now(UTC)

        author_selectors = [
            "a[href*='/in/']",
            ".update-components-actor__name",
            ".feed-shared-actor__name",
            "a[data-field='actor_name']",
            ".update-components-actor__meta span[aria-hidden='true']",
            ".update-components-actor__title span[aria-hidden='true']",
            ".feed-shared-actor__title",
            "span.update-components-actor__name",
            ".update-components-actor__container a",
            "span[dir='ltr']",
            "span[dir='rtl']",
            "h3",
            "h4",
        ]

        text_selectors = [
            ".update-components-text",
            ".feed-shared-update-v2__description",
            ".feed-shared-text",
            ".feed-shared-inline-show-more-text",
            ".feed-shared-update-v2__commentary",
            "div.feed-shared-update-v2__description-wrapper",
            "span.break-words",
            "div.break-words",
            "div[dir='ltr']",
            "div[dir='rtl']",
            "span[dir='ltr']",
            "span[dir='rtl']",
            "p",
        ]

        for i in range(card_count):
            if len(candidates) >= max_posts:
                break

            card = post_locators.nth(i)
            try:
                # Extract URN / URL
                urn = (
                    await card.get_attribute("data-urn")
                    or await card.get_attribute("data-activity-urn")
                    or await card.get_attribute("data-id")
                )
                if not urn:
                    try:
                        inner_urn = card.locator(
                            "[data-urn], [data-activity-urn], [data-id], a[href*='/feed/update/urn:li:activity:']"
                        ).first
                        if await inner_urn.count() > 0:
                            urn = (
                                await inner_urn.get_attribute("data-urn")
                                or await inner_urn.get_attribute("data-activity-urn")
                                or await inner_urn.get_attribute("data-id")
                            )
                            if not urn:
                                href = await inner_urn.get_attribute("href") or ""
                                if "urn:li:activity:" in href:
                                    urn = (
                                        "urn:li:activity:"
                                        + href.split("urn:li:activity:")[1]
                                        .split("/")[0]
                                        .split("?")[0]
                                    )
                    except Exception:
                        pass

                if not urn:
                    urn = f"urn:li:activity:scraped_{i}_{int(now.timestamp())}"

                post_url = f"https://www.linkedin.com/feed/update/{urn}/"

                # Extract Author Name
                author_name = "LinkedIn Member"
                for a_sel in author_selectors:
                    author_el = card.locator(a_sel).first
                    if await author_el.count() > 0:
                        raw_name = (await author_el.inner_text()).strip()
                        if raw_name and len(raw_name) > 1 and not raw_name.startswith("http"):
                            author_name = raw_name.split("\n")[0].strip()
                            break

                # Extract Post Text
                post_text = ""
                for t_sel in text_selectors:
                    text_el = card.locator(t_sel).first
                    try:
                        if await text_el.count() > 0:
                            raw_t = (await text_el.inner_text()).strip()
                            if raw_t and isinstance(raw_t, str) and len(raw_t) > 0:
                                post_text = raw_t
                                break
                    except Exception:
                        continue

                if not post_text:
                    continue

                content_hash = hashlib.sha256(post_text.encode("utf-8")).hexdigest()
                if content_hash in seen_hashes:
                    logger.debug("Skipping already seen post: %s (author: %s)", urn, author_name)
                    continue

                logger.info(
                    "Discovered post by '%s' (%d chars): %s...",
                    author_name,
                    len(post_text),
                    post_text[:100].replace("\n", " "),
                )

                record = PostRecord(
                    post_urn=urn,
                    post_url=post_url,
                    author_name=author_name,
                    post_text=post_text,
                    content_hash=content_hash,
                    scraped_at=now,
                )
                candidates.append(record)
                seen_hashes.add(content_hash)
            except Exception as parse_err:
                logger.debug("Failed to parse card %d: %s", i, parse_err)
                continue

        logger.info(
            "Scraped %d new candidate post(s) from %d DOM cards", len(candidates), card_count
        )
        return candidates
