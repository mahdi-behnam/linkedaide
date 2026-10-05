"""Integration tests for ThreadMonitorGraph topology, routing, and persistence."""

from __future__ import annotations

import subprocess
from pathlib import Path
from unittest.mock import AsyncMock

import pytest
from pydantic import SecretStr

from agent.config import Settings
from agent.graphs import (
    GraphContext,
    ThreadMonitorState,
    build_thread_monitor_graph,
)
from agent.models import (
    ActiveThreadRecord,
    CommentDraft,
    EngagementStyle,
    ReplyTriageResult,
    ThreadReplyItem,
)
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
def thread_context(test_repo: Path) -> GraphContext:
    settings = Settings(
        nvidia_nim_api_key=SecretStr("nvapi-test"),
        nim_model_primary="primary-model",
        nim_model_fallback="fallback-model",
        telegram_bot_token=SecretStr("123:token"),
        telegram_authorized_chat_id=12345,
        user_focus_areas=["AI", "Python"],
        state_dir=test_repo / "state",
        dry_run=False,
    )
    state_store = GitStateStore(test_repo)
    return GraphContext(
        settings=settings,
        state_store=state_store,
    )


@pytest.mark.asyncio
async def test_thread_monitor_graph_halted(thread_context: GraphContext) -> None:
    """Graph halts immediately when agent_paused is set."""
    paused_settings = thread_context.settings.model_copy(update={"agent_paused": True})
    paused_context = GraphContext(
        settings=paused_settings,
        state_store=thread_context.state_store,
    )
    graph = build_thread_monitor_graph()
    initial_state: ThreadMonitorState = {}
    result = await graph.ainvoke(
        initial_state, config={"configurable": {"context": paused_context}}
    )

    assert result.get("status") == "halted"
    assert "paused" in (result.get("halted_reason") or "").lower()


@pytest.mark.asyncio
async def test_thread_monitor_graph_no_active_threads(thread_context: GraphContext) -> None:
    """Graph routes to END when no active threads are tracked."""
    graph = build_thread_monitor_graph()
    initial_state: ThreadMonitorState = {}
    result = await graph.ainvoke(
        initial_state, config={"configurable": {"context": thread_context}}
    )

    assert result.get("status") == "threads_loaded"
    assert result.get("active_threads") == []


@pytest.mark.asyncio
async def test_thread_monitor_graph_no_replies_found(thread_context: GraphContext) -> None:
    """Graph stops after inspecting when no new replies are discovered."""
    assert thread_context.state_store is not None
    thread = ActiveThreadRecord(
        id="th-1",
        post_url="https://linkedin.com/feed/update/urn:li:activity:123",
        post_urn="urn:li:activity:123",
        our_comment_urn="urn:li:comment:456",
        our_comment_text="Our insightful comment",
        post_author="Alice",
        status="active",
    )
    thread_context.state_store.save_active_thread(thread)

    mock_executor = AsyncMock()
    mock_executor.inspect_comment_replies.return_value = []

    context = GraphContext(
        settings=thread_context.settings,
        state_store=thread_context.state_store,
        executor=mock_executor,
    )

    graph = build_thread_monitor_graph()
    result = await graph.ainvoke({}, config={"configurable": {"context": context}})

    assert result.get("status") == "inspected"
    assert result.get("discovered_replies") == []
    mock_executor.inspect_comment_replies.assert_awaited_once()


@pytest.mark.asyncio
async def test_thread_monitor_graph_triage_ignore(thread_context: GraphContext) -> None:
    """Graph stops after triage when replies are recommended to be ignored."""
    assert thread_context.state_store is not None
    thread = ActiveThreadRecord(
        id="th-2",
        post_url="https://linkedin.com/feed/update/urn:li:activity:456",
        post_urn="urn:li:activity:456",
        our_comment_urn="urn:li:comment:789",
        our_comment_text="Our original comment",
        post_author="Bob",
        status="active",
    )
    thread_context.state_store.save_active_thread(thread)

    reply = ThreadReplyItem(
        reply_urn="urn:li:comment:999",
        parent_comment_urn="urn:li:comment:789",
        author_name="Charlie",
        reply_text="Thanks!",
    )

    mock_executor = AsyncMock()
    mock_executor.inspect_comment_replies.return_value = [reply]

    mock_llm = AsyncMock()
    mock_llm.triage_thread_reply.return_value = ReplyTriageResult(
        recommendation="ignore",
        confidence=0.9,
        reasoning="Generic praise, no substance",
    )

    context = GraphContext(
        settings=thread_context.settings,
        state_store=thread_context.state_store,
        executor=mock_executor,
        llm=mock_llm,
    )

    graph = build_thread_monitor_graph()
    result = await graph.ainvoke({}, config={"configurable": {"context": context}})

    assert result.get("status") == "triaged"
    assert len(result.get("triage_results", [])) == 1
    mock_llm.draft_thread_reply.assert_not_called()


@pytest.mark.asyncio
async def test_thread_monitor_graph_full_success_flow(thread_context: GraphContext) -> None:
    """Graph executes end-to-end: discovers replies, triages, drafts, persists, and notifies."""
    assert thread_context.state_store is not None
    thread = ActiveThreadRecord(
        id="th-3",
        post_url="https://linkedin.com/feed/update/urn:li:activity:789",
        post_urn="urn:li:activity:789",
        our_comment_urn="urn:li:comment:101",
        our_comment_text="Original observation about distributed consensus",
        post_author="Dave",
        status="active",
    )
    thread_context.state_store.save_active_thread(thread)

    reply = ThreadReplyItem(
        reply_urn="urn:li:comment:202",
        parent_comment_urn="urn:li:comment:101",
        author_name="Eve",
        author_headline="Staff Engineer",
        reply_text="How do you handle split-brain in that scenario?",
    )

    mock_executor = AsyncMock()
    mock_executor.inspect_comment_replies.return_value = [reply]

    mock_llm = AsyncMock()
    mock_llm.triage_thread_reply.return_value = ReplyTriageResult(
        recommendation="reply",
        confidence=0.95,
        reasoning="Substantive technical inquiry on partition tolerance",
        engagement_style=EngagementStyle.TECHNICAL_DEEP_DIVE,
    )
    mock_llm.draft_thread_reply.return_value = CommentDraft(
        draft_comment="We employ generation clocks combined with raft leases to avoid split-brain.",
        topic_tags=["consensus", "raft"],
        engagement_style=EngagementStyle.TECHNICAL_DEEP_DIVE,
    )

    mock_telegram = AsyncMock()
    mock_telegram.send_suggestion.return_value = 5544

    context = GraphContext(
        settings=thread_context.settings,
        state_store=thread_context.state_store,
        executor=mock_executor,
        llm=mock_llm,
        telegram=mock_telegram,
    )

    graph = build_thread_monitor_graph()
    result = await graph.ainvoke({}, config={"configurable": {"context": context}})

    assert result.get("status") == "completed"
    assert result.get("queued_count") == 1
    pending_items = result.get("pending_items", [])
    assert len(pending_items) == 1
    pending = pending_items[0]
    assert pending.action_type == "approve_reply"
    assert pending.author_name == "Eve"
    assert pending.telegram_message_id == 5544
    assert "raft leases" in pending.draft_text

    # Verify persisted in durable state store
    persisted = thread_context.state_store.read_pending(pending.item_id)
    assert persisted is not None
    assert persisted.item_id == pending.item_id
    assert persisted.telegram_message_id == 5544
