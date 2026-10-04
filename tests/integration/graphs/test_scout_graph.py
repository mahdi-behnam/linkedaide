"""Integration tests for ScoutGraph topology, routing, and side effects."""

from __future__ import annotations

import subprocess
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from pydantic import SecretStr

from agent.config import Settings
from agent.errors import BotDetectionError, ScrapeError
from agent.graphs.scout_graph import build_scout_graph, get_scout_target_sources
from agent.graphs.state import GraphContext, ScoutState
from agent.models import CommentDraft, PendingAction, PostRecord, RiskFlag, TriageResult
from agent.safety.rate_limiter import DailyCapEnforcer
from agent.state.store import GitStateStore


@pytest.fixture
def test_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir(parents=True, exist_ok=True)
    subprocess.run(["git", "init"], cwd=str(repo), check=True, capture_output=True)
    subprocess.run(
        ["git", "config", "user.name", "Test"], cwd=str(repo), check=True, capture_output=True
    )
    subprocess.run(
        ["git", "config", "user.email", "test@test.com"],
        cwd=str(repo),
        check=True,
        capture_output=True,
    )

    state_dir = repo / "state"
    state_dir.mkdir(parents=True, exist_ok=True)
    (state_dir / ".gitkeep").write_text("", encoding="utf-8")
    subprocess.run(["git", "add", "."], cwd=str(repo), check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", "init"], cwd=str(repo), check=True, capture_output=True)
    return repo


@pytest.fixture
def mock_context(test_repo: Path) -> GraphContext:
    settings = Settings(
        nvidia_nim_api_key=SecretStr("nvapi-test"),
        nim_model_primary="primary-model",
        nim_model_fallback="fallback-model",
        telegram_bot_token=SecretStr("123:token"),
        telegram_authorized_chat_id=12345,
        user_focus_areas=["AI", "Python"],
        max_suggestions_per_run=3,
        state_dir=test_repo / "state",
        dry_run=True,
    )
    state_store = GitStateStore(test_repo)
    enforcer = DailyCapEnforcer(settings)

    mock_llm: Any = MagicMock()
    mock_telegram: Any = MagicMock()
    mock_telegram.send_suggestion = AsyncMock(return_value=101)
    mock_telegram.send_notification = AsyncMock(return_value=102)

    mock_scraper: Any = MagicMock()

    return GraphContext(
        settings=settings,
        llm=mock_llm,
        state_store=state_store,
        telegram=mock_telegram,
        scraper=mock_scraper,
        enforcer=enforcer,
    )


@pytest.mark.asyncio
async def test_scout_graph_halted_run(mock_context: GraphContext) -> None:
    paused_settings = mock_context.settings.model_copy(update={"agent_paused": True})
    paused_context = GraphContext(
        settings=paused_settings,
        llm=mock_context.llm,
        state_store=mock_context.state_store,
        telegram=mock_context.telegram,
        scraper=mock_context.scraper,
        enforcer=mock_context.enforcer,
    )

    graph = build_scout_graph()
    initial_state: ScoutState = {}
    result = await graph.ainvoke(
        initial_state, config={"configurable": {"context": paused_context}}
    )

    assert result["status"] == "halted"
    assert result["halted_reason"] is not None
    scraper_mock: Any = mock_context.scraper
    assert not scraper_mock.scrape_feed.called


@pytest.mark.asyncio
async def test_scout_graph_zero_new_posts(mock_context: GraphContext) -> None:
    scraper_mock: Any = mock_context.scraper
    scraper_mock.scrape_feed = AsyncMock(return_value=[])

    graph = build_scout_graph()
    result = await graph.ainvoke({}, config={"configurable": {"context": mock_context}})

    assert len(result.get("posts", [])) == 0
    llm_mock: Any = mock_context.llm
    assert not llm_mock.evaluate_post.called


@pytest.mark.asyncio
async def test_scout_graph_all_posts_ignored_by_triage(mock_context: GraphContext) -> None:
    now = datetime.now(UTC)
    sample_posts = [
        PostRecord(
            post_urn="urn:li:activity:1",
            post_url="https://www.linkedin.com/feed/update/urn:li:activity:1/",
            author_name="Sales Guy",
            post_text="Buy our product now!",
            content_hash="hash_1",
            scraped_at=now,
        )
    ]
    scraper_mock: Any = mock_context.scraper
    scraper_mock.scrape_feed = AsyncMock(return_value=sample_posts)

    llm_mock: Any = mock_context.llm
    llm_mock.evaluate_post = AsyncMock(
        return_value=TriageResult(
            recommendation="ignore",
            confidence=0.9,
            reasoning="Sales pitch",
            risk_flags=[RiskFlag.SALES_PITCH],
        )
    )

    graph = build_scout_graph()
    result = await graph.ainvoke({}, config={"configurable": {"context": mock_context}})

    assert len(result.get("posts", [])) == 1
    assert len(result.get("triage_results", [])) == 1
    assert not llm_mock.draft_comment.called
    assert len(result.get("pending_items", [])) == 0


@pytest.mark.asyncio
async def test_scout_graph_qualifying_post_creates_pending_and_notifies(
    mock_context: GraphContext,
) -> None:
    now = datetime.now(UTC)
    sample_post = PostRecord(
        post_urn="urn:li:activity:200",
        post_url="https://www.linkedin.com/feed/update/urn:li:activity:200/",
        author_name="Dr. AI",
        post_text="New paper on agentic reasoning models with structured output.",
        content_hash="hash_ai_200",
        scraped_at=now,
    )
    scraper_mock: Any = mock_context.scraper
    scraper_mock.scrape_feed = AsyncMock(return_value=[sample_post])

    llm_mock: Any = mock_context.llm
    llm_mock.evaluate_post = AsyncMock(
        return_value=TriageResult(
            recommendation="comment",
            confidence=0.95,
            reasoning="High relevance to AI architecture",
            risk_flags=[],
        )
    )
    llm_mock.draft_comment = AsyncMock(
        return_value=CommentDraft(
            draft_comment="Great technical analysis on structured decoding performance.",
            topic_tags=["AI", "LLM"],
        )
    )

    graph = build_scout_graph()
    result = await graph.ainvoke({}, config={"configurable": {"context": mock_context}})

    pending_items = result.get("pending_items", [])
    assert len(pending_items) == 1
    assert pending_items[0].confidence == 0.95
    assert (
        pending_items[0].draft_text
        == "Great technical analysis on structured decoding performance."
    )
    assert pending_items[0].telegram_message_id == 101

    assert mock_context.state_store is not None
    persisted = mock_context.state_store.read_pending(pending_items[0].item_id)
    assert persisted is not None
    assert persisted.post_urn == "urn:li:activity:200"


@pytest.mark.asyncio
async def test_scout_graph_prunes_expired_pending_and_updates_telegram(
    mock_context: GraphContext,
) -> None:
    assert mock_context.state_store is not None
    now = datetime.now(UTC)

    # Expired item (created 20h ago with TTL=12h)
    item_expired = PendingAction(
        item_id="exp_item_01",
        action_type="approve_comment",
        created_at=now - timedelta(hours=20),
        post_urn="urn:li:activity:exp101",
        post_url="https://www.linkedin.com/feed/update/urn:li:activity:exp101/",
        author_name="Expired Author",
        post_excerpt="Old post...",
        draft_text="Old draft...",
        confidence=0.9,
        reasoning="Relevant at the time",
        telegram_chat_id=12345,
        telegram_message_id=555,
    )
    # Fresh item (created 1h ago)
    item_fresh = PendingAction(
        item_id="fresh_item_01",
        action_type="approve_post",
        created_at=now - timedelta(hours=1),
        post_urn="",
        post_url="",
        author_name="",
        post_excerpt="",
        draft_text="Fresh post draft...",
        confidence=0.85,
        reasoning="Fresh reasoning",
        telegram_chat_id=12345,
        telegram_message_id=556,
    )

    mock_context.state_store.write_pending(item_expired)
    mock_context.state_store.write_pending(item_fresh)

    mock_telegram: Any = mock_context.telegram
    mock_telegram.edit_to_outcome = AsyncMock()

    scraper_mock: Any = mock_context.scraper
    scraper_mock.scrape_feed = AsyncMock(return_value=[])

    graph = build_scout_graph()
    result = await graph.ainvoke({}, config={"configurable": {"context": mock_context}})

    # Check pruned items in graph state
    pruned_items = result.get("pruned_items", [])
    assert len(pruned_items) == 1
    assert pruned_items[0].item_id == "exp_item_01"

    # Verify Telegram edit_to_outcome was called with exact text
    mock_telegram.edit_to_outcome.assert_awaited_once_with(
        chat_id=12345,
        message_id=555,
        outcome_text="⏱️ Suggestion expired (exceeded approval TTL)",
    )

    # Disk state verification
    assert mock_context.state_store.read_pending("exp_item_01") is None
    loaded_fresh = mock_context.state_store.read_pending("fresh_item_01")
    assert loaded_fresh is not None
    assert loaded_fresh.item_id == "fresh_item_01"

    # History verification
    history = mock_context.state_store.read_history()
    assert len(history) == 1
    assert history[0].item_id == "exp_item_01"
    assert history[0].final_status == "expired"
    assert history[0].error == "Pending approval expired (exceeded 12h TTL)"


@pytest.mark.asyncio
async def test_scout_graph_prune_resilient_to_telegram_error(
    mock_context: GraphContext,
) -> None:
    assert mock_context.state_store is not None
    now = datetime.now(UTC)

    item_expired = PendingAction(
        item_id="exp_item_err",
        action_type="approve_comment",
        created_at=now - timedelta(hours=24),
        post_urn="urn:li:activity:err1",
        post_url="https://www.linkedin.com/feed/update/urn:li:activity:err1/",
        author_name="Error Author",
        post_excerpt="Post...",
        draft_text="Draft...",
        confidence=0.9,
        reasoning="Reasoning",
        telegram_chat_id=12345,
        telegram_message_id=777,
    )
    mock_context.state_store.write_pending(item_expired)

    # Mock telegram raising an API/network exception on edit_to_outcome
    mock_telegram: Any = mock_context.telegram
    mock_telegram.edit_to_outcome = AsyncMock(side_effect=Exception("Telegram connection timeout"))

    scraper_mock: Any = mock_context.scraper
    scraper_mock.scrape_feed = AsyncMock(return_value=[])

    graph = build_scout_graph()
    # Graph execution must NOT crash
    result = await graph.ainvoke({}, config={"configurable": {"context": mock_context}})

    assert len(result.get("pruned_items", [])) == 1
    # File must still be pruned from disk
    assert mock_context.state_store.read_pending("exp_item_err") is None
    # History must still be written
    history = mock_context.state_store.read_history()
    assert len(history) == 1
    assert history[0].final_status == "expired"


@pytest.mark.asyncio
async def test_scout_graph_prune_skips_telegram_when_no_message_id(
    mock_context: GraphContext,
) -> None:
    assert mock_context.state_store is not None
    now = datetime.now(UTC)

    item_no_msg = PendingAction(
        item_id="exp_item_nomsg",
        action_type="approve_comment",
        created_at=now - timedelta(hours=24),
        post_urn="urn:li:activity:nomsg1",
        post_url="https://www.linkedin.com/feed/update/urn:li:activity:nomsg1/",
        author_name="NoMsg Author",
        post_excerpt="Post...",
        draft_text="Draft...",
        confidence=0.9,
        reasoning="Reasoning",
        telegram_chat_id=12345,
        telegram_message_id=0,  # No telegram message ID
    )
    mock_context.state_store.write_pending(item_no_msg)

    mock_telegram: Any = mock_context.telegram
    mock_telegram.edit_to_outcome = AsyncMock()

    scraper_mock: Any = mock_context.scraper
    scraper_mock.scrape_feed = AsyncMock(return_value=[])

    graph = build_scout_graph()
    result = await graph.ainvoke({}, config={"configurable": {"context": mock_context}})

    assert len(result.get("pruned_items", [])) == 1
    assert not mock_telegram.edit_to_outcome.called
    assert mock_context.state_store.read_pending("exp_item_nomsg") is None
    assert len(mock_context.state_store.read_history()) == 1


# ---------------------------------------------------------------------------
# Targeted Scouting Integration Tests
# ---------------------------------------------------------------------------


def test_get_scout_target_sources_fallback_default(mock_context: GraphContext) -> None:
    """Verify get_scout_target_sources falls back to [None] when no targets are configured."""
    settings = mock_context.settings.model_copy(
        update={"scout_target_urls": [], "target_hashtags": []}
    )
    sources = get_scout_target_sources(settings)
    assert sources == [None]


def test_get_scout_target_sources_combines_and_deduplicates(mock_context: GraphContext) -> None:
    """Verify get_scout_target_sources combines URLs and hashtags, stripping and deduplicating."""
    settings = mock_context.settings.model_copy(
        update={
            "scout_target_urls": [
                "https://www.linkedin.com/in/creator/recent-activity/all/",
                "https://www.linkedin.com/in/creator/recent-activity/all/",
                "   ",
            ],
            "target_hashtags": ["python", "#python", "#AI_Agents"],
        }
    )
    sources = get_scout_target_sources(settings)
    assert sources == [
        "https://www.linkedin.com/in/creator/recent-activity/all/",
        "https://www.linkedin.com/feed/hashtag/?keywords=python",
        "https://www.linkedin.com/feed/hashtag/?keywords=ai_agents",
    ]


@pytest.mark.asyncio
async def test_scout_graph_multi_target_sequential_iteration(mock_context: GraphContext) -> None:
    """Verify ScoutGraph sequentially scrapes multiple targets with mocked humanized_dwell."""
    now = datetime.now(UTC)
    post1 = PostRecord(
        post_urn="urn:li:activity:target1",
        post_url="https://www.linkedin.com/feed/update/urn:li:activity:target1/",
        author_name="Target 1 Author",
        post_text="Target 1 content",
        content_hash="hash_target_1",
        scraped_at=now,
    )
    post2 = PostRecord(
        post_urn="urn:li:activity:target2",
        post_url="https://www.linkedin.com/feed/update/urn:li:activity:target2/",
        author_name="Target 2 Author",
        post_text="Target 2 content",
        content_hash="hash_target_2",
        scraped_at=now,
    )

    settings = mock_context.settings.model_copy(
        update={
            "scout_target_urls": ["https://www.linkedin.com/in/creator/recent-activity/all/"],
            "target_hashtags": ["python"],
            "max_suggestions_per_run": 3,
        }
    )
    multi_context = GraphContext(
        settings=settings,
        llm=mock_context.llm,
        state_store=mock_context.state_store,
        telegram=mock_context.telegram,
        scraper=mock_context.scraper,
        enforcer=mock_context.enforcer,
    )

    scraper_mock: Any = multi_context.scraper
    scraper_mock.scrape_feed = AsyncMock(side_effect=[[post1], [post2]])

    llm_mock: Any = multi_context.llm
    llm_mock.evaluate_post = AsyncMock(
        return_value=TriageResult(
            recommendation="ignore",
            confidence=0.5,
            reasoning="Ignore in test",
            risk_flags=[],
        )
    )

    graph = build_scout_graph()

    with patch("agent.graphs.scout_graph.humanized_dwell", new_callable=AsyncMock) as mock_dwell:
        result = await graph.ainvoke({}, config={"configurable": {"context": multi_context}})

    # Assert scraper called twice
    assert scraper_mock.scrape_feed.call_count == 2
    # Verify target URLs passed in order
    first_call_kwargs = scraper_mock.scrape_feed.call_args_list[0].kwargs
    second_call_kwargs = scraper_mock.scrape_feed.call_args_list[1].kwargs
    assert (
        first_call_kwargs["target_url"]
        == "https://www.linkedin.com/in/creator/recent-activity/all/"
    )
    assert (
        second_call_kwargs["target_url"] == "https://www.linkedin.com/feed/hashtag/?keywords=python"
    )
    assert second_call_kwargs["max_posts"] == 8  # 9 - 1

    # Assert dwell called exactly once between targets (not before target 1)
    assert mock_dwell.call_count == 1
    mock_dwell.assert_awaited_once_with(min_seconds=1.5, max_seconds=3.5)

    assert len(result.get("posts", [])) == 2


@pytest.mark.asyncio
async def test_scout_graph_multi_target_quota_early_break(mock_context: GraphContext) -> None:
    """Verify ScoutGraph stops iterating when post quota is fulfilled on an early target."""
    now = datetime.now(UTC)
    posts = [
        PostRecord(
            post_urn=f"urn:li:activity:batch_{i}",
            post_url=f"https://www.linkedin.com/feed/update/urn:li:activity:batch_{i}/",
            author_name=f"Author {i}",
            post_text=f"Content {i}",
            content_hash=f"hash_{i}",
            scraped_at=now,
        )
        for i in range(9)  # 3 * 3 = 9 posts (quota fulfilled)
    ]

    settings = mock_context.settings.model_copy(
        update={
            "scout_target_urls": [
                "https://www.linkedin.com/feed/hashtag/?keywords=python",
                "https://www.linkedin.com/feed/hashtag/?keywords=ai",
            ],
            "max_suggestions_per_run": 3,
        }
    )
    quota_context = GraphContext(
        settings=settings,
        llm=mock_context.llm,
        state_store=mock_context.state_store,
        telegram=mock_context.telegram,
        scraper=mock_context.scraper,
        enforcer=mock_context.enforcer,
    )

    scraper_mock: Any = quota_context.scraper
    scraper_mock.scrape_feed = AsyncMock(return_value=posts)

    llm_mock: Any = quota_context.llm
    llm_mock.evaluate_post = AsyncMock(
        return_value=TriageResult(
            recommendation="ignore",
            confidence=0.5,
            reasoning="Ignore",
            risk_flags=[],
        )
    )

    graph = build_scout_graph()

    with patch("agent.graphs.scout_graph.humanized_dwell", new_callable=AsyncMock) as mock_dwell:
        result = await graph.ainvoke({}, config={"configurable": {"context": quota_context}})

    # Only first target should be scraped
    assert scraper_mock.scrape_feed.call_count == 1
    assert mock_dwell.call_count == 0
    assert len(result.get("posts", [])) == 9


@pytest.mark.asyncio
async def test_scout_graph_scrape_error_isolation_continues(mock_context: GraphContext) -> None:
    """Verify ScrapeError on one target is isolated and the graph continues to subsequent targets."""
    now = datetime.now(UTC)
    post2 = PostRecord(
        post_urn="urn:li:activity:target2_ok",
        post_url="https://www.linkedin.com/feed/update/urn:li:activity:target2_ok/",
        author_name="Target 2 OK",
        post_text="Good content",
        content_hash="hash_target_2_ok",
        scraped_at=now,
    )

    settings = mock_context.settings.model_copy(
        update={
            "scout_target_urls": ["https://www.linkedin.com/in/drifted-feed/"],
            "target_hashtags": ["python"],
        }
    )
    isolation_context = GraphContext(
        settings=settings,
        llm=mock_context.llm,
        state_store=mock_context.state_store,
        telegram=mock_context.telegram,
        scraper=mock_context.scraper,
        enforcer=mock_context.enforcer,
    )

    scraper_mock: Any = isolation_context.scraper
    scraper_mock.scrape_feed = AsyncMock(
        side_effect=[
            ScrapeError("Selector drift on drifted-feed container"),
            [post2],
        ]
    )

    llm_mock: Any = isolation_context.llm
    llm_mock.evaluate_post = AsyncMock(
        return_value=TriageResult(
            recommendation="ignore",
            confidence=0.5,
            reasoning="Ignore",
            risk_flags=[],
        )
    )

    graph = build_scout_graph()

    with patch("agent.graphs.scout_graph.humanized_dwell", new_callable=AsyncMock) as mock_dwell:
        result = await graph.ainvoke({}, config={"configurable": {"context": isolation_context}})

    assert scraper_mock.scrape_feed.call_count == 2
    assert mock_dwell.call_count == 1
    assert len(result.get("posts", [])) == 1
    assert any("Selector drift" in err for err in result.get("errors", []))


@pytest.mark.asyncio
async def test_scout_graph_bot_detection_halts_immediately_multi_target(
    mock_context: GraphContext,
) -> None:
    """Verify BotDetectionError immediately halts, trips breaker, and skips remaining targets."""
    settings = mock_context.settings.model_copy(
        update={
            "scout_target_urls": [
                "https://www.linkedin.com/feed/hashtag/?keywords=python",
                "https://www.linkedin.com/feed/hashtag/?keywords=ai",
            ],
        }
    )
    bot_context = GraphContext(
        settings=settings,
        llm=mock_context.llm,
        state_store=mock_context.state_store,
        telegram=mock_context.telegram,
        scraper=mock_context.scraper,
        enforcer=mock_context.enforcer,
    )

    scraper_mock: Any = bot_context.scraper
    scraper_mock.scrape_feed = AsyncMock(
        side_effect=BotDetectionError("CAPTCHA checkpoint encountered")
    )

    telegram_mock: Any = bot_context.telegram

    graph = build_scout_graph()

    with patch("agent.graphs.scout_graph.humanized_dwell", new_callable=AsyncMock) as mock_dwell:
        result = await graph.ainvoke({}, config={"configurable": {"context": bot_context}})

    # Should stop on target 1 immediately
    assert scraper_mock.scrape_feed.call_count == 1
    assert mock_dwell.call_count == 0
    assert result["status"] == "halted_bot_detection"
    assert result["halted_reason"] is not None
    assert len(result.get("posts", [])) == 0
    assert telegram_mock is not None
    assert telegram_mock.send_notification.called


@pytest.mark.asyncio
async def test_scout_graph_connection_candidate_discovery(mock_context: GraphContext) -> None:
    """Verify qualifying posts discover connection outreach candidates and persist them to connection_queue."""
    now = datetime.now(UTC)
    sample_posts = [
        PostRecord(
            post_urn="urn:li:activity:conn_disc_1",
            post_url="https://www.linkedin.com/feed/update/urn:li:activity:conn_disc_1/",
            author_name="Alice Engineer",
            post_text="Deep dive into distributed systems and consensus!",
            content_hash="hash_conn_disc_1",
            scraped_at=now,
        )
    ]
    scraper_mock: Any = mock_context.scraper
    scraper_mock.scrape_feed = AsyncMock(return_value=sample_posts)

    llm_mock: Any = mock_context.llm
    llm_mock.evaluate_post = AsyncMock(
        return_value=TriageResult(
            recommendation="comment",
            confidence=0.95,
            reasoning="Strong technical post",
            risk_flags=[],
        )
    )
    llm_mock.draft_comment = AsyncMock(
        return_value=CommentDraft(
            draft_comment="Insightful thoughts on consensus protocols!",
            topic_tags=["distributed-systems"],
        )
    )

    graph = build_scout_graph()
    result = await graph.ainvoke({}, config={"configurable": {"context": mock_context}})

    assert result["status"] == "completed"
    candidates = result.get("connection_candidates", [])
    assert len(candidates) > 0
    assert candidates[0].target_name == "Alice Engineer"
    assert "linkedin.com/in/" in candidates[0].profile_url

    # Verify persisted in state_store connection_queue
    assert mock_context.state_store is not None
    queue = mock_context.state_store.load_connection_queue()
    assert len(queue) > 0
    assert queue[0].target_name == "Alice Engineer"
    assert queue[0].status == "pending"
