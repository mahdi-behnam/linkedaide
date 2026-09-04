"""Integration test suite for targeted scouting in ScoutGraph.

Tests ScoutGraph multi-source iteration, dwell delays, early break on quota fulfillment,
BotDetectionError circuit breaker tripping and halting, and ScrapeError isolation.
"""

from __future__ import annotations

import json
import subprocess
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from pydantic import SecretStr

from agent.config import Settings
from agent.errors import BotDetectionError, ScrapeError, SessionExpiredError
from agent.graphs.scout_graph import build_scout_graph
from agent.graphs.state import GraphContext
from agent.models.schemas import CommentDraft, EngagementStyle, PostRecord, TriageResult
from agent.safety.circuit_breaker import is_halted
from agent.safety.rate_limiter import DailyCapEnforcer
from agent.state.store import GitStateStore


@pytest.fixture
def challenger_test_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir(parents=True, exist_ok=True)
    subprocess.run(["git", "init"], cwd=str(repo), check=True, capture_output=True)
    subprocess.run(
        ["git", "config", "user.name", "ChallengerTest"],
        cwd=str(repo),
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ["git", "config", "user.email", "challenger@test.com"],
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
def challenger_context(challenger_test_repo: Path) -> GraphContext:
    settings = Settings(
        nvidia_nim_api_key=SecretStr("nvapi-challenger-test"),
        nim_model_primary="primary-model",
        nim_model_fallback="fallback-model",
        telegram_bot_token=SecretStr("123:token"),
        telegram_authorized_chat_id=12345,
        user_focus_areas=["AI", "Python"],
        max_suggestions_per_run=3,
        state_dir=challenger_test_repo / "state",
        dry_run=True,
    )
    state_store = GitStateStore(challenger_test_repo)
    enforcer = DailyCapEnforcer(settings)

    mock_llm: Any = MagicMock()
    mock_llm.evaluate_post = AsyncMock(
        return_value=TriageResult(
            recommendation="comment",
            confidence=0.9,
            reasoning="Relevant post",
            risk_flags=[],
            engagement_style=EngagementStyle.TECHNICAL_DEEP_DIVE,
        )
    )
    mock_llm.draft_comment = AsyncMock(
        return_value=CommentDraft(
            draft_comment="Great insightful post!",
            engagement_style=EngagementStyle.TECHNICAL_DEEP_DIVE,
        )
    )

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


def _make_dummy_post(urn_suffix: str, content: str = "Test content") -> PostRecord:
    now = datetime.now(UTC)
    return PostRecord(
        post_urn=f"urn:li:activity:{urn_suffix}",
        post_url=f"https://www.linkedin.com/feed/update/urn:li:activity:{urn_suffix}/",
        author_name=f"Author {urn_suffix}",
        post_text=content,
        content_hash=f"hash_{urn_suffix}",
        scraped_at=now,
    )


# ---------------------------------------------------------------------------
# Objective 1 & 2: Dwell Delay Enforcement & Timing
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_obj1_never_dwell_before_first_target_single_source(
    challenger_context: GraphContext,
) -> None:
    """Obj 1: Single default target source must NEVER invoke humanized_dwell."""
    post = _make_dummy_post("p1")
    scraper_mock: Any = challenger_context.scraper
    scraper_mock.scrape_feed = AsyncMock(return_value=[post])

    graph = build_scout_graph()

    with patch("agent.graphs.scout_graph.humanized_dwell", new_callable=AsyncMock) as mock_dwell:
        result = await graph.ainvoke({}, config={"configurable": {"context": challenger_context}})

    assert scraper_mock.scrape_feed.call_count == 1
    assert mock_dwell.call_count == 0
    assert len(result.get("posts", [])) == 1


@pytest.mark.asyncio
async def test_obj1_and_obj2_dwell_timing_order_multi_targets(
    challenger_context: GraphContext,
) -> None:
    """Obj 1 & 2: humanized_dwell is NEVER invoked before idx==0 and IS invoked on transitions idx>0.

    Verify strict chronological interleaving:
    scrape(target_0) -> dwell(1.5, 3.5) -> scrape(target_1) -> dwell(1.5, 3.5) -> scrape(target_2)
    """
    settings = challenger_context.settings.model_copy(
        update={
            "scout_target_urls": [
                "https://www.linkedin.com/in/creator1/recent-activity/all/",
                "https://www.linkedin.com/in/creator2/recent-activity/all/",
                "https://www.linkedin.com/in/creator3/recent-activity/all/",
            ],
            "max_suggestions_per_run": 5,  # quota = 15
        }
    )
    ctx = GraphContext(
        settings=settings,
        llm=challenger_context.llm,
        state_store=challenger_context.state_store,
        telegram=challenger_context.telegram,
        scraper=challenger_context.scraper,
        enforcer=challenger_context.enforcer,
    )

    execution_timeline: list[str] = []

    async def mock_scrape_feed(*args: Any, **kwargs: Any) -> list[PostRecord]:
        t_url = kwargs.get("target_url")
        execution_timeline.append(f"scrape:{t_url}")
        return [_make_dummy_post(f"post_{len(execution_timeline)}")]

    async def mock_dwell_fn(min_seconds: float = 1.5, max_seconds: float = 3.5) -> None:
        execution_timeline.append(f"dwell:{min_seconds}-{max_seconds}")

    scraper_mock: Any = ctx.scraper
    scraper_mock.scrape_feed = AsyncMock(side_effect=mock_scrape_feed)

    graph = build_scout_graph()

    with patch("agent.graphs.scout_graph.humanized_dwell", side_effect=mock_dwell_fn) as mock_dwell:
        result = await graph.ainvoke({}, config={"configurable": {"context": ctx}})

    expected_timeline = [
        "scrape:https://www.linkedin.com/in/creator1/recent-activity/all/",
        "dwell:1.5-3.5",
        "scrape:https://www.linkedin.com/in/creator2/recent-activity/all/",
        "dwell:1.5-3.5",
        "scrape:https://www.linkedin.com/in/creator3/recent-activity/all/",
    ]
    assert execution_timeline == expected_timeline
    assert mock_dwell.call_count == 2
    assert len(result.get("posts", [])) == 3


# ---------------------------------------------------------------------------
# Objective 3: Post Quota Fulfillment & Early Break
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_obj3_quota_fulfilled_on_first_target_no_extra_navigation_or_dwell(
    challenger_context: GraphContext,
) -> None:
    """Obj 3: Fulfilling quota on target 0 immediately halts loop; 0 dwells, 0 extra navigations."""
    # max_suggestions_per_run = 3 -> quota = 9 posts
    posts_target0 = [_make_dummy_post(f"quota_p{i}") for i in range(9)]

    settings = challenger_context.settings.model_copy(
        update={
            "scout_target_urls": [
                "https://www.linkedin.com/feed/hashtag/?keywords=python",
                "https://www.linkedin.com/feed/hashtag/?keywords=ai",
                "https://www.linkedin.com/feed/hashtag/?keywords=rust",
            ],
            "max_suggestions_per_run": 3,
        }
    )
    ctx = GraphContext(
        settings=settings,
        llm=challenger_context.llm,
        state_store=challenger_context.state_store,
        telegram=challenger_context.telegram,
        scraper=challenger_context.scraper,
        enforcer=challenger_context.enforcer,
    )

    scraper_mock: Any = ctx.scraper
    scraper_mock.scrape_feed = AsyncMock(return_value=posts_target0)

    graph = build_scout_graph()

    with patch("agent.graphs.scout_graph.humanized_dwell", new_callable=AsyncMock) as mock_dwell:
        result = await graph.ainvoke({}, config={"configurable": {"context": ctx}})

    assert scraper_mock.scrape_feed.call_count == 1
    assert mock_dwell.call_count == 0
    first_call_target = scraper_mock.scrape_feed.call_args.kwargs.get("target_url")
    assert first_call_target == "https://www.linkedin.com/feed/hashtag/?keywords=python"
    assert len(result.get("posts", [])) == 9


@pytest.mark.asyncio
async def test_obj3_quota_fulfilled_on_second_target_stops_before_third(
    challenger_context: GraphContext,
) -> None:
    """Obj 3: Target 0 yields 5 posts, Target 1 yields 4 posts (total 9 >= 9).

    Target 2 must NOT be scraped and Dwell 2 must NOT be executed.
    """
    posts_t0 = [_make_dummy_post(f"t0_{i}") for i in range(5)]
    posts_t1 = [_make_dummy_post(f"t1_{i}") for i in range(4)]

    settings = challenger_context.settings.model_copy(
        update={
            "scout_target_urls": [
                "https://www.linkedin.com/feed/hashtag/?keywords=source1",
                "https://www.linkedin.com/feed/hashtag/?keywords=source2",
                "https://www.linkedin.com/feed/hashtag/?keywords=source3",
            ],
            "max_suggestions_per_run": 3,  # quota = 9
        }
    )
    ctx = GraphContext(
        settings=settings,
        llm=challenger_context.llm,
        state_store=challenger_context.state_store,
        telegram=challenger_context.telegram,
        scraper=challenger_context.scraper,
        enforcer=challenger_context.enforcer,
    )

    scraper_mock: Any = ctx.scraper
    scraper_mock.scrape_feed = AsyncMock(side_effect=[posts_t0, posts_t1])

    graph = build_scout_graph()

    with patch("agent.graphs.scout_graph.humanized_dwell", new_callable=AsyncMock) as mock_dwell:
        result = await graph.ainvoke({}, config={"configurable": {"context": ctx}})

    # Exactly 2 scrape calls and 1 dwell call
    assert scraper_mock.scrape_feed.call_count == 2
    assert mock_dwell.call_count == 1
    # Check max_posts passed to second call was remaining quota (9 - 5 = 4)
    second_call_max = scraper_mock.scrape_feed.call_args_list[1].kwargs.get("max_posts")
    assert second_call_max == 4
    assert len(result.get("posts", [])) == 9


@pytest.mark.asyncio
async def test_obj3_overshoot_quota_breaks_without_extra_dwell(
    challenger_context: GraphContext,
) -> None:
    """Obj 3: If target 0 yields 12 posts (exceeding quota 9), breaks immediately."""
    posts_overshoot = [_make_dummy_post(f"over_{i}") for i in range(12)]

    settings = challenger_context.settings.model_copy(
        update={
            "scout_target_urls": [
                "https://www.linkedin.com/feed/hashtag/?keywords=source1",
                "https://www.linkedin.com/feed/hashtag/?keywords=source2",
            ],
            "max_suggestions_per_run": 3,
        }
    )
    ctx = GraphContext(
        settings=settings,
        llm=challenger_context.llm,
        state_store=challenger_context.state_store,
        telegram=challenger_context.telegram,
        scraper=challenger_context.scraper,
        enforcer=challenger_context.enforcer,
    )

    scraper_mock: Any = ctx.scraper
    scraper_mock.scrape_feed = AsyncMock(return_value=posts_overshoot)

    graph = build_scout_graph()

    with patch("agent.graphs.scout_graph.humanized_dwell", new_callable=AsyncMock) as mock_dwell:
        result = await graph.ainvoke({}, config={"configurable": {"context": ctx}})

    assert scraper_mock.scrape_feed.call_count == 1
    assert mock_dwell.call_count == 0
    assert len(result.get("posts", [])) == 12


@pytest.mark.asyncio
async def test_obj3_zero_quota_breaks_immediately(
    challenger_context: GraphContext,
) -> None:
    """Obj 3 boundary: max_suggestions_per_run = 0 -> quota = 0 -> loop breaks on idx==0."""
    settings = challenger_context.settings.model_copy(
        update={
            "scout_target_urls": [
                "https://www.linkedin.com/feed/hashtag/?keywords=source1",
                "https://www.linkedin.com/feed/hashtag/?keywords=source2",
            ],
            "max_suggestions_per_run": 0,
        }
    )
    ctx = GraphContext(
        settings=settings,
        llm=challenger_context.llm,
        state_store=challenger_context.state_store,
        telegram=challenger_context.telegram,
        scraper=challenger_context.scraper,
        enforcer=challenger_context.enforcer,
    )

    scraper_mock: Any = ctx.scraper
    scraper_mock.scrape_feed = AsyncMock()

    graph = build_scout_graph()

    with patch("agent.graphs.scout_graph.humanized_dwell", new_callable=AsyncMock) as mock_dwell:
        result = await graph.ainvoke({}, config={"configurable": {"context": ctx}})

    assert scraper_mock.scrape_feed.call_count == 0
    assert mock_dwell.call_count == 0
    assert result.get("posts", []) == []


# ---------------------------------------------------------------------------
# Objective 4: BotDetectionError Halting & Circuit Breaker Tripping
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_obj4_bot_detection_on_first_target_halts_and_trips_breaker(
    challenger_context: GraphContext, challenger_test_repo: Path
) -> None:
    """Obj 4: BotDetectionError on target 0 trips circuit breaker, creates incident.json, notifies, and halts."""
    settings = challenger_context.settings.model_copy(
        update={
            "scout_target_urls": [
                "https://www.linkedin.com/feed/hashtag/?keywords=python",
                "https://www.linkedin.com/feed/hashtag/?keywords=ai",
            ],
        }
    )
    ctx = GraphContext(
        settings=settings,
        llm=challenger_context.llm,
        state_store=challenger_context.state_store,
        telegram=challenger_context.telegram,
        scraper=challenger_context.scraper,
        enforcer=challenger_context.enforcer,
    )

    scraper_mock: Any = ctx.scraper
    bot_msg = "Security checkpoint: Cloudflare Turnstile challenge detected"
    scraper_mock.scrape_feed = AsyncMock(side_effect=BotDetectionError(bot_msg))

    telegram_mock: Any = ctx.telegram

    graph = build_scout_graph()

    with patch("agent.graphs.scout_graph.humanized_dwell", new_callable=AsyncMock) as mock_dwell:
        result = await graph.ainvoke({}, config={"configurable": {"context": ctx}})

    # 1. Scraper called once, second target never called, no dwell
    assert scraper_mock.scrape_feed.call_count == 1
    assert mock_dwell.call_count == 0

    # 2. Status is halted_bot_detection and halted_reason is set
    assert result["status"] == "halted_bot_detection"
    assert bot_msg in result["halted_reason"]

    # 3. Circuit breaker file incident.json actually created on filesystem
    incident_file = challenger_test_repo / "state" / "incident.json"
    assert incident_file.exists(), "incident.json must be created when circuit breaker trips"
    incident_data = json.loads(incident_file.read_text(encoding="utf-8"))
    assert incident_data["reason"] == bot_msg
    assert "tripped_at" in incident_data

    # 4. is_halted reports True
    halted, reason = is_halted(challenger_test_repo, ctx.settings)
    assert halted is True
    assert reason is not None and bot_msg in reason

    # 5. Telegram notification sent
    assert telegram_mock.send_notification.called
    notification_msg = telegram_mock.send_notification.call_args[0][0]
    assert "Circuit breaker tripped" in notification_msg

    # 6. Downstream LLM not called
    llm_mock: Any = ctx.llm
    assert not llm_mock.evaluate_post.called


@pytest.mark.asyncio
async def test_obj4_bot_detection_on_second_target_discards_earlier_posts_and_trips_breaker(
    challenger_context: GraphContext, challenger_test_repo: Path
) -> None:
    """Obj 4: BotDetectionError on target 1 must discard posts from target 0, trip breaker, and halt."""
    post_t0 = _make_dummy_post("t0_ok")

    settings = challenger_context.settings.model_copy(
        update={
            "scout_target_urls": [
                "https://www.linkedin.com/feed/hashtag/?keywords=source1",
                "https://www.linkedin.com/feed/hashtag/?keywords=source2",
                "https://www.linkedin.com/feed/hashtag/?keywords=source3",
            ],
        }
    )
    ctx = GraphContext(
        settings=settings,
        llm=challenger_context.llm,
        state_store=challenger_context.state_store,
        telegram=challenger_context.telegram,
        scraper=challenger_context.scraper,
        enforcer=challenger_context.enforcer,
    )

    bot_msg = "Arkose Labs challenge detected on source 2"
    scraper_mock: Any = ctx.scraper
    scraper_mock.scrape_feed = AsyncMock(side_effect=[[post_t0], BotDetectionError(bot_msg)])

    graph = build_scout_graph()

    with patch("agent.graphs.scout_graph.humanized_dwell", new_callable=AsyncMock) as mock_dwell:
        result = await graph.ainvoke({}, config={"configurable": {"context": ctx}})

    # Exactly 2 scrape calls, 1 dwell call, source 3 never reached
    assert scraper_mock.scrape_feed.call_count == 2
    assert mock_dwell.call_count == 1

    # Invariant: posts must be cleared to prevent processing posts when account is flagged
    assert result.get("posts") == []
    assert result["status"] == "halted_bot_detection"

    # Circuit breaker tripped
    halted, reason = is_halted(challenger_test_repo, ctx.settings)
    assert halted is True
    assert reason is not None and bot_msg in reason


# ---------------------------------------------------------------------------
# Objective 5: ScrapeError Isolation
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_obj5_scrape_error_on_target1_isolated_target2_scraped(
    challenger_context: GraphContext,
) -> None:
    """Obj 5: ScrapeError on target 0 is isolated; dwell occurs; target 1 is scraped successfully; workflow proceeds."""
    post_t1 = _make_dummy_post("t1_success")

    settings = challenger_context.settings.model_copy(
        update={
            "scout_target_urls": [
                "https://www.linkedin.com/feed/hashtag/?keywords=broken_feed",
                "https://www.linkedin.com/feed/hashtag/?keywords=healthy_feed",
            ],
        }
    )
    ctx = GraphContext(
        settings=settings,
        llm=challenger_context.llm,
        state_store=challenger_context.state_store,
        telegram=challenger_context.telegram,
        scraper=challenger_context.scraper,
        enforcer=challenger_context.enforcer,
    )

    scraper_mock: Any = ctx.scraper
    scraper_mock.scrape_feed = AsyncMock(
        side_effect=[
            ScrapeError("Selector drift: feed container missing"),
            [post_t1],
        ]
    )

    graph = build_scout_graph()

    with patch("agent.graphs.scout_graph.humanized_dwell", new_callable=AsyncMock) as mock_dwell:
        result = await graph.ainvoke({}, config={"configurable": {"context": ctx}})

    # Both targets attempted, 1 dwell between them
    assert scraper_mock.scrape_feed.call_count == 2
    assert mock_dwell.call_count == 1

    # Posts collected from target 1
    assert len(result.get("posts", [])) == 1
    assert result["posts"][0].post_urn == "urn:li:activity:t1_success"

    # Errors isolated and recorded
    assert any("Selector drift" in err for err in result.get("errors", []))

    # Downstream workflow proceeded: triage and draft were called
    llm_mock: Any = ctx.llm
    assert llm_mock.evaluate_post.called
    assert llm_mock.draft_comment.called

    # Pending item persisted
    assert len(result.get("pending_items", [])) == 1


@pytest.mark.asyncio
async def test_obj5_scrape_error_in_middle_target_isolated(
    challenger_context: GraphContext,
) -> None:
    """Obj 5: Target 0 succeeds, Target 1 fails with ScrapeError, Target 2 succeeds.

    All 3 are attempted, both successful sets of posts are aggregated.
    """
    post_t0 = _make_dummy_post("t0_success")
    post_t2 = _make_dummy_post("t2_success")

    settings = challenger_context.settings.model_copy(
        update={
            "scout_target_urls": [
                "https://www.linkedin.com/feed/hashtag/?keywords=feed0",
                "https://www.linkedin.com/feed/hashtag/?keywords=feed1_drifted",
                "https://www.linkedin.com/feed/hashtag/?keywords=feed2",
            ],
            "max_suggestions_per_run": 5,
        }
    )
    ctx = GraphContext(
        settings=settings,
        llm=challenger_context.llm,
        state_store=challenger_context.state_store,
        telegram=challenger_context.telegram,
        scraper=challenger_context.scraper,
        enforcer=challenger_context.enforcer,
    )

    scraper_mock: Any = ctx.scraper
    scraper_mock.scrape_feed = AsyncMock(
        side_effect=[
            [post_t0],
            ScrapeError("Feed 1 network timeout"),
            [post_t2],
        ]
    )

    graph = build_scout_graph()

    with patch("agent.graphs.scout_graph.humanized_dwell", new_callable=AsyncMock) as mock_dwell:
        result = await graph.ainvoke({}, config={"configurable": {"context": ctx}})

    assert scraper_mock.scrape_feed.call_count == 3
    assert mock_dwell.call_count == 2
    assert len(result.get("posts", [])) == 2
    urns = {p.post_urn for p in result["posts"]}
    assert urns == {"urn:li:activity:t0_success", "urn:li:activity:t2_success"}
    assert any("Feed 1 network timeout" in err for err in result.get("errors", []))


@pytest.mark.asyncio
async def test_obj5_all_targets_scrape_error_halts_cleanly(
    challenger_context: GraphContext,
) -> None:
    """Obj 5 edge case: If ALL targets fail with ScrapeError, graph records all errors and routes to END."""
    settings = challenger_context.settings.model_copy(
        update={
            "scout_target_urls": [
                "https://www.linkedin.com/feed/hashtag/?keywords=fail1",
                "https://www.linkedin.com/feed/hashtag/?keywords=fail2",
            ],
        }
    )
    ctx = GraphContext(
        settings=settings,
        llm=challenger_context.llm,
        state_store=challenger_context.state_store,
        telegram=challenger_context.telegram,
        scraper=challenger_context.scraper,
        enforcer=challenger_context.enforcer,
    )

    scraper_mock: Any = ctx.scraper
    scraper_mock.scrape_feed = AsyncMock(
        side_effect=[
            ScrapeError("Error 1"),
            ScrapeError("Error 2"),
        ]
    )

    graph = build_scout_graph()

    with patch("agent.graphs.scout_graph.humanized_dwell", new_callable=AsyncMock) as mock_dwell:
        result = await graph.ainvoke({}, config={"configurable": {"context": ctx}})

    assert scraper_mock.scrape_feed.call_count == 2
    assert mock_dwell.call_count == 1
    assert result.get("posts") == []
    assert result.get("status") == "scrape_error"
    assert len(result.get("errors", [])) == 2

    # LLM never invoked because no posts
    llm_mock: Any = ctx.llm
    assert not llm_mock.evaluate_post.called


@pytest.mark.asyncio
async def test_obj4_session_expired_halts_multi_target_immediately(
    challenger_context: GraphContext,
) -> None:
    """SessionExpiredError on target 0 must halt immediately, notify Telegram, and skip remaining targets."""
    settings = challenger_context.settings.model_copy(
        update={
            "scout_target_urls": [
                "https://www.linkedin.com/feed/hashtag/?keywords=t0",
                "https://www.linkedin.com/feed/hashtag/?keywords=t1",
            ],
        }
    )
    ctx = GraphContext(
        settings=settings,
        llm=challenger_context.llm,
        state_store=challenger_context.state_store,
        telegram=challenger_context.telegram,
        scraper=challenger_context.scraper,
        enforcer=challenger_context.enforcer,
    )

    scraper_mock: Any = ctx.scraper
    scraper_mock.scrape_feed = AsyncMock(
        side_effect=SessionExpiredError("Scraper redirected to authwall")
    )

    telegram_mock: Any = ctx.telegram

    graph = build_scout_graph()

    with patch("agent.graphs.scout_graph.humanized_dwell", new_callable=AsyncMock) as mock_dwell:
        result = await graph.ainvoke({}, config={"configurable": {"context": ctx}})

    assert scraper_mock.scrape_feed.call_count == 1
    assert mock_dwell.call_count == 0
    assert result.get("status") == "session_expired"
    assert result.get("posts") == []
    assert telegram_mock.send_notification.called
    assert "session expired" in telegram_mock.send_notification.call_args[0][0].lower()


def test_edge_case_cross_source_deduplication(challenger_context: GraphContext) -> None:
    """Verify deduplication when target_hashtags produces same URL as explicit scout_target_urls."""
    from agent.graphs.scout_graph import get_scout_target_sources

    settings = challenger_context.settings.model_copy(
        update={
            "scout_target_urls": [
                "https://www.linkedin.com/feed/hashtag/?keywords=python",
            ],
            "target_hashtags": ["python", "#PYTHON"],
        }
    )
    sources = get_scout_target_sources(settings)
    assert len(sources) == 1
    assert sources[0] == "https://www.linkedin.com/feed/hashtag/?keywords=python"
