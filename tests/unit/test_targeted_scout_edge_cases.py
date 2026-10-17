"""Comprehensive stress-test suite for targeted scouting edge cases.

Tests:
1. `hashtag_to_feed_url` boundary inputs (unicode, punctuation, empty strings, spaces, multiple hashes, full URLs).
2. `Settings` parsing (corrupted strings, nested quotes, whitespace variations, mixed types, env vars).
3. `FeedScraper.scrape_feed` with target URLs (parameter propagation, soft warnings, challenge/authwall detection, selector drift).
4. Cross-component integration & boundary interactions (e.g. `get_scout_target_sources`).
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from agent.browser.scraper import FeedScraper
from agent.browser.url_utils import hashtag_to_feed_url
from agent.config import Settings, load_settings
from agent.errors import ScrapeError, SelectorDriftError, SessionExpiredError
from agent.graphs.scout_graph import get_scout_target_sources

# ---------------------------------------------------------------------------
# Suite 1: Stress-testing hashtag_to_feed_url with boundary inputs
# ---------------------------------------------------------------------------


class TestHashtagToFeedUrlBoundaryInputs:
    """Adversarial stress-testing of hashtag_to_feed_url."""

    @pytest.mark.parametrize(
        ("tag", "expected_encoded"),
        [
            ("人工智能", "%E4%BA%BA%E5%B7%A5%E6%99%BA%E8%83%BD"),  # Chinese: AI
            (
                "инновации",
                "%D0%B8%D0%BD%D0%BD%D0%BE%D0%B2%D0%B0%D1%86%D0%B8%D0%B8",
            ),  # Russian: Innovation
            (
                "ذكاء_اصطناعي",
                "%D8%B0%D9%83%D8%A7%D8%A1_%D8%A7%D8%B5%D8%B7%D9%86%D8%A7%D8%B9%D9%8A",
            ),  # Arabic RTL
            ("développement", "d%C3%A9veloppement"),  # French accent
            ("café", "caf%C3%A9"),  # Acute accent
            ("🤖🚀", "%F0%9F%A4%96%F0%9F%9A%80"),  # Emojis
            ("🐍", "%F0%9F%90%8D"),  # Python emoji
        ],
    )
    def test_unicode_and_non_ascii_hashtags(self, tag: str, expected_encoded: str) -> None:
        """Unicode characters, accents, RTL scripts, and emojis are correctly URL-encoded."""
        url = hashtag_to_feed_url(f"#{tag}")
        assert url == f"https://www.linkedin.com/feed/hashtag/?keywords={expected_encoded}"

    @pytest.mark.parametrize(
        ("tag", "expected_encoded"),
        [
            ("c++", "c%2B%2B"),
            ("#c#", "c%23"),
            ("###c#", "c%23"),
            (".net", ".net"),
            ("node.js", "node.js"),
            ("ai/ml", "ai%2Fml"),
            ("ai&ml", "ai%26ml"),
            ("ai?tech=1", "ai%3Ftech%3D1"),
            ("../../../evil", "..%2F..%2F..%2Fevil"),
            ("tag!", "tag%21"),
            ("tag@home", "tag%40home"),
        ],
    )
    def test_punctuation_and_special_characters(self, tag: str, expected_encoded: str) -> None:
        """Punctuation, symbols, path traversal strings, and programming language names encode safely."""
        url = hashtag_to_feed_url(tag)
        assert url == f"https://www.linkedin.com/feed/hashtag/?keywords={expected_encoded}"

    @pytest.mark.parametrize(
        "empty_input",
        [
            "",
            "   ",
            "\t\n\r",
            "#",
            "##",
            "###",
            "#######",
        ],
    )
    def test_empty_and_hash_only_inputs_raise_value_error(self, empty_input: str) -> None:
        """Empty strings, whitespace-only, or strings containing only '#' must raise ValueError."""
        with pytest.raises(ValueError, match="Invalid empty hashtag"):
            hashtag_to_feed_url(empty_input)

    def test_multiple_hashes_with_internal_spaces_raises_value_error(self) -> None:
        """Strings containing only hashes separated by spaces must raise ValueError."""
        with pytest.raises(ValueError, match="Invalid empty hashtag"):
            hashtag_to_feed_url("# #")

        with pytest.raises(ValueError, match="Invalid empty hashtag"):
            hashtag_to_feed_url("# # #")

    @pytest.mark.parametrize(
        ("raw_input", "expected_encoded"),
        [
            ("###Python", "python"),
            ("  #  python  ", "python"),
            ("#python#sharp", "python%23sharp"),
            ("\n\t#MachineLearning\r\n", "machinelearning"),
            ("  #data  science  ", "data++science"),
        ],
    )
    def test_multiple_hashes_and_mixed_whitespace(
        self, raw_input: str, expected_encoded: str
    ) -> None:
        """Multiple leading hashes and mixed whitespace are trimmed and lowercased."""
        url = hashtag_to_feed_url(raw_input)
        assert url == f"https://www.linkedin.com/feed/hashtag/?keywords={expected_encoded}"

    def test_full_urls_preservation_and_casing(self) -> None:
        """Full HTTP/HTTPS URLs are preserved as-is when properly formatted."""
        http_url = "http://linkedin.com/feed/hashtag/?keywords=python"
        https_url = "https://www.linkedin.com/feed/hashtag/?keywords=ai"
        creator_url = "https://www.linkedin.com/in/somecreator/recent-activity/all/"

        assert hashtag_to_feed_url(http_url) == http_url
        assert hashtag_to_feed_url(https_url) == https_url
        assert hashtag_to_feed_url(creator_url) == creator_url

        # Whitespace padded URL
        assert hashtag_to_feed_url(f"  {https_url}  ") == https_url

    def test_uppercase_url_scheme_preserved(self) -> None:
        """Uppercase URL schemes (e.g. HTTPS://) are recognized as URLs and preserved."""
        raw_upper = "HTTPS://www.linkedin.com/feed/hashtag/?keywords=python"
        assert hashtag_to_feed_url(raw_upper) == raw_upper


# ---------------------------------------------------------------------------
# Suite 2: Stress-testing Settings Parsing
# ---------------------------------------------------------------------------


class TestSettingsParsingStress:
    """Adversarial stress-testing of Settings list parsing and normalization."""

    def test_settings_corrupted_json_fallback_to_csv(self) -> None:
        """Malformed JSON strings fall back to comma-separated splitting gracefully."""
        # Starts with [ and ends with ] but contains invalid JSON syntax
        settings = Settings(
            nvidia_nim_api_key="nvapi-test-key",
            telegram_bot_token="123:ABC",
            telegram_authorized_chat_id=123,
            scout_target_urls='["https://a.com", broken_entry]',  # type: ignore[arg-type]
        )
        # Fell back to comma split: '["https://a.com"' and 'broken_entry]'
        assert len(settings.scout_target_urls) == 2
        assert '["https://a.com"' in settings.scout_target_urls
        assert "broken_entry]" in settings.scout_target_urls

    def test_settings_unclosed_json_bracket(self) -> None:
        """JSON missing closing bracket splits by comma."""
        settings = Settings(
            nvidia_nim_api_key="nvapi-test-key",
            telegram_bot_token="123:ABC",
            telegram_authorized_chat_id=123,
            scout_target_urls='["https://a.com", "https://b.com"',  # type: ignore[arg-type]
        )
        assert len(settings.scout_target_urls) == 2
        assert '["https://a.com"' in settings.scout_target_urls

    def test_settings_json_with_mixed_primitive_types(self) -> None:
        """Valid JSON list containing numbers, booleans, and nulls converts all to strings."""
        settings = Settings(
            nvidia_nim_api_key="nvapi-test-key",
            telegram_bot_token="123:ABC",
            telegram_authorized_chat_id=123,
            scout_target_urls='["https://a.com", 123, true, null]',  # type: ignore[arg-type]
        )
        assert settings.scout_target_urls == ["https://a.com", "123", "True"]

    def test_settings_json_with_nested_objects(self) -> None:
        """JSON list containing nested dictionaries converts dict representation to string."""
        settings = Settings(
            nvidia_nim_api_key="nvapi-test-key",
            telegram_bot_token="123:ABC",
            telegram_authorized_chat_id=123,
            scout_target_urls='[{"url": "https://a.com"}]',  # type: ignore[arg-type]
        )
        assert len(settings.scout_target_urls) == 1
        assert "{'url': 'https://a.com'}" in settings.scout_target_urls[0]

    def test_settings_nested_quotes_and_single_quote_json(self) -> None:
        """Python-style single quoted lists fall back to CSV split since standard JSON requires double quotes."""
        settings = Settings(
            nvidia_nim_api_key="nvapi-test-key",
            telegram_bot_token="123:ABC",
            telegram_authorized_chat_id=123,
            scout_target_urls="['https://a.com', 'https://b.com']",  # type: ignore[arg-type]
        )
        assert len(settings.scout_target_urls) == 2
        assert "['https://a.com'" in settings.scout_target_urls
        assert "'https://b.com']" in settings.scout_target_urls

    def test_settings_whitespace_variations_and_empty_entries(self) -> None:
        """Tabs, newlines, consecutive commas, and empty items are cleaned."""
        raw_csv = "\n\n  https://a.com  \n,\t,\t\thttps://b.com\r\n,\n   ,\nhttps://c.com\n"
        settings = Settings(
            nvidia_nim_api_key="nvapi-test-key",
            telegram_bot_token="123:ABC",
            telegram_authorized_chat_id=123,
            scout_target_urls=raw_csv,  # type: ignore[arg-type]
        )
        assert settings.scout_target_urls == [
            "https://a.com",
            "https://b.com",
            "https://c.com",
        ]

    def test_settings_only_commas_and_whitespace(self) -> None:
        """Input containing only commas and spaces produces empty list."""
        for empty_val in [",,,,", "  ,  ,  ,  ", "\t,\n,\r,"]:
            settings = Settings(
                nvidia_nim_api_key="nvapi-test-key",
                telegram_bot_token="123:ABC",
                telegram_authorized_chat_id=123,
                scout_target_urls=empty_val,  # type: ignore[arg-type]
            )
            assert settings.scout_target_urls == []

    def test_settings_mixed_python_types_in_list(self) -> None:
        """Direct list containing non-string Python objects (int, bool, None) parses safely."""
        settings = Settings(
            nvidia_nim_api_key="nvapi-test-key",
            telegram_bot_token="123:ABC",
            telegram_authorized_chat_id=123,
            scout_target_urls=[None, True, False, 12345, "https://valid.com"],  # type: ignore[list-item]
        )
        assert settings.scout_target_urls == ["True", "False", "12345", "https://valid.com"]

    def test_settings_non_iterable_primitives(self) -> None:
        """Passing integer or dict to list fields returns empty list via parse_string_list."""
        settings_int = Settings(
            nvidia_nim_api_key="nvapi-test-key",
            telegram_bot_token="123:ABC",
            telegram_authorized_chat_id=123,
            scout_target_urls=9999,  # type: ignore[arg-type]
        )
        assert settings_int.scout_target_urls == []

        settings_dict = Settings(
            nvidia_nim_api_key="nvapi-test-key",
            telegram_bot_token="123:ABC",
            telegram_authorized_chat_id=123,
            scout_target_urls={"invalid": "dict"},  # type: ignore[arg-type]
        )
        assert settings_dict.scout_target_urls == []

    def test_target_hashtags_hash_normalization_dedup(self) -> None:
        """Hashtags normalize by stripping whitespace and '#', filtering empty, and deduplicating."""
        settings = Settings(
            nvidia_nim_api_key="nvapi-test-key",
            telegram_bot_token="123:ABC",
            telegram_authorized_chat_id=123,
            target_hashtags=["#Python", "###python", "  AI  ", "#AI", "cloud", "###"],
        )
        # Note: 'python' and 'AI' preserved once, '###' stripped to empty and omitted
        assert settings.target_hashtags == ["Python", "python", "AI", "cloud"]

    def test_env_loading_with_whitespace_and_commas(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """load_settings correctly extracts and parses env vars with irregular spacing."""
        monkeypatch.setenv("NVIDIA_NIM_API_KEY", "nvapi-env-key")
        monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "999:TOKEN")
        monkeypatch.setenv("TELEGRAM_AUTHORIZED_CHAT_ID", "555123")
        monkeypatch.setenv("SCOUT_TARGET_URLS", "  https://a.com/1  ,\n  https://a.com/2  ,\n\n")
        monkeypatch.setenv("TARGET_HASHTAGS", "  #deeplearning  ,   #nlp  ,  nlp  ")

        settings = load_settings()
        assert settings.scout_target_urls == ["https://a.com/1", "https://a.com/2"]
        assert settings.target_hashtags == ["deeplearning", "nlp"]


# ---------------------------------------------------------------------------
# Suite 3: Stress-testing FeedScraper.scrape_feed with Target URLs
# ---------------------------------------------------------------------------


class TestFeedScraperTargetUrlStress:
    """Adversarial stress-testing of FeedScraper target URL navigation and error states."""

    @pytest.fixture
    def mock_settings(self) -> Settings:
        return Settings(
            nvidia_nim_api_key="nvapi-test-key",
            telegram_bot_token="123:ABC",
            telegram_authorized_chat_id=123,
        )

    @pytest.mark.asyncio
    async def test_target_url_whitespace_only_skips_navigation(
        self, mock_settings: Settings
    ) -> None:
        """When target_url contains only whitespace, navigation is skipped (treated as None)."""
        page = MagicMock()
        page.url = "https://www.linkedin.com/feed/"
        page.goto = AsyncMock()

        container_loc = MagicMock()
        container_loc.count = AsyncMock(return_value=1)
        cards_loc = MagicMock()
        cards_loc.count = AsyncMock(return_value=0)

        def page_locator(selector: str) -> MagicMock:
            return container_loc if "main" in selector else cards_loc

        page.locator = MagicMock(side_effect=page_locator)
        page.wait_for_selector = AsyncMock()

        with (
            patch("agent.browser.scraper.capture_dom_telemetry", new_callable=AsyncMock),
            patch("agent.browser.scraper.humanized_scroll", new_callable=AsyncMock),
        ):
            scraper = FeedScraper(page, mock_settings)
            await scraper.scrape_feed(max_posts=5, seen_hashes=set(), target_url="    ")
            page.goto.assert_not_called()

    @pytest.mark.asyncio
    async def test_target_url_trims_whitespace_before_navigation(
        self, mock_settings: Settings
    ) -> None:
        """Target URL with surrounding whitespace is stripped before calling page.goto."""
        page = MagicMock()
        page.url = "https://www.linkedin.com/feed/hashtag/?keywords=python"
        page.goto = AsyncMock()

        container_loc = MagicMock()
        container_loc.count = AsyncMock(return_value=1)
        cards_loc = MagicMock()
        cards_loc.count = AsyncMock(return_value=0)

        def page_locator(selector: str) -> MagicMock:
            return container_loc if "main" in selector else cards_loc

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
                target_url="   https://www.linkedin.com/feed/hashtag/?keywords=python   \n",
            )
            page.goto.assert_awaited_once_with(
                "https://www.linkedin.com/feed/hashtag/?keywords=python",
                wait_until="domcontentloaded",
                timeout=30000,
            )

    @pytest.mark.asyncio
    async def test_target_url_navigation_raises_selector_drift_when_container_missing(
        self, mock_settings: Settings
    ) -> None:
        """When target page has 0 feed containers, SelectorDriftError is raised with telemetry."""
        page = MagicMock()
        page.url = "https://www.linkedin.com/feed/hashtag/?keywords=nonexistent"
        page.goto = AsyncMock()

        container_loc = MagicMock()
        container_loc.count = AsyncMock(return_value=0)  # Container not found

        page.locator = MagicMock(return_value=container_loc)

        with (
            patch(
                "agent.browser.scraper.capture_dom_telemetry", new_callable=AsyncMock
            ) as mock_telemetry,
            patch.object(
                FeedScraper,
                "_capture_screenshot",
                new_callable=AsyncMock,
                return_value="debug/drift.png",
            ),
        ):
            scraper = FeedScraper(page, mock_settings)
            with pytest.raises(SelectorDriftError, match="Feed root container not found"):
                await scraper.scrape_feed(
                    max_posts=5,
                    seen_hashes=set(),
                    target_url="https://www.linkedin.com/feed/hashtag/?keywords=nonexistent",
                )

            page.goto.assert_awaited_once()
            mock_telemetry.assert_awaited_once_with(
                page,
                trigger="feed_container_drift",
                target_selector="main, div.scaffold-finite-scroll, div.feed-shared-update-v2, div.scaffold-layout__main",
            )

    @pytest.mark.asyncio
    async def test_target_url_redirected_to_authwall_raises_session_expired(
        self, mock_settings: Settings
    ) -> None:
        """When target URL redirects to login/authwall, SessionExpiredError is raised."""
        page = MagicMock()
        page.url = "https://www.linkedin.com/authwall?trk=rip"
        page.goto = AsyncMock()

        with patch.object(
            FeedScraper,
            "_capture_screenshot",
            new_callable=AsyncMock,
            return_value="debug/auth.png",
        ):
            scraper = FeedScraper(page, mock_settings)
            with pytest.raises(SessionExpiredError, match="session expired or unauthenticated"):
                await scraper.scrape_feed(
                    max_posts=5,
                    seen_hashes=set(),
                    target_url="https://www.linkedin.com/feed/hashtag/?keywords=python",
                )
            page.goto.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_target_url_container_count_exception_raises_scrape_error(
        self, mock_settings: Settings
    ) -> None:
        """When page DOM throws an unexpected exception during container query, ScrapeError is raised."""
        page = MagicMock()
        page.url = "https://www.linkedin.com/feed/hashtag/?keywords=python"
        page.goto = AsyncMock()

        container_loc = MagicMock()
        container_loc.count = AsyncMock(side_effect=RuntimeError("DOM execution context destroyed"))

        page.locator = MagicMock(return_value=container_loc)

        scraper = FeedScraper(page, mock_settings)
        with pytest.raises(ScrapeError, match="Failed to locate feed container"):
            await scraper.scrape_feed(
                max_posts=5,
                seen_hashes=set(),
                target_url="https://www.linkedin.com/feed/hashtag/?keywords=python",
            )


# ---------------------------------------------------------------------------
# Suite 4: End-to-End Integration & Boundary Discovery Tests
# ---------------------------------------------------------------------------


class TestTargetSourcesIntegrationAndVulnerabilities:
    """Stress-test integration between Settings, get_scout_target_sources, and ScoutGraph."""

    def test_deduplication_between_urls_and_hashtags(self) -> None:
        """If scout_target_urls already includes a hashtag URL, target_hashtags will not duplicate it."""
        hashtag_url = "https://www.linkedin.com/feed/hashtag/?keywords=python"
        settings = Settings(
            nvidia_nim_api_key="nvapi-test-key",
            telegram_bot_token="123:ABC",
            telegram_authorized_chat_id=123,
            scout_target_urls=[hashtag_url],
            target_hashtags=["python", "#python"],
        )
        sources = get_scout_target_sources(settings)
        assert sources == [hashtag_url]

    def test_hashtag_with_space_separated_hashes_safe_in_get_scout_target_sources(self) -> None:
        """Verify remediation: '# #' is stripped during Settings validation,
        and get_scout_target_sources falls back safely without unhandled ValueError.
        """
        settings = Settings(
            nvidia_nim_api_key="nvapi-test-key",
            telegram_bot_token="123:ABC",
            telegram_authorized_chat_id=123,
            target_hashtags=["# #"],
        )
        assert settings.target_hashtags == []
        sources = get_scout_target_sources(settings)
        assert sources == [None]

        # Defensively verify that even if invalid hashtag somehow bypassed Settings,
        # get_scout_target_sources catches ValueError and falls back safely
        mock_settings = MagicMock()
        mock_settings.scout_target_urls = []
        mock_settings.target_hashtags = ["# #"]
        assert get_scout_target_sources(mock_settings) == [None]

    @pytest.mark.asyncio
    async def test_scout_graph_calculates_max_total_posts_with_candidate_multiplier(self) -> None:
        from typing import cast

        from langchain_core.runnables import RunnableConfig

        from agent.graphs.scout_graph import scrape_feed
        from agent.graphs.state import GraphContext, ScoutState

        mock_scraper = MagicMock()
        mock_scraper.scrape_feed = AsyncMock(return_value=[])

        settings = Settings(
            nvidia_nim_api_key="nvapi-test-key",
            telegram_bot_token="123:ABC",
            telegram_authorized_chat_id=123,
            max_suggestions_per_run=3,
            candidate_pool_multiplier=4,
            scout_scroll_screens=3,
        )

        context = GraphContext(settings=settings, scraper=mock_scraper)
        config = cast(RunnableConfig, {"configurable": {"context": context}})

        state: ScoutState = {"seen_hashes": set()}
        result = await scrape_feed(state, config)

        assert result["status"] == "scraped"
        # 3 suggestions * 4 multiplier = 12 max_posts
        mock_scraper.scrape_feed.assert_awaited_once_with(
            max_posts=12,
            seen_hashes=set(),
            target_url=None,
            screens=3,
        )

    @pytest.mark.asyncio
    async def test_scout_graph_draft_batch_skips_below_min_triage_confidence(self) -> None:
        from datetime import UTC, datetime
        from typing import cast

        from langchain_core.runnables import RunnableConfig

        from agent.graphs.scout_graph import draft_batch
        from agent.graphs.state import GraphContext, ScoutState
        from agent.models.browser import PostRecord
        from agent.models.llm import CommentDraft, TriageResult

        settings = Settings(
            nvidia_nim_api_key="nvapi-test-key",
            telegram_bot_token="123:ABC",
            telegram_authorized_chat_id=123,
            min_triage_confidence=0.75,
        )

        mock_llm = MagicMock()
        mock_llm.draft_comment = AsyncMock(
            return_value=CommentDraft(draft_comment="High signal commentary")
        )

        context = GraphContext(settings=settings, llm=mock_llm)
        config = cast(RunnableConfig, {"configurable": {"context": context}})

        post1 = PostRecord(
            post_urn="urn:li:activity:1",
            author_name="Alice",
            post_text="First post",
            post_url="https://linkedin.com/feed/update/1",
            content_hash="hash1",
            scraped_at=datetime.now(UTC),
        )
        post2 = PostRecord(
            post_urn="urn:li:activity:2",
            author_name="Bob",
            post_text="Second post",
            post_url="https://linkedin.com/feed/update/2",
            content_hash="hash2",
            scraped_at=datetime.now(UTC),
        )

        triage_low = TriageResult(
            recommendation="comment",
            confidence=0.60,  # Below 0.75 threshold
            reasoning="Marginal relevance",
        )
        triage_high = TriageResult(
            recommendation="comment",
            confidence=0.85,  # Above threshold
            reasoning="Strong relevance",
        )

        state: ScoutState = {
            "triage_results": [(post1, triage_low), (post2, triage_high)],
        }

        result = await draft_batch(state, config)
        drafts = result["drafts"]

        # Only post2 should qualify for drafting
        assert len(drafts) == 1
        assert drafts[0][0].post_urn == "urn:li:activity:2"
        mock_llm.draft_comment.assert_awaited_once_with(post2, triage_high)
