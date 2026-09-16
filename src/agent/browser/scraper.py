"""LinkedIn feed scraper for post discovery and candidate extraction."""

from __future__ import annotations

import asyncio
import hashlib
import logging
import re
import urllib.parse
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

from agent.browser.stealth import (
    detect_challenge_page,
    humanized_scroll,
    is_authwall_or_login,
)
from agent.browser.telemetry import capture_dom_telemetry
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


def hashtag_to_feed_url(hashtag: str) -> str:
    """Convert a hashtag or keyword into a LinkedIn hashtag feed URL.

    Handles leading '#', leading/trailing whitespace, full URLs, and URL encoding.

    Examples:
        'python' -> 'https://www.linkedin.com/feed/hashtag/?keywords=python'
        '#Python' -> 'https://www.linkedin.com/feed/hashtag/?keywords=python'
        '#ai_agents' -> 'https://www.linkedin.com/feed/hashtag/?keywords=ai_agents'
        'https://www.linkedin.com/feed/hashtag/?keywords=custom' -> 'https://www.linkedin.com/feed/hashtag/?keywords=custom'

    Raises:
        ValueError: If hashtag is empty or contains only whitespace/hashes.
    """
    clean = hashtag.strip()
    if clean.lower().startswith(("http://", "https://")):
        return clean
    clean = clean.lstrip("#").strip()
    if not clean or set(clean).issubset({"#", " "}):
        raise ValueError(f"Invalid empty hashtag: {hashtag!r}")
    encoded = urllib.parse.quote_plus(clean.lower())
    return f"https://www.linkedin.com/feed/hashtag/?keywords={encoded}"


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

    async def scrape_feed(
        self,
        *,
        max_posts: int,
        seen_hashes: set[str],
        target_url: str | None = None,
    ) -> list[PostRecord]:
        """Scrape new, unseen posts from the feed or a target URL.

        Args:
            max_posts: Maximum candidate posts to return.
            seen_hashes: Set of previously seen post content hashes.
            target_url: Optional specific LinkedIn feed or hashtag URL to navigate to.

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
            await humanized_scroll(self.page, screens=2)
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
        card_selectors = [
            "div[id^='expanded'][id$='MAIN_FEED_RELEVANCE']",
            "div[id^='expanded'][id*='FEED']",
            "div.feed-shared-update-v2",
            "div[data-urn*='urn:li:activity']",
            "div[data-activity-urn]",
            "div[data-id*='urn:li:activity']",
            "div[data-view-name='feed-full-update']",
            "div[data-view-name*='update']",
            "div[class*='feed-shared-update']",
            "div.scaffold-finite-scroll__content div:has(button[aria-label*='Comment'])",
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
                "div[id^='expanded'][id$='MAIN_FEED_RELEVANCE'], div[id^='expanded'][id*='FEED'], div.feed-shared-update-v2, div[data-urn], div.scaffold-finite-scroll__content > div"
            )
            card_count = await post_locators.count()
            logger.info("Fallback card locator found %d card(s)", card_count)

        if card_count == 0:
            await self._capture_telemetry(
                trigger="feed_cards_drift",
                target_selector=", ".join(card_selectors),
            )

        candidates: list[PostRecord] = []
        now = datetime.now(UTC)

        author_selectors = [
            ".update-components-actor__name",
            ".update-components-actor__title span[aria-hidden='true']",
            ".update-components-actor__title",
            "span.update-components-actor__name",
            ".feed-shared-actor__name",
            ".feed-shared-actor__title",
            "a[data-field='actor_name']",
            ".update-components-actor__meta span[aria-hidden='true']",
            ".update-components-actor__container a",
            "a[href*='/in/']",
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

        parsed_card_count = 0
        for i in range(card_count):
            if len(candidates) >= max_posts:
                break

            card = post_locators.nth(i)
            try:
                # 1. Skip non-post recommendation cards or ads without interaction
                try:
                    comment_btn = card.locator(
                        "button:has-text('Comment'), button[aria-label*='Comment']"
                    ).first
                    if await comment_btn.count() == 0:
                        card_raw = (await card.inner_text()).strip()
                        if "Recommended for you" in card_raw or "Promoted" in card_raw:
                            logger.debug("Skipping non-post card %d (recommendation/ad)", i)
                            continue
                except Exception:
                    pass

                # 2. Extract URN / URL
                urn = (
                    await card.get_attribute("data-urn")
                    or await card.get_attribute("data-activity-urn")
                    or await card.get_attribute("data-id")
                )
                if not urn:
                    card_id = await card.get_attribute("id") or ""
                    if "urn:li:activity:" in card_id:
                        urn_match = re.search(r"urn:li:activity:\d+", card_id)
                        if urn_match:
                            urn = urn_match.group(0)
                    elif "urn:li:ugcPost:" in card_id:
                        urn_match = re.search(r"urn:li:ugcPost:\d+", card_id)
                        if urn_match:
                            urn = urn_match.group(0)
                    elif card_id.startswith("expanded"):
                        clean_key = (
                            card_id.replace("expanded", "")
                            .replace("FeedType_MAIN_FEED_RELEVANCE", "")
                            .replace("MAIN_FEED_RELEVANCE", "")
                            .strip()
                        )
                        if clean_key:
                            urn = f"urn:li:activity:{clean_key}"

                if not urn:
                    try:
                        inner_urn = card.locator(
                            "[data-urn], [data-activity-urn], [data-id], a[href*='/feed/update/urn:li:activity:'], a[href*='urn:li:activity:']"
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
                                elif "urn:li:ugcPost:" in href:
                                    urn = (
                                        "urn:li:ugcPost:"
                                        + href.split("urn:li:ugcPost:")[1]
                                        .split("/")[0]
                                        .split("?")[0]
                                    )
                    except Exception:
                        pass

                if not urn:
                    urn = f"urn:li:activity:scraped_{i}_{int(now.timestamp())}"

                post_url = f"https://www.linkedin.com/feed/update/{urn}/"

                # 3. Extract Author Name
                author_name = "LinkedIn Member"
                try:
                    in_links = card.locator("a[href*='/in/'], a[href*='/company/']")
                    in_count = await in_links.count()
                    # First priority: Link with network degree indicator (• 1st, • 2nd, • 3rd, • Following)
                    for idx in range(in_count):
                        raw_a = (await in_links.nth(idx).inner_text()).strip()
                        if not raw_a or raw_a.startswith("http"):
                            continue
                        if any(
                            deg in raw_a
                            for deg in ("• 1st", "• 2nd", "• 3rd", "• Following", "• Follow")
                        ):
                            clean_a = raw_a.split("\n")[0].split("•")[0].split(",")[0].strip()
                            if clean_a:
                                author_name = clean_a
                                break
                    # Second priority: Any profile link not inside social proof ("likes this")
                    if author_name == "LinkedIn Member" and in_count > 0:
                        for idx in range(in_count):
                            raw_a = (await in_links.nth(idx).inner_text()).strip()
                            if (
                                raw_a
                                and not raw_a.startswith("http")
                                and not any(
                                    sp in raw_a.lower()
                                    for sp in ("likes this", "reposted this", "celebrates this")
                                )
                            ):
                                clean_a = raw_a.split("\n")[0].split("•")[0].split(",")[0].strip()
                                if clean_a:
                                    author_name = clean_a
                                    break
                except Exception:
                    pass

                if author_name == "LinkedIn Member":
                    for a_sel in author_selectors:
                        author_el = card.locator(a_sel).first
                        if await author_el.count() > 0:
                            raw_name = (await author_el.inner_text()).strip()
                            if raw_name and len(raw_name) > 1 and not raw_name.startswith("http"):
                                name_candidate = (
                                    raw_name.split("\n")[0].split("•")[0].split(",")[0].strip()
                                )
                                if name_candidate:
                                    author_name = name_candidate
                                    break

                # Clean any trailing profile badge noise
                if author_name != "LinkedIn Member":
                    author_name = re.sub(
                        r"\b(Verified Profile|Premium Profile|Open to work|Following|Follow|1st|2nd|3rd|\+)\b",
                        "",
                        author_name,
                        flags=re.IGNORECASE,
                    ).strip()

                # 4. Extract Post Text
                post_text = ""
                # Priority 1: Modern expandable-text-box or description components
                try:
                    expandable = card.locator(
                        "[data-testid='expandable-text-box'], .update-components-text, .feed-shared-update-v2__description"
                    ).first
                    if await expandable.count() > 0:
                        raw_exp = (await expandable.inner_text()).strip()
                        if len(raw_exp) > 20:
                            post_text = raw_exp
                except Exception:
                    pass

                # Priority 2: Extract candidate <p> elements, sorted by length descending
                if not post_text:
                    try:
                        paras_loc = card.locator("p")
                        p_count = await paras_loc.count()
                        valid_paras: list[str] = []
                        for p_idx in range(p_count):
                            p_txt = (await paras_loc.nth(p_idx).inner_text()).strip()
                            if len(p_txt) > 25 and not any(
                                sp in p_txt.lower()
                                for sp in (
                                    "likes this",
                                    "reposted this",
                                    "celebrates this",
                                    "recommended for you",
                                )
                            ):
                                valid_paras.append(p_txt)
                        if valid_paras:
                            valid_paras.sort(key=len, reverse=True)
                            post_text = valid_paras[0]
                    except Exception:
                        pass

                # Priority 3: Fallback text selectors
                if not post_text:
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

                # Strip trailing "...see more" / "… more" artifacts if present
                for suffix in (
                    "… more",
                    "...more",
                    "…more",
                    "…see more",
                    "...see more",
                    "See more",
                ):
                    if post_text.endswith(suffix):
                        post_text = post_text[: -len(suffix)].strip()

                if not post_text or len(post_text) < 20:
                    continue

                # Skip known UI navigation artifacts
                if post_text.lower() in {
                    "saved items",
                    "groups",
                    "newsletters",
                    "events",
                    "profile viewers",
                    "view all analytics",
                    "post impressions",
                }:
                    continue

                parsed_card_count += 1

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

        if card_count > 0 and parsed_card_count == 0:
            logger.warning(
                "Feed card layout drift: %d card(s) detected but text extraction failed on all of them",
                card_count,
            )
            await self._capture_telemetry(
                trigger="feed_card_layout_drift",
                target_selector=", ".join(text_selectors),
            )

        logger.info(
            "Scraped %d new candidate post(s) from %d DOM cards", len(candidates), card_count
        )
        return candidates
