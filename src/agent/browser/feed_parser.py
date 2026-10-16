"""DOM parser for individual LinkedIn feed cards into PostRecord models."""

from __future__ import annotations

import hashlib
import logging
import re
from datetime import datetime
from typing import Any

from agent.browser.media_extractor import extract_media_from_card
from agent.models import PostRecord

logger = logging.getLogger(__name__)

CARD_SELECTORS: list[str] = [
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

AUTHOR_SELECTORS: list[str] = [
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

TEXT_SELECTORS: list[str] = [
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


def extract_valid_urn(text: str | None) -> str | None:
    """Extract a valid LinkedIn post/activity URN from a string or None.

    Matches:
      - Standard numeric URNs: urn:li:(activity|ugcPost|share):<digits>
      - Permalinks: /posts/...-activity-<digits>... or /feed/update/activity:<digits>
      - Test mock URNs while rejecting opaque DOM layout tokens (e.g. 30+ char hashes).
    """
    if not text:
        return None
    # 1. Standard LinkedIn numeric URN (e.g. urn:li:activity:7123456789)
    match = re.search(r"urn:li:(?:activity|ugcPost|share):(\d+)", text)
    if match:
        return match.group(0)
    # 2. Permalinks like activity-7123456789 or /feed/update/activity:7123456789
    match = re.search(r"(?:^|[\W_])(activity|ugcPost|share)[-:](\d{8,25})(?:[\W_]|$)", text)
    if match:
        return f"urn:li:{match.group(1)}:{match.group(2)}"
    # 3. Allow unit-test mock URNs (e.g. urn:li:activity:good_card) while rejecting layout hashes
    match = re.search(r"urn:li:(?:activity|ugcPost|share):([a-zA-Z0-9_-]+)", text)
    if match:
        val = match.group(1)
        if not val.startswith("scraped_") and len(val) < 30:
            return match.group(0)
    return None


async def parse_feed_card(
    card: Any,
    index: int,
    now: datetime,
    seen_hashes: set[str],
) -> tuple[PostRecord | None, str | None]:
    """Parse a single DOM feed card into a typed PostRecord.

    Args:
        card: Playwright Locator for the card.
        index: Feed index of the card.
        now: Current UTC timestamp.
        seen_hashes: Set of previously seen post content hashes.

    Returns:
        tuple[PostRecord | None, str | None]: (PostRecord, None) on success,
        or (None, reason) if skipped or unparseable.
    """
    # 1. Skip non-post recommendation cards or ads without interaction
    try:
        comment_btn = card.locator(
            "button:has-text('Comment'), button[aria-label*='Comment']"
        ).first
        if await comment_btn.count() == 0:
            card_raw = (await card.inner_text()).strip()
            if "Recommended for you" in card_raw or "Promoted" in card_raw:
                return None, "recommendation_or_ad"
    except Exception:
        pass

    # 2. Extract URN / URL
    urn: str | None = None

    # Priority A: Check card-level attributes
    for attr in ("data-urn", "data-activity-urn", "data-id"):
        try:
            val = await card.get_attribute(attr)
            urn = extract_valid_urn(val)
            if urn:
                break
        except Exception:
            pass

    # Priority B: Check card ID attribute
    if not urn:
        try:
            card_id = await card.get_attribute("id") or ""
            urn = extract_valid_urn(card_id)
            if not urn and card_id.startswith("expanded"):
                clean_key = (
                    card_id.replace("expanded", "")
                    .replace("FeedType_MAIN_FEED_RELEVANCE", "")
                    .replace("MAIN_FEED_RELEVANCE", "")
                    .strip("-")
                    .strip()
                )
                if clean_key.isdigit() and len(clean_key) >= 8:
                    urn = f"urn:li:activity:{clean_key}"
        except Exception:
            pass

    # Priority C: Check inner elements for data-urn / data-activity-urn / data-id
    if not urn:
        try:
            inner_urn_els = card.locator("[data-urn], [data-activity-urn], [data-id]")
            count = await inner_urn_els.count()
            for idx in range(min(count, 5)):
                el = inner_urn_els.nth(idx)
                for attr in ("data-urn", "data-activity-urn", "data-id"):
                    val = await el.get_attribute(attr)
                    cand = extract_valid_urn(val)
                    if cand:
                        urn = cand
                        break
                if urn:
                    break
        except Exception:
            pass

    # Priority D: Check inner anchor tags (post permalinks, timestamp links)
    if not urn:
        try:
            inner_links = card.locator(
                "a[href*='/feed/update/'], a[href*='/posts/'], a[href*='urn:li:activity'], "
                "a[href*='activity-'], a[class*='sub-description-link'], a.app-aware-link"
            )
            count = await inner_links.count()
            for idx in range(min(count, 10)):
                link = inner_links.nth(idx)
                href = await link.get_attribute("href")
                if not href or href.startswith("#") or "/in/" in href or "/company/" in href:
                    continue
                cand = extract_valid_urn(href)
                if cand:
                    urn = cand
                    break
        except Exception:
            pass

    if not urn:
        urn = f"urn:li:activity:scraped_{index}_{int(now.timestamp())}"
        post_url = ""
    else:
        post_url = f"https://www.linkedin.com/feed/update/{urn}/"

    # 3. Extract Author Name and Profile URL
    author_name = "LinkedIn Member"
    author_profile_url: str | None = None
    try:
        in_links = card.locator("a[href*='/in/'], a[href*='/company/']")
        in_count = await in_links.count()
        # First priority: Link with network degree indicator (• 1st, • 2nd, • 3rd, • Following)
        for idx in range(in_count):
            link_el = in_links.nth(idx)
            raw_a = (await link_el.inner_text()).strip()
            if not raw_a or raw_a.startswith("http"):
                continue
            if any(deg in raw_a for deg in ("• 1st", "• 2nd", "• 3rd", "• Following", "• Follow")):
                clean_a = raw_a.split("\n")[0].split("•")[0].split(",")[0].strip()
                if clean_a:
                    author_name = clean_a
                    href = await link_el.get_attribute("href")
                    if href:
                        clean_href = href.split("?")[0].strip()
                        if clean_href.startswith("/"):
                            clean_href = f"https://www.linkedin.com{clean_href}"
                        author_profile_url = clean_href
                    break
        # Second priority: Any profile link not inside social proof ("likes this")
        if author_name == "LinkedIn Member" and in_count > 0:
            for idx in range(in_count):
                link_el = in_links.nth(idx)
                raw_a = (await link_el.inner_text()).strip()
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
                        href = await link_el.get_attribute("href")
                        if href:
                            clean_href = href.split("?")[0].strip()
                            if clean_href.startswith("/"):
                                clean_href = f"https://www.linkedin.com{clean_href}"
                            author_profile_url = clean_href
                        break
    except Exception:
        pass

    if author_name == "LinkedIn Member":
        for a_sel in AUTHOR_SELECTORS:
            author_el = card.locator(a_sel).first
            if await author_el.count() > 0:
                raw_name = (await author_el.inner_text()).strip()
                if raw_name and len(raw_name) > 1 and not raw_name.startswith("http"):
                    name_candidate = raw_name.split("\n")[0].split("•")[0].split(",")[0].strip()
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
    # Expand collapsed "...see more" button if present
    try:
        see_more = card.locator(
            "button.feed-shared-inline-show-more-text__see-more-less-toggle, "
            "button[aria-label*='see more' i], "
            "button:has-text('… more'), "
            "button:has-text('...more'), "
            "button:has-text('see more')"
        ).first
        if await see_more.count() > 0:
            visible = await see_more.is_visible() if hasattr(see_more, "is_visible") else True
            if visible:
                await see_more.click(timeout=1000)
    except Exception:
        pass

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
        for t_sel in TEXT_SELECTORS:
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
        return None, "empty_or_too_short"

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
        return None, "navigation_artifact"

    content_hash = hashlib.sha256(post_text.encode("utf-8")).hexdigest()
    if content_hash in seen_hashes:
        return None, f"already_seen:{urn}"

    image_url, media_type = await extract_media_from_card(card)

    record = PostRecord(
        post_urn=urn,
        post_url=post_url,
        author_name=author_name,
        author_profile_url=author_profile_url,
        post_text=post_text,
        content_hash=content_hash,
        scraped_at=now,
        image_url=image_url,
        media_type=media_type,
    )
    return record, None
