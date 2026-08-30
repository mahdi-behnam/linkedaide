"""LinkedIn feed scraper for post discovery and candidate extraction."""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from agent.browser.stealth import detect_challenge_page, humanized_scroll
from agent.config import Settings
from agent.errors import BotDetectionError, ScrapeError, SelectorDriftError
from agent.models.schemas import PostRecord

if TYPE_CHECKING:
    from playwright.async_api import Page


class FeedScraper:
    """Scrapes candidate posts from LinkedIn feed."""

    def __init__(self, page: Page, settings: Settings) -> None:
        self.page = page
        self.settings = settings

    async def scrape_feed(self, *, max_posts: int, seen_hashes: set[str]) -> list[PostRecord]:
        """Scrape new, unseen posts from the feed.

        Args:
            max_posts: Maximum candidate posts to return.
            seen_hashes: Set of previously seen post content hashes.

        Returns:
            list[PostRecord]: List of discovered new posts.

        Raises:
            BotDetectionError: If a security checkpoint / CAPTCHA is encountered.
            SelectorDriftError: If feed root structure is missing from the DOM.
            ScrapeError: On unrecoverable scraping failure.
        """
        # 1. Challenge check
        if detect_challenge_page(self.page):
            raise BotDetectionError(
                f"Bot detection challenge encountered on feed page: {self.page.url}"
            )

        # 2. Verify feed container
        feed_container = self.page.locator(
            "main, div.scaffold-finite-scroll, div.feed-shared-update-v2"
        )
        try:
            container_count = await feed_container.count()
            if container_count == 0:
                # Check for login redirect
                if "/login" in self.page.url or "authwall" in self.page.url:
                    raise ScrapeError("Scraper redirected to login / authwall")
                raise SelectorDriftError(
                    "Feed root container not found in DOM — LinkedIn markup may have changed"
                )
        except BotDetectionError, SelectorDriftError, ScrapeError:
            raise
        except Exception as err:
            raise ScrapeError(f"Failed to locate feed container: {err}") from err

        # 3. Organic scroll
        try:
            await humanized_scroll(self.page, screens=2)
        except Exception:
            pass

        if detect_challenge_page(self.page):
            raise BotDetectionError(f"Bot challenge triggered during feed scroll: {self.page.url}")

        # 4. Extract post cards
        post_locators = self.page.locator("div.feed-shared-update-v2, div[data-urn]")
        card_count = await post_locators.count()

        candidates: list[PostRecord] = []
        now = datetime.now(UTC)

        for i in range(card_count):
            if len(candidates) >= max_posts:
                break

            card = post_locators.nth(i)
            try:
                # Extract URN / URL
                urn = await card.get_attribute("data-urn") or f"urn:li:activity:mock_{i}"
                post_url = f"https://www.linkedin.com/feed/update/{urn}/"

                # Extract Author
                author_el = card.locator(
                    ".update-components-actor__name, .feed-shared-actor__name"
                ).first
                author_name = "LinkedIn Member"
                if await author_el.count() > 0:
                    author_name = (await author_el.inner_text()).strip() or author_name

                # Extract Post Text
                text_el = card.locator(
                    ".update-components-text, .feed-shared-update-v2__description"
                ).first
                post_text = ""
                if await text_el.count() > 0:
                    post_text = (await text_el.inner_text()).strip()

                if not post_text:
                    continue

                content_hash = hashlib.sha256(post_text.encode("utf-8")).hexdigest()
                if content_hash in seen_hashes:
                    continue

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
            except Exception:
                continue

        return candidates
