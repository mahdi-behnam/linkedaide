"""Unit tests for FeedScraper extracting candidate posts."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from pydantic import SecretStr

from agent.browser.feed_parser import extract_valid_urn, parse_feed_card
from agent.browser.scraper import FeedScraper
from agent.browser.url_utils import hashtag_to_feed_url
from agent.config import Settings
from agent.errors import BotDetectionError, SelectorDriftError, SessionExpiredError


@pytest.fixture
def mock_settings(tmp_path: Path) -> Settings:
    return Settings(
        nvidia_nim_api_key=SecretStr("nvapi-test"),
        nim_model_primary="primary-model",
        nim_model_fallback="fallback-model",
        telegram_bot_token=SecretStr("123:token"),
        telegram_authorized_chat_id=12345,
        user_focus_areas=["AI"],
        max_suggestions_per_run=5,
    )


@pytest.mark.asyncio
async def test_scraper_challenge_detection_raises_bot_error(mock_settings: Settings) -> None:
    page = MagicMock()
    page.url = "https://www.linkedin.com/checkpoint/challenge"

    scraper = FeedScraper(page, mock_settings)
    with pytest.raises(BotDetectionError, match="challenge"):
        await scraper.scrape_feed(max_posts=5, seen_hashes=set())


@pytest.mark.asyncio
async def test_scraper_missing_feed_container_raises_selector_drift(
    mock_settings: Settings,
) -> None:
    page = MagicMock()
    page.url = "https://www.linkedin.com/feed/"

    locator = MagicMock()
    locator.count = AsyncMock(return_value=0)
    page.locator = MagicMock(return_value=locator)

    scraper = FeedScraper(page, mock_settings)
    with pytest.raises(SelectorDriftError, match="Feed root container not found"):
        await scraper.scrape_feed(max_posts=5, seen_hashes=set())


@pytest.mark.asyncio
async def test_scraper_extracts_posts_and_deduplicates(mock_settings: Settings) -> None:
    page = MagicMock()
    page.url = "https://www.linkedin.com/feed/"

    # Mock container locator
    container_loc = MagicMock()
    container_loc.count = AsyncMock(return_value=1)

    # Mock post cards
    card1 = MagicMock()
    card1.get_attribute = AsyncMock(return_value="urn:li:activity:1001")
    actor1 = MagicMock()
    actor1.count = AsyncMock(return_value=1)
    actor1.inner_text = AsyncMock(return_value="Alice Smith")
    card1.locator.return_value.first = actor1

    text1 = MagicMock()
    text1.count = AsyncMock(return_value=1)
    text1.inner_text = AsyncMock(return_value="Exciting advancements in AI Agents and Python 3.14.")

    def card1_locator(selector: str) -> MagicMock:
        loc = MagicMock()
        if "actor" in selector:
            loc.first = actor1
        elif "text" in selector or "description" in selector:
            loc.first = text1
        else:
            unmatched = MagicMock()
            unmatched.count = AsyncMock(return_value=0)
            loc.first = unmatched
        return loc

    card1.locator = MagicMock(side_effect=card1_locator)

    # Mock cards collection locator
    cards_loc = MagicMock()
    cards_loc.count = AsyncMock(return_value=1)
    cards_loc.nth = MagicMock(return_value=card1)

    def page_locator(selector: str) -> MagicMock:
        if "feed-shared-update-v2" in selector and "div." not in selector:
            return cards_loc
        if "main" in selector:
            return container_loc
        return cards_loc

    page.locator = MagicMock(side_effect=page_locator)

    scraper = FeedScraper(page, mock_settings)
    seen_hashes: set[str] = set()

    posts = await scraper.scrape_feed(max_posts=5, seen_hashes=seen_hashes)
    assert len(posts) == 1
    assert posts[0].post_urn == "urn:li:activity:1001"
    assert posts[0].author_name == "Alice Smith"
    assert "AI Agents" in posts[0].post_text
    assert len(seen_hashes) == 1

    # Second pass with same seen_hashes should skip
    posts2 = await scraper.scrape_feed(max_posts=5, seen_hashes=seen_hashes)
    assert len(posts2) == 0


@pytest.mark.asyncio
async def test_scraper_challenge_detection_captures_telemetry(mock_settings: Settings) -> None:
    page = MagicMock()
    page.url = "https://www.linkedin.com/checkpoint/challenge"

    with patch(
        "agent.browser.scraper.capture_dom_telemetry", new_callable=AsyncMock
    ) as mock_telemetry:
        scraper = FeedScraper(page, mock_settings)
        with pytest.raises(BotDetectionError):
            await scraper.scrape_feed(max_posts=5, seen_hashes=set())

        mock_telemetry.assert_awaited_once_with(page, trigger="feed_challenge")


@pytest.mark.asyncio
async def test_scraper_container_drift_captures_telemetry(mock_settings: Settings) -> None:
    page = MagicMock()
    page.url = "https://www.linkedin.com/feed/"

    locator = MagicMock()
    locator.count = AsyncMock(return_value=0)
    page.locator = MagicMock(return_value=locator)

    with patch(
        "agent.browser.scraper.capture_dom_telemetry", new_callable=AsyncMock
    ) as mock_telemetry:
        scraper = FeedScraper(page, mock_settings)
        with pytest.raises(SelectorDriftError):
            await scraper.scrape_feed(max_posts=5, seen_hashes=set())

        mock_telemetry.assert_awaited_once()
        call_kwargs = mock_telemetry.call_args.kwargs
        assert call_kwargs["trigger"] == "feed_container_drift"
        assert "main" in call_kwargs["target_selector"]


@pytest.mark.asyncio
async def test_scraper_card_resolution_drift_captures_telemetry(mock_settings: Settings) -> None:
    page = MagicMock()
    page.url = "https://www.linkedin.com/feed/"

    container_loc = MagicMock()
    container_loc.count = AsyncMock(return_value=1)

    empty_cards_loc = MagicMock()
    empty_cards_loc.count = AsyncMock(return_value=0)

    def page_locator(selector: str) -> MagicMock:
        if "main" in selector:
            return container_loc
        return empty_cards_loc

    page.locator = MagicMock(side_effect=page_locator)
    page.wait_for_selector = AsyncMock()

    with (
        patch(
            "agent.browser.scraper.capture_dom_telemetry", new_callable=AsyncMock
        ) as mock_telemetry,
        patch("agent.browser.scraper.humanized_scroll", new_callable=AsyncMock),
    ):
        scraper = FeedScraper(page, mock_settings)
        candidates = await scraper.scrape_feed(max_posts=5, seen_hashes=set())

        assert len(candidates) == 0
        mock_telemetry.assert_awaited_once()
        call_kwargs = mock_telemetry.call_args.kwargs
        assert call_kwargs["trigger"] == "feed_cards_drift"


@pytest.mark.asyncio
async def test_scraper_card_layout_drift_captures_telemetry(mock_settings: Settings) -> None:
    page = MagicMock()
    page.url = "https://www.linkedin.com/feed/"

    container_loc = MagicMock()
    container_loc.count = AsyncMock(return_value=1)

    # 1 card found, but neither author nor text selectors resolve text
    card = MagicMock()
    card.get_attribute = AsyncMock(return_value="urn:li:activity:9999")
    unmatched = MagicMock()
    unmatched.count = AsyncMock(return_value=0)
    card.locator.return_value.first = unmatched

    cards_loc = MagicMock()
    cards_loc.count = AsyncMock(return_value=1)
    cards_loc.nth = MagicMock(return_value=card)

    def page_locator(selector: str) -> MagicMock:
        if "main" in selector:
            return container_loc
        return cards_loc

    page.locator = MagicMock(side_effect=page_locator)
    page.wait_for_selector = AsyncMock()

    with (
        patch(
            "agent.browser.scraper.capture_dom_telemetry", new_callable=AsyncMock
        ) as mock_telemetry,
        patch("agent.browser.scraper.humanized_scroll", new_callable=AsyncMock),
    ):
        scraper = FeedScraper(page, mock_settings)
        candidates = await scraper.scrape_feed(max_posts=5, seen_hashes=set())

        assert len(candidates) == 0
        mock_telemetry.assert_awaited_once()
        call_kwargs = mock_telemetry.call_args.kwargs
        assert call_kwargs["trigger"] == "feed_card_layout_drift"


@pytest.mark.asyncio
async def test_scraper_telemetry_failure_does_not_break_error_workflow(
    mock_settings: Settings,
) -> None:
    page = MagicMock()
    page.url = "https://www.linkedin.com/checkpoint/challenge"

    with patch(
        "agent.browser.scraper.capture_dom_telemetry",
        new_callable=AsyncMock,
        side_effect=Exception("Telemetry storage disk error"),
    ):
        scraper = FeedScraper(page, mock_settings)
        with pytest.raises(BotDetectionError):
            await scraper.scrape_feed(max_posts=5, seen_hashes=set())


# ---------------------------------------------------------------------------
# Tests for hashtag_to_feed_url helper
# ---------------------------------------------------------------------------


def test_hashtag_to_feed_url_standard_keywords() -> None:
    """Helper converts standard keywords and tags to canonical hashtag URLs."""
    assert hashtag_to_feed_url("python") == "https://www.linkedin.com/feed/hashtag/?keywords=python"
    assert hashtag_to_feed_url("ai") == "https://www.linkedin.com/feed/hashtag/?keywords=ai"
    assert (
        hashtag_to_feed_url("machinelearning")
        == "https://www.linkedin.com/feed/hashtag/?keywords=machinelearning"
    )


def test_hashtag_to_feed_url_with_hashes_casing_and_whitespace() -> None:
    """Helper handles leading '#', multiple hashes, casing, and whitespace."""
    assert (
        hashtag_to_feed_url("#Python") == "https://www.linkedin.com/feed/hashtag/?keywords=python"
    )
    assert (
        hashtag_to_feed_url("  #AI_Agents  ")
        == "https://www.linkedin.com/feed/hashtag/?keywords=ai_agents"
    )
    assert (
        hashtag_to_feed_url("###DeepLearning")
        == "https://www.linkedin.com/feed/hashtag/?keywords=deeplearning"
    )


def test_hashtag_to_feed_url_preserves_full_urls() -> None:
    """Helper returns existing HTTP/HTTPS URLs without modification."""
    url1 = "https://www.linkedin.com/feed/hashtag/?keywords=python"
    assert hashtag_to_feed_url(url1) == url1

    url2 = "https://www.linkedin.com/in/somecreator/recent-activity/all/"
    assert hashtag_to_feed_url(url2) == url2

    url3 = "http://example.com/custom/feed"
    assert hashtag_to_feed_url(url3) == url3


def test_hashtag_to_feed_url_encodes_special_characters_and_spaces() -> None:
    """Helper URL-encodes special characters and spaces."""
    assert hashtag_to_feed_url("c++") == "https://www.linkedin.com/feed/hashtag/?keywords=c%2B%2B"
    assert hashtag_to_feed_url("#c#") == "https://www.linkedin.com/feed/hashtag/?keywords=c%23"
    assert (
        hashtag_to_feed_url("data science")
        == "https://www.linkedin.com/feed/hashtag/?keywords=data+science"
    )


def test_hashtag_to_feed_url_invalid_empty_raises_value_error() -> None:
    """Helper raises ValueError on empty string or string containing only hashes."""
    with pytest.raises(ValueError, match="Invalid empty hashtag"):
        hashtag_to_feed_url("")

    with pytest.raises(ValueError, match="Invalid empty hashtag"):
        hashtag_to_feed_url("   ")

    with pytest.raises(ValueError, match="Invalid empty hashtag"):
        hashtag_to_feed_url("#")

    with pytest.raises(ValueError, match="Invalid empty hashtag"):
        hashtag_to_feed_url("###")

    with pytest.raises(ValueError, match="Invalid empty hashtag"):
        hashtag_to_feed_url("# #")

    with pytest.raises(ValueError, match="Invalid empty hashtag"):
        hashtag_to_feed_url("# # #")

    with pytest.raises(ValueError, match="Invalid empty hashtag"):
        hashtag_to_feed_url("  #   #  ")


def test_hashtag_to_feed_url_preserves_uppercase_and_mixed_case_urls() -> None:
    """Helper preserves URLs with uppercase or mixed-case HTTP/HTTPS schemes."""
    upper_https = "HTTPS://www.linkedin.com/feed/hashtag/?keywords=python"
    assert hashtag_to_feed_url(upper_https) == upper_https

    mixed_http = "Http://example.com/custom/feed"
    assert hashtag_to_feed_url(mixed_http) == mixed_http

    padded_upper = "  HTTPS://www.linkedin.com/in/creator/recent-activity/all/  "
    assert hashtag_to_feed_url(padded_upper) == padded_upper.strip()


# ---------------------------------------------------------------------------
# Tests for FeedScraper targeted URL navigation
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_scraper_navigates_to_target_url(mock_settings: Settings) -> None:
    """Scraper navigates to target URL when target_url is provided."""
    page = MagicMock()
    page.url = "https://www.linkedin.com/feed/hashtag/?keywords=python"
    page.goto = AsyncMock()

    # Mock container locator
    container_loc = MagicMock()
    container_loc.count = AsyncMock(return_value=1)

    cards_loc = MagicMock()
    cards_loc.count = AsyncMock(return_value=0)

    def page_locator(selector: str) -> MagicMock:
        if "main" in selector:
            return container_loc
        return cards_loc

    page.locator = MagicMock(side_effect=page_locator)
    page.wait_for_selector = AsyncMock()

    with (
        patch("agent.browser.scraper.capture_dom_telemetry", new_callable=AsyncMock),
        patch("agent.browser.scraper.humanized_scroll", new_callable=AsyncMock),
    ):
        scraper = FeedScraper(page, mock_settings)
        await scraper.scrape_feed(
            max_posts=5,
            seen_hashes=set(),
            target_url="https://www.linkedin.com/feed/hashtag/?keywords=python",
        )

        page.goto.assert_awaited_once_with(
            "https://www.linkedin.com/feed/hashtag/?keywords=python",
            wait_until="domcontentloaded",
            timeout=30000,
        )


@pytest.mark.asyncio
async def test_scraper_no_navigation_when_target_url_none(mock_settings: Settings) -> None:
    """Scraper does not call page.goto when target_url is None (backwards compatible)."""
    page = MagicMock()
    page.url = "https://www.linkedin.com/feed/"
    page.goto = AsyncMock()

    container_loc = MagicMock()
    container_loc.count = AsyncMock(return_value=1)

    cards_loc = MagicMock()
    cards_loc.count = AsyncMock(return_value=0)

    def page_locator(selector: str) -> MagicMock:
        if "main" in selector:
            return container_loc
        return cards_loc

    page.locator = MagicMock(side_effect=page_locator)
    page.wait_for_selector = AsyncMock()

    with (
        patch("agent.browser.scraper.capture_dom_telemetry", new_callable=AsyncMock),
        patch("agent.browser.scraper.humanized_scroll", new_callable=AsyncMock),
    ):
        scraper = FeedScraper(page, mock_settings)
        await scraper.scrape_feed(max_posts=5, seen_hashes=set(), target_url=None)

        page.goto.assert_not_called()


@pytest.mark.asyncio
async def test_scraper_navigation_warning_does_not_break_scraping(
    mock_settings: Settings,
) -> None:
    """Scraper logs warning on soft page.goto timeout but proceeds with scraping."""
    page = MagicMock()
    page.url = "https://www.linkedin.com/feed/hashtag/?keywords=python"
    page.goto = AsyncMock(side_effect=TimeoutError("Soft navigation timeout"))

    container_loc = MagicMock()
    container_loc.count = AsyncMock(return_value=1)

    cards_loc = MagicMock()
    cards_loc.count = AsyncMock(return_value=0)

    def page_locator(selector: str) -> MagicMock:
        if "main" in selector:
            return container_loc
        return cards_loc

    page.locator = MagicMock(side_effect=page_locator)
    page.wait_for_selector = AsyncMock()

    with (
        patch("agent.browser.scraper.capture_dom_telemetry", new_callable=AsyncMock),
        patch("agent.browser.scraper.humanized_scroll", new_callable=AsyncMock),
    ):
        scraper = FeedScraper(page, mock_settings)
        # Should NOT raise TimeoutError; warning logged and container checked
        candidates = await scraper.scrape_feed(
            max_posts=5,
            seen_hashes=set(),
            target_url="https://www.linkedin.com/feed/hashtag/?keywords=python",
        )
        assert candidates == []
        page.goto.assert_awaited_once()


@pytest.mark.asyncio
async def test_scraper_target_url_bot_challenge_detection(mock_settings: Settings) -> None:
    """Scraper detects bot challenge after navigating to target URL."""
    page = MagicMock()
    page.url = "https://www.linkedin.com/checkpoint/challenge"
    page.goto = AsyncMock()

    with patch(
        "agent.browser.scraper.capture_dom_telemetry", new_callable=AsyncMock
    ) as mock_telemetry:
        scraper = FeedScraper(page, mock_settings)
        with pytest.raises(BotDetectionError, match="challenge"):
            await scraper.scrape_feed(
                max_posts=5,
                seen_hashes=set(),
                target_url="https://www.linkedin.com/feed/hashtag/?keywords=python",
            )

        page.goto.assert_awaited_once()
        mock_telemetry.assert_awaited_once_with(page, trigger="feed_challenge")


@pytest.mark.asyncio
async def test_scraper_extracts_posts_from_expanded_feed_cards(mock_settings: Settings) -> None:
    """Scraper resolves posts using div[id^='expanded'][id$='MAIN_FEED_RELEVANCE'] and extracts URN from id."""
    page = MagicMock()
    page.url = "https://www.linkedin.com/feed/"

    container_loc = MagicMock()
    container_loc.count = AsyncMock(return_value=1)

    # Mock card with URN in ID attribute
    card = MagicMock()
    card.get_attribute = AsyncMock(
        side_effect=lambda attr: (
            "expanded-desktop-feed-update-urn:li:activity:7999888777-MAIN_FEED_RELEVANCE"
            if attr == "id"
            else None
        )
    )

    actor = MagicMock()
    actor.count = AsyncMock(return_value=1)
    actor.inner_text = AsyncMock(return_value="Bob Developer • 1st\nPrincipal Architect")

    text = MagicMock()
    text.count = AsyncMock(return_value=1)
    text.inner_text = AsyncMock(
        return_value="Here is a detailed post about building reliable distributed systems with Python and LangGraph. …see more"
    )

    def card_locator(selector: str) -> MagicMock:
        loc = MagicMock()
        if "actor" in selector:
            loc.first = actor
        elif "text" in selector:
            loc.first = text
        else:
            unmatched = MagicMock()
            unmatched.count = AsyncMock(return_value=0)
            loc.first = unmatched
        return loc

    card.locator = MagicMock(side_effect=card_locator)

    cards_loc = MagicMock()
    cards_loc.count = AsyncMock(return_value=1)
    cards_loc.nth = MagicMock(return_value=card)

    def page_locator(selector: str) -> MagicMock:
        if "main" in selector:
            return container_loc
        if "div[id^='expanded'][id$='MAIN_FEED_RELEVANCE']" in selector:
            return cards_loc
        empty = MagicMock()
        empty.count = AsyncMock(return_value=0)
        return empty

    page.locator = MagicMock(side_effect=page_locator)
    page.wait_for_selector = AsyncMock()

    with (
        patch("agent.browser.scraper.capture_dom_telemetry", new_callable=AsyncMock),
        patch("agent.browser.scraper.humanized_scroll", new_callable=AsyncMock),
    ):
        scraper = FeedScraper(page, mock_settings)
        posts = await scraper.scrape_feed(max_posts=5, seen_hashes=set())

        assert len(posts) == 1
        assert posts[0].post_urn == "urn:li:activity:7999888777"
        assert posts[0].author_name == "Bob Developer"
        assert "distributed systems with Python" in posts[0].post_text
        assert not posts[0].post_text.endswith("…see more")


@pytest.mark.asyncio
async def test_scraper_filters_sidebar_navigation_and_short_texts(mock_settings: Settings) -> None:
    """Scraper skips short texts (< 30 chars) and known navigation artifacts."""
    page = MagicMock()
    page.url = "https://www.linkedin.com/feed/"

    container_loc = MagicMock()
    container_loc.count = AsyncMock(return_value=1)

    # Card 1: Sidebar item "Saved items" (11 chars)
    card1 = MagicMock()
    card1.get_attribute = AsyncMock(return_value=None)
    actor1 = MagicMock()
    actor1.count = AsyncMock(return_value=0)
    text1 = MagicMock()
    text1.count = AsyncMock(return_value=1)
    text1.inner_text = AsyncMock(return_value="Saved items")

    def card1_locator(s: str) -> MagicMock:
        loc = MagicMock()
        if "text" in s:
            loc.first = text1
        else:
            unmatched = MagicMock()
            unmatched.count = AsyncMock(return_value=0)
            loc.first = unmatched
        return loc

    card1.locator = MagicMock(side_effect=card1_locator)

    # Card 2: Valid post (> 30 chars)
    card2 = MagicMock()
    card2.get_attribute = AsyncMock(
        side_effect=lambda attr: "urn:li:activity:888111222" if attr == "data-urn" else None
    )
    actor2 = MagicMock()
    actor2.count = AsyncMock(return_value=1)
    actor2.inner_text = AsyncMock(return_value="Charlie Engineer")
    text2 = MagicMock()
    text2.count = AsyncMock(return_value=1)
    text2.inner_text = AsyncMock(
        return_value="Comprehensive guide to microservices orchestration and resilience patterns."
    )

    def card2_locator(s: str) -> MagicMock:
        loc = MagicMock()
        if "actor" in s:
            loc.first = actor2
        elif "text" in s:
            loc.first = text2
        else:
            unmatched = MagicMock()
            unmatched.count = AsyncMock(return_value=0)
            loc.first = unmatched
        return loc

    card2.locator = MagicMock(side_effect=card2_locator)

    cards_loc = MagicMock()
    cards_loc.count = AsyncMock(return_value=2)
    cards_loc.nth = MagicMock(side_effect=lambda idx: card1 if idx == 0 else card2)

    def page_locator(selector: str) -> MagicMock:
        if "main" in selector:
            return container_loc
        return cards_loc

    page.locator = MagicMock(side_effect=page_locator)
    page.wait_for_selector = AsyncMock()

    with (
        patch("agent.browser.scraper.capture_dom_telemetry", new_callable=AsyncMock),
        patch("agent.browser.scraper.humanized_scroll", new_callable=AsyncMock),
    ):
        scraper = FeedScraper(page, mock_settings)
        posts = await scraper.scrape_feed(max_posts=5, seen_hashes=set())

        # Only card 2 should be accepted, card 1 must be filtered out
        assert len(posts) == 1
        assert posts[0].post_urn == "urn:li:activity:888111222"
        assert posts[0].author_name == "Charlie Engineer"


@pytest.mark.asyncio
async def test_scraper_session_expired_when_redirect_wait_fails(
    mock_settings: Settings,
) -> None:
    page = MagicMock()
    page.url = "https://www.linkedin.com/login"

    with patch(
        "agent.browser.scraper.wait_for_login_redirect", new_callable=AsyncMock
    ) as mock_wait:
        mock_wait.return_value = False
        scraper = FeedScraper(page, mock_settings)

        with pytest.raises(SessionExpiredError, match="session expired or unauthenticated"):
            await scraper.scrape_feed(max_posts=5, seen_hashes=set())

        mock_wait.assert_awaited_once_with(page, timeout=15.0)


@pytest.mark.asyncio
async def test_scraper_survives_when_login_redirect_succeeds(
    mock_settings: Settings,
) -> None:
    page = MagicMock()
    # Initially on login handshake URL
    page.url = (
        "https://www.linkedin.com/login/?session_redirect=https%3A%2F%2Fwww.linkedin.com%2Ffeed%2F"
    )

    container_loc = MagicMock()
    container_loc.count = AsyncMock(return_value=1)

    cards_loc = MagicMock()
    cards_loc.count = AsyncMock(return_value=0)

    def page_locator(selector: str) -> MagicMock:
        if "main" in selector:
            return container_loc
        return cards_loc

    page.locator = MagicMock(side_effect=page_locator)
    page.wait_for_selector = AsyncMock()

    with (
        patch("agent.browser.scraper.wait_for_login_redirect", new_callable=AsyncMock) as mock_wait,
        patch("agent.browser.scraper.capture_dom_telemetry", new_callable=AsyncMock),
        patch("agent.browser.scraper.humanized_scroll", new_callable=AsyncMock),
    ):
        mock_wait.return_value = True
        scraper = FeedScraper(page, mock_settings)
        posts = await scraper.scrape_feed(max_posts=5, seen_hashes=set())

        assert len(posts) == 0  # No cards found, but did not raise SessionExpiredError
        mock_wait.assert_awaited_once_with(page, timeout=15.0)


@pytest.mark.asyncio
async def test_scraper_respects_custom_screens_scroll_parameter(
    mock_settings: Settings,
) -> None:
    page = MagicMock()
    page.url = "https://www.linkedin.com/feed/"

    container_loc = MagicMock()
    container_loc.count = AsyncMock(return_value=1)

    cards_loc = MagicMock()
    cards_loc.count = AsyncMock(return_value=0)

    def page_locator(selector: str) -> MagicMock:
        if "main" in selector:
            return container_loc
        return cards_loc

    page.locator = MagicMock(side_effect=page_locator)
    page.wait_for_selector = AsyncMock()

    with (
        patch("agent.browser.scraper.wait_for_login_redirect", new_callable=AsyncMock) as mock_wait,
        patch("agent.browser.scraper.capture_dom_telemetry", new_callable=AsyncMock),
        patch("agent.browser.scraper.humanized_scroll", new_callable=AsyncMock) as mock_scroll,
    ):
        mock_wait.return_value = True
        scraper = FeedScraper(page, mock_settings)
        await scraper.scrape_feed(max_posts=5, seen_hashes=set(), screens=4)

        mock_scroll.assert_awaited_once_with(page, screens=4)


@pytest.mark.asyncio
async def test_parse_feed_card_clicks_see_more_to_expand_post() -> None:
    now = datetime.now(UTC)
    card = MagicMock()
    card.get_attribute = AsyncMock(return_value="urn:li:activity:999000")

    # Comment button present
    comment_btn = MagicMock()
    comment_btn.count = AsyncMock(return_value=1)

    # Actor name present
    actor_el = MagicMock()
    actor_el.count = AsyncMock(return_value=1)
    actor_el.inner_text = AsyncMock(return_value="Jane Developer")

    # See more button present and visible
    see_more_btn = MagicMock()
    see_more_btn.count = AsyncMock(return_value=1)
    see_more_btn.is_visible = AsyncMock(return_value=True)
    see_more_btn.click = AsyncMock()

    # Expandable text box with full text
    expanded_text = (
        "This is a full-length expanded post that was revealed after clicking see more on LinkedIn. "
        "It includes in-depth discussion of systems programming and concurrency primitives."
    )
    text_box = MagicMock()
    text_box.count = AsyncMock(return_value=1)
    text_box.inner_text = AsyncMock(return_value=expanded_text)

    def card_locator(selector: str) -> MagicMock:
        loc = MagicMock()
        if "Comment" in selector:
            loc.first = comment_btn
        elif "actor" in selector:
            loc.first = actor_el
        elif "see-more" in selector or "see more" in selector:
            loc.first = see_more_btn
        elif "expandable-text-box" in selector or "update-components-text" in selector:
            loc.first = text_box
        else:
            unmatched = MagicMock()
            unmatched.count = AsyncMock(return_value=0)
            loc.first = unmatched
        return loc

    card.locator = MagicMock(side_effect=card_locator)

    record, reason = await parse_feed_card(card, index=0, now=now, seen_hashes=set())

    # Verify that see_more was clicked to expand post text
    see_more_btn.click.assert_awaited_once_with(timeout=1000)
    assert record is not None
    assert record.post_text == expanded_text
    assert record.author_name == "Jane Developer"


def test_extract_valid_urn() -> None:
    """Test extract_valid_urn handles digits, permalinks, mocks, and rejects layout hashes."""
    assert (
        extract_valid_urn("urn:li:activity:7123456789012345678")
        == "urn:li:activity:7123456789012345678"
    )
    assert extract_valid_urn("urn:li:ugcPost:123456789") == "urn:li:ugcPost:123456789"
    assert extract_valid_urn("urn:li:share:987654321") == "urn:li:share:987654321"
    assert (
        extract_valid_urn("https://www.linkedin.com/feed/update/urn:li:activity:7123456789012345678/")
        == "urn:li:activity:7123456789012345678"
    )
    assert (
        extract_valid_urn(
            "https://www.linkedin.com/posts/alice_headline-activity-7123456789012345678-abcd?utm_source=share"
        )
        == "urn:li:activity:7123456789012345678"
    )
    assert (
        extract_valid_urn(
            "expanded-desktop-feed-update-urn:li:activity:7999888777-MAIN_FEED_RELEVANCE"
        )
        == "urn:li:activity:7999888777"
    )
    # Reject opaque DOM layout container hash
    assert (
        extract_valid_urn("expandedwia6F-QsrTbyoUOQxmOTW4pERTjZUyQ2k50KXuJhs2EMAIN_FEED_RELEVANCE")
        is None
    )
    assert extract_valid_urn("wia6F-QsrTbyoUOQxmOTW4pERTjZUyQ2k50KXuJhs2E") is None
    assert extract_valid_urn("urn:li:activity:wia6F-QsrTbyoUOQxmOTW4pERTjZUyQ2k50KXuJhs2E") is None
    assert extract_valid_urn("urn:li:activity:scraped_0_123456") is None
    assert extract_valid_urn("") is None
    assert extract_valid_urn(None) is None


@pytest.mark.asyncio
async def test_scraper_resolves_real_urn_when_expanded_container_has_opaque_hash() -> None:
    """When outer card has an opaque expanded hash like wia6F-Qsr..., resolve real URN from inner elements."""
    now = datetime.now(UTC)

    card = MagicMock()
    # Outer card has opaque layout hash ID reported by user
    card.get_attribute = AsyncMock(
        side_effect=lambda attr: (
            "expandedwia6F-QsrTbyoUOQxmOTW4pERTjZUyQ2k50KXuJhs2EMAIN_FEED_RELEVANCE"
            if attr == "id"
            else None
        )
    )

    comment_btn = MagicMock(count=AsyncMock(return_value=1))
    actor_el = MagicMock(
        count=AsyncMock(return_value=1),
        inner_text=AsyncMock(return_value="Alice Engineer • 1st\nAI Architect"),
    )
    actor_link = MagicMock(
        count=AsyncMock(return_value=1),
        inner_text=AsyncMock(return_value="Alice Engineer • 1st"),
        get_attribute=AsyncMock(return_value="https://www.linkedin.com/in/alice-engineer"),
    )
    actor_links = MagicMock(
        count=AsyncMock(return_value=1),
        nth=MagicMock(return_value=actor_link),
    )
    text_box = MagicMock(
        count=AsyncMock(return_value=1),
        inner_text=AsyncMock(
            return_value="Building high performance agents with LangGraph and Python 3.14 async runtime."
        ),
    )

    # Inner element containing real LinkedIn activity URN
    inner_urn_el = MagicMock()
    inner_urn_el.get_attribute = AsyncMock(
        side_effect=lambda attr: (
            "urn:li:activity:7123456789012345678" if attr == "data-urn" else None
        )
    )
    inner_urn_els = MagicMock(
        count=AsyncMock(return_value=1),
        nth=MagicMock(return_value=inner_urn_el),
    )

    def card_locator(selector: str) -> MagicMock:
        loc = MagicMock()
        if "Comment" in selector:
            loc.first = comment_btn
        elif "a[href*='/in/']" in selector:
            return actor_links
        elif "actor" in selector:
            loc.first = actor_el
        elif "expandable-text-box" in selector or "update-components-text" in selector:
            loc.first = text_box
        elif "data-urn" in selector:
            return inner_urn_els
        else:
            unmatched = MagicMock(count=AsyncMock(return_value=0))
            loc.first = unmatched
            return loc
        return loc

    card.locator = MagicMock(side_effect=card_locator)

    record, reason = await parse_feed_card(card, index=0, now=now, seen_hashes=set())

    assert record is not None
    # Must NOT have fabricated the fake wia6F... link
    assert "wia6F" not in record.post_urn
    assert "wia6F" not in record.post_url
    # Must have resolved the real numeric activity URN and canonical post URL
    assert record.post_urn == "urn:li:activity:7123456789012345678"
    assert (
        record.post_url
        == "https://www.linkedin.com/feed/update/urn:li:activity:7123456789012345678/"
    )


@pytest.mark.asyncio
async def test_scraper_resolves_urn_from_posts_permalink() -> None:
    """When outer card has opaque hash and no data-urn, resolve URN from /posts/ permalink anchor."""
    now = datetime.now(UTC)

    card = MagicMock()
    card.get_attribute = AsyncMock(
        side_effect=lambda attr: (
            "expandedwia6F-QsrTbyoUOQxmOTW4pERTjZUyQ2k50KXuJhs2EMAIN_FEED_RELEVANCE"
            if attr == "id"
            else None
        )
    )

    comment_btn = MagicMock(count=AsyncMock(return_value=1))
    actor_el = MagicMock(
        count=AsyncMock(return_value=1),
        inner_text=AsyncMock(return_value="Bob Developer • 1st"),
    )
    actor_link = MagicMock(
        count=AsyncMock(return_value=1),
        inner_text=AsyncMock(return_value="Bob Developer • 1st"),
        get_attribute=AsyncMock(return_value="https://www.linkedin.com/in/bob-dev"),
    )
    actor_links = MagicMock(
        count=AsyncMock(return_value=1),
        nth=MagicMock(return_value=actor_link),
    )
    text_box = MagicMock(
        count=AsyncMock(return_value=1),
        inner_text=AsyncMock(
            return_value="Exploring the frontier of autonomous coding systems with Playwright."
        ),
    )

    # Empty inner URN elements
    empty_urn_els = MagicMock(count=AsyncMock(return_value=0))

    # Inner link containing /posts/ permalink with activity ID
    permalink_el = MagicMock()
    permalink_el.get_attribute = AsyncMock(
        return_value="https://www.linkedin.com/posts/bob-dev_coding-systems-activity-7987654321098765432-xyz?utm_source=share"
    )
    inner_links = MagicMock(
        count=AsyncMock(return_value=1),
        nth=MagicMock(return_value=permalink_el),
    )

    def card_locator(selector: str) -> MagicMock:
        loc = MagicMock()
        if "Comment" in selector:
            loc.first = comment_btn
        elif "a[href*='/in/']" in selector:
            return actor_links
        elif "actor" in selector:
            loc.first = actor_el
        elif "expandable-text-box" in selector or "update-components-text" in selector:
            loc.first = text_box
        elif "data-urn" in selector:
            return empty_urn_els
        elif "a[href*='/feed/update/']" in selector or "a[href*='/posts/']" in selector:
            return inner_links
        else:
            unmatched = MagicMock(count=AsyncMock(return_value=0))
            loc.first = unmatched
            return loc
        return loc

    card.locator = MagicMock(side_effect=card_locator)

    record, reason = await parse_feed_card(card, index=0, now=now, seen_hashes=set())

    assert record is not None
    assert record.post_urn == "urn:li:activity:7987654321098765432"
    assert (
        record.post_url
        == "https://www.linkedin.com/feed/update/urn:li:activity:7987654321098765432/"
    )



