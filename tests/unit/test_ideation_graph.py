"""Unit and graph integration tests for IdeationGraph nodes, routing, and persistence."""

from __future__ import annotations

import subprocess
from datetime import UTC, datetime
from pathlib import Path
from typing import cast
from unittest.mock import AsyncMock, MagicMock

import pytest
from langchain_core.runnables import RunnableConfig
from langgraph.graph import END
from pydantic import SecretStr

from agent.config import Settings
from agent.graphs.ideation_graph import (
    build_ideation_graph,
    check_halted,
    filter_and_rank,
    generate_ideas,
    load_context,
    persist_pending,
    route_after_filter,
    route_after_generate,
    route_after_halt_check,
    send_suggestions,
)
from agent.graphs.state import GraphContext, IdeationState
from agent.models.schemas import HistoryEntry, PendingAction, PostIdea
from agent.safety.rate_limiter import DailyCapEnforcer
from agent.state.store import GitStateStore


def _make_config(context: GraphContext) -> RunnableConfig:
    return cast(RunnableConfig, {"configurable": {"context": context}})


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
        user_focus_areas=["AI Agents", "Python Systems"],
        max_suggestions_per_run=2,
        state_dir=test_repo / "state",
        dry_run=False,
    )
    state_store = GitStateStore(test_repo)
    enforcer = DailyCapEnforcer(settings)
    return GraphContext(
        settings=settings,
        state_store=state_store,
        enforcer=enforcer,
    )


# ============================================================================
# 1. check_halted Tests
# ============================================================================


@pytest.mark.asyncio
async def test_check_halted_when_active(mock_context: GraphContext) -> None:
    config = _make_config(mock_context)
    state: IdeationState = {}
    result = await check_halted(state, config)
    assert result["status"] == "active"
    assert result["halted_reason"] is None


@pytest.mark.asyncio
async def test_check_halted_when_paused(mock_context: GraphContext) -> None:
    paused_settings = mock_context.settings.model_copy(update={"agent_paused": True})
    paused_context = GraphContext(
        settings=paused_settings,
        state_store=mock_context.state_store,
        enforcer=mock_context.enforcer,
    )
    config = _make_config(paused_context)
    state: IdeationState = {}
    result = await check_halted(state, config)
    assert result["status"] == "halted"
    assert "paused" in result["halted_reason"].lower()


# ============================================================================
# 2. load_context Tests
# ============================================================================


@pytest.mark.asyncio
async def test_load_context_extracts_focus_areas_and_topics(
    mock_context: GraphContext,
) -> None:
    assert mock_context.state_store is not None
    # Add a pending action with a post excerpt
    pending = PendingAction(
        item_id="item_pend_1",
        action_type="approve_post",
        created_at=datetime.now(UTC),
        post_urn="",
        post_url="",
        author_name="",
        post_excerpt="Existing Agent Architecture",
        draft_text="Existing Agent Architecture\n\nDeep dive into agent design.",
        confidence=1.0,
        reasoning="Relevant topic",
        telegram_chat_id=12345,
    )
    mock_context.state_store.write_pending(pending)

    # Add a history entry
    entry = HistoryEntry(
        item_id="hist_topic_1",
        action_type="approve_post",
        final_status="executed_success",
        decided_at=datetime.now(UTC),
        executed_at=datetime.now(UTC),
    )
    mock_context.state_store.append_history(entry)

    config = _make_config(mock_context)
    state: IdeationState = {}
    result = await load_context(state, config)

    assert result["status"] == "context_loaded"
    assert result["user_focus_areas"] == ["AI Agents", "Python Systems"]
    assert "Existing Agent Architecture" in result["recent_topics"]
    assert "hist_topic_1" in result["recent_topics"]


@pytest.mark.asyncio
async def test_load_context_handles_missing_state_store(mock_context: GraphContext) -> None:
    no_store_context = GraphContext(
        settings=mock_context.settings,
        state_store=None,
        enforcer=mock_context.enforcer,
    )
    config = _make_config(no_store_context)
    state: IdeationState = {}
    result = await load_context(state, config)

    assert result["status"] == "context_loaded"
    assert result["user_focus_areas"] == ["AI Agents", "Python Systems"]
    assert result["recent_topics"] == []


# ============================================================================
# 3. generate_ideas Tests
# ============================================================================


@pytest.mark.asyncio
async def test_generate_ideas_without_llm_service(mock_context: GraphContext) -> None:
    config = _make_config(mock_context)
    state: IdeationState = {"user_focus_areas": ["AI"], "recent_topics": []}
    result = await generate_ideas(state, config)

    assert result["status"] == "llm_unavailable"
    assert result["candidate_ideas"] == []
    assert len(result["errors"]) == 1
    assert "No LLM service" in result["errors"][0]


@pytest.mark.asyncio
async def test_generate_ideas_success(mock_context: GraphContext) -> None:
    mock_llm = MagicMock()
    valid_idea = PostIdea(
        should_post=True,
        headline="Decoupling Graph Workflows in Agentic Systems",
        draft_post_text="Here is why decoupled state graphs outperform monoliths...",
        hashtags=["#AI", "#Python"],
        reasoning="Timely software architecture insight",
    )
    mock_llm.draft_post_idea = AsyncMock(return_value=valid_idea)

    ctx = GraphContext(
        settings=mock_context.settings,
        llm=mock_llm,
        state_store=mock_context.state_store,
        enforcer=mock_context.enforcer,
    )
    config = _make_config(ctx)
    state: IdeationState = {
        "user_focus_areas": ["AI Agents"],
        "recent_topics": ["Basic LLMs"],
    }

    result = await generate_ideas(state, config)
    assert result["status"] == "ideas_generated"
    assert len(result["candidate_ideas"]) == 1
    assert result["candidate_ideas"][0].headline == "Decoupling Graph Workflows in Agentic Systems"
    mock_llm.draft_post_idea.assert_awaited_once()


@pytest.mark.asyncio
async def test_generate_ideas_should_not_post(mock_context: GraphContext) -> None:
    mock_llm = MagicMock()
    no_post_idea = PostIdea(
        should_post=False,
        headline="",
        draft_post_text="",
        hashtags=[],
        reasoning="Market conditions or topics saturated",
    )
    mock_llm.draft_post_idea = AsyncMock(return_value=no_post_idea)

    ctx = GraphContext(
        settings=mock_context.settings,
        llm=mock_llm,
        state_store=mock_context.state_store,
        enforcer=mock_context.enforcer,
    )
    config = _make_config(ctx)
    state: IdeationState = {"user_focus_areas": ["AI"], "recent_topics": []}

    result = await generate_ideas(state, config)
    assert result["status"] == "ideas_generated"
    assert len(result["candidate_ideas"]) == 1
    assert result["candidate_ideas"][0].should_post is False


@pytest.mark.asyncio
async def test_generate_ideas_handles_llm_exception(mock_context: GraphContext) -> None:
    mock_llm = MagicMock()
    mock_llm.draft_post_idea = AsyncMock(side_effect=RuntimeError("NIM Provider 503"))

    ctx = GraphContext(
        settings=mock_context.settings,
        llm=mock_llm,
        state_store=mock_context.state_store,
        enforcer=mock_context.enforcer,
    )
    config = _make_config(ctx)
    state: IdeationState = {"user_focus_areas": ["AI"], "recent_topics": []}

    result = await generate_ideas(state, config)
    assert result["status"] == "no_ideas_generated"
    assert result["candidate_ideas"] == []
    assert any("NIM Provider 503" in err for err in result["errors"])


# ============================================================================
# 4. filter_and_rank Tests
# ============================================================================


@pytest.mark.asyncio
async def test_filter_and_rank_filters_and_deduplicates(mock_context: GraphContext) -> None:
    candidates = [
        # Valid idea
        PostIdea(
            should_post=True,
            headline="Agent Memory Patterns",
            draft_post_text="Exploring short-term vs long-term memory in LLMs.",
            hashtags=["#Agents", "#Architecture"],
            reasoning="Strong technical interest",
        ),
        # Unwanted: should_post is False
        PostIdea(
            should_post=False,
            headline="Generic Tech News",
            draft_post_text="Some text",
            hashtags=[],
            reasoning="Not relevant",
        ),
        # Unwanted: empty draft text
        PostIdea(
            should_post=True,
            headline="Empty Post Idea",
            draft_post_text="   ",
            hashtags=[],
            reasoning="Missing body",
        ),
        # Unwanted: duplicate headline in recent topics
        PostIdea(
            should_post=True,
            headline="Existing Agent Architecture",
            draft_post_text="A rehash of existing architecture.",
            hashtags=["#Dupe"],
            reasoning="Duplicate",
        ),
    ]

    state: IdeationState = {
        "candidate_ideas": candidates,
        "recent_topics": ["Existing Agent Architecture"],
    }
    config = _make_config(mock_context)

    result = await filter_and_rank(state, config)
    assert result["status"] == "filtered"
    assert len(result["filtered_ideas"]) == 1
    assert result["filtered_ideas"][0].headline == "Agent Memory Patterns"

    pending_items = result["pending_items"]
    assert len(pending_items) == 1
    item = pending_items[0]
    assert item.action_type == "approve_post"
    assert item.post_excerpt == "Agent Memory Patterns"
    assert "Exploring short-term vs long-term memory" in item.draft_text
    assert "#Agents #Architecture" in item.draft_text
    assert item.telegram_chat_id == 12345
    assert item.confidence == 1.0


# ============================================================================
# 5. persist_pending Tests
# ============================================================================


@pytest.mark.asyncio
async def test_persist_pending_success(mock_context: GraphContext) -> None:
    assert mock_context.state_store is not None
    pending = PendingAction(
        item_id="pend_write_1",
        action_type="approve_post",
        created_at=datetime.now(UTC),
        post_urn="",
        post_url="",
        author_name="",
        post_excerpt="Persist Test",
        draft_text="Body of post",
        confidence=1.0,
        reasoning="Test reason",
        telegram_chat_id=12345,
    )
    state: IdeationState = {"pending_items": [pending]}
    config = _make_config(mock_context)

    result = await persist_pending(state, config)
    assert result["status"] == "persisted"
    assert len(result["pending_items"]) == 1

    loaded = mock_context.state_store.read_pending("pend_write_1")
    assert loaded is not None
    assert loaded.post_excerpt == "Persist Test"


@pytest.mark.asyncio
async def test_persist_pending_missing_store(mock_context: GraphContext) -> None:
    no_store_context = GraphContext(
        settings=mock_context.settings,
        state_store=None,
        enforcer=mock_context.enforcer,
    )
    pending = PendingAction(
        item_id="pend_fail_1",
        action_type="approve_post",
        created_at=datetime.now(UTC),
        draft_text="Body",
        post_excerpt="Fail Test",
    )
    state: IdeationState = {"pending_items": [pending]}
    config = _make_config(no_store_context)

    result = await persist_pending(state, config)
    assert result["status"] == "persist_skipped"
    assert any("No state_store" in err for err in result["errors"])


# ============================================================================
# 6. send_suggestions Tests
# ============================================================================


@pytest.mark.asyncio
async def test_send_suggestions_dry_run(mock_context: GraphContext) -> None:
    dry_settings = mock_context.settings.model_copy(update={"dry_run": True})
    mock_telegram = AsyncMock()
    dry_context = GraphContext(
        settings=dry_settings,
        state_store=mock_context.state_store,
        telegram=mock_telegram,
        enforcer=mock_context.enforcer,
    )
    pending = PendingAction(
        item_id="dry_item_1",
        action_type="approve_post",
        created_at=datetime.now(UTC),
        draft_text="Body",
        post_excerpt="Dry run test",
    )
    state: IdeationState = {"pending_items": [pending]}
    config = _make_config(dry_context)

    result = await send_suggestions(state, config)
    assert result["status"] == "completed_dry_run"
    assert len(result["pending_items"]) == 1
    mock_telegram.send_suggestion.assert_not_called()


@pytest.mark.asyncio
async def test_send_suggestions_live_delivery(mock_context: GraphContext) -> None:
    assert mock_context.state_store is not None
    mock_telegram = AsyncMock()
    mock_telegram.send_suggestion.return_value = 8802

    live_context = GraphContext(
        settings=mock_context.settings,
        state_store=mock_context.state_store,
        telegram=mock_telegram,
        enforcer=mock_context.enforcer,
    )

    pending = PendingAction(
        item_id="live_item_1",
        action_type="approve_post",
        created_at=datetime.now(UTC),
        draft_text="Body",
        post_excerpt="Live post suggestion",
        telegram_chat_id=12345,
    )
    mock_context.state_store.write_pending(pending)

    state: IdeationState = {"pending_items": [pending]}
    config = _make_config(live_context)

    result = await send_suggestions(state, config)
    assert result["status"] == "completed"
    assert len(result["pending_items"]) == 1
    assert result["pending_items"][0].telegram_message_id == 8802

    # Check that state_store was updated with new message_id
    updated_in_store = mock_context.state_store.read_pending("live_item_1")
    assert updated_in_store is not None
    assert updated_in_store.telegram_message_id == 8802

    # Verify suggestion count was incremented
    counters = mock_context.state_store.load_daily_counters()
    assert counters.suggestions_sent == 1


# ============================================================================
# 7. Routing Functions Tests
# ============================================================================


def test_route_after_halt_check() -> None:
    assert route_after_halt_check({"halted_reason": "Paused"}) == END
    assert route_after_halt_check({"halted_reason": None}) == "load_context"


def test_route_after_generate() -> None:
    assert route_after_generate({"candidate_ideas": []}) == END
    valid_idea = PostIdea(should_post=True, draft_post_text="Hi")
    assert route_after_generate({"candidate_ideas": [valid_idea]}) == "filter_and_rank"


def test_route_after_filter() -> None:
    assert route_after_filter({"pending_items": []}) == END
    dummy_pending = PendingAction(
        item_id="1", action_type="approve_post", draft_text="t", post_excerpt="e"
    )
    assert route_after_filter({"pending_items": [dummy_pending]}) == "persist_pending"


# ============================================================================
# 8. Full Graph End-to-End Tests
# ============================================================================


@pytest.mark.asyncio
async def test_full_graph_halted_routes_to_end(mock_context: GraphContext) -> None:
    paused_settings = mock_context.settings.model_copy(update={"agent_paused": True})
    paused_context = GraphContext(
        settings=paused_settings,
        state_store=mock_context.state_store,
        enforcer=mock_context.enforcer,
    )
    graph = build_ideation_graph()
    initial_state: IdeationState = {}

    result = await graph.ainvoke(
        initial_state, config={"configurable": {"context": paused_context}}
    )
    assert result["status"] == "halted"
    assert result.get("pending_items") is None or result.get("pending_items") == []


@pytest.mark.asyncio
async def test_full_graph_success_end_to_end(mock_context: GraphContext) -> None:
    assert mock_context.state_store is not None
    mock_llm = MagicMock()
    idea = PostIdea(
        should_post=True,
        headline="Scaling Autonomous Workflows",
        draft_post_text="How to design resilient graphs with LangGraph and HITL safety.",
        hashtags=["#Python", "#LangGraph"],
        reasoning="Key architecture trend",
    )
    mock_llm.draft_post_idea = AsyncMock(return_value=idea)

    mock_telegram = AsyncMock()
    mock_telegram.send_suggestion.return_value = 9911

    full_context = GraphContext(
        settings=mock_context.settings,
        llm=mock_llm,
        state_store=mock_context.state_store,
        telegram=mock_telegram,
        enforcer=mock_context.enforcer,
    )

    graph = build_ideation_graph()
    initial_state: IdeationState = {}
    result = await graph.ainvoke(initial_state, config={"configurable": {"context": full_context}})

    assert result["status"] == "completed"
    assert len(result["pending_items"]) == 1
    created_item = result["pending_items"][0]
    assert created_item.action_type == "approve_post"
    assert created_item.telegram_message_id == 9911

    # Verify item is in state_store
    stored_item = mock_context.state_store.read_pending(created_item.item_id)
    assert stored_item is not None
    assert stored_item.post_excerpt == "Scaling Autonomous Workflows"


@pytest.mark.asyncio
async def test_full_graph_dry_run_execution(mock_context: GraphContext) -> None:
    assert mock_context.state_store is not None
    dry_settings = mock_context.settings.model_copy(update={"dry_run": True})
    mock_llm = MagicMock()
    idea = PostIdea(
        should_post=True,
        headline="Dry Run Test Post",
        draft_post_text="Testing dry run post drafting without telegram delivery.",
        hashtags=["#Test"],
        reasoning="Testing dry run",
    )
    mock_llm.draft_post_idea = AsyncMock(return_value=idea)
    mock_telegram = AsyncMock()

    dry_context = GraphContext(
        settings=dry_settings,
        llm=mock_llm,
        state_store=mock_context.state_store,
        telegram=mock_telegram,
        enforcer=mock_context.enforcer,
    )

    graph = build_ideation_graph()
    initial_state: IdeationState = {}
    result = await graph.ainvoke(initial_state, config={"configurable": {"context": dry_context}})

    assert result["status"] == "completed_dry_run"
    assert len(result["pending_items"]) == 1
    mock_telegram.send_suggestion.assert_not_called()


@pytest.mark.asyncio
async def test_full_graph_should_post_false_routes_to_end(mock_context: GraphContext) -> None:
    mock_llm = MagicMock()
    idea = PostIdea(
        should_post=False,
        headline="",
        draft_post_text="",
        hashtags=[],
        reasoning="No ideas today",
    )
    mock_llm.draft_post_idea = AsyncMock(return_value=idea)
    mock_telegram = AsyncMock()

    ctx = GraphContext(
        settings=mock_context.settings,
        llm=mock_llm,
        state_store=mock_context.state_store,
        telegram=mock_telegram,
        enforcer=mock_context.enforcer,
    )

    graph = build_ideation_graph()
    initial_state: IdeationState = {}
    result = await graph.ainvoke(initial_state, config={"configurable": {"context": ctx}})

    # filter_and_rank filters it out, so pending_items is empty and routes to END
    assert result.get("pending_items") == []
    mock_telegram.send_suggestion.assert_not_called()
