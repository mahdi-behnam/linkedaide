"""Integration tests for ExecuteGraph approval, rejection, and safety gates."""

from __future__ import annotations

import subprocess
from datetime import UTC, datetime, timedelta
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest
from pydantic import SecretStr

from agent.config import Settings
from agent.graphs.execute_graph import build_execute_graph
from agent.graphs.state import ExecuteState, GraphContext
from agent.models import (
    ConnectionRequestAction,
    ExecutionResult,
    PendingAction,
    ScheduledPost,
)
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
        user_focus_areas=["AI"],
        max_comments_per_day=5,
        pending_action_ttl_hours=20,
        state_dir=test_repo / "state",
        dry_run=True,
    )
    state_store = GitStateStore(test_repo)
    enforcer = DailyCapEnforcer(settings)

    telegram = MagicMock()
    telegram.is_authorized = MagicMock(return_value=True)
    telegram.edit_to_outcome = AsyncMock()

    executor = MagicMock()
    executor.verify_login = AsyncMock(return_value=True)
    executor.verify_post_exists = AsyncMock(return_value=True)
    executor.post_comment = AsyncMock(
        return_value=ExecutionResult(
            success=True,
            action_type="approve_comment",
            item_id="item1",
            comment_text="Sample",
            screenshot_path="path.png",
            error=None,
            executed_at=datetime.now(UTC),
        )
    )
    executor.post_thread_reply = AsyncMock(
        return_value=ExecutionResult(
            success=True,
            action_type="approve_reply",
            item_id="reply1",
            comment_text="Sample reply",
            screenshot_path="path.png",
            error=None,
            executed_at=datetime.now(UTC),
        )
    )
    executor.send_connection_request = AsyncMock(
        return_value=ExecutionResult(
            success=True,
            action_type="approve_connection",
            item_id="conn1",
            comment_text="Note",
            screenshot_path="conn.png",
            error=None,
            executed_at=datetime.now(UTC),
        )
    )
    executor.create_post = AsyncMock(
        return_value=ExecutionResult(
            success=True,
            action_type="approve_post",
            item_id="post1",
            comment_text=None,
            post_text="Sample post",
            screenshot_path="post.png",
            error=None,
            executed_at=datetime.now(UTC),
        )
    )
    executor.react_to_post = AsyncMock(return_value=True)

    return GraphContext(
        settings=settings,
        state_store=state_store,
        telegram=telegram,
        executor=executor,
        enforcer=enforcer,
    )


@pytest.mark.asyncio
async def test_execute_graph_missing_pending_item(mock_context: GraphContext) -> None:
    graph = build_execute_graph()
    state: ExecuteState = {
        "action": "approve",
        "item_id": "nonexistent_item",
        "telegram_chat_id": 12345,
        "telegram_message_id": 500,
    }

    result = await graph.ainvoke(state, config={"configurable": {"context": mock_context}})
    assert result["status"] == "already_handled"
    assert mock_context.telegram.edit_to_outcome.called  # type: ignore[union-attr]


@pytest.mark.asyncio
async def test_execute_graph_reject_action(mock_context: GraphContext) -> None:
    pending = PendingAction(
        item_id="rej001",
        action_type="approve_comment",
        created_at=datetime.now(UTC),
        post_urn="urn:li:activity:1",
        post_url="https://www.linkedin.com/feed/update/urn:li:activity:1/",
        author_name="Author",
        post_excerpt="Excerpt",
        draft_text="Draft",
        confidence=0.9,
        reasoning="Fit",
        telegram_chat_id=12345,
        telegram_message_id=501,
    )
    mock_context.state_store.write_pending(pending)  # type: ignore[union-attr]

    graph = build_execute_graph()
    state: ExecuteState = {
        "action": "reject",
        "item_id": "rej001",
        "telegram_chat_id": 12345,
        "telegram_message_id": 501,
    }

    result = await graph.ainvoke(state, config={"configurable": {"context": mock_context}})
    assert result["status"] == "rejected"
    assert mock_context.state_store.read_pending("rej001") is None  # type: ignore[union-attr]

    history = mock_context.state_store.read_history()  # type: ignore[union-attr]
    assert len(history) == 1
    assert history[0].final_status == "rejected"


@pytest.mark.asyncio
async def test_execute_graph_approve_success(mock_context: GraphContext) -> None:
    pending = PendingAction(
        item_id="app001",
        action_type="approve_comment",
        created_at=datetime.now(UTC),
        post_urn="urn:li:activity:2",
        post_url="https://www.linkedin.com/feed/update/urn:li:activity:2/",
        author_name="Author 2",
        post_excerpt="Excerpt 2",
        draft_text="Great comment draft",
        confidence=0.95,
        reasoning="Good match",
        telegram_chat_id=12345,
        telegram_message_id=502,
    )
    mock_context.state_store.write_pending(pending)  # type: ignore[union-attr]

    graph = build_execute_graph()
    state: ExecuteState = {
        "action": "approve",
        "item_id": "app001",
        "telegram_chat_id": 12345,
        "telegram_message_id": 502,
    }

    result = await graph.ainvoke(state, config={"configurable": {"context": mock_context}})
    assert result["status"] == "completed_success"
    assert mock_context.state_store.read_pending("app001") is None  # type: ignore[union-attr]

    counters = mock_context.state_store.load_daily_counters()  # type: ignore[union-attr]
    assert counters.comments_executed == 1


@pytest.mark.asyncio
async def test_execute_graph_expired_approval_rejected(mock_context: GraphContext) -> None:
    now = datetime.now(UTC)
    expired_pending = PendingAction(
        item_id="exp001",
        action_type="approve_comment",
        created_at=now - timedelta(hours=25),
        post_urn="urn:li:activity:3",
        post_url="https://www.linkedin.com/feed/update/urn:li:activity:3/",
        author_name="Author 3",
        post_excerpt="Excerpt 3",
        draft_text="Draft",
        confidence=0.85,
        reasoning="Reason",
        telegram_chat_id=12345,
        telegram_message_id=503,
    )
    mock_context.state_store.write_pending(expired_pending)  # type: ignore[union-attr]

    graph = build_execute_graph()
    state: ExecuteState = {
        "action": "approve",
        "item_id": "exp001",
        "telegram_chat_id": 12345,
        "telegram_message_id": 503,
    }

    result = await graph.ainvoke(state, config={"configurable": {"context": mock_context}})
    assert result["status"] == "failed"
    assert "expired" in result["error"].lower()
    assert not mock_context.executor.post_comment.called  # type: ignore[union-attr]


@pytest.mark.asyncio
async def test_execute_graph_approve_reply_success(mock_context: GraphContext) -> None:
    pending = PendingAction(
        item_id="reply001",
        action_type="approve_reply",
        created_at=datetime.now(UTC),
        post_urn="urn:li:comment:999",
        post_url="https://www.linkedin.com/feed/update/urn:li:activity:4/",
        author_name="Commenter",
        post_excerpt="Parent comment text",
        draft_text="Insightful follow-up reply",
        confidence=0.92,
        reasoning="Good context fit",
        telegram_chat_id=12345,
        telegram_message_id=504,
    )
    mock_context.state_store.write_pending(pending)  # type: ignore[union-attr]

    graph = build_execute_graph()
    state: ExecuteState = {
        "action": "approve",
        "item_id": "reply001",
        "telegram_chat_id": 12345,
        "telegram_message_id": 504,
    }

    result = await graph.ainvoke(state, config={"configurable": {"context": mock_context}})
    assert result["status"] == "completed_success"
    assert mock_context.state_store.read_pending("reply001") is None  # type: ignore[union-attr]
    assert mock_context.executor.post_thread_reply.called  # type: ignore[union-attr]
    assert not mock_context.executor.post_comment.called  # type: ignore[union-attr]

    counters = mock_context.state_store.load_daily_counters()  # type: ignore[union-attr]
    assert counters.comments_executed == 1
    call_args = mock_context.telegram.edit_to_outcome.call_args[0]  # type: ignore[union-attr]
    assert call_args[0] == 12345
    assert call_args[1] == 504
    assert "<b>✅ Successfully Replied on LinkedIn!</b>" in call_args[2]
    assert "View Your Comment on LinkedIn ↗" in call_args[2]


@pytest.mark.asyncio
async def test_execute_graph_approve_reply_cap_exceeded(mock_context: GraphContext) -> None:
    counters = mock_context.state_store.load_daily_counters()  # type: ignore[union-attr]
    counters.comments_executed = 5  # max is 5
    mock_context.state_store.save_daily_counters(counters)  # type: ignore[union-attr]

    pending = PendingAction(
        item_id="reply002",
        action_type="approve_reply",
        created_at=datetime.now(UTC),
        post_urn="urn:li:comment:888",
        post_url="https://www.linkedin.com/feed/update/urn:li:activity:5/",
        author_name="Commenter",
        post_excerpt="Parent comment text",
        draft_text="Another reply",
        confidence=0.90,
        reasoning="Good context fit",
        telegram_chat_id=12345,
        telegram_message_id=505,
    )
    mock_context.state_store.write_pending(pending)  # type: ignore[union-attr]

    graph = build_execute_graph()
    state: ExecuteState = {
        "action": "approve",
        "item_id": "reply002",
        "telegram_chat_id": 12345,
        "telegram_message_id": 505,
    }

    result = await graph.ainvoke(state, config={"configurable": {"context": mock_context}})
    assert result["status"] == "failed"
    assert "cap" in result["error"].lower()
    assert not mock_context.executor.post_thread_reply.called  # type: ignore[union-attr]


@pytest.mark.asyncio
async def test_execute_graph_approve_connection_success(mock_context: GraphContext) -> None:
    assert mock_context.state_store is not None
    conn_candidate = ConnectionRequestAction(
        id="conn1",
        profile_url="https://linkedin.com/in/test-conn",
        target_name="Bob Engineer",
        note_text="Let's connect!",
    )
    mock_context.state_store.add_connection_candidate(conn_candidate)

    initial_state: ExecuteState = {
        "action": "approve",
        "item_id": "conn1",
        "telegram_chat_id": 12345,
        "telegram_message_id": 506,
    }

    graph = build_execute_graph()
    result = await graph.ainvoke(initial_state, config={"configurable": {"context": mock_context}})

    assert result["status"] == "completed_success"
    assert mock_context.executor.send_connection_request.called  # type: ignore[union-attr]
    counters = mock_context.state_store.load_daily_counters()
    assert counters.connections_sent == 1
    call_args = mock_context.telegram.edit_to_outcome.call_args[0]  # type: ignore[union-attr]
    assert call_args[0] == 12345
    assert call_args[1] == 506
    assert "<b>✅ Sent Connection Invitation to Bob Engineer!</b>" in call_args[2]
    assert "View Profile on LinkedIn ↗" in call_args[2]


@pytest.mark.asyncio
async def test_execute_graph_approve_connection_cap_exceeded(mock_context: GraphContext) -> None:
    assert mock_context.state_store is not None
    counters = mock_context.state_store.load_daily_counters()
    counters.connections_sent = 10  # cap is 10
    mock_context.state_store.save_daily_counters(counters)

    conn_candidate = ConnectionRequestAction(
        id="conn2",
        profile_url="https://linkedin.com/in/test-conn-2",
        target_name="Alice Architect",
        note_text="Hi Alice",
    )
    mock_context.state_store.add_connection_candidate(conn_candidate)

    initial_state: ExecuteState = {
        "action": "approve",
        "item_id": "conn2",
        "telegram_chat_id": 12345,
        "telegram_message_id": 507,
    }

    graph = build_execute_graph()
    result = await graph.ainvoke(initial_state, config={"configurable": {"context": mock_context}})

    assert result["status"] == "failed"
    assert "cap" in result["error"].lower()
    assert not mock_context.executor.send_connection_request.called  # type: ignore[union-attr]


@pytest.mark.asyncio
async def test_execute_graph_approve_scheduled_post_success(
    mock_context: GraphContext,
) -> None:
    assert mock_context.state_store is not None
    sched_post = ScheduledPost(
        id="sched_1",
        post_text="Excited to share our new system architecture update!",
        status="scheduled",
    )
    mock_context.state_store.save_scheduled_post(sched_post)

    initial_state: ExecuteState = {
        "action": "approve",
        "item_id": "sched_1",
        "telegram_chat_id": 12345,
        "telegram_message_id": 508,
    }

    graph = build_execute_graph()
    result = await graph.ainvoke(initial_state, config={"configurable": {"context": mock_context}})

    assert result["status"] == "completed_success"
    assert mock_context.executor.create_post.called  # type: ignore[union-attr]

    updated = mock_context.state_store.read_scheduled_post("sched_1")
    assert updated is not None
    assert updated.status == "published"


@pytest.mark.asyncio
async def test_execute_graph_reject_scheduled_post(
    mock_context: GraphContext,
) -> None:
    assert mock_context.state_store is not None
    sched_post = ScheduledPost(
        id="sched_2",
        post_text="Draft post that got cancelled.",
        status="scheduled",
    )
    mock_context.state_store.save_scheduled_post(sched_post)

    initial_state: ExecuteState = {
        "action": "reject",
        "item_id": "sched_2",
        "telegram_chat_id": 12345,
        "telegram_message_id": 509,
    }

    graph = build_execute_graph()
    result = await graph.ainvoke(initial_state, config={"configurable": {"context": mock_context}})

    assert result["status"] == "rejected"
    assert not mock_context.executor.create_post.called  # type: ignore[union-attr]

    updated = mock_context.state_store.read_scheduled_post("sched_2")
    assert updated is not None
    assert updated.status == "rejected"


@pytest.mark.asyncio
async def test_execute_graph_prescheduled_post_created_days_ago_executes_successfully(
    mock_context: GraphContext,
) -> None:
    assert mock_context.state_store is not None
    now = datetime.now(UTC)
    # Post created 3 days ago, scheduled for now
    sched_post = ScheduledPost(
        id="sched_old_1",
        post_text="Architectural update scheduled days ago.",
        status="scheduled",
        created_at=now - timedelta(days=3),
        scheduled_time=now,
    )
    mock_context.state_store.save_scheduled_post(sched_post)

    initial_state: ExecuteState = {
        "action": "approve",
        "item_id": "sched_old_1",
        "telegram_chat_id": 12345,
        "telegram_message_id": 510,
    }

    graph = build_execute_graph()
    result = await graph.ainvoke(initial_state, config={"configurable": {"context": mock_context}})

    assert result["status"] == "completed_success"
    assert mock_context.executor.create_post.called  # type: ignore[union-attr]

    updated = mock_context.state_store.read_scheduled_post("sched_old_1")
    assert updated is not None
    assert updated.status == "published"


@pytest.mark.asyncio
async def test_execute_graph_scheduled_post_failure_transitions_to_failed(
    mock_context: GraphContext,
) -> None:
    assert mock_context.state_store is not None
    sched_post = ScheduledPost(
        id="sched_fail_1",
        post_text="This post will encounter a browser error.",
        status="scheduled",
    )
    mock_context.state_store.save_scheduled_post(sched_post)

    # Force executor.create_post to fail
    mock_context.executor.create_post = AsyncMock(  # type: ignore[union-attr,method-assign]
        return_value=ExecutionResult(
            success=False,
            action_type="approve_post",
            item_id="sched_fail_1",
            comment_text=None,
            post_text="This post will encounter a browser error.",
            screenshot_path=None,
            error="Browser DOM submission timed out",
            executed_at=datetime.now(UTC),
        )
    )

    initial_state: ExecuteState = {
        "action": "approve",
        "item_id": "sched_fail_1",
        "telegram_chat_id": 12345,
        "telegram_message_id": 511,
    }

    graph = build_execute_graph()
    result = await graph.ainvoke(initial_state, config={"configurable": {"context": mock_context}})

    assert result["status"] == "failed"

    updated = mock_context.state_store.read_scheduled_post("sched_fail_1")
    assert updated is not None
    assert updated.status == "failed"


@pytest.mark.asyncio
async def test_execute_graph_connection_failure_transitions_to_failed(
    mock_context: GraphContext,
) -> None:
    assert mock_context.state_store is not None
    conn_candidate = ConnectionRequestAction(
        id="conn_fail_1",
        profile_url="https://linkedin.com/in/failed-target",
        target_name="Bob Builder",
        note_text="Hi Bob",
        status="approved",
    )
    mock_context.state_store.add_connection_candidate(conn_candidate)

    # Force executor.send_connection_request to fail
    mock_context.executor.send_connection_request = AsyncMock(  # type: ignore[union-attr,method-assign]
        return_value=ExecutionResult(
            success=False,
            action_type="approve_connection",
            item_id="conn_fail_1",
            comment_text="Hi Bob",
            post_text=None,
            screenshot_path=None,
            error="Target profile not found",
            executed_at=datetime.now(UTC),
        )
    )

    initial_state: ExecuteState = {
        "action": "approve",
        "item_id": "conn_fail_1",
        "telegram_chat_id": 12345,
        "telegram_message_id": 512,
    }

    graph = build_execute_graph()
    result = await graph.ainvoke(initial_state, config={"configurable": {"context": mock_context}})

    assert result["status"] == "failed"

    updated = mock_context.state_store.read_connection_candidate("conn_fail_1")
    assert updated is not None
    assert updated.status == "failed"


@pytest.mark.asyncio
async def test_execute_graph_approve_comment_indexes_voice_memory(
    mock_context: GraphContext,
) -> None:
    assert mock_context.state_store is not None
    pending = PendingAction(
        item_id="item_voice_1",
        action_type="approve_comment",
        created_at=datetime.now(UTC),
        post_urn="urn:li:activity:9999",
        post_url="https://www.linkedin.com/feed/update/urn:li:activity:9999/",
        author_name="Dave Distributed",
        post_excerpt="Discussion on raft log replication and leader elections.",
        draft_text="Leader election timeouts must be randomized to prevent split votes.",
        confidence=0.92,
        reasoning="Technical depth on distributed consensus",
        telegram_chat_id=12345,
        telegram_message_id=513,
    )
    mock_context.state_store.write_pending(pending)

    initial_state: ExecuteState = {
        "action": "approve",
        "item_id": "item_voice_1",
        "telegram_chat_id": 12345,
        "telegram_message_id": 513,
    }

    graph = build_execute_graph()
    result = await graph.ainvoke(initial_state, config={"configurable": {"context": mock_context}})

    assert result["status"] == "completed_success"
    assert mock_context.executor.post_comment.called  # type: ignore[union-attr]

    # Verify voice samples were durably persisted in state store
    samples = mock_context.state_store.load_dynamic_voice_samples()
    assert len(samples) >= 1
    assert any("split votes" in s.get("sample", "") for s in samples)


@pytest.mark.asyncio
async def test_execute_graph_approve_reaction(
    mock_context: GraphContext,
) -> None:
    assert mock_context.state_store is not None
    pending = PendingAction(
        item_id="item_react_1",
        action_type="approve_reaction",
        reaction_type="insightful",
        created_at=datetime.now(UTC),
        post_urn="urn:li:activity:8888",
        post_url="https://www.linkedin.com/feed/update/urn:li:activity:8888/",
        author_name="Alice Architect",
        post_excerpt="Great article on event-driven architecture.",
        draft_text="Reaction: Insightful",
        confidence=0.88,
        reasoning="Relevant architecture insight",
        telegram_chat_id=12345,
        telegram_message_id=514,
    )
    mock_context.state_store.write_pending(pending)

    initial_state: ExecuteState = {
        "action": "approve",
        "item_id": "item_react_1",
        "telegram_chat_id": 12345,
        "telegram_message_id": 514,
    }

    graph = build_execute_graph()
    result = await graph.ainvoke(initial_state, config={"configurable": {"context": mock_context}})

    assert result["status"] == "completed_success"
    mock_context.executor.react_to_post.assert_awaited_once_with(  # type: ignore[union-attr]
        reaction_type="insightful",
        item_id="item_react_1",
        post_url="https://www.linkedin.com/feed/update/urn:li:activity:8888/",
    )
    # Check that pending action was removed
    assert mock_context.state_store.read_pending("item_react_1") is None
    # Check history was recorded
    history = mock_context.state_store.read_history()
    assert any(
        h.item_id == "item_react_1" and h.final_status == "executed_success" for h in history
    )
