"""Unit tests for FeedScraper extracting candidate posts."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from pydantic import SecretStr

from agent.browser.scraper import FeedScraper, hashtag_to_feed_url
from agent.config import Settings
from agent.errors import BotDetectionError, SelectorDriftError


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
