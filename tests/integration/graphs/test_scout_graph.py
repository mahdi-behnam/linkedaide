"""Integration tests for ScoutGraph topology, routing, and side effects."""

from __future__ import annotations

import subprocess
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest
from pydantic import SecretStr

from agent.config import Settings
from agent.graphs.scout_graph import build_scout_graph
from agent.graphs.state import GraphContext, ScoutState
from agent.models.schemas import CommentDraft, PostRecord, RiskFlag, TriageResult
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
