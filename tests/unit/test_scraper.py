"""Unit tests for FeedScraper extracting candidate posts."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from pydantic import SecretStr

from agent.browser.scraper import FeedScraper
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
